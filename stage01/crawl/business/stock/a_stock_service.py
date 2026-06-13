import time
import random
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
from peewee import IntegrityError

from core.service.stock_service import BaseStockService
from core.client.eastmoney_client import EastmoneyClient
from core.models import StockInfo, StockKlineDaily, CapitalFlowStock, LhbDetail


class AStockService(BaseStockService):
    """
    A股服务实现
    组合 EastmoneyClient 负责请求，Service 负责编排（拉数据 + 存库）
    """

    def __init__(self):
        self.client = EastmoneyClient()

    # ============================================================
    # 股票列表
    # ============================================================

    def sync_stock_list(self):
        """获取所有A股代码 → 存库"""
        logger.info("📥 开始同步股票列表")
        resp = self.client.fetch_stock_list()

        if not resp:
            logger.warning("⚠️ 股票列表返回为空")
            return

        # 响应结构: {"data": [...], "rows": N, "truncated": bool, "columns": [...]}
        items = resp.get("data", resp) if isinstance(resp, dict) else resp
        if not isinstance(items, list):
            logger.warning("⚠️ 股票列表格式异常: {}", type(items))
            return

        truncated = resp.get("truncated", False) if isinstance(resp, dict) else False
        total_rows = resp.get("rows", len(items)) if isinstance(resp, dict) else len(items)
        logger.info("📊 接口返回 {} 条, truncated={}", len(items), truncated)
        if truncated:
            logger.warning("⚠️ 数据被截断！共 {} 条只拿到 {} 条，需要分页或调整接口参数", total_rows, len(items))

        # 批量插入，每 500 条一批
        batch_size = 500
        batch = []
        inserted = 0
        for i, item in enumerate(items):
            code = str(item.get("code", item.get("symbol", ""))).strip()
            name = str(item.get("name", "")).strip()
            if not code:
                continue
            batch.append({"symbol": code, "name": name, "market": "A股"})

            if len(batch) >= batch_size:
                inserted += self._batch_upsert(StockInfo, batch)
                batch = []
                logger.info("⏳ 已处理 {}/{}", i + 1, len(items))

        # 处理剩余
        if batch:
            inserted += self._batch_upsert(StockInfo, batch)

        logger.info("✅ 股票列表同步完成: {} 条入库", inserted)

    def _batch_upsert(self, model, batch: list[dict]) -> int:
        """批量插入，遇到重复跳过（INSERT IGNORE）"""
        if not batch:
            return 0
        try:
            table = model._meta.table_name
            fields = list(batch[0].keys())
            cols = ", ".join(f"`{f}`" for f in fields)
            placeholders = ", ".join(["%s"] * len(fields))
            sql = f"INSERT IGNORE INTO `{table}` ({cols}) VALUES ({placeholders})"
            values = [tuple(item[f] for f in fields) for item in batch]
            from core.utils.db import db
            conn = db.connection()
            cursor = conn.cursor()
            cursor.executemany(sql, values)
            conn.commit()
            return len(batch)
        except Exception as e:
            logger.warning("⚠️ 批量插入失败，降级逐条: {}", e)
            count = 0
            for data in batch:
                try:
                    model.create(**data)
                    count += 1
                except IntegrityError:
                    pass
            return count

    # ============================================================
    # K线
    # ============================================================

    def sync_kline_daily(self, symbol, period="daily",
                         start_date=None, end_date=None, adjust="qfq"):
        """拉取日/周/月K线 → 存库"""
        # 默认取一周
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        resp = self.client.fetch_kline_daily(symbol, period, start_date, end_date, adjust)

        if not resp:
            logger.warning("⚠️ K线数据返回为空: symbol={}", symbol)
            return

        df = pd.DataFrame(resp) if isinstance(resp, list) else pd.DataFrame(resp)

        # 中文列名 → Model 字段映射
        field_map = {
            "日期": "trade_date", "股票代码": "symbol",
            "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount",
            "振幅": "amplitude", "涨跌幅": "change_pct",
            "涨跌额": "change_amt", "换手率": "turnover",
        }

        inserted, updated = 0, 0
        for _, row in df.iterrows():
            data = {}
            for cn_name, model_field in field_map.items():
                col = cn_name
                if col in row and pd.notna(row[col]):
                    data[model_field] = row[col]

            # 补充 period 和 adjust
            data["period"] = period
            data["adjust"] = adjust

            if "symbol" not in data:
                data["symbol"] = symbol

            try:
                StockKlineDaily.create(**data)
                inserted += 1
            except IntegrityError:
                query = (
                    (StockKlineDaily.symbol == data["symbol"]) &
                    (StockKlineDaily.trade_date == data["trade_date"]) &
                    (StockKlineDaily.period == data["period"]) &
                    (StockKlineDaily.adjust == data["adjust"])
                )
                StockKlineDaily.update(**data).where(query).execute()
                updated += 1

        logger.info("✅ K线[{}] {} → {} 新增, {} 更新", period, symbol, inserted, updated)

    def sync_kline_minute(self, symbol, period="5",
                          start_date=None, end_date=None, adjust=""):
        """拉取分钟K线 → 存库"""
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d 09:30:00")

        resp = self.client.fetch_kline_minute(symbol, period, start_date, end_date, adjust)

        if not resp:
            return

        df = pd.DataFrame(resp) if isinstance(resp, list) else pd.DataFrame(resp)

        field_map = {
            "时间": "trade_time",
            "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
            "成交量": "volume", "成交额": "amount", "均价": "avg_price",
        }

        inserted, updated = 0, 0
        for _, row in df.iterrows():
            data = {"symbol": symbol, "period": period, "adjust": adjust}
            for cn_name, model_field in field_map.items():
                if cn_name in row and pd.notna(row[cn_name]):
                    data[model_field] = row[cn_name]

            try:
                from core.models import StockKlineMinute
                StockKlineMinute.create(**data)
                inserted += 1
            except IntegrityError:
                query = (
                    (StockKlineMinute.symbol == data["symbol"]) &
                    (StockKlineMinute.trade_time == data["trade_time"]) &
                    (StockKlineMinute.period == data["period"])
                )
                StockKlineMinute.update(**data).where(query).execute()
                updated += 1

        logger.info("✅ 分钟线[{}] {} → {} 新增, {} 更新", period, symbol, inserted, updated)

    # ============================================================
    # 龙虎榜
    # ============================================================

    def sync_lhb_detail(self, start_date=None, end_date=None):
        """拉取龙虎榜详情 → 存库"""
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        resp = self.client.fetch_lhb_detail(start_date, end_date)

        if not resp:
            return

        df = pd.DataFrame(resp) if isinstance(resp, list) else pd.DataFrame(resp)

        field_map = {
            "代码": "symbol", "名称": "name", "上榜日": "list_date",
            "解读": "interpretation", "收盘价": "close_price", "涨跌幅": "change_pct",
            "龙虎榜净买额": "lhb_net_buy", "龙虎榜买入额": "lhb_buy_amt",
            "龙虎榜卖出额": "lhb_sell_amt", "龙虎榜成交额": "lhb_total_amt",
            "市场总成交额": "market_total_amt", "净买额占总成交比": "net_buy_ratio",
            "成交额占总成交比": "total_amt_ratio", "换手率": "turnover",
            "流通市值": "float_market_cap", "上榜原因": "reason",
            "上榜后1日": "return_1d", "上榜后2日": "return_2d",
            "上榜后5日": "return_5d", "上榜后10日": "return_10d",
        }

        inserted, updated = 0, 0
        for _, row in df.iterrows():
            data = {}
            for cn_name, model_field in field_map.items():
                if cn_name in row and pd.notna(row[cn_name]):
                    data[model_field] = row[cn_name]

            try:
                LhbDetail.create(**data)
                inserted += 1
            except IntegrityError:
                query = (
                    (LhbDetail.symbol == data["symbol"]) &
                    (LhbDetail.list_date == data["list_date"])
                )
                LhbDetail.update(**data).where(query).execute()
                updated += 1

        logger.info("✅ 龙虎榜 → {} 新增, {} 更新", inserted, updated)

    # ============================================================
    # 资金流向
    # ============================================================

    def sync_capital_flow_stock(self, symbol, market="sz"):
        """拉取个股资金流 → 存库"""
        resp = self.client.fetch_capital_flow_stock(symbol, market)

        if not resp:
            return

        df = pd.DataFrame(resp) if isinstance(resp, list) else pd.DataFrame(resp)

        field_map = {
            "日期": "trade_date",
            "主力净流入-净额": "main_net_amt", "小单净流入-净额": "small_net_amt",
            "中单净流入-净额": "mid_net_amt", "大单净流入-净额": "big_net_amt",
            "超大单净流入-净额": "huge_net_amt",
            "主力净流入-净占比": "main_net_pct", "小单净流入-净占比": "small_net_pct",
            "中单净流入-净占比": "mid_net_pct", "大单净流入-净占比": "big_net_pct",
            "超大单净流入-净占比": "huge_net_pct",
            "收盘价": "close_price", "涨跌幅": "change_pct",
        }

        inserted, updated = 0, 0
        for _, row in df.iterrows():
            data = {"symbol": symbol, "market": market}
            for cn_name, model_field in field_map.items():
                if cn_name in row and pd.notna(row[cn_name]):
                    data[model_field] = row[cn_name]

            try:
                CapitalFlowStock.create(**data)
                inserted += 1
            except IntegrityError:
                query = (
                    (CapitalFlowStock.symbol == data["symbol"]) &
                    (CapitalFlowStock.trade_date == data["trade_date"])
                )
                CapitalFlowStock.update(**data).where(query).execute()
                updated += 1

        logger.info("✅ 个股资金流 {} → {} 新增, {} 更新", symbol, inserted, updated)

    # ============================================================
    # 定时任务：随机10只股票拉一周数据
    # ============================================================

    def sync_random_stocks_weekly(self):
        """从 StockInfo 表随机选10只，拉一周内所有数据入库，请求间隔2~5秒"""
        logger.info("🎲 开始随机抽取10只股票拉取一周数据")

        # 1. 从数据库随机取10只
        all_stocks = list(StockInfo.select(StockInfo.symbol))
        if not all_stocks:
            logger.warning("⚠️ StockInfo 表为空，请先执行 sync_stock_list")
            return

        sample_size = min(10, len(all_stocks))
        picked = random.sample(all_stocks, sample_size)
        symbols = [s.symbol for s in picked]
        logger.info("🎲 抽中股票: {}", symbols)

        # 2. 计算一周日期范围
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        # 3. 逐只拉取
        for i, symbol in enumerate(symbols, 1):
            logger.info("📊 [{}/{}] 开始拉取 {} 的数据", i, len(symbols), symbol)

            # 推算 market（0/3开头=sz, 6开头=sh, 8/4开头=bj）
            market = "sz" if symbol[0] in ("0", "3") else "sh" if symbol[0] == "6" else "bj"

            try:
                # 日线
                self.sync_kline_daily(symbol, period="daily",
                                      start_date=start_date, end_date=end_date, adjust="qfq")
                self._random_delay()

                # 5分钟线
                self.sync_kline_minute(symbol, period="5",
                                       start_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d 09:30:00"),
                                       end_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                self._random_delay()

                # 个股资金流
                self.sync_capital_flow_stock(symbol, market=market)
                self._random_delay()

                logger.info("✅ [{}/{}] {} 全部完成", i, len(symbols), symbol)

            except Exception as e:
                logger.error("❌ [{}/{}] {} 拉取失败: {}", i, len(symbols), symbol, e)
                continue

        # 4. 龙虎榜（不按个股，按日期范围拉）
        try:
            self.sync_lhb_detail(start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.error("❌ 龙虎榜拉取失败: {}", e)

        logger.info("🎉 本轮随机采集任务完成")

    def _random_delay(self):
        """请求间隔：2~5秒随机"""
        delay = random.uniform(2, 5)
        logger.debug("⏳ 等待 {:.1f}s", delay)
        time.sleep(delay)


if __name__ == '__main__':
    aStock = AStockService()
    resp = aStock.client.fetch_stock_list()
    logger.info("✅ 获取所有A股代码 {}", resp)
