"""应急管理部 (mem.gov.cn) HTTP 客户端

对标 EastmoneyClient 模式：
  Client 只负责数据获取，编排和存储由 Service 完成。

核心方法：
  - fetch_list()      → 抓取栏目列表页，返回条目列表
  - fetch_detail()    → 抓取详情页，提取结构化信息
  - download_pdf()    → 下载 PDF 文件到本地
  - extract_pdf_text()→ 提取 PDF 文本

数据源：https://www.mem.gov.cn
"""
import hashlib
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from loguru import logger

from core.utils.request import HttpRequest, ContentType, HttpHeaders, UserAgent
from core.utils.text_cleaner import TextCleaner


# mem.gov.cn 政策法规栏目配置
SECTIONS = {
    "bl": {
        "name": "部令",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/bl/",
        "description": "应急管理部令（部门规章）",
    },
    "tz": {
        "name": "通知",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/tz/",
        "description": "通知公告 - 通知类",
    },
    "yjbgg": {
        "name": "公告",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/yjbgg/",
        "description": "通知公告 - 公告类",
    },
    "yj": {
        "name": "意见",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/yj/",
        "description": "通知公告 - 意见类",
    },
    "h": {
        "name": "函",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/h/",
        "description": "通知公告 - 函件类",
    },
    "tb": {
        "name": "通报",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/tb/",
        "description": "通知公告 - 通报类",
    },
    "qt": {
        "name": "其他",
        "list_url": "https://www.mem.gov.cn/gk/tzgg/qt/",
        "description": "通知公告 - 其他类",
    },
    "zcjd": {
        "name": "政策解读",
        "list_url": "https://www.mem.gov.cn/gk/zcjd/",
        "description": "政策解读",
    },
}

# 非政策文档的导航标题（需排除）
NAVIGATION_TITLES = {
    "首页", "机构", "新闻", "公开", "服务", "互动", "党建",
    "社会救援服务", "应急科普", "法律法规标准", "应急预案",
    "政务服务", "警示信息", "通知公告", "政策解读",
    "政府信息公开", "人事信息", "财务信息", "计划规划", "统计数据",
    "行政许可", "行政执法公示", "应急普法", "查询服务", "业务系统",
    "回应关切", "征求意见", "在线访谈", "公众留言",
    "党建要闻", "基层党建", "党建交流", "党风廉政",
    "规章制度", "学习园地", "群团统战", "巡视工作",
    "生活安全", "自然灾害", "安全生产", "应急科普场馆",
    "时政要闻", "应急要闻", "工作动态", "地方应急",
    "救援力量", "灾害事故信息", "新闻发布会", "媒体信息",
    "队伍风采", "工作信息", "事故及灾害查处", "电子证照",
    "应急管理部公报",
}

# 消防相关关键词
FIRE_KEYWORDS = [
    "消防", "防火", "灭火", "救援", "应急", "火灾",
    "森林防火", "草原防火", "高层建筑", "易燃", "危化品",
    "矿山安全", "烟花爆竹", "消防技术", "消防安全",
    "消防救援", "消防设施", "消防产品", "消防队伍",
    "消防员", "消防车", "消防通道", "防火门",
    "自动喷水", "火灾报警", "灭火器", "消防给水",
    "消火栓", "防排烟", "疏散", "避难层",
]


class MemClient:
    """应急管理部 HTTP 客户端"""

    BASE_URL = "https://www.mem.gov.cn"

    def __init__(self, request_delay: float = 1.5, max_retries: int = 3):
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0

        self.http = HttpRequest(
            headers={
                HttpHeaders.USER_AGENT.value: UserAgent.CHROME_CURRENT.value,
                HttpHeaders.ACCEPT.value: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                HttpHeaders.ACCEPT_LANGUAGE.value: "zh-CN,zh;q=0.9,en;q=0.8",
                HttpHeaders.ACCEPT_ENCODING.value: "gzip, deflate",
                HttpHeaders.CONNECTION.value: "keep-alive",
            },
            cookies={},
            bearer_token=None,
            content_type=ContentType.FORM,
        )

    def _rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def _fetch_page(self, url: str, encoding: str = "") -> Optional[str]:
        """GET 请求，带重试和频率控制，返回 HTML 文本"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                resp = self.http.session.get(url, timeout=30)
                resp.raise_for_status()

                # 编码检测
                if encoding:
                    resp.encoding = encoding
                elif resp.apparent_encoding:
                    resp.encoding = resp.apparent_encoding
                else:
                    resp.encoding = resp.apparent_encoding or "utf-8"

                return resp.text

            except Exception as e:
                logger.warning("⚠️ MEM 请求失败: url={}, attempt={}/{}, error={}",
                               url, attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    time.sleep(wait)

        logger.error("❌ MEM 请求全部失败: url={}", url)
        return None

    # ================================================================
    # 列表页解析
    # ================================================================

    def fetch_list(self, section: str, page: int = 0) -> List[Dict[str, str]]:
        """抓取栏目列表页，返回条目列表

        Args:
            section: 栏目代码 (bl/tz/yjbgg/yj/h/tb/qt/zcjd)
            page: 页码（0 表示首页，即不带分页参数）

        Returns:
            [{"title", "url", "date"}] 条目列表
        """
        section_info = SECTIONS.get(section)
        if not section_info:
            logger.error("❌ MEM 未知栏目: {}", section)
            return []

        list_url = section_info["list_url"]
        if page > 0:
            list_url = f"{list_url}index_{page}.html"

        logger.info("📋 MEM 列表: section='{}', page={}", section_info["name"], page)

        html = self._fetch_page(list_url)
        if not html:
            return []

        return self._parse_list_page(html, list_url)

    def _parse_list_page(self, html: str, page_url: str) -> List[Dict[str, str]]:
        """解析列表页 HTML，提取条目"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        entries = []

        # 模式 1: <li> 列表
        for li in soup.find_all("li"):
            a_tag = li.find("a", href=True)
            if a_tag:
                href = a_tag.get("href", "").strip()
                if not href or "javascript" in href:
                    continue
                title = a_tag.get_text(strip=True)
                if len(title) < 4:
                    continue

                date_str = ""
                date_span = li.find("span")
                if date_span:
                    date_str = TextCleaner.extract_date(date_span.get_text(strip=True)) or ""
                if not date_str:
                    date_str = TextCleaner.extract_date(li.get_text(strip=True)) or ""

                full_url = self._normalize_url(href, page_url)
                entries.append({"title": title, "url": full_url, "date": date_str})

        # 模式 2: 表格形式
        if not entries:
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    a_tag = row.find("a", href=True)
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        if len(title) < 4:
                            continue
                        href = a_tag.get("href", "").strip()
                        if not href or "javascript" in href:
                            continue
                        full_url = self._normalize_url(href, page_url)
                        cells = row.find_all("td")
                        date_str = ""
                        if cells:
                            date_str = TextCleaner.extract_date(cells[-1].get_text(strip=True)) or ""
                        entries.append({"title": title, "url": full_url, "date": date_str})

        # 去重（按 URL）
        seen = set()
        unique = []
        for entry in entries:
            key = entry["url"].rstrip("/")
            if key not in seen:
                seen.add(key)
                unique.append(entry)

        logger.info("📊 MEM 列表解析: {} 条", len(unique))
        return unique

    # ================================================================
    # 详情页解析
    # ================================================================

    def fetch_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """抓取详情页，提取结构化信息

        Args:
            url: 详情页 URL

        Returns:
            {"title", "publish_date", "content", "source_url", "metadata", "pdf_urls"}
            或 None
        """
        logger.info("📄 MEM 详情: {}", url)

        html = self._fetch_page(url)
        if not html:
            return None

        return self._parse_detail_page(html, url)

    def _parse_detail_page(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """解析详情页 HTML"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # --- 标题 ---
        title = ""
        for selector in [
            "div.article h1", "div.article h2", "div.conTit h1",
            "div.main h1", "div.TRS_Editor h1", "div.xl_tit1",
            "div#Title", "h1", "title",
        ]:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                if len(title) > 5:
                    break

        # --- 发布日期 ---
        publish_date = ""
        meta_table = soup.find("table")
        if meta_table:
            for row in meta_table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if "发布日期" in text or "成文日期" in text:
                        publish_date = TextCleaner.extract_date(text) or ""
                        break
                if publish_date:
                    break

        if not publish_date:
            page_text = soup.get_text()
            date_patterns = [
                r"发布日期[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})",
                r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})",
            ]
            for pat in date_patterns:
                m = re.search(pat, page_text)
                if m:
                    publish_date = TextCleaner.extract_date(m.group(1)) or ""
                    break

        # --- 元数据 ---
        metadata = {}
        if meta_table:
            for row in meta_table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    for i in range(0, len(cells) - 1, 2):
                        key = cells[i].get_text(strip=True).rstrip("：:")
                        val = cells[i + 1].get_text(strip=True)
                        if key and val:
                            metadata[key] = val

        # --- 正文 ---
        content = ""
        content_selectors = [
            "div.TRS_Editor", "div.article div.TRS_Editor", "div#Zoom",
            "div.main div.content", "div.con", "div.article", "div#content", "div.main",
        ]
        for sel in content_selectors:
            content_elem = soup.select_one(sel)
            if content_elem and len(content_elem.get_text(strip=True)) > 200:
                for tag in content_elem.find_all(["script", "style"]):
                    tag.decompose()
                for tag in content_elem.find_all("a", class_="prev"):
                    tag.decompose()
                content = content_elem.get_text("\n", strip=True)
                break

        if not content:
            body = soup.find("body")
            if body:
                for tag in body.find_all(["script", "style", "nav", "footer"]):
                    tag.decompose()
                content = body.get_text("\n", strip=True)

        content = self._clean_mem_content(content)

        # --- PDF 附件链接 ---
        pdf_urls = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip().lower()
            if href.endswith(".pdf") or ".pdf?" in href:
                full = self._normalize_url(a_tag["href"], url)
                if full not in pdf_urls:
                    pdf_urls.append(full)

        if not title and not content:
            return None

        return {
            "title": title,
            "publish_date": publish_date,
            "content": content.strip(),
            "source_url": url,
            "metadata": metadata,
            "pdf_urls": pdf_urls,
        }

    # ================================================================
    # PDF 下载
    # ================================================================

    def download_pdf(self, pdf_url: str, save_path: str) -> bool:
        """下载 PDF 文件

        Args:
            pdf_url: PDF 文件 URL
            save_path: 本地保存路径

        Returns:
            是否下载成功
        """
        self._rate_limit()
        logger.info("⬇️ MEM PDF: {}", pdf_url)

        try:
            resp = self.http.session.get(pdf_url, timeout=60)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")

            is_pdf = "application/pdf" in content_type or pdf_url.lower().endswith(".pdf") or resp.content[:5] == b"%PDF-"
            if not is_pdf:
                logger.warning("⚠️ URL 内容非 PDF: {}", pdf_url)
                return False

            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(resp.content)
            logger.info("✅ MEM PDF 下载成功: {} ({} bytes)", path.name, len(resp.content))
            return True

        except Exception as e:
            logger.error("❌ MEM PDF 下载失败: url={}, error={}", pdf_url, e)
            return False

    # ================================================================
    # PDF 文本提取
    # ================================================================

    @staticmethod
    def extract_pdf_text(pdf_path: str) -> str:
        """使用 pdfplumber 提取 PDF 文本，备用 pymupdf

        Args:
            pdf_path: PDF 文件本地路径

        Returns:
            提取的纯文本；扫描型 PDF 返回空字符串
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.warning("⚠️ PDF 文件不存在: {}", pdf_path)
            return ""

        text_parts = []

        # 方法 1: pdfplumber（主力）
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"\n--- 第 {page_num} 页 ---\n")
                        text_parts.append(page_text)
            if text_parts:
                return "".join(text_parts)
        except Exception as e:
            logger.debug("pdfplumber 失败: {} — {}", path.name, e)

        # 方法 2: pymupdf（备用）
        try:
            import fitz
            doc = fitz.open(str(path))
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"\n--- 第 {page_num + 1} 页 ---\n")
                    text_parts.append(page_text)
            doc.close()
            if text_parts:
                return "".join(text_parts)
        except Exception as e:
            logger.debug("pymupdf 失败: {} — {}", path.name, e)

        logger.info("PDF 为扫描件（无文本层）: {}", path.name)
        return ""

    # ================================================================
    # 工具方法
    # ================================================================

    def _normalize_url(self, url: str, base_url: str = "") -> str:
        """规范化 URL：补全相对路径"""
        url = url.strip()
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(base_url or self.BASE_URL, url)

    @staticmethod
    def _clean_mem_content(text: str) -> str:
        """清理 MEM 页面正文：移除导航、页头页尾"""
        nav_marker = "应急科普场馆"
        idx = text.find(nav_marker)
        if 0 < idx < len(text) * 0.5:
            after_nav = text[idx + len(nav_marker):]
            lines = after_nav.split("\n")
            content_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and len(stripped) > 30:
                    content_start = i
                    break
            if content_start > 0:
                text = "\n".join(lines[content_start:])

        for footer_marker in ["主办单位：应急管理部", "网站标识码", "京ICP备", "网站地图"]:
            idx = text.find(footer_marker)
            if idx > 0:
                text = text[:idx].strip()

        return TextCleaner.normalize_text(text)

    @staticmethod
    def is_fire_related(title: str, keywords: list[str] | None = None) -> bool:
        """判断标题是否与消防相关"""
        if keywords is None:
            keywords = FIRE_KEYWORDS
        for kw in keywords:
            if kw in title:
                return True
        if "应急" in title:
            non_fire = ["公共卫生", "地质灾害", "地震应急", "防汛", "抗旱", "气象", "防疫", "医疗", "食品安全"]
            for pat in non_fire:
                if pat in title:
                    return False
            return True
        return False

    @staticmethod
    def hash_url(url: str) -> str:
        """生成 URL 的短哈希，用作 doc_id"""
        return hashlib.md5(url.encode()).hexdigest()[:16]
