"""
Zighoosh ReelForge - Reusable UI Components
Minimalist Apple & Google Desktop Styled Controls
"""

from __future__ import annotations

import datetime
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from ui.theme import (
    ACCENT_HOVER,
    ACCENT_PRIMARY,
    ACCENT_SECONDARY,
    BORDER_ACTIVE,
    BORDER_COLOR,
    CORNER_RADIUS_BTN,
    CORNER_RADIUS_CARD,
    CORNER_RADIUS_INPUT,
    CORNER_RADIUS_PILL,
    DANGER_BG,
    DANGER_COLOR,
    FONT_BODY,
    FONT_BOLD,
    FONT_CAPTION,
    FONT_MONO,
    FONT_TITLE,
    SUCCESS_BG,
    SUCCESS_COLOR,
    SURFACE_CARD,
    SURFACE_HOVER,
    SURFACE_INNER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_BG,
    WARNING_COLOR,
)


class CardFrame(ctk.CTkFrame):
    """
    Apple-inspired sleek container card with subtle 1px border and rounded corners.
    """

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=kwargs.pop("fg_color", SURFACE_CARD),
            border_color=kwargs.pop("border_color", BORDER_COLOR),
            border_width=kwargs.pop("border_width", 1),
            corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_CARD),
            **kwargs,
        )


class PrimaryButton(ctk.CTkButton):
    """
    High-emphasis Apple System Blue action button.
    """

    def __init__(self, master, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=kwargs.pop("fg_color", ACCENT_PRIMARY),
            hover_color=kwargs.pop("hover_color", ACCENT_HOVER),
            text_color=kwargs.pop("text_color", TEXT_PRIMARY),
            corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_BTN),
            font=kwargs.pop("font", FONT_BOLD),
            height=kwargs.pop("height", 38),
            cursor="hand2",
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    """
    Subtle bordered button for secondary actions.
    """

    def __init__(self, master, text: str, command=None, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=kwargs.pop("fg_color", SURFACE_INNER),
            hover_color=kwargs.pop("hover_color", SURFACE_HOVER),
            border_color=kwargs.pop("border_color", BORDER_COLOR),
            border_width=kwargs.pop("border_width", 1),
            text_color=kwargs.pop("text_color", TEXT_PRIMARY),
            corner_radius=kwargs.pop("corner_radius", CORNER_RADIUS_BTN),
            font=kwargs.pop("font", FONT_BODY),
            height=kwargs.pop("height", 36),
            cursor="hand2",
            **kwargs,
        )


class StatusPill(ctk.CTkFrame):
    """
    Compact status indicator pill badge (e.g. '✅ آماده' or '⚠️ در انتظار').
    """

    def __init__(
        self,
        master,
        text: str = "آماده",
        state: str = "success",  # "success", "warning", "danger", "neutral"
        **kwargs,
    ):
        colors = {
            "success": (SUCCESS_BG, SUCCESS_COLOR),
            "warning": (WARNING_BG, WARNING_COLOR),
            "danger": (DANGER_BG, DANGER_COLOR),
            "neutral": (SURFACE_INNER, TEXT_SECONDARY),
            "active": ("#0F2D4A", ACCENT_SECONDARY),
        }
        bg, fg = colors.get(state, (SURFACE_INNER, TEXT_SECONDARY))

        super().__init__(
            master,
            fg_color=bg,
            corner_radius=CORNER_RADIUS_PILL,
            height=26,
            **kwargs,
        )
        self.label = ctk.CTkLabel(
            self,
            text=text,
            text_color=fg,
            font=FONT_CAPTION,
            padx=10,
            pady=2,
        )
        self.label.pack(fill="both", expand=True)

    def set_status(self, text: str, state: str = "success"):
        colors = {
            "success": (SUCCESS_BG, SUCCESS_COLOR),
            "warning": (WARNING_BG, WARNING_COLOR),
            "danger": (DANGER_BG, DANGER_COLOR),
            "neutral": (SURFACE_INNER, TEXT_SECONDARY),
            "active": ("#0F2D4A", ACCENT_SECONDARY),
        }
        bg, fg = colors.get(state, (SURFACE_INNER, TEXT_SECONDARY))
        self.configure(fg_color=bg)
        self.label.configure(text=text, text_color=fg)


class LiveConsole(CardFrame):
    """
    Modern embedded live console widget with timestamps and auto-scroll.
    Runs smoothly without locking the GUI.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Header bar
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))

        title_lbl = ctk.CTkLabel(
            header,
            text="کنسول لاگ زنده سیستم",
            font=FONT_BOLD,
            text_color=TEXT_SECONDARY,
        )
        title_lbl.pack(side="left")

        clear_btn = ctk.CTkButton(
            header,
            text="پاکسازی",
            width=65,
            height=24,
            fg_color="transparent",
            hover_color=SURFACE_HOVER,
            text_color=TEXT_MUTED,
            font=FONT_CAPTION,
            command=self.clear_logs,
        )
        clear_btn.pack(side="right", padx=4)

        # Text Area with modern dark styling
        self.textbox = ctk.CTkTextbox(
            self,
            fg_color=SURFACE_INNER,
            text_color=TEXT_PRIMARY,
            font=FONT_MONO,
            corner_radius=CORNER_RADIUS_INPUT,
            border_width=0,
            wrap="word",
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def log(self, message: str, level: str = "INFO"):
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        prefix = f"[{now_str}] "
        if level == "SUCCESS":
            prefix += "✔ "
        elif level == "WARNING":
            prefix += "▲ "
        elif level == "ERROR":
            prefix += "✖ "

        full_line = f"{prefix}{message}\n"
        self.textbox.insert("end", full_line)
        self.textbox.see("end")

    def clear_logs(self):
        self.textbox.delete("1.0", "end")
