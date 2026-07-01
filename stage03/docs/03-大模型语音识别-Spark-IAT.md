# 大模型语音识别（Spark IAT）API 详解

## 概述
星火大模型版语音听写，底层使用大模型引擎，相比传统 IAT 支持 **202 种方言免切换识别**，中英文混合识别效果更好。

## 接口规范

| 项目 | 说明 |
|------|------|
| 协议 | `wss://`（强烈推荐） |
| 地址 | `wss://iat.xf-yun.com/v1` |
| 编码 | UTF-8 |
| 响应 | JSON（Base64 编码的结果文本） |
| 音频 | 16k/8k，16bit，单声道，PCM(raw) 或 MP3(lame) |
| 最长 | 60 秒 |

## 与 IAT v2 的关键区别

| 维度 | IAT v2 | Spark IAT |
|------|--------|-----------|
| 地址 | `iat-api.xfyun.cn/v2/iat` | `iat.xf-yun.com/v1` |
| domain 参数 | `iat`（多领域可选） | 固定 `slm` |
| language | `zh_cn` / `en_us` | 固定 `zh_cn` |
| accent | `mandarin`（可选方言） | 固定 `mandarin` |
| 方言支持 | 23 种 | **202 种免切换** |
| 鉴权 | 同（hmac-sha256） | 同 |
| 热词 | 不支持 | 支持 `dhw` 参数 |

## 鉴权机制
与 IAT v2 完全相同的 HMAC-SHA256 签名机制。区别仅在于 request-line 为 `GET /v1 HTTP/1.1` 而非 `/v2/iat`。

```
signature_origin = "host: iat.xf-yun.com\ndate: $date\nGET /v1 HTTP/1.1"
```

## 请求参数

### header 公共参数

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| header.app_id | string | 是 | 平台 APPID |
| header.status | int | 是 | 0/1/2（首帧/中间/末帧） |

### parameter.iat 参数

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| domain | string | 是 | 固定 `slm` |
| language | string | 是 | 固定 `zh_cn` |
| accent | string | 是 | 固定 `mandarin` |
| eos | int | 否 | 静音超时 ms |
| ltc | int | 否 | 1 不筛选 / 2 只出中文 / 3 只出英文 |
| dwa | string | 否 | `wpgs` 开启动态修正 |
| dhw | string | 否 | 会话级热词（UTF-8 和 GB2312 编码） |

### payload.audio 参数

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| encoding | string | 是 | `raw`(PCM) / `lame`(MP3) |
| sample_rate | int | 否 | 16000 / 8000 |
| audio | string | 是 | Base64 编码音频 |

## 返回结果

结果文本经过 Base64 编码，解码后为 JSON：

```json
{
  "sn": 1,
  "ls": false,
  "ws": [
    {
      "cw": [{"w": "科大讯飞", "sc": 0.98}]
    }
  ],
  "pgs": "apd",    // 动态修正
  "rg": [0, 1]     // 替换范围
}
```

## 传输建议
- 每 **40ms** 发送一次
- 每次 **1280 字节**（未压缩）
- 首帧传完整 header + parameter + payload
- 中间帧仅传 header + payload，status=1
- 末帧 status=2，audio 为空字符串
