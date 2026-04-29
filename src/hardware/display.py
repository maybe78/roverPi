"""
Face animation + lidar radar for 320×480 SPI display (ILI9488/ST7796).

Layout (portrait 320×480):
  ┌──────────────────┐  0
  │   FACE  320×240  │
  ├──────────────────┤  240
  │   RADAR 320×240  │
  └──────────────────┘  480

Hardware: rendered to Linux framebuffer /dev/fb1.
Mock mode: regular pygame desktop window.
"""

import logging
import threading
import time
import math
import random
import os
from typing import Optional

logger = logging.getLogger("rover.display")

# --- Palette ---
BG        = (10,  18,  35)
BG_RADAR  = (5,   12,  22)
WHITE     = (220, 220, 220)
CYAN      = (0,   200, 255)
YELLOW    = (255, 215, 0)
RED       = (220, 50,  50)
BLUE      = (50,  100, 220)
DIM       = (60,  70,  90)
GRID      = (20,  35,  55)

# radar colours by distance
_NEAR_COL  = (255, 60,  60)    # < 500 mm
_MID_COL   = (255, 180, 30)    # 500–1500 mm
_FAR_COL   = (60,  220, 100)   # > 1500 mm


class FaceDisplay:
    # Physical display: 480×320 landscape.
    # Split: left half = face (240×320), right half = radar (240×320)
    W  = 480
    H  = 320
    HH = 240   # half-width split (face | radar)

    def __init__(self, fb_device: str = "/dev/fb0", rotation: int = 0,
                 mock: bool = False):
        self._fb       = fb_device
        self._rotation = rotation
        self._mock     = mock
        self._state    = "idle"
        self._scan: dict[int, float] = {}   # latest lidar scan
        self._scan_lock = threading.Lock()
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._screen   = None
        self._clock    = None
        self._pygame_ok = False
        self._pg        = None
        self._init_pygame()

    def _init_pygame(self) -> None:
        try:
            import pygame as pg
            if not self._mock:
                os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
                os.environ.setdefault("SDL_FBDEV", self._fb)
                os.environ["SDL_NOMOUSE"] = "1"
            # Init only display + font — do NOT call pg.init() which also
            # inits the mixer and grabs the audio device, conflicting with sounddevice
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            pg.display.init()
            pg.font.init()
            self._screen = pg.display.set_mode((self.W, self.H))
            pg.display.set_caption("Rover" + (" [MOCK]" if self._mock else ""))
            self._clock = pg.time.Clock()
            self._pg = pg
            self._pygame_ok = True
            mode = "desktop" if self._mock else self._fb
            logger.info(f"Display ready {self.W}×{self.H} → {mode}")
        except Exception as e:
            logger.warning(f"Display unavailable: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        self._state = state

    def update_radar(self, scan: dict) -> None:
        """Feed latest full 360° scan {angle_deg: distance_mm}."""
        with self._scan_lock:
            self._scan = dict(scan)

    @property
    def needs_main_thread(self) -> bool:
        """True on macOS — SDL/Cocoa requires pygame on the main thread."""
        import platform
        return self._mock and platform.system() == "Darwin"

    def start(self) -> None:
        """Start render loop in a background thread (Linux/Pi only)."""
        if not self._pygame_ok or self.needs_main_thread:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._render_loop, daemon=True, name="DisplayThread"
        )
        self._thread.start()

    def run(self) -> None:
        """Run render loop on the calling thread (required on macOS)."""
        if not self._pygame_ok:
            return
        self._running = True
        self._render_loop()

    def stop(self) -> None:
        self._running = False
        if self._pygame_ok:
            try:
                self._pg.display.quit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Main render loop
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        pg = self._pg
        t = 0.0
        blink_next = random.uniform(2.0, 5.0)
        blink_start = 0.0
        blinking = False
        mouth_phase = 0.0

        while self._running:
            dt = self._clock.tick(30) / 1000.0
            t += dt

            for ev in pg.event.get():
                if ev.type == pg.QUIT:
                    self._running = False

            state = self._state
            scr = self._screen
            scr.fill(BG)

            # blink
            if state in ("idle", "listening"):
                if not blinking and t >= blink_next:
                    blinking = True
                    blink_start = t
                if blinking and (t - blink_start) > 0.12:
                    blinking = False
                    blink_next = t + random.uniform(2.0, 6.0)
            else:
                blinking = False

            blink_ratio = 0.0
            if blinking:
                blink_ratio = math.sin((t - blink_start) / 0.12 * math.pi)

            if state == "speaking":
                mouth_phase += dt * 8.0

            # --- LEFT: face (0..HH × 0..H) ---
            face_surf = scr.subsurface((0, 0, self.HH, self.H))
            face_surf.fill(BG)
            self._draw_face(face_surf, pg, state, blink_ratio, t, mouth_phase)

            # divider
            pg.draw.line(scr, GRID, (self.HH, 0), (self.HH, self.H), 1)

            # --- RIGHT: radar (HH..W × 0..H) ---
            radar_surf = scr.subsurface((self.HH, 0, self.W - self.HH, self.H))
            radar_surf.fill(BG_RADAR)
            with self._scan_lock:
                scan = dict(self._scan)
            self._draw_radar(radar_surf, pg, scan, t)

            pg.display.flip()

    # ------------------------------------------------------------------
    # RADAR
    # ------------------------------------------------------------------

    def _draw_radar(self, surf, pg, scan: dict, t: float) -> None:
        # radar panel is (W-HH) × H = 240 × 320
        panel_w = self.W - self.HH
        cx, cy = panel_w // 2, self.H // 2
        max_r = 105    # px  — represents MAX_DIST_MM
        MAX_DIST = 3500.0

        # grid rings  (1 m, 2 m, 3 m)
        for ring_mm, label in [(1000, "1m"), (2000, "2m"), (3000, "3m")]:
            r_px = int(ring_mm / MAX_DIST * max_r)
            pg.draw.circle(surf, GRID, (cx, cy), r_px, 1)

        # cross-hairs
        pg.draw.line(surf, GRID, (cx, cy - max_r), (cx, cy + max_r), 1)
        pg.draw.line(surf, GRID, (cx - max_r, cy), (cx + max_r, cy), 1)

        # scan points
        if scan:
            for angle_deg, dist_mm in scan.items():
                if dist_mm <= 0:
                    continue
                r_px = min(int(dist_mm / MAX_DIST * max_r), max_r)
                # 0° = forward = up on screen  → subtract 90°
                rad = math.radians(angle_deg - 90)
                px = cx + int(r_px * math.cos(rad))
                py = cy + int(r_px * math.sin(rad))

                if dist_mm < 500:
                    col = _NEAR_COL
                    dot_r = 3
                elif dist_mm < 1500:
                    col = _MID_COL
                    dot_r = 2
                else:
                    col = _FAR_COL
                    dot_r = 1

                pg.draw.circle(surf, col, (px, py), dot_r)

        # robot body — small arrow pointing forward (up)
        body_pts = [
            (cx,      cy - 10),   # nose
            (cx - 7,  cy + 8),
            (cx,      cy + 4),
            (cx + 7,  cy + 8),
        ]
        pg.draw.polygon(surf, CYAN, body_pts)

        # "RADAR" label top-right
        try:
            font = pg.font.SysFont("monospace", 11)
            label_surf = font.render("RADAR", True, DIM)
            surf.blit(label_surf, (self.W - 52, 4))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # FACE
    # ------------------------------------------------------------------

    def _draw_face(self, surf, pg, state, blink_ratio, t, mouth_phase):
        # face panel: HH × H = 240 × 320
        cx    = self.HH // 2       # 120
        eye_y = self.H  // 2 - 20  # 140
        eye_gap = 68
        lx, rx = cx - eye_gap, cx + eye_gap

        colour = {
            "idle":      CYAN,
            "listening": CYAN,
            "thinking":  YELLOW,
            "speaking":  WHITE,
            "happy":     YELLOW,
            "surprised": WHITE,
            "angry":     RED,
            "sad":       BLUE,
        }.get(state, CYAN)

        if state == "happy":
            self._eyes_happy(surf, pg, lx, rx, eye_y, colour)
        elif state == "surprised":
            self._eyes_surprised(surf, pg, lx, rx, eye_y, colour)
        elif state == "angry":
            self._eyes_angry(surf, pg, lx, rx, eye_y, colour, blink_ratio)
        elif state == "sad":
            self._eyes_sad(surf, pg, lx, rx, eye_y, colour, blink_ratio)
        elif state == "thinking":
            self._eyes_normal(surf, pg, lx, rx, eye_y, colour, 0.4)
            self._thinking_dots(surf, pg, cx, eye_y + 90, t)
        else:
            self._eyes_normal(surf, pg, lx, rx, eye_y, colour, blink_ratio)

        if state == "speaking":
            self._mouth_talking(surf, pg, cx, eye_y + 95, mouth_phase)
        elif state in ("happy", "surprised"):
            self._mouth_smile(surf, pg, cx, eye_y + 95, state)

        # state label (small, bottom of face panel)
        try:
            font = pg.font.SysFont("monospace", 11)
            lbl  = font.render(state.upper(), True, DIM)
            surf.blit(lbl, (self.HH // 2 - lbl.get_width() // 2,
                            self.H - 18))
        except Exception:
            pass

    # --- eye helpers ---

    def _eyes_normal(self, surf, pg, lx, rx, ey, col, blink_ratio):
        r = 32
        for ex in (lx, rx):
            pg.draw.circle(surf, WHITE, (ex, ey), r)
            lid = int(r * 2 * blink_ratio)
            if lid > 0:
                pg.draw.rect(surf, BG, (ex - r, ey - r, r * 2, lid))
            pg.draw.circle(surf, col, (ex, ey), int(r * 0.55))
            pg.draw.circle(surf, (0, 0, 0), (ex, ey), int(r * 0.25))
            pg.draw.circle(surf, WHITE, (ex - 7, ey - 7), 5)

    def _eyes_happy(self, surf, pg, lx, rx, ey, col):
        r = 32
        for ex in (lx, rx):
            pg.draw.circle(surf, WHITE, (ex, ey), r)
            pg.draw.rect(surf, BG, (ex - r - 2, ey, r * 2 + 4, r + 4))
            pg.draw.arc(surf, col,
                        (ex - r, ey - r, r * 2, r * 2), 0, math.pi, 5)

    def _eyes_surprised(self, surf, pg, lx, rx, ey, col):
        r = 38
        for ex in (lx, rx):
            pg.draw.circle(surf, WHITE, (ex, ey), r)
            pg.draw.circle(surf, col, (ex, ey), int(r * 0.6))
            pg.draw.circle(surf, (0, 0, 0), (ex, ey), int(r * 0.3))
            pg.draw.circle(surf, WHITE, (ex - 9, ey - 9), 6)
            pg.draw.line(surf, WHITE,
                         (ex - r + 4, ey - r - 10),
                         (ex + r - 4, ey - r - 16), 4)

    def _eyes_angry(self, surf, pg, lx, rx, ey, col, blink_ratio):
        self._eyes_normal(surf, pg, lx, rx, ey, col, blink_ratio)
        for ex, sign in ((lx, 1), (rx, -1)):
            pg.draw.line(surf, WHITE,
                         (ex + sign * 10, ey - 36),
                         (ex - sign * 28, ey - 50), 5)

    def _eyes_sad(self, surf, pg, lx, rx, ey, col, blink_ratio):
        self._eyes_normal(surf, pg, lx, rx, ey, col, blink_ratio)
        r = 32
        for ex, sign in ((lx, -1), (rx, 1)):
            pg.draw.line(surf, WHITE,
                         (ex + sign * (r - 4), ey - r + 10),
                         (ex - sign * (r - 14), ey - r - 8), 4)

    def _mouth_talking(self, surf, pg, cx, my, phase):
        opening = int(12 * abs(math.sin(phase)))
        pg.draw.ellipse(surf, WHITE,
                        (cx - 26, my - opening // 2, 52, max(4, opening)))

    def _mouth_smile(self, surf, pg, cx, my, state):
        if state == "happy":
            pg.draw.arc(surf, WHITE,
                        (cx - 36, my - 18, 72, 36), math.pi, 2 * math.pi, 4)
        elif state == "surprised":
            pg.draw.ellipse(surf, WHITE, (cx - 16, my - 10, 32, 26))

    def _thinking_dots(self, surf, pg, cx, dy, t):
        for i in range(3):
            offset = math.sin(t * 4 + i * 1.2) * 7
            pg.draw.circle(surf, CYAN,
                           (cx - 20 + i * 20, int(dy + offset)), 6)
