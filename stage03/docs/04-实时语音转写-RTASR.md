# 实时语音转写（RTASR）API 详解

## 概述
基于深度全序列卷积神经网络，WebSocket 长连接实现连续音频流实时识别，**单次连接时长理论上无限制**。适用于会议记录、直播字幕等持续流式场景。

## 接口规范

| 项目 | 说明 |
|------|------|
| 协议 | `ws[s]://`（强烈推荐 wss） |
| 地址 | `wss://rtasr.xfyun.cn/v1/ws` |
| 鉴权 | HMAC-SHA1（URL 参数传递） |
| 音频 | 16kHz，16bit，单声道，PCM(pcm_s16le) |
| 数据发送 | 每 40ms 发送 1280 字节 Binary Message |

## 鉴权机制（HMAC-SHA1）

与 IAT 系列不同，RTASR 使用 **HMAC-SHA1** + URL 参数鉴权：

```
signa = Base64(HmacSHA1(MD5(appid + ts), api_key))
```

### URL 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| appid | string | 是 | 应用 ID |
| ts | string | 是 | Unix 时间戳（秒） |
| signa | string | 是 | 签名 |
| lang | string | 否 | `cn` 中文（默认）/ `en` 英文 |
| punc | string | 否 | `punc=0` 过滤标点 |
| pd | string | 否 | 垂直领域：court/edu/finance/medical/tech/isp/gov/ecom/mil/com/life/car |
| vadMdn | int | 否 | 远场=1（默认）/ 近场=2 |
| roleType | int | 否 | 角色分离：2 开启 |
| engLangType | int | 否 | 1 自动中英 / 2 少量英文 / 4 纯中文 |
| transType | string | 否 | `normal` 翻译模式 |
| transStrategy | int | 否 | 翻译策略：1 VAD后 / **2 中间结果**（推荐）/ 3 按标点 |
| targetLang | string | 否 | 翻译目标语种：en/ja/ko/ru/fr/es/vi/de/it/ar 等 |

## 数据交互流程

### 握手阶段
WebSocket 连接后服务端立即返回握手结果（Text JSON）：
```json
{"action":"started","code":"0","data":"","desc":"success","sid":"rta..."}
// 或失败：
{"action":"error","code":"10110","desc":"invalid authorization|illegal signa","sid":"rta..."}
```

### 实时通信阶段

**发送数据：** Binary Message 发送 PCM 音频，建议 40ms/1280 字节。
**结束标志：** 音频发送完毕后，发送 Binary Message `{"end": true}`。

**超时限制：** 超过 **15 秒**未发送数据，服务端断开连接。

## 返回结果字段

| 字段 | 含义 |
|------|------|
| bg | 句子开始时间（ms） |
| ed | 句子结束时间（ms） |
| w | 词识别结果 |
| wp | 词标识：n=普通词, s=顺滑词(语气词), p=标点 |
| wb | 词在句内开始帧（1帧=10ms），词开始时间 = bg + wb×10 ms |
| we | 词在句内结束帧（1帧=10ms），词结束时间 = bg + we×10 ms |
| type | 0=最终结果 / 1=中间结果 |
| seg_id | 转写序号，从 0 开始 |
| rl | 角色编号（开启角色分离时返回） |

### 翻译扩展字段（开启翻译时）

| 字段 | 说明 |
|------|------|
| biz | `"trans"` |
| src | 送翻译的原始文本 |
| dst | 目标语种翻译文本 |
| isEnd | 翻译是否结束 |

## 关键错误码

| 错误码 | 含义 |
|--------|------|
| 0 | 成功 |
| 10105 | 无权限（检查 apiKey、IP 白名单、ts） |
| 10106 | 无效参数 |
| 10107 | 非法参数值 |
| 10110 | 无授权许可（检查有效期、时长、路数） |
| 10202 | WebSocket 连接错误 |
| 10204 | WebSocket 写错误 |
| 10205 | WebSocket 读错误 |
| 10800 | 超过最大连接数 |
| 37005 | 超过 15 秒未发送音频 |

## 特殊能力
- **实时翻译**：边转写边翻译到目标语言
- **角色分离**：自动区分不同说话人（需开启 roleType=2）
- **多领域优化**：支持法院/教育/金融/医疗/科技/政府/电商/军事/汽车等垂直领域
