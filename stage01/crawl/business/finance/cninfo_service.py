"""巨潮资讯网 cninfo 财报数据服务 — 编排：查询 → 清洗 → 存库

遵循项目分层：
  CninfoClient 负责拿数据，CninfoFinanceService 负责编排和存储
  对标 business/stock/a_stock_service.py 的风格
"""
import datetime
import os
from loguru import logger

from core.client.cninfo_client import CninfoClient
from core.models.finance import CninfoAnnouncement
from core.models import StockInfo
from core.utils.db import db


# 默认配置
DEFAULT_YEARS = (2023, 2026)  # 默认查询年份区间
DEFAULT_CATEGORY = "年报"


class CninfoFinanceService:
    """巨潮资讯财报数据服务

    对标 AStockService：
      AStockService:        EastmoneyClient → 拉API → 存库
      CninfoFinanceService: CninfoClient    → 查询公告 → 清洗 → 存库
    """

    def __init__(self, request_delay: float = 1.0):
        self.client = CninfoClient(request_delay=request_delay)
        self.total_saved = 0

    # ================================================================
    # 前置准备：同步 orgId
    # ================================================================

    def sync_org_ids(self):
        """一次性同步：从远程加载 orgId → 写入 StockInfo 表

        建议在首次使用 cninfo 功能前执行一次。
        之后 Client 查 orgId 直接读库，不再依赖远程。
        """
        db.connect()
        logger.info("📥 开始同步 cninfo orgId 到 StockInfo 表")
        self.client.sync_org_ids_to_db()
        logger.info("✅ orgId 同步完成")

    # ================================================================
    # 入口
    # ================================================================

    def sync_announcements(
        self,
        stock_codes: list[str] | None = None,
        years: tuple | None = None,
        category: str = DEFAULT_CATEGORY,
    ):
        """主入口：查询财报公告 → 存库

        Args:
            stock_codes: 股票代码列表，如 ["000001", "600519"]；None 则从 StockInfo 取全部
            years: 年份区间，如 (2023, 2025)；None 则使用默认值
            category: 公告类别，默认 "年报"
        """
        # 建表
        db.connect()
        db.create_tables([CninfoAnnouncement], safe=True)
        logger.info("数据库表已确保创建")

        # 默认参数
        if years is None:
            years = DEFAULT_YEARS

        # 如果没指定股票，从 StockInfo 取全部
        if stock_codes is None:
            stock_codes = self._get_all_stock_codes()

        if not stock_codes:
            logger.error("❌ 没有可查询的股票，退出")
            return

        logger.info("📋 目标: {} 只股票 | 类别: {} | 年份: {}-{}",
                     len(stock_codes), category, years[0], years[1])

        # 逐只查询
        for i, code in enumerate(stock_codes):
            logger.info("=" * 50)
            logger.info("[{}/{}] 查询 {} 的{}公告", i + 1, len(stock_codes), code, category)

            try:
                # 1. 查询公告列表
                announcements = self.client.fetch_announcements(
                    stock_code=code,
                    years=years,
                    category=category,
                )

                if not announcements:
                    logger.warning("{} 无{}数据", code, category)
                    continue

                # 2. 清洗 + 存库
                saved = 0
                for ann in announcements:
                    if self._save_announcement(ann, category):
                        saved += 1

                self.total_saved += saved
                logger.info("✅ {} → 查询 {} 条，入库 {} 条，累计已保存 {} 条",
                             code, len(announcements), saved, self.total_saved)

            except Exception as e:
                logger.error("❌ [{}/{}] {} 查询失败: {}", i + 1, len(stock_codes), code, e)
                continue

        logger.info("=" * 50)
        logger.info("全部查询完成！共保存 {} 条公告", self.total_saved)

    def sync_announcements_by_random(
        self,
        count: int = 10,
        years: tuple | None = None,
        category: str = DEFAULT_CATEGORY,
    ):
        """从 StockInfo 随机取 N 只股票查询财报

        Args:
            count: 随机取几只股票
            years: 年份区间
            category: 公告类别
        """
        import random

        all_stocks = list(StockInfo.select(StockInfo.symbol))
        if not all_stocks:
            logger.warning("⚠️  StockInfo 表为空，请先运行 python main.py scheduler 同步股票列表")
            return

        sample_size = min(count, len(all_stocks))
        picked = random.sample(all_stocks, sample_size)
        codes = [s.symbol for s in picked]

        logger.info("🎲 随机抽取 {} 只股票: {}", len(codes), codes)
        self.sync_announcements(stock_codes=codes, years=years, category=category)

    # ================================================================
    # PDF 下载
    # ================================================================

    def download_pdfs(
        self,
        stock_codes: list[str] | None = None,
        years: tuple | None = None,
        category: str = DEFAULT_CATEGORY,
        output_dir: str = "./pdfs",
    ):
        """查询公告 + 下载 PDF

        Args:
            stock_codes: 股票代码列表
            years: 年份区间
            category: 公告类别
            output_dir: PDF 输出目录
        """
        # 建表
        db.connect()
        db.create_tables([CninfoAnnouncement], safe=True)

        if years is None:
            years = DEFAULT_YEARS

        if stock_codes is None:
            stock_codes = self._get_all_stock_codes()

        if not stock_codes:
            logger.error("❌ 没有可查询的股票，退出")
            return

        total_downloaded = 0

        for i, code in enumerate(stock_codes):
            logger.info("[{}/{}] 下载 {} 的{}PDF", i + 1, len(stock_codes), code, category)

            try:
                # 查询公告
                announcements = self.client.fetch_announcements(
                    stock_code=code,
                    years=years,
                    category=category,
                )

                # 下载 PDF
                paths = self.client.download_pdfs(
                    announcements,
                    output_dir=output_dir,
                    stock_code=code,
                )
                total_downloaded += len(paths)

                # 更新数据库中的本地路径
                for ann, path in zip(announcements, paths):
                    announcement_id = ann.get("announcementId", "")
                    if announcement_id and path:
                        CninfoAnnouncement.update(local_pdf_path=path).where(
                            CninfoAnnouncement.announcement_id == announcement_id
                        ).execute()

                # 同时存库
                for ann in announcements:
                    self._save_announcement(ann, category)

            except Exception as e:
                logger.error("❌ [{}/{}] {} 下载失败: {}", i + 1, len(stock_codes), code, e)
                continue

        logger.info("下载完成！共下载 {} 份 PDF", total_downloaded)

    # ================================================================
    # 辅助方法
    # ================================================================

    def _get_all_stock_codes(self) -> list[str]:
        """从 StockInfo 表获取全部股票代码"""
        stocks = list(StockInfo.select(StockInfo.symbol))
        if not stocks:
            logger.warning("⚠️  StockInfo 表为空，请先同步股票列表")
            return []
        return [s.symbol for s in stocks]

    def _save_announcement(self, ann: dict, category: str) -> bool:
        """保存单条公告到数据库

        使用 INSERT ... ON DUPLICATE KEY UPDATE 避免重复
        """
        announcement_id = str(ann.get("announcementId", ""))
        if not announcement_id:
            return False

        # 公告时间：毫秒时间戳 → 日期字符串
        announcement_time = ann.get("announcementTime", 0)
        announcement_date = ""
        if announcement_time:
            try:
                dt = datetime.datetime.fromtimestamp(announcement_time / 1000)
                announcement_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        row = {
            "sec_code": ann.get("secCode", ""),
            "sec_name": ann.get("secName", ""),
            "announcement_id": announcement_id,
            "announcement_title": ann.get("announcementTitle", ""),
            "announcement_time": announcement_time,
            "announcement_date": announcement_date,
            "adjunct_url": ann.get("adjunctUrl", ""),
            "category": category,
            "source": "cninfo",
            "fetched_at": datetime.datetime.now(),
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
        }

        try:
            self._raw_upsert(
                CninfoAnnouncement,
                row,
                conflict_keys=["announcement_id"],
                update_keys=["announcement_title", "announcement_time", "announcement_date",
                             "adjunct_url", "updated_at"],
            )
            return True
        except Exception as e:
            logger.debug("公告保存失败 {}: {}", announcement_id, e)
            return False

    def _raw_upsert(self, model, row: dict, conflict_keys: list[str], update_keys: list[str]):
        """原生 SQL upsert：INSERT ... ON DUPLICATE KEY UPDATE

        避免 Peewee on_conflict 在 MySQL 上的兼容性问题。
        """
        table = model._meta.table_name
        cols = list(row.keys())
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join(f"`{c}`" for c in cols)
        update_clause = ", ".join(f"`{k}` = VALUES(`{k}`)" for k in update_keys)

        sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
        values = tuple(row[c] for c in cols)

        conn = db.connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


# ─── 便捷函数（兼容旧 cninfo_finance.py 的调用方式）─────────

def get_reports(stock_code: str, years: tuple | None = None, category: str = DEFAULT_CATEGORY) -> list[dict]:
    """获取单只股票的财报公告列表（便捷函数）"""
    client = CninfoClient()
    return client.fetch_announcements(stock_code, years=years, category=category)


def download_pdfs(announcements: list[dict], output_dir: str = "./pdfs", stock_code: str | None = None) -> list[str]:
    """批量下载公告 PDF（便捷函数）"""
    client = CninfoClient()
    return client.download_pdfs(announcements, output_dir=output_dir, stock_code=stock_code)
