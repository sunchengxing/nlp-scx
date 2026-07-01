# Kaggle Whisper 消防视频语音转写 Notebook
# GPU: T4 × 2 | Model: faster-whisper large-v3
#
# 使用说明：
# 1. 在 Kaggle 创建 Dataset，上传你的消防视频（mp4/mov/avi）
# 2. 新建 Notebook → Add Input → 选择视频数据集
# 3. 右上角 Accelerator 选 GPU T4 × 2
# 4. Run All

# ========== Cell 1: 安装依赖 ==========
!pip install -q faster-whisper ffmpeg-python
!apt-get update -qq && apt-get install -y -qq ffmpeg

# ========== Cell 2: 导入库 & 配置 ==========
import os
import json
import subprocess
import time
import gc
from pathlib import Path
from datetime import datetime
import numpy as np

# 导入 faster-whisper
from faster_whisper import WhisperModel

# ===== 配置参数 =====
# 视频输入目录（挂载的 Kaggle Dataset 路径，按实际修改）
VIDEO_DIR = Path("/kaggle/input/your-fire-videos")

# 临时目录和输出目录
TEMP_DIR = Path("/kaggle/working/temp")
OUTPUT_DIR = Path("/kaggle/working/output")
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Whisper 模型配置
MODEL_SIZE = "large-v3"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"  # T4 支持 float16
BEAM_SIZE = 5
LANGUAGE = "zh"  # 中文为主
VAD_FILTER = True  # 启用内置 VAD 过滤静音

# 消防领域提示词（提升专业术语识别准确率）
FIRE_PROMPT = (
    "消防指挥调度对话，消防救援场景，包括以下术语："
    "火灾扑救、应急救援、灭火救援、消防车、水枪、水带、泡沫灭火、"
    "破拆工具、搜救、人员疏散、警戒线、供水、排烟、通风排烟、"
    "通讯联络、安全员、指挥员、战斗员、被困人员、云梯、"
    "室内消火栓、消防通道、疏散楼梯、防火门、喷淋系统、"
    "烟感报警器、消防泵房、消防水池、调压站、"
    "接警、出动、到场、展开、扑灭、收队"
)

# 支持的视频格式
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}

# 每处理完 N 个文件清理一次 GPU 缓存
CLEAR_CACHE_EVERY = 3

print(f"✅ 配置加载完成")
print(f"   模型：{MODEL_SIZE} | 设备：{DEVICE} | 精度：{COMPUTE_TYPE}")
print(f"   语言：{LANGUAGE} | VAD过滤：{VAD_FILTER}")
print(f"   视频目录：{VIDEO_DIR}")

# ========== Cell 3: 加载 Whisper 模型 ==========
print("🔄 正在加载 Whisper 模型...")
_start = time.time()

model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)

_elapsed = time.time() - _start
print(f"✅ 模型加载完成，耗时 {_elapsed:.1f} 秒")

# ========== Cell 4: 核心函数 ==========
def find_video_files(directory: Path) -> list:
    """递归查找目录下所有视频文件"""
    videos = []
    if not directory.exists():
        print(f"⚠️ 目录不存在：{directory}")
        return videos
    for ext in VIDEO_EXTENSIONS:
        videos.extend(directory.rglob(f"*{ext}"))
        videos.extend(directory.rglob(f"*{ext.upper()}"))
    return sorted(set(videos))


def extract_audio(video_path: Path, audio_path: Path,
                  sample_rate=16000) -> bool:
    """用 ffmpeg 从视频提取单声道 16kHz WAV 音频"""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn",                     # 不要视频流
        "-acodec", "pcm_s16le",    # PCM 16bit
        "-ar", str(sample_rate),   # 采样率
        "-ac", "1",                # 单声道
        "-y",                      # 覆盖已存在文件
        "-loglevel", "error",      # 只输出错误
        str(audio_path)
    ]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ ffmpeg 提取失败：{e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"   ❌ ffmpeg 超时（>300s）")
        return False


def transcribe_audio(audio_path: Path, video_name: str) -> dict:
    """用 faster-whisper 转写音频，返回结构化结果"""
    print(f"   🎤 正在转写...")
    _t0 = time.time()

    segments, info = model.transcribe(
        str(audio_path),
        language=LANGUAGE,
        beam_size=BEAM_SIZE,
        vad_filter=VAD_FILTER,
        initial_prompt=FIRE_PROMPT,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=400,
        ),
    )

    seg_list = []
    total_text = []
    for seg in segments:
        seg_list.append({
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "tokens": None,  # 不存 tokens，太大
            "avg_logprob": round(seg.avg_logprob, 4),
        })
        total_text.append(seg.text.strip())

    _elapsed = time.time() - _t0
    audio_duration = info.duration  # 秒

    result = {
        "video": video_name,
        "audio_file": str(audio_path.name),
        "duration_seconds": round(audio_duration, 1),
        "detected_language": info.language,
        "language_probability": round(info.language_probability, 4),
        "transcription_time_seconds": round(_elapsed, 1),
        "speed_ratio": round(audio_duration / _elapsed, 1) if _elapsed > 0 else 0,
        "num_segments": len(seg_list),
        "full_text": "".join(total_text),
        "segments": seg_list,
    }

    print(f"   ✅ 转写完成：{len(seg_list)} 段 | "
          f"时长 {audio_duration:.0f}s | "
          f"速度 {result['speed_ratio']}x | "
          f"语言 {info.language}({info.language_probability:.2f})")

    return result


def save_json(data, filepath: Path):
    """保存 JSON 文件"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== Cell 5: 主处理流程 ==========
print("=" * 60)
print("🔍 搜索视频文件...")
video_files = find_video_files(VIDEO_DIR)

if not video_files:
    print("❌ 未找到任何视频文件！")
    print(f"   请检查 VIDEO_DIR 路径：{VIDEO_DIR}")
    print("   支持的格式：{VIDEO_EXTENSIONS}")
else:
    print(f"📹 找到 {len(video_files)} 个视频文件：")
    for vf in video_files:
        size_mb = vf.stat().st_size / (1024 * 1024)
        print(f"   {vf.name} ({size_mb:.1f} MB)")

print("=" * 60)

all_results = []
failed_videos = []
total_start = time.time()

for idx, video_path in enumerate(video_files):
    video_name = video_path.stem
    print(f"\n[{idx+1}/{len(video_files)}] 📹 {video_name}")

    # 1. 提取音频
    audio_path = TEMP_DIR / f"{video_name}_{idx}.wav"
    print(f"   🔉 提取音频...")
    if not extract_audio(video_path, audio_path):
        failed_videos.append({"video": video_name, "error": "音频提取失败"})
        continue

    audio_size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"   音频大小：{audio_size_mb:.1f} MB")

    # 跳过空音频
    if audio_size_mb < 0.01:
        print(f"   ⚠️ 音频为空，跳过")
        failed_videos.append({"video": video_name, "error": "音频为空"})
        audio_path.unlink()
        continue

    # 2. Whisper 转写
    try:
        result = transcribe_audio(audio_path, video_name)
        all_results.append(result)
    except Exception as e:
        print(f"   ❌ 转写失败：{e}")
        failed_videos.append({"video": video_name, "error": str(e)})

    # 3. 清理临时音频（节省磁盘）
    if audio_path.exists():
        audio_path.unlink()

    # 4. 定期清理 GPU 缓存
    if (idx + 1) % CLEAR_CACHE_EVERY == 0:
        gc.collect()
        import torch
        torch.cuda.empty_cache()

total_elapsed = time.time() - total_start

print("\n" + "=" * 60)
print("📊 处理完成")
print(f"   成功：{len(all_results)}/{len(video_files)}")
print(f"   失败：{len(failed_videos)}")
print(f"   总耗时：{total_elapsed:.0f} 秒")
print("=" * 60)

# ========== Cell 6: 保存结果 ==========
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# 主结果 JSON：每个视频的完整转写
results_json_path = OUTPUT_DIR / f"transcripts_{timestamp}.json"
save_json({
    "metadata": {
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "language": LANGUAGE,
        "num_videos_total": len(video_files),
        "num_videos_success": len(all_results),
        "num_videos_failed": len(failed_videos),
        "total_time_seconds": round(total_elapsed, 0),
        "timestamp": timestamp,
        "fire_prompt_used": FIRE_PROMPT,
    },
    "results": all_results,
    "failed": failed_videos,
}, results_json_path)

print(f"📄 主结果已保存：{results_json_path}")
print(f"   文件大小：{results_json_path.stat().st_size / 1024:.1f} KB")

# 简化摘要 JSON：只含视频名 + 完整文本 + 时间段数
summary = []
for r in all_results:
    summary.append({
        "video": r["video"],
        "duration_s": r["duration_seconds"],
        "segments": r["num_segments"],
        "full_text": r["full_text"],
    })
summary_path = OUTPUT_DIR / f"summary_{timestamp}.json"
save_json(summary, summary_path)
print(f"📄 摘要已保存：{summary_path}")

# ========== Cell 7: 生成 SRT 字幕（可选） ==========
def generate_srt(segments, output_path):
    """将转写段转换为 SRT 字幕格式"""
    def _format_time(seconds):
        ms = int((seconds - int(seconds)) * 1000)
        s = int(seconds) % 60
        m = (int(seconds) // 60) % 60
        h = int(seconds) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_format_time(seg['start'])} --> {_format_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")  # 空行分隔

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# 为每个视频生成独立 SRT
srt_dir = OUTPUT_DIR / "srt"
srt_dir.mkdir(exist_ok=True)
for r in all_results:
    srt_path = srt_dir / f"{r['video']}.srt"
    generate_srt(r["segments"], srt_path)
print(f"🎬 SRT 字幕已保存至：{srt_dir}  ({len(all_results)} 个文件)")

# ========== Cell 8: 结果预览 ==========
print("\n" + "=" * 60)
print("📋 转写结果预览")
print("=" * 60)

for r in all_results[:3]:  # 只预览前 3 个
    text_preview = r["full_text"][:200]
    print(f"\n🎬 {r['video']}")
    print(f"   时长：{r['duration_seconds']}s | "
          f"段数：{r['num_segments']} | "
          f"语言：{r['detected_language']}")
    print(f"   文本预览：{text_preview}...")
    if r["segments"]:
        seg = r["segments"][0]
        print(f"   首段 [{seg['start']}s-{seg['end']}s]: {seg['text'][:100]}")

print(f"\n📁 所有输出文件在：{OUTPUT_DIR}")
!ls -lh {OUTPUT_DIR}

# ========== 完成 ==========
print("\n✅ 全部完成！下载 output 文件夹即可获取转写结果。")
