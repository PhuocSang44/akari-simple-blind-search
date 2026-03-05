"""Pygame-based Akari (Light Up) visual solver UI — dual pane comparison.

Layout
------
┌─────────────────────┬─────────────────────┬──────────────────┐
│   DFS + Propagation │   A* + Propagation  │  SHARED PANEL    │
│                     │                     │  Speed / Puzzle  │
│      BOARD 1        │      BOARD 2        │  Stats L │ R     │
│                     │                     │  Step Log        │
├─────────────────────┴─────────────────────┴──────────────────┤
│  ▶ Run  ⏸ Pause  ■ Reset  | Puzzle ▼  Theme                 │
└──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

import pygame

from core.board import Board
from core.types import Position
from algorithms.visual_common import Step, StepType
from algorithms.a_star_visual import VisualAStarSolver
from algorithms.dfs_visual import VisualDFSSolver
from ui.theme import DARK, LIGHT, Theme
from ui.renderer import (
    BoardRenderer,
    C_HL_CONTRA,
    C_HL_FORCED,
    C_HL_PLACE,
    C_HL_REMOVE,
)

# ─── constants ────────────────────────────────────────────────────

WINDOW_W, WINDOW_H = 1600, 820
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
        StepType.PLACE_BULB:    C_HL_PLACE,
        StepType.POP_NODE:      C_HL_PLACE,
        StepType.REMOVE_BULB:   C_HL_REMOVE,
        StepType.REMOVE_FORCED: C_HL_REMOVE,
        StepType.FORCED_BULB:   C_HL_FORCED,
        StepType.CONTRADICTION: C_HL_CONTRA,
    }.get(stype)


def _step_icon(stype: StepType) -> str:
    return {
        StepType.PLACE_BULB:    "[B]",
        StepType.POP_NODE:      "[^]",
        StepType.REMOVE_BULB:   "<- ",
        StepType.REMOVE_FORCED: "<- ",
        StepType.FORCED_BULB:   "[!]",
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


# ─── per-solver pane state ────────────────────────────────────────

class _SolverPane:
    """Holds all mutable state for one solver lane."""

    def __init__(self, algo_name: str, algo_idx: int) -> None:
        self.algo_name = algo_name
        self.algo_idx = algo_idx  # 0=DFS, 1=A*
        self.renderer = BoardRenderer()

        # thread / queue
        self.step_queue: queue.Queue[Step] = queue.Queue()
        self.continue_ev = threading.Event()
        self.stop_ev = threading.Event()
        self.solver_thread: Optional[threading.Thread] = None

        # visualisation state
        self.mode = _Mode.IDLE
        self.bulbs: Set[Position] = set()
        self.lit: Set[Position] = set()
        self.hl_pos: Optional[Position] = None
        self.hl_color: Optional[Tuple[int, ...]] = None
        self.candidates: List[Position] = []
        self.step_count = 0
        self.nodes = 0
        self.depth = 0
        self.frontier_size = 0
        self.f_n = 0.0
        self.bulb_count = 0
        self.elapsed = 0.0
        self.status_msg = "Ready"
        self.status_color = DARK["text_dim"]

        # log
        self.log: List[Tuple[str, Tuple[int, int, int]]] = []
        self.log_scroll = 0

        self.last_step_time = 0.0

    def reset(self, theme: Theme) -> None:
        self.bulbs = set()
        self.lit = set()
        self.hl_pos = None
        self.hl_color = None
        self.candidates = []
        self.step_count = 0
        self.nodes = 0
        self.depth = 0
        self.frontier_size = 0
        self.f_n = 0.0
        self.bulb_count = 0
        self.elapsed = 0.0
        self.log.clear()
        self.log_scroll = 0
        self.status_msg = "Ready"
        self.status_color = theme["text_dim"]
        self.mode = _Mode.IDLE

    def stop(self) -> None:
        self.stop_ev.set()
        self.continue_ev.set()
        if self.solver_thread and self.solver_thread.is_alive():
            self.solver_thread.join(timeout=1.0)
        self.solver_thread = None


# ─── main UI class ───────────────────────────────────────────────

class AkariUI:
    """Full Pygame application — dual pane comparison."""

    def __init__(self, initial_puzzle: Optional[str] = None) -> None:
        pygame.init()
        pygame.display.set_caption("Akari — Light Up — DFS vs A* Comparison")
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.clock = pygame.time.Clock()

        # fonts
        self._f: Dict[str, pygame.font.Font] = {}
        self._f["h1"]    = pygame.font.SysFont("Segoe UI", 22, bold=True)
        self._f["h2"]    = pygame.font.SysFont("Segoe UI", 16, bold=True)
        self._f["body"]  = pygame.font.SysFont("Segoe UI", 14)
        self._f["small"] = pygame.font.SysFont("Segoe UI", 12)
        self._f["mono"]  = pygame.font.SysFont("Consolas", 12)
        self._f["btn"]   = pygame.font.SysFont("Segoe UI", 14, bold=True)
        self._f["title"] = pygame.font.SysFont("Segoe UI", 26, bold=True)

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

        # theme
        self._dark_theme: bool = True
        self._theme: Theme = DARK

        # two solver panes
        self._panes: List[_SolverPane] = [
            _SolverPane("DFS + Propagation", 0),
            _SolverPane("A* + Propagation", 1),
        ]
        for p in self._panes:
            p.renderer.set_theme(self._theme)

        # shared speed
        self._speed_idx = DEFAULT_SPEED_IDX

        # animation tick
        self._tick = 0

        # dropdown
        self._puzzle_dropdown_open = False

        # dynamic layout position
        self._speed_btn_y = 0

        # layout
        self._layout()

    def _t(self, key: str) -> Tuple[int, int, int]:
        return self._theme[key]  # type: ignore[return-value]

    def _toggle_theme(self) -> None:
        self._dark_theme = not self._dark_theme
        self._theme = DARK if self._dark_theme else LIGHT
        for p in self._panes:
            p.renderer.set_theme(self._theme)

    # ── layout ────────────────────────────────────────────────────

    def _layout(self) -> None:
        tb_h = 56
        board_w = WINDOW_W * 35 // 100
        panel_w = WINDOW_W - board_w * 2
        h = WINDOW_H - tb_h

        self._board_rects = [
            pygame.Rect(0, 0, board_w, h),
            pygame.Rect(board_w, 0, board_w, h),
        ]
        self._panel_rect = pygame.Rect(board_w * 2, 0, panel_w, h)
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

    def _start_solvers(self) -> None:
        if self.board is None:
            return
        self._stop_solvers()
        for pane in self._panes:
            pane.reset(self._theme)
            pane.mode = _Mode.RUNNING
            pane.status_msg = "Running…"
            pane.status_color = self._t("accent")

            pane.step_queue = queue.Queue()
            pane.continue_ev = threading.Event()
            pane.stop_ev = threading.Event()

            if pane.algo_idx == 0:
                solver = VisualDFSSolver(self.board, pane.step_queue,
                                         pane.continue_ev, pane.stop_ev)
            else:
                solver = VisualAStarSolver(self.board, pane.step_queue,
                                           pane.continue_ev, pane.stop_ev)
            pane.solver_thread = threading.Thread(target=solver.solve, daemon=True)
            pane.solver_thread.start()

    def _stop_solvers(self) -> None:
        for pane in self._panes:
            pane.stop()

    def _pause_solvers(self) -> None:
        for pane in self._panes:
            if pane.mode == _Mode.RUNNING:
                pane.mode = _Mode.PAUSED
                pane.status_msg = "Paused"
                pane.status_color = (255, 200, 60)

    def _resume_solvers(self) -> None:
        for pane in self._panes:
            if pane.mode == _Mode.PAUSED:
                pane.mode = _Mode.RUNNING
                pane.status_msg = "Running…"
                pane.status_color = self._t("accent")

    def _all_idle(self) -> bool:
        return all(p.mode == _Mode.IDLE for p in self._panes)

    def _all_done(self) -> bool:
        return all(p.mode == _Mode.DONE for p in self._panes)

    def _any_running(self) -> bool:
        return any(p.mode == _Mode.RUNNING for p in self._panes)

    def _any_paused(self) -> bool:
        return any(p.mode == _Mode.PAUSED for p in self._panes)

    # ── step processing ───────────────────────────────────────────

    def _process_steps(self) -> None:
        delay_ms = SPEED_LEVELS[self._speed_idx][1]
        now = time.time() * 1000
        batch = 20 if delay_ms == 0 else 1

        for pane in self._panes:
            if pane.mode != _Mode.RUNNING:
                continue
            if delay_ms > 0 and (now - pane.last_step_time) < delay_ms:
                continue
            for _ in range(batch):
                try:
                    step: Step = pane.step_queue.get_nowait()
                except queue.Empty:
                    break
                pane.last_step_time = now
                self._apply_step(pane, step)
                pane.continue_ev.set()
                if step.step_type in (StepType.SOLVED, StepType.NO_SOLUTION):
                    break

    def _apply_step(self, pane: _SolverPane, step: Step) -> None:
        pane.step_count += 1
        pane.nodes = step.nodes_expanded
        pane.depth = step.depth
        pane.frontier_size = step.frontier_size
        pane.f_n = step.f_n
        pane.bulb_count = step.bulb_count
        pane.elapsed = step.elapsed
        pane.bulbs = step.bulb_positions
        pane.lit = step.lit_cells
        pane.candidates = step.candidates

        pane.hl_pos = step.position
        pane.hl_color = _step_color(step.step_type)

        icon = _step_icon(step.step_type)
        color = {
            StepType.PLACE_BULB:    C_HL_PLACE,
            StepType.POP_NODE:      C_HL_PLACE,
            StepType.REMOVE_BULB:   C_HL_REMOVE,
            StepType.REMOVE_FORCED: C_HL_REMOVE,
            StepType.FORCED_BULB:   C_HL_FORCED,
            StepType.CONTRADICTION: self._t("error"),
            StepType.SOLVED:        self._t("success"),
            StepType.NO_SOLUTION:   self._t("error"),
        }.get(step.step_type, self._t("text_dim"))

        pane.log.insert(0, (f"{icon} #{pane.step_count:>5}  {step.message}", color))
        if len(pane.log) > 500:
            pane.log = pane.log[:500]

        if step.step_type == StepType.SOLVED:
            pane.mode = _Mode.DONE
            pane.status_msg = "Solved!"
            pane.status_color = self._t("success")
            pane.hl_pos = None
        elif step.step_type == StepType.NO_SOLUTION:
            pane.mode = _Mode.DONE
            pane.status_msg = "No Solution"
            pane.status_color = self._t("error")
            pane.hl_pos = None

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
            if self._all_idle() or self._all_done():
                self._start_solvers()
            elif self._any_running():
                self._pause_solvers()
            elif self._any_paused():
                self._resume_solvers()
        elif ev.key == pygame.K_t:
            self._toggle_theme()
        elif ev.key == pygame.K_r:
            self._stop_solvers()
            for p in self._panes:
                p.reset(self._theme)
        elif ev.key == pygame.K_ESCAPE:
            self._puzzle_dropdown_open = False
        elif ev.key == pygame.K_RIGHT:
            self._speed_idx = min(self._speed_idx + 1, len(SPEED_LEVELS) - 1)
        elif ev.key == pygame.K_LEFT:
            self._speed_idx = max(self._speed_idx - 1, 0)

    def _on_click(self, ev: pygame.event.Event) -> None:
        mx, my = ev.pos

        if self._puzzle_dropdown_open:
            dd_rect = self._puzzle_dd_rect()
            if dd_rect.collidepoint(mx, my):
                idx = (my - dd_rect.y) // 28
                if 0 <= idx < len(self._puzzles):
                    self._stop_solvers()
                    for p in self._panes:
                        p.reset(self._theme)
                    self._puz_idx = idx
                    self._load_current_puzzle()
                self._puzzle_dropdown_open = False
                return
            self._puzzle_dropdown_open = False
            return

        if self._toolbar_rect.collidepoint(mx, my):
            self._toolbar_click(mx, my)
            return

        if self._panel_rect.collidepoint(mx, my):
            self._panel_click(mx, my)
            return

    def _on_scroll(self, ev: pygame.event.Event) -> None:
        mx, my = pygame.mouse.get_pos()
        if self._panel_rect.collidepoint(mx, my):
            # scroll both logs together
            for pane in self._panes:
                pane.log_scroll = max(0, pane.log_scroll - ev.y * 3)

    # ── toolbar ───────────────────────────────────────────────────

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

        puz_btn_rect = self._puz_btn_rect()
        if puz_btn_rect.collidepoint(mx, my):
            self._puzzle_dropdown_open = not self._puzzle_dropdown_open
            return

        if self._theme_btn_rect().collidepoint(mx, my):
            self._toggle_theme()

    def _toolbar_buttons(self):
        def do_run():
            if self._all_idle() or self._all_done():
                self._start_solvers()
            elif self._any_paused():
                self._resume_solvers()

        def do_pause():
            self._pause_solvers()

        def do_reset():
            self._stop_solvers()
            for p in self._panes:
                p.reset(self._theme)

        return [
            ("> Run",    self._t("success"), do_run),
            ("|| Pause", (255, 200, 60),     do_pause),
            ("[] Reset", self._t("error"),   do_reset),
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

    # ── panel click (speed) ───────────────────────────────────────

    def _panel_click(self, mx: int, my: int) -> None:
        sx = self._panel_rect.x + 16
        sy = self._speed_btn_y
        btn_w, btn_h = 36, 30

        minus_r = pygame.Rect(sx, sy, btn_w, btn_h)
        plus_r = pygame.Rect(sx + 160, sy, btn_w, btn_h)

        bar_x = sx + 44
        bar_y = sy + 34
        bar_w = self._panel_rect.width - 70
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
        for i, pane in enumerate(self._panes):
            self._draw_board_panel(pane, self._board_rects[i])
        self._draw_info_panel()
        self._draw_toolbar()

        if self._puzzle_dropdown_open:
            self._draw_puzzle_dropdown()

        pygame.display.flip()

    # ── board panel (per pane) ────────────────────────────────────

    def _draw_board_panel(self, pane: _SolverPane, r: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, self._t("panel_bg"), r)
        # divider line between panes
        pygame.draw.line(self.screen, self._t("grid"),
                         (r.right - 1, r.y), (r.right - 1, r.bottom), 1)

        # title
        title = self._f["h1"].render(pane.algo_name, True, self._t("accent"))
        self.screen.blit(title, (r.x + 14, r.y + 8))

        # status badge
        badge_col = pane.status_color
        pygame.draw.circle(self.screen, badge_col, (r.x + 14, r.y + 38), 5)
        st = self._f["small"].render(f"  {pane.status_msg}", True, badge_col)
        self.screen.blit(st, (r.x + 22, r.y + 32))

        if self.board is None:
            msg = self._f["body"].render("No puzzle loaded", True, self._t("text_dim"))
            self.screen.blit(msg, (r.centerx - msg.get_width() // 2, r.centery))
            return

        # compact stats line
        stats_parts = [f"Nodes:{pane.nodes:,}", f"Bulbs:{pane.bulb_count}",
                       f"Time:{pane.elapsed:.2f}s"]
        if pane.algo_idx == 0:
            stats_parts.insert(1, f"Depth:{pane.depth}")
        else:
            stats_parts.insert(1, f"Frontier:{pane.frontier_size}")
            stats_parts.insert(2, f"f={pane.f_n:.0f}")
        stats_str = "  |  ".join(stats_parts)
        ss = self._f["small"].render(stats_str, True, self._t("text_dim"))
        self.screen.blit(ss, (r.x + 14, r.y + 50))

        board_area = pygame.Rect(r.x + 8, r.y + 68, r.width - 16, r.height - 78)
        pane.renderer.draw(
            self.screen, self.board,
            pane.bulbs, pane.lit, board_area,
            highlight_pos=pane.hl_pos,
            highlight_color=pane.hl_color,
            candidates=pane.candidates,
            anim_tick=self._tick,
        )

    # ── info panel (shared) ───────────────────────────────────────

    def _draw_info_panel(self) -> None:
        r = self._panel_rect
        pygame.draw.rect(self.screen, self._t("info_panel_bg"), r)
        pygame.draw.line(self.screen, self._t("accent"), (r.x, r.y), (r.x, r.bottom), 2)

        x0 = r.x + 16
        y = r.y + 12

        # ── Puzzle info ───────────────────────────────────────────
        pname = self._puzzles[self._puz_idx] if self._puzzles else "(none)"
        size_str = f"{self.board.width}x{self.board.height}" if self.board else "?"
        self._section_header("PUZZLE", x0, y)
        y += 26
        pt = self._f["small"].render(f"{pname}  ({size_str})", True, self._t("text"))
        self.screen.blit(pt, (x0, y))
        y += 24

        # ── Speed Control ─────────────────────────────────────────
        self._section_header("SPEED CONTROL", x0, y)
        y += 28
        self._speed_btn_y = y

        self._draw_small_btn(self.screen, "<", x0, y, 36, 30, self._t("grid"))
        spd_name = SPEED_LEVELS[self._speed_idx][0]
        sn = self._f["btn"].render(spd_name, True, self._t("accent"))
        self.screen.blit(sn, (x0 + 80 - sn.get_width() // 2 + 18, y + 4))
        self._draw_small_btn(self.screen, ">", x0 + 160, y, 36, 30, self._t("grid"))

        bar_x = x0 + 44
        bar_y = y + 34
        bar_w = r.width - 70
        bar_h = 6
        pygame.draw.rect(self.screen, self._t("grid"), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
        fill_w = int(bar_w * self._speed_idx / max(1, len(SPEED_LEVELS) - 1))
        pygame.draw.rect(self.screen, self._t("accent"), (bar_x, bar_y, fill_w, bar_h), border_radius=3)
        knob_x = bar_x + fill_w
        pygame.draw.circle(self.screen, self._t("accent"), (knob_x, bar_y + 3), 8)
        pygame.draw.circle(self.screen, self._t("text"), (knob_x, bar_y + 3), 4)

        y += 50

        # ── Comparison table ──────────────────────────────────────
        self._section_header("COMPARISON", x0, y)
        y += 26

        col_w = (r.width - 32) // 3
        headers = ["", self._panes[0].algo_name.split()[0],
                       self._panes[1].algo_name.split()[0]]
        for ci, h in enumerate(headers):
            ht = self._f["small"].render(h, True, self._t("accent"))
            self.screen.blit(ht, (x0 + ci * col_w, y))
        y += 20

        rows = [
            ("Nodes", f"{self._panes[0].nodes:,}", f"{self._panes[1].nodes:,}"),
            ("Bulbs", str(self._panes[0].bulb_count), str(self._panes[1].bulb_count)),
            ("Steps", f"{self._panes[0].step_count:,}", f"{self._panes[1].step_count:,}"),
            ("Time",  f"{self._panes[0].elapsed:.3f}s", f"{self._panes[1].elapsed:.3f}s"),
            ("Status", self._panes[0].status_msg, self._panes[1].status_msg),
        ]
        for label, v1, v2 in rows:
            lt = self._f["small"].render(label, True, self._t("text_dim"))
            t1 = self._f["small"].render(v1, True, self._t("text"))
            t2 = self._f["small"].render(v2, True, self._t("text"))
            self.screen.blit(lt, (x0, y))
            self.screen.blit(t1, (x0 + col_w, y))
            self.screen.blit(t2, (x0 + col_w * 2, y))
            y += 20
        y += 10

        # ── Step Logs side by side ────────────────────────────────
        self._section_header("STEP LOGS", x0, y)
        y += 24

        log_h = r.bottom - y - 8
        half_w = (r.width - 36) // 2

        for pi, pane in enumerate(self._panes):
            lx = x0 + pi * (half_w + 4)
            log_rect = pygame.Rect(lx, y, half_w, log_h)
            pygame.draw.rect(self.screen, self._t("board_bg"), log_rect, border_radius=4)

            # pane label
            pl = self._f["small"].render(pane.algo_name.split()[0], True, self._t("accent"))
            self.screen.blit(pl, (lx + 4, y + 2))

            clip_save = self.screen.get_clip()
            self.screen.set_clip(log_rect)

            ly = log_rect.y + 18 - pane.log_scroll
            line_h = 16
            for text, color in pane.log:
                if ly + line_h < log_rect.y:
                    ly += line_h
                    continue
                if ly > log_rect.bottom:
                    break
                ts = self._f["mono"].render(text[:45], True, color)
                self.screen.blit(ts, (log_rect.x + 4, ly))
                ly += line_h

            self.screen.set_clip(clip_save)

            # scrollbar
            if pane.log:
                total_h = len(pane.log) * line_h
                if total_h > log_rect.height:
                    sb_h = max(20, int(log_rect.height * log_rect.height / total_h))
                    sb_y = log_rect.y + int(pane.log_scroll / total_h * log_rect.height)
                    sb_y = min(sb_y, log_rect.bottom - sb_h)
                    pygame.draw.rect(self.screen, (*self._t("accent"), 120),
                                     (log_rect.right - 5, sb_y, 3, sb_h), border_radius=2)

    # ── toolbar drawing ───────────────────────────────────────────

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

        # theme toggle
        theme_btn = self._theme_btn_rect()
        th_label = "[Dark]" if self._dark_theme else "[Light]"
        hover_th = theme_btn.collidepoint(*pygame.mouse.get_pos())
        tc = self._t("accent") if hover_th else self._t("grid")
        pygame.draw.rect(self.screen, tc, theme_btn, width=2, border_radius=4)
        tt = self._f["btn"].render(th_label, True, self._t("text"))
        self.screen.blit(tt, (theme_btn.centerx - tt.get_width() // 2,
                              theme_btn.centery - tt.get_height() // 2))

        # hints
        hints = "Space:Run/Pause  R:Reset  </>:Speed  T:Theme"
        ht = self._f["small"].render(hints, True, self._t("text_dim"))
        self.screen.blit(ht, (r.right - ht.get_width() - 14, r.centery - ht.get_height() // 2))

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
        ac = self._t("accent")
        pygame.draw.rect(self.screen, ac, (x, y + 1, 3, 15), border_radius=2)
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

        self._stop_solvers()
        pygame.quit()

