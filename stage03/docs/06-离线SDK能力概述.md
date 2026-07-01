# 离线语音识别 SDK 能力概述

> 离线 SDK 通过下载集成到客户端，不需联网即可使用。详细 API 文档需下载对应 SDK 查看。

## 离线语音听写

| 特性 | 说明 |
|------|------|
| 平台 | Android（主力）、iOS、Windows、Linux |
| 传统 SDK 版本 | 1144 |
| 新版（AIKit） | `com.iflytek.aikit.core`，`edencn_2-2-14` |
| 场景 | 无网络环境下的自由语音识别 |

## 离线命令词识别

| 特性 | 说明 |
|------|------|
| 平台 | Android、iOS、Windows、Linux |
| 传统 SDK 版本 | 1144 |
| 新版（AIKit-ESR） | `2-2-15-rc5`（Android AAR 约 8.8MB） |
| 场景 | 智能家居设备指令（"打开灯"、"调高温度"等） |
| 特点 | 预定义语法/命令词表，离线本地匹配，响应极快 |

## 语音唤醒

| 特性 | 说明 |
|------|------|
| 平台 | Android、iOS、Windows、Linux |
| 传统 SDK 版本 | 1144 |
| 新版（AIKit-IVW） | `2-2-17-rc6`（Android AAR 约 4.7MB） |
| 场景 | 设备端关键词唤醒（"你好小飞"等） |
| 特点 | 低功耗持续监听，命中关键词后触发 |

## AIKit 系列（新一代统一 SDK）

统一包名 `com.iflytek.aikit.core`，打包为 AAR（Android）/ ZIP（其他平台）：

| SDK | 能力 | Android 大小 | Linux | iOS | Windows |
|-----|------|-------------|--------|-----|---------|
| AIKit-IVW | 语音唤醒 | 4.7MB AAR | 5.3MB | 5.1MB | 5.1MB |
| AIKit-ESR | 命令词 | 8.8MB AAR | 81.5MB | 95.1MB | 82.5MB |
| AIKit-EDEnCN | 离线听写 | AAR（仅 Android） | - | - | - |
| AIKit-AISound | 轻量 TTS | 4.0MB AAR | 20.5MB | 19.9MB | - |
| AIKit-XTTS | 高品质离线TTS | 7.2MB AAR | 27.2MB | 24.8MB | 25.5MB |

## 离线 SDK 获取方式

1. 登录讯飞开放平台控制台 → 我的应用 → 选择应用
2. 服务管理页面 → SDK 版块
3. 选择平台 + 能力 → 下载 SDK zip/aar
4. 需同意《开发者用户个人信息保护合规指引》

每个 SDK 包内含：开发文档、库文件、示例代码。合规要求：必须集成对应《个人信息处理规则》文档中说明的隐私合规模块。
