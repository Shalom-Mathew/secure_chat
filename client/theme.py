"""Design tokens shared by the GUI (and mirrored by the brag video).

Principles: dark surfaces with elevation (each layer is a step lighter), an 8-px spacing
rhythm, one accent colour per meaning (blue = you, green = secure, amber = ciphertext,
red = error/eavesdropper), consistent radii, and interaction feedback within ~150 ms.
"""

import tkinter.font as tkfont

# surfaces (elevation: BG < SURFACE < SURFACE2)
BG = "#0b0f14"
SURFACE = "#111a24"
SURFACE2 = "#16222f"
INPUT = "#0b1219"
BORDER = "#23344a"

# text
TEXT = "#e6edf3"
MUTED = "#93a4b5"
PLACEHOLDER = "#7f90a3"

# meaning colours
BLUE = "#2563eb"          # you / primary action
BLUE_HOVER = "#3b7bff"
BUBBLE_IN = "#223246"     # incoming message
GREEN = "#3ddc84"         # secure / online
GREEN_DK = "#1d6b47"
GREEN_BG = "#10281d"
GREEN_TX = "#8ff0bb"
GREEN_LINE = "#2e8f5f"
AMBER = "#ffcf7a"         # ciphertext
AMBER_BG = "#33261a"
RED = "#ff9c9c"           # error / eavesdropper
RED_BG = "#1a1216"

# spacing scale (8-px rhythm) and radii
SP1, SP2, SP3, SP4 = 8, 16, 24, 32
RADIUS = 18

FONT_CANDIDATES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Noto Sans", "DejaVu Sans", "Arial")
MONO_CANDIDATES = ("Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Courier New")


def pick_font(root, candidates, fallback):
    available = set(tkfont.families(root))
    return next((name for name in candidates if name in available), fallback)


def shade(hex_color: str, factor: float) -> str:
    """Lighten (factor > 1) or darken (factor < 1) a #rrggbb colour."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"
