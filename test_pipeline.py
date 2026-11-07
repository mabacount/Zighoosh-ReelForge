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
    assert (proj_dir / "02_AI_Brain_JSON" / "flow.json").exists()
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

    # STEP 6: Google Flow Automation & Manifest Unit Test
    test_flow_automator_and_manifest()

    print("\n====================================================")
    print("🎉 ALL 6 WORKFLOW STEPS PASSED WITH 100% SUCCESS!")
    print("====================================================")


SAMPLE_GEMINI_JSON_6_PLANS = {
    "job_id": "OJ-14051",
    "job_title": "کارشناس ارشد بهره‌برداری نفت و گاز",
    "company_name": "شرکت مهندسی نفت و گاز پتروسینا آریا",
    "music_generation_prompt": "Cinematic industrial ambient track, subtle deep bass pulse, 95 BPM",
    "thumbnail_data": {
        "bg_image_prompt": "Cinematic wide shot of an oil refinery in southern Iran at golden hour, 9:16 vertical",
        "hook_headline_text": "استخدام مهندس ارشد نفت و گاز!"
    },
    "plans": [
        {
            "plan_number": 1,
            "plan_type": "AVATAR_HOOK",
            "visual_prompt_flow": "Charismatic Iranian senior oil engineer in modern office, vertical 9:16",
            "tts_phonetic_text": "اَگه کارشِناسِ اَرشَدِ بَهره‌بَرداری هَستی، این آگهی رو اَز دَست نَده!",
            "clean_subtitle_chunks": ["اگه کارشناس ارشد", "بهره‌برداری هستی", "از دست نده"]
        },
        {
            "plan_number": 2,
            "plan_type": "BROLL_NARRATION",
            "visual_prompt_flow": "Industrial control panel and gauges in gas plant, cinematic lighting",
            "tts_phonetic_text": "این شرکت معتبر نفتی برای تکمیل کادر فنی خود نیاز به متخصص دارد.",
            "clean_subtitle_chunks": ["این شرکت معتبر نفتی", "به متخصص نیاز دارد"]
        },
        {
            "plan_number": 3,
            "plan_type": "COMPANY_INTRO",
            "visual_prompt_flow": "Modern engineering office building exterior with company logo",
            "tts_phonetic_text": "شرکت پتروسینا آریا با پروژه‌های عظیم فراساحلی و خشکی.",
            "clean_subtitle_chunks": ["شرکت پتروسینا آریا", "پروژه‌های عظیم"]
        },
        {
            "plan_number": 4,
            "plan_type": "REQUIREMENTS",
            "visual_prompt_flow": "Engineer analyzing flow simulation software on monitors",
            "tts_phonetic_text": "حداقل پنج سال سابقه و تسلط کامل بر نرم‌افزارهای پایپ‌سیم و هایسیس.",
            "clean_subtitle_chunks": ["حداقل پنج سال سابقه", "تسلط بر هایسیس"]
        },
        {
            "plan_number": 5,
            "plan_type": "BENEFITS",
            "visual_prompt_flow": "Comfortable accommodation quarters and industrial helicopter landing",
            "tts_phonetic_text": "شرایط کاری اقماری، بیمه تکمیلی، اسکان و حقوق رقابتی.",
            "clean_subtitle_chunks": ["شرایط اقماری", "حقوق رقابتی"]
        },
        {
            "plan_number": 6,
            "plan_type": "CTA_AVATAR",
            "visual_prompt_flow": "Iranian engineer holding tablet gesturing to apply now, vertical 9:16",
            "tts_phonetic_text": "همین حالا وارد سایت ایران اویل جاب شو و رزومه‌ت رو بفرست!",
            "clean_subtitle_chunks": ["همین حالا وارد سایت شو", "رزومه‌ت رو بفرست"]
        }
    ]
}


def test_flow_automator_and_manifest():
    print("\n--- [STEP 6: AI Brain & 6-Plan Manifest Unit Test] ---")

    # 1. Test processing 6-plan JSON & manifest generation
    print("1. Testing json_processor & flow.json manifest generation for 6 plans...")
    test_flow_dir = Path("./test_sandbox/Flow_Test_Project").resolve()
    shutil.rmtree(test_flow_dir, ignore_errors=True)
    test_flow_dir.mkdir(parents=True, exist_ok=True)

    ok, msg, parsed = process_gemini_json(SAMPLE_GEMINI_JSON_6_PLANS, test_flow_dir)
    assert ok is True, f"process_gemini_json failed: {msg}"

    flow_json_path = test_flow_dir / "02_AI_Brain_JSON" / "flow.json"
    assert flow_json_path.exists(), "02_AI_Brain_JSON/flow.json must be created!"
    print(f"flow.json created at: {flow_json_path}")

    # 3. Validate flow.json structure
    with open(flow_json_path, "r", encoding="utf-8") as f:
        flow_data = json.load(f)

    print("3. Validating flow.json schema, defaults, and scenes...")
    assert "$schema" in flow_data, "Missing '$schema' key in flow.json!"
    assert "defaults" in flow_data, "Missing 'defaults' key in flow.json!"
    assert "scenes" in flow_data, "Missing 'scenes' key in flow.json!"
    assert flow_data["name"] == "OJ-14051", f"Unexpected manifest name: {flow_data.get('name')}"

    scenes = flow_data["scenes"]
    assert len(scenes) == 6, f"Expected 6 scenes, found {len(scenes)}!"

    expected_folders = [
        "Plan_01_Hook_Avatar",
        "Plan_02_Problem",
        "Plan_03_Company_Intro",
        "Plan_04_Requirements",
        "Plan_05_Benefits",
        "Plan_06_CTA_Avatar",
    ]

    for idx, (scene, expected_folder) in enumerate(zip(scenes, expected_folders), start=1):
        assert scene["name"] == expected_folder, f"Scene {idx} name mismatch: {scene['name']} != {expected_folder}"
        expected_output = f"../03_Raw_DropZone/{expected_folder}/V_Plan_{idx:02d}.mp4"
        assert scene["output"] == expected_output, f"Scene {idx} output mismatch: {scene['output']} != {expected_output}"

        # Verify avatar vs broll model & prompt
        if idx in (1, 6):
            assert scene["model"] == "Omni 1.1 Flash", f"Avatar scene {idx} should use Omni 1.1 Flash, got {scene['model']}"
            assert 'Speaking in Persian:' in scene["prompt"], f"Avatar scene {idx} prompt should include Persian speech directive"
        else:
            assert scene["model"] == "Veo 3.1 - Fast", f"Scene {idx} should use Veo 3.1 - Fast, got {scene['model']}"

    print("All 6 scenes in flow.json verified with correct DropZone output paths and models! ✅")
    print("Step 6 SUCCESS! ✅")


if __name__ == "__main__":
    run_test()
