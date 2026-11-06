"""
Zighoosh ReelForge - UI Theme & Design Tokens
Minimalist Apple & Google Desktop Aesthetic (Dark Mode)
"""

from __future__ import annotations

# Color Palette
BG_MAIN = "#0C0D12"           # Deep matte backdrop
SURFACE_CARD = "#14161F"      # Primary card surface
SURFACE_INNER = "#1B1E29"     # Sub-card / input field background
SURFACE_HOVER = "#242735"     # Hover state
BORDER_COLOR = "#282C3D"      # Subtle hairline border
BORDER_ACTIVE = "#0A84FF"     # Active / focused accent border

# Brand & System Accents
ACCENT_PRIMARY = "#0A84FF"    # Apple System Blue
ACCENT_HOVER = "#0071E3"      # Darker blue on hover
ACCENT_SECONDARY = "#38BDF8"  # Google Sky / Cyan
ACCENT_GLOW = "rgba(10, 132, 255, 0.15)"

# Status & Feedback
SUCCESS_COLOR = "#10B981"     # Emerald Green
SUCCESS_BG = "#064E3B"
WARNING_COLOR = "#F59E0B"     # Amber
WARNING_BG = "#78350F"
DANGER_COLOR = "#EF4444"      # Coral Red
DANGER_BG = "#7F1D1D"

# Typography Colors
TEXT_PRIMARY = "#F8FAFC"      # Clean high-contrast white
TEXT_SECONDARY = "#94A3B8"    # Apple neutral light gray
TEXT_MUTED = "#64748B"        # Low-emphasis slate
TEXT_CODE = "#38BDF8"         # Sky cyan for code / paths

# Font Stacks
FONT_FAMILY = "Segoe UI"
FONT_BOLD = ("Segoe UI", 13, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_HEADER = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_CAPTION = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 11)

# Dimensions & Geometry
CORNER_RADIUS_CARD = 12
CORNER_RADIUS_BTN = 8
CORNER_RADIUS_PILL = 16
CORNER_RADIUS_INPUT = 8
