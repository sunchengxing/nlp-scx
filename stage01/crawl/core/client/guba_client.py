"""东方财富股吧 Playwright 客户端 — 只负责页面访问和数据提取，不关心存储

关键设计：
1. 全程复用同一个 page，只换 URL → 不会闪烁开新窗口
2. 检测到人机验证 → 暂停轮询拖动滑块，这个滑块如果是纯验证人机应该只需要0.5s左右就可以结束，会存在干扰项
但是如果是验证脚本就需要拖动长距离，需要0。7s左右不会有干扰项操作 → 验证码消失后自动恢复
"""
import re
import datetime
from playwright.async_api import async_playwright, Page, ViewportSize
from playwright._impl._api_structures import SetCookieParam
from parsel import Selector
from loguru import logger
from core.config import settings
from core.utils.request import UserAgent


def parse_read_count(text: str) -> int:
    """
    解析阅读数: '2.6万' → 26000
    """
    text = text.strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    return int(text) if text.isdigit() else 0


def parse_list_time(text: str, current_year: int) -> datetime.datetime | None:
    """
    解析列表页时间: '06-11 13:53' → 2026-06-11 13:53:00
    """
    try:
        text = text.strip()
        if re.match(r"\d{2}-\d{2}\s\d{2}:\d{2}", text):
            dt = datetime.datetime.strptime(text, "%m-%d %H:%M")
            return dt.replace(year=current_year)
    except Exception:
        logger.error("❌ parse_list_time: {}", text)
        pass
    return None

# 解析Cookie
def parse_cookie(cookie_str: str) -> list[SetCookieParam]:
    """解析 Cookie 字符串为 Playwright add_cookies 所需的 SetCookieParam 列表"""
    cookies: list[SetCookieParam] = []
    if not cookie_str:
        return cookies
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            cookies.append({
                "name": k.strip(), "value": v.strip(),
                "domain": ".eastmoney.com", "path": "/",
            })
    return cookies

# 广告过滤
AD_KEYWORDS = ["加群", "V信", "荐股", "牛股推荐", "直播", "荐股大师"]


class GubaClient:
    """东方财富股吧 Playwright 客户端
    职责：启动浏览器 → 访问页面 → 提取结构化数据 → 返回 dict
    不涉及：数据库存储、任务调度、数据清洗
    """

    def __init__(self, request_delay: float = 1.5):
        self.request_delay = request_delay
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None  # 全局复用同一个 page


    async def start(self):
        """
        启动浏览器，创建唯一 page
        浏览器生命周期
        """
        # 调用函数，返回一个 PlaywrightContextManager 对象 后续直接启动start
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        view_port = ViewportSize(width=1440, height=900)
        self._context = await self._browser.new_context(
            # 控制窗口大小
            viewport=view_port,
            # ua
            user_agent= UserAgent.CHROME_CURRENT.value,
        )
        # 注入 cookie
        if settings.akshare_em_cookie:
            cookies = parse_cookie(settings.akshare_em_cookie)
            if cookies:
                await self._context.add_cookies(cookies)
                logger.info("GubaClient: 注入 {} 条 cookie", len(cookies))

        # 创建唯一 page，全程复用
        self._page = await self._context.new_page()
        logger.info("GubaClient: 浏览器已启动（单页面模式）")

    async def stop(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("GubaClient: 浏览器已关闭")

    # ================================================================
    # 人机验证检测 + 等待
    # ================================================================

    async def _is_page_blocked(self, page: Page, expected_url_pattern: str = "") -> bool:
        """判断页面是否被拦截（人机验证/重定向）

        东方财富验证码会把页面重定向到其他域名/路径。
        检测方式：
        1. 当前 URL 是否还停留在股吧域名下
        2. 如果指定了期望 URL 模式，检查是否匹配

        Args:
            page: 当前页面
            expected_url_pattern: 期望 URL 中包含的关键字（如 "guba.eastmoney.com"）
        """
        try:
            current_url = page.url
            # 检查是否还在股吧域名
            if "guba.eastmoney.com" not in current_url:
                return True  # 被重定向到其他域名了
            # 检查是否匹配期望的 URL 模式
            if expected_url_pattern and expected_url_pattern not in current_url:
                return True
            return False
        except Exception:
            return True

    async def _wait_for_captcha_resolve(self, page: Page, expected_url_pattern: str = "guba.eastmoney.com", timeout: int = 300):
        """页面被拦截 → 暂停等你操作 → URL 回到股吧域名后恢复

        Args:
            expected_url_pattern: 验证通过后 URL 应包含的关键字
            timeout: 最多等多少秒（默认5分钟）
        """
        logger.warning("=" * 60)
        logger.warning("⚠️  检测到人机验证！请在浏览器中手动完成验证！")
        logger.warning("⚠️  等待验证完成中...（最多等 {} 秒）", timeout)
        logger.warning("=" * 60)

        elapsed = 0
        check_interval = 3  # 每3秒检查一次

        while elapsed < timeout:
            await page.wait_for_timeout(check_interval * 1000)
            elapsed += check_interval

            # 验证通过 = URL 回到股吧域名
            blocked = await self._is_page_blocked(page, expected_url_pattern)
            if not blocked:
                logger.info("✅ 人机验证已通过，继续爬取！")
                await page.wait_for_timeout(1000)
                return True

            # 每15秒提醒一次
            if elapsed % 15 == 0:
                logger.info("⏳ 仍在等待人机验证...（已等 {} 秒）", elapsed)

        logger.error("❌ 人机验证等待超时（{} 秒）", timeout)
        return False

    async def _safe_goto(self, page: Page, url: str) -> bool:
        """安全跳转：访问页面 → 检测拦截（URL 是否还在股吧域名）→ 被拦截就等你验证

        Args:
            url: 目标URL
        """
        try:
            logger.debug("访问: {}", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(int(self.request_delay * 1000))

            # 检查 URL 是否还在股吧域名下
            if await self._is_page_blocked(page):
                resolved = await self._wait_for_captcha_resolve(page)
                if not resolved:
                    return False
                # 验证通过后重新导航到目标URL
                logger.info("重新加载目标页面: {}", url)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(int(self.request_delay * 1000))

            return True

        except Exception as e:
            logger.warning("页面访问失败 {}: {}", url, e)
            return False

    # ================================================================
    # 数据获取
    # ================================================================

    async def fetch_post_list(self, stock_code: str, max_pages: int = 100, max_posts: int = 700) -> list[dict]:
        """从列表页收集帖子URL和基础信息（复用全局 page）"""
        posts = []
        page = self._page  # 复用同一个页面

        for page_num in range(1, max_pages + 1):
            if len(posts) >= max_posts:
                break

            url = f"https://guba.eastmoney.com/list,{stock_code},{page_num}.html"
            ok = await self._safe_goto(page, url)
            if not ok:
                logger.warning("列表页访问失败 page={}，跳过", page_num)
                continue

            html = await page.content()
            sel = Selector(text=html)
            items = sel.css("#mainlist .listitem")

            if not items:
                logger.info("列表页无数据，停止翻页: page={}", page_num)
                break

            for item in items:
                if len(posts) >= max_posts:
                    break

                read_text = (item.css("div.read::text").get() or "").strip()
                reply_text = (item.css("div.reply::text").get() or "").strip()
                title_el = item.css("div.title a")
                title = (title_el.css("::attr(title)").get() or title_el.css("::text").get() or "").strip()
                href = (title_el.css("::attr(href)").get() or "").strip()
                author = (item.css("div.author .nametext::text").get() or "").strip()
                update_time = (item.css("div.update::text").get() or "").strip()

                # 过滤广告
                if any(kw in title for kw in AD_KEYWORDS):
                    continue
                if not title or not href:
                    continue

                post_id_match = re.search(r"news,\d+,(\d+)\.html", href)
                if not post_id_match:
                    continue

                full_url = f"https://guba.eastmoney.com{href}" if href.startswith("/") else href

                posts.append({
                    "stock_code": stock_code,
                    "post_id": post_id_match.group(1),
                    "title": title,
                    "url": full_url,
                    "author": author,
                    "read_count": parse_read_count(read_text),
                    "comment_count": parse_read_count(reply_text),
                    "update_time_text": update_time,
                })

            logger.info("列表页 page={}: 累计 {} 条", page_num, len(posts))

        logger.info("股票 {} 列表页收集完成: {} 条", stock_code, len(posts))
        return posts

    async def fetch_post_detail(self, post_info: dict) -> dict | None:
        """爬取帖子详情页：正文 + 评论（复用全局 page）

        关键：评论是 AJAX 延迟加载的，domcontentloaded 后评论=0条，
        需要等 .reply_item 出现后才能抓取。
        """
        page = self._page
        url = post_info["url"]

        try:
            ok = await self._safe_goto(page, url)
            if not ok:
                logger.warning("详情页访问失败 {}", url)
                return None

            # 等评论 AJAX 加载（最多等10秒，没有评论也不影响）
            try:
                await page.wait_for_selector(".reply_item", timeout=10000)
            except Exception:
                pass  # 没有评论或超时，继续抓正文

            html = await page.content()
        except Exception as e:
            logger.warning("详情页异常 {}: {}", url, e)
            return None
        sel = Selector(text=html)

        # --- 正文 ---
        title = (sel.css(".title::text").get() or sel.css(".cn-title::text").get() or "").strip()
        content_html = sel.css("#zw_body").get() or ""
        content_text = re.sub(r"<[^>]+>", "", content_html).strip()
        content_text = re.sub(r"\s+", " ", content_text)

        # --- 元信息 ---
        author_name = (sel.css(".author-info a.name::text").get() or "").strip()
        post_time_text = (sel.css(".author-info .time::text").get() or "").strip()
        post_time = None
        try:
            post_time = datetime.datetime.strptime(post_time_text, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        # --- 评论（选择器已按调研结果修正）---
        comments = []
        for ci in sel.css(".reply_item"):
            reply_id = ci.attrib.get("data-reply_id", "")
            author = (ci.css(".item_reuser a::text").get() or "").strip()
            # 时间：.pubtime，地域：.ipfrom
            pub_time_text = (ci.css(".publishtime .pubtime::text").get() or "").strip()
            ipfrom_text = (ci.css(".publishtime .ipfrom::text").get() or "").strip()
            comment_time = None
            try:
                comment_time = datetime.datetime.strptime(pub_time_text, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            # 地域：去掉"来自 "前缀
            region = ipfrom_text.replace("来自 ", "").replace("来自", "").strip()
            # 评论内容
            content = (ci.css(".reply_title_span::text").get() or "").strip()
            # 点赞数：初始评论无数字，默认0
            like_count = 0

            if not reply_id and not content:
                continue

            comments.append({
                "stock_code": post_info["stock_code"],
                "post_id": post_info["post_id"],
                "reply_id": reply_id,
                "content": content,
                "author": author,
                "comment_time": comment_time,
                "like_count": like_count,
                "region": region,
                "is_sub": 0,
            })

            # 二级评论
            for si in ci.css(".reuser_l2"):
                sub_text_list = si.css("::text").getall()
                sub_full = "".join(t.strip() for t in sub_text_list if t.strip())
                if sub_full:
                    sub_author = ""
                    sub_content = sub_full
                    for sep in ["：", ":"]:
                        if sep in sub_full:
                            parts = sub_full.split(sep, 1)
                            sub_author = parts[0].strip()
                            sub_content = parts[1].strip() if len(parts) > 1 else sub_full
                            break

                    comments.append({
                        "stock_code": post_info["stock_code"],
                        "post_id": post_info["post_id"],
                        "reply_id": "",
                        "parent_reply_id": reply_id,
                        "content": sub_content,
                        "author": sub_author,
                        "comment_time": None,
                        "like_count": 0,
                        "region": "",
                        "is_sub": 1,
                    })

        return {
            **post_info,
            "title": title or post_info["title"],
            "content": content_text,
            "content_html": content_html,
            "author": author_name or post_info.get("author", ""),
            "post_time": post_time,
            "comments": comments,
        }
