"""国家法律法规数据库 (flk.npc.gov.cn) HTTP 客户端

对标 EastmoneyClient 模式：
  Client 只负责数据获取，编排和存储由 Service 完成。

核心方法：
  - search_laws()   → API 搜索法规列表
  - get_detail()    → 获取法规详情（含下载路径）
  - download_file() → 下载 DOCX/HTML 文件
  - extract_text()  → 从下载内容提取纯文本

数据源：https://flk.npc.gov.cn
"""
import hashlib
import json
import time
from io import BytesIO
from typing import Any, Dict, List, Optional

from loguru import logger

from core.utils.request import HttpRequest, ContentType, HttpHeaders, UserAgent
from core.utils.text_cleaner import TextCleaner


# 法规类型代码映射
TYPE_MAP = {
    "flfg": "法律",
    "xzfg": "行政法规",
    "dfxfg": "地方性法规",
    "sfjs": "司法解释",
    "jcfg": "监察法规",
}


class FlkClient:
    """国家法律法规数据库 HTTP 客户端"""

    BASE_URL = "https://flk.npc.gov.cn"
    API_LIST_URL = "https://flk.npc.gov.cn/api/"
    API_DETAIL_URL = "https://flk.npc.gov.cn/api/detail"
    FILE_BASE_URL = "https://wb.flk.npc.gov.cn"

    def __init__(self, request_delay: float = 1.5, max_retries: int = 3):
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0

        self.http = HttpRequest(
            headers={
                HttpHeaders.USER_AGENT.value: UserAgent.CHROME_CURRENT.value,
                HttpHeaders.ACCEPT.value: "application/json, text/javascript, */*; q=0.01",
                HttpHeaders.ACCEPT_LANGUAGE.value: "zh-CN,zh;q=0.9,en;q=0.8",
                "X-Requested-With": "XMLHttpRequest",
                HttpHeaders.REFERER.value: f"{self.BASE_URL}/index.html",
                HttpHeaders.CONNECTION.value: "keep-alive",
            },
            cookies={},
            bearer_token=None,
            content_type=ContentType.JSON,
        )

    def _rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def _is_waf_blocked(self, response) -> bool:
        """判断响应是否被 WAF 拦截（返回 HTML 而非 JSON）"""
        content_type = response.headers.get("Content-Type", "")
        is_json = "application/json" in content_type or response.text.strip().startswith("{")
        return (
            response.status_code == 200
            and not is_json
            and "<html" in response.text[:200].lower()
        )

    # ================================================================
    # API: 搜索法规列表
    # ================================================================

    def search_laws(
        self,
        keyword: str = "",
        law_type: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> Optional[Dict[str, Any]]:
        """搜索法律法规列表

        Args:
            keyword: 搜索关键词
            law_type: 法规类型代码 (flfg/xzfg/dfxfg/sfjs/jcfg)
            page: 页码
            page_size: 每页条数（API 最大 100）

        Returns:
            API 返回的完整 JSON 数据，或 None（请求失败 / WAF 拦截）
        """
        self._rate_limit()

        params: Dict[str, Any] = {
            "type": law_type,
            "sortTr": "f_bbrq_s;desc",
            "gbrqStart": "",
            "gbrqEnd": "",
            "sxrqStart": "",
            "sxrqEnd": "",
            "sort": "true",
            "page": str(page),
            "size": str(min(page_size, 100)),
            "_": str(int(time.time() * 1000)),
        }

        if keyword:
            params["searchWord"] = keyword
            params["searchType"] = "title;vague"
        else:
            params["searchType"] = "title;vague"

        logger.info("🔍 FLK 搜索: keyword='{}', type='{}', page={}", keyword, law_type or "全部", page)

        try:
            self.http.do_get(self.API_LIST_URL, params=params)
            response = self.http.response
        except Exception as e:
            logger.error("❌ FLK 搜索请求失败: {}", e)
            return None

        if self._is_waf_blocked(response):
            logger.error("🚫 FLK API 被 WAF 拦截，需要设置 Cookie 或使用浏览器模式")
            return None

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error("❌ FLK 搜索响应非 JSON: {}", response.text[:200])
            return None

        if not data.get("success"):
            logger.error("❌ FLK API 返回失败: {}", data)
            return None

        result = data.get("result", {})
        total = result.get("totalSizes", 0)
        logger.info("📊 FLK 搜索结果: {} 条, 第 {}/{} 页",
                     total, result.get("page", page), (total + page_size - 1) // page_size if total else 1)

        return data

    # ================================================================
    # API: 获取法规详情
    # ================================================================

    def get_detail(self, law_id: str) -> Optional[Dict[str, Any]]:
        """获取法规详情（含下载路径）

        Args:
            law_id: 法规 ID

        Returns:
            API 返回的完整 JSON 数据，含 body[].path 下载路径
        """
        self._rate_limit()

        logger.debug("📄 FLK 详情: id={}", law_id)

        try:
            self.http.do_post(self.API_DETAIL_URL, data={"id": law_id})
            response = self.http.response
        except Exception as e:
            logger.error("❌ FLK 详情请求失败: id={}, error={}", law_id, e)
            return None

        if self._is_waf_blocked(response):
            logger.warning("🚫 FLK 详情被 WAF 拦截: id={}", law_id)
            return None

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error("❌ FLK 详情响应非 JSON: id={}", law_id)
            return None

        if not data.get("success"):
            logger.warning("⚠️ FLK 详情 API 返回失败: id={}", law_id)
            return None

        return data

    # ================================================================
    # 文件下载
    # ================================================================

    def download_file(self, path: str) -> Optional[bytes]:
        """下载法规文件（DOCX/HTML）

        Args:
            path: 相对路径如 /flfg/WORD/xxx.docx，或完整 URL

        Returns:
            文件二进制内容，或 None
        """
        self._rate_limit()

        url = path if path.startswith("http") else self.FILE_BASE_URL + path
        logger.debug("⬇️ FLK 下载: {}", url)

        try:
            resp = self.http.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            logger.error("❌ FLK 下载失败: url={}, error={}", url, e)
            return None

    # ================================================================
    # 文本提取
    # ================================================================

    def extract_text(self, content: bytes, doc_type: str = "WORD") -> str:
        """根据文件类型从下载内容中提取纯文本

        Args:
            content: 文件二进制数据
            doc_type: WORD / HTML / PDF

        Returns:
            提取的纯文本
        """
        if doc_type.upper() == "WORD":
            return self._extract_text_from_docx(content)
        elif doc_type.upper() in ("HTML", "HTM"):
            return self._extract_text_from_html(content)
        elif doc_type.upper() == "PDF":
            logger.warning("⚠️ FLK: PDF 格式暂不支持文本提取")
            return "[PDF格式，未提取]"
        else:
            logger.warning("⚠️ FLK: 未知文件类型: {}", doc_type)
            return ""

    def _extract_text_from_docx(self, content: bytes) -> str:
        """从 DOCX 二进制数据提取纯文本"""
        try:
            from docx import Document
            doc = Document(BytesIO(content))
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    # 识别标题样式
                    style_name = (para.style.name or "").lower()
                    if "heading" in style_name or "title" in style_name or "标题" in style_name:
                        paragraphs.append(f"\n{text}\n")
                    else:
                        paragraphs.append(text)
            raw = "\n".join(paragraphs)
            return TextCleaner.clean_docx_text(raw)
        except ImportError:
            logger.warning("⚠️ python-docx 未安装，无法解析 DOCX。pip install python-docx")
            return ""
        except Exception as e:
            logger.error("❌ DOCX 解析失败: {}", e)
            return ""

    def _extract_text_from_html(self, content: bytes) -> str:
        """从 HTML 二进制数据提取纯文本"""
        try:
            html = content.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            try:
                html = content.decode("gbk", errors="replace")
            except UnicodeDecodeError:
                html = content.decode("utf-8", errors="ignore")
        return TextCleaner.clean_html_text(html)

    # ================================================================
    # 便捷方法：获取单条法律的完整信息
    # ================================================================

    def fetch_law_full(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取单条法律的完整信息：详情 + 下载 + 文本提取

        Args:
            item: search_laws 返回的列表条目，含 id/title/office/publish/type/status

        Returns:
            {
              "id", "title", "office", "publish", "expiry", "type", "status",
              "url", "content", "content_hash", "download_links", "metadata"
            }
        """
        law_id = item.get("id", "")
        title = item.get("title", "未知标题")

        result = {
            "id": law_id,
            "title": title,
            "office": item.get("office", ""),
            "publish": item.get("publish", ""),
            "expiry": item.get("expiry", ""),
            "type": item.get("type", ""),
            "status": item.get("status", ""),
            "url": f"{self.BASE_URL}/detail2.html?{law_id}",
            "content": "",
            "content_hash": "",
            "download_links": {},
            "metadata": {},
        }

        # 获取详情
        detail = self.get_detail(law_id)
        if not detail:
            return result

        detail_result = detail.get("result", {})

        # 更新元数据
        result["office"] = detail_result.get("office", result["office"])
        result["publish"] = detail_result.get("publish", result["publish"])
        result["title"] = detail_result.get("title", result["title"])

        # 获取下载链接
        body_files = detail_result.get("body", [])
        download_links = {}
        for f in body_files:
            file_type = f.get("type", "UNKNOWN")
            file_path = f.get("path", "")
            if file_path:
                download_links[file_type] = self.FILE_BASE_URL + file_path
        result["download_links"] = download_links

        # 优先下载 WORD → HTML → HTM 提取文本
        for doc_type in ("WORD", "HTML", "HTM"):
            path = next(
                (f.get("path", "") for f in body_files if f.get("type", "").upper() == doc_type.upper()),
                "",
            )
            if path:
                file_content = self.download_file(path)
                if file_content:
                    text = self.extract_text(file_content, doc_type)
                    if text:
                        result["content"] = text
                        result["content_hash"] = TextCleaner.compute_content_hash(text)
                        result["metadata"] = self._extract_metadata_from_text(text)
                        logger.info("✅ FLK 文本提取成功: {} ({} 字符)", title, len(text))
                        return result
                    else:
                        logger.warning("⚠️ FLK 文本提取为空: {} ({})", title, doc_type)
                else:
                    logger.warning("⚠️ FLK 下载失败: {} ({})", title, doc_type)

        logger.warning("⚠️ FLK 未能提取正文: {}", title)
        return result

    @staticmethod
    def _extract_metadata_from_text(text: str) -> Dict[str, str]:
        """从法律文本开头提取元数据"""
        meta = {}
        first_lines = text.split("\n")[:10]

        # 提取标题
        for line in first_lines:
            line = line.strip()
            if line and not line.startswith("（") and not line.startswith("("):
                meta["extracted_title"] = line
                break

        # 提取公文编号
        import re
        doc_no_pattern = re.compile(r"([一-鿿]+第[一-鿿\d]+号|[一-鿿]+〔\d+〕[一-鿿\d]+号)")
        for line in first_lines:
            match = doc_no_pattern.search(line)
            if match:
                meta["document_number"] = match.group(1)
                break

        # 提取日期
        date_pattern = re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)")
        dates = []
        for line in first_lines:
            for match in date_pattern.finditer(line):
                dates.append(match.group(1))
        if dates:
            meta["publish_date_in_text"] = dates[0]
            if len(dates) >= 2:
                meta["implement_date_in_text"] = dates[1]

        return meta

    @staticmethod
    def resolve_type_name(type_code: str) -> str:
        """将法规类型代码转为中文名称"""
        return TYPE_MAP.get(type_code, type_code)
