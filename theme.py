"""Color palettes for Arthos. Pick one with the ARTHOS_THEME env var."""
from __future__ import annotations

import os

PALETTES = {
    "indigo": {"name": "Royal Indigo", "accent": "#4F46E5", "accent2": "#7C3AED"},
    "sapphire": {"name": "Sapphire", "accent": "#1D4ED8", "accent2": "#0EA5E9"},
    "plum": {"name": "Plum & Gold", "accent": "#6D28D9", "accent2": "#D97706"},
    "midnight": {"name": "Midnight & Coral", "accent": "#1E293B", "accent2": "#F43F5E"},
}
DEFAULT = "indigo"

THEME = os.environ.get("ARTHOS_THEME", DEFAULT).lower()
P = PALETTES.get(THEME, PALETTES[DEFAULT])

ACCENT = P["accent"]
ACCENT2 = P["accent2"]
INK = "#0F172A"
MUTED = "#64748B"
FAINT = "#94A3B8"
GRID = "#EEF0F3"
BORDER = "#E5E7EB"
BG = "#F8FAFC"
UP = "#059669"
DOWN = "#E11D48"


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


ACCENT_SOFT = rgba(ACCENT, 0.18)
GRADIENT = f"linear-gradient(135deg, {ACCENT} 0%, {ACCENT2} 100%)"
BAR_GRADIENT = f"linear-gradient(90deg, {ACCENT} 0%, {ACCENT2} 100%)"
