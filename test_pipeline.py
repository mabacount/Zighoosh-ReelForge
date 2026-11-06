"""
Zighoosh ReelForge - Comprehensive Pipeline Test Script
Tests all 4 steps end-to-end.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configure utf-8 for Windows console
if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from core.archiver import archive_project, check_final_exports
from core.json_processor import check_dropzone_status, process_gemini_json
from core.scraper import (
    PROMPT_JSON_EXPORTER,
    PROMPT_ROLE_EXPLORER,
    extract_job_info_from_url,
    fetch_job_details,
    get_combined_dossier_text,
    initialize_step1_workspace,
    save_deep_search_result,
)
from core.subtitle_engine import generate_all_plan_subtitles
from core.workspace_builder import (
    deploy_project_templates,
    link_and_rename_raw_media,
    migrate_to_active_workspace,
)

SAMPLE_URL = "https://iranoiljob.com/career-opportunities/14051/%DA%A9%D8%A7%D8%B1%D8%B4%D9%86%D8%A7%D8%B3%20%D8%A7%D8%B1%D8%B4%D8%AF%20%D8%A8%D9%87%D8%B1%D9%87%20%D8%A8%D8%B1%D8%AF%D8%A7%D8%B1%DB%8C%20%D9%86%D9%81%D8%AA%20%D9%88%20%DA%AF%D8%A7%D8%B2"

SAMPLE_GEMINI_JSON = {
    "job_id": "OJ-14051",
    "job_title": "کارشناس ارشد بهره‌برداری نفت و گاز",
    "company_name": "شرکت مهندسی نفت و گاز پتروسینا آریا",
    "music_generation_prompt": "Cinematic industrial ambient track, subtle deep bass pulse, modern corporate tech vibe, 95 BPM, inspiring and professional, no vocals",
    "thumbnail_data": {
        "bg_image_prompt": "Cinematic wide shot of a modern oil and gas production facility in south of Iran at golden hour, dramatic lighting, photorealistic, 8k, vertical 9:16",
        "hook_headline_text": "استخدام کارشناس ارشد بهره‌برداری!"
    },
    "plans": [
        {
            "plan_number": 1,
            "plan_type": "AVATAR_HOOK",
            "visual_prompt_flow": "A charismatic Iranian senior oil engineer in smart casual attire standing in a modern glass office overlooking an oil refinery, speaking directly to camera, shallow depth of field, 9:16 vertical",
            "tts_phonetic_text": "اَگه کارشِناسِ اَرشَدِ بَهره‌بَرداری هَستی و دُنبالِ یه فُرصَتِ ویژه می‌گَردی... این آگهی رو اَز دَست نَده!",
            "clean_subtitle_chunks": [
                "اگه کارشناس ارشد",
                "بهره‌برداری هستی",
                "و دنبال یه فرصت ویژه",
                "می‌گردی،",
                "این آگهی رو",
                "از دست نده!"
            ]
        },
        {
            "plan_number": 2,
            "plan_type": "BROLL_NARRATION",
            "visual_prompt_flow": "Close up of an industrial control panel and pressure gauges in an oil and gas processing plant, engineer hands adjusting valves, cinematic lighting",
            "tts_phonetic_text": "این شِرکَتِ مُعتَبَر نَفتی بَرایِ تَکمیلِ کادرِ فَنّیِ خودِش، به یِک مُتِخَصِّصِ با تَجرُبه نیاز داره.",
            "clean_subtitle_chunks": [
                "این شرکت معتبر نفتی",
                "برای تکمیل کادر فنی خودش،",
                "به یک متخصص با تجربه",
                "نیاز داره."
            ]
        }
    ]
}


def create_dummy_media_files(dropzone_dir: Path):
    """
    Creates small dummy video and audio files using ffmpeg for testing linking and forced alignment.
    """
    plan1_dir = dropzone_dir / "Plan_01_Hook_Avatar"
    plan2_dir = dropzone_dir / "Plan_02_Problem"
    bgm_dir = dropzone_dir / "Audio_BGM"

    plan1_dir.mkdir(parents=True, exist_ok=True)
    plan2_dir.mkdir(parents=True, exist_ok=True)
    bgm_dir.mkdir(parents=True, exist_ok=True)

    # 1. Plan 1: Video with embedded audio (3 seconds)
    v1_file = plan1_dir / "rush_avatar.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=3",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-c:a", "aac", str(v1_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 2. Plan 2: Video + Separate Audio
    v2_file = plan2_dir / "broll_clip.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=720x1280:d=3",
        "-c:v", "libx264", str(v2_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    a2_file = plan2_dir / "voiceover.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=520:duration=3",
        "-c:a", "pcm_s16le", str(a2_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 3. BGM audio
    bgm_file = bgm_dir / "ambient_music.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=4",
        "-c:a", "libmp3lame", str(bgm_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # 4. Thumbnail Background
    thumb_img = bgm_dir / "ai_bg_vertical.png"
    from PIL import Image
    im = Image.new("RGB", (720, 1280), color=(30, 40, 60))
    im.save(thumb_img)


def run_test():
    print("====================================================")
    print("▶ RUNNING END-TO-END PIPELINE TEST")
    print("====================================================")

    test_base = Path("./test_sandbox").resolve()
    shutil.rmtree(test_base, ignore_errors=True)
    test_base.mkdir(parents=True, exist_ok=True)

    downloads_dir = test_base / "Downloads"
    active_dir = test_base / "Active"
    archive_dir = test_base / "Archive"
    templates_dir = Path("./App_Templates").resolve()

    downloads_dir.mkdir(parents=True, exist_ok=True)
    active_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    # STEP 1: Ingest & Scrape
    print("\n--- [STEP 1: Scrape & Initialize Workspace] ---")
    job_id, slug = extract_job_info_from_url(SAMPLE_URL)
    print(f"Extracted Job ID: {job_id}, Slug: {slug}")
    assert job_id == "14051", "Job ID mismatch!"

    print("Fetching job details from IranOilJob API...")
    job_data = fetch_job_details(SAMPLE_URL)
    print(f"Job Title: {job_data.get('job_title')}")
    print(f"Company: {job_data.get('company_name')}")
    print(f"Logo URL: {job_data.get('logo_url')}")
    assert job_data.get("job_title"), "Job title should not be empty!"

    print("Initializing workspace directory in Downloads...")
    proj_dir, dirs = initialize_step1_workspace(job_data, downloads_dir)
    print(f"Project folder created at: {proj_dir}")
    assert (proj_dir / "01_Extracted_Data" / "job_details.json").exists()
    assert (proj_dir / "01_Extracted_Data" / "deep_search_prompt.txt").exists()
    assert (proj_dir / "05_Thumbnail_Workspace" / "Linked_Assets" / "Company_Logo.png").exists()
    print("Step 1 SUCCESS! ✅")

    # STEP 2: Deep Search Result & Combined Dossier
    print("\n--- [STEP 2: Deep Search Result & Combined Dossier] ---")
    mock_deep_result = """تحلیل بازار کار:
مهندسان بهره‌برداری نفت و گاز در مناطق جنوبی ایران با شرایط اقماری ۱۴-۱۴ فعالیت می‌کنند.
ابزارهای کلیدی: HYSYS, PIPESIM, استاندارد API 520/521."""
    res_file, combined_file = save_deep_search_result(proj_dir, mock_deep_result)
    print(f"Deep search result file: {res_file}")
    print(f"Combined dossier file: {combined_file}")
    assert res_file.exists(), "deep_search_result.md must exist!"
    assert combined_file.exists(), "combined_dossier_for_gemini.md must exist!"

    dossier_text = get_combined_dossier_text(proj_dir)
    assert "PIPESIM" in dossier_text, "Combined dossier must contain deep search result!"
    assert "مهندسی نفت و گاز پتروسینا آریا" in dossier_text, "Combined dossier must contain job details!"
    assert "@oiljob-role-explorer" in PROMPT_ROLE_EXPLORER, "Prompt role explorer format mismatch!"
    assert "@oiljob-json-exporter" in PROMPT_JSON_EXPORTER, "Prompt json exporter format mismatch!"
    print("Step 2 SUCCESS! ✅")

    # STEP 3: Process Gemini JSON
    print("\n--- [STEP 3: Brain & JSON Parser] ---")
    success, msg, brain_data = process_gemini_json(SAMPLE_GEMINI_JSON, proj_dir)
    print(f"JSON Process result: {success} ({msg})")
    assert success is True
    assert (proj_dir / "02_AI_Brain_JSON" / "gemini_master_output.json").exists()
    assert (proj_dir / "02_AI_Brain_JSON" / "flow_ready_script.txt").exists()
    assert (proj_dir / "02_AI_Brain_JSON" / "music_prompt.txt").exists()
    assert (proj_dir / "02_AI_Brain_JSON" / "thumbnail_bg_prompt.txt").exists()
    print("Step 3 SUCCESS! ✅")

    # Populate dummy media into DropZone
    print("\nCreating mock video/audio files in DropZone...")
    create_dummy_media_files(proj_dir / "03_Raw_DropZone")
    dz_status = check_dropzone_status(proj_dir)
    print("DropZone status check:")
    for k, v in dz_status.items():
        print(f"  {k}: video={v['has_video']}, audio={v['has_audio']}, ready={v['ready']}")
    assert dz_status["Plan_01_Hook_Avatar"]["has_video"] is True

    # STEP 4: Workspace Assembly, Subtitles & Templates
    print("\n--- [STEP 4: Assembly, Media Linking, Subtitles & Premiere] ---")
    print("1. Migrating from Downloads to Active Workspace...")
    proj_dir = migrate_to_active_workspace(proj_dir, active_dir)
    print(f"New project location: {proj_dir}")
    assert proj_dir.parent == active_dir

    print("2. Linking & renaming raw media...")
    link_results = link_and_rename_raw_media(proj_dir)
    print(f"Linked videos: {link_results['linked_videos']}")
    print(f"Linked audios: {link_results['linked_audios']}")
    print(f"BGM linked: {link_results['bgm_linked']}")
    print(f"Thumbnail BG linked: {link_results['thumbnail_bg_linked']}")

    assert (proj_dir / "04_Premiere_Workspace" / "Linked_Media" / "V_Plan_01.mp4").exists()
    assert (proj_dir / "04_Premiere_Workspace" / "Linked_Media" / "A_Plan_01.wav").exists()
    assert (proj_dir / "04_Premiere_Workspace" / "Linked_Media" / "V_Plan_02.mp4").exists()
    assert (proj_dir / "04_Premiere_Workspace" / "Linked_Media" / "A_Plan_02.wav").exists()

    print("3. Generating .srt subtitles...")
    sub_results = generate_all_plan_subtitles(proj_dir, model_size="base")
    print(f"Subtitle results: {sub_results}")
    srt1_file = proj_dir / "04_Premiere_Workspace" / "Subtitles" / "Sub_Plan_01.srt"
    assert srt1_file.exists()
    srt1_content = srt1_file.read_text(encoding="utf-8")
    print("Sample SRT Content:")
    print("-" * 30)
    print(srt1_content[:250])
    print("-" * 30)

    print("4. Deploying mother templates...")
    prproj, ai = deploy_project_templates(proj_dir, templates_dir, job_id="14051")
    print(f"Premiere file: {prproj}")
    print(f"Illustrator file: {ai}")
    assert prproj and prproj.exists()
    assert ai and ai.exists()
    print("Step 4 SUCCESS! ✅")

    # STEP 5: Verification & Archive
    print("\n--- [STEP 5: Verification & Archive] ---")
    # Simulate final render
    export_file = proj_dir / "06_Final_Exports" / "Reels_OJ-14051_Final_Render.mp4"
    export_file.write_bytes(b"dummy video render stream data" * 100)

    exports = check_final_exports(proj_dir)
    print(f"Found exports: {[e.name for e in exports]}")
    assert len(exports) == 1

    print("Archiving project...")
    ok, archive_msg, archived_path = archive_project(proj_dir, archive_dir, cleanup_raw=True)
    print(f"Archive status: {ok} -> {archived_path}")
    assert ok is True
    assert archived_path.exists()
    assert (archive_dir / "archive_registry.json").exists()
    print("Step 5 SUCCESS! ✅")

    print("\n====================================================")
    print("🎉 ALL 5 WORKFLOW STEPS PASSED WITH 100% SUCCESS!")
    print("====================================================")


if __name__ == "__main__":
    run_test()
