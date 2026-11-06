"""
Zighoosh ReelForge - Scraper & Extractor Module (Step 1)
Extracts IranOilJob job posting data, downloads company logo,
builds Gemini Deep Research prompt and initializes the project workspace.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def extract_job_info_from_url(url: str) -> Tuple[str, str]:
    """
    Extracts (Job_ID, Decoded_Slug) from IranOilJob URL.
    Pattern: /career-opportunities/(\\d+)/(.*)
    """
    clean_url = url.strip()
    match = re.search(r"/career-opportunities/(\d+)(?:/([^/?#]+))?", clean_url)
    if not match:
        # Fallback: check if URL contains any numeric id
        num_match = re.search(r"(\d{4,7})", clean_url)
        if num_match:
            job_id = num_match.group(1)
            slug = "Job"
            return job_id, slug
        raise ValueError("شناسه آگهی در لینک وارد شده یافت نشد. لینک باید شامل شناسه فرصت شغلی باشد.")

    job_id = match.group(1)
    raw_slug = match.group(2) or ""
    decoded_slug = urllib.parse.unquote(raw_slug).strip()
    if not decoded_slug:
        decoded_slug = f"Job_{job_id}"

    return job_id, decoded_slug


def sanitize_filename(name: str, max_length: int = 60) -> str:
    """
    Sanitizes string for Windows directory/file names.
    Removes invalid characters: \\ / : * ? " < > |
    """
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._- ")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip("._- ")
    return cleaned or "Project"


# Mapping tables for IranOilJob API enums
EDUCATION_LEVEL_MAP = {
    10: "حداقل زیر دیپلم",
    20: "حداقل سیکل",
    30: "حداقل دیپلم",
    40: "حداقل کاردانی / فوق دیپلم",
    50: "حداقل کارشناسی (لیسانس)",
    60: "حداقل کارشناسی ارشد (فوق لیسانس)",
    70: "حداقل دکتری",
}

JOB_TYPE_MAP = {
    10: "تمام وقت",
    20: "پاره وقت",
    30: "دورکاری",
    40: "مشاوره‌ای",
    50: "اقماری / روتیشن",
}

GENDER_MAP = {
    10: "آقا",
    20: "خانم",
    30: "تفاوتی ندارد / آقا یا خانم",
}


def format_mastery_level(level: Optional[int]) -> str:
    """Returns human-readable Persian mastery label based on percentage."""
    if not level:
        return "آشنایی اولیه"
    if level >= 85:
        return "تسلط کامل و پیشرفته"
    if level >= 65:
        return "تسلط خوب"
    if level >= 40:
        return "تسلط متوسط"
    return "آشنایی مقدماتی"


def fetch_job_details(url: str, timeout: int = 12) -> Dict[str, Any]:
    """
    Fetches job details from iranoiljob.com using the official API or HTML fallback.
    Extracts all fields: skills, educations, experience, job type, company profile, and full description.
    """
    job_id, decoded_slug = extract_job_info_from_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Referer": "https://iranoiljob.com/",
    }

    api_url = f"https://api.iranoiljob.com/api/fa/JobVacancyAd/GetById?id={job_id}"
    data: Dict[str, Any] = {
        "job_id": job_id,
        "job_code": f"OJ-{job_id}",
        "url": url,
        "job_title": decoded_slug.replace("_", " "),
        "company_name": "",
        "company_en_title": "",
        "company_description": "",
        "company_services": "",
        "location": "",
        "state": "",
        "city": "",
        "category_title": "",
        "job_type_title": "قید نشده",
        "gender_title": "تفاوتی ندارد",
        "experience_text": "بدون محدودیت سابقه / سابقه مرتبط",
        "site_type": "",
        "skills": [],
        "skills_formatted": "",
        "educations": [],
        "educations_formatted": "",
        "requirements": "",
        "duties": "",
        "full_description_clean": "",
        "logo_url": "",
        "raw_json": {},
    }

    api_succeeded = False
    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            job_json = resp.json()
            data["raw_json"] = job_json
            data["job_title"] = job_json.get("title") or data["job_title"]

            # Category
            data["category_title"] = job_json.get("occupationCategoryRefTitle") or job_json.get("occupationTitle") or ""

            # Job Type and Conditions
            job_type_code = job_json.get("jobType")
            data["job_type_title"] = JOB_TYPE_MAP.get(job_type_code, "تمام وقت")
            if job_json.get("isLandOperationalSite") is False:
                data["site_type"] = "سایت عملیاتی فراساحل / دریا (Offshore)"
            elif job_json.get("isLandOperationalSite") is True:
                data["site_type"] = "سایت عملیاتی خشکی (Onshore)"

            # Gender
            gender_code = job_json.get("acceptableGender")
            data["gender_title"] = GENDER_MAP.get(gender_code, "تفاوتی ندارد")

            # Experience Range
            exp_from = job_json.get("experienceFrom")
            exp_to = job_json.get("experienceTo")
            min_exp = job_json.get("minExperiances")
            if exp_to and exp_to > 0:
                data["experience_text"] = f"{exp_from or 0} تا {exp_to} سال سابقه کار مرتبط"
            elif min_exp and min_exp > 0:
                data["experience_text"] = f"حداقل {min_exp} سال سابقه کار مرتبط"

            # -------------------------------------------------------------
            # Extract Skills (jobVacancyAdSkills)
            # -------------------------------------------------------------
            skills_raw = job_json.get("jobVacancyAdSkills") or []
            skills_list = []
            skills_formatted_lines = []
            for s in skills_raw:
                s_title = s.get("title") or s.get("skillRefTitle") or ""
                if not s_title.strip():
                    continue
                m_level = s.get("masteryLevel") or 50
                m_label = format_mastery_level(m_level)
                is_soft = s.get("isSoftSkill", False)
                desc = (s.get("description") or "").strip()

                s_dict = {
                    "title": s_title.strip(),
                    "mastery_level": m_level,
                    "mastery_label": m_label,
                    "is_soft_skill": is_soft,
                    "description": desc,
                }
                skills_list.append(s_dict)

                line = f"• {s_title} [سطح تسلط: {m_label} ({m_level}%)]"
                if desc:
                    line += f" - توضیحات: {desc}"
                skills_formatted_lines.append(line)

            data["skills"] = skills_list
            data["skills_formatted"] = "\n".join(skills_formatted_lines)

            # -------------------------------------------------------------
            # Extract Educations (jobVacancyAdEducations)
            # -------------------------------------------------------------
            edus_raw = job_json.get("jobVacancyAdEducations") or []
            edus_list = []
            edus_formatted_lines = []
            for e in edus_raw:
                e_title = e.get("title") or ""
                if not e_title.strip():
                    continue
                e_lvl_code = e.get("educationLevel")
                lvl_label = EDUCATION_LEVEL_MAP.get(e_lvl_code, "مدرک معتبر دانشگاهی")

                e_dict = {
                    "title": e_title.strip(),
                    "level_code": e_lvl_code,
                    "level_label": lvl_label,
                }
                edus_list.append(e_dict)
                edus_formatted_lines.append(f"• {e_title.strip()} ({lvl_label})")

            data["educations"] = edus_list
            data["educations_formatted"] = "\n".join(edus_formatted_lines)

            # Company details
            company = job_json.get("company") or {}
            data["company_name"] = company.get("title") or ""
            data["company_en_title"] = company.get("enTitle") or ""
            data["company_description"] = (company.get("description") or "").strip()
            data["company_services"] = (company.get("productAndServices") or "").strip()

            logo_rel = company.get("logo")
            if logo_rel:
                if logo_rel.startswith("http"):
                    data["logo_url"] = logo_rel
                else:
                    data["logo_url"] = f"https://api.iranoiljob.com/{logo_rel.lstrip('/')}"

            # Location
            state = job_json.get("stateTitle") or ""
            city = job_json.get("cityTitle") or ""
            data["state"] = state
            data["city"] = city
            data["location"] = f"{state} - {city}".strip(" -")

            # Parse HTML description
            html_desc = job_json.get("jobDescription") or ""
            if html_desc:
                soup = BeautifulSoup(html_desc, "html.parser")
                clean_text = soup.get_text(separator="\n").strip()
                data["full_description_clean"] = clean_text

                # Split requirements and duties if present
                lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
                req_idx = -1
                duty_idx = -1
                for i, l in enumerate(lines):
                    if "شرایط احراز" in l:
                        req_idx = i
                    elif "شرح وظایف" in l or "وظایف" in l or "توضیحات" in l:
                        duty_idx = i

                if req_idx != -1 and duty_idx != -1 and duty_idx > req_idx:
                    data["requirements"] = "\n".join(lines[req_idx:duty_idx])
                    data["duties"] = "\n".join(lines[duty_idx:])
                elif req_idx != -1:
                    data["requirements"] = "\n".join(lines[req_idx:])
                    data["duties"] = "\n".join(lines[:req_idx])
                else:
                    data["duties"] = clean_text

            api_succeeded = True
    except Exception as e:
        logger.warning(f"API fetch failed: {e}")

    # Fallback to direct HTML page scraping if API did not succeed or returned empty
    if not api_succeeded or not data["company_name"]:
        try:
            page_resp = requests.get(url, headers=headers, timeout=timeout)
            if page_resp.status_code == 200:
                soup = BeautifulSoup(page_resp.text, "html.parser")
                if not data["job_title"] and soup.title:
                    data["job_title"] = soup.title.get_text().split("-")[0].strip()
        except Exception as e:
            logger.warning(f"HTML scraping fallback failed: {e}")

    return data


def create_placeholder_logo(output_path: Path, company_name: str = "Company") -> None:
    """
    Generates a minimalist Apple/Google styled high-res logo placeholder.
    Dark slate background with elegant monogram and accent border.
    """
    size = (600, 600)
    img = Image.new("RGBA", size, color=(24, 25, 32, 255))
    draw = ImageDraw.Draw(img)

    # Rounded card rect / subtle border
    draw.rounded_rectangle(
        [(24, 24), (576, 576)],
        radius=48,
        outline=(56, 189, 248, 180),
        width=6,
    )

    # Monogram initial
    initial = (company_name.strip()[:1] if company_name else "Z").upper()
    
    # Try loading standard Windows system fonts or default
    font = None
    for font_name in ["segoeui.ttf", "tahoma.ttf", "arial.ttf"]:
        try:
            font = ImageFont.truetype(font_name, 190)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initial, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((600 - w) / 2, (560 - h) / 2), initial, font=font, fill=(245, 247, 250, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")


def download_company_logo(logo_url: str, target_paths: List[Path], company_name: str = "") -> bool:
    """
    Downloads company logo from URL and writes to multiple target paths.
    If download fails or URL is empty, generates a minimalist placeholder logo.
    """
    success = False
    if logo_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(logo_url, headers=headers, timeout=12)
            if resp.status_code == 200 and len(resp.content) > 100:
                for target in target_paths:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(target, "wb") as f:
                        f.write(resp.content)
                success = True
        except Exception as e:
            logger.warning(f"Error downloading logo from {logo_url}: {e}")

    if not success:
        for target in target_paths:
            target.parent.mkdir(parents=True, exist_ok=True)
            create_placeholder_logo(target, company_name=company_name)
        success = True

    return success


DEEP_SEARCH_PROMPT_TEMPLATE = """شما یک پژوهشگر ارشد بازار کار، استراتژیست منابع انسانی و کارشناس عملیاتی صنایع نفت، گاز، پتروشیمی و انرژی در حوزه ایران و خاورمیانه هستید.

هدف پژوهش:
بر اساس مشخصات موقعیت شغلی ارائهشده در بخش دوم، یک «سند جامع کالبدشکافی تخصصی و تحلیل بازار کار» تهیه کنید. این تحلیل باید با نگاهی میدانی، عمیق و فارغ از تعارفات اداری نگاشته شود تا ابعاد واقعی این موقعیت شغلی را به صورت شفاف و مستند مشخص کند.

گزارش شما باید به طور دقیق شامل پنج محور زیر باشد:

۱. کالبدشکافی فنی، ابزارها و جریان کاری (Technical & Operational Workflow):
- شرح فرآیند واقعی کار در این جایگاه: وظایف کلیدی روزمره، تصمیمگیریهای حساس، و گلوگاههای اصلی شغل (چه در محیط ستادی/آفیسی، چه در خطوط تولید و کارخانه، و چه در عملیات میدانی/سر چاه/کمپ).
- ابزارها و پیشنیازهای مهارتی: نرمافزارهای تخصصی، تجهیزات و قطعات کاری، سامانههای اداری/عملیاتی، و استانداردهای حاکم بر این سمت (نظیر API, ASME, IPS, NACE, PMBOK یا رویههای ویژه شرکتهای کارفرما).
- ارتباطات سازمانی و زنجیره پاسخگویی: این متخصص ورودی کار خود را از چه واحدهایی میگیرد، خروجی کارش را به چه کسانی تحویل میدهد و در لحظات بحرانی مستقیماً با چه عناوینی در تعامل است؟

۲. شرایط زیستی، ارگونومی و واقعیت محیط کار (Lifestyle & Work Environment):
- ساختار کاری حاکم بر موقعیت: نظام اقماری و روتیشن (نظیر ۱۴-۱۴، ۲۱-۲۱، ۲۸-۲۸) یا ساعات اداری مرسوم و ماموریتهای دورهای.
- وضعیت اقامت و محیط زیست حرفهای: مقتضیات فیزیکی و روانی محیط کاری (فضای ایزوله دریا/بارج/شناور، کابینهای دکل، شرایط استقرار در کمپ، یا محیطهای پرتنش آفیسی و جلسات کارفرمایی).
- چالشهای واقعی و فرسودگیهای موقعیت: فشارهای جوی و آبوهوایی، مواجهه با ریسکهای ایمنی و فرایندی، شیفتکاری شبانه، یا بار کاری و تعهدات قراردادی.

۳. ادبیات تخصصی، اصطلاحات صنفی و زبان رایج (Industry Slang & Terminology):
- استخراج واژگان تخصصی، مخففها، کدهای استاندارد و کلمات عامیانه مرسوم که صرفاً فعالان باسابقه این موقعیت در گفتگوهای کاری از آنها استفاده میکنند (زبانی که تسلط گوینده بر واقعیت این شغل را نشان میدهد).

۴. جایگاه کارفرما، ابعاد پروژه و اعتبار سازمانی (Company & Project Intelligence):
- نوع فعالیت شرکت در زنجیره ارزش (کارفرمای اصلی/E&P، پیمانکار عمومی/EPC، شرکت خدمات جانبی، بازرگانی، مهندسی مشاور، یا بهرهبرداری).
- وضعیت اعتبار کارفرما و مقتضیات پروژههای جاری در منطقه قیدشده در آگهی.
- فرهنگ سازمانی، انضباط مالی در پرداخت دستمزد و مزایا، وضعیت کمپها و خدمات رفاهی بر اساس تجربه و دیدگاه نیروهای شاغل در این مجموعه.

۵. بنچمارک دستمزد، بازار کار و انگیزههای مهاجرت شغلی (Compensation & Talent Market):
- وضعیت عرضه و تقاضای این مهارت در بازار کار فعلی ایران: میزان کمیابی یا وفور نیروی ماهر، و موانع ورود به این سمت.
- میانگین دستمزد، نحوه محاسبه دریافتی (حقوق ثابت، حق ماموریت، پاداشهای عملیاتی، فوقالعاده کار در مناطق سخت) در شرکتهای خصوصی و دولتی همرده در ایران.
- بنچمارک منطقهای (خلیج فارس / GCC نظیر امارات، عمان، قطر، عربستان و عراق): وضعیت دستمزد دلاری، میزان تمایل به جذب نیروی متخصص ایرانی در این جایگاه، و پتانسیل جهش شغلی به بازارهای بینالمللی.
- روانشناسی و نقاط اهرم: بزرگترین دغدغهها و نارضایتیهای متخصصان این رده در شرکتهای دیگر، و دلایلی که میتواند فرد را قانع به تغییر شغل و پذیرش این فرصت کاری کند.

---
اطلاعات استخراجشده از آگهی شغلی:
- شناسه آگهی: {job_id}
- عنوان موقعیت شغلی: {job_title}
- نام شرکت / کارفرما: {company_name}
- محل خدمت / منطقه عملیاتی: {job_location}

شرح شغل، شرایط احراز و جزئیات مندرج در آگهی:
{job_requirements_and_duties}
---
"""


def build_deep_search_prompt(job_data: Dict[str, Any]) -> str:
    """
    Creates an in-depth research and intelligence prompt for Gemini Deep Research.
    Focuses strictly on operational realities, industry workflows, skills, and labor market benchmarking.
    """
    raw_job_id = str(job_data.get("job_id", "0000"))
    job_code = job_data.get("job_code") or (raw_job_id if raw_job_id.startswith("OJ-") else f"OJ-{raw_job_id}")
    title = job_data.get("job_title", "فرصت شغلی")
    company = job_data.get("company_name", "نامشخص / محرمانه")
    company_en = job_data.get("company_en_title", "")
    location = job_data.get("location") or job_data.get("city") or "قید نشده در آگهی"

    # Assemble comprehensive job dossier
    dossier_sections: List[str] = []

    # 1. Skills section
    skills_text = job_data.get("skills_formatted", "").strip()
    if skills_text:
        dossier_sections.append(f"■ مهارت‌های تخصصی، فردی و نرم‌افزاری مورد نیاز (Skills):\n{skills_text}")
    else:
        dossier_sections.append("■ مهارت‌های تخصصی، فردی و نرم‌افزاری مورد نیاز (Skills):\n(در فرم آگهی مهارت مجزایی تگ نشده و مهارت‌های کلیدی در متن شرح وظایف درج شده‌اند)")

    # 2. Education section
    edus_text = job_data.get("educations_formatted", "").strip()
    if edus_text:
        dossier_sections.append(f"■ مدارک و رشته‌های تحصیلی مجاز (Education & Majors):\n{edus_text}")

    # 3. Work Conditions & Requirements
    cond_lines = []
    if job_data.get("category_title"):
        cond_lines.append(f"- حوزه و رسته شغلی: {job_data.get('category_title')}")
    if job_data.get("experience_text"):
        cond_lines.append(f"- سابقه کار مورد نیاز: {job_data.get('experience_text')}")
    if job_data.get("job_type_title"):
        cond_lines.append(f"- نوع همکاری و نظام شیفت: {job_data.get('job_type_title')}")
    if job_data.get("gender_title"):
        cond_lines.append(f"- جنسیت مورد پذیرش: {job_data.get('gender_title')}")
    if job_data.get("site_type"):
        cond_lines.append(f"- موقعیت عملیاتی: {job_data.get('site_type')}")

    if cond_lines:
        dossier_sections.append("■ مشخصات سازمانی، سابقه کار و شرایط احراز:\n" + "\n".join(cond_lines))

    # 4. Job Description & Duties
    clean_desc = job_data.get("full_description_clean", "").strip()
    requirements = job_data.get("requirements", "").strip()
    duties = job_data.get("duties", "").strip()
    desc_content = clean_desc or ("\n\n".join([p for p in [requirements, duties] if p])) or "در متن آگهی توضیحات بیشتری درج نشده است."
    dossier_sections.append(f"■ شرح وظایف، جزئیات و متن کامل آگهی (Job Description & Duties):\n{desc_content}")

    # 5. Company Background & Projects
    company_lines = []
    if company:
        name_str = f"{company} ({company_en})" if company_en else company
        company_lines.append(f"- نام رسمی کارفرما: {name_str}")
    if job_data.get("company_description"):
        company_lines.append(f"- سوابق و زمینه فعالیت: {job_data.get('company_description')}")
    if job_data.get("company_services"):
        company_lines.append(f"- پروژه‌ها، محصولات و خدمات: {job_data.get('company_services')}")

    if company_lines:
        dossier_sections.append("■ مشخصات و پیشینه شرکت کارفرما (Company Profile):\n" + "\n".join(company_lines))

    compiled_requirements = "\n\n".join(dossier_sections)

    prompt = DEEP_SEARCH_PROMPT_TEMPLATE.format(
        job_id=job_code,
        job_title=title,
        company_name=company,
        job_location=location,
        job_requirements_and_duties=compiled_requirements,
    )
    return prompt.strip()


def initialize_step1_workspace(
    job_data: Dict[str, Any],
    base_dir: Path,
) -> Tuple[Path, Dict[str, Path]]:
    """
    Creates standard project directory blueprint:
    📁 OJ-{Job_ID}_{Slug}/
    ├── 📁 01_Extracted_Data/
    ├── 📁 02_AI_Brain_JSON/
    ├── 📁 03_Raw_DropZone/
    ├── 📁 04_Premiere_Workspace/
    ├── 📁 05_Thumbnail_Workspace/
    └── 📁 06_Final_Exports/
    """
    job_id = job_data.get("job_id", "0000")
    raw_slug = job_data.get("job_title", "Job")
    safe_slug = sanitize_filename(raw_slug, max_length=40)
    folder_name = f"OJ-{job_id}_{safe_slug}"

    project_dir = base_dir / folder_name
    project_dir.mkdir(parents=True, exist_ok=True)

    dirs = {
        "01_Extracted_Data": project_dir / "01_Extracted_Data",
        "02_AI_Brain_JSON": project_dir / "02_AI_Brain_JSON",
        "03_Raw_DropZone": project_dir / "03_Raw_DropZone",
        "04_Premiere_Workspace": project_dir / "04_Premiere_Workspace",
        "05_Thumbnail_Workspace": project_dir / "05_Thumbnail_Workspace",
        "06_Final_Exports": project_dir / "06_Final_Exports",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Subdirectories for DropZone (Plans 1..6 + Audio_BGM)
    plan_names = [
        "Plan_01_Hook_Avatar",
        "Plan_02_Problem",
        "Plan_03_Company_Intro",
        "Plan_04_Requirements",
        "Plan_05_Benefits",
        "Plan_06_CTA_Avatar",
        "Audio_BGM",
    ]
    for p_name in plan_names:
        (dirs["03_Raw_DropZone"] / p_name).mkdir(parents=True, exist_ok=True)

    # Subdirectories for Premiere and Thumbnail
    (dirs["04_Premiere_Workspace"] / "Linked_Media").mkdir(parents=True, exist_ok=True)
    (dirs["04_Premiere_Workspace"] / "Subtitles").mkdir(parents=True, exist_ok=True)
    (dirs["05_Thumbnail_Workspace"] / "Linked_Assets").mkdir(parents=True, exist_ok=True)

    # Save job_details.json
    details_file = dirs["01_Extracted_Data"] / "job_details.json"
    with open(details_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, ensure_ascii=False, indent=2)

    # Save job_summary_clean.md
    summary_file = dirs["01_Extracted_Data"] / "job_summary_clean.md"
    skills_sec = f"## مهارت‌های مورد نیاز (Skills)\n{job_data.get('skills_formatted')}\n" if job_data.get('skills_formatted') else ""
    edus_sec = f"## تحصیلات و رشته‌های دانشگاهی (Educations)\n{job_data.get('educations_formatted')}\n" if job_data.get('educations_formatted') else ""
    company_sec = f"## مشخصات شرکت کارفرما\n- نام: {job_data.get('company_name')} ({job_data.get('company_en_title', '')})\n{job_data.get('company_description')}\n" if job_data.get('company_description') else ""

    summary_md = f"""# {job_data.get('job_title')}
- **شرکت:** {job_data.get('company_name')}
- **موقعیت:** {job_data.get('location')}
- **کد آگهی:** OJ-{job_id}
- **نوع همکاری:** {job_data.get('job_type_title')}
- **سابقه کار:** {job_data.get('experience_text')}
- **لینک آگهی:** {job_data.get('url')}

{skills_sec}
{edus_sec}
## شرح وظایف و جزئیات کامل آگهی
{job_data.get('full_description_clean') or job_data.get('duties')}

{company_sec}
"""
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary_md.strip() + "\n")

    # Save deep_search_prompt.txt
    deep_prompt = build_deep_search_prompt(job_data)
    prompt_file = dirs["01_Extracted_Data"] / "deep_search_prompt.txt"
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(deep_prompt)

    # Save logo in both places
    logo_paths = [
        dirs["05_Thumbnail_Workspace"] / "Linked_Assets" / "Company_Logo.png",
        dirs["04_Premiere_Workspace"] / "Linked_Media" / "Company_Logo.png",
    ]
    download_company_logo(
        job_data.get("logo_url", ""),
        logo_paths,
        company_name=job_data.get("company_name", ""),
    )

    return project_dir, dirs


PROMPT_ROLE_EXPLORER = """@oiljob-role-explorer 
سناریو ای جذاب و منسجم بنویس تا در اینستاگرام ویو خوب و وایرالی بگیرد"""

PROMPT_JSON_EXPORTER = """@oiljob-json-exporter
لطفا حالا محتوا را به صورت کامل در خروجی استاندارد بهم تحویل بده"""


def save_deep_search_result(project_dir: Path, result_text: str) -> Tuple[Path, Path]:
    """
    Saves the user's Gemini Deep Research result into 01_Extracted_Data/deep_search_result.md
    and builds 01_Extracted_Data/combined_dossier_for_gemini.md which combines
    the Deep Search result and job_summary_clean.md.
    """
    extracted_dir = project_dir / "01_Extracted_Data"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    result_file = extracted_dir / "deep_search_result.md"
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(result_text.strip() + "\n")

    summary_file = extracted_dir / "job_summary_clean.md"
    summary_content = ""
    if summary_file.exists():
        summary_content = summary_file.read_text(encoding="utf-8").strip()

    combined_content = f"""# پکیج جامع محتوایی موقعیت شغلی (آماده ورود به جمینای)

============================================================
## بخش اول: نتیجه کالبدشکافی عمیق بازار کار و اطلاعات میدانی (Deep Research)
============================================================
{result_text.strip()}

============================================================
## بخش دوم: شرح شغل، مهارت‌ها و مشخصات آگهی ایران اویل جاب (Job Details)
============================================================
{summary_content}
"""

    combined_file = extracted_dir / "combined_dossier_for_gemini.md"
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write(combined_content.strip() + "\n")

    return result_file, combined_file


def get_combined_dossier_text(project_dir: Path) -> str:
    """
    Returns the combined content of Deep Search result and Job Summary.
    """
    extracted_dir = project_dir / "01_Extracted_Data"
    combined_file = extracted_dir / "combined_dossier_for_gemini.md"
    if combined_file.exists():
        return combined_file.read_text(encoding="utf-8")

    # If combined file not created yet, build on the fly
    result_file = extracted_dir / "deep_search_result.md"
    summary_file = extracted_dir / "job_summary_clean.md"

    res_text = result_file.read_text(encoding="utf-8").strip() if result_file.exists() else ""
    sum_text = summary_file.read_text(encoding="utf-8").strip() if summary_file.exists() else ""

    return f"""# پکیج جامع محتوایی موقعیت شغلی (آماده ورود به جمینای)

============================================================
## بخش اول: نتیجه کالبدشکافی عمیق بازار کار و اطلاعات میدانی (Deep Research)
============================================================
{res_text}

============================================================
## بخش دوم: شرح شغل، مهارت‌ها و مشخصات آگهی ایران اویل جاب (Job Details)
============================================================
{sum_text}
"""

