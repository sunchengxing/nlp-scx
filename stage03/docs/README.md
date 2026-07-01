# 7.1 语音识别 — 总结 README

## 文档清单

### 7.1.1 科大讯飞 SDK

| 文件 | 内容 |
|------|------|
| 01-服务全景图.md | 全部服务概览，在线/离线分类 |
| 02-语音听写-流式版-IAT.md | IAT 流式听写 API 详解（最常用） |
| 03-大模型语音识别-Spark-IAT.md | Spark 大模型版听写（202种方言） |
| 04-实时语音转写-RTASR.md | RTASR 长音频实时转写 + 翻译 |
| 05-语音转写-Lfasr-REST-API.md | Lfasr 长音频异步转写（5步流程） |
| 06-离线SDK能力概述.md | 离线听写/命令词/唤醒 SDK 能力 |
| 07-服务对比与选型指南.md | 4 种在线服务横向对比 + 选型决策树 |
| 08-Python集成实践-IAT.md | Python 代码：IAT 流式听写 |
| 09-Python集成实践-Lfasr.md | Python 代码：Lfasr 长音频转写 |
| 10-Python集成实践-RTASR-SparkIAT.md | Python 代码：RTASR + Spark IAT |

### 7.1.2 Whisper 语音识别（结合消防项目视频）

| 文件 | 内容 |
|------|------|
| kaggle_whisper_notebook.py | 🔥 Kaggle Notebook 完整脚本（GPU T4，faster-whisper large-v3） |
| 11-Kaggle-Whisper使用指南.md | 使用说明：数据集准备、Notebook 操作、输出格式 |

## 核心信息速查

### 开发者接入 3 步走
1. **注册** → https://www.xfyun.cn/ 注册账号
2. **创建应用** → 控制台创建，获取 APPID / APIKey / APISecret
3. **开通服务** → 控制台 → 服务管理 → 开通语音听写等服务

### 两种鉴权机制
- **HMAC-SHA256**：IAT / Spark IAT 使用，需 GMT 时间 + host + request-line
- **HMAC-SHA1**：RTASR / Lfasr 使用，需 MD5(appid+ts) + secret_key

### 音频通用要求
- 采样率：**16000Hz**（大部分场景）
- 位深：**16bit**
- 声道：**单声道**
- 格式：PCM(raw) 最通用

### 服务选择速查
- 📱 App 语音输入 → **IAT 流式听写** 或 **Spark IAT**
- 📝 录音文件转文字 → **Lfasr 语音转写**
- 🎤 会议/直播实时字幕 → **RTASR 实时转写**
- 📴 离线场景 → **离线听写/命令词 SDK**
- 🔊 设备唤醒 → **语音唤醒 SDK**

### 重要约束
- IAT/Spark IAT 单次最长 60s，超时会话自动断开
- RTASR 15s 无数据会断开
- Lfasr 分片建议 10MB/片，轮询间隔 10 分钟
- 所有服务默认并发有限，超量需申请
- 时钟偏差不能超过 300s（HMAC-SHA256 系列）
