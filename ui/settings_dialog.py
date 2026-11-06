"""
Zighoosh ReelForge - Settings Dialog
Minimalist Apple/Google Modal for managing workspace paths, Whisper model, and Google Flow settings.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk

from ui.components import CardFrame, PrimaryButton, SecondaryButton
from ui.theme import (
    ACCENT_PRIMARY,
    BORDER_COLOR,
    CORNER_RADIUS_CARD,
    CORNER_RADIUS_INPUT,
    FONT_BODY,
    FONT_BOLD,
    FONT_CAPTION,
    FONT_HEADER,
    FONT_TITLE,
    SURFACE_CARD,
    SURFACE_INNER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SettingsDialog(ctk.CTkToplevel):
    """
    Modal window for configuring workspace paths, Whisper model, and Google Flow settings.
    """

    def __init__(
        self,
        master,
        config: Dict[str, Any],
        on_save_cb: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        super().__init__(master)
        self.config = config.copy()
        self.on_save_cb = on_save_cb

        self.title("تنظیمات سیستم و هوش مصنوعی | Zighoosh ReelForge")
        self.geometry("680x730")
        self.minsize(620, 640)
        self.configure(fg_color=SURFACE_CARD)

        # Center on parent window
        self.transient(master)
        self.grab_set()

        self.build_ui()

    def build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(16, 8))

        title = ctk.CTkLabel(
            header,
            text="تنظیمات سیستم و مسیرهای کاری",
            font=FONT_HEADER,
            text_color=TEXT_PRIMARY,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="مسیرهای پیش‌فرض پروژه‌ها، قالب‌های مادر، تنظیمات زیرنویس و Google Flow را مشخص کنید.",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        # Main Scrollable Container
        scroll_card = ctk.CTkScrollableFrame(
            self,
            fg_color=SURFACE_INNER,
            corner_radius=CORNER_RADIUS_CARD,
        )
        scroll_card.pack(fill="both", expand=True, padx=24, pady=8)

        # Form fields
        self.entries: Dict[str, ctk.CTkEntry] = {}

        fields = [
            (
                "downloads_path",
                "مسیر موقت دریافت (Downloads / Ingest Path):",
                "پوشه‌ای که در گام اول پروژه اولیه در آن ساخته می‌شود",
            ),
            (
                "active_workspace_path",
                "مسیر دائمی پروژه‌ها (Active Workspace Path):",
                "مسیر نهایی پروژه‌ها قبل از باز شدن در پریمیر (جلوگیری از شکستن لینک‌ها)",
            ),
            (
                "archive_path",
                "مسیر بایگانی دائمی (Archive Path):",
                "پوشه ذخیره دائمی پروژه‌های تکمیل و تدوین شده",
            ),
            (
                "templates_path",
                "مسیر قالب‌های مادر (Templates Path):",
                "پوشه حاوی Template_Reels.prproj و Template_Thumb.ai",
            ),
        ]

        for key, label_text, hint in fields:
            f_frame = ctk.CTkFrame(scroll_card, fg_color="transparent")
            f_frame.pack(fill="x", padx=12, pady=6)

            lbl_row = ctk.CTkFrame(f_frame, fg_color="transparent")
            lbl_row.pack(fill="x")

            lbl = ctk.CTkLabel(lbl_row, text=label_text, font=FONT_BOLD, text_color=TEXT_PRIMARY)
            lbl.pack(side="left")

            row = ctk.CTkFrame(f_frame, fg_color="transparent")
            row.pack(fill="x", pady=(4, 0))

            entry = ctk.CTkEntry(
                row,
                fg_color=SURFACE_CARD,
                border_color=BORDER_COLOR,
                text_color=TEXT_PRIMARY,
                corner_radius=CORNER_RADIUS_INPUT,
                height=34,
            )
            entry.insert(0, str(self.config.get(key, "")))
            entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.entries[key] = entry

            browse_btn = SecondaryButton(
                row,
                text="انتخاب...",
                width=80,
                height=34,
                command=lambda k=key: self.browse_folder(k),
            )
            browse_btn.pack(side="right")

            hint_lbl = ctk.CTkLabel(f_frame, text=hint, font=FONT_CAPTION, text_color=TEXT_MUTED)
            hint_lbl.pack(anchor="w", pady=(2, 0))

        # Google Flow Settings Section
        flow_cfg = self.config.get("flow_config", {})

        flow_card = CardFrame(scroll_card, fg_color=SURFACE_CARD)
        flow_card.pack(fill="x", padx=12, pady=(10, 8))

        flow_header = ctk.CTkFrame(flow_card, fg_color="transparent")
        flow_header.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            flow_header,
            text="تنظیمات پیش‌فرض Google Flow (Terminal CDP):",
            font=FONT_BOLD,
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        flow_grid = ctk.CTkFrame(flow_card, fg_color="transparent")
        flow_grid.pack(fill="x", padx=14, pady=(0, 12))

        # Default Video Model
        v_col = ctk.CTkFrame(flow_grid, fg_color="transparent")
        v_col.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(v_col, text="مدل پیش‌فرض ویدیو:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).pack(anchor="w")
        self.flow_video_combo = ctk.CTkComboBox(
            v_col,
            values=["Veo 3.1 - Fast", "Veo 3.1 - Quality", "Veo 3.1 - Lite", "Omni 1.1 Flash"],
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            dropdown_fg_color=SURFACE_CARD,
            dropdown_text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=34,
        )
        self.flow_video_combo.set(flow_cfg.get("default_video_model", "Veo 3.1 - Fast"))
        self.flow_video_combo.pack(fill="x", pady=(4, 0))

        # Default Image Model
        img_col = ctk.CTkFrame(flow_grid, fg_color="transparent")
        img_col.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkLabel(img_col, text="مدل پیش‌فرض تصویر:", font=FONT_CAPTION, text_color=TEXT_SECONDARY).pack(anchor="w")
        self.flow_image_combo = ctk.CTkComboBox(
            img_col,
            values=["Nano Banana Pro", "Nano Banana 2.1", "Nano Banana 2 Lite"],
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            dropdown_fg_color=SURFACE_CARD,
            dropdown_text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=34,
        )
        self.flow_image_combo.set(flow_cfg.get("default_image_model", "Nano Banana Pro"))
        self.flow_image_combo.pack(fill="x", pady=(4, 0))

        # Timeout Field
        timeout_col = ctk.CTkFrame(flow_grid, fg_color="transparent")
        timeout_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(timeout_col, text="مهلت تایم‌اوت (ثانیه):", font=FONT_CAPTION, text_color=TEXT_SECONDARY).pack(anchor="w")
        self.flow_timeout_entry = ctk.CTkEntry(
            timeout_col,
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=34,
        )
        self.flow_timeout_entry.insert(0, str(flow_cfg.get("generation_timeout_sec", 300)))
        self.flow_timeout_entry.pack(fill="x", pady=(4, 0))

        # Chrome Profile Directory Selection
        prof_frame = ctk.CTkFrame(flow_card, fg_color="transparent")
        prof_frame.pack(fill="x", padx=14, pady=(0, 12))

        prof_lbl_row = ctk.CTkFrame(prof_frame, fg_color="transparent")
        prof_lbl_row.pack(fill="x")

        ctk.CTkLabel(
            prof_lbl_row,
            text="مسیر پروفایل کروم (ذخیره همیشگی لاگین اکانت گوگل):",
            font=FONT_CAPTION,
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        # Quick preset buttons
        default_flow_dir = "~/.config/google-chrome-flow"
        chrome_default_user_data = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data")

        preset_row = ctk.CTkFrame(prof_frame, fg_color="transparent")
        preset_row.pack(fill="x", pady=(2, 4))

        use_flow_prof_btn = SecondaryButton(
            preset_row,
            text="پروفایل اختصاصی Flow",
            width=140,
            height=26,
            command=lambda: self.set_profile_path(default_flow_dir),
        )
        use_flow_prof_btn.pack(side="left", padx=(0, 6))

        use_system_chrome_btn = SecondaryButton(
            preset_row,
            text="پروفایل کروم اصلی ویندوز (اکانت فعلی شما)",
            width=230,
            height=26,
            command=lambda: self.set_profile_path(chrome_default_user_data),
        )
        use_system_chrome_btn.pack(side="left")

        prof_input_row = ctk.CTkFrame(prof_frame, fg_color="transparent")
        prof_input_row.pack(fill="x")

        self.flow_profile_entry = ctk.CTkEntry(
            prof_input_row,
            fg_color=SURFACE_INNER,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=34,
        )
        self.flow_profile_entry.insert(0, str(flow_cfg.get("chrome_profile_dir", default_flow_dir)))
        self.flow_profile_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        prof_browse_btn = SecondaryButton(
            prof_input_row,
            text="انتخاب...",
            width=80,
            height=34,
            command=self.browse_flow_profile_folder,
        )
        prof_browse_btn.pack(side="right")

        # Whisper & Other Options Row
        opts_frame = ctk.CTkFrame(scroll_card, fg_color="transparent")
        opts_frame.pack(fill="x", padx=12, pady=(8, 12))

        # Whisper Model selection
        model_col = ctk.CTkFrame(opts_frame, fg_color="transparent")
        model_col.pack(side="left", fill="x", expand=True)

        m_lbl = ctk.CTkLabel(model_col, text="سایز مدل Whisper (تراز زیرنویس):", font=FONT_BOLD, text_color=TEXT_PRIMARY)
        m_lbl.pack(anchor="w")

        self.model_combo = ctk.CTkComboBox(
            model_col,
            values=["base", "small", "medium", "large-v3"],
            fg_color=SURFACE_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            dropdown_fg_color=SURFACE_CARD,
            dropdown_text_color=TEXT_PRIMARY,
            corner_radius=CORNER_RADIUS_INPUT,
            height=34,
        )
        self.model_combo.set(self.config.get("whisper_model", "base"))
        self.model_combo.pack(anchor="w", pady=(4, 0))

        # Auto open premiere switch
        switch_col = ctk.CTkFrame(opts_frame, fg_color="transparent")
        switch_col.pack(side="right", padx=(20, 0))

        self.open_pr_var = ctk.BooleanVar(value=self.config.get("auto_open_premiere", True))
        self.pr_switch = ctk.CTkSwitch(
            switch_col,
            text="باز کردن خودکار پریمیر بعد از ساخت",
            variable=self.open_pr_var,
            font=FONT_BODY,
            text_color=TEXT_PRIMARY,
            progress_color=ACCENT_PRIMARY,
        )
        self.pr_switch.pack(pady=10)

        # Footer Actions
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(8, 16))

        cancel_btn = SecondaryButton(footer, text="انصراف", width=100, command=self.destroy)
        cancel_btn.pack(side="left")

        save_btn = PrimaryButton(footer, text="ذخیره تنظیمات", width=140, command=self.save_settings)
        save_btn.pack(side="right")

    def set_profile_path(self, path_str: str):
        self.flow_profile_entry.delete(0, "end")
        self.flow_profile_entry.insert(0, path_str)

    def browse_flow_profile_folder(self):
        current_val = self.flow_profile_entry.get().strip()
        initial_dir = current_val if Path(os.path.expanduser(current_val)).exists() else str(Path.home())
        selected = filedialog.askdirectory(initialdir=initial_dir, title="انتخاب پوشه پروفایل کروم")
        if selected:
            self.set_profile_path(selected)

    def browse_folder(self, key: str):
        current_val = self.entries[key].get()
        initial_dir = current_val if Path(current_val).exists() else str(Path.home())
        selected = filedialog.askdirectory(initialdir=initial_dir, title="انتخاب پوشه")
        if selected:
            self.entries[key].delete(0, "end")
            self.entries[key].insert(0, selected)

    def save_settings(self):
        for key, entry in self.entries.items():
            self.config[key] = entry.get().strip()
        self.config["whisper_model"] = self.model_combo.get()
        self.config["auto_open_premiere"] = self.open_pr_var.get()

        # Update Flow config
        flow_cfg = self.config.get("flow_config", {})
        flow_cfg["default_video_model"] = self.flow_video_combo.get()
        flow_cfg["default_image_model"] = self.flow_image_combo.get()
        flow_cfg["chrome_profile_dir"] = self.flow_profile_entry.get().strip()
        try:
            flow_cfg["generation_timeout_sec"] = int(self.flow_timeout_entry.get().strip())
        except ValueError:
            flow_cfg["generation_timeout_sec"] = 300
        self.config["flow_config"] = flow_cfg

        # Save to config.json
        config_path = Path("config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if self.on_save_cb:
            self.on_save_cb(self.config)

        self.destroy()
