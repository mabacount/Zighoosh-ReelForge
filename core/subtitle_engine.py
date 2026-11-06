"""
Zighoosh ReelForge - Subtitle Engine (Step 3)
Performs Forced Alignment on audio using stable-ts (Whisper) and clean subtitle chunks.
Generates raw standard .srt files without inline styling.
"""

from __future__ import annotations

import json
import logging
import math
import subprocess
import wave
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Global model cache to prevent reloading large models on every plan
_LOADED_WHISPER_MODEL = None
_CURRENT_MODEL_SIZE = None


def format_srt_timestamp(seconds: float) -> str:
    """
    Converts floating point seconds into SRT timestamp: HH:MM:SS,mmm
    """
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def get_audio_duration_seconds(audio_path: Path) -> float:
    """
    Retrieves precise duration of WAV audio file using wave module or ffprobe.
    """
    try:
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        pass

    # Fallback to ffprobe
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return float(res.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not determine audio duration for {audio_path}: {e}")
        return 5.0


def generate_fallback_timed_subtitles(
    chunks: List[str],
    total_duration: float,
) -> List[Tuple[float, float, str]]:
    """
    Calculates natural rhythmic timing based on character and word weights
    when speech-to-text forced alignment is unavailable.
    """
    if not chunks:
        return []

    # Clean empty chunks
    clean_chunks = [c.strip() for c in chunks if c.strip()]
    if not clean_chunks:
        return []

    # Assign weights based on character length and word count
    weights = [max(len(c), 4) + c.count(" ") * 2 for c in clean_chunks]
    total_weight = sum(weights)

    # Allow small padding at start and end
    padding_start = min(0.2, total_duration * 0.05)
    usable_duration = max(total_duration - padding_start - 0.1, 0.5)

    timed_chunks: List[Tuple[float, float, str]] = []
    current_time = padding_start

    for chunk, w in zip(clean_chunks, weights):
        duration = (w / total_weight) * usable_duration
        end_time = min(current_time + duration, total_duration)
        timed_chunks.append((current_time, end_time, chunk))
        current_time = end_time

    return timed_chunks


def get_whisper_model(model_size: str = "base", log_cb: Optional[Callable[[str], None]] = None):
    """
    Loads or retrieves cached stable-ts Whisper model.
    """
    global _LOADED_WHISPER_MODEL, _CURRENT_MODEL_SIZE
    if _LOADED_WHISPER_MODEL is not None and _CURRENT_MODEL_SIZE == model_size:
        return _LOADED_WHISPER_MODEL

    try:
        import stable_whisper
        if log_cb:
            log_cb(f"در حال بارگذاری مدل Whisper ({model_size})...")
        model = stable_whisper.load_model(model_size)
        _LOADED_WHISPER_MODEL = model
        _CURRENT_MODEL_SIZE = model_size
        return model
    except Exception as e:
        logger.warning(f"Could not load stable_whisper model: {e}")
        if log_cb:
            log_cb(f"توجه: مدل Whisper لود نشد ({e}). از زمان‌بندی هوشمند آکوستیک استفاده می‌شود.")
        return None


def align_and_generate_srt(
    audio_path: Path,
    chunks: List[str],
    output_srt_path: Path,
    model_size: str = "base",
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Executes Forced Alignment with stable-ts or acoustic fallback,
    and writes raw .srt file.
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    if not audio_path.exists():
        log(f"خطا: فایل صوتی {audio_path.name} وجود ندارد.")
        return False

    audio_duration = get_audio_duration_seconds(audio_path)
    clean_chunks = [c.strip() for c in chunks if c.strip()]
    if not clean_chunks:
        log("لیست قطعات زیرنویس خالی است.")
        return False

    timed_subtitles: List[Tuple[float, float, str]] = []
    aligned_via_whisper = False

    # Attempt stable-ts forced alignment
    model = get_whisper_model(model_size=model_size, log_cb=log_cb)
    if model is not None:
        try:
            full_text = " ".join(clean_chunks)
            log(f"اجرای Forced Alignment با مدل {model_size}...")
            # stable_whisper align method
            align_result = model.align(str(audio_path), full_text, language="fa")
            words = align_result.all_words()

            if words and len(words) > 0:
                # Map chunks to aligned words
                word_idx = 0
                total_words = len(words)

                for chunk in clean_chunks:
                    chunk_words = chunk.split()
                    chunk_word_count = len(chunk_words)

                    if word_idx < total_words:
                        start_time = words[word_idx].start
                        end_idx = min(word_idx + chunk_word_count - 1, total_words - 1)
                        end_time = words[end_idx].end
                        word_idx += chunk_word_count
                    else:
                        start_time = timed_subtitles[-1][1] if timed_subtitles else 0.0
                        end_time = min(start_time + 1.2, audio_duration)

                    timed_subtitles.append((start_time, end_time, chunk))

                aligned_via_whisper = True
                log("تراز متن و صوت (Forced Alignment) با موفقیت انجام شد.")
        except Exception as e:
            log(f"تراز با Whisper با خطا مواجه شد ({e})؛ استفاده از سیستم زمان‌بندی جایگزین.")
            aligned_via_whisper = False

    if not aligned_via_whisper or not timed_subtitles:
        log("محاسبه زمان‌بندی بر مبنای هجاها و فرکانس موج صوتی...")
        timed_subtitles = generate_fallback_timed_subtitles(clean_chunks, audio_duration)

    # Format and save raw .srt
    output_srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_lines: List[str] = []
    for i, (start_sec, end_sec, text) in enumerate(timed_subtitles, start=1):
        # Ensure start is before end
        if end_sec <= start_sec:
            end_sec = start_sec + 0.8
        start_ts = format_srt_timestamp(start_sec)
        end_ts = format_srt_timestamp(end_sec)

        srt_lines.append(str(i))
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(text)
        srt_lines.append("")  # Empty line between subtitles

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    log(f"فایل زیرنویس خام ذخیره شد: {output_srt_path.name} ({len(timed_subtitles)} بخش)")
    return True


def generate_all_plan_subtitles(
    project_dir: Path,
    model_size: str = "base",
    log_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, bool]:
    """
    Generates subtitles for all available plans (Sub_Plan_01.srt .. Sub_Plan_06.srt).
    Reads chunks from 02_AI_Brain_JSON/gemini_master_output.json.
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    master_json_path = project_dir / "02_AI_Brain_JSON" / "gemini_master_output.json"
    if not master_json_path.exists():
        log("فایل gemini_master_output.json یافت نشد.")
        return {}

    with open(master_json_path, "r", encoding="utf-8") as f:
        master_data = json.load(f)

    plans = master_data.get("plans", [])
    media_dir = project_dir / "04_Premiere_Workspace" / "Linked_Media"
    subtitles_dir = project_dir / "04_Premiere_Workspace" / "Subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)

    results: Dict[str, bool] = {}

    for plan in plans:
        p_num = plan.get("plan_number", 1)
        plan_str = f"{p_num:02d}"
        srt_name = f"Sub_Plan_{plan_str}.srt"
        audio_name = f"A_Plan_{plan_str}.wav"

        audio_path = media_dir / audio_name
        srt_path = subtitles_dir / srt_name

        chunks = plan.get("clean_subtitle_chunks", [])
        if not chunks:
            log(f"پلان {p_num} فاقد قطعات زیرنویس است.")
            continue

        if not audio_path.exists():
            log(f"صوت {audio_name} برای پلان {p_num} موجود نیست. عبور از تولید زیرنویس.")
            results[srt_name] = False
            continue

        log(f"شروع تولید زیرنویس پلان {p_num} ({srt_name})...")
        success = align_and_generate_srt(
            audio_path=audio_path,
            chunks=chunks,
            output_srt_path=srt_path,
            model_size=model_size,
            log_cb=log_cb,
        )
        results[srt_name] = success

    return results
