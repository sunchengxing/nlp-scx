import asyncio
import sys
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from core.utils.db import db
from business.stock.a_stock_service import AStockService
from core.models import (
    StockKlineDaily, StockKlineMinute, StockIntradayTick, StockInfo,
    LhbDetail, LhbSeatDetail, LhbInstitutionDaily,
    LhbBranchActive, LhbBranchStatistic,
    CapitalFlowStock, CapitalFlowMarket, CapitalFlowMainRank,
    CapitalFlowSector, CapitalFlowHsgt,
    GubaPost, GubaComment,
    CninfoAnnouncement,
    FireLawRegulation, FireIndustryDoc,
)


# ============================================================
# 数据库初始化
# ============================================================

def init_db():
    """初始化：建表（已存在则跳过）"""
    db.connect()

    all_models = [
        StockKlineDaily, StockKlineMinute, StockIntradayTick, StockInfo,
        LhbDetail, LhbSeatDetail, LhbInstitutionDaily,
        LhbBranchActive, LhbBranchStatistic,
        CapitalFlowStock, CapitalFlowMarket, CapitalFlowMainRank,
        CapitalFlowSector, CapitalFlowHsgt,
        GubaPost, GubaComment,
        CninfoAnnouncement,
        FireLawRegulation, FireIndustryDoc,
    ]
    for model in all_models:
        table = model._meta.table_name
        if model.table_exists():
            logger.info("⏭️  表 {} 已存在，跳过", table)
        else:
            db.create_tables([model])
            logger.info("✅ 表 {} 创建成功", table)


def init_stock_list():
    """首次运行：同步所有A股代码到 StockInfo 表"""
    service = AStockService()
    count = StockInfo.select().count()
    if count > 0:
        logger.info("⏭️  StockInfo 已有 {} 条，跳过同步", count)
    else:
        service.sync_stock_list()


# ============================================================
# 定时调度（结构化数据）
# ============================================================

def start_scheduler():
    """启动定时任务：每10分钟随机10只股票拉一周数据"""
    service = AStockService()
    sched = BlockingScheduler()

    sched.add_job(
        service.sync_random_stocks_weekly,
        "interval",
        minutes=10,
        id="random_stocks_weekly",
        max_instances=1,
    )

    logger.info("📅 定时任务启动：每10分钟随机10只股票采集一周数据")
    sched.start()


# ============================================================
# 股吧爬虫任务（非结构化数据）
# ============================================================

# ============================================================
# 股吧爬虫任务（非结构化数据）
# ============================================================

def run_guba(stocks: str | None = None, count: int = 300):
    """运行股吧爬虫

    Args:
        stocks: 逗号分隔的股票代码，如 "600519,300750"，默认从 StockInfo 表随机取10只
        count: 每只股票爬取帖子数，默认 300
    """
    from business.sa.guba_service import GubaService

    # 解析股票参数
    if stocks:
        stock_list = [{"code": s.strip(), "name": s.strip()} for s in stocks.split(",")]
        service = GubaService(stocks=stock_list, posts_per_stock=count)
    else:
        # 不指定股票 → 从 StockInfo 随机取10只
        service = GubaService(posts_per_stock=count)

    asyncio.run(service.sync_all())


# ============================================================
# 巨潮资讯任务（财报公告数据）
# ============================================================

def run_cninfo(stocks: str | None = None, years: str | None = None,
               category: str = "年报", download: bool = False,
               output: str = "./pdfs"):
    """运行巨潮资讯财报查询/下载

    Args:
        stocks: 逗号分隔的股票代码，如 "000001,600519"，默认从 StockInfo 表取全部
        years: 年份区间，如 "2023-2025" 或 "2024"，默认 2023-2026
        category: 公告类别，默认 "年报"
        download: 是否下载 PDF
        output: PDF 输出目录
    """
    from business.finance.cninfo_service import CninfoFinanceService

    # 解析年份
    years_tuple = None
    if years:
        parts = years.split("-")
        if len(parts) == 1:
            y = int(parts[0])
            years_tuple = (y, y)
        elif len(parts) == 2:
            years_tuple = (int(parts[0]), int(parts[1]))

    # 解析股票
    stock_list = None
    if stocks:
        stock_list = [s.strip() for s in stocks.split(",") if s.strip()]

    service = CninfoFinanceService()

    if download:
        service.download_pdfs(stock_codes=stock_list, years=years_tuple,
                              category=category, output_dir=output)
    else:
        service.sync_announcements(stock_codes=stock_list, years=years_tuple,
                                   category=category)


# ============================================================
# 消防法规采集任务
# ============================================================

def run_flk(keyword: str = "消防", law_type: str = "", max_pages: int = 0,
            resume: bool = False):
    """运行国家法律法规数据库采集

    Args:
        keyword: 搜索关键词，默认 "消防"
        law_type: 法规类型代码 (flfg/xzfg/dfxfg/sfjs/jcfg)，空=全部
        max_pages: 最大页数，0=不限
        resume: 断点续传
    """
    from business.fire.flk_service import FlkService

    service = FlkService()
    service.sync_laws(keyword=keyword, law_type=law_type,
                      max_pages=max_pages, resume=resume)


def run_mem(sections: str = "bl,tz,yjbgg", max_pages: int = 0,
            fire_only: bool = True, resume: bool = False):
    """运行应急管理部法规采集

    Args:
        sections: 栏目代码逗号分隔 (bl/tz/yjbgg/yj/h/tb/qt/zcjd)
        max_pages: 每栏目最大页数，0=不限
        fire_only: 仅采集消防相关条目
        resume: 断点续传
    """
    from business.fire.mem_service import MemService

    section_list = [s.strip() for s in sections.split(",") if s.strip()]
    service = MemService()
    service.sync_regulations(sections=section_list, max_pages=max_pages,
                             fire_only=fire_only, resume=resume)


def run_localreg(config: str = "", sites: str = "", keyword: str = "消防",
                 resume: bool = False):
    """运行地方性法规采集（配置驱动）

    Args:
        config: 站点配置 JSON 文件路径（默认: scripts/sites_config.json）
        sites: 指定 site_id 逗号分隔（默认: 全部启用站点）
        keyword: 标题关键词过滤
        resume: 断点续传
    """
    from business.fire.local_gov_service import LocalGovService

    site_ids = None
    if sites:
        site_ids = [s.strip() for s in sites.split(",") if s.strip()]

    service = LocalGovService(config_path=config or "")
    service.sync_regulations(site_ids=site_ids, keyword=keyword, resume=resume)


# NOTE: openstd (国标在线) 已移除 — 消防核心 GB 规范属工程建设类，不在 openstd 收录范围。
# 后续如采购正版电子版 PDF，直接手动入库 FireIndustryDoc 即可。


# ============================================================
# 消防法规文件下载任务
# ============================================================

def run_fire_download(
    source: str = "",
    file_type: str = "",
    limit: int = 0,
    output_dir: str = "./downloads/fire",
):
    """从数据库取下载链接 → 下载文件到本地 → 回填路径

    Args:
        source: 数据来源过滤 (flk/mem_bl/openstd/...)，空=全部
        file_type: 文件类型过滤 (WORD/HTML/PDF/IMAGE)，空=全部
        limit: 最大下载数，0=全部待下载
        output_dir: 文件保存目录

    注意：
      - file_type=IMAGE 的 openstd 条目只存预览页面 URL，不自动下载
        需要在 RAG 流程中用 Playwright 截图 + OCR 处理
      - file_type=PDF/WORD/HTML 的条目会直接下载文件
    """
    from pathlib import Path as _Path
    from core.models.fire import FireLawRegulation, FireIndustryDoc
    from core.utils.db import db

    db.connect()

    download_dir = _Path(output_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0

    # --- 下载 FireLawRegulation 中的文件 ---
    query = FireLawRegulation.select().where(
        FireLawRegulation.download_url != "",
        FireLawRegulation.local_file_path == "",
    )
    if source:
        query = query.where(FireLawRegulation.source == source)
    if file_type:
        query = query.where(FireLawRegulation.file_type == file_type)

    laws = list(query)
    logger.info("📥 待下载法规文件: {} 条", len(laws))

    import requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })

    for law in laws:
        if limit > 0 and downloaded >= limit:
            break

        url = law.download_url
        ext = law.file_type.lower() if law.file_type else "html"
        if ext == "word":
            ext = "docx"
        filename = f"{law.source}_{law.doc_id}.{ext}"
        save_path = download_dir / "laws" / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            save_path.write_bytes(resp.content)

            # 回填 local_file_path
            FireLawRegulation.update(
                local_file_path=str(save_path)
            ).where(
                FireLawRegulation.source == law.source,
                FireLawRegulation.doc_id == law.doc_id,
            ).execute()

            downloaded += 1
            logger.info("✅ 下载: {} → {}", law.title[:40], save_path.name)
        except Exception as e:
            logger.error("❌ 下载失败: {} — {}", url, e)

    # --- 下载 FireIndustryDoc 中的 PDF ---
    query2 = FireIndustryDoc.select().where(
        FireIndustryDoc.download_url != "",
        FireIndustryDoc.local_pdf_path == "",
    )
    if source:
        query2 = query2.where(FireIndustryDoc.source == source)

    docs = list(query2)
    logger.info("📥 待下载标准文档 PDF: {} 条", len(docs))

    for doc in docs:
        if limit > 0 and downloaded >= limit:
            break

        url = doc.download_url
        filename = f"{doc.source}_{doc.doc_id}.pdf"
        save_path = download_dir / "standards" / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = session.get(url, timeout=60)
            resp.raise_for_status()
            save_path.write_bytes(resp.content)

            # 回填 local_pdf_path
            FireIndustryDoc.update(
                local_pdf_path=str(save_path)
            ).where(
                FireIndustryDoc.source == doc.source,
                FireIndustryDoc.doc_id == doc.doc_id,
            ).execute()

            downloaded += 1
            logger.info("✅ 下载PDF: {} → {}", doc.title[:40], save_path.name)
        except Exception as e:
            logger.error("❌ PDF下载失败: {} — {}", url, e)

    logger.info("✅ 下载完成: 共 {} 个文件", downloaded)


# 如果不带参数直接启动，那么打印这个适用方法然后让用户按照要求输入
USAGE = """
用法: python main.py <task> [options]

任务:
  scheduler    启动定时调度（结构化数据：K线/龙虎榜/资金流）
  guba         运行股吧爬虫（非结构化数据：帖子+评论）
  cninfo       运行巨潮资讯查询（财报公告：年报/半年报/季报）
  syncorgid    同步 cninfo orgId 到 StockInfo 表（首次使用 cninfo 前执行一次）
  flk          国家法律法规数据库采集 (flk.npc.gov.cn) → 入库元数据+下载链接
  mem          应急管理部法规采集 (mem.gov.cn) → 入库元数据+下载链接
  localreg     地方性法规采集（配置驱动）→ 入库元数据+下载链接
  # openstd    国标在线采集（已移除：消防核心GB属工程建设类不在收录范围）
  fire-dl      从数据库取下载链接 → 下载文件到本地 → 回填路径
  initdb       初始化数据库（建表）

股吧爬虫选项:
  --stocks 600519,300750   指定股票代码（默认: 从StockInfo表随机取10只）
  --count 300              每只股票爬取条数（默认: 300）

巨潮资讯选项:
  --stocks 000001,600519   指定股票代码（默认: 从StockInfo表取全部）
  --years 2023-2025        年份区间（默认: 2023-2026）
  --category 年报          公告类别（默认: 年报）
  --download               下载 PDF 文件
  --output ./pdfs          PDF 输出目录（默认: ./pdfs）

消防法规选项 (flk):
  --keyword 消防           搜索关键词（默认: 消防）
  --type flfg              法规类型代码（默认: 全部）
  --max-pages 5            最大页数（默认: 不限）
  --resume                 断点续传（跳过已完成页和条目）

消防法规选项 (mem):
  --sections bl,tz,yjbgg   栏目代码逗号分隔（默认: bl,tz,yjbgg）
  --max-pages 5            每栏目最大页数（默认: 不限）
  --all                    采集全部条目（不过滤消防关键词）
  --resume                 断点续传

消防法规选项 (localreg):
  --config sites_config.json  站点配置文件（默认: scripts/sites_config.json）
  --sites beijing_dfxfg,shanghai  指定站点ID（默认: 全部启用）
  --keyword 消防              标题关键词过滤（默认: 消防）
  --resume                    断点续传

# 国标在线选项 (openstd) — 已移除
#   --keyword 消防              搜索关键词（默认: 消防）
#   --max-pages 5               最大搜索页数（默认: 不限）
#   --resume                    断点续传

消防法规下载选项 (fire-dl):
  --source flk              按数据来源过滤下载（默认: 全部）
  --file-type WORD          按文件类型过滤（默认: 全部）
  --limit 50                最大下载数（默认: 全部待下载）
  --output ./downloads/fire  文件保存目录

示例:
  python main.py flk                              # 搜索"消防" → 入库元数据+下载链接
  python main.py flk --keyword "安全生产" --max-pages 3
  python main.py flk --resume                     # 断点续传
  python main.py mem                              # 部令+通知+公告 → 入库元数据
  python main.py mem --sections bl,tz             # 只采集部令和通知
  python main.py mem --resume
  python main.py localreg                         # 地方性法规 → 入库元数据
  python main.py localreg --keyword "防火"
  python main.py localreg --resume
  # python main.py openstd  # 已移除：消防核心GB不在openstd收录范围
  python main.py fire-dl                          # 下载全部待下载文件
  python main.py fire-dl --source flk --limit 10  # 只下载 flk 来源前 10 个
  python main.py fire-dl --file-type PDF          # 只下载 PDF
  python main.py guba
  python main.py cninfo
  python main.py initdb
  python main.py scheduler
"""


def main():
    args = sys.argv[1:]

    if not args:
        print(USAGE)
        return

    task = args[0]

    if task == "scheduler":
        init_db()
        init_stock_list()
        start_scheduler()

    elif task == "guba":
        # 解析 --stocks 和 --count 参数
        stocks = None
        count = 700
        i = 1
        while i < len(args):
            if args[i] == "--stocks" and i + 1 < len(args):
                stocks = args[i + 1]
                i += 2
            elif args[i] == "--count" and i + 1 < len(args):
                count = int(args[i + 1])
                i += 2
            else:
                i += 1

        run_guba(stocks=stocks, count=count)

    elif task == "cninfo":
        # 解析 --stocks, --years, --category, --download, --output 参数
        stocks = None
        years = None
        category = "年报"
        download = False
        output = "./pdfs"
        i = 1
        while i < len(args):
            if args[i] == "--stocks" and i + 1 < len(args):
                stocks = args[i + 1]
                i += 2
            elif args[i] == "--years" and i + 1 < len(args):
                years = args[i + 1]
                i += 2
            elif args[i] == "--category" and i + 1 < len(args):
                category = args[i + 1]
                i += 2
            elif args[i] == "--download":
                download = True
                i += 1
            elif args[i] == "--output" and i + 1 < len(args):
                output = args[i + 1]
                i += 2
            else:
                i += 1

        run_cninfo(stocks=stocks, years=years, category=category,
                   download=download, output=output)

    elif task == "syncorgid":
        from business.finance.cninfo_service import CninfoFinanceService
        init_db()
        init_stock_list()
        service = CninfoFinanceService()
        service.sync_org_ids()

    elif task == "flk":
        # 解析 --keyword, --type, --max-pages, --resume 参数
        keyword = "消防"
        law_type = ""
        max_pages = 0
        resume = False
        i = 1
        while i < len(args):
            if args[i] == "--keyword" and i + 1 < len(args):
                keyword = args[i + 1]
                i += 2
            elif args[i] == "--type" and i + 1 < len(args):
                law_type = args[i + 1]
                i += 2
            elif args[i] == "--max-pages" and i + 1 < len(args):
                max_pages = int(args[i + 1])
                i += 2
            elif args[i] == "--resume":
                resume = True
                i += 1
            else:
                i += 1

        run_flk(keyword=keyword, law_type=law_type,
                max_pages=max_pages, resume=resume)

    elif task == "mem":
        # 解析 --sections, --max-pages, --all, --resume 参数
        sections = "bl,tz,yjbgg"
        max_pages = 0
        fire_only = True
        resume = False
        i = 1
        while i < len(args):
            if args[i] == "--sections" and i + 1 < len(args):
                sections = args[i + 1]
                i += 2
            elif args[i] == "--max-pages" and i + 1 < len(args):
                max_pages = int(args[i + 1])
                i += 2
            elif args[i] == "--all":
                fire_only = False
                i += 1
            elif args[i] == "--resume":
                resume = True
                i += 1
            else:
                i += 1

        run_mem(sections=sections, max_pages=max_pages,
                fire_only=fire_only, resume=resume)

    elif task == "localreg":
        # 解析 --config, --sites, --keyword, --resume 参数
        config = ""
        sites = ""
        keyword = "消防"
        resume = False
        i = 1
        while i < len(args):
            if args[i] == "--config" and i + 1 < len(args):
                config = args[i + 1]
                i += 2
            elif args[i] == "--sites" and i + 1 < len(args):
                sites = args[i + 1]
                i += 2
            elif args[i] == "--keyword" and i + 1 < len(args):
                keyword = args[i + 1]
                i += 2
            elif args[i] == "--resume":
                resume = True
                i += 1
            else:
                i += 1

        run_localreg(config=config, sites=sites, keyword=keyword, resume=resume)

    # elif task == "openstd":  # 已移除：消防核心GB属工程建设类，不在openstd收录范围

    elif task == "fire-dl":
        # 解析 --source, --file-type, --limit, --output 参数
        source = ""
        file_type = ""
        limit = 0
        output_dir = "./downloads/fire"
        i = 1
        while i < len(args):
            if args[i] == "--source" and i + 1 < len(args):
                source = args[i + 1]
                i += 2
            elif args[i] == "--file-type" and i + 1 < len(args):
                file_type = args[i + 1]
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                limit = int(args[i + 1])
                i += 2
            elif args[i] == "--output" and i + 1 < len(args):
                output_dir = args[i + 1]
                i += 2
            else:
                i += 1

        run_fire_download(source=source, file_type=file_type,
                          limit=limit, output_dir=output_dir)

    elif task == "initdb":
        init_db()

    else:
        print(f"未知任务: {task}")
        print(USAGE)


if __name__ == "__main__":
    main()
