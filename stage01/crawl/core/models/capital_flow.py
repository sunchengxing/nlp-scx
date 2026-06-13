from peewee import (
    CharField, DateField,
    DecimalField, IntegerField, BooleanField,
)
from core.models.base import ScxBaseModel


# ============================================================
# 资金流向公共字段
# ============================================================

class CapitalFlowBase(ScxBaseModel):
    """资金流向公共字段 — abstract，不建表
    主力/超大单/大单/中单/小单 的净额+净占比，个股和大盘都有
    """
    class Meta:
        abstract = True

    main_net_amt = DecimalField(max_digits=18, decimal_places=4)    # 主力净流入-净额
    small_net_amt = DecimalField(max_digits=18, decimal_places=4)   # 小单净流入-净额
    mid_net_amt = DecimalField(max_digits=18, decimal_places=4)    # 中单净流入-净额
    big_net_amt = DecimalField(max_digits=18, decimal_places=4)    # 大单净流入-净额
    huge_net_amt = DecimalField(max_digits=18, decimal_places=4)   # 超大单净流入-净额
    main_net_pct = DecimalField(max_digits=8, decimal_places=4)    # 主力净流入-净占比%
    small_net_pct = DecimalField(max_digits=8, decimal_places=4)   # 小单净流入-净占比%
    mid_net_pct = DecimalField(max_digits=8, decimal_places=4)     # 中单净流入-净占比%
    big_net_pct = DecimalField(max_digits=8, decimal_places=4)     # 大单净流入-净占比%
    huge_net_pct = DecimalField(max_digits=8, decimal_places=4)    # 超大单净流入-净占比%


# ============================================================
# P0 — 资金流向核心表
# ============================================================

class CapitalFlowStock(CapitalFlowBase):
    """个股资金流 — 建表 scx_capital_flow_stock
    对应接口: ak.stock_individual_fund_flow(stock, market)
    """
    class Meta:
        table_name = "scx_capital_flow_stock"
        indexes = (
            (("symbol", "trade_date"), True),  # 联合唯一
        )

    # API 入参补充（返回中没有这两个字段）
    symbol = CharField(max_length=6)                                   # 唯一索引已覆盖
    market = CharField(max_length=2)                                 # "sh"/"sz"/"bj"

    # API 返回字段
    trade_date = DateField()                                          # 唯一索引已覆盖
    close_price = DecimalField(max_digits=12, decimal_places=4)     # 收盘价
    change_pct = DecimalField(max_digits=8, decimal_places=4)       # 涨跌幅%


class CapitalFlowMarket(CapitalFlowBase):
    """大盘资金流 — 建表 scx_capital_flow_market
    对应接口: ak.stock_market_fund_flow()
    """
    class Meta:
        table_name = "scx_capital_flow_market"
        indexes = (
            (("trade_date",), True),  # 每天唯一一条
        )

    trade_date = DateField()                                          # 唯一索引已覆盖
    sh_close = DecimalField(max_digits=12, decimal_places=4)        # 上证-收盘价
    sh_change_pct = DecimalField(max_digits=8, decimal_places=4)   # 上证-涨跌幅%
    sz_close = DecimalField(max_digits=12, decimal_places=4)       # 深证-收盘价
    sz_change_pct = DecimalField(max_digits=8, decimal_places=4)   # 深证-涨跌幅%


# ============================================================
# P1 — 资金流向排行/板块
# ============================================================

class CapitalFlowMainRank(ScxBaseModel):
    """主力净流入排名 — 建表 scx_capital_flow_main_rank
    对应接口: ak.stock_main_fund_flow(symbol) + ak.stock_individual_fund_flow_rank(indicator)
    indicator: "今日"/"3日"/"5日"/"10日"
    """
    class Meta:
        table_name = "scx_capital_flow_main_rank"
        indexes = (
            (("symbol", "indicator", "trade_date"), True),
        )

    symbol = CharField(max_length=6)                                   # 唯一索引已覆盖
    name = CharField(max_length=32)                                  # 名称
    indicator = CharField(max_length=8)                                 # 唯一索引已覆盖
    latest_price = DecimalField(max_digits=12, decimal_places=4)     # 最新价
    change_pct = DecimalField(max_digits=8, decimal_places=4, null=True)  # 涨跌幅%
    main_net_pct = DecimalField(max_digits=8, decimal_places=4)     # 主力净占比%
    main_rank = IntegerField(null=True)                              # 主力排名
    huge_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)   # 超大单净流入额
    huge_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)    # 超大单净占比%
    big_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)    # 大单净流入额
    big_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)     # 大单净占比%
    mid_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)    # 中单净流入额
    mid_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)     # 中单净占比%
    small_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)  # 小单净流入额
    small_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)   # 小单净占比%
    sector = CharField(max_length=32, null=True)                    # 所属板块（main_flow 专有）
    trade_date = DateField()                                          # 唯一索引已覆盖


class CapitalFlowSector(ScxBaseModel):
    """板块资金流 — 建表 scx_capital_flow_sector
    对应接口: ak.stock_sector_fund_flow_rank + stock_sector_fund_flow_summary
              + stock_sector_fund_flow_hist + stock_concept_fund_flow_hist
    4个接口字段结构相似，用 sector_type + data_type 区分
    """
    class Meta:
        table_name = "scx_capital_flow_sector"
        indexes = (
            (("sector_name", "sector_type", "data_type", "indicator", "trade_date"), True),
        )

    sector_name = CharField(max_length=64)                             # 唯一索引已覆盖
    sector_type = CharField(max_length=8)                              # 唯一索引已覆盖
    data_type = CharField(max_length=8)                               # 唯一索引已覆盖
    indicator = CharField(max_length=8, default="")                 # "今日"/"5日"/"10日"（rank/summary用）
    trade_date = DateField()                                          # 唯一索引已覆盖
    latest_price = DecimalField(max_digits=12, decimal_places=4, null=True)  # 最新价（summary用）
    change_pct = DecimalField(max_digits=8, decimal_places=4, null=True)     # 涨跌幅%
    main_net_amt = DecimalField(max_digits=18, decimal_places=4)    # 主力净流入额
    main_net_pct = DecimalField(max_digits=8, decimal_places=4)     # 主力净占比%
    huge_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)  # 超大单净流入额
    huge_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)   # 超大单净占比%
    big_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)   # 大单净流入额
    big_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)    # 大单净占比%
    mid_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)    # 中单净流入额
    mid_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)     # 中单净占比%
    small_net_amt = DecimalField(max_digits=18, decimal_places=4, null=True)  # 小单净流入额
    small_net_pct = DecimalField(max_digits=8, decimal_places=4, null=True)   # 小单净占比%
    top_stock = CharField(max_length=32, null=True)                 # 主力净流入最大股（rank专有）
    top_stock_code = CharField(max_length=6, null=True)            # 最大股代码（rank专有）
    is_net_inflow = BooleanField(null=True)                         # 是否净流入（rank专有）


class CapitalFlowHsgt(ScxBaseModel):
    """沪深港通资金流向 — 建表 scx_capital_flow_hsgt
    对应接口: ak.stock_hsgt_fund_flow_summary_em()
    """
    class Meta:
        table_name = "scx_capital_flow_hsgt"
        indexes = (
            (("trade_date", "mutual_type"), True),
        )

    trade_date = DateField()                                          # 唯一索引已覆盖
    mutual_type = CharField(max_length=16)                           # 类型：沪股通/深股通/沪深港通
    board_type = CharField(max_length=16, default="")               # 板块
    direction = CharField(max_length=8, default="")                 # 资金方向：流入/流出
    index_name = CharField(max_length=32, default="")               # 相关指数
    status = CharField(max_length=16, default="")                   # 交易状态
    net_inflow = DecimalField(max_digits=18, decimal_places=4)      # 资金净流入
    daily_balance = DecimalField(max_digits=18, decimal_places=4, null=True)  # 当日资金余额
    up_count = IntegerField(null=True)                              # 上涨数
    down_count = IntegerField(null=True)                            # 下跌数
    flat_count = IntegerField(null=True)                            # 持平数
    index_change_pct = DecimalField(max_digits=8, decimal_places=4, null=True) # 指数涨跌幅%
    net_buy_amt = DecimalField(max_digits=18, decimal_places=4, null=True)     # 成交净买额
