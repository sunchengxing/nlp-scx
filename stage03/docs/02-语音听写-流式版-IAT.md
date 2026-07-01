# 语音听写（流式版 IAT）API 详解

## 核心特性
- 1 分钟内即时语音转文字，边上传音频边返回识别结果
- 支持中文、英文、中英文混合、23 种方言
- 支持动态修正（仅中文）：识别过程中不断修正前面已返回的结果

## 接口规范

| 项目 | 说明 |
|------|------|
| 协议 | `wss://`（强烈推荐） |
| 地址 | `wss://iat-api.xfyun.cn/v2/iat`（主力）/ `ws-api.xfyun.cn`（备用） |
| 小语种地址 | `wss://iat-niche-api.xfyun.cn/v2/iat` |
| 编码 | UTF-8 |
| 响应格式 | JSON（所有帧 opcode=1 TextMessage） |

## 音频要求

| 参数 | 规格 |
|------|------|
| 采样率 | 16000Hz 或 8000Hz |
| 位深 | 16bit |
| 声道 | 单声道 |
| 格式 | raw（PCM）、speex(8k)、speex-wb(16k)、lame（MP3，仅中英文） |
| 最长 | 60 秒 |

## 数据传输节奏

- **建议间隔 40ms/次**，每次 1280 字节（未压缩 PCM 16k）
- 3 种帧状态：`status=0` 首帧（需带 common + business 参数）、`status=1` 中间帧、`status=2` 末帧（必须发送，audio 可为空）

## 鉴权机制（HMAC-SHA256）

### URL 参数
- `host`：如 `iat-api.xfyun.cn`
- `date`：RFC1123 GMT 格式，如 `Wed, 10 Jul 2019 07:35:43 GMT`
- `authorization`：Base64 编码的签名信息

### 生成步骤（4 步）

```
# 第 1 步：构建签名字符串
signature_origin = "host: $host\ndate: $date\nGET /v2/iat HTTP/1.1"

# 第 2 步：HMAC-SHA256 + Base64
signature = base64(hmac_sha256(signature_origin, APISecret))

# 第 3 步：拼接 authorization 原始字符串
auth_origin = 'api_key="$api_key",algorithm="hmac-sha256",headers="host date request-line",signature="$signature"'

# 第 4 步：对 auth_origin 做 Base64 得到最终 authorization
```

### 时钟校验
服务端对 Date 参数检查，最大允许 **±300 秒**偏差，超出则拒绝。

## 请求参数

### 公共参数 common（首帧必传，JSON）

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| app_id | string | 是 | 讯飞开放平台 APPID |

### 业务参数 business（首帧必传，JSON）

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| language | string | 是 | `zh_cn` 中文 / `en_us` 英文 |
| domain | string | 是 | `iat` 日常 / `medical` 医疗 / `gov-seat-assistant` 等 |
| accent | string | 是 | `mandarin` 普通话，支持 23 种方言 |
| eos | int | 否 | 后端点静默检测 ms，默认 2000，最大 10000 |
| dwa | string | 否 | `wpgs` 开启动态修正（仅中文普通话） |
| ptt | int | 否 | 标点添加：1 开启（默认）/ 0 关闭 |
| nbest | int | 否 | 句子多候选 [1,5] |
| wbest | int | 否 | 词语多候选 [1,5] |
| rlang | string | 否 | `zh-cn` 简体 / `zh-hk` 繁体 |
| nunum | int | 否 | 数字转阿拉伯：1 开启 / 0 关闭 |

### 数据流参数 data（每帧都传）

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| status | int | 是 | 0 首帧 / 1 中间 / 2 末帧 |
| format | string | 是 | `audio/L16;rate=16000` 或 `audio/L16;rate=8000` |
| encoding | string | 是 | `raw`(PCM) / `speex` / `speex-wb` / `lame`(MP3) |
| audio | string | 是 | 音频 Base64 编码（末帧可为空串） |

## 返回参数

### 握手成功首帧

```json
{
  "sid": "iat00000000@ch...",
  "code": 0,
  "message": "success"
}
```

### 识别结果 data 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| data.status | int | 0 开始 / 1 中间 / 2 结束 |
| data.result.sn | int | 结果序号 |
| data.result.ls | bool | 是否最后一片 |
| data.result.ws | array | 听写结果词列表 |
| data.result.ws[].cw | array | 中文分词 |
| data.result.ws[].cw[].w | string | 字/词 |
| data.result.ws[].cw[].sc | float | 置信度 [0,1] |
| data.result.pgs | string | `"apd"` 追加 / `"rpl"` 替换前面结果（动态修正） |
| data.result.rg | array | 替换范围如 `[2,5]`（动态修正） |

## 关键错误码

| 错误码 | 含义 | 处理 |
|--------|------|------|
| 10005 | APPID 授权失败 | 确认 APPID 和服务开通 |
| 10006 | 采样率参数获取失败 | 检查参数上传 |
| 10007 | 采样率非法 | 确认 16k 或 8k |
| 10043 | 音频解码失败 | 检查编码参数 |
| 10114 | 会话超时 | 60s 内完成 |
| 10160 | JSON 格式非法 | 检查请求体 |
| 10161 | Base64 解码失败 | 确认音频已编码 |
| 10163 | 缺少必传参数 | 检查报错提示的参数 |
| 10165 | status 非法 | 首帧必须 status=0 |
| 10200 | 数据超时 | 检查是否 10s 未发送 |
| 11200 | 调用量超限/未授权 | 检查套餐 |
| 11201 | 日流控超限 | 联系商务 |

## 会话规则
- 整个会话最长 **60s**，超时服务端主动断开
- **10s** 未发送数据，服务端主动断开
- eos 默认 2000ms，最大 10000ms
- 客户端关闭连接应发送 WebSocket 错误码 **1000**
- 默认并发 **50 路**
