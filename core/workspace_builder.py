"""
Zighoosh ReelForge - Workspace Builder & Media Linker Module (Step 3)
Handles safe directory migration to Active Workspace, intelligent media renaming,
audio extraction via FFmpeg, and mother template deployment.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def migrate_to_active_workspace(
    current_project_dir: Path,
    active_workspace_base: Path,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Safely moves project directory from Downloads/temp path to Active Workspace
    to prevent broken links in Premiere Pro.
    If project is already inside active workspace, returns current path.
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    current_project_dir = current_project_dir.resolve()
    active_workspace_base = active_workspace_base.resolve()
    active_workspace_base.mkdir(parents=True, exist_ok=True)

    # Check if already inside active workspace
    try:
        current_project_dir.relative_to(active_workspace_base)
        log(f"پروژه در حال حاضر در مسیر اکتیو قرار دارد: {current_project_dir}")
        return current_project_dir
    except ValueError:
        pass

    target_dir = active_workspace_base / current_project_dir.name
    log(f"در حال انتقال ایمن پروژه از '{current_project_dir}' به '{target_dir}'...")

    if target_dir.exists():
        # Destination folder already exists; merge or update
        log("پوشه مقصد در ورک‌اسپیس اکتیو از قبل وجود دارد. در حال انتقال فایل‌ها...")
        for item in current_project_dir.iterdir():
            dest_item = target_dir / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.move(str(item), str(dest_item))
            else:
                shutil.copy2(item, dest_item)
        shutil.rmtree(current_project_dir, ignore_errors=True)
    else:
        shutil.move(str(current_project_dir), str(target_dir))

    log(f"پروژه با موفقیت به ورک‌اسپیس اکتیو منتقل شد: {target_dir}")
    return target_dir


def extract_audio_with_ffmpeg(
    video_path: Path,
    output_audio_path: Path,
    log_cb: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Extracts high-quality PCM WAV audio from video using FFmpeg.
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(output_audio_path),
    ]

    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            check=True,
        )
        return True
    except Exception as e:
        if log_cb:
            log_cb(f"خطا در استخراج صوتی با FFmpeg از {video_path.name}: {e}")
        logger.error(f"FFmpeg extraction error: {e}")
        return False


def link_and_rename_raw_media(
    project_dir: Path,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Scans 03_Raw_DropZone and standardizes raw files into:
    - 04_Premiere_Workspace/Linked_Media/V_Plan_01.mp4 ... V_Plan_06.mp4
    - 04_Premiere_Workspace/Linked_Media/A_Plan_01.wav ... A_Plan_06.wav
    - 04_Premiere_Workspace/Linked_Media/BGM_Track.mp3
    - 05_Thumbnail_Workspace/Linked_Assets/AI_Background.png
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    dropzone_dir = project_dir / "03_Raw_DropZone"
    premiere_media = project_dir / "04_Premiere_Workspace" / "Linked_Media"
    thumb_assets = project_dir / "05_Thumbnail_Workspace" / "Linked_Assets"

    premiere_media.mkdir(parents=True, exist_ok=True)
    thumb_assets.mkdir(parents=True, exist_ok=True)

    plan_folder_names = [
        "Plan_01_Hook_Avatar",
        "Plan_02_Problem",
        "Plan_03_Company_Intro",
        "Plan_04_Requirements",
        "Plan_05_Benefits",
        "Plan_06_CTA_Avatar",
    ]

    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    audio_exts = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}

    results = {
        "linked_videos": [],
        "linked_audios": [],
        "bgm_linked": False,
        "thumbnail_bg_linked": False,
        "warnings": [],
    }

    # Process Plans 1 through 6
    for idx, folder_name in enumerate(plan_folder_names, start=1):
        plan_num_str = f"{idx:02d}"
        target_video_name = f"V_Plan_{plan_num_str}.mp4"
        target_audio_name = f"A_Plan_{plan_num_str}.wav"

        target_video_path = premiere_media / target_video_name
        target_audio_path = premiere_media / target_audio_name

        folder_path = dropzone_dir / folder_name
        if not folder_path.exists():
            results["warnings"].append(f"پوشه {folder_name} یافت نشد.")
            continue

        # Find raw video and audio in plan folder
        found_video: Optional[Path] = None
        found_audio: Optional[Path] = None

        for item in folder_path.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                if ext in video_exts and not found_video:
                    found_video = item
                elif ext in audio_exts and not found_audio:
                    found_audio = item

        # Copy Video
        if found_video:
            log(f"لینک ویدیو پلان {idx}: {found_video.name} -> {target_video_name}")
            shutil.copy2(found_video, target_video_path)
            results["linked_videos"].append(target_video_name)
        else:
            results["warnings"].append(f"ویدیو در پوشه {folder_name} یافت نشد.")

        # Handle Audio
        if found_audio:
            # If already wav, copy directly; else convert to standard wav via ffmpeg
            if found_audio.suffix.lower() == ".wav":
                shutil.copy2(found_audio, target_audio_path)
            else:
                extract_audio_with_ffmpeg(found_audio, target_audio_path, log_cb=log_cb)
            log(f"لینک صدا پلان {idx}: {found_audio.name} -> {target_audio_name}")
            results["linked_audios"].append(target_audio_name)
        elif found_video:
            # Extract audio track directly from video file
            log(f"استخراج صدا از ویدیوی پلان {idx} با FFmpeg...")
            if extract_audio_with_ffmpeg(found_video, target_audio_path, log_cb=log_cb):
                log(f"صدا با موفقیت از ویدیو استخراج و ذخیره شد: {target_audio_name}")
                results["linked_audios"].append(target_audio_name)
            else:
                results["warnings"].append(f"استخراج صدا از ویدیوی {folder_name} ناموفق بود.")
        else:
            results["warnings"].append(f"فایل صوتی برای پلان {idx} یافت نشد.")

    # Process Audio_BGM and Thumbnail Background
    bgm_folder = dropzone_dir / "Audio_BGM"
    if bgm_folder.exists():
        for item in bgm_folder.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                if ext in audio_exts and not results["bgm_linked"]:
                    dest_bgm = premiere_media / f"BGM_Track{ext}"
                    shutil.copy2(item, dest_bgm)
                    log(f"موزیک پس‌زمینه کپی شد: {item.name} -> {dest_bgm.name}")
                    results["bgm_linked"] = True
                elif ext in image_exts and not results["thumbnail_bg_linked"]:
                    dest_thumb = thumb_assets / "AI_Background.png"
                    shutil.copy2(item, dest_thumb)
                    log(f"تصویر پس‌زمینه تامنیل کپی شد: {item.name} -> AI_Background.png")
                    results["thumbnail_bg_linked"] = True

    return results


def deploy_project_templates(
    project_dir: Path,
    templates_base_dir: Path,
    job_id: str,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Copies mother templates into the project workspace:
    - Template_Reels.prproj -> 04_Premiere_Workspace/Project_OJ-{Job_ID}.prproj
    - Template_Thumb.ai -> 05_Thumbnail_Workspace/Thumbnail_OJ-{Job_ID}.ai
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    prproj_dest = project_dir / "04_Premiere_Workspace" / f"Project_OJ-{job_id}.prproj"
    ai_dest = project_dir / "05_Thumbnail_Workspace" / f"Thumbnail_OJ-{job_id}.ai"

    prproj_src = templates_base_dir / "Template_Reels.prproj"
    ai_src = templates_base_dir / "Template_Thumb.ai"

    copied_prproj = None
    copied_ai = None

    if prproj_src.exists():
        shutil.copy2(prproj_src, prproj_dest)
        log(f"پروژه پریمیر بر اساس قالب ایجاد شد: {prproj_dest.name}")
        copied_prproj = prproj_dest
    else:
        log(f"هشدار: فایل قالب پریمیر در {prproj_src} یافت نشد.")

    if ai_src.exists():
        shutil.copy2(ai_src, ai_dest)
        log(f"پروژه تامنیل بر اساس قالب ایجاد شد: {ai_dest.name}")
        copied_ai = ai_dest
    else:
        log(f"هشدار: فایل قالب ایلوستریتور در {ai_src} یافت نشد.")

    return copied_prproj, copied_ai


def open_file_or_folder(path: Path) -> bool:
    """
    Opens file or directory in Windows default associated application or Explorer.
    """
    try:
        os.startfile(str(path))
        return True
    except Exception as e:
        logger.error(f"Failed to open {path}: {e}")
        return False
