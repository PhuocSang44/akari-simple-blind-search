"""Pygame-based Akari (Light Up) visual solver UI.

Layout
------
┌──────────────────────────┬──────────────────────┐
│                          │  SOLVER STATISTICS    │
│                          │  Status / Algorithm   │
│      BOARD PANEL         │  Nodes / Depth / …    │
│      (grid + bulbs)      │                       │
│                          │  SPEED CONTROL        │
│                          │  ◀ ██░░░ ▶            │
│                          │                       │
│                          │  STEP LOG (scrollable)│
├──────────────────────────┴──────────────────────┤
│  ▶ Run  ⏸ Pause  ■ Reset  | Puzzle ▼  Algo ▼   │
└─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
import os
import queue
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

import pygame

from core.board import Board
from core.types import Position
from algorithms.solver_visual import Step, StepType, VisualDFSSolver
from ui.theme import DARK, LIGHT, Theme
from ui.renderer import (
    BoardRenderer,
    C_HL_CONTRA,
    C_HL_FORCED,
    C_HL_PLACE,
    C_HL_REMOVE,
)

# ─── constants ────────────────────────────────────────────────────

WINDOW_W, WINDOW_H = 1280, 780
FPS = 60
PUZZLES_DIR = "puzzles"

SPEED_LEVELS = [
    ("0.25x", 2000),
    ("0.5x",  1000),
    ("1x",     500),
    ("2x",     250),
    ("5x",     100),
    ("10x",     50),
    ("25x",     20),
    ("Max",      0),
]
DEFAULT_SPEED_IDX = 2  # 1x

# ─── helpers ──────────────────────────────────────────────────────

def _collect_puzzles() -> List[str]:
    if not os.path.isdir(PUZZLES_DIR):
        return []
    return sorted(
        f for f in os.listdir(PUZZLES_DIR) if f.endswith(".txt")
    )


def _step_color(stype: StepType):
    return {
        StepType.PLACE_BULB:   C_HL_PLACE,
        StepType.REMOVE_BULB:  C_HL_REMOVE,
        StepType.FORCED_BULB:  C_HL_FORCED,
        StepType.REMOVE_FORCED:C_HL_REMOVE,
        StepType.CONTRADICTION:C_HL_CONTRA,
    }.get(stype)


def _step_icon(stype: StepType) -> str:
    return {
        StepType.PLACE_BULB:    "[B]",
        StepType.REMOVE_BULB:   "<- ",
        StepType.FORCED_BULB:   "[!]",
        StepType.REMOVE_FORCED: "<- ",
        StepType.CONTRADICTION: "[X]",
        StepType.SOLVED:        "[v]",
        StepType.NO_SOLUTION:   "[X]",
        StepType.START:         "[>]",
        StepType.GOAL_CHECK:    "[?]",
        StepType.FORBIDDEN:     "[-]",
    }.get(stype, "   ")


# ─── UI state enum ───────────────────────────────────────────────

class _Mode:
    IDLE     = "idle"
    RUNNING  = "running"
    PAUSED   = "paused"
    DONE     = "done"


# ─── main UI class ───────────────────────────────────────────────

class AkariUI:
    """Full Pygame application."""

    def __init__(self, initial_puzzle: Optional[str] = None) -> None:
        pygame.init()
        pygame.display.set_caption("Akari — Light Up Puzzle Solver")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        # fonts
        self._f: Dict[str, pygame.font.Font] = {}
        self._f["h1"]    = pygame.font.SysFont("Segoe UI", 26, bold=True)
        self._f["h2"]    = pygame.font.SysFont("Segoe UI", 18, bold=True)
        self._f["body"]  = pygame.font.SysFont("Segoe UI", 15)
        self._f["small"] = pygame.font.SysFont("Segoe UI", 13)
        self._f["mono"]  = pygame.font.SysFont("Consolas", 13)
        self._f["btn"]   = pygame.font.SysFont("Segoe UI", 15, bold=True)
        self._f["title"] = pygame.font.SysFont("Segoe UI", 30, bold=True)

        # puzzle list
        self._puzzles = _collect_puzzles()
        self._puz_idx = 0
        if initial_puzzle:
            for i, p in enumerate(self._puzzles):
                if initial_puzzle in p:
                    self._puz_idx = i
                    break

        # board
        self.board: Optional[Board] = None
        self._load_current_puzzle()

        # renderer
        self._renderer = BoardRenderer()

        # theme
        self._dark_theme: bool = True
        self._theme: Theme = DARK
        self._mode = _Mode.IDLE
        self._step_queue: queue.Queue[Step] = queue.Queue()
        self._continue_ev = threading.Event()
        self._stop_ev = threading.Event()
        self._solver_thread: Optional[threading.Thread] = None

        # current visualisation state
        self._bulbs: Set[Position] = set()
        self._lit: Set[Position] = set()
        self._hl_pos: Optional[Position] = None
        self._hl_color: Optional[Tuple[int, ...]] = None
        self._candidates: List[Position] = []
        self._step_count = 0
        self._nodes = 0
        self._depth = 0
        self._bulb_count = 0
        self._elapsed = 0.0
        self._status_msg = "Ready"
        self._status_color = DARK["text_dim"]

        # step log (newest first)
        self._log: List[Tuple[str, Tuple[int, int, int]]] = []
        self._log_scroll = 0

        # speed
        self._speed_idx = DEFAULT_SPEED_IDX
        self._last_step_time = 0.0

        # dynamic layout positions (set during draw, read during click)
        self._speed_btn_y = 0  # updated each frame in _draw_info_panel

        # animation tick
        self._tick = 0

        # dropdown
        self._puzzle_dropdown_open = False
        self._algo_dropdown_open = False
        self._algo_names = ["DFS + Propagation"]
        self._algo_idx = 0

        # layout rects (computed once)
        self._layout()

    def _t(self, key: str) -> Tuple[int, int, int]:
        """Quick accessor for current theme colour."""
        return self._theme[key]  # type: ignore[return-value]

    def _toggle_theme(self) -> None:
        self._dark_theme = not self._dark_theme
        self._theme = DARK if self._dark_theme else LIGHT
        self._renderer.set_theme(self._theme)

    # ── layout ────────────────────────────────────────────────────

    def _layout(self) -> None:
        tb_h = 56
        self._board_rect = pygame.Rect(0, 0, WINDOW_W * 55 // 100, WINDOW_H - tb_h)
        self._panel_rect = pygame.Rect(self._board_rect.right, 0,
                                       WINDOW_W - self._board_rect.width, WINDOW_H - tb_h)
        self._toolbar_rect = pygame.Rect(0, WINDOW_H - tb_h, WINDOW_W, tb_h)

    # ── puzzle loading ────────────────────────────────────────────

    def _load_current_puzzle(self) -> None:
        if not self._puzzles:
            self.board = None
            return
        path = os.path.join(PUZZLES_DIR, self._puzzles[self._puz_idx])
        try:
            self.board = Board.from_file(path)
        except Exception:
            self.board = None

    # ── solver thread control ─────────────────────────────────────

    def _start_solver(self) -> None:
        if self.board is None:
            return
        self._stop_solver()
        self._reset_vis()
        self._mode = _Mode.RUNNING
        self._status_msg = "Running…"
        self._status_color = self._t("accent")

        self._step_queue = queue.Queue()
        self._continue_ev = threading.Event()
        self._stop_ev = threading.Event()

        solver = VisualDFSSolver(self.board, self._step_queue,
                                 self._continue_ev, self._stop_ev)
        self._solver_thread = threading.Thread(target=solver.solve, daemon=True)
        self._solver_thread.start()

    def _stop_solver(self) -> None:
        self._stop_ev.set()
        self._continue_ev.set()  # unblock solver if waiting
        if self._solver_thread and self._solver_thread.is_alive():
            self._solver_thread.join(timeout=1.0)
        self._solver_thread = None

    def _pause(self) -> None:
        if self._mode == _Mode.RUNNING:
            self._mode = _Mode.PAUSED
            self._status_msg = "Paused"
            self._status_color = (255, 200, 60)

    def _resume(self) -> None:
        if self._mode == _Mode.PAUSED:
            self._mode = _Mode.RUNNING
            self._status_msg = "Running…"
            self._status_color = self._t("accent")

    def _reset_vis(self) -> None:
        self._bulbs = set()
        self._lit = set()
        self._hl_pos = None
        self._hl_color = None
        self._candidates = []
        self._step_count = 0
        self._nodes = 0
        self._depth = 0
        self._bulb_count = 0
        self._elapsed = 0.0
        self._log.clear()
        self._log_scroll = 0
        self._status_msg = "Ready"
        self._status_color = self._t("text_dim")

    # ── step processing ───────────────────────────────────────────

    def _process_steps(self) -> None:
        if self._mode not in (_Mode.RUNNING,):
            return

        delay_ms = SPEED_LEVELS[self._speed_idx][1]
        now = time.time() * 1000

        if delay_ms > 0 and (now - self._last_step_time) < delay_ms:
            return

        # At "Max" speed, drain up to N steps per frame for responsiveness
        batch = 20 if delay_ms == 0 else 1
        for _ in range(batch):
            try:
                step: Step = self._step_queue.get_nowait()
            except queue.Empty:
                return
            self._last_step_time = now
            self._apply_step(step)
            self._continue_ev.set()
            if step.step_type in (StepType.SOLVED, StepType.NO_SOLUTION):
                return

    def _apply_step(self, step: Step) -> None:
        self._step_count += 1
        self._nodes = step.nodes_expanded
        self._depth = step.depth
        self._bulb_count = step.bulb_count
        self._elapsed = step.elapsed
        self._bulbs = step.bulb_positions
        self._lit = step.lit_cells
        self._candidates = step.candidates

        # highlight
        self._hl_pos = step.position
        self._hl_color = _step_color(step.step_type)

        # log entry
        icon = _step_icon(step.step_type)
        color = {
            StepType.PLACE_BULB:    C_HL_PLACE,
            StepType.REMOVE_BULB:   C_HL_REMOVE,
            StepType.FORCED_BULB:   C_HL_FORCED,
            StepType.CONTRADICTION: self._t("error"),
            StepType.SOLVED:        self._t("success"),
            StepType.NO_SOLUTION:   self._t("error"),
        }.get(step.step_type, self._t("text_dim"))

        self._log.insert(0, (f"{icon} #{self._step_count:>5}  {step.message}", color))
        # cap log
        if len(self._log) > 500:
            self._log = self._log[:500]

        # status for terminal states
        if step.step_type == StepType.SOLVED:
            self._mode = _Mode.DONE
            self._status_msg = "Solved!"
            self._status_color = self._t("success")
            self._hl_pos = None
        elif step.step_type == StepType.NO_SOLUTION:
            self._mode = _Mode.DONE
            self._status_msg = "No Solution"
            self._status_color = self._t("error")
            self._hl_pos = None

    # ── event handling ────────────────────────────────────────────

    def _handle_events(self) -> bool:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                self._on_key(ev)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                self._on_click(ev)
            if ev.type == pygame.MOUSEWHEEL:
                self._on_scroll(ev)
        return True

    def _on_key(self, ev: pygame.event.Event) -> None:
        if ev.key == pygame.K_SPACE:
            if self._mode == _Mode.IDLE or self._mode == _Mode.DONE:
                self._start_solver()
            elif self._mode == _Mode.RUNNING:
                self._pause()
            elif self._mode == _Mode.PAUSED:
                self._resume()
        elif ev.key == pygame.K_t:
            self._toggle_theme()
        elif ev.key == pygame.K_r:
            self._stop_solver()
            self._reset_vis()
            self._mode = _Mode.IDLE
        elif ev.key == pygame.K_ESCAPE:
            self._puzzle_dropdown_open = False
            self._algo_dropdown_open = False
        elif ev.key == pygame.K_RIGHT:
            self._speed_idx = min(self._speed_idx + 1, len(SPEED_LEVELS) - 1)
        elif ev.key == pygame.K_LEFT:
            self._speed_idx = max(self._speed_idx - 1, 0)

    def _on_click(self, ev: pygame.event.Event) -> None:
        mx, my = ev.pos

        # ── check puzzle dropdown first (if open, it overlaps panel) ──
        if self._puzzle_dropdown_open:
            dd_rect = self._puzzle_dd_rect()
            if dd_rect.collidepoint(mx, my):
                idx = (my - dd_rect.y) // 28
                if 0 <= idx < len(self._puzzles):
                    self._stop_solver()
                    self._reset_vis()
                    self._mode = _Mode.IDLE
                    self._puz_idx = idx
                    self._load_current_puzzle()
                self._puzzle_dropdown_open = False
                return
            self._puzzle_dropdown_open = False
            return

        # ── toolbar buttons ───────────────────────────────────────
        if self._toolbar_rect.collidepoint(mx, my):
            self._toolbar_click(mx, my)
            return

        # ── speed buttons in panel ────────────────────────────────
        if self._panel_rect.collidepoint(mx, my):
            self._panel_click(mx, my)
            return

    def _on_scroll(self, ev: pygame.event.Event) -> None:
        mx, my = pygame.mouse.get_pos()
        if self._panel_rect.collidepoint(mx, my):
            self._log_scroll = max(0, self._log_scroll - ev.y * 3)

    # ── toolbar interaction ───────────────────────────────────────

    def _toolbar_click(self, mx: int, my: int) -> None:
        bx = self._toolbar_rect.x + 16
        by = self._toolbar_rect.y + 10
        bw, bh = 90, 36

        btns = self._toolbar_buttons()
        for i, (label, _color, action) in enumerate(btns):
            r = pygame.Rect(bx + i * (bw + 10), by, bw, bh)
            if r.collidepoint(mx, my):
                action()
                return

        # puzzle selector button
        puz_btn_rect = self._puz_btn_rect()
        if puz_btn_rect.collidepoint(mx, my):
            self._puzzle_dropdown_open = not self._puzzle_dropdown_open
            self._algo_dropdown_open = False
            return

        # theme toggle button
        if self._theme_btn_rect().collidepoint(mx, my):
            self._toggle_theme()

    def _toolbar_buttons(self):
        def do_run():
            if self._mode == _Mode.IDLE or self._mode == _Mode.DONE:
                self._start_solver()
            elif self._mode == _Mode.PAUSED:
                self._resume()

        def do_pause():
            self._pause()

        def do_reset():
            self._stop_solver()
            self._reset_vis()
            self._mode = _Mode.IDLE

        return [
            ("> Run",   self._t("success"), do_run),
            ("|| Pause", (255, 200, 60),    do_pause),
            ("[] Reset", self._t("error"),  do_reset),
        ]

    def _puz_btn_rect(self) -> pygame.Rect:
        return pygame.Rect(self._toolbar_rect.x + 320, self._toolbar_rect.y + 10, 200, 36)

    def _theme_btn_rect(self) -> pygame.Rect:
        pr = self._puz_btn_rect()
        return pygame.Rect(pr.right + 10, pr.y, 80, 36)

    def _puzzle_dd_rect(self) -> pygame.Rect:
        pr = self._puz_btn_rect()
        h = min(len(self._puzzles) * 28 + 4, 400)
        return pygame.Rect(pr.x, pr.y - h, pr.width, h)

    # ── panel click (speed controls) ──────────────────────────────

    def _panel_click(self, mx: int, my: int) -> None:
        # speed − and + buttons (y position from last draw)
        sx = self._panel_rect.x + 20
        sy = self._speed_btn_y
        btn_w, btn_h = 36, 30

        minus_r = pygame.Rect(sx, sy, btn_w, btn_h)
        plus_r = pygame.Rect(sx + 180, sy, btn_w, btn_h)

        # also allow clicking on the speed bar to set speed directly
        bar_x = sx + 44
        bar_y = sy + 34
        bar_w = self._panel_rect.width - 80
        bar_rect = pygame.Rect(bar_x, bar_y - 8, bar_w, 20)

        if minus_r.collidepoint(mx, my):
            self._speed_idx = max(0, self._speed_idx - 1)
        elif plus_r.collidepoint(mx, my):
            self._speed_idx = min(len(SPEED_LEVELS) - 1, self._speed_idx + 1)
        elif bar_rect.collidepoint(mx, my):
            ratio = (mx - bar_x) / max(1, bar_w)
            self._speed_idx = int(ratio * (len(SPEED_LEVELS) - 1) + 0.5)
            self._speed_idx = max(0, min(self._speed_idx, len(SPEED_LEVELS) - 1))

    # ── drawing ───────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(self._t("bg"))
        self._draw_board_panel()
        self._draw_info_panel()
        self._draw_toolbar()

        # dropdown overlay (on top of everything)
        if self._puzzle_dropdown_open:
            self._draw_puzzle_dropdown()

        pygame.display.flip()

    # ── board panel ───────────────────────────────────────────────

    def _draw_board_panel(self) -> None:
        r = self._board_rect
        pygame.draw.rect(self.screen, self._t("panel_bg"), r)
        # title
        title = self._f["h1"].render("AKARI  —  Light Up", True, self._t("accent"))
        self.screen.blit(title, (r.x + 20, r.y + 10))

        if self.board is None:
            msg = self._f["body"].render("No puzzle loaded", True, self._t("text_dim"))
            self.screen.blit(msg, (r.centerx - msg.get_width() // 2, r.centery))
            return

        # puzzle name
        pname = self._puzzles[self._puz_idx] if self._puzzles else ""
        pn_surf = self._f["small"].render(f"Puzzle: {pname}   ({self.board.width}x{self.board.height})", True, self._t("text_dim"))
        self.screen.blit(pn_surf, (r.x + 20, r.y + 42))

        board_area = pygame.Rect(r.x + 10, r.y + 62, r.width - 20, r.height - 72)
        self._renderer.draw(
            self.screen, self.board,
            self._bulbs, self._lit, board_area,
            highlight_pos=self._hl_pos,
            highlight_color=self._hl_color,
            candidates=self._candidates,
            anim_tick=self._tick,
        )

    # ── info panel ────────────────────────────────────────────────

    def _draw_info_panel(self) -> None:
        r = self._panel_rect
        # panel bg
        pygame.draw.rect(self.screen, self._t("info_panel_bg"), r)
        # left border accent
        pygame.draw.line(self.screen, self._t("accent"), (r.x, r.y), (r.x, r.bottom), 2)

        x0 = r.x + 20
        y = r.y + 16

        # ── section: Solver Statistics ────────────────────────────
        self._section_header("SOLVER STATISTICS", x0, y)
        y += 32

        # status badge
        badge_col = self._status_color
        pygame.draw.circle(self.screen, badge_col, (x0 + 6, y + 8), 5)
        st = self._f["body"].render(f"  {self._status_msg}", True, badge_col)
        self.screen.blit(st, (x0 + 14, y - 1))
        y += 26

        # stats grid
        stats = [
            ("Algorithm", self._algo_names[self._algo_idx]),
            ("Nodes expanded", f"{self._nodes:,}"),
            ("Search depth", str(self._depth)),
            ("Bulbs placed", str(self._bulb_count)),
            ("Steps shown", f"{self._step_count:,}"),
            ("Elapsed", f"{self._elapsed:.3f} s"),
        ]
        for label, val in stats:
            lbl = self._f["small"].render(label, True, self._t("text_dim"))
            v = self._f["small"].render(val, True, self._t("text"))
            self.screen.blit(lbl, (x0, y))
            self.screen.blit(v, (x0 + 150, y))
            y += 22
        y += 10

        # ── section: Speed Control ────────────────────────────────
        self._section_header("SPEED CONTROL", x0, y)
        y += 32
        self._speed_btn_y = y  # save for click detection

        # - button
        self._draw_small_btn(self.screen, "<", x0, y, 36, 30, self._t("grid"))
        # speed level name
        spd_name = SPEED_LEVELS[self._speed_idx][0]
        sn = self._f["btn"].render(spd_name, True, self._t("accent"))
        self.screen.blit(sn, (x0 + 90 - sn.get_width() // 2 + 18, y + 4))
        # + button
        self._draw_small_btn(self.screen, ">", x0 + 180, y, 36, 30, self._t("grid"))

        # speed bar
        bar_x = x0 + 44
        bar_y = y + 34
        bar_w = r.width - 80
        bar_h = 6
        pygame.draw.rect(self.screen, self._t("grid"), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * self._speed_idx / max(1, len(SPEED_LEVELS) - 1))
        pygame.draw.rect(self.screen, self._t("accent"), (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        # knob
        knob_x = bar_x + fill_w
        pygame.draw.circle(self.screen, self._t("accent"), (knob_x, bar_y + 3), 8)
        pygame.draw.circle(self.screen, self._t("text"), (knob_x, bar_y + 3), 4)

        y += 52

        # ── section: Step Log ─────────────────────────────────────
        self._section_header("STEP LOG", x0, y)
        y += 28

        log_rect = pygame.Rect(x0, y, r.width - 40, r.bottom - y - 10)
        pygame.draw.rect(self.screen, self._t("board_bg"), log_rect, border_radius=4)

        # clip
        clip_save = self.screen.get_clip()
        self.screen.set_clip(log_rect)

        ly = log_rect.y + 4 - self._log_scroll
        line_h = 18
        for text, color in self._log:
            if ly + line_h < log_rect.y:
                ly += line_h
                continue
            if ly > log_rect.bottom:
                break
            ts = self._f["mono"].render(text[:60], True, color)
            self.screen.blit(ts, (log_rect.x + 6, ly))
            ly += line_h

        self.screen.set_clip(clip_save)

        # scrollbar
        if self._log:
            total_h = len(self._log) * line_h
            if total_h > log_rect.height:
                sb_h = max(20, int(log_rect.height * log_rect.height / total_h))
                sb_y = log_rect.y + int(self._log_scroll / total_h * log_rect.height)
                sb_y = min(sb_y, log_rect.bottom - sb_h)
                pygame.draw.rect(self.screen, (*self._t("accent"), 120),
                                 (log_rect.right - 6, sb_y, 4, sb_h), border_radius=2)

    # ── toolbar ───────────────────────────────────────────────────

    def _draw_toolbar(self) -> None:
        r = self._toolbar_rect
        pygame.draw.rect(self.screen, self._t("toolbar_bg"), r)
        pygame.draw.line(self.screen, self._t("grid"), (r.x, r.y), (r.right, r.y), 1)

        bx = r.x + 16
        by = r.y + 10
        bw, bh = 90, 36

        for i, (label, color, _action) in enumerate(self._toolbar_buttons()):
            br = pygame.Rect(bx + i * (bw + 10), by, bw, bh)
            mx, my = pygame.mouse.get_pos()
            hover = br.collidepoint(mx, my)
            bg = (*color[:3], 40) if not hover else (*color[:3], 70)
            s = pygame.Surface((bw, bh), pygame.SRCALPHA)
            s.fill(bg)
            self.screen.blit(s, br.topleft)
            pygame.draw.rect(self.screen, color, br, width=2, border_radius=4)
            t = self._f["btn"].render(label, True, color)
            self.screen.blit(t, (br.centerx - t.get_width() // 2,
                                 br.centery - t.get_height() // 2))

        # puzzle selector
        puz_btn = self._puz_btn_rect()
        pname = self._puzzles[self._puz_idx] if self._puzzles else "(none)"
        hover = puz_btn.collidepoint(*pygame.mouse.get_pos())
        bc = self._t("accent") if hover else self._t("grid")
        pygame.draw.rect(self.screen, bc, puz_btn, width=2, border_radius=4)
        pt = self._f["btn"].render(f"[F]  {pname}", True, self._t("text"))
        self.screen.blit(pt, (puz_btn.x + 10, puz_btn.centery - pt.get_height() // 2))

        # theme toggle button
        theme_btn = self._theme_btn_rect()
        th_label = "[Dark]" if self._dark_theme else "[Light]"
        hover_th = theme_btn.collidepoint(*pygame.mouse.get_pos())
        tc = self._t("accent") if hover_th else self._t("grid")
        pygame.draw.rect(self.screen, tc, theme_btn, width=2, border_radius=4)
        tt = self._f["btn"].render(th_label, True, self._t("text"))
        self.screen.blit(tt, (theme_btn.centerx - tt.get_width() // 2,
                              theme_btn.centery - tt.get_height() // 2))

        # keyboard hints
        hints = "Space:Run/Pause  R:Reset  </> :Speed  T:Theme"
        ht = self._f["small"].render(hints, True, self._t("text_dim"))
        self.screen.blit(ht, (r.right - ht.get_width() - 16, r.centery - ht.get_height() // 2))

    # ── puzzle dropdown ───────────────────────────────────────────

    def _draw_puzzle_dropdown(self) -> None:
        dd = self._puzzle_dd_rect()
        pygame.draw.rect(self.screen, self._t("panel_bg"), dd, border_radius=6)
        pygame.draw.rect(self.screen, self._t("accent"), dd, width=1, border_radius=6)

        clip_save = self.screen.get_clip()
        self.screen.set_clip(dd)

        y = dd.y + 2
        mx, my = pygame.mouse.get_pos()
        for i, name in enumerate(self._puzzles):
            item_r = pygame.Rect(dd.x, y, dd.width, 28)
            if item_r.collidepoint(mx, my):
                pygame.draw.rect(self.screen, self._t("grid"), item_r)
            if i == self._puz_idx:
                ac = self._t("accent")
                s = pygame.Surface((item_r.width, item_r.height), pygame.SRCALPHA)
                s.fill((*ac, 30))
                self.screen.blit(s, item_r.topleft)
            t = self._f["small"].render(name, True, self._t("text"))
            self.screen.blit(t, (dd.x + 10, y + 5))
            y += 28

        self.screen.set_clip(clip_save)

    # ── draw helpers ──────────────────────────────────────────────

    def _section_header(self, text: str, x: int, y: int) -> None:
        # modern left-accent bar
        ac = self._t("accent")
        pygame.draw.rect(self.screen, ac, (x, y + 1, 3, 17), border_radius=2)
        # label in dimmed text — uppercase small caps feel
        t = self._f["h2"].render(text, True, self._t("text_dim"))
        self.screen.blit(t, (x + 10, y))

    def _draw_small_btn(self, surf: pygame.Surface, label: str,
                        x: int, y: int, w: int, h: int,
                        color: Tuple[int, ...]) -> None:
        r = pygame.Rect(x, y, w, h)
        hover = r.collidepoint(*pygame.mouse.get_pos())
        bc = self._t("accent") if hover else color
        pygame.draw.rect(surf, bc, r, width=2, border_radius=4)
        t = self._f["btn"].render(label, True, bc)
        surf.blit(t, (r.centerx - t.get_width() // 2, r.centery - t.get_height() // 2))

    # ── main loop ─────────────────────────────────────────────────

    def run(self) -> None:
        running = True
        while running:
            running = self._handle_events()
            self._process_steps()
            self._tick += 1
            self._draw()
            self.clock.tick(FPS)

        self._stop_solver()
        pygame.quit()

