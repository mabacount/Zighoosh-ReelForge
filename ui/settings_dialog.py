"""
Zighoosh ReelForge - Settings Dialog
Minimalist Apple/Google Modal for managing workspace paths and engine settings.
"""

from __future__ import annotations

import json
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
    Modal window for configuring workspace paths and Whisper model.
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

        self.title("تنظیمات مسیرها و هوش مصنوعی | Zighoosh ReelForge")
        self.geometry("640x580")
        self.resizable(False, False)
        self.configure(fg_color=SURFACE_CARD)

        # Center on parent window
        self.transient(master)
        self.grab_set()

        self.build_ui()

    def build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 10))

        title = ctk.CTkLabel(
            header,
            text="تنظیمات سیستم و مسیرهای کاری",
            font=FONT_HEADER,
            text_color=TEXT_PRIMARY,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="مسیرهای پیش‌فرض پروژه‌ها، قالب‌های مادر و تنظیمات مدل Forced Alignment را مشخص کنید.",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        # Main Card Container
        card = CardFrame(self, fg_color=SURFACE_INNER)
        card.pack(fill="both", expand=True, padx=24, pady=10)

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
            f_frame = ctk.CTkFrame(card, fg_color="transparent")
            f_frame.pack(fill="x", padx=16, pady=8)

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

        # Model & Options Row
        opts_frame = ctk.CTkFrame(card, fg_color="transparent")
        opts_frame.pack(fill="x", padx=16, pady=(12, 16))

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
        footer.pack(fill="x", padx=24, pady=(10, 20))

        cancel_btn = SecondaryButton(footer, text="انصراف", width=100, command=self.destroy)
        cancel_btn.pack(side="left")

        save_btn = PrimaryButton(footer, text="ذخیره تنظیمات", width=140, command=self.save_settings)
        save_btn.pack(side="right")

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

        # Save to config.json
        config_path = Path("config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

        if self.on_save_cb:
            self.on_save_cb(self.config)

        self.destroy()
