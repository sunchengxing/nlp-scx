# 语音转写（Lfasr）REST API 详解

## 概述
基于深度全序列卷积神经网络，将 **长段音频（≤5 小时）** 异步转为文字。REST API 方式，不需保持长连接。适用于录音文件批量转写场景。

## 接口规范

| 项目 | 说明 |
|------|------|
| 协议 | `https://`（强烈推荐） |
| 地址 | `https://raasr.xfyun.cn/api/xxx` |
| 请求方式 | POST |
| 鉴权 | HMAC-SHA1（每次请求都需签名） |
| 响应格式 | JSON |
| 音频格式 | wav / flac / opus / m4a / mp3 |
| 音频属性 | 16k 或 8k，8bit 或 16bit，单声道或双声道 |
| 音频大小 | ≤ 500MB |
| 音频时长 | ≤ 5 小时（建议 5 分钟以上） |
| 结果保存 | 30 天 |
| 获取结果 | ≤ 100 次 |

## 调用流程（5 步顺序执行）

```
预处理(/prepare) → 文件分片上传(/upload) → 合并(/merge) → 查进度(/getProgress) → 获取结果(/getResult)
```

## 鉴权机制（HMAC-SHA1）

**所有 5 个接口使用相同的鉴权方式：**

```
signa = Base64(HmacSHA1(MD5(app_id + ts), secret_key))
```

### 公共请求参数（每个接口都带）

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| app_id | string | 是 | 应用 ID |
| signa | string | 是 | 签名 |
| ts | string | 是 | Unix 时间戳（秒） |

---

## 接口 1：预处理 `/api/prepare`

Content-Type: `application/x-www-form-urlencoded`

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| file_len | string | 是 | 文件字节数 |
| file_name | string | 是 | 带后缀的文件名 |
| slice_num | int | 是 | 分片数（建议 10MB/片，<10MB 则=1） |
| lfasr_type | string | 否 | 0 标准版 |
| has_participle | string | 否 | "true" 包含分词 |
| has_seperate | string | 否 | "true" 包含说话人分离 |
| speaker_number | string | 否 | 发音人数 0-10（0=盲分） |
| has_smooth | string | 否 | 顺滑词（true/false） |
| max_alternatives | string | 否 | 最大候选词 [0,5] |
| language | string | 否 | `cn` 中英文 / `en` 英文 |
| pd | string | 否 | 垂直领域：court/edu/finance/medical/tech/sport/gov/game/ecom/car |
| hotWord | string | 否 | 会话级热词，`|` 分隔，单个≤16字符，最多 200 个 |
| role_type | string | 否 | 通用角色分离：填 `1` |

**成功响应：** `{"ok":0, "err_no":0, "data": "task_id字符串"}`

---

## 接口 2：文件分片上传 `/api/upload`

Content-Type: `multipart/form-data`

| 参数 | 类型 | 必传 | 说明 |
|------|------|------|------|
| task_id | string | 是 | 预处理返回的 task_id |
| slice_id | string | 是 | 分片序号（`aaaaaaaaaa` → `aaaaaaaaab` → ...，30进制递增） |
| content | binary | 是 | 分片文件内容 |

**要求：** 必须串行上传，上一片成功后才能上传下一片。

---

## 接口 3：合并 `/api/merge`

Content-Type: `application/x-www-form-urlencoded`

全部切片上传完毕后调用，通知服务端开始转写。只返回状态，不返回结果。

---

## 接口 4：查询进度 `/api/getProgress`

**建议轮询间隔：10 分钟**

### 任务状态码

| status | 含义 |
|--------|------|
| 0 | 任务创建成功 |
| 1 | 音频上传完成 |
| 2 | 音频合并完成 |
| 3 | 音频转写中 |
| 4 | 转写结果处理中 |
| 5 | 转写完成 |
| **9** | 结果上传完成（此时可获取结果） |

---

## 接口 5：获取结果 `/api/getResult`

前提：status=9。服务端也可主动回调推送结果。

**响应 data 字段（JSON 数组）：**

```json
[{
  "bg": "0",        // 句子起始 ms
  "ed": "4950",     // 句子终止 ms
  "onebest": "...",  // 转写文本
  "speaker": "0"     // 说话人编号（0=未开启分离）
}]
```

### 扩展字段（开启分词/多候选时）

| 字段 | 说明 |
|------|------|
| si | 句子标识，从 0 起 |
| wc | 句子置信度 [0,1] |
| wordsResultList | 分词列表 |
| alternativeList | 多候选结果列表 |
| wordBg/wordEd | 词起止帧（1帧=10ms） |
| wordsName | 词内容 |
| wp | 词属性：n=普通词, r=人名, d=数字, m=量词, s=顺滑词, t=地名, p=标点 |

## Lfasr 主要错误码

| 错误码 | 含义 |
|--------|------|
| 26601 | 非法应用信息 |
| 26602 | 任务 ID 不存在 |
| 26603 | 频率受限（≤20次/秒） |
| 26604 | 获取结果次数超限（≤100次） |
| 26605 | 任务处理中 |
| 26606 | 空音频 |
| 26607 | 语种未授权 |
| 26610 | 请求参数错误 |
| 26621/26631 | 文件超 500MB |
| 26622/26632 | 音频超 5 小时 |
| 26623 | 格式受限 |
| 26625/26633 | 服务时长不足 |
| 26650 | 音频格式转换失败 |
| 26680 | 引擎处理错误 |

## 重要约束
- 并发：同一 appid **≤20 次/秒**
- 分片：每片 **10MB** 建议
- 时长建议：尽量 5 分钟以上（短音频易排队积压）
- 返回时间参考：<10 分钟约 3 分钟内返回；≥60 分钟约 10-20 分钟返回
