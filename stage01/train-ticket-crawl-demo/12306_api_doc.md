# 12306 余票查询接口文档

## 接口信息

- **URL**: `https://kyfw.12306.cn/otn/leftTicket/queryG`
- **方法**: GET
- **说明**: 查询指定日期、出发站、到达站的余票信息

---

## 请求参数

| 参数名 | 类型 | 示例值 | 说明 |
|--------|------|--------|------|
| leftTicketDTO.train_date | string | 2026-06-10 | 出发日期 |
| leftTicketDTO.from_station | string | BJP | 出发站代码 |
| leftTicketDTO.to_station | string | SHH | 到达站代码 |
| purpose_codes | string | ADULT | 旅客类型，成人固定传 ADULT |

---

## 响应结构

```json
{
  "httpstatus": 200,
  "data": {
    "result": ["...车次字符串列表..."],
    "flag": "1",
    "level": "0",
    "sametlc": "Y",
    "map": {
      "VNP": "北京南",
      "AOH": "上海虹桥"
    }
  },
  "messages": "",
  "status": true
}
```

### 顶层字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| httpstatus | int | HTTP状态码，200为成功 |
| data.result | list | 车次原始字符串列表，每条一趟车 |
| data.map | dict | 站代码与中文站名映射表 |
| status | bool | 接口是否成功 |

---

## result 字段解析（用 `|` 分隔）

每条 result 字符串按 `|` 分割后，各字段含义如下：

| 索引 | 字段名 | 示例值 | 说明 |
|------|--------|--------|------|
| 0 | booking_token | `Aoq8q...roQw%3D` | 预订签名token，提交购票时携带 |
| 1 | 固定值 | `预订` | 固定字符串 |
| 2 | train_id | `2400000G190T` | 列车内部ID |
| 3 | train_no | `G19` | 显示车次号 |
| 4 | from_station_code | `VNP` | 出发站代码 |
| 5 | to_station_code | `AOH` | 到达站代码 |
| 6 | origin_station_code | `VNP` | 始发站代码 |
| 7 | terminal_station_code | `AOH` | 终点站代码 |
| 8 | depart_time | `14:00` | 出发时间 |
| 9 | arrive_time | `18:32` | 到达时间 |
| 10 | duration | `04:32` | 历时 |
| 11 | can_buy | `Y` | 是否可预订，Y=可以 |
| 12 | secret | `Kimy8j...lfPc%3D` | 购票密钥，下单必须携带 |
| 13 | train_date | `20260610` | 列车运行日期 |
| 14 | train_type | `3` | 列车类型编码 |
| 15 | seat_type | `P4` | 席别代码 |
| 16 | from_station_no | `01` | 出发站在全程中的第几站 |
| 17 | to_station_no | `05` | 到达站在全程中的第几站 |
| 18 | 商务座/特等座 | `无`/数字/空 | 余票数，空=有票，无=无此席别 |
| 21 | 一等座 | `无`/数字/空 | 同上 |
| 22 | 二等座 | `12` | 同上 |
| 23 | 高级软卧 | `无`/数字/空 | 同上 |
| 24 | 软卧 | `无`/数字/空 | 同上 |
| 25 | 动卧 | `无`/数字/空 | 同上 |
| 26 | 硬卧 | `无`/数字/空 | 同上 |
| 29 | seat_flag | `90M0O0D0W0` | 席别组合标识 |
| 30 | seat_code | `9MODO` | 席别简码 |

---

## 余票字段值说明

| 值 | 含义 |
|----|------|
| 空字符串 | 有票（具体数量未显示） |
| 数字（如 `12`） | 剩余票数 |
| `无` | 该列车无此席别 |

---

## 站代码对照表（示例）

| 代码 | 站名 |
|------|------|
| VNP | 北京南 |
| AOH | 上海虹桥 |
| BJP | 北京 |
| SHH | 上海 |
| FTP | 北京丰台 |
| IMH | 上海松江 |
| SNH | 上海南 |

> 完整映射由接口返回的 `data.map` 字段提供，无需硬编码。

---

## Python 解析示例

```python
def parse_train(raw: str, station_map: dict) -> dict:
    parts = raw.split('|')
    return {
        'booking_token': parts[0],
        'train_no':      parts[3],
        'from_station':  station_map.get(parts[4], parts[4]),
        'to_station':    station_map.get(parts[5], parts[5]),
        'depart_time':   parts[8],
        'arrive_time':   parts[9],
        'duration':      parts[10],
        'can_buy':       parts[11],
        'secret':        parts[12],
        'biz_seat':      parts[18] if len(parts) > 18 else '',
        'first_seat':    parts[21] if len(parts) > 21 else '',
        'second_seat':   parts[22] if len(parts) > 22 else '',
        'soft_sleeper':  parts[24] if len(parts) > 24 else '',
        'hard_sleeper':  parts[26] if len(parts) > 26 else '',
    }

station_map = resp['data']['map']
trains = [parse_train(r, station_map) for r in resp['data']['result']]
```

