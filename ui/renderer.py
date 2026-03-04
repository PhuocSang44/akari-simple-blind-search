"""Pygame-based board renderer for the Akari visualiser.

Draws the puzzle grid, bulbs (with a light-bulb icon), illumination glow,
wall cells, numbered constraints, and step highlights.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

import pygame

from core.board import Board
from core.types import Position
from ui.theme import DARK, Theme

# ─── theme-independent highlight / bulb colours ──────────────────

C_HL_PLACE      = ( 76, 200, 100)   # green
C_HL_REMOVE     = (244,  67,  54)   # red
C_HL_FORCED     = (170,  90, 230)   # purple
C_HL_CONTRA     = (255,  50,  50)   # bright red
C_HL_CANDIDATE  = (  0, 180, 255)   # cyan

C_BULB_FILL      = (255, 210,  50)
C_BULB_GLASS     = (255, 240, 120)
C_BULB_HIGHLIGHT = (255, 255, 220)
C_BULB_BASE      = (160, 140,  90)
C_RAY            = (255, 235, 100)

# Re-export from dark theme so existing imports in game_ui.py still work.
C_BG         = DARK["bg"]
C_PANEL_BG   = DARK["panel_bg"]
C_BOARD_BG   = DARK["board_bg"]
C_GRID       = DARK["grid"]
C_TEXT_WHITE = DARK["text"]
C_TEXT_DIM   = DARK["text_dim"]
C_ACCENT     = DARK["accent"]
C_SUCCESS    = DARK["success"]
C_ERROR      = DARK["error"]


# ─── renderer class ──────────────────────────────────────────────

class BoardRenderer:
    """Renderer that honours a swappable colour theme."""

    def __init__(self, theme: Theme = DARK) -> None:
        self._font_cache: Dict[int, pygame.font.Font] = {}
        self.theme: Theme = theme

    def set_theme(self, theme: Theme) -> None:
        """Swap the active colour theme at runtime."""
        self.theme = theme

    # ── fonts ─────────────────────────────────────────────────────

    def _font(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont("Segoe UI", size, bold=False)
        return self._font_cache[size]

    def _font_bold(self, size: int) -> pygame.font.Font:
        key = -size  # negative key for bold variant
        if key not in self._font_cache:
            self._font_cache[key] = pygame.font.SysFont("Segoe UI", size, bold=True)
        return self._font_cache[key]

    # ── main draw entry ───────────────────────────────────────────

    def draw(
        self,
        surface: pygame.Surface,
        board: Board,
        bulbs: Set[Position],
        lit: Set[Position],
        rect: pygame.Rect,
        highlight_pos: Optional[Position] = None,
        highlight_color: Optional[Tuple[int, ...]] = None,
        candidates: Optional[List[Position]] = None,
        anim_tick: int = 0,
    ) -> None:
        """Render the full board inside *rect*."""
        rows, cols = board.height, board.width

        # compute cell size to fit
        pad = 8
        avail_w = rect.width - 2 * pad
        avail_h = rect.height - 2 * pad
        cell = min(avail_w // cols, avail_h // rows)
        cell = max(cell, 12)  # minimum

        grid_w = cell * cols
        grid_h = cell * rows
        ox = rect.x + (rect.width - grid_w) // 2
        oy = rect.y + (rect.height - grid_h) // 2

        # board background
        t = self.theme
        board_rect = pygame.Rect(ox - 4, oy - 4, grid_w + 8, grid_h + 8)
        pygame.draw.rect(surface, t["board_bg"], board_rect, border_radius=6)
        pygame.draw.rect(surface, t["grid"], board_rect, width=2, border_radius=6)

        # ── draw cells ────────────────────────────────────────────
        cand_set = set(candidates) if candidates else set()

        for r in range(rows):
            for c in range(cols):
                pos = (r, c)
                cx = ox + c * cell
                cy = oy + r * cell
                crect = pygame.Rect(cx, cy, cell, cell)

                if board.is_wall(pos):
                    self._draw_wall(surface, board, pos, crect, cell)
                elif pos in bulbs:
                    self._draw_bulb_cell(surface, crect, cell, anim_tick)
                elif pos in lit:
                    self._draw_lit_cell(surface, crect, cell)
                else:
                    self._draw_empty_cell(surface, crect, cell)

                # candidate highlight (subtle dot)
                if pos in cand_set and pos != highlight_pos:
                    dot_r = max(3, cell // 8)
                    center = (cx + cell // 2, cy + cell // 2)
                    s = pygame.Surface((dot_r * 4, dot_r * 4), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*C_HL_CANDIDATE, 110), (dot_r * 2, dot_r * 2), dot_r)
                    surface.blit(s, (center[0] - dot_r * 2, center[1] - dot_r * 2))

        # ── grid lines ───────────────────────────────────────────
        for r in range(rows + 1):
            y = oy + r * cell
            pygame.draw.line(surface, t["grid"], (ox, y), (ox + grid_w, y), 1)
        for c in range(cols + 1):
            x = ox + c * cell
            pygame.draw.line(surface, t["grid"], (x, oy), (x, oy + grid_h), 1)

        # ── highlight current step ────────────────────────────────
        if highlight_pos is not None and highlight_color is not None:
            hr, hc = highlight_pos
            hx = ox + hc * cell
            hy = oy + hr * cell
            # pulsating alpha
            alpha = int(140 + 80 * math.sin(anim_tick * 0.15))
            alpha = max(0, min(255, alpha))
            s = pygame.Surface((cell, cell), pygame.SRCALPHA)
            s.fill((*highlight_color[:3], alpha))
            surface.blit(s, (hx, hy))
            # border
            pygame.draw.rect(surface, highlight_color[:3],
                             pygame.Rect(hx, hy, cell, cell), width=3, border_radius=2)

    # ── individual cell drawers ───────────────────────────────────

    def _draw_wall(self, surface: pygame.Surface, board: Board,
                   pos: Position, rect: pygame.Rect, cell: int) -> None:
        t = self.theme
        # Both plain and numbered walls share the same rounded-rect fill
        # so they look identical in weight (plain walls are no longer black).
        inner = rect.inflate(-4, -4)
        pygame.draw.rect(surface, t["wall"], rect)            # outer gap
        pygame.draw.rect(surface, t["wall_num_bg"], inner, border_radius=4)
        # subtle bevel
        pygame.draw.line(surface, t["bevel_hi"], rect.topleft, rect.topright, 1)
        pygame.draw.line(surface, t["bevel_hi"], rect.topleft, rect.bottomleft, 1)
        pygame.draw.line(surface, t["bevel_lo"], rect.bottomleft, rect.bottomright, 1)
        pygame.draw.line(surface, t["bevel_lo"], rect.topright, rect.bottomright, 1)

        if board.is_numbered_wall(pos):
            num = board.get_number(pos)
            fsize = max(12, int(cell * 0.55))
            txt = self._font_bold(fsize).render(str(num), True, t["wall_num_txt"])
            tx = rect.centerx - txt.get_width() // 2
            ty = rect.centery - txt.get_height() // 2
            surface.blit(txt, (tx, ty))

    def _draw_empty_cell(self, surface: pygame.Surface,
                         rect: pygame.Rect, cell: int) -> None:
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(surface, self.theme["empty"], inner, border_radius=2)

    def _draw_lit_cell(self, surface: pygame.Surface,
                       rect: pygame.Rect, cell: int) -> None:
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(surface, self.theme["lit"], inner, border_radius=2)
        # subtle inner glow overlay
        s = pygame.Surface((inner.width, inner.height), pygame.SRCALPHA)
        s.fill((255, 240, 100, 25))
        surface.blit(s, inner.topleft)

    def _draw_bulb_cell(self, surface: pygame.Surface,
                        rect: pygame.Rect, cell: int, tick: int) -> None:
        inner = rect.inflate(-2, -2)
        # warm glow background (theme-aware)
        pygame.draw.rect(surface, self.theme["lit_strong"], inner, border_radius=2)

        cx, cy = rect.centerx, rect.centery
        r = max(4, int(cell * 0.28))

        # outer glow (pulsating)
        glow_alpha = int(50 + 20 * math.sin(tick * 0.08))
        glow_r = int(r * 2.2)
        gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        for i in range(glow_r, 0, -1):
            a = int(glow_alpha * (i / glow_r))
            pygame.draw.circle(gs, (255, 230, 80, a), (glow_r, glow_r), i)
        surface.blit(gs, (cx - glow_r, cy - glow_r))

        # rays
        ray_len = int(r * 1.6)
        ray_w = max(1, cell // 20)
        for angle_deg in range(0, 360, 45):
            a = math.radians(angle_deg)
            x1 = cx + int(math.cos(a) * (r + 2))
            y1 = cy + int(math.sin(a) * (r + 2))
            x2 = cx + int(math.cos(a) * (r + ray_len))
            y2 = cy + int(math.sin(a) * (r + ray_len))
            pygame.draw.line(surface, C_RAY, (x1, y1), (x2, y2), ray_w)

        # bulb body
        pygame.draw.circle(surface, C_BULB_FILL, (cx, cy), r)
        # glass highlight
        highlight_r = max(2, r // 2)
        pygame.draw.circle(surface, C_BULB_GLASS, (cx - r // 4, cy - r // 4), highlight_r)
        # tiny white specular
        spec_r = max(1, r // 4)
        pygame.draw.circle(surface, C_BULB_HIGHLIGHT, (cx - r // 3, cy - r // 3), spec_r)
        # base
        base_w = max(3, int(r * 0.9))
        base_h = max(2, int(r * 0.4))
        base_rect = pygame.Rect(cx - base_w // 2, cy + r - 1, base_w, base_h)
        pygame.draw.rect(surface, C_BULB_BASE, base_rect, border_radius=1)

    # ── utility ───────────────────────────────────────────────────

    @staticmethod
    def compute_cell_size(board: Board, rect: pygame.Rect) -> int:
        pad = 8
        cw = (rect.width - 2 * pad) // board.width
        ch = (rect.height - 2 * pad) // board.height
        return max(12, min(cw, ch))
