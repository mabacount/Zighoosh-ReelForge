"""
Zighoosh ReelForge - JSON Processor & Brain Module (Step 2)
Validates Gemini Master JSON output, splits into dedicated prompt files,
and prepares the DropZone workspaces for media ingest.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def clean_json_text(raw_text: str) -> str:
    """
    Cleans markdown code fences, leading/trailing notes from LLM output.
    """
    cleaned = raw_text.strip()
    # Remove markdown code blocks ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # If starting with { and ending with }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1].strip()
    
    return cleaned


def validate_gemini_json(data: Any) -> Tuple[bool, str]:
    """
    Validates that the parsed JSON conforms to the ReelForge specification.
    """
    if not isinstance(data, dict):
        return False, "داده ورودی باید یک شیء معتبر JSON باشد."

    if "plans" not in data or not isinstance(data["plans"], list) or len(data["plans"]) == 0:
        return False, "کلید 'plans' در فایل JSON یافت نشد یا لیست پلان‌ها خالی است."

    for i, plan in enumerate(data["plans"]):
        if not isinstance(plan, dict):
            return False, f"پلان شماره {i+1} ساختار معتبری ندارد."
        if "visual_prompt_flow" not in plan:
            return False, f"پلان شماره {i+1} فاقد فیلد 'visual_prompt_flow' است."
        if "tts_phonetic_text" not in plan:
            return False, f"پلان شماره {i+1} فاقد فیلد 'tts_phonetic_text' است."
        if "clean_subtitle_chunks" not in plan or not isinstance(plan["clean_subtitle_chunks"], list):
            return False, f"پلان شماره {i+1} فاقد آرایه 'clean_subtitle_chunks' است."

    return True, "ساختار JSON معتبر و منطبق بر استاندارد است."


def generate_flow_pipeline_manifest(
    gemini_data: Dict[str, Any],
    project_dir: Path,
    flow_config: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Generates the standard 02_AI_Brain_JSON/flow.json declarative pipeline manifest
    for automated multi-scene rendering via google-flow-cli.
    """
    plan_folder_map = {
        1: "Plan_01_Hook_Avatar",
        2: "Plan_02_Problem",
        3: "Plan_03_Company_Intro",
        4: "Plan_04_Requirements",
        5: "Plan_05_Benefits",
        6: "Plan_06_CTA_Avatar",
    }

    if flow_config is None:
        try:
            cfg_file = Path("config.json")
            if cfg_file.exists():
                with open(cfg_file, "r", encoding="utf-8") as f:
                    flow_config = json.load(f).get("flow_config", {})
        except Exception:
            flow_config = {}
    flow_config = flow_config or {}

    video_model = flow_config.get("default_video_model", "Veo 3.1 - Fast")
    avatar_model = flow_config.get("default_avatar_model", "Omni 1.1 Flash")
    resolution = flow_config.get("default_resolution", "720p")
    duration = flow_config.get("default_duration", "8s")
    aspect = flow_config.get("default_aspect", "9:16")
    timeout = int(flow_config.get("generation_timeout_sec", 300))

    scenes: List[Dict[str, Any]] = []
    for plan in gemini_data.get("plans", []):
        p_num = plan.get("plan_number", len(scenes) + 1)
        folder_name = plan_folder_map.get(p_num, f"Plan_{p_num:02d}")
        p_type = str(plan.get("plan_type", "")).upper()
        visual = plan.get("visual_prompt_flow", "").strip()
        phonetic = plan.get("tts_phonetic_text", "").strip()

        if "AVATAR" in p_type:
            scene_model = avatar_model
            prompt_str = f'{visual} Speaking in Persian: "{phonetic}"'
        else:
            scene_model = video_model
            prompt_str = visual

        scenes.append({
            "name": folder_name,
            "model": scene_model,
            "prompt": prompt_str,
            "output": f"../03_Raw_DropZone/{folder_name}/V_Plan_{p_num:02d}.mp4",
        })

    manifest = {
        "$schema": "https://flow.google/schema/v1.json",
        "version": "1.0.0",
        "name": str(gemini_data.get("job_id", "Flow_Project")),
        "defaults": {
            "mediaType": "video",
            "model": video_model,
            "resolution": resolution,
            "duration": duration,
            "aspect": aspect,
            "batches": "x1",
            "timeout": timeout,
        },
        "scenes": scenes,
    }

    brain_dir = project_dir / "02_AI_Brain_JSON"
    brain_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = brain_dir / "flow.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest_path


def process_gemini_json(
    json_input: str | dict,
    project_dir: Path,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Processes Gemini JSON, writes master JSON and individual prompt documents:
    - 02_AI_Brain_JSON/gemini_master_output.json
    - 02_AI_Brain_JSON/flow_ready_script.txt
    - 02_AI_Brain_JSON/music_prompt.txt
    - 02_AI_Brain_JSON/thumbnail_bg_prompt.txt
    """
    parsed: Dict[str, Any] = {}
    if isinstance(json_input, str):
        cleaned = clean_json_text(json_input)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            return False, f"خطا در خواندن فرمت JSON: {e}", {}
    elif isinstance(json_input, dict):
        parsed = json_input
    else:
        return False, "نوع داده ورودی نامعتبر است.", {}

    is_valid, msg = validate_gemini_json(parsed)
    if not is_valid:
        return False, msg, {}

    brain_dir = project_dir / "02_AI_Brain_JSON"
    brain_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save gemini_master_output.json
    master_file = brain_dir / "gemini_master_output.json"
    with open(master_file, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    # 2. Build flow_ready_script.txt
    flow_script_lines: List[str] = [
        "============================================================",
        f"ZIGHOOSH REELFORGE | GOOGLE FLOW PRODUCTION SCRIPT",
        f"پروژه: {parsed.get('job_id', '')} - {parsed.get('job_title', '')}",
        f"شرکت: {parsed.get('company_name', '')}",
        "============================================================\n",
    ]

    for plan in parsed.get("plans", []):
        p_num = plan.get("plan_number", 1)
        p_type = plan.get("plan_type", f"PLAN_{p_num}")
        visual = plan.get("visual_prompt_flow", "").strip()
        phonetic = plan.get("tts_phonetic_text", "").strip()
        chunks = plan.get("clean_subtitle_chunks", [])

        flow_script_lines.append(f"------------------------------------------------------------")
        flow_script_lines.append(f"▶ PLAN {p_num:02d}: [{p_type}]")
        flow_script_lines.append(f"------------------------------------------------------------")
        flow_script_lines.append("🎬 GOOGLE FLOW VISUAL PROMPT (پرامپت ویدیو/تصویر عمودی):")
        flow_script_lines.append(visual)
        flow_script_lines.append("\n🎙️ TTS PHONETIC SCRIPT (متن گفتار با اعراب‌گذاری کامل برای ویس):")
        flow_script_lines.append(phonetic)
        flow_script_lines.append("\n📝 SUBTITLE CHUNKS (قطعات زیرنویس ۳-۴ کلمه‌ای):")
        for c in chunks:
            flow_script_lines.append(f"  • {c}")
        flow_script_lines.append("\n")

    flow_script_path = brain_dir / "flow_ready_script.txt"
    with open(flow_script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(flow_script_lines))

    # 3. Build music_prompt.txt
    music_prompt = parsed.get("music_generation_prompt", "")
    music_path = brain_dir / "music_prompt.txt"
    with open(music_path, "w", encoding="utf-8") as f:
        f.write(music_prompt.strip() + "\n")

    # 4. Build thumbnail_bg_prompt.txt
    thumb_data = parsed.get("thumbnail_data", {})
    thumb_prompt = thumb_data.get("bg_image_prompt", "")
    hook_text = thumb_data.get("hook_headline_text", "")
    thumb_content = (
        f"🖼️ THUMBNAIL BACKGROUND PROMPT (پرامپت تصویر پس‌زمینه عمودی ۹:۱۶):\n"
        f"{thumb_prompt}\n\n"
        f"🎯 HOOK HEADLINE TEXT (متن تیتر جذاب روی کاور):\n"
        f"{hook_text}\n"
    )
    thumb_path = brain_dir / "thumbnail_bg_prompt.txt"
    with open(thumb_path, "w", encoding="utf-8") as f:
        f.write(thumb_content)

    # 5. Generate declarative Google Flow manifest (02_AI_Brain_JSON/flow.json)
    generate_flow_pipeline_manifest(parsed, project_dir)

    # 6. Ensure DropZone folders exist
    dropzone_dir = project_dir / "03_Raw_DropZone"
    dropzone_dir.mkdir(parents=True, exist_ok=True)
    plan_names = [
        "Plan_01_Hook_Avatar",
        "Plan_02_Problem",
        "Plan_03_Company_Intro",
        "Plan_04_Requirements",
        "Plan_05_Benefits",
        "Plan_06_CTA_Avatar",
        "Audio_BGM",
    ]
    for p in plan_names:
        (dropzone_dir / p).mkdir(parents=True, exist_ok=True)

    return True, "فایل‌های اسکریپت و پرامپت‌ها با موفقیت در پوشه 02_AI_Brain_JSON تولید شدند.", parsed


def check_dropzone_status(project_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Checks the status of each Plan folder in 03_Raw_DropZone:
    Returns dict: {
        'Plan_01_Hook_Avatar': {'video': bool, 'audio': bool, 'ready': bool, 'files': list[str]},
        ...
    }
    """
    dropzone = project_dir / "03_Raw_DropZone"
    plan_folders = [
        ("Plan_01_Hook_Avatar", "پلان ۱ (قلاب آواتار)"),
        ("Plan_02_Problem", "پلان ۲ (چالش/بی‌رول)"),
        ("Plan_03_Company_Intro", "پلان ۳ (معرفی شرکت)"),
        ("Plan_04_Requirements", "پلان ۴ (شرایط احراز)"),
        ("Plan_05_Benefits", "پلان ۵ (مزایا و حقوق)"),
        ("Plan_06_CTA_Avatar", "پلان ۶ (فراخوان اقدام)"),
        ("Audio_BGM", "موزیک پس‌زمینه و تصویر تامنیل"),
    ]

    status: Dict[str, Dict[str, Any]] = {}
    video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    audio_exts = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}

    for folder_name, title in plan_folders:
        folder_path = dropzone / folder_name
        has_video = False
        has_audio = False
        has_image = False
        files: List[str] = []

        if folder_path.exists():
            for f in folder_path.iterdir():
                if f.is_file():
                    ext = f.suffix.lower()
                    files.append(f.name)
                    if ext in video_exts:
                        has_video = True
                    if ext in audio_exts:
                        has_audio = True
                    if ext in image_exts:
                        has_image = True

        if folder_name == "Audio_BGM":
            ready = has_audio or has_image
        else:
            # Plan is ready if it has video AND audio, OR if it has a video that might contain audio
            ready = has_video and (has_audio or True)

        status[folder_name] = {
            "title": title,
            "path": folder_path,
            "has_video": has_video,
            "has_audio": has_audio,
            "has_image": has_image,
            "ready": ready,
            "files": files,
        }

    return status
