# AKShare 交易数据 Model 设计文档

> 基于 AKShare 东方财富接口实际返回字段设计
> ORM：Peewee | 数据库：MySQL | 表前缀：`scx_`
> 对应接口文档：[结构化数据-交易信息爬取AKShare API 清单](./结构化数据-交易信息爬取AKShare%20API%20清单.md)

---

## 一、Model 总览

### 1.1 按模块分文件

| 文件 | 数据类型 | Model 数量 | Model 列表 |
|------|---------|-----------|-----------|
| `kline.py` | K线行情 | **3** | StockKlineDaily, StockKlineMinute, StockIntradayTick |
| `dragon_tiger.py` | 龙虎榜 | **5** | LhbDetail, LhbSeatDetail, LhbInstitutionDaily, LhbBranchActive, LhbBranchStatistic |
| `capital_flow.py` | 资金流向 | **5** | CapitalFlowStock, CapitalFlowMarket, CapitalFlowMainRank, CapitalFlowSector, CapitalFlowHsgt |
| `base.py` | 公共基类+枚举 | — | ScxBaseModel, PeriodEnum, SideEnum 等 |

**合计：13 个业务 Model + 1 个基类**

### 1.2 Model 与 API 对应关系

| Model | 对应 AKShare 接口 | 优先级 |
|-------|-----------------|--------|
| **StockKlineDaily** | `stock_zh_a_hist` (daily/weekly/monthly) | P0 必须 |
| **StockKlineMinute** | `stock_zh_a_hist_min_em` | P0 必须 |
| **StockIntradayTick** | `stock_intraday_em` | P2 可选 |
| **LhbDetail** | `stock_lhb_detail_em` | P0 必须 |
| **LhbSeatDetail** | `stock_lhb_stock_detail_em` | P0 必须 |
| **LhbInstitutionDaily** | `stock_lhb_jgmmtj_em` | P1 重要 |
| **LhbBranchActive** | `stock_lhb_hyyyb_em` | P1 重要 |
| **LhbBranchStatistic** | `stock_lhb_traderstatistic_em` + `stock_lhb_yybph_em` | P2 可选 |
| **CapitalFlowStock** | `stock_individual_fund_flow` | P0 必须 |
| **CapitalFlowMarket** | `stock_market_fund_flow` | P0 必须 |
| **CapitalFlowMainRank** | `stock_main_fund_flow` + `stock_individual_fund_flow_rank` | P1 重要 |
| **CapitalFlowSector** | `stock_sector_fund_flow_rank` + `stock_sector_fund_flow_summary` + `stock_sector_fund_flow_hist` + `stock_concept_fund_flow_hist` | P1 重要 |
| **CapitalFlowHsgt** | `stock_hsgt_fund_flow_summary_em` | P1 重要 |

### 1.3 为什么从 24 个 API 精简到 13 个 Model？

| 策略 | 说明 |
|------|------|
| **同结构合并** | `stock_sector_fund_flow_hist` / `stock_concept_fund_flow_hist` 字段完全一致，用 `sector_type` 枚举区分 |
| **统计表合并** | `stock_lhb_traderstatistic_em` + `stock_lhb_yybph_em` 都是营业部维度，合并到 `LhbBranchStatistic`，用 `stat_type` 区分 |
| **排行合并** | `stock_main_fund_flow` + `stock_individual_fund_flow_rank` 结构类似，合并到 `CapitalFlowMainRank`，用 `indicator` 区分 |
| **跳过纯查询辅助** | `stock_lhb_stock_detail_date_em`（3个字段的日期查询辅助）不需要建表 |
| **跳过聚合统计** | `stock_lhb_stock_statistic_em` / `stock_lhb_jgstatistic_em` 是累计算子，可从明细表聚合，不单独建表 |

---

## 二、公共设计（base.py）

### 2.1 ScxBaseModel — 基类

```python
import datetime
from peewee import Model, DateTimeField, CharField
from core.utils.db import db


class ScxBaseModel(Model):
    """所有 Model 的公共基类"""
    class Meta:
        database = db

    # 通用审计字段
    source = CharField(max_length=32, default="eastmoney")   # 数据来源
    fetched_at = DateTimeField(default=datetime.datetime.now) # 采集时间
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)
```

### 2.2 枚举定义

```python
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
```

---

## 三、K线行情 Model（kline.py）

### 3.1 StockKlineDaily — 日/周/月K线 ⭐ P0

**对应接口：** `ak.stock_zh_a_hist` (period=daily/weekly/monthly)

**AKShare 返回字段 → Model 字段映射：**

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 日期 | `trade_date` | DateField(index=True) | 交易日期 |
| 股票代码 | `symbol` | CharField(6, index=True) | 如 "000001" |
| 开盘 | `open` | DecimalField | 开盘价 |
| 收盘 | `close` | DecimalField | 收盘价 |
| 最高 | `high` | DecimalField | 最高价 |
| 最低 | `low` | DecimalField | 最低价 |
| 成交量 | `volume` | BigIntegerField | 成交量（手） |
| 成交额 | `amount` | DecimalField | 成交额（元） |
| 振幅 | `amplitude` | DecimalField | 振幅% |
| 涨跌幅 | `change_pct` | DecimalField | 涨跌幅% |
| 涨跌额 | `change_amt` | DecimalField | 涨跌额（元） |
| 换手率 | `turnover` | DecimalField | 换手率% |
| — | `period` | CharField(8, index=True) | "daily"/"weekly"/"monthly" |
| — | `adjust` | CharField(3, default="") | 复权: ""/"qfq"/"hfq" |

**表名：** `scx_stock_kline_daily`

**联合唯一索引：** `(symbol, trade_date, period, adjust)`

---

### 3.2 StockKlineMinute — 分钟K线 ⭐ P0

**对应接口：** `ak.stock_zh_a_hist_min_em`

> 分钟线与日线字段不同：没有 振幅/涨跌幅/涨跌额/换手率，但有 均价。所以必须独立 Model。

**AKShare 返回字段 → Model 字段映射：**

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 时间 | `trade_time` | DateTimeField(index=True) | 如 "2025-06-10 09:30:00" |
| — | `symbol` | CharField(6, index=True) | 股票代码（API入参，不在返回中） |
| 开盘 | `open` | DecimalField | 开盘价 |
| 收盘 | `close` | DecimalField | 收盘价 |
| 最高 | `high` | DecimalField | 最高价 |
| 最低 | `low` | DecimalField | 最低价 |
| 成交量 | `volume` | BigIntegerField | 成交量 |
| 成交额 | `amount` | DecimalField | 成交额 |
| 均价 | `avg_price` | DecimalField | 均价 |
| — | `period` | CharField(2, index=True) | "1"/"5"/"15"/"30"/"60" |
| — | `adjust` | CharField(3, default="") | 复权（1min时不支持） |

**表名：** `scx_stock_kline_minute`

**联合唯一索引：** `(symbol, trade_time, period)`

---

### 3.3 StockIntradayTick — 逐笔分时 P2

**对应接口：** `ak.stock_intraday_em`

**说明：** 当日逐笔分时数据，数据量极大（1只股票1天约2万条），仅近期使用时建表。

| 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|
| `symbol` | CharField(6, index=True) | 股票代码 |
| `trade_time` | DateTimeField(index=True) | 成交时间 |
| `price` | DecimalField | 成交价 |
| `volume` | BigIntegerField | 成交量 |
| `type` | CharField(4) | 买/卖/中 |

**表名：** `scx_stock_intraday_tick`

---

## 四、龙虎榜 Model（dragon_tiger.py）

### 4.1 LhbDetail — 龙虎榜详情 ⭐ P0

**对应接口：** `ak.stock_lhb_detail_em`

**AKShare 返回字段 → Model 字段映射：**

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 序号 | _(丢弃)_ | — | 顺序号，无业务意义 |
| 代码 | `symbol` | CharField(6, index=True) | 股票代码 |
| 名称 | `name` | CharField(32) | 股票名称 |
| 上榜日 | `list_date` | DateField(index=True) | 上榜日期 |
| 解读 | `interpretation` | CharField(128, default="") | 如 "主力做T，成功率51.18%" |
| 收盘价 | `close_price` | DecimalField | 当日收盘价 |
| 涨跌幅 | `change_pct` | DecimalField | 涨跌幅% |
| 龙虎榜净买额 | `lhb_net_buy` | DecimalField | 龙虎榜净买入额（元） |
| 龙虎榜买入额 | `lhb_buy_amt` | DecimalField | 龙虎榜买入额（元） |
| 龙虎榜卖出额 | `lhb_sell_amt` | DecimalField | 龙虎榜卖出额（元） |
| 龙虎榜成交额 | `lhb_total_amt` | DecimalField | 龙虎榜成交额（元） |
| 市场总成交额 | `market_total_amt` | DecimalField | 市场总成交额（元） |
| 净买额占总成交比 | `net_buy_ratio` | DecimalField | 净买额/总成交 % |
| 成交额占总成交比 | `total_amt_ratio` | DecimalField | 龙虎榜成交/总成交 % |
| 换手率 | `turnover` | DecimalField | 换手率% |
| 流通市值 | `float_market_cap` | DecimalField | 流通市值（元） |
| 上榜原因 | `reason` | CharField(256) | 如 "日涨幅偏离值达到7%的前5只证券" |
| 上榜后1日 | `return_1d` | DecimalField(null=True) | 上榜后1日涨跌幅% |
| 上榜后2日 | `return_2d` | DecimalField(null=True) | 上榜后2日涨跌幅% |
| 上榜后5日 | `return_5d` | DecimalField(null=True) | 上榜后5日涨跌幅% |
| 上榜后10日 | `return_10d` | DecimalField(null=True) | 上榜后10日涨跌幅% |

**表名：** `scx_lhb_detail`

**联合唯一索引：** `(symbol, list_date)`

---

### 4.2 LhbSeatDetail — 席位买卖明细 ⭐ P0

**对应接口：** `ak.stock_lhb_stock_detail_em`

> 龙虎榜子表：每只上榜股票的买卖方席位明细，通过 `(symbol, list_date)` 关联 LhbDetail。

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 序号 | _(丢弃)_ | — | 顺序号 |
| — | `symbol` | CharField(6, index=True) | 关联股票代码（API入参） |
| — | `list_date` | DateField(index=True) | 关联上榜日期（API入参） |
| 交易营业部名称 | `branch_name` | CharField(256) | 营业部名称 |
| 买入金额 | `buy_amt` | DecimalField(default=0) | 买入金额（元） |
| 买入金额-占总成交比例 | `buy_ratio` | DecimalField(default=0) | 买入占比% |
| 卖出金额 | `sell_amt` | DecimalField(default=0) | 卖出金额（元） |
| 卖出金额-占总成交比例 | `sell_ratio` | DecimalField(default=0) | 卖出占比% |
| 净额 | `net_amt` | DecimalField | 净额（元） |
| 类型 | `side` | CharField(8, index=True) | "买入" / "卖出" |

**表名：** `scx_lhb_seat_detail`

**联合唯一索引：** `(symbol, list_date, branch_name, side)`

---

### 4.3 LhbInstitutionDaily — 机构买卖每日统计 P1

**对应接口：** `ak.stock_lhb_jgmmtj_em`

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 序号 | _(丢弃)_ | — | |
| 代码 | `symbol` | CharField(6, index=True) | 股票代码 |
| 名称 | `name` | CharField(32) | 股票名称 |
| 收盘价 | `close_price` | DecimalField | 收盘价 |
| 涨跌幅 | `change_pct` | DecimalField | 涨跌幅% |
| 买方机构数 | `buy_inst_count` | IntegerField | 买方机构席位数 |
| 卖方机构数 | `sell_inst_count` | IntegerField | 卖方机构席位数 |
| 机构买入总额 | `inst_buy_total` | DecimalField | 机构买入总额（元） |
| 机构卖出总额 | `inst_sell_total` | DecimalField | 机构卖出总额（元） |
| 机构买入净额 | `inst_net_buy` | DecimalField | 机构净买入额（元） |
| 市场总成交额 | `market_total_amt` | DecimalField | 市场总成交额（元） |
| 机构净买额占总成交额比 | `inst_net_ratio` | DecimalField | 占比% |
| 换手率 | `turnover` | DecimalField | 换手率% |
| 流通市值 | `float_market_cap` | DecimalField | 流通市值（亿元） |
| 上榜原因 | `reason` | CharField(256) | 上榜原因 |
| 上榜日期 | `list_date` | DateField(index=True) | 上榜日期 |

**表名：** `scx_lhb_institution_daily`

**联合唯一索引：** `(symbol, list_date)`

---

### 4.4 LhbBranchActive — 每日活跃营业部 P1

**对应接口：** `ak.stock_lhb_hyyyb_em`

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 序号 | _(丢弃)_ | — | |
| 营业部名称 | `branch_name` | CharField(256, index=True) | 营业部名称 |
| 上榜日 | `list_date` | DateField(index=True) | 上榜日期 |
| 买入个股数 | `buy_stock_count` | IntegerField | 买入个股数 |
| 卖出个股数 | `sell_stock_count` | IntegerField | 卖出个股数 |
| 买入总金额 | `buy_total_amt` | DecimalField | 买入总金额（元） |
| 卖出总金额 | `sell_total_amt` | DecimalField | 卖出总金额（元） |
| 总买卖净额 | `net_amt` | DecimalField | 净额（元） |
| 买入股票 | `buy_stocks` | CharField(512, default="") | 买入的股票名称列表 |
| 营业部代码 | `branch_code` | CharField(16, index=True) | 营业部代码 |

**表名：** `scx_lhb_branch_active`

**联合唯一索引：** `(branch_code, list_date)`

---

### 4.5 LhbBranchStatistic — 营业部统计/排行 P2

**对应接口：** `ak.stock_lhb_traderstatistic_em` + `ak.stock_lhb_yybph_em`

> 两个接口都是营业部维度，用 `stat_type` 枚举区分。

| Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|
| `branch_name` | CharField(256, index=True) | 营业部名称 |
| `stat_type` | CharField(8, index=True) | "statistic" / "rank" |
| `stat_range` | CharField(8) | "近一月"/"近三月"/"近六月"/"近一年" |
| `total_amt` | DecimalField(null=True) | 龙虎榜成交金额 |
| `list_count` | IntegerField(null=True) | 上榜次数 |
| `buy_amt` | DecimalField(null=True) | 买入额 |
| `buy_count` | IntegerField(null=True) | 买入次数 |
| `sell_amt` | DecimalField(null=True) | 卖出额 |
| `sell_count` | IntegerField(null=True) | 卖出次数 |
| `rank_1d_buy_count` | IntegerField(null=True) | 上榜后1天买入次数（rank专有） |
| `rank_1d_avg_return` | DecimalField(null=True) | 上榜后1天平均涨幅（rank专有） |
| `rank_1d_up_prob` | DecimalField(null=True) | 上榜后1天上涨概率%（rank专有） |
| `rank_2d_buy_count` | IntegerField(null=True) | 上榜后2天买入次数 |
| `rank_2d_avg_return` | DecimalField(null=True) | 上榜后2天平均涨幅 |
| `rank_2d_up_prob` | DecimalField(null=True) | 上榜后2天上涨概率% |
| `rank_3d_buy_count` | IntegerField(null=True) | 上榜后3天 |
| `rank_3d_avg_return` | DecimalField(null=True) | |
| `rank_3d_up_prob` | DecimalField(null=True) | |
| `rank_5d_buy_count` | IntegerField(null=True) | 上榜后5天 |
| `rank_5d_avg_return` | DecimalField(null=True) | |
| `rank_5d_up_prob` | DecimalField(null=True) | |
| `rank_10d_buy_count` | IntegerField(null=True) | 上榜后10天 |
| `rank_10d_avg_return` | DecimalField(null=True) | |
| `rank_10d_up_prob` | DecimalField(null=True) | |

**表名：** `scx_lhb_branch_statistic`

**联合唯一索引：** `(branch_name, stat_type, stat_range)`

---

## 五、资金流向 Model（capital_flow.py）

### 5.1 CapitalFlowStock — 个股资金流 ⭐ P0

**对应接口：** `ak.stock_individual_fund_flow`

**AKShare 返回字段 → Model 字段映射：**

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 日期 | `trade_date` | DateField(index=True) | 交易日期 |
| — | `symbol` | CharField(6, index=True) | 股票代码（API入参） |
| — | `market` | CharField(2) | "sh"/"sz"/"bj"（API入参） |
| 主力净流入-净额 | `main_net_amt` | DecimalField | 主力净流入额（元） |
| 小单净流入-净额 | `small_net_amt` | DecimalField | 小单净流入额 |
| 中单净流入-净额 | `mid_net_amt` | DecimalField | 中单净流入额 |
| 大单净流入-净额 | `big_net_amt` | DecimalField | 大单净流入额 |
| 超大单净流入-净额 | `huge_net_amt` | DecimalField | 超大单净流入额 |
| 主力净流入-净占比 | `main_net_pct` | DecimalField | 主力净占比% |
| 小单净流入-净占比 | `small_net_pct` | DecimalField | 小单净占比% |
| 中单净流入-净占比 | `mid_net_pct` | DecimalField | 中单净占比% |
| 大单净流入-净占比 | `big_net_pct` | DecimalField | 大单净占比% |
| 超大单净流入-净占比 | `huge_net_pct` | DecimalField | 超大单净占比% |
| 收盘价 | `close_price` | DecimalField | 收盘价 |
| 涨跌幅 | `change_pct` | DecimalField | 涨跌幅% |

**表名：** `scx_capital_flow_stock`

**联合唯一索引：** `(symbol, trade_date)`

---

### 5.2 CapitalFlowMarket — 大盘资金流 ⭐ P0

**对应接口：** `ak.stock_market_fund_flow`

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 日期 | `trade_date` | DateField(index=True) | 交易日期 |
| 主力净流入-净额 | `main_net_amt` | DecimalField | 主力净流入额 |
| 小单净流入-净额 | `small_net_amt` | DecimalField | |
| 中单净流入-净额 | `mid_net_amt` | DecimalField | |
| 大单净流入-净额 | `big_net_amt` | DecimalField | |
| 超大单净流入-净额 | `huge_net_amt` | DecimalField | |
| 主力净流入-净占比 | `main_net_pct` | DecimalField | |
| 小单净流入-净占比 | `small_net_pct` | DecimalField | |
| 中单净流入-净占比 | `mid_net_pct` | DecimalField | |
| 大单净流入-净占比 | `big_net_pct` | DecimalField | |
| 超大单净流入-净占比 | `huge_net_pct` | DecimalField | |
| 上证-收盘价 | `sh_close` | DecimalField | 上证收盘 |
| 上证-涨跌幅 | `sh_change_pct` | DecimalField | 上证涨跌幅% |
| 深证-收盘价 | `sz_close` | DecimalField | 深证收盘 |
| 深证-涨跌幅 | `sz_change_pct` | DecimalField | 深证涨跌幅% |

**表名：** `scx_capital_flow_market`

**联合唯一索引：** `(trade_date)`

---

### 5.3 CapitalFlowMainRank — 主力净流入排名 P1

**对应接口：** `ak.stock_main_fund_flow` + `ak.stock_individual_fund_flow_rank`

> `stock_main_fund_flow` 返回今日/5日/10日排行，`stock_individual_fund_flow_rank` 返回今日/3日/5日/10日排行。结构相似，用 `indicator` 区分。

| Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|
| `symbol` | CharField(6, index=True) | 股票代码 |
| `name` | CharField(32) | 股票名称 |
| `indicator` | CharField(8, index=True) | "今日"/"3日"/"5日"/"10日" |
| `latest_price` | DecimalField | 最新价 |
| `change_pct` | DecimalField(null=True) | 涨跌幅% |
| `main_net_pct` | DecimalField | 主力净占比% |
| `main_rank` | IntegerField(null=True) | 主力排名 |
| `huge_net_amt` | DecimalField(null=True) | 超大单净流入额 |
| `huge_net_pct` | DecimalField(null=True) | 超大单净占比% |
| `big_net_amt` | DecimalField(null=True) | 大单净流入额 |
| `big_net_pct` | DecimalField(null=True) | 大单净占比% |
| `mid_net_amt` | DecimalField(null=True) | 中单净流入额 |
| `mid_net_pct` | DecimalField(null=True) | 中单净占比% |
| `small_net_amt` | DecimalField(null=True) | 小单净流入额 |
| `small_net_pct` | DecimalField(null=True) | 小单净占比% |
| `sector` | CharField(32, null=True) | 所属板块（main_flow专有） |
| `trade_date` | DateField(index=True) | 采集日期 |

**表名：** `scx_capital_flow_main_rank`

**联合唯一索引：** `(symbol, indicator, trade_date)`

---

### 5.4 CapitalFlowSector — 板块资金流 P1

**对应接口：** `ak.stock_sector_fund_flow_rank` + `ak.stock_sector_fund_flow_summary` + `ak.stock_sector_fund_flow_hist` + `ak.stock_concept_fund_flow_hist`

> 4个接口字段结构高度相似，用 `sector_type` + `data_type` 区分。

| Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|
| `sector_name` | CharField(64, index=True) | 板块名称（如 "汽车服务"） |
| `sector_type` | CharField(8, index=True) | "行业"/"概念"/"地域" |
| `data_type` | CharField(8, index=True) | "rank"/"summary"/"hist" |
| `indicator` | CharField(8) | "今日"/"5日"/"10日"（rank/summary用） |
| `trade_date` | DateField(index=True) | 交易日期（hist用） |
| `change_pct` | DecimalField(null=True) | 涨跌幅% |
| `main_net_amt` | DecimalField | 主力净流入额 |
| `main_net_pct` | DecimalField | 主力净占比% |
| `huge_net_amt` | DecimalField(null=True) | 超大单净流入额 |
| `huge_net_pct` | DecimalField(null=True) | 超大单净占比% |
| `big_net_amt` | DecimalField(null=True) | 大单净流入额 |
| `big_net_pct` | DecimalField(null=True) | 大单净占比% |
| `mid_net_amt` | DecimalField(null=True) | 中单净流入额 |
| `mid_net_pct` | DecimalField(null=True) | 中单净占比% |
| `small_net_amt` | DecimalField(null=True) | 小单净流入额 |
| `small_net_pct` | DecimalField(null=True) | 小单净占比% |
| `top_stock` | CharField(32, null=True) | 主力净流入最大股（rank专有） |
| `top_stock_code` | CharField(6, null=True) | 最大股代码（rank专有） |
| `is_net_inflow` | BooleanField(null=True) | 是否净流入（rank专有） |
| `latest_price` | DecimalField(null=True) | 最新价（summary用） |

**表名：** `scx_capital_flow_sector`

**联合唯一索引：** `(sector_name, sector_type, data_type, indicator, trade_date)`

---

### 5.5 CapitalFlowHsgt — 沪深港通资金流向 P1

**对应接口：** `ak.stock_hsgt_fund_flow_summary_em`

| AKShare 中文列名 | Model 字段 | Peewee 类型 | 说明 |
|:---|:---|:---|:---|
| 交易日 | `trade_date` | DateField(index=True) | 交易日期 |
| 类型 | `mutual_type` | CharField(16) | 如 "沪股通"/"深股通" |
| 板块 | `board_type` | CharField(16) | 板块 |
| 资金方向 | `direction` | CharField(8) | 流入/流出 |
| 相关指数 | `index_name` | CharField(32) | 对应指数 |
| 交易状态 | `status` | CharField(16) | 交易状态 |
| 资金净流入 | `net_inflow` | DecimalField | 资金净流入额（元） |
| 当日资金余额 | `daily_balance` | DecimalField | 当日余额（元） |
| 上涨数 | `up_count` | IntegerField(null=True) | 上涨家数 |
| 下跌数 | `down_count` | IntegerField(null=True) | 下跌家数 |
| 持平数 | `flat_count` | IntegerField(null=True) | 持平家数 |
| 指数涨跌幅 | `index_change_pct` | DecimalField(null=True) | 指数涨跌幅% |
| 成交净买额 | `net_buy_amt` | DecimalField(null=True) | 成交净买额（元） |

**表名：** `scx_capital_flow_hsgt`

**联合唯一索引：** `(trade_date, mutual_type)`

---

## 六、配置说明

### 6.1 .env 新增配置项

```ini
# 东方财富 Cookie
AKSHARE_EM_COOKIE=fullscreengg=1; ...

# AKShare 请求间隔（秒）
AKSHARE_REQUEST_INTERVAL=0.5

# 远程数据服务地址
REMOTE_SERVER_URL=http://138.201.173.21:8900

# 远程服务 Bearer Token
REMOTE_SERVER_TOKEN=2026shijian
```

### 6.2 config.py 新增

```python
# AKShare 东方财富
akshare_em_cookie: str = ""
akshare_request_interval: float = 0.5

# 远程服务器鉴权
remote_server_url: str = "http://localhost:8900"
remote_server_token: str = ""
```

### 6.3 Cookie 使用方式

AKShare 底层使用 `requests`，通过环境变量或配置注入 Cookie：

```python
import os
import akshare as ak
from core.config import settings

# 方案：通过 requests session 注入 Cookie
# akshare 部分接口支持通过修改 requests 默认 headers 传递 cookie
import requests
session = requests.Session()
session.headers.update({"Cookie": settings.akshare_em_cookie})
```

---

## 七、文件结构

```
core/models/
├── __init__.py              # 导出所有 Model
├── base.py                  # ScxBaseModel + 枚举定义
├── kline.py                 # StockKlineDaily, StockKlineMinute, StockIntradayTick
├── dragon_tiger.py          # LhbDetail, LhbSeatDetail, LhbInstitutionDaily,
│                            # LhbBranchActive, LhbBranchStatistic
├── capital_flow.py          # CapitalFlowStock, CapitalFlowMarket, CapitalFlowMainRank,
│                            # CapitalFlowSector, CapitalFlowHsgt
└── article.py               # (已有)
```

---

## 八、实施顺序

| 步骤 | 内容 | Model |
|------|------|-------|
| 1 | 创建 `base.py` | ScxBaseModel + 枚举 |
| 2 | 创建 `kline.py` | StockKlineDaily → StockKlineMinute |
| 3 | 创建 `dragon_tiger.py` | LhbDetail → LhbSeatDetail → LhbInstitutionDaily |
| 4 | 创建 `capital_flow.py` | CapitalFlowStock → CapitalFlowMarket → CapitalFlowSector |
| 5 | 更新 `__init__.py` | 统一导出 |
| 6 | 建表验证 | `python -c "from core.models import *; db.create_tables()"` |
| 7 | 对接远程服务器写入 | 配合 `REMOTE_SERVER_URL` + `REMOTE_SERVER_TOKEN` |
