"""股吧爬虫服务 — 编排：爬取 → 清洗 → 存库

遵循项目分层：GubaClient 负责拿数据，GubaService 负责编排和存储
对标 business/stock/a_stock_service.py 的风格
"""
import random
import re
import datetime
from loguru import logger

from core.client.guba_client import GubaClient
from core.models.guba import GubaPost, GubaComment
from core.models import StockInfo
from core.utils.db import db


# 爬取配置
DEFAULT_POSTS_PER_STOCK = 300
DEFAULT_STOCK_COUNT = 10


def pick_random_stocks(count: int = DEFAULT_STOCK_COUNT) -> list[dict]:
    """从 StockInfo 表随机取 N 只股票

    Returns:
        [{"code": "600519", "name": "贵州茅台"}, ...]
    """
    all_stocks = list(StockInfo.select(StockInfo.symbol, StockInfo.name))
    if not all_stocks:
        logger.warning("⚠️  StockInfo 表为空，请先运行 python main.py scheduler 同步股票列表")
        return []

    sample_size = min(count, len(all_stocks))
    picked = random.sample(all_stocks, sample_size)
    return [{"code": s.symbol, "name": s.name} for s in picked]


class GubaService:
    """股吧数据服务

    对标 AStockService：
      AStockService: EastmoneyClient → 拉API → 存库
      GubaService:   GubaClient     → 爬页面 → 清洗 → 存库
    """

    def __init__(self, stocks: list[dict] | None = None, posts_per_stock: int = DEFAULT_POSTS_PER_STOCK):
        self.stocks = stocks
        self.posts_per_stock = posts_per_stock
        self.client = GubaClient(request_delay=1.5)
        self.total_saved = 0

    # ================================================================
    # 入口
    # ================================================================

    async def sync_all(self):
        """主入口：爬取所有目标股票的帖子"""
        # 建表
        db.connect()
        db.create_tables([GubaPost, GubaComment], safe=True)
        logger.info("数据库表已确保创建")

        # 如果没指定股票，从 StockInfo 随机取
        if self.stocks is None:
            self.stocks = pick_random_stocks(DEFAULT_STOCK_COUNT)

        if not self.stocks:
            logger.error("❌ 没有可爬取的股票，退出")
            return

        logger.info("📋 目标: {} 只股票 × {} 条/只 = 预计 {} 条",
                    len(self.stocks), self.posts_per_stock,
                    len(self.stocks) * self.posts_per_stock)
        for s in self.stocks:
            logger.info("   {} ({})", s["name"], s["code"])

        # 启动浏览器
        await self.client.start()

        try:
            for stock in self.stocks:
                code = stock["code"]
                name = stock["name"]
                logger.info("=" * 50)
                logger.info("开始爬取: {} ({})", name, code)

                # 1. 列表页 → 收集帖子URL
                post_list = await self.client.fetch_post_list(
                    stock_code=code,
                    max_pages=100,
                    max_posts=self.posts_per_stock,
                )
                if not post_list:
                    logger.warning("{} 无帖子数据，跳过", name)
                    continue

                # 2. 详情页 → 正文+评论
                for i, post_info in enumerate(post_list):
                    detail = await self.client.fetch_post_detail(post_info)

                    if not detail:
                        logger.warning("跳过失败帖子: {}", post_info["post_id"])
                        continue

                    # 3. 清洗
                    detail = self._clean_post(detail)

                    # 4. 存库
                    if detail.get("content"):
                        self._save_post(detail)
                        self.total_saved += 1
                        comment_count = len(detail.get("comments", []))
                        logger.info("✅ [{}/{}] {} | 评论{}条 | 正文{}字",
                                    i + 1, len(post_list), post_info["post_id"],
                                    comment_count, len(detail["content"]))
                    else:
                        logger.debug("跳过无正文帖子: {}", post_info["post_id"])

                logger.info("{} 爬取完成，累计已保存 {} 条", name, self.total_saved)

        finally:
            await self.client.stop()

        logger.info("=" * 50)
        logger.info("全部爬取完成！共保存 {} 条帖子", self.total_saved)

    # ================================================================
    # 数据清洗
    # ================================================================

    def _clean_post(self, data: dict) -> dict:
        """清洗帖子数据"""
        # 正文：去除多余空白
        if data.get("content"):
            data["content"] = data["content"].strip()
            # 去除超短正文（<10字）
            if len(data["content"]) < 10:
                data["content"] = ""

        # 标题：去除首尾空白
        if data.get("title"):
            data["title"] = data["title"].strip()

        # 评论：清洗内容
        cleaned_comments = []
        for c in data.get("comments", []):
            content = c.get("content", "").strip()
            if not content:
                continue
            # 过滤广告评论
            if any(kw in content for kw in ["加群", "V信", "荐股", "牛股推荐"]):
                continue
            c["content"] = content
            cleaned_comments.append(c)
        data["comments"] = cleaned_comments

        return data

    # ================================================================
    # 存储
    # ================================================================

    def _save_post(self, data: dict):
        """保存帖子+评论到数据库

        用原生 SQL 的 INSERT ... ON DUPLICATE KEY UPDATE，
        避免 Peewee on_conflict 的 MySQL 兼容性问题。
        """
        now = datetime.datetime.now()
        try:
            row = {
                "stock_code": data["stock_code"],
                "post_id": data["post_id"],
                "title": data["title"],
                "content": data["content"],
                "content_html": data["content_html"],
                "author": data["author"],
                "post_time": data["post_time"],
                "read_count": data["read_count"],
                "comment_count": data["comment_count"],
                "url": data["url"],
                # AI标注字段默认值（MySQL strict mode 需要显式填）
                "label": None,
                "confidence": None,
                "label_reason": "",
                "label_reviewed": 0,
                # ScxBaseModel 自动字段
                "source": "eastmoney",
                "fetched_at": now,
                "created_at": now,
                "updated_at": now,
            }
            self._raw_upsert(GubaPost, row,
                             conflict_keys=["stock_code", "post_id"],
                             update_keys=["title", "content", "content_html", "author",
                                          "post_time", "read_count", "comment_count", "updated_at"])
        except Exception as e:
            logger.error("保存帖子失败 {}: {}", data["post_id"], e)
            return

        # 评论
        for c in data.get("comments", []):
            try:
                c.setdefault("parent_reply_id", "")
                c.setdefault("region", "")
                c.setdefault("is_sub", 0)
                c["source"] = "eastmoney"
                c["fetched_at"] = now
                c["created_at"] = now
                c["updated_at"] = now
                if c.get("reply_id"):
                    self._raw_upsert(GubaComment, c,
                                     conflict_keys=["stock_code", "reply_id"],
                                     update_keys=["content", "updated_at"])
                else:
                    GubaComment.insert(**c).execute()
            except Exception as e:
                logger.debug("评论保存失败: {}", e)

    def _raw_upsert(self, model, row: dict, conflict_keys: list[str], update_keys: list[str]):
        """原生 SQL upsert：INSERT ... ON DUPLICATE KEY UPDATE

        避免 Peewee on_conflict 在 MySQL 上的兼容性问题。
        带 rollback + 连接及时释放，防止 Lock wait timeout。
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
