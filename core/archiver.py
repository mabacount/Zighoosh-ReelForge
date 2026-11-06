"""
Zighoosh ReelForge - Archiver Module (Step 4)
Verifies final exported video, cleans up duplicate dropzone files (optional),
moves project to permanent archive directory, and logs archive status.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def check_final_exports(project_dir: Path) -> List[Path]:
    """
    Checks if final rendered video or thumbnail files exist in 06_Final_Exports.
    """
    exports_dir = project_dir / "06_Final_Exports"
    if not exports_dir.exists():
        return []

    valid_exts = {".mp4", ".mov", ".mkv", ".avi", ".png", ".jpg"}
    found_exports = [
        f for f in exports_dir.iterdir()
        if f.is_file() and f.suffix.lower() in valid_exts and f.stat().st_size > 1024
    ]
    return found_exports


def cleanup_dropzone_duplicates(
    project_dir: Path,
    log_cb: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Deletes heavy raw files in 03_Raw_DropZone to optimize disk space,
    since they have already been linked to 04_Premiere_Workspace/Linked_Media.
    Returns bytes freed.
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    dropzone_dir = project_dir / "03_Raw_DropZone"
    if not dropzone_dir.exists():
        return 0

    bytes_freed = 0
    deleted_count = 0

    for plan_folder in dropzone_dir.iterdir():
        if plan_folder.is_dir():
            for item in plan_folder.iterdir():
                if item.is_file():
                    try:
                        size = item.stat().st_size
                        item.unlink()
                        bytes_freed += size
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Could not delete {item}: {e}")

    mb_freed = bytes_freed / (1024 * 1024)
    log(f"پاکسازی فایل‌های تکراری DropZone: {deleted_count} فایل حذف شد ({mb_freed:.1f} مگابایت آزاد شد).")
    return bytes_freed


def archive_project(
    project_dir: Path,
    archive_base_dir: Path,
    cleanup_raw: bool = True,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, Optional[Path]]:
    """
    Archives the project:
    1. Verifies exports.
    2. Cleans up raw duplicates if requested.
    3. Moves project folder to archive_base_dir.
    4. Writes archive manifest log.
    """
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        logger.info(msg)

    project_dir = project_dir.resolve()
    archive_base_dir = archive_base_dir.resolve()
    archive_base_dir.mkdir(parents=True, exist_ok=True)

    exports = check_final_exports(project_dir)
    if not exports:
        return False, "هیچ فایل خروجی رندرشده‌ای در پوشه 06_Final_Exports یافت نشد. لطفاً ابتدا ویدیوی نهایی را اکسپورت کنید.", None

    if cleanup_raw:
        cleanup_dropzone_duplicates(project_dir, log_cb=log_cb)

    # Move to archive directory
    target_dir = archive_base_dir / project_dir.name
    log(f"در حال انتقال پروژه به آرشیو: {target_dir}...")

    try:
        if target_dir.exists():
            log("پوشه پروژه در آرشیو از قبل وجود دارد. به‌روزرسانی اطلاعات...")
            for item in project_dir.iterdir():
                dest_item = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item)
            shutil.rmtree(project_dir, ignore_errors=True)
        else:
            shutil.move(str(project_dir), str(target_dir))

        # Write manifest entry
        manifest_file = archive_base_dir / "archive_registry.json"
        registry = []
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    registry = json.load(f)
            except Exception:
                registry = []

        registry.append({
            "project_name": target_dir.name,
            "archived_at": datetime.now().isoformat(),
            "path": str(target_dir),
            "exports": [e.name for e in exports],
        })

        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)

        log("پروژه با موفقیت بایگانی و در لاگ سراسری ثبت شد.")
        return True, f"پروژه با موفقیت به آرشیو منتقل شد:\n{target_dir}", target_dir

    except Exception as e:
        err_msg = f"خطا در انتقال پروژه به آرشیو: {e}"
        log(err_msg)
        return False, err_msg, None
