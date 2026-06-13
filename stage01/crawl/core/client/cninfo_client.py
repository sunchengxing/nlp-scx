"""巨潮资讯网 cninfo 客户端 — 只负责数据请求，不关心存储

对标 EastmoneyClient 的分层设计：
  EastmoneyClient → AKShare 远程接口
  CninfoClient    → cninfo 巨潮资讯网 HTTP API

核心能力：
  1. 查询上市公司财报公告（年报/半年报/季报等）
  2. 获取 PDF 下载链接
  3. 下载 PDF 文件到本地
"""
import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Optional

import requests
from loguru import logger

from core.utils.request import HttpRequest, ContentType, HttpHeaders, UserAgent


# ─── 常量 ───────────────────────────────────────────────
BASE_URL = "http://www.cninfo.com.cn"
API_QUERY = f"{BASE_URL}/new/hisAnnouncement/query"
CDN_BASE = "http://static.cninfo.com.cn"
PAGE_SIZE = 30

# 公告类别 → API 参数映射
CATEGORY_MAP = {
    "年报":      "category_ndbg_szsh",
    "半年报":    "category_bndbg_szsh",
    "一季报":    "category_yjdbg_szsh",
    "三季报":    "category_sjdbg_szsh",
    "业绩预告":  "category_yjyg_szsh",
    "业绩快报":  "category_yjkb_szsh",
    "招股说明书": "category_zssms_szsh",
    "配股说明书": "category_pgsms_szsh",
    "增发说明书": "category_zfsms_szsh",
    "权益变动":  "category_qybd_szsh",
    "股东大会":  "category_gddh_szsh",
    "董事会决议": "category_dshjy_szsh",
    "监事会决议": "category_jshjy_szsh",
}

DEFAULT_CATEGORY = "年报"


class CninfoClient:
    """巨潮资讯网 cninfo 客户端

    职责：发送 HTTP 请求 → 返回原始数据
    不涉及：数据库存储、任务调度、数据清洗

    对标 EastmoneyClient：
      EastmoneyClient → AKShare 远程接口 → 返回 JSON
      CninfoClient    → cninfo HTTP API   → 返回 JSON

    orgId 获取策略：
      1. 优先查 StockInfo 表的 cninfo_org_id 字段
      2. 降级：公式推导（覆盖 95%+ A股）
         - 6开头 → gssh0{code}
         - 000/001/002/003开头 → gssz0{code}
      3. 再降级：远程 GitHub 加载
    """

    def __init__(self, request_delay: float = 1.0):
        self.base_url = BASE_URL
        self.cdn_base = CDN_BASE
        self.request_delay = request_delay
        self._last_request_time = 0.0

        # cninfo 需要用 FORM 编码提交 POST，不用 JSON
        self.http = HttpRequest(
            headers={
                HttpHeaders.USER_AGENT.value: UserAgent.CHROME_CURRENT.value,
                HttpHeaders.REFERER.value: f"{self.base_url}/new/commonUrl?url=disclosure/list/notice",
                "X-Requested-With": "XMLHttpRequest",
            },
            cookies={},
            bearer_token=None,
            content_type=ContentType.FORM,
        )

    # ================================================================
    # 请求控制
    # ================================================================

    def _rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def _post_api(self, payload: dict) -> dict | None:
        """统一 POST 请求"""
        self._rate_limit()
        try:
            resp = self.http.do_post(API_QUERY, data=payload)
            return resp
        except Exception as e:
            logger.error("❌ cninfo POST 失败: {}", e)
            return None

    # ================================================================
    # orgId 获取：查表 → 公式推导 → 远程加载
    # ================================================================

    @lru_cache(maxsize=512)
    def get_org_id(self, stock_code: str) -> str | None:
        """根据股票代码获取 cninfo 内部 orgId

        策略：
          1. 查 StockInfo 表 cninfo_org_id 字段（最可靠）
          2. 公式推导（覆盖沪深主板+中小创）
          3. 远程 GitHub 加载（兜底）

        Args:
            stock_code: 股票代码，如 "000001"

        Returns:
            orgId 字符串 或 None
        """
        # 1. 查库
        org_id = self._get_org_id_from_db(stock_code)
        if org_id:
            return org_id

        # 2. 公式推导
        org_id = self._infer_org_id(stock_code)
        if org_id:
            return org_id

        # 3. 远程加载兜底
        return self._get_org_id_remote(stock_code)

    def _get_org_id_from_db(self, stock_code: str) -> str | None:
        """从 StockInfo 表查 cninfo_org_id"""
        try:
            from core.models import StockInfo
            stock = StockInfo.select(StockInfo.cninfo_org_id).where(
                StockInfo.symbol == stock_code
            ).first()
            if stock and stock.cninfo_org_id:
                return stock.cninfo_org_id
        except Exception as e:
            logger.debug("CninfoClient: 查库获取 orgId 失败 {}: {}", stock_code, e)
        return None

    def _infer_org_id(self, stock_code: str) -> str | None:
        """公式推导 orgId（覆盖 95%+ A股）

        规则：
          - 6开头 → 上交所: gssh0{code}
          - 000/001/002/003开头 → 深交所: gssz0{code}
          - 3开头 → 创业板: gssz0{code}
          - 8/4开头 → 北交所: 暂不支持
        """
        code = stock_code.zfill(6)
        if code.startswith("6"):
            return f"gssh0{code}"
        elif code.startswith(("000", "001", "002", "003", "3")):
            return f"gssz0{code}"
        return None

    def _get_org_id_remote(self, stock_code: str) -> str | None:
        """远程 GitHub 加载单只股票 orgId（兜底，不缓存全量）"""
        url = "https://raw.githubusercontent.com/jingmian/cninfo_spider/main/stock_info.json"
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": UserAgent.CHROME_CURRENT.value})
            resp.raise_for_status()
            data = resp.json()
            for s in data.get("stockList", []):
                if s.get("code") == stock_code:
                    org_id = s.get("orgId")
                    logger.info("CninfoClient: 远程获取 {} orgId={}", stock_code, org_id)
                    return org_id
        except Exception as e:
            logger.warning("CninfoClient: 远程获取 orgId 失败 {}: {}", stock_code, e)
        return None

    def sync_org_ids_to_db(self):
        """一次性同步：从远程加载全部 orgId → 写入 StockInfo 表

        建议在 initdb 后执行一次，之后就不需要远程加载了。
        """
        url = "https://raw.githubusercontent.com/jingmian/cninfo_spider/main/stock_info.json"
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": UserAgent.CHROME_CURRENT.value})
            resp.raise_for_status()
            data = resp.json()
            mapping = {s["code"]: s["orgId"] for s in data.get("stockList", []) if s.get("code") and s.get("orgId")}
            logger.info("CninfoClient: 远程加载 {} 条 orgId 映射", len(mapping))
        except Exception as e:
            logger.error("CninfoClient: 远程加载失败: {}", e)
            return 0

        # 写入 StockInfo 表
        from core.models import StockInfo
        from core.utils.db import db

        updated = 0
        for code, org_id in mapping.items():
            try:
                cnt = (StockInfo
                       .update(cninfo_org_id=org_id)
                       .where(StockInfo.symbol == code)
                       .execute())
                if cnt > 0:
                    updated += 1
            except Exception:
                pass

        logger.info("CninfoClient: ✅ 已将 {} 条 orgId 写入 StockInfo 表", updated)

        # 对于没匹配上的，用公式推导补齐
        formula_filled = 0
        stocks = StockInfo.select(StockInfo.symbol, StockInfo.cninfo_org_id).where(
            StockInfo.cninfo_org_id == ""
        )
        for s in stocks:
            inferred = self._infer_org_id(s.symbol)
            if inferred:
                StockInfo.update(cninfo_org_id=inferred).where(
                    StockInfo.symbol == s.symbol
                ).execute()
                formula_filled += 1

        logger.info("CninfoClient: ✅ 公式推导补齐 {} 条 orgId", formula_filled)
        return updated + formula_filled

    # ================================================================
    # 数据获取
    # ================================================================

    def fetch_announcements(
        self,
        stock_code: str,
        years: tuple | None = None,
        category: str = DEFAULT_CATEGORY,
        page_size: int = PAGE_SIZE,
        max_pages: int = 50,
    ) -> list[dict]:
        """获取单只股票的财报公告列表

        Args:
            stock_code: 股票代码，如 "000001"
            years: 年份区间 (start, end)，如 (2023, 2025)；None 表示全部年份
            category: 公告类别，如 "年报" "半年报" "一季报" "三季报"
            page_size: 每页条数 (默认 30)
            max_pages: 最大翻页数 (防止无限循环)

        Returns:
            公告列表，每个元素包含:
                secCode, secName, announcementId, announcementTitle,
                announcementTime (时间戳ms), adjunctUrl (PDF相对路径)
        """
        org_id = self.get_org_id(stock_code)
        if org_id is None:
            logger.warning("CninfoClient: 未找到 {} 的 orgId，跳过", stock_code)
            return []

        cat_key = CATEGORY_MAP.get(category, CATEGORY_MAP[DEFAULT_CATEGORY])

        # 构建日期区间
        if years:
            start_date = f"{years[0]}-01-01"
            end_date = f"{years[1]}-12-31"
        else:
            start_date = "2000-01-01"
            end_date = datetime.now().strftime("%Y-%m-%d")

        stock_param = f"{stock_code},{org_id}"
        all_announcements = []

        for page in range(1, max_pages + 1):
            payload = {
                "pageNum": page,
                "pageSize": page_size,
                "stock": stock_param,
                "category": cat_key,
                "seDate": f"{start_date}~{end_date}",
                "column": "szse",
                "tabName": "fulltext",
            }

            data = self._post_api(payload)
            if not data:
                logger.warning("CninfoClient: 查询失败 page={}", page)
                break

            announcements = data.get("announcements") or []
            if not announcements:
                break

            all_announcements.extend(announcements)
            logger.debug("CninfoClient: {} page={} 累计 {} 条", stock_code, page, len(all_announcements))

            if not data.get("hasMore"):
                break

        logger.info("CninfoClient: {} {} 公告共 {} 条", stock_code, category, len(all_announcements))
        return all_announcements

    def fetch_announcements_batch(
        self,
        stock_codes: list[str],
        years: tuple | None = None,
        category: str = DEFAULT_CATEGORY,
        **kwargs,
    ) -> dict[str, list[dict]]:
        """批量获取多只股票的财报公告

        Args:
            stock_codes: 股票代码列表
            years: 年份区间
            category: 公告类别

        Returns:
            {stock_code: [announcements]}
        """
        results = {}
        for i, code in enumerate(stock_codes):
            logger.info("CninfoClient: [{}/{}] 查询 {} ...", i + 1, len(stock_codes), code)
            results[code] = self.fetch_announcements(code, years=years, category=category, **kwargs)
        return results

    # ================================================================
    # PDF 下载
    # ================================================================

    def download_pdf(
        self,
        adjunct_url: str,
        output_dir: str = "./pdfs",
        filename: str | None = None,
        timeout: int = 120,
    ) -> str | None:
        """下载单个 PDF 文件

        Args:
            adjunct_url: 公告中的 adjunctUrl 字段
            output_dir:  输出目录
            filename:    自定义文件名；不传则从 URL 提取
            timeout:     下载超时 (秒)

        Returns:
            保存路径 或 None (失败时)
        """
        os.makedirs(output_dir, exist_ok=True)

        if filename is None:
            filename = os.path.basename(adjunct_url)
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"

        filepath = os.path.join(output_dir, filename)

        if os.path.exists(filepath):
            logger.debug("CninfoClient: 文件已存在 {}", filepath)
            return filepath

        url = f"{self.cdn_base}/{adjunct_url}"
        dl_headers = {
            "User-Agent": UserAgent.CHROME_CURRENT.value,
            "Referer": f"{self.base_url}/",
        }

        try:
            resp = requests.get(url, headers=dl_headers, timeout=timeout, stream=True)
            resp.raise_for_status()

            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

            if total > 0 and downloaded < total * 0.95:
                os.remove(filepath)
                logger.error("CninfoClient: 下载不完整 {}", filename)
                return None

            logger.info("CninfoClient: ✅ 下载 {} → {}", filename, filepath)
            return filepath

        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            logger.error("CninfoClient: 下载失败 {} - {}", filename, e)
            return None

    def download_pdfs(
        self,
        announcements: list[dict],
        output_dir: str = "./pdfs",
        stock_code: str | None = None,
    ) -> list[str]:
        """批量下载公告 PDF

        Args:
            announcements: fetch_announcements() 返回的公告列表
            output_dir:   输出根目录 (会自动按股票代码建子目录)
            stock_code:   股票代码

        Returns:
            成功下载的文件路径列表
        """
        results = []
        for ann in announcements:
            adjunct_url = ann.get("adjunctUrl")
            if not adjunct_url:
                continue

            code = stock_code or ann.get("secCode", "unknown")
            title = ann.get("announcementTitle", "unknown").replace("/", "_")
            subdir = os.path.join(output_dir, code)
            os.makedirs(subdir, exist_ok=True)

            base_name = os.path.basename(adjunct_url)
            filename = f"{title}_{base_name}" if not base_name.lower().endswith(".pdf") else f"{title}.pdf"

            path = self.download_pdf(adjunct_url, output_dir=subdir, filename=filename)
            if path:
                results.append(path)

        logger.info("CninfoClient: 批量下载完成，成功 {} 份", len(results))
        return results
