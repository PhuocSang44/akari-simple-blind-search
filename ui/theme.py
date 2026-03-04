"""Light / Dark colour themes for the Akari UI."""

from __future__ import annotations
from typing import Dict, Tuple

Color = Tuple[int, int, int]
Theme = Dict[str, Color]

# ─── Dark theme (default) ─────────────────────────────────────────

DARK: Theme = {
    # layout backgrounds
    "bg":             (18,  18,  30),
    "panel_bg":       (24,  28,  42),
    "board_bg":       (30,  32,  48),
    "info_panel_bg":  (20,  24,  38),
    "toolbar_bg":     (14,  16,  26),

    # grid & cells
    "grid":           (50,  54,  72),
    "wall":           (35,  38,  55),   # plain walls same shade as numbered bg
    "wall_num_bg":    (35,  38,  55),
    "wall_num_txt":  (230, 230, 240),
    "empty":         (195, 200, 215),
    "lit":           (255, 248, 200),
    "lit_strong":    (255, 238, 140),

    # text
    "text":          (235, 235, 245),
    "text_dim":      (140, 145, 165),

    # semantic
    "accent":        (  0, 196, 255),
    "success":       (  0, 230, 130),
    "error":         (255,  82,  82),

    # bevel highlights (wall)
    "bevel_hi":      ( 60,  62,  88),
    "bevel_lo":      ( 15,  15,  20),
}

# ─── Light theme ──────────────────────────────────────────────────

LIGHT: Theme = {
    # layout backgrounds
    "bg":             (230, 234, 248),
    "panel_bg":       (215, 220, 238),
    "board_bg":       (255, 255, 255),   # white board
    "info_panel_bg":  (210, 214, 232),
    "toolbar_bg":     (195, 200, 222),

    # grid & cells
    "grid":           (195, 198, 212),
    "wall":           ( 48,  50,  62),   # dark-slate walls
    "wall_num_bg":    ( 48,  50,  62),
    "wall_num_txt":  (255, 255, 255),
    "empty":         (238, 240, 248),   # off-white empty cells
    "lit":           (255, 243, 160),
    "lit_strong":    (255, 228,  60),

    # text
    "text":          ( 25,  30,  60),
    "text_dim":      ( 95, 100, 140),

    # semantic
    "accent":        (  0,  90, 200),
    "success":       (  0, 140,  75),
    "error":         (200,  45,  45),

    # bevel highlights (wall)
    "bevel_hi":      ( 72,  75,  92),
    "bevel_lo":      ( 28,  28,  38),
}
