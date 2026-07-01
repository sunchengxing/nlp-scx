# 7.1.2 Whisper 语音识别 — Kaggle Notebook 使用指南

## 所需资源（全部免费）

| 资源 | 说明 |
|------|------|
| Kaggle 账号 | 注册即送 GPU 30h/周 |
| GPU T4 × 2 | 16GB 显存，large-v3 跑得动 |
| 磁盘 20GB | 只放临时音频，够用 |
| 互联网 | pip install 畅通 |

## 快速开始（3 步）

### 步骤 1：准备消防视频

在 Kaggle 上找一个消防视频数据集，或者自己上传：

**方案 A：用 Kaggle 已有数据集**
- 搜索关键词：`fire video`、`fire detection`、`rescue operation`
- 注意：大部分是**图片/帧**数据集，不是视频。优先找含 `.mp4` 文件的数据集

**方案 B：自己上传（推荐，可控）**
1. Kaggle → `Data` → `New Dataset`
2. 上传消防相关视频（消防演练、火灾救援、消防讲座等）
3. 权限选 **Private**（你的视频别人看不到）

**方案 C：Notebook 里用 yt-dlp 临时下载**
```python
!pip install -q yt-dlp
!yt-dlp -f "best[height<=720]" "https://www.youtube.com/watch?v=xxx" -o /kaggle/working/videos/%(title)s.%(ext)s
VIDEO_DIR = Path("/kaggle/working/videos")
```

### 步骤 2：创建 Kaggle Notebook

1. kaggle.com → `Code` → `New Notebook`
2. 右上角 **Accelerator** → 选 `GPU T4 × 2`
3. 右侧 **Add Input** → 搜索并添加你的视频数据集
4. 把 `kaggle_whisper_notebook.py` 的内容按 Cell 复制进去
5. 修改 Cell 2 中的视频路径：
```python
VIDEO_DIR = Path("/kaggle/input/你的数据集名称")
```

### 步骤 3：Run All

菜单 `Run` → `Run All`，等待完成。

处理速度参考：1 小时视频 ≈ 10 分钟转写（GPU T4）。

## 输出文件

```
/kaggle/working/output/
├── transcripts_20260701_120000.json  ← 完整结果（每段时间戳+文本+置信度）
├── summary_20260701_120000.json      ← 摘要（每个视频的完整文本）
└── srt/
    ├── video1.srt                    ← SRT 字幕文件
    └── video2.srt
```

## JSON 输出格式

```json
{
  "metadata": {
    "model": "large-v3",
    "language": "zh",
    "num_videos_total": 5,
    "num_videos_success": 4,
    "num_videos_failed": 1
  },
  "results": [
    {
      "video": "fire_drill_01",
      "duration_seconds": 120.5,
      "detected_language": "zh",
      "language_probability": 0.98,
      "transcription_time_seconds": 18.2,
      "speed_ratio": 6.6,
      "num_segments": 15,
      "full_text": "接警中心收到报警...",
      "segments": [
        {
          "id": 0,
          "start": 0.0,
          "end": 3.5,
          "text": "119吗我们这里着火了",
          "avg_logprob": -0.23
        }
      ]
    }
  ],
  "failed": []
}
```

## 消防术语提升技巧

Notebook 已内置 `FIRE_PROMPT` 消防术语列表，Whisper 会优先匹配这些词。

如果你的视频涉及的消防术语不同，修改 Cell 2 中的 `FIRE_PROMPT` 变量即可。

## 常见问题

| 问题 | 解决 |
|------|------|
| `Out of memory` | 改用 `medium` 模型，或 `compute_type="int8"` |
| 转写结果不对 | 检查音频是否有语音（很多消防视频只有警报声） |
| Kaggle 断连 | 用 `Save Version` + `Save & Run All` 后台跑 |
| 视频太多跑不完 | 分批跑，每次几个视频，结果合并 |
| 磁盘写满 | Notebook 已自动逐文件清理临时音频 |
