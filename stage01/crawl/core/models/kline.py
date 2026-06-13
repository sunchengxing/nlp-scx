import datetime
from peewee import (
    CharField, DateField, DateTimeField,
    DecimalField, BigIntegerField,
)
from core.models.base import ScxBaseModel

class StockKlineBase (ScxBaseModel):
    """K线公共字段 — abstract，不建表"""

    class Meta:
        abstract = True
    symbol = CharField(max_length=6)  # 子类唯一索引覆盖
    open = DecimalField(max_digits=12, decimal_places=4)  # 开盘
    close = DecimalField(max_digits=12, decimal_places=4)  # 收盘
    high = DecimalField(max_digits=12, decimal_places=4)  # 最高
    low = DecimalField(max_digits=12, decimal_places=4)  # 最低
    volume = BigIntegerField()  # 成交量
    amount = DecimalField(max_digits=18, decimal_places=4)  # 成交额
    period = CharField(max_length=8)  # 子类唯一索引覆盖
    adjust = CharField(max_length=3, default="")  # ""/"qfq"/"hfq"


class StockKlineDaily(StockKlineBase):
    """日/周/月K线 — 建表 scx_stock_kline_daily"""
    class Meta:
        table_name = "scx_stock_kline_daily"
        indexes = (
            (("symbol", "trade_date", "period", "adjust"), True),  # 联合唯一
        )

    # 日/周/月线共有、分钟线没有的字段
    trade_date = DateField()  # 唯一索引已覆盖
    amplitude = DecimalField(max_digits=8, decimal_places=4)  # 振幅%
    change_pct = DecimalField(max_digits=8, decimal_places=4)  # 涨跌幅%
    change_amt = DecimalField(max_digits=12, decimal_places=4)  # 涨跌额
    turnover = DecimalField(max_digits=8, decimal_places=4)  # 换手率%



class StockKlineMinute(StockKlineBase):
    """分钟K线 — 建表 scx_stock_kline_minute"""

    class Meta:
        table_name = "scx_stock_kline_minute"
        indexes = (
            (("symbol", "trade_time", "period"), True),  # 联合唯一
        )
        
    # 分钟线独有字段
    trade_time = DateTimeField()  # 唯一索引已覆盖
    avg_price = DecimalField(max_digits=12, decimal_places=4)  # 均价


class StockIntradayTick(ScxBaseModel):
    """分时数据 — 建表 scx_stock_intraday_tick"""
    class Meta:
        table_name = "scx_stock_intraday_tick"
        indexes = (
            (("symbol", "trade_time"), False),  # 联合普通索引
        )

    symbol = CharField(max_length=6, index=True)
    trade_time = DateTimeField(index=True)  # 成交时间
    price = DecimalField(max_digits=12, decimal_places=4)  # 成交价
    volume = BigIntegerField()  # 成交量
    type = CharField(max_length=4, default="")  # 买/卖/中

class StockInfo(ScxBaseModel):
    """股票信息表 — 建表 scx_stock_info"""
    class Meta:
        table_name = "scx_stock_info"
        indexes = (
            (("symbol",), True),  # 单字段唯一索引
        )

    symbol = CharField(max_length=6)                   # 唯一索引已覆盖，不需要 index=True
    name = CharField(max_length=32, index=True)     # 股票名称，如 "平安银行"
    market = CharField(max_length=4, default="A股")  # 市场类型
    cninfo_org_id = CharField(max_length=32, default="", verbose_name="巨潮资讯orgId")  # cninfo 内部 ID，如 "gssz0000001"