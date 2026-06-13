import enum


class PeriodEnum(enum.Enum):
    """K线周期"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MinutePeriodEnum(enum.Enum):
    """分钟线周期"""
    MIN_1 = "1"
    MIN_5 = "5"
    MIN_15 = "15"
    MIN_30 = "30"
    MIN_60 = "60"


class SideEnum(enum.Enum):
    """买卖方向"""
    BUY = "buy"
    SELL = "sell"


class SectorTypeEnum(enum.Enum):
    """板块类型"""
    INDUSTRY = "行业资金流"
    CONCEPT = "概念资金流"
    REGION = "地域资金流"


class HsgtTypeEnum(enum.Enum):
    """沪深港通类型"""
    HGT = "沪股通"     # 沪港通-沪股
    SGT = "深股通"     # 深港通-深股
    HSCCJ = "沪深港通"  # 合计