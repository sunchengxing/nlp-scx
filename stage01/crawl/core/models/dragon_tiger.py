from peewee import (
    CharField, DateField, DateTimeField,
    DecimalField, IntegerField,
)
from core.models.base import ScxBaseModel


# ============================================================
# P0 — 龙虎榜核心表
# ============================================================

class LhbDetail(ScxBaseModel):
    """龙虎榜详情 — 建表 scx_lhb_detail
    对应接口: ak.stock_lhb_detail_em(start_date, end_date)
    """
    class Meta:
        table_name = "scx_lhb_detail"
        indexes = (
            (("symbol", "list_date"), True),  # 联合唯一：一只股票一天只上榜一次
        )

    # API 返回字段
    symbol = CharField(max_length=6)                                   # 唯一索引已覆盖
    name = CharField(max_length=32)                                  # 名称
    list_date = DateField()                                           # 唯一索引已覆盖    interpretation = CharField(max_length=128, default="")           # 解读，如 "主力做T，成功率51.18%"
    close_price = DecimalField(max_digits=12, decimal_places=4)      # 收盘价
    change_pct = DecimalField(max_digits=8, decimal_places=4)        # 涨跌幅%
    lhb_net_buy = DecimalField(max_digits=18, decimal_places=4)      # 龙虎榜净买额
    lhb_buy_amt = DecimalField(max_digits=18, decimal_places=4)      # 龙虎榜买入额
    lhb_sell_amt = DecimalField(max_digits=18, decimal_places=4)     # 龙虎榜卖出额
    lhb_total_amt = DecimalField(max_digits=18, decimal_places=4)    # 龙虎榜成交额
    market_total_amt = DecimalField(max_digits=18, decimal_places=4) # 市场总成交额
    net_buy_ratio = DecimalField(max_digits=8, decimal_places=4)     # 净买额占总成交比%
    total_amt_ratio = DecimalField(max_digits=8, decimal_places=4)   # 成交额占总成交比%
    turnover = DecimalField(max_digits=8, decimal_places=4)          # 换手率%
    float_market_cap = DecimalField(max_digits=18, decimal_places=4) # 流通市值（元）
    reason = CharField(max_length=256)                              # 上榜原因
    return_1d = DecimalField(max_digits=8, decimal_places=4, null=True)   # 上榜后1日涨跌幅%
    return_2d = DecimalField(max_digits=8, decimal_places=4, null=True)   # 上榜后2日
    return_5d = DecimalField(max_digits=8, decimal_places=4, null=True)   # 上榜后5日
    return_10d = DecimalField(max_digits=8, decimal_places=4, null=True)  # 上榜后10日


class LhbSeatDetail(ScxBaseModel):
    """席位买卖明细 — 建表 scx_lhb_seat_detail
    对应接口: ak.stock_lhb_stock_detail_em(symbol, date, flag)
    龙虎榜子表：通过 (symbol, list_date) 关联 LhbDetail
    """
    class Meta:
        table_name = "scx_lhb_seat_detail"
        indexes = (
            (("symbol", "list_date", "branch_name", "side"), True),  # 联合唯一
        )

    # API 入参补充（返回中没有这两个字段）
    symbol = CharField(max_length=6)                                   # 唯一索引已覆盖
    list_date = DateField()                                           # 唯一索引已覆盖

    # API 返回字段
    branch_name = CharField(max_length=256)                          # 交易营业部名称
    buy_amt = DecimalField(max_digits=18, decimal_places=4, default=0)  # 买入金额
    buy_ratio = DecimalField(max_digits=8, decimal_places=4, default=0) # 买入金额-占总成交比例%
    sell_amt = DecimalField(max_digits=18, decimal_places=4, default=0) # 卖出金额
    sell_ratio = DecimalField(max_digits=8, decimal_places=4, default=0) # 卖出金额-占总成交比例%
    net_amt = DecimalField(max_digits=18, decimal_places=4)         # 净额
    side = CharField(max_length=8)                                   # 唯一索引已覆盖


# ============================================================
# P1 — 龙虎榜补充表
# ============================================================

class LhbInstitutionDaily(ScxBaseModel):
    """机构买卖每日统计 — 建表 scx_lhb_institution_daily
    对应接口: ak.stock_lhb_jgmmtj_em(start_date, end_date)
    """
    class Meta:
        table_name = "scx_lhb_institution_daily"
        indexes = (
            (("symbol", "list_date"), True),
        )

    symbol = CharField(max_length=6)                                   # 唯一索引已覆盖
    name = CharField(max_length=32)                                   # 名称
    close_price = DecimalField(max_digits=12, decimal_places=4)       # 收盘价
    change_pct = DecimalField(max_digits=8, decimal_places=4)        # 涨跌幅%
    buy_inst_count = IntegerField()                                   # 买方机构数
    sell_inst_count = IntegerField()                                  # 卖方机构数
    inst_buy_total = DecimalField(max_digits=18, decimal_places=4)    # 机构买入总额
    inst_sell_total = DecimalField(max_digits=18, decimal_places=4)   # 机构卖出总额
    inst_net_buy = DecimalField(max_digits=18, decimal_places=4)      # 机构买入净额
    market_total_amt = DecimalField(max_digits=18, decimal_places=4)  # 市场总成交额
    inst_net_ratio = DecimalField(max_digits=8, decimal_places=4)    # 机构净买额占总成交额比%
    turnover = DecimalField(max_digits=8, decimal_places=4)          # 换手率%
    float_market_cap = DecimalField(max_digits=12, decimal_places=4) # 流通市值（亿元）
    reason = CharField(max_length=256)                               # 上榜原因
    list_date = DateField()                                           # 唯一索引已覆盖期


class LhbBranchActive(ScxBaseModel):
    """每日活跃营业部 — 建表 scx_lhb_branch_active
    对应接口: ak.stock_lhb_hyyyb_em(start_date, end_date)
    """
    class Meta:
        table_name = "scx_lhb_branch_active"
        indexes = (
            (("branch_code", "list_date"), True),
        )

    branch_name = CharField(max_length=256)                            # 唯一索引已覆盖
    list_date = DateField()                                           # 唯一索引已覆盖    buy_stock_count = IntegerField()                                 # 买入个股数
    sell_stock_count = IntegerField()                                # 卖出个股数
    buy_total_amt = DecimalField(max_digits=18, decimal_places=4)   # 买入总金额
    sell_total_amt = DecimalField(max_digits=18, decimal_places=4)  # 卖出总金额
    net_amt = DecimalField(max_digits=18, decimal_places=4)         # 总买卖净额
    buy_stocks = CharField(max_length=512, default="")              # 买入股票名称列表
    branch_code = CharField(max_length=16)                            # 唯一索引已覆盖


# ============================================================
# P2 — 龙虎榜统计表（可从明细聚合，按需建表）
# ============================================================

class LhbBranchStatistic(ScxBaseModel):
    """营业部统计/排行 — 建表 scx_lhb_branch_statistic
    对应接口: ak.stock_lhb_traderstatistic_em + ak.stock_lhb_yybph_em
    stat_type: "statistic"(统计) / "rank"(排行)
    """
    class Meta:
        table_name = "scx_lhb_branch_statistic"
        indexes = (
            (("branch_name", "stat_type", "stat_range"), True),
        )

    branch_name = CharField(max_length=256)                            # 唯一索引已覆盖
    stat_type = CharField(max_length=8)                               # 唯一索引已覆盖
    stat_range = CharField(max_length=8)                             # 近一月/近三月/近六月/近一年

    # statistic 接口字段
    total_amt = DecimalField(max_digits=18, decimal_places=4, null=True)   # 龙虎榜成交金额
    list_count = IntegerField(null=True)                                   # 上榜次数
    buy_amt = DecimalField(max_digits=18, decimal_places=4, null=True)    # 买入额
    buy_count = IntegerField(null=True)                                    # 买入次数
    sell_amt = DecimalField(max_digits=18, decimal_places=4, null=True)    # 卖出额
    sell_count = IntegerField(null=True)                                  # 卖出次数

    # rank 接口字段（上榜后N天表现）
    rank_1d_buy_count = IntegerField(null=True)                       # 上榜后1天-买入次数
    rank_1d_avg_return = DecimalField(max_digits=8, decimal_places=4, null=True)   # 平均涨幅
    rank_1d_up_prob = DecimalField(max_digits=8, decimal_places=4, null=True)      # 上涨概率%
    rank_2d_buy_count = IntegerField(null=True)
    rank_2d_avg_return = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_2d_up_prob = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_3d_buy_count = IntegerField(null=True)
    rank_3d_avg_return = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_3d_up_prob = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_5d_buy_count = IntegerField(null=True)
    rank_5d_avg_return = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_5d_up_prob = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_10d_buy_count = IntegerField(null=True)
    rank_10d_avg_return = DecimalField(max_digits=8, decimal_places=4, null=True)
    rank_10d_up_prob = DecimalField(max_digits=8, decimal_places=4, null=True)
