# 结构化数据 - 交易信息爬取 AKShare API 清单

> 数据源：东方财富（EastMoney）
> AKShare 版本：v1.18.64+
> Python 要求：≥ 3.9（64-bit）
> 文档地址：https://akshare.akfamily.xyz/data/stock/stock.html

---

## 目录

- [一、K线行情（日线 / 周线 / 月线）](#一k线行情日线--周线--月线)
- [二、分钟线行情](#二分钟线行情)
- [三、龙虎榜数据](#三龙虎榜数据)
- [四、资金流入流出](#四资金流入流出)
- [五、接口速查总表](#五接口速查总表)
- [六、对接注意事项](#六对接注意事项)

---

## 一、K线行情（日线 / 周线 / 月线）

### 1.1 `ak.stock_zh_a_hist` — A股历史行情

**接口说明：** 东方财富网-行情首页-沪深京 A 股-每日行情

**函数签名：**

```python
ak.stock_zh_a_hist(
    symbol: str = '000001',       # 股票代码，6位数字，如 "000001"
    period: str = 'daily',        # 周期：'daily' | 'weekly' | 'monthly'
    start_date: str = '19700101', # 开始日期，格式 "YYYYMMDD"
    end_date: str = '20500101',   # 结束日期，格式 "YYYYMMDD"
    adjust: str = '',             # 复权类型：'' 不复权 | 'qfq' 前复权 | 'hfq' 后复权
    timeout: float = None         # 请求超时
) -> pandas.DataFrame
```

**调用示例：**

```python
import akshare as ak

# 日线（前复权）
df_daily = ak.stock_zh_a_hist(
    symbol="000001",
    period="daily",
    start_date="20250101",
    end_date="20250610",
    adjust="qfq"
)

# 周线
df_weekly = ak.stock_zh_a_hist(
    symbol="000001",
    period="weekly",
    start_date="20250101",
    end_date="20250610",
    adjust="qfq"
)

# 月线
df_monthly = ak.stock_zh_a_hist(
    symbol="000001",
    period="monthly",
    start_date="20240101",
    end_date="20250610",
    adjust="qfq"
)
```

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 日期 | str | 交易日期，如 "2025-06-05" |
| 股票代码 | str | 6位股票代码，如 "000001" |
| 开盘 | float | 开盘价 |
| 收盘 | float | 收盘价 |
| 最高 | float | 最高价 |
| 最低 | float | 最低价 |
| 成交量 | int | 成交量（手） |
| 成交额 | float | 成交额（元） |
| 振幅 | float | 振幅百分比 |
| 涨跌幅 | float | 涨跌幅百分比 |
| 涨跌额 | float | 涨跌额 |
| 换手率 | float | 换手率百分比 |

**返回示例：**

```
          日期    股票代码    开盘    收盘    最高    最低     成交量          成交额   振幅   涨跌幅   涨跌额  换手率
0  2025-06-03  000001  10.94  11.21  11.31  10.93  2192480  2.581e+09  3.47   2.28   0.25   1.13
1  2025-06-04  000001  11.22  11.24  11.28  11.18  1167960  1.383e+09  0.89   0.27   0.03   0.60
2  2025-06-05  000001  11.28  11.07  11.31  11.06  1166803  1.369e+09  2.22  -1.51  -0.17   0.60
```

---

## 二、分钟线行情

### 2.1 `ak.stock_zh_a_hist_min_em` — A股分时行情（分钟K线）

**接口说明：** 东方财富网-行情首页-沪深京 A 股-每日分时行情

**函数签名：**

```python
ak.stock_zh_a_hist_min_em(
    symbol: str = '000001',                        # 股票代码，如 "000001"
    start_date: str = '1979-09-01 09:32:00',       # 开始时间，格式 "YYYY-MM-DD HH:MM:SS"
    end_date: str = '2222-01-01 09:32:00',         # 结束时间，格式 "YYYY-MM-DD HH:MM:SS"
    period: str = '5',                             # 周期：'1' | '5' | '15' | '30' | '60' 分钟
    adjust: str = ''                               # 复权：'' | 'qfq' | 'hfq'（⚠️ 1分钟时不支持复权）
) -> pandas.DataFrame
```

**调用示例：**

```python
# 5分钟线
df_5min = ak.stock_zh_a_hist_min_em(
    symbol="000001",
    period="5",
    start_date="2025-06-10 09:30:00",
    end_date="2025-06-10 15:00:00",
    adjust=""
)

# 1分钟线（⚠️ 仅近5个交易日，不支持复权）
df_1min = ak.stock_zh_a_hist_min_em(
    symbol="000001",
    period="1",
    start_date="2025-06-05 09:30:00",
    end_date="2025-06-05 15:00:00",
    adjust=""
)
```

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 时间 | str | 时间戳，如 "2025-06-10 09:30:00" |
| 开盘 | float | 开盘价 |
| 收盘 | float | 收盘价 |
| 最高 | float | 最高价 |
| 最低 | float | 最低价 |
| 成交量 | int | 成交量 |
| 成交额 | float | 成交额 |
| 均价 | float | 均价 |

**⚠️ 限制说明：**

- `period="1"` 时：仅返回**近5个交易日**数据，不支持复权
- `period="5"/"15"/"30"/"60"`：支持较长时间范围查询，支持复权

---

### 2.2 `ak.stock_intraday_em` — 当日逐笔分时数据

**接口说明：** 东方财富-分时数据，返回最近一个交易日逐笔分时（含盘前数据）

**函数签名：**

```python
ak.stock_intraday_em(
    symbol: str = '000001'    # 股票代码，如 "000001"
) -> pandas.DataFrame
```

**调用示例：**

```python
df_intraday = ak.stock_intraday_em(symbol="000001")
```

---

### 2.3 `ak.stock_zh_a_hist_pre_min_em` — 盘前分钟数据

**接口说明：** 东方财富网-沪深京 A 股-每日分时行情（含盘前数据）

**函数签名：**

```python
ak.stock_zh_a_hist_pre_min_em(
    symbol: str = '000001',       # 股票代码，如 "000001"
    start_time: str = '09:00:00', # 开始时间，格式 "HH:MM:SS"
    end_time: str = '15:50:00'    # 结束时间，格式 "HH:MM:SS"
) -> pandas.DataFrame
```

**调用示例：**

```python
df_pre = ak.stock_zh_a_hist_pre_min_em(
    symbol="000001",
    start_time="09:00:00",
    end_time="15:40:00"
)
```

---

## 三、龙虎榜数据

### 3.1 `ak.stock_lhb_detail_em` — 龙虎榜详情 ⭐

**接口说明：** 东方财富网-数据中心-龙虎榜单-龙虎榜详情

**函数签名：**

```python
ak.stock_lhb_detail_em(
    start_date: str = '20230403',  # 开始日期，格式 "YYYYMMDD"
    end_date: str = '20230417'      # 结束日期，格式 "YYYYMMDD"
) -> pandas.DataFrame
```

**调用示例：**

```python
df_lhb = ak.stock_lhb_detail_em(start_date="20250601", end_date="20250610")
```

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 序号 | int | 序号 |
| 代码 | str | 股票代码 |
| 名称 | str | 股票名称 |
| 上榜日 | str | 上榜日期，如 "2025-06-05" |
| 解读 | str | 龙虎榜解读，如 "主力做T，成功率51.18%" |
| 收盘价 | float | 收盘价 |
| 涨跌幅 | float | 涨跌幅百分比 |
| 龙虎榜净买额 | float | 龙虎榜净买入金额（元） |
| 龙虎榜买入额 | float | 龙虎榜买入金额（元） |
| 龙虎榜卖出额 | float | 龙虎榜卖出金额（元） |
| 龙虎榜成交额 | float | 龙虎榜成交金额（元） |
| 市场总成交额 | float | 市场总成交额（元） |
| 净买额占总成交比 | float | 净买额占总成交比百分比 |
| 成交额占总成交比 | float | 成交额占总成交比百分比 |
| 换手率 | float | 换手率百分比 |
| 流通市值 | float | 流通市值（元） |
| 上榜原因 | str | 如 "日跌幅偏离值达到7%的前5只证券" |
| 上榜后1日 | float | 上榜后1日涨跌幅 |
| 上榜后2日 | float | 上榜后2日涨跌幅 |
| 上榜后5日 | float | 上榜后5日涨跌幅 |
| 上榜后10日 | float | 上榜后10日涨跌幅 |

---

### 3.2 `ak.stock_lhb_stock_statistic_em` — 个股上榜统计 ⭐

**接口说明：** 东方财富网-数据中心-龙虎榜单-个股上榜统计

**函数签名：**

```python
ak.stock_lhb_stock_statistic_em(
    symbol: str = '近一月'    # 时间范围：'近一月' | '近三月' | '近六月' | '近一年'
) -> pandas.DataFrame
```

**调用示例：**

```python
df_stat = ak.stock_lhb_stock_statistic_em(symbol="近一月")
```

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 序号 | int | 序号 |
| 代码 | str | 股票代码 |
| 名称 | str | 股票名称 |
| 最近上榜日 | str | 最近上榜日期 |
| 收盘价 | float | 当前收盘价 |
| 涨跌幅 | float | 当前涨跌幅 |
| 上榜次数 | int | 时间范围内上榜次数 |
| 龙虎榜净买额 | float | 累计净买额（元） |
| 龙虎榜买入额 | float | 累计买入额（元） |
| 龙虎榜卖出额 | float | 累计卖出额（元） |
| 龙虎榜总成交额 | float | 累计成交额（元） |
| 买方机构次数 | int | 买方机构上榜次数 |
| 卖方机构次数 | int | 卖方机构上榜次数 |
| 机构买入净额 | float | 机构买入净额（元） |
| 机构买入总额 | float | 机构买入总额（元） |
| 机构卖出总额 | float | 机构卖出总额（元） |
| 近1个月涨跌幅 | float | 近1月涨跌幅 |
| 近3个月涨跌幅 | float | 近3月涨跌幅 |
| 近6个月涨跌幅 | float | 近6月涨跌幅 |
| 近1年涨跌幅 | float | 近1年涨跌幅 |

---

### 3.3 `ak.stock_lhb_jgmmtj_em` — 机构买卖每日统计 ⭐

**接口说明：** 东方财富网-数据中心-龙虎榜单-机构买卖每日统计

**函数签名：**

```python
ak.stock_lhb_jgmmtj_em(
    start_date: str = '20240417',  # 开始日期，格式 "YYYYMMDD"
    end_date: str = '20240430'     # 结束日期，格式 "YYYYMMDD"
) -> pandas.DataFrame
```

**调用示例：**

```python
df_jg = ak.stock_lhb_jgmmtj_em(start_date="20250501", end_date="20250610")
```

**返回字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| 序号 | int | 序号 |
| 代码 | str | 股票代码 |
| 名称 | str | 股票名称 |
| 收盘价 | float | 收盘价 |
| 涨跌幅 | float | 涨跌幅百分比 |
| 买方机构数 | int | 买方机构席位数 |
| 卖方机构数 | int | 卖方机构席位数 |
| 机构买入总额 | float | 机构买入总额（元） |
| 机构卖出总额 | float | 机构卖出总额（元） |
| 机构买入净额 | float | 机构净买入额（元） |
| 市场总成交额 | float | 市场总成交额（元） |
| 机构净买额占总成交额比 | float | 占比百分比 |
| 换手率 | float | 换手率百分比 |
| 流通市值 | float | 流通市值（元） |
| 上榜原因 | str | 上榜原因说明 |
| 上榜日期 | str | 上榜日期，如 "2025-05-20" |

---

### 3.4 `ak.stock_lhb_hyyyb_em` — 每日活跃营业部

**接口说明：** 东方财富网-数据中心-龙虎榜单-每日活跃营业部

**函数签名：**

```python
ak.stock_lhb_hyyyb_em(
    start_date: str = '20220324',  # 开始日期，格式 "YYYYMMDD"
    end_date: str = '20220324'     # 结束日期，格式 "YYYYMMDD"
) -> pandas.DataFrame
```

---

### 3.5 `ak.stock_lhb_jgstatistic_em` — 机构席位追踪

**接口说明：** 东方财富网-数据中心-龙虎榜单-机构席位追踪

**函数签名：**

```python
ak.stock_lhb_jgstatistic_em(
    symbol: str = '近一月'    # 时间范围：'近一月' | '近三月' | '近六月' | '近一年'
) -> pandas.DataFrame
```

---

### 3.6 `ak.stock_lhb_stock_detail_em` — 个股龙虎榜详情（买卖方明细）

**接口说明：** 东方财富网-数据中心-龙虎榜单-个股龙虎榜详情

**函数签名：**

```python
ak.stock_lhb_stock_detail_em(
    symbol: str = '000788',     # 股票代码，如 "000788"
    date: str = '20220315',     # 上榜日期，格式 "YYYYMMDD"
    flag: str = '卖出'          # 方向：'买入' | '卖出'
) -> pandas.DataFrame
```

---

### 3.7 `ak.stock_lhb_stock_detail_date_em` — 个股龙虎榜日期列表

**接口说明：** 东方财富网-数据中心-龙虎榜单-个股龙虎榜详情-日期

**函数签名：**

```python
ak.stock_lhb_stock_detail_date_em(
    symbol: str = '600077'     # 股票代码，如 "600077"
) -> pandas.DataFrame
```

---

### 3.8 `ak.stock_lhb_yybph_em` — 营业部排行

**接口说明：** 东方财富网-数据中心-龙虎榜单-营业部排行

**函数签名：**

```python
ak.stock_lhb_yybph_em(
    symbol: str = '近一月'    # 时间范围：'近一月' | '近三月' | '近六月' | '近一年'
) -> pandas.DataFrame
```

---

### 3.9 `ak.stock_lhb_traderstatistic_em` — 营业部统计

**接口说明：** 东方财富网-数据中心-龙虎榜单-营业部统计

**函数签名：**

```python
ak.stock_lhb_traderstatistic_em(
    symbol: str = '近一月'    # 时间范围：'近一月' | '近三月' | '近六月' | '近一年'
) -> pandas.DataFrame
```

---

### 3.10 `ak.stock_lhb_yyb_detail_em` — 营业部历史交易明细

**接口说明：** 东方财富网-数据中心-龙虎榜单-营业部历史交易明细

**函数签名：**

```python
ak.stock_lhb_yyb_detail_em(
    symbol: str = '10188715'   # 营业部代码
) -> pandas.DataFrame
```

---

### 3.11 `ak.option_lhb_em` — 期权龙虎榜

**接口说明：** 东方财富网-数据中心-期货期权-期权龙虎榜单

**函数签名：**

```python
ak.option_lhb_em(
    symbol: str = '510050',                           # 期权标的代码
    indicator: str = '期权交易情况-认沽交易量',         # 指标类型
    trade_date: str = '20220121'                      # 交易日期，格式 "YYYYMMDD"
) -> pandas.DataFrame
```

---

## 四、资金流入流出

### 4.1 `ak.stock_individual_fund_flow` — 个股资金流 ⭐

**接口说明：** 东方财富网-数据中心-资金流向-个股

**函数签名：**

```python
ak.stock_individual_fund_flow(
    stock: str = '600094',     # 股票代码，如 "000001"
    market: str = 'sh'         # 市场：'sh' 上海 | 'sz' 深圳 | 'bj' 北京
) -> pandas.DataFrame
```

**调用示例：**

```python
# 平安银行个股资金流
df = ak.stock_individual_fund_flow(stock="000001", market="sz")
```

---

### 4.2 `ak.stock_market_fund_flow` — 大盘资金流 ⭐

**接口说明：** 东方财富网-数据中心-资金流向-大盘

**函数签名：**

```python
ak.stock_market_fund_flow() -> pandas.DataFrame
```

**调用示例：**

```python
df = ak.stock_market_fund_flow()
```

---

### 4.3 `ak.stock_main_fund_flow` — 主力净流入排名 ⭐

**接口说明：** 东方财富网-数据中心-资金流向-主力净流入排名

**函数签名：**

```python
ak.stock_main_fund_flow(
    symbol: str = '全部股票'    # 市场范围
) -> pandas.DataFrame
```

**symbol 可选值：**

| 值 | 说明 |
|-----|------|
| `"全部股票"` | 全市场 |
| `"沪深A股"` | 沪深A股 |
| `"沪市A股"` | 上海A股 |
| `"科创板"` | 科创板 |
| `"深市A股"` | 深圳A股 |
| `"创业板"` | 创业板 |
| `"沪市B股"` | 上海B股 |
| `"深市B股"` | 深圳B股 |

**调用示例：**

```python
df = ak.stock_main_fund_flow(symbol="全部股票")
```

---

### 4.4 `ak.stock_individual_fund_flow_rank` — 资金流向排名

**接口说明：** 东方财富网-数据中心-资金流向-排名

**函数签名：**

```python
ak.stock_individual_fund_flow_rank(
    indicator: str = '5日'     # 时间范围：'今日' | '3日' | '5日' | '10日'
) -> pandas.DataFrame
```

**调用示例：**

```python
df = ak.stock_individual_fund_flow_rank(indicator="今日")
```

---

### 4.5 `ak.stock_sector_fund_flow_rank` — 板块资金流排名

**接口说明：** 东方财富网-数据中心-资金流向-板块资金流-排名

**函数签名：**

```python
ak.stock_sector_fund_flow_rank(
    indicator: str = '今日',           # 时间范围：'今日' | '5日' | '10日'
    sector_type: str = '行业资金流'     # 板块类型：'行业资金流' | '概念资金流' | '地域资金流'
) -> pandas.DataFrame
```

**调用示例：**

```python
# 行业资金流
df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")

# 概念资金流
df = ak.stock_sector_fund_flow_rank(indicator="5日", sector_type="概念资金流")
```

---

### 4.6 `ak.stock_sector_fund_flow_summary` — 行业个股资金流

**接口说明：** 东方财富网-数据中心-资金流向-行业资金流-行业个股资金流

**函数签名：**

```python
ak.stock_sector_fund_flow_summary(
    symbol: str = '电源设备',     # 行业名称
    indicator: str = '今日'       # 时间范围：'今日' | '5日' | '10日'
) -> pandas.DataFrame
```

**调用示例：**

```python
df = ak.stock_sector_fund_flow_summary(symbol="汽车服务", indicator="今日")
```

---

### 4.7 `ak.stock_sector_fund_flow_hist` — 行业历史资金流

**接口说明：** 东方财富网-数据中心-资金流向-行业资金流-行业历史资金流

**函数签名：**

```python
ak.stock_sector_fund_flow_hist(
    symbol: str = '汽车服务'     # 行业名称
) -> pandas.DataFrame
```

---

### 4.8 `ak.stock_concept_fund_flow_hist` — 概念历史资金流

**接口说明：** 东方财富网-数据中心-资金流向-概念资金流-概念历史资金流

**函数签名：**

```python
ak.stock_concept_fund_flow_hist(
    symbol: str = '数据要素'     # 概念名称
) -> pandas.DataFrame
```

---

### 4.9 `ak.stock_hsgt_fund_flow_summary_em` — 沪深港通资金流向（北向资金）

**接口说明：** 东方财富网-数据中心-资金流向-沪深港通资金流向

**函数签名：**

```python
ak.stock_hsgt_fund_flow_summary_em() -> pandas.DataFrame
```

**调用示例：**

```python
df = ak.stock_hsgt_fund_flow_summary_em()
```

---

## 五、接口速查总表

### K线行情

| 接口函数 | 周期 | 关键参数 | 核心用途 |
|---------|------|---------|---------|
| `stock_zh_a_hist` | daily / weekly / monthly | symbol, period, adjust | ✅ 日/周/月K线，主力接口 |
| `stock_zh_a_hist_min_em` | 1 / 5 / 15 / 30 / 60 min | symbol, period, start_date, end_date | ✅ 分钟K线，主力接口 |
| `stock_intraday_em` | 逐笔分时 | symbol | 当日逐笔分时数据 |
| `stock_zh_a_hist_pre_min_em` | 含盘前分钟 | symbol, start_time, end_time | 含盘前数据的分钟线 |

### 龙虎榜

| 接口函数 | 关键参数 | 核心用途 |
|---------|---------|---------|
| `stock_lhb_detail_em` | start_date, end_date | ✅ 龙虎榜详情（按日期查） |
| `stock_lhb_stock_statistic_em` | symbol（时间范围） | ✅ 个股上榜统计 |
| `stock_lhb_jgmmtj_em` | start_date, end_date | ✅ 机构买卖每日统计 |
| `stock_lhb_stock_detail_em` | symbol, date, flag | 个股买卖方明细 |
| `stock_lhb_stock_detail_date_em` | symbol | 个股上榜日期列表 |
| `stock_lhb_hyyyb_em` | start_date, end_date | 每日活跃营业部 |
| `stock_lhb_jgstatistic_em` | symbol（时间范围） | 机构席位追踪 |
| `stock_lhb_yybph_em` | symbol（时间范围） | 营业部排行 |
| `stock_lhb_traderstatistic_em` | symbol（时间范围） | 营业部统计 |
| `stock_lhb_yyb_detail_em` | symbol（营业部代码） | 营业部历史交易明细 |
| `option_lhb_em` | symbol, indicator, trade_date | 期权龙虎榜 |

### 资金流入流出

| 接口函数 | 关键参数 | 核心用途 |
|---------|---------|---------|
| `stock_individual_fund_flow` | stock, market | ✅ 个股资金流（历史序列） |
| `stock_market_fund_flow` | 无 | ✅ 大盘资金流 |
| `stock_main_fund_flow` | symbol（市场范围） | ✅ 主力净流入排名 |
| `stock_individual_fund_flow_rank` | indicator | 资金流向排名 |
| `stock_sector_fund_flow_rank` | indicator, sector_type | 板块资金流排名 |
| `stock_sector_fund_flow_summary` | symbol, indicator | 行业内个股资金流 |
| `stock_sector_fund_flow_hist` | symbol（行业名） | 行业历史资金流 |
| `stock_concept_fund_flow_hist` | symbol（概念名） | 概念历史资金流 |
| `stock_hsgt_fund_flow_summary_em` | 无 | 沪深港通/北向资金 |

---

## 六、对接注意事项

### 6.1 频率限制

| 数据源 | 限制 | 建议 |
|--------|------|------|
| 东方财富 | 单IP高频请求可能触发反爬 | 单次请求间隔 ≥ 0.5s，批量采集加 `time.sleep()` |
| 分钟线 | 1分钟数据仅近5个交易日 | 需要长期1分钟数据请每日定时采集落库 |

### 6.2 数据落库策略

```python
import time
import akshare as ak

def crawl_all_stocks(stock_list: list[str]):
    """批量采集K线数据示例"""
    for symbol in stock_list:
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                adjust="qfq"
            )
            # TODO: 写入数据库
            print(f"✅ {symbol} 采集成功，{len(df)} 条")
        except Exception as e:
            print(f"❌ {symbol} 采集失败: {e}")
        time.sleep(0.5)  # 限频保护
```

### 6.3 复权选择建议

| 场景 | 推荐 adjust 值 | 原因 |
|------|---------------|------|
| 技术分析（画K线图） | `"qfq"` 前复权 | 价格连续，适合看趋势 |
| 回测策略 | `"qfq"` 前复权 | 避免除权缺口干扰信号 |
| 查看真实成交价 | `""` 不复权 | 反映当日实际价格 |
| 分红分析 | `"hfq"` 后复权 | 可追溯累计收益 |

### 6.4 字段单位说明

| 字段 | 单位 | 备注 |
|------|------|------|
| 成交量 | 手 | 1手 = 100股 |
| 成交额 | 元 | 需注意精度，建议数据库用 DECIMAL |
| 流通市值 | 元 | 数值很大，建议存储时除以 1e8 换算为"亿元" |
| 龙虎榜净买额等金额字段 | 元 | 同上 |
| 涨跌幅 / 换手率 / 振幅 | 百分比 | 如 2.28 表示 2.28% |
