"""
Zighoosh ReelForge - Main Window
Apple & Google Minimalist UI with Threaded Asynchronous Workflows
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, Optional

import customtkinter as ctk
from PIL import Image

from core.archiver import archive_project, check_final_exports
from core.flow_automator import FlowAutomator
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
    open_file_or_folder,
)
from ui.components import (
    CardFrame,
    LiveConsole,
    PrimaryButton,
    SecondaryButton,
    StatusPill,
)
from ui.settings_dialog import SettingsDialog
from ui.theme import (
    ACCENT_HOVER,
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    BG_MAIN,
    BORDER_ACTIVE,
    BORDER_COLOR,
    CORNER_RADIUS_BTN,
    CORNER_RADIUS_CARD,
    CORNER_RADIUS_INPUT,
    CORNER_RADIUS_PILL,
    DANGER_COLOR,
    FONT_BODY,
    FONT_BOLD,
    FONT_CAPTION,
    FONT_HEADER,
    FONT_MONO,
    FONT_TITLE,
    SUCCESS_COLOR,
    SURFACE_CARD,
    SURFACE_HOVER,
    SURFACE_INNER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
)

logger = logging.getLogger(__name__)


class ReelForgeApp(ctk.CTk):
    """
    Main Application Window for Zighoosh ReelForge (P-09).
    """

    def __init__(self):
        super().__init__()

        # Appearance setup
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Zighoosh ReelForge | استودیو هوشمند ویدیوسازی زیگهوش (P-09)")
        self.geometry("1100x820")
        self.minsize(980, 720)
        self.configure(fg_color=BG_MAIN)

        # State Variables
        self.config = self.load_config()
        self.flow_automator = FlowAutomator(self.config, log_callback=self.log)
        self.current_project_dir: Optional[Path] = None
        self.current_job_data: Optional[Dict[str, Any]] = None
        self.current_brain_data: Optional[Dict[str, Any]] = None
        self.log_queue = queue.Queue()

        # Build GUI
        self.build_header()
        self.build_tabs()
        self.build_bottom_console()

        # Start periodic log pump
        self.after(100, self.process_log_queue)

        self.log("نرم‌افزار Zighoosh ReelForge با موفقیت آماده به کار شد.", "SUCCESS")

    def load_config(self) -> Dict[str, Any]:
        default_config = {
            "downloads_path": str(Path.home() / "Downloads"),
            "active_workspace_path": "e:\\Zighoosh_Projects\\Active",
            "archive_path": "e:\\Zighoosh_Projects\\Archive",
            "templates_path": "App_Templates",
            "whisper_model": "base",
            "theme_mode": "dark",
            "auto_open_premiere": True,
            "flow_config": {
                "cdp_port": 9222,
                "chrome_profile_dir": "~/.config/google-chrome-flow",
                "default_video_model": "Veo 3.1 - Fast",
                "default_avatar_model": "Omni 1.1 Flash",
                "default_image_model": "Nano Banana Pro",
                "default_aspect": "9:16",
                "default_duration": "8s",
                "default_resolution": "720p",
                "generation_timeout_sec": 300,
            },
        }
        cfg_file = Path("config.json")
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_config.update(data)
            except Exception as e:
                logger.warning(f"Failed to read config.json: {e}")

        # Ensure base directories exist
        for k in ["downloads_path", "active_workspace_path", "archive_path", "templates_path"]:
            p = Path(default_config[k])
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        return default_config

    def log(self, message: str, level: str = "INFO"):
        self.log_queue.put((message, level))

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg, level = self.log_queue.get_nowait()
            self.console.log(msg, level)
        self.after(100, self.process_log_queue)

    def set_progress(self, value: float, indeterminate: bool = False):
        if indeterminate:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(max(0.0, min(value, 1.0)))

    # -------------------------------------------------------------
    # UI Building Blocks
    # -------------------------------------------------------------

    def build_header(self):
        header_card = CardFrame(self, height=64, fg_color=SURFACE_CARD)
        header_card.pack(fill="x", padx=16, pady=(14, 8))

        inner = ctk.CTkFrame(header_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=10)

        # Title and system badge
        left_box = ctk.CTkFrame(inner, fg_color="transparent")
        left_box.pack(side="left", fill="y")

        brand_title = ctk.CTkLabel(
            left_box,
            text="Zighoosh ReelForge",
            font=("Segoe UI", 16, "bold"),
            text_color=TEXT_PRIMARY,
        )
        brand_title.pack(side="left", padx=(0, 10))

        sub_brand = ctk.CTkLabel(
            left_box,
            text="| کارخانه ریلزسازی هوشمند (نسخه ایران اویل جاب)",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        )
        sub_brand.pack(side="left")

        # Right actions: Project Badge & Settings
        right_box = ctk.CTkFrame(inner, fg_color="transparent")
        right_box.pack(side="right", fill="y")

        self.project_badge = StatusPill(right_box, text="پروژه‌ای انتخاب نشده", state="neutral")
        self.project_badge.pack(side="left", padx=(0, 12))

        settings_btn = SecondaryButton(
            right_box,
            text="⚙️ تنظیمات مسیرها",
            width=120,
            command=self.open_settings_dialog,
        )
        settings_btn.pack(side="right")

    def build_tabs(self):
        # Modern Tabview
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=BG_MAIN,
            segmented_button_fg_color=SURFACE_INNER,
            segmented_button_selected_color=ACCENT_PRIMARY,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=SURFACE_INNER,
            segmented_button_unselected_hover_color=SURFACE_HOVER,
            text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_CARD,
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Add 5 core tabs
        self.tab_step1 = self.tabview.add("۱. استخراج آگهی (Ingest)")
        self.tab_step2 = self.tabview.add("۲. نتیجه دیپ‌سرچ و سناریو (Research & Prompts)")
        self.tab_step3 = self.tabview.add("۳. مغز متفکر و JSON (AI Brain)")
        self.tab_step4 = self.tabview.add("۴. تدوین و پریمیر (Assembly)")
        self.tab_step5 = self.tabview.add("۵. بازبینی و آرشیو (Archive)")

        self.setup_step1_ui()
        self.setup_step2_ui()
        self.setup_step3_ui()
        self.setup_step4_ui()
        self.setup_step5_ui()

    # -------------------------------------------------------------
    # Step 1: Ingest & Scrape
    # -------------------------------------------------------------
    def setup_step1_ui(self):
        parent = self.tab_step1

        # URL Ingest Card
        input_card = CardFrame(parent)
        input_card.pack(fill="x", padx=10, pady=(10, 8))

        lbl_row = ctk.CTkFrame(input_card, fg_color="transparent")
        lbl_row.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            lbl_row,
            text="🔗 لینک آگهی فرصت شغلی (از سایت iranoiljob.com):",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        input_row = ctk.CTkFrame(input_card, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 14))

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="https://iranoiljob.com/career-opportunities/14051/...",
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=40,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        paste_btn = SecondaryButton(
            input_row,
            text="چسباندن (Paste)",
            width=100,
            command=self.paste_url_from_clipboard,
        )
        paste_btn.pack(side="left", padx=(0, 8))

        self.scrape_btn = PrimaryButton(
            input_row,
            text="🚀 شروع استخراج اطلاعات",
            width=160,
            command=self.on_start_scrape_clicked,
        )
        self.scrape_btn.pack(side="right")

        # Extracted Data Preview Card
        self.preview_card = CardFrame(parent)
        self.preview_card.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        preview_header = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        preview_header.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            preview_header,
            text="خلاصه اطلاعات استخراج‌شده آگهی و فایل‌های تولیدی",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        self.step1_status_pill = StatusPill(preview_header, text="در انتظار دریافت لینک", state="neutral")
        self.step1_status_pill.pack(side="right")

        # Details Grid
        details_grid = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        details_grid.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Left: Logo Preview
        logo_box = ctk.CTkFrame(details_grid, width=160, fg_color=SURFACE_INNER, corner_radius=10)
        logo_box.pack(side="left", fill="y", padx=(0, 14), pady=4)
        logo_box.pack_propagate(False)

        self.logo_lbl = ctk.CTkLabel(logo_box, text="پیش‌نمایش لوگو", font=FONT_CAPTION, text_color=TEXT_MUTED)
        self.logo_lbl.pack(expand=True)

        # Right: Job Metadata Details
        meta_box = ctk.CTkFrame(details_grid, fg_color="transparent")
        meta_box.pack(side="left", fill="both", expand=True)

        self.lbl_job_title = ctk.CTkLabel(
            meta_box,
            text="عنوان شغل: —",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_job_title.pack(fill="x", pady=2)

        self.lbl_company = ctk.CTkLabel(
            meta_box,
            text="نام شرکت: —",
            font=FONT_BODY,
            text_color=ACCENT_SECONDARY,
            anchor="w",
        )
        self.lbl_company.pack(fill="x", pady=2)

        self.lbl_location = ctk.CTkLabel(
            meta_box,
            text="موقعیت: —",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_location.pack(fill="x", pady=2)

        self.lbl_conditions = ctk.CTkLabel(
            meta_box,
            text="شرایط کاری: —",
            font=FONT_BODY,
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self.lbl_conditions.pack(fill="x", pady=2)

        self.lbl_skills = ctk.CTkLabel(
            meta_box,
            text="مهارت‌های استخراج‌شده: —",
            font=FONT_BODY,
            text_color=ACCENT_SECONDARY,
            anchor="w",
            wraplength=650,
            justify="left",
        )
        self.lbl_skills.pack(fill="x", pady=2)

        self.lbl_project_path = ctk.CTkLabel(
            meta_box,
            text="پوشه پروژه: —",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_project_path.pack(fill="x", pady=2)

        # Action Buttons in Step 1
        actions_bar = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=16, pady=(4, 14))

        self.copy_prompt_btn = PrimaryButton(
            actions_bar,
            text="📋 کپی پرامپت Gemini Deep Research",
            command=self.copy_deep_search_prompt,
            fg_color="#1E293B",
            hover_color="#334155",
            state="disabled",
        )
        self.copy_prompt_btn.pack(side="left", padx=(0, 10))

        self.open_proj_btn = SecondaryButton(
            actions_bar,
            text="📂 باز کردن پوشه پروژه",
            command=self.open_current_project_folder,
            state="disabled",
        )
        self.open_proj_btn.pack(side="left")

        # Next Step button
        self.go_to_step2_btn = PrimaryButton(
            actions_bar,
            text="ادامه به گام ۲ (دیپ‌سرچ و سناریو) ◀",
            command=lambda: self.tabview.set("۲. نتیجه دیپ‌سرچ و سناریو (Research & Prompts)"),
            state="disabled",
        )
        self.go_to_step2_btn.pack(side="right")

    # -------------------------------------------------------------
    # Step 2: Deep Search Result & Gemini Prompts
    # -------------------------------------------------------------
    def setup_step2_ui(self):
        parent = self.tab_step2

        # Card: Deep Search Result Paste
        ds_card = CardFrame(parent)
        ds_card.pack(fill="both", expand=True, padx=10, pady=(10, 8))

        h_frame = ctk.CTkFrame(ds_card, fg_color="transparent")
        h_frame.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            h_frame,
            text="نتیجه تحلیل و کالبدشکافی عمیق بازار کار و اطلاعات میدانی (Gemini Deep Research):",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        top_actions = ctk.CTkFrame(h_frame, fg_color="transparent")
        top_actions.pack(side="right")

        paste_ds_btn = SecondaryButton(
            top_actions,
            text="📋 چسباندن (Paste)",
            width=110,
            command=self.paste_deep_result_from_clipboard,
        )
        paste_ds_btn.pack(side="left", padx=(0, 8))

        select_ds_file_btn = SecondaryButton(
            top_actions,
            text="📁 بارگذاری از فایل...",
            width=130,
            command=self.load_deep_result_from_file,
        )
        select_ds_file_btn.pack(side="left")

        # Textbox for Deep Search result
        self.deep_search_textbox = ctk.CTkTextbox(
            ds_card,
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_BODY,
            corner_radius=CORNER_RADIUS_INPUT,
            wrap="word",
        )
        self.deep_search_textbox.pack(fill="both", expand=True, padx=16, pady=(4, 10))

        # Save and status bar inside ds_card
        save_bar = ctk.CTkFrame(ds_card, fg_color="transparent")
        save_bar.pack(fill="x", padx=16, pady=(0, 12))

        self.save_deep_result_btn = PrimaryButton(
            save_bar,
            text="💾 ذخیره نتیجه دیپ‌سرچ و ساخت پکیج جامع محتوایی",
            width=270,
            command=self.on_save_deep_search_result_clicked,
        )
        self.save_deep_result_btn.pack(side="left", padx=(0, 12))

        self.step2_status_pill = StatusPill(
            save_bar,
            text="در انتظار ثبت نتیجه دیپ‌سرچ ⚠️",
            state="warning",
        )
        self.step2_status_pill.pack(side="left")

        # Card: Prompts & Pipeline Actions
        prompts_card = CardFrame(parent, fg_color=SURFACE_CARD)
        prompts_card.pack(fill="x", padx=10, pady=(0, 10))

        p_inner = ctk.CTkFrame(prompts_card, fg_color="transparent")
        p_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            p_inner,
            text="هدایت جریان کار با هوش مصنوعی (Gemini Commands & Dossier):",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        # Action Buttons Row
        action_btns_row = ctk.CTkFrame(p_inner, fg_color="transparent")
        action_btns_row.pack(fill="x")

        # Button 1: Copy Combined Dossier (Deep Search + Job Clean Summary)
        self.btn_copy_dossier = PrimaryButton(
            action_btns_row,
            text="📋 ۱. کپی پکیج جامع (دیپ‌سرچ + شرح کامل شغل)",
            command=self.copy_combined_dossier,
            state="disabled",
            fg_color="#1E293B",
            hover_color="#334155",
        )
        self.btn_copy_dossier.pack(side="left", padx=(0, 8))

        # Button 2: Copy Role Explorer Prompt
        self.btn_copy_role_explorer = SecondaryButton(
            action_btns_row,
            text="✍️ ۲. کپی پرامپت @oiljob-role-explorer",
            command=self.copy_prompt_role_explorer,
            state="disabled",
        )
        self.btn_copy_role_explorer.pack(side="left", padx=(0, 8))

        # Button 3: Copy JSON Exporter Prompt
        self.btn_copy_json_exporter = SecondaryButton(
            action_btns_row,
            text="⚙️ ۳. کپی پرامپت @oiljob-json-exporter",
            command=self.copy_prompt_json_exporter,
            state="disabled",
        )
        self.btn_copy_json_exporter.pack(side="left", padx=(0, 8))

        # Open extracted data folder
        self.btn_step2_open_docs = SecondaryButton(
            action_btns_row,
            text="📂 اسناد پروژه",
            width=100,
            command=self.open_extracted_data_folder,
            state="disabled",
        )
        self.btn_step2_open_docs.pack(side="left", padx=(0, 8))

        # Next Step Button
        self.go_to_step3_btn = PrimaryButton(
            action_btns_row,
            text="ادامه به گام ۳ (مغز متفکر و JSON) ◀",
            command=lambda: self.tabview.set("۳. مغز متفکر و JSON (AI Brain)"),
            state="disabled",
        )
        self.go_to_step3_btn.pack(side="right")

    # -------------------------------------------------------------
    # Step 3: AI Brain & JSON Parser
    # -------------------------------------------------------------
    def setup_step3_ui(self):
        parent = self.tab_step3

        # Scrollable container for Step 3 to ensure all cards fit comfortably
        scroll_step3 = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll_step3.pack(fill="both", expand=True, padx=4, pady=4)

        # Card 1: JSON Input
        json_card = CardFrame(scroll_step3)
        json_card.pack(fill="x", padx=10, pady=(6, 8))

        h_frame = ctk.CTkFrame(json_card, fg_color="transparent")
        h_frame.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            h_frame,
            text="خروجی JSON حاصل از دستور @oiljob-json-exporter را اینجا قرار دهید:",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        json_top_actions = ctk.CTkFrame(h_frame, fg_color="transparent")
        json_top_actions.pack(side="right")

        paste_json_btn = SecondaryButton(
            json_top_actions,
            text="📋 چسباندن (Paste)",
            width=100,
            command=self.paste_json_from_clipboard,
        )
        paste_json_btn.pack(side="left", padx=(0, 8))

        select_file_btn = SecondaryButton(
            json_top_actions,
            text="📁 انتخاب فایل JSON...",
            width=130,
            command=self.load_json_from_file,
        )
        select_file_btn.pack(side="left")

        self.json_textbox = ctk.CTkTextbox(
            json_card,
            height=130,
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            corner_radius=CORNER_RADIUS_INPUT,
            wrap="word",
        )
        self.json_textbox.pack(fill="x", padx=16, pady=(4, 10))

        # Action Buttons in Step 3
        btn_bar = ctk.CTkFrame(json_card, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=(0, 14))

        self.process_json_btn = PrimaryButton(
            btn_bar,
            text="⚡ پردازش JSON و ساخت اسناد تفکیک‌شده",
            command=self.on_process_json_clicked,
        )
        self.process_json_btn.pack(side="left", padx=(0, 10))

        self.copy_flow_btn = SecondaryButton(
            btn_bar,
            text="📋 کپی اسکریپت‌های گوگل فلو",
            command=self.copy_flow_scripts,
            state="disabled",
        )
        self.copy_flow_btn.pack(side="left", padx=(0, 8))

        self.copy_music_btn = SecondaryButton(
            btn_bar,
            text="🎵 کپی پرامپت موزیک",
            command=self.copy_music_prompt,
            state="disabled",
        )
        self.copy_music_btn.pack(side="left", padx=(0, 8))

        self.copy_thumb_btn = SecondaryButton(
            btn_bar,
            text="🖼️ کپی پرامپت تامنیل",
            command=self.copy_thumb_prompt,
            state="disabled",
        )
        self.copy_thumb_btn.pack(side="left", padx=(0, 8))

        self.open_dropzone_btn = SecondaryButton(
            btn_bar,
            text="📂 باز کردن پوشه DropZone",
            command=self.open_dropzone_folder,
            state="disabled",
        )
        self.open_dropzone_btn.pack(side="left", padx=(0, 8))

        self.go_to_step4_btn = PrimaryButton(
            btn_bar,
            text="ادامه به گام ۴ (تدوین و پریمیر) ◀",
            command=lambda: self.tabview.set("۴. تدوین و پریمیر (Assembly)"),
            state="disabled",
        )
        self.go_to_step4_btn.pack(side="right")

        # Card 2: Google Flow Automation Card (Terminal CDP)
        flow_card = CardFrame(scroll_step3, fg_color=SURFACE_CARD)
        flow_card.pack(fill="x", padx=10, pady=(0, 10))

        fc_head = ctk.CTkFrame(flow_card, fg_color="transparent")
        fc_head.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            fc_head,
            text="اتوماسیون مستقیم Google Flow (Terminal CDP)",
            font=FONT_TITLE,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            fc_head,
            text="اتصال مستقیم و دانلود راش‌ها از طریق Chrome DevTools Protocol بدون مسدودی یا پرچم رباتیک",
            font=FONT_CAPTION,
            text_color=TEXT_MUTED,
        ).pack(side="left", padx=(12, 0))

        # Row 1: Status & Browser Launch
        row1 = ctk.CTkFrame(flow_card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(8, 6))

        self.flow_status_pill = StatusPill(row1, text="⚪ وضعیت مرورگر: بررسی نشده", state="neutral")
        self.flow_status_pill.pack(side="left", padx=(0, 12))

        self.flow_launch_btn = SecondaryButton(
            row1,
            text="۱. باز کردن کروم (flow launch)",
            width=180,
            command=self.on_flow_launch_clicked,
        )
        self.flow_launch_btn.pack(side="left", padx=(0, 8))

        self.flow_doctor_btn = SecondaryButton(
            row1,
            text="۲. تست اتصال (flow doctor)",
            width=170,
            command=self.on_flow_doctor_clicked,
        )
        self.flow_doctor_btn.pack(side="left")

        # Row 2: Automated Generation Controls
        row2 = ctk.CTkFrame(flow_card, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(6, 14))

        self.flow_dry_run_var = ctk.BooleanVar(value=False)
        self.flow_dry_run_cb = ctk.CTkCheckBox(
            row2,
            text="تست آزمایشی بدون مصرف کردیت (Dry Run)",
            variable=self.flow_dry_run_var,
            font=FONT_BODY,
            text_color=TEXT_PRIMARY,
            border_color=BORDER_COLOR,
            checkmark_color="#FFFFFF",
            fg_color=ACCENT_PRIMARY,
        )
        self.flow_dry_run_cb.pack(side="left", padx=(0, 16))

        self.flow_thumb_btn = SecondaryButton(
            row2,
            text="🖼 تولید خودکار تصویر تامنیل در Flow",
            command=self.on_generate_flow_thumbnail_clicked,
            state="disabled",
        )
        self.flow_thumb_btn.pack(side="left", padx=(0, 10))

        self.flow_run_pipeline_btn = PrimaryButton(
            row2,
            text="🚀 تولید و دانلود خودکار کل ۶ پلان ویدیویی در Flow",
            command=self.on_run_flow_pipeline_clicked,
            state="disabled",
            fg_color="#059669",
            hover_color="#047857",
        )
        self.flow_run_pipeline_btn.pack(side="right")
        self.go_to_step4_btn.pack(side="right")

    # -------------------------------------------------------------
    # Step 4: Assembly, Subtitles & Premiere
    # -------------------------------------------------------------
    def setup_step4_ui(self):
        parent = self.tab_step4

        # DropZone Checklist Card
        checklist_card = CardFrame(parent)
        checklist_card.pack(fill="both", expand=True, padx=10, pady=(10, 8))

        cl_header = ctk.CTkFrame(checklist_card, fg_color="transparent")
        cl_header.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            cl_header,
            text="چک‌لیست راش‌های موجود در DropZone (پلان‌های ۱ تا ۶ + موزیک)",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        refresh_btn = SecondaryButton(
            cl_header,
            text="🔄 بازخوانی وضعیت راش‌ها",
            width=140,
            command=self.refresh_dropzone_checklist,
        )
        refresh_btn.pack(side="right")

        # Scrollable container for plans checklist
        self.plans_scroll = ctk.CTkScrollableFrame(
            checklist_card,
            fg_color=SURFACE_INNER,
            corner_radius=10,
        )
        self.plans_scroll.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        self.plan_row_widgets = {}
        self.populate_initial_checklist()

        # Step 4 Control Bar
        control_card = CardFrame(parent, fg_color=SURFACE_INNER)
        control_card.pack(fill="x", padx=10, pady=(0, 10))

        ctrl_inner = ctk.CTkFrame(control_card, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=16, pady=12)

        # Whisper Model Size Option
        model_frame = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        model_frame.pack(side="left", fill="y")

        ctk.CTkLabel(
            model_frame,
            text="مدل Whisper:",
            font=FONT_BOLD,
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 6))

        self.step3_model_combo = ctk.CTkComboBox(
            model_frame,
            values=["base", "small", "medium"],
            width=90,
            height=32,
            fg_color=SURFACE_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
        )
        self.step3_model_combo.set(self.config.get("whisper_model", "base"))
        self.step3_model_combo.pack(side="left")

        # Next Step to Archive Button
        self.go_to_step5_btn = PrimaryButton(
            ctrl_inner,
            text="ادامه به گام ۵ (آرشیو) ◀",
            command=lambda: self.tabview.set("۵. بازبینی و آرشیو (Archive)"),
        )
        self.go_to_step5_btn.pack(side="right", padx=(8, 0))

        # Big CTA Build Button
        self.build_workspace_btn = PrimaryButton(
            ctrl_inner,
            text="✨ ساخت پروژه پریمیر + تولید زیرنویس هوشمند .srt",
            height=42,
            font=("Segoe UI", 13, "bold"),
            command=self.on_build_workspace_clicked,
            state="disabled",
        )
        self.build_workspace_btn.pack(side="right", padx=(8, 0))

        self.open_premiere_btn = SecondaryButton(
            ctrl_inner,
            text="🎬 باز کردن پروژه پریمیر",
            command=self.open_premiere_project,
            state="disabled",
        )
        self.open_premiere_btn.pack(side="right", padx=(8, 0))

        self.open_subs_btn = SecondaryButton(
            ctrl_inner,
            text="📁 پوشه زیرنویس‌ها",
            command=self.open_subtitles_folder,
            state="disabled",
        )
        self.open_subs_btn.pack(side="right")

    def populate_initial_checklist(self):
        plan_definitions = [
            ("Plan_01_Hook_Avatar", "پلان ۰۱: قلاب توجه آواتار (AVATAR_HOOK)"),
            ("Plan_02_Problem", "پلان ۰۲: چالش فنی و نریشن (BROLL_NARRATION)"),
            ("Plan_03_Company_Intro", "پلان ۰۳: معرفی شرکت و اعتبار ملی (COMPANY_INTRO)"),
            ("Plan_04_Requirements", "پلان ۰۴: شرایط احراز و مهارت‌ها (REQUIREMENTS)"),
            ("Plan_05_Benefits", "پلان ۰۵: حقوق و مزایای همکاری (BENEFITS)"),
            ("Plan_06_CTA_Avatar", "پلان ۰۶: کال تو اکشن ارسال رزومه (CTA_AVATAR)"),
            ("Audio_BGM", "موزیک پس‌زمینه ریلز و تصویر تامنیل (BGM & Thumbnail)"),
        ]

        for p_key, title in plan_definitions:
            row = ctk.CTkFrame(self.plans_scroll, fg_color=SURFACE_CARD, corner_radius=8, height=38)
            row.pack(fill="x", pady=3, padx=4)
            row.pack_propagate(False)

            t_lbl = ctk.CTkLabel(row, text=title, font=FONT_BODY, text_color=TEXT_PRIMARY)
            t_lbl.pack(side="left", padx=12)

            pill = StatusPill(row, text="در انتظار راش ⚠️", state="warning")
            pill.pack(side="right", padx=10)

            self.plan_row_widgets[p_key] = pill

    def refresh_dropzone_checklist(self):
        if not self.current_project_dir:
            self.log("ابتدا باید یک پروژه ایجاد یا انتخاب شود.", "WARNING")
            return

        status = check_dropzone_status(self.current_project_dir)
        all_ready = True

        for p_key, data in status.items():
            pill = self.plan_row_widgets.get(p_key)
            if not pill:
                continue

            if p_key == "Audio_BGM":
                if data.get("has_audio") and data.get("has_image"):
                    pill.set_status("موزیک و تصویر تامنیل آماده ✅", "success")
                elif data.get("has_image"):
                    pill.set_status("تصویر تامنیل آماده ✅", "success")
                elif data.get("has_audio"):
                    pill.set_status("موزیک آماده ✅", "success")
                else:
                    pill.set_status("بدون موزیک و تامنیل ⚠️", "warning")
            else:
                if data.get("has_video") and data.get("has_audio"):
                    pill.set_status("ویدیو و صدا آماده ✅", "success")
                elif data.get("has_video"):
                    pill.set_status("ویدیو آماده ✅", "success")
                else:
                    all_ready = False
                    pill.set_status("خالی / منتظر ویدیو ⚠️", "warning")

        self.log("وضعیت راش‌های DropZone با موفقیت به‌روزرسانی شد.")
        self.build_workspace_btn.configure(state="normal")

    # -------------------------------------------------------------
    # Step 5: Verification & Archive
    # -------------------------------------------------------------
    def setup_step5_ui(self):
        parent = self.tab_step5

        archive_card = CardFrame(parent)
        archive_card.pack(fill="both", expand=True, padx=10, pady=(10, 10))

        ctk.CTkLabel(
            archive_card,
            text="کنترل نهایی کیفیت و بایگانی امن پروژه",
            font=FONT_HEADER,
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            archive_card,
            text="پس از اتمام تدوین و ذخیره خروجی رندر نهایی در پوشه 06_Final_Exports، پروژه را آرشیو کنید.",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # Status check container
        status_box = ctk.CTkFrame(archive_card, fg_color=SURFACE_INNER, corner_radius=10)
        status_box.pack(fill="x", padx=20, pady=(0, 14))

        self.export_status_lbl = ctk.CTkLabel(
            status_box,
            text="وضعیت خروجی رندر: بررسی نشده",
            font=FONT_BOLD,
            text_color=TEXT_SECONDARY,
        )
        self.export_status_lbl.pack(side="left", padx=16, pady=12)

        check_btn = SecondaryButton(
            status_box,
            text="🔍 بررسی خروجی‌ها",
            width=130,
            command=self.check_exports_status,
        )
        check_btn.pack(side="right", padx=12, pady=12)

        # Cleanup option
        self.clean_raw_var = ctk.BooleanVar(value=True)
        self.clean_switch = ctk.CTkSwitch(
            archive_card,
            text="پاکسازی راش‌های تکراری و خام در پوشه DropZone برای صرفه‌جویی در فضای دیسک",
            variable=self.clean_raw_var,
            font=FONT_BODY,
            text_color=TEXT_PRIMARY,
            progress_color=ACCENT_PRIMARY,
        )
        self.clean_switch.pack(anchor="w", padx=20, pady=10)

        # Actions
        actions_row = ctk.CTkFrame(archive_card, fg_color="transparent")
        actions_row.pack(fill="x", padx=20, pady=(16, 20))

        self.open_exports_btn = SecondaryButton(
            actions_row,
            text="📂 باز کردن پوشه خروجی نهایی (06_Final_Exports)",
            command=self.open_final_exports_folder,
        )
        self.open_exports_btn.pack(side="left")

        self.archive_btn = PrimaryButton(
            actions_row,
            text="📦 انتقال نهایی پروژه به آرشیو",
            width=180,
            command=self.on_archive_project_clicked,
            fg_color="#10B981",
            hover_color="#059669",
        )
        self.archive_btn.pack(side="right")

    # -------------------------------------------------------------
    # Bottom Console & Live Progress Bar
    # -------------------------------------------------------------
    def build_bottom_console(self):
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=16, pady=(0, 12))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            bottom_frame,
            height=6,
            corner_radius=3,
            fg_color=SURFACE_INNER,
            progress_color=ACCENT_PRIMARY,
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(0, 6))

        # Console
        self.console = LiveConsole(bottom_frame, height=130)
        self.console.pack(fill="x")

    # -------------------------------------------------------------
    # Event Handlers & Workflows
    # -------------------------------------------------------------

    def open_settings_dialog(self):
        SettingsDialog(self, config=self.config, on_save_cb=self.on_settings_saved)

    def on_settings_saved(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.flow_automator = FlowAutomator(self.config, log_callback=self.log)
        self.step3_model_combo.set(self.config.get("whisper_model", "base"))
        self.log("تنظیمات با موفقیت ذخیره و اعمال شد.", "SUCCESS")

    def paste_url_from_clipboard(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def on_start_scrape_clicked(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("ورودی ناقص", "لطفاً لینک آگهی را وارد کنید.")
            return

        self.scrape_btn.configure(state="disabled")
        self.set_progress(0.2, indeterminate=True)
        self.log(f"شروع استخراج اطلاعات از: {url}")

        def worker():
            try:
                job_data = fetch_job_details(url)
                base_dir = Path(self.config.get("downloads_path", str(Path.home() / "Downloads")))

                self.log("ایجاد ساختار استاندارد پوشه‌ها و دانلود لوگوی شرکت...")
                project_dir, dirs = initialize_step1_workspace(job_data, base_dir)

                self.current_job_data = job_data
                self.current_project_dir = project_dir

                self.after(0, lambda: self.on_scrape_success(job_data, project_dir))
            except Exception as e:
                logger.error(f"Scrape error: {e}")
                self.after(0, lambda: self.on_scrape_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_scrape_success(self, job_data: Dict[str, Any], project_dir: Path):
        self.scrape_btn.configure(state="normal")
        self.set_progress(1.0)

        # Update metadata UI
        job_code = job_data.get("job_code", "OJ-0000")
        self.lbl_job_title.configure(text=f"عنوان شغل: {job_data.get('job_title', '—')}")
        self.lbl_company.configure(text=f"نام شرکت: {job_data.get('company_name', '—')}")
        self.lbl_location.configure(text=f"موقعیت: {job_data.get('location', '—')}")

        jtype = job_data.get("job_type_title", "تمام وقت")
        exp = job_data.get("experience_text", "سابقه مرتبط")
        self.lbl_conditions.configure(text=f"شرایط کاری: {jtype} | {exp}")

        skills = [s.get("title") for s in job_data.get("skills", []) if s.get("title")]
        if skills:
            skills_preview = " ، ".join(skills[:5])
            if len(skills) > 5:
                skills_preview += f" و {len(skills) - 5} مورد دیگر..."
            self.lbl_skills.configure(text=f"مهارت‌های تخصصی ({len(skills)} مهارت): {skills_preview}")
        else:
            self.lbl_skills.configure(text="مهارت‌های تخصصی: استخراج‌شده از متن شرح آگهی")

        self.lbl_project_path.configure(text=f"پوشه پروژه: {project_dir}")

        self.project_badge.set_status(job_code, "active")
        self.step1_status_pill.set_status("استخراج موفق ✅", "success")

        # Load logo preview if exists
        logo_file = project_dir / "05_Thumbnail_Workspace" / "Linked_Assets" / "Company_Logo.png"
        if logo_file.exists():
            try:
                pil_img = Image.open(logo_file)
                pil_img.thumbnail((120, 120))
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                self.logo_lbl.configure(image=ctk_img, text="")
            except Exception as e:
                logger.warning(f"Failed to display logo preview: {e}")

        # Enable Buttons
        self.copy_prompt_btn.configure(state="normal", fg_color=ACCENT_PRIMARY)
        self.open_proj_btn.configure(state="normal")
        self.go_to_step2_btn.configure(state="normal")
        self.open_dropzone_btn.configure(state="normal")
        self.btn_step2_open_docs.configure(state="normal")

        # Check if flow.json exists
        flow_manifest = project_dir / "02_AI_Brain_JSON" / "flow.json"
        if flow_manifest.exists():
            self.flow_thumb_btn.configure(state="normal")
            self.flow_run_pipeline_btn.configure(state="normal")

        # Check if deep_search_result.md exists
        ds_res_file = project_dir / "01_Extracted_Data" / "deep_search_result.md"
        if ds_res_file.exists():
            try:
                ds_content = ds_res_file.read_text(encoding="utf-8")
                self.deep_search_textbox.delete("1.0", "end")
                self.deep_search_textbox.insert("1.0", ds_content)
                self.step2_status_pill.set_status("نتیجه قبلاً ثبت شده ✅", "success")
                self.btn_copy_dossier.configure(state="normal", fg_color=ACCENT_PRIMARY)
                self.btn_copy_role_explorer.configure(state="normal")
                self.btn_copy_json_exporter.configure(state="normal")
                self.go_to_step3_btn.configure(state="normal")
            except Exception:
                pass
        else:
            self.step2_status_pill.set_status("در انتظار ثبت نتیجه دیپ‌سرچ ⚠️", "warning")

        self.log(f"پروژه با موفقیت ایجاد شد: {project_dir.name}", "SUCCESS")
        self.log("پرامپت Gemini Deep Research آماده کپی است.", "INFO")

    def on_scrape_error(self, err_msg: str):
        self.scrape_btn.configure(state="normal")
        self.set_progress(0.0)
        self.step1_status_pill.set_status("خطا در استخراج ✖", "danger")
        self.log(f"خطا در دریافت و استخراج اطلاعات: {err_msg}", "ERROR")
        messagebox.showerror("خطا", f"عملیات با خطا مواجه شد:\n{err_msg}")

    def copy_deep_search_prompt(self):
        if not self.current_project_dir:
            return
        prompt_file = self.current_project_dir / "01_Extracted_Data" / "deep_search_prompt.txt"
        if prompt_file.exists():
            content = prompt_file.read_text(encoding="utf-8")
            self.clipboard_clear()
            self.clipboard_append(content)
            self.log("پرامپت Gemini Deep Research در حافظه کپی شد (آماده Paste در چت).", "SUCCESS")
            messagebox.showinfo("کپی شد", "پرامپت دیپ‌سرچ با موفقیت کپی شد!\nمی‌توانید آن را در جمینای پیست کنید.")

    def open_current_project_folder(self):
        if self.current_project_dir and self.current_project_dir.exists():
            open_file_or_folder(self.current_project_dir)

    def paste_deep_result_from_clipboard(self):
        try:
            text = self.clipboard_get()
            self.deep_search_textbox.delete("1.0", "end")
            self.deep_search_textbox.insert("1.0", text.strip())
            self.log("نتیجه دیپ‌سرچ از حافظه چسبانده شد.")
        except Exception as e:
            self.log(f"خطا در خواندن از کلیپ‌بورد: {e}", "WARNING")

    def load_deep_result_from_file(self):
        file_path = filedialog.askopenfilename(
            title="انتخاب فایل نتیجه دیپ‌سرچ",
            filetypes=[("Markdown & Text", "*.md;*.txt"), ("All Files", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.deep_search_textbox.delete("1.0", "end")
                self.deep_search_textbox.insert("1.0", content)
                self.log(f"نتیجه دیپ‌سرچ از فایل بارگذاری شد: {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("خطا", f"خطا در خواندن فایل: {e}")

    def on_save_deep_search_result_clicked(self):
        content = self.deep_search_textbox.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("ورودی خالی", "لطفاً ابتدا متن خروجی دیپ‌سرچ را در کادر قرار دهید.")
            return

        if not self.current_project_dir:
            selected = filedialog.askdirectory(title="انتخاب پوشه پروژه (OJ-XXXXX)")
            if selected:
                self.current_project_dir = Path(selected)
            else:
                messagebox.showwarning("پروژه مشخص نشده", "لطفاً ابتدا در گام ۱ پروژه را ایجاد کنید یا پوشه پروژه را انتخاب فرمایید.")
                return

        try:
            res_file, combined_file = save_deep_search_result(self.current_project_dir, content)
            self.step2_status_pill.set_status("نتیجه و پکیج تجمیعی ذخیره شد ✅", "success")
            self.btn_copy_dossier.configure(state="normal", fg_color=ACCENT_PRIMARY)
            self.btn_copy_role_explorer.configure(state="normal")
            self.btn_copy_json_exporter.configure(state="normal")
            self.btn_step2_open_docs.configure(state="normal")
            self.go_to_step3_btn.configure(state="normal")

            self.log(f"نتیجه دیپ‌سرچ و پکیج جامع محتوایی با موفقیت در {res_file.name} و {combined_file.name} ذخیره شدند.", "SUCCESS")
            messagebox.showinfo(
                "ذخیره موفق",
                "نتیجه دیپ‌سرچ ذخیره شد و پکیج جامع محتوایی (شامل دیپ‌سرچ + شرح کامل شغل و مهارت‌ها) با موفقیت تولید شد.\n\n"
                "گام‌های بعدی:\n"
                "۱. با دکمه ۱، پکیج جامع را کپی کرده و در چت جمینای Paste کنید.\n"
                "۲. با دکمه ۲، پرامپت سناریونویسی (@oiljob-role-explorer) را ارسال کنید.\n"
                "۳. پس از تایید سناریو، با دکمه ۳ پرامپت خروجی JSON (@oiljob-json-exporter) را ارسال کنید.",
            )
        except Exception as e:
            logger.error(f"Save deep search error: {e}")
            self.log(f"خطا در ذخیره نتیجه دیپ‌سرچ: {e}", "ERROR")
            messagebox.showerror("خطا", f"عملیات ذخیره‌سازی با خطا مواجه شد:\n{e}")

    def copy_combined_dossier(self):
        if not self.current_project_dir:
            messagebox.showwarning("خطا", "پروژه‌ای انتخاب نشده است.")
            return
        dossier_text = get_combined_dossier_text(self.current_project_dir)
        if not dossier_text.strip():
            messagebox.showwarning("خطا", "محتوای پکیج تجمیعی خالی است. ابتدا نتیجه دیپ‌سرچ را ذخیره کنید.")
            return

        self.clipboard_clear()
        self.clipboard_append(dossier_text)
        self.log("پکیج جامع محتوایی (دیپ‌سرچ + شرح کامل شغل) در کلیپ‌بورد کپی شد.", "SUCCESS")
        messagebox.showinfo(
            "کپی شد",
            "پکیج جامع محتوایی در کلیپ‌بورد کپی شد!\nاکنون می‌توانید آن را در چت جمینای Paste کنید.",
        )

    def copy_prompt_role_explorer(self):
        self.clipboard_clear()
        self.clipboard_append(PROMPT_ROLE_EXPLORER)
        self.log("پرامپت سناریونویسی @oiljob-role-explorer در کلیپ‌بورد کپی شد.", "SUCCESS")
        messagebox.showinfo(
            "کپی شد",
            f"پرامپت سناریونویسی در کلیپ‌بورد کپی شد:\n\n{PROMPT_ROLE_EXPLORER}\n\nاکنون آن را در چت جمینای ارسال فرمایید.",
        )

    def copy_prompt_json_exporter(self):
        self.clipboard_clear()
        self.clipboard_append(PROMPT_JSON_EXPORTER)
        self.log("پرامپت استخراج JSON نهایی @oiljob-json-exporter در کلیپ‌بورد کپی شد.", "SUCCESS")
        messagebox.showinfo(
            "کپی شد",
            f"پرامپت استخراج خروجی JSON در کلیپ‌بورد کپی شد:\n\n{PROMPT_JSON_EXPORTER}\n\nپس از رسیدن به سناریوی مطلوب، این پرامپت را بفرستید تا خروجی نهایی به صورت JSON آماده شود.",
        )

    def open_extracted_data_folder(self):
        if self.current_project_dir:
            extracted_dir = self.current_project_dir / "01_Extracted_Data"
            if extracted_dir.exists():
                open_file_or_folder(extracted_dir)

    def paste_json_from_clipboard(self):
        try:
            text = self.clipboard_get()
            self.json_textbox.delete("1.0", "end")
            self.json_textbox.insert("1.0", text.strip())
            self.log("کد JSON از کلیپ‌بورد چسبانده شد.")
        except Exception as e:
            self.log(f"خطا در خواندن از کلیپ‌بورد: {e}", "WARNING")

    def load_json_from_file(self):
        file_path = filedialog.askopenfilename(
            title="انتخاب فایل gemini_master_output.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.json_textbox.delete("1.0", "end")
                self.json_textbox.insert("1.0", content)
                self.log(f"فایل JSON بارگذاری شد: {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("خطا", f"خطا در خواندن فایل: {e}")

    def on_process_json_clicked(self):
        raw_text = self.json_textbox.get("1.0", "end").strip()
        if not raw_text:
            messagebox.showwarning("ورودی خالی", "لطفاً ابتدا کد JSON خروجی جمینای را وارد کنید.")
            return

        if not self.current_project_dir:
            # Pick project folder manually if not created in step 1
            selected = filedialog.askdirectory(title="انتخاب پوشه پروژه (OJ-XXXXX)")
            if selected:
                self.current_project_dir = Path(selected)
            else:
                messagebox.showwarning("پروژه مشخص نشده", "لطفاً پوشه پروژه را انتخاب کنید.")
                return

        self.set_progress(0.4, indeterminate=True)
        self.log("در حال اعتبارسنجی و پردازش JSON...")

        success, msg, brain_data = process_gemini_json(raw_text, self.current_project_dir)
        self.set_progress(1.0)

        if success:
            self.current_brain_data = brain_data
            self.copy_flow_btn.configure(state="normal")
            self.copy_music_btn.configure(state="normal")
            self.copy_thumb_btn.configure(state="normal")
            self.open_dropzone_btn.configure(state="normal")
            self.build_workspace_btn.configure(state="normal")
            self.go_to_step4_btn.configure(state="normal")
            self.flow_thumb_btn.configure(state="normal")
            self.flow_run_pipeline_btn.configure(state="normal")

            self.log(msg, "SUCCESS")
            self.refresh_dropzone_checklist()
            messagebox.showinfo("موفقیت", "اسناد با موفقیت تفکیک شدند.\nاکنون راش‌های دانلودشده از گوگل فلو را در پوشه DropZone قرار دهید.")
        else:
            self.log(msg, "ERROR")
            messagebox.showerror("خطا در ساختار JSON", msg)

    def copy_flow_scripts(self):
        if not self.current_project_dir:
            return
        f = self.current_project_dir / "02_AI_Brain_JSON" / "flow_ready_script.txt"
        if f.exists():
            self.clipboard_clear()
            self.clipboard_append(f.read_text(encoding="utf-8"))
            self.log("اسکریپت‌های گوگل فلو در کلیپ‌بورد کپی شد.", "SUCCESS")

    def copy_music_prompt(self):
        if not self.current_project_dir:
            return
        f = self.current_project_dir / "02_AI_Brain_JSON" / "music_prompt.txt"
        if f.exists():
            self.clipboard_clear()
            self.clipboard_append(f.read_text(encoding="utf-8"))
            self.log("پرامپت موزیک در کلیپ‌بورد کپی شد.", "SUCCESS")

    def copy_thumb_prompt(self):
        if not self.current_project_dir:
            return
        f = self.current_project_dir / "02_AI_Brain_JSON" / "thumbnail_bg_prompt.txt"
        if f.exists():
            self.clipboard_clear()
            self.clipboard_append(f.read_text(encoding="utf-8"))
            self.log("پرامپت تامنیل در کلیپ‌بورد کپی شد.", "SUCCESS")

    def open_dropzone_folder(self):
        if self.current_project_dir:
            dropzone = self.current_project_dir / "03_Raw_DropZone"
            if dropzone.exists():
                open_file_or_folder(dropzone)

    # -------------------------------------------------------------
    # Google Flow (Terminal CDP) Handlers
    # -------------------------------------------------------------
    def on_flow_launch_clicked(self):
        self.log("🌐 در حال راه‌اندازی مرورگر Google Chrome (پورت CDP 9222)...", "INFO")
        self.flow_launch_btn.configure(state="disabled")

        def worker():
            try:
                ok = self.flow_automator.launch_chrome()
                if ok:
                    self.after(0, lambda: self.flow_status_pill.set_status("مرورگر باز شد - نیازمند لاگین در اکانت ⚠️", "warning"))
                else:
                    self.after(0, lambda: self.flow_status_pill.set_status("خطا در باز کردن کروم 🔴", "danger"))
            except Exception as e:
                self.log(f"خطا در اجرای flow launch: {e}", "ERROR")
                self.after(0, lambda: self.flow_status_pill.set_status("خطا در اجرا 🔴", "danger"))
            finally:
                self.after(0, lambda: self.flow_launch_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def on_flow_doctor_clicked(self):
        self.log("🩺 در حال بررسی وضعیت اتصال به Google Flow (flow doctor)...", "INFO")
        self.flow_doctor_btn.configure(state="disabled")

        def worker():
            try:
                diag = self.flow_automator.run_diagnostics()
                cdp_open = diag.get("cdpOpen", False)
                auth_ok = diag.get("googleAuthenticated", False)

                if cdp_open and auth_ok:
                    self.after(0, lambda: self.flow_status_pill.set_status("🟢 متصل و آماده (Port 9222 & Auth OK)", "success"))
                elif cdp_open and not auth_ok:
                    self.after(0, lambda: self.flow_status_pill.set_status("🔴 نیازمند لاگین در کروم (Port Open)", "danger"))
                elif not cdp_open:
                    self.after(0, lambda: self.flow_status_pill.set_status("🔴 پورت 9222 بسته (کروم باز نیست)", "danger"))
                else:
                    self.after(0, lambda: self.flow_status_pill.set_status("🔴 خطا در اتصال", "danger"))
            except Exception as e:
                self.log(f"خطا در بررسی flow doctor: {e}", "ERROR")
                self.after(0, lambda: self.flow_status_pill.set_status("خطا در بررسی 🔴", "danger"))
            finally:
                self.after(0, lambda: self.flow_doctor_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def on_generate_flow_thumbnail_clicked(self):
        if not self.current_project_dir:
            messagebox.showwarning("پروژه مشخص نشده", "ابتدا پروژه را انتخاب یا ایجاد کنید.")
            return

        thumb_prompt = ""
        thumb_prompt_file = self.current_project_dir / "02_AI_Brain_JSON" / "thumbnail_bg_prompt.txt"
        if thumb_prompt_file.exists():
            content = thumb_prompt_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "THUMBNAIL BACKGROUND PROMPT" in line and i + 1 < len(lines):
                    thumb_prompt = lines[i + 1].strip()
                    break
            if not thumb_prompt:
                thumb_prompt = content.strip()

        if not thumb_prompt and self.current_brain_data:
            thumb_prompt = self.current_brain_data.get("thumbnail_data", {}).get("bg_image_prompt", "")

        if not thumb_prompt:
            messagebox.showwarning("پرامپت تامنیل یافت نشد", "پرامپت تصویر تامنیل در پوشه 02_AI_Brain_JSON یافت نشد.")
            return

        flow_cfg = self.config.get("flow_config", {})
        model = flow_cfg.get("default_image_model", "Nano Banana Pro")

        self.flow_thumb_btn.configure(state="disabled")
        self.set_progress(0.2, indeterminate=True)
        self.log(f"🖼 شروع تولید خودکار تصویر پس‌زمینه تامنیل در Google Flow (مدل: {model})...")

        def worker():
            try:
                ok = self.flow_automator.generate_thumbnail_bg(
                    project_root=self.current_project_dir,
                    bg_prompt=thumb_prompt,
                    model=model,
                )

                def done():
                    self.flow_thumb_btn.configure(state="normal")
                    self.set_progress(1.0)
                    self.refresh_dropzone_checklist()
                    if ok:
                        messagebox.showinfo("موفقیت", "تصویر پس‌زمینه تامنیل با موفقیت تولید و در Audio_BGM ذخیره شد.")
                    else:
                        messagebox.showerror("خطا", "تولید تصویر پس‌زمینه تامنیل با خطا مواجه شد. لطفاً کنسول لاگ را بررسی کنید.")

                self.after(0, done)
            except Exception as e:
                self.log(f"خطا در تولید تامنیل: {e}", "ERROR")
                self.after(0, lambda: self.flow_thumb_btn.configure(state="normal"))
                self.after(0, lambda: self.set_progress(0.0))

        threading.Thread(target=worker, daemon=True).start()

    def on_run_flow_pipeline_clicked(self):
        if not self.current_project_dir:
            messagebox.showwarning("پروژه مشخص نشده", "ابتدا پروژه را انتخاب یا ایجاد کنید.")
            return

        flow_json_path = self.current_project_dir / "02_AI_Brain_JSON" / "flow.json"
        if not flow_json_path.exists():
            messagebox.showwarning("فایل flow.json یافت نشد", "لطفاً ابتدا کد JSON را پردازش کنید تا فایل flow.json تولید شود.")
            return

        dry_run = self.flow_dry_run_var.get()
        self.flow_run_pipeline_btn.configure(state="disabled")
        self.set_progress(0.1, indeterminate=True)

        def worker():
            try:
                # Diagnostics check before live generation
                if not dry_run:
                    self.log("🩺 بررسی وضعیت اتصال مرورگر قبل از شروع تولید راش‌ها...", "INFO")
                    diag = self.flow_automator.run_diagnostics()
                    cdp_open = diag.get("cdpOpen", False)
                    auth_ok = diag.get("googleAuthenticated", False)

                    if not (cdp_open and auth_ok):
                        msg = "اتصال به Google Flow آماده نیست!\n\n"
                        if not cdp_open:
                            msg += "• پورت 9222 مرورگر کروم باز نیست. لطفاً ابتدا دکمه «۱. باز کردن کروم (flow launch)» را بزنید.\n"
                        if not auth_ok:
                            msg += "• در مرورگر کروم بازشده وارد حساب کاربری گوگل خود شوید.\n"
                        self.log(f"❌ {msg}", "ERROR")
                        self.after(0, lambda: messagebox.showerror("عدم اتصال به گوگل فلو", msg))
                        self.after(0, lambda: self.flow_run_pipeline_btn.configure(state="normal"))
                        self.after(0, lambda: self.set_progress(0.0))
                        return

                self.log("🚀 آغاز پایپلاین تولید راش‌های ویدیویی در Google Flow...", "INFO")
                ok = self.flow_automator.run_declarative_pipeline(
                    project_root=self.current_project_dir,
                    dry_run=dry_run,
                )

                def done():
                    self.flow_run_pipeline_btn.configure(state="normal")
                    self.set_progress(1.0)
                    self.refresh_dropzone_checklist()
                    if ok:
                        messagebox.showinfo("عملیات پایان یافت", "تولید و دانلود راش‌های ویدیویی Google Flow با موفقیت انجام شد.")
                    else:
                        messagebox.showwarning("پایان با اخطار", "اجرای پایپلاین به پایان رسید اما ممکن است برخی فایل‌ها دانلود نشده باشند. لطفاً کنسول لاگ و چک‌لیست گام ۴ را بررسی کنید.")

                self.after(0, done)
            except Exception as e:
                self.log(f"خطا در اجرای پایپلاین: {e}", "ERROR")
                self.after(0, lambda: self.flow_run_pipeline_btn.configure(state="normal"))
                self.after(0, lambda: self.set_progress(0.0))

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------
    # Step 3 Workflows: Build Workspace & Subtitles
    # -------------------------------------------------------------
    def on_build_workspace_clicked(self):
        if not self.current_project_dir:
            messagebox.showwarning("خطا", "پروژه‌ای انتخاب نشده است.")
            return

        model_size = self.step3_model_combo.get()
        self.build_workspace_btn.configure(state="disabled")
        self.set_progress(0.1, indeterminate=True)
        self.log("=== شروع ساخت پروژه پریمیر و تولید زیرنویس هوشمند ===")

        def worker():
            try:
                # 1. Migrate safely to active workspace
                active_base = Path(self.config.get("active_workspace_path", "e:\\Zighoosh_Projects\\Active"))
                self.current_project_dir = migrate_to_active_workspace(
                    self.current_project_dir,
                    active_base,
                    log_cb=self.log,
                )

                # 2. Standardize media renaming & audio extraction
                self.log("در حال نام‌گذاری استاندارد و لینک‌سازی راش‌ها...")
                link_results = link_and_rename_raw_media(self.current_project_dir, log_cb=self.log)

                # 3. Generate subtitles
                self.log(f"در حال تولید زیرنویس‌های خام .srt با موتور هوشمند (مدل: {model_size})...")
                sub_results = generate_all_plan_subtitles(
                    self.current_project_dir,
                    model_size=model_size,
                    log_cb=self.log,
                )

                # 4. Deploy mother templates
                templates_dir = Path(self.config.get("templates_path", "App_Templates"))
                job_id = self.current_job_data.get("job_id", "Job") if self.current_job_data else "Project"
                prproj_path, ai_path = deploy_project_templates(
                    self.current_project_dir,
                    templates_dir,
                    job_id=job_id,
                    log_cb=self.log,
                )

                self.after(0, lambda: self.on_build_workspace_success(prproj_path))
            except Exception as e:
                logger.error(f"Workspace build error: {e}")
                self.after(0, lambda: self.on_build_workspace_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_build_workspace_success(self, prproj_path: Optional[Path]):
        self.build_workspace_btn.configure(state="normal")
        self.open_premiere_btn.configure(state="normal")
        self.open_subs_btn.configure(state="normal")
        self.set_progress(1.0)

        self.log("پروژه پریمیر و زیرنویس‌ها با موفقیت ساخته شدند! ✅", "SUCCESS")

        # Auto open premiere if enabled
        if self.config.get("auto_open_premiere", True) and prproj_path and prproj_path.exists():
            self.log(f"در حال بازگشایی خودکار پروژه پریمیر: {prproj_path.name}")
            open_file_or_folder(prproj_path)

        # Open subtitles directory
        subs_dir = self.current_project_dir / "04_Premiere_Workspace" / "Subtitles"
        if subs_dir.exists():
            open_file_or_folder(subs_dir)

        messagebox.showinfo("پروژه آماده است", "پروژه پریمیر پرو و فایل‌های زیرنویس استاندارد با موفقیت آماده شدند.")

    def on_build_workspace_error(self, err_msg: str):
        self.build_workspace_btn.configure(state="normal")
        self.set_progress(0.0)
        self.log(f"خطا در ساخت ورک‌اسپیس: {err_msg}", "ERROR")
        messagebox.showerror("خطا", f"عملیات ناموفق بود:\n{err_msg}")

    def open_premiere_project(self):
        if not self.current_project_dir:
            return
        p_dir = self.current_project_dir / "04_Premiere_Workspace"
        prproj_files = list(p_dir.glob("*.prproj"))
        if prproj_files:
            open_file_or_folder(prproj_files[0])
        else:
            messagebox.showinfo("پیام", "فایل پروژه پریمیر هنوز در این مسیر ساخته نشده است.")

    def open_subtitles_folder(self):
        if not self.current_project_dir:
            return
        s_dir = self.current_project_dir / "04_Premiere_Workspace" / "Subtitles"
        if s_dir.exists():
            open_file_or_folder(s_dir)

    # -------------------------------------------------------------
    # Step 4 Workflows: Check Exports & Archive
    # -------------------------------------------------------------
    def check_exports_status(self):
        if not self.current_project_dir:
            self.export_status_lbl.configure(text="پروژه‌ای انتخاب نشده است.", text_color=DANGER_COLOR)
            return

        exports = check_final_exports(self.current_project_dir)
        if exports:
            names = ", ".join([e.name for e in exports])
            self.export_status_lbl.configure(
                text=f"خروجی نهایی آماده است ({len(exports)} فایل): {names} ✅",
                text_color=SUCCESS_COLOR,
            )
            self.log(f"فایل‌های خروجی رندر شده مشاهده شدند: {names}", "SUCCESS")
        else:
            self.export_status_lbl.configure(
                text="هیچ فایل خروجی در 06_Final_Exports یافت نشد! ⚠️",
                text_color=WARNING_COLOR,
            )
            self.log("هشدار: فایل رندر نهایی در پوشه خروجی یافت نشد.", "WARNING")

    def open_final_exports_folder(self):
        if not self.current_project_dir:
            return
        exp_dir = self.current_project_dir / "06_Final_Exports"
        if exp_dir.exists():
            open_file_or_folder(exp_dir)

    def on_archive_project_clicked(self):
        if not self.current_project_dir:
            messagebox.showwarning("خطا", "پروژه‌ای انتخاب نشده است.")
            return

        confirm = messagebox.askyesno(
            "تایید بایگانی",
            "آیا مطمئن هستید که تدوین به اتمام رسیده و مایلید این پروژه را به آرشیو دائمی منتقل کنید؟",
        )
        if not confirm:
            return

        archive_base = Path(self.config.get("archive_path", "e:\\Zighoosh_Projects\\Archive"))
        cleanup = self.clean_raw_var.get()

        self.set_progress(0.5, indeterminate=True)
        self.log("در حال بایگانی پروژه در مسیر دائمی...")

        success, msg, archived_path = archive_project(
            self.current_project_dir,
            archive_base,
            cleanup_raw=cleanup,
            log_cb=self.log,
        )
        self.set_progress(1.0)

        if success:
            self.log(f"پروژه با موفقیت به آرشیو منتقل شد: {archived_path}", "SUCCESS")
            messagebox.showinfo("بایگانی تکمیل شد", msg)
            self.current_project_dir = archived_path
            self.project_badge.set_status("آرشیو شده 📦", "neutral")
        else:
            self.log(msg, "ERROR")
            messagebox.showerror("خطا در بایگانی", msg)


def run_app():
    app = ReelForgeApp()
    app.mainloop()
