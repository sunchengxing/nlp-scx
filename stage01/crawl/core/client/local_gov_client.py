"""地方政府网站法规客户端（配置驱动）

对标 EastmoneyClient 模式：
  Client 只负责数据获取，编排和存储由 Service 完成。

核心方法：
  - fetch_list()      → 按站点配置抓取列表页
  - fetch_detail()    → 按站点配置抓取详情页
  - load_sites_config() → 从 JSON 加载站点配置

数据源：各省市政府网站（配置文件定义）
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from loguru import logger

from core.utils.request import HttpRequest, ContentType, HttpHeaders, UserAgent
from core.utils.text_cleaner import TextCleaner


# ---------------------------------------------------------------------------
# 数据模型：站点配置模板
# ---------------------------------------------------------------------------

@dataclass
class ListPageTemplate:
    """列表页模板：定义如何从列表页提取法规条目链接"""
    name: str
    base_url: str
    list_url_template: str       # 支持 {page} 占位符
    item_selector: str
    title_selector: str
    link_selector: str
    date_selector: str = ""
    page_start: int = 1
    page_end: int = -1            # -1 表示自动探测
    encoding: str = "utf-8"


@dataclass
class DetailPageTemplate:
    """详情页模板：定义如何从法规详情页提取正文和元数据"""
    name: str
    content_selector: str
    title_selector: str = "h1"
    publish_date_selector: str = ""
    issuing_authority_selector: str = ""
    document_number_selector: str = ""
    exclude_selectors: list = field(default_factory=list)
    encoding: str = "utf-8"


@dataclass
class SiteConfig:
    """单个站点的完整采集配置"""
    site_id: str
    source_name: str
    list_template: ListPageTemplate
    detail_template: DetailPageTemplate
    regulation_type: str = "地方性法规"
    enabled: bool = True


class LocalGovClient:
    """通用地方性法规客户端（配置驱动）"""

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

    def _fetch_page(self, url: str, encoding: str = "utf-8") -> Optional[str]:
        """GET 请求，带重试和频率控制"""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                resp = self.http.session.get(url, timeout=30)
                self._last_request_time = time.time()
                resp.raise_for_status()

                # 编码检测
                if encoding:
                    resp.encoding = encoding
                elif resp.encoding and resp.encoding.lower() in ("iso-8859-1", "latin-1"):
                    match = re.search(rb'charset=["\']?([\w-]+)', resp.content[:2048])
                    if match:
                        resp.encoding = match.group(1).decode("ascii")
                    else:
                        resp.encoding = "utf-8"

                return resp.text

            except Exception as e:
                logger.warning("⚠️ LocalGov 请求失败: url={}, attempt={}/{}, error={}",
                               url, attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        logger.error("❌ LocalGov 请求全部失败: url={}", url)
        return None

    # ================================================================
    # 列表页
    # ================================================================

    def fetch_list(self, site: SiteConfig, keyword_filter: str = "") -> List[Dict[str, str]]:
        """从列表页发现法规详情页 URL

        Args:
            site: 站点配置
            keyword_filter: 标题关键词过滤（空=不过滤）

        Returns:
            [{"title", "url", "date"}] 条目列表
        """
        template = site.list_template
        discovered = []

        # 构造分页 URL
        if "{page}" in template.list_url_template:
            end = template.page_end if template.page_end > 0 else 5  # 自动探测最多 5 页
            page_urls = [template.list_url_template.format(page=p) for p in range(template.page_start, end + 1)]
        else:
            page_urls = [template.list_url_template]

        for page_url in page_urls:
            logger.info("📋 LocalGov 列表: site='{}', url={}", site.site_id, page_url)

            html = self._fetch_page(page_url, template.encoding)
            if not html:
                continue

            items = self._parse_list_page(html, template, page_url)
            discovered.extend(items)

            # 自动探测下一页
            if template.page_end == -1 and items:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                next_link = soup.select_one('a:contains("下一页"), a.next, .pagination .next')
                if not next_link:
                    break

        # 去重
        seen = set()
        unique = []
        for item in discovered:
            if item["url"] not in seen:
                seen.add(item["url"])
                unique.append(item)

        # 关键词过滤
        if keyword_filter:
            unique = [d for d in unique if keyword_filter in d.get("title", "")]

        logger.info("📊 LocalGov 列表: site='{}', {} 条", site.site_id, len(unique))
        return unique

    def _parse_list_page(
        self, html: str, template: ListPageTemplate, page_url: str
    ) -> List[Dict[str, str]]:
        """按模板解析列表页"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        entries = []

        items = soup.select(template.item_selector)
        for item in items:
            title_el = item.select_one(template.title_selector)
            link_el = item.select_one(template.link_selector)
            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            href = link_el.get("href", "")
            if not href or not title:
                continue

            # 补全 URL
            detail_url = urljoin(template.base_url, href)

            date_str = ""
            if template.date_selector:
                date_el = item.select_one(template.date_selector)
                if date_el:
                    date_str = date_el.get_text(strip=True)

            entries.append({"title": title, "url": detail_url, "date": date_str})

        return entries

    # ================================================================
    # 详情页
    # ================================================================

    def fetch_detail(self, url: str, template: DetailPageTemplate) -> Optional[Dict[str, Any]]:
        """按模板抓取详情页

        Args:
            url: 详情页 URL
            template: 详情页模板

        Returns:
            {"title", "publish_date", "content", "source_url", "document_number",
             "issuing_authority", "content_hash"}
            或 None
        """
        logger.info("📄 LocalGov 详情: {}", url)

        html = self._fetch_page(url, template.encoding)
        if not html:
            return None

        return self._parse_detail_page(html, url, template)

    def _parse_detail_page(
        self, html: str, url: str, template: DetailPageTemplate
    ) -> Optional[Dict[str, Any]]:
        """按模板解析详情页"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # 排除不需要的子元素
        for sel in template.exclude_selectors:
            for el in soup.select(sel):
                el.decompose()

        # 提取元数据
        title = self._extract_text(soup, template.title_selector)
        publish_date = self._extract_text(soup, template.publish_date_selector)
        issuing_authority = self._extract_text(soup, template.issuing_authority_selector)
        document_number = self._extract_text(soup, template.document_number_selector)

        # 提取正文
        content = ""
        el = soup.select_one(template.content_selector)
        if el:
            content = el.get_text(separator="\n", strip=True)
            content = TextCleaner.normalize_text(content)

        if not title and not content:
            logger.warning("⚠️ LocalGov 详情无内容: {}", url)
            return None

        content_hash = TextCleaner.compute_content_hash(content) if content else ""

        return {
            "title": title,
            "publish_date": TextCleaner.extract_date(publish_date) or publish_date,
            "content": content,
            "source_url": url,
            "document_number": document_number,
            "issuing_authority": issuing_authority,
            "content_hash": content_hash,
        }

    # ================================================================
    # 站点配置加载
    # ================================================================

    @staticmethod
    def load_sites_config(config_path: str) -> List[SiteConfig]:
        """从 JSON 配置文件加载站点采集规则

        Args:
            config_path: JSON 配置文件路径

        Returns:
            SiteConfig 列表
        """
        path = Path(config_path)
        if not path.exists():
            logger.error("❌ 配置文件不存在: {}", config_path)
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sites = []
        for site_data in data.get("sites", []):
            if not site_data.get("enabled", True):
                continue

            list_data = site_data["list_template"]
            detail_data = site_data["detail_template"]

            list_template = ListPageTemplate(
                name=list_data["name"],
                base_url=list_data["base_url"],
                list_url_template=list_data["list_url_template"],
                item_selector=list_data["item_selector"],
                title_selector=list_data["title_selector"],
                link_selector=list_data["link_selector"],
                date_selector=list_data.get("date_selector", ""),
                page_start=list_data.get("page_start", 1),
                page_end=list_data.get("page_end", -1),
                encoding=list_data.get("encoding", "utf-8"),
            )
            detail_template = DetailPageTemplate(
                name=detail_data["name"],
                content_selector=detail_data["content_selector"],
                title_selector=detail_data.get("title_selector", "h1"),
                publish_date_selector=detail_data.get("publish_date_selector", ""),
                issuing_authority_selector=detail_data.get("issuing_authority_selector", ""),
                document_number_selector=detail_data.get("document_number_selector", ""),
                exclude_selectors=detail_data.get("exclude_selectors", []),
                encoding=detail_data.get("encoding", "utf-8"),
            )
            site = SiteConfig(
                site_id=site_data["site_id"],
                source_name=site_data["source_name"],
                list_template=list_template,
                detail_template=detail_template,
                regulation_type=site_data.get("regulation_type", "地方性法规"),
            )
            sites.append(site)

        logger.info("📋 加载站点配置: {} 个站点", len(sites))
        return sites

    # ================================================================
    # 工具方法
    # ================================================================

    @staticmethod
    def _extract_text(soup, selector: str, default: str = "") -> str:
        """安全提取选择器文本"""
        if not selector:
            return default
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)
        return default

    @staticmethod
    def hash_url(url: str) -> str:
        """生成 URL 的短哈希，用作 doc_id"""
        return hashlib.md5(url.encode()).hexdigest()[:16]
