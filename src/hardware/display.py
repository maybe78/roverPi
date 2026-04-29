"""
Face animation for 320×480 SPI color display (ILI9488 / ST7796).

The display is driven via the Linux framebuffer (/dev/fb1).
pygame renders to the framebuffer directly.

States and their visual:
  idle       — eyes blinking slowly at random intervals
  listening  — eyes wide open, cyan iris
  thinking   — eyes half-closed, rotating dots below
  speaking   — mouth animates open/close
  happy      — eyes curved up (^_^)
  surprised  — eyes fully round, raised eyebrows
  angry      — V-shaped eyebrows, narrowed eyes
  sad        — eyes curved down, drooped lids
"""

import logging
import threading
import time
import math
import random
import os
from typing import Optional

logger = logging.getLogger("rover.display")

# Colours
BG      = (15,  25,  42)
WHITE   = (220, 220, 220)
CYAN    = (0,   200, 255)
YELLOW  = (255, 220, 0)
RED     = (220, 50,  50)
BLUE    = (50,  100, 220)


class FaceDisplay:
    W = 320
    H = 480

    def __init__(self, fb_device: str = "/dev/fb1", rotation: int = 0):
        self._fb = fb_device
        self._rotation = rotation
        self._state = "idle"
        self._prev_state = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._screen = None
        self._clock = None
        self._pygame_ok = False
        self._init_pygame()

    def _init_pygame(self) -> None:
        try:
            import pygame
            os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
            os.environ.setdefault("SDL_FBDEV", self._fb)
            os.environ["SDL_NOMOUSE"] = "1"
            pygame.init()
            self._screen = pygame.display.set_mode(
                (self.W, self.H), flags=0
            )
            pygame.display.set_caption("Rover Face")
            self._clock = pygame.time.Clock()
            self._pygame = pygame
            self._pygame_ok = True
            logger.info(f"Display ready ({self.W}×{self.H}) on {self._fb}")
        except Exception as e:
            logger.warning(f"Display unavailable: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        self._state = state

    def start(self) -> None:
        if not self._pygame_ok:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._render_loop, daemon=True, name="DisplayThread"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._pygame_ok:
            try:
                self._pygame.quit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Render loop
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        pg = self._pygame
        t = 0.0
        blink_t = random.uniform(2.0, 5.0)
        blink_dur = 0.12
        blinking = False
        blink_start = 0.0
        mouth_phase = 0.0

        while self._running:
            dt = self._clock.tick(30) / 1000.0
            t += dt

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self._running = False

            state = self._state
            screen = self._screen
            screen.fill(BG)

            # blink logic (only in idle / listening)
            if state in ("idle", "listening"):
                if not blinking and t >= blink_t:
                    blinking = True
                    blink_start = t
                if blinking and (t - blink_start) > blink_dur:
                    blinking = False
                    blink_t = t + random.uniform(2.0, 6.0)
            else:
                blinking = False

            blink_ratio = 0.0
            if blinking:
                progress = (t - blink_start) / blink_dur
                blink_ratio = math.sin(progress * math.pi)

            if state == "speaking":
                mouth_phase += dt * 8.0

            self._draw_face(screen, pg, state, blink_ratio, t, mouth_phase)
            pg.display.flip()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_face(self, screen, pg, state, blink_ratio, t, mouth_phase):
        cx = self.W // 2
        eye_y = self.H // 2 - 60
        eye_gap = 70
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
            self._draw_happy_eyes(screen, pg, lx, rx, eye_y, colour)
        elif state == "surprised":
            self._draw_surprised_eyes(screen, pg, lx, rx, eye_y, colour)
        elif state == "angry":
            self._draw_angry_eyes(screen, pg, lx, rx, eye_y, colour, blink_ratio)
        elif state == "sad":
            self._draw_sad_eyes(screen, pg, lx, rx, eye_y, colour, blink_ratio)
        elif state == "thinking":
            self._draw_normal_eyes(screen, pg, lx, rx, eye_y, colour, blink_ratio=0.4)
            self._draw_thinking_dots(screen, pg, cx, eye_y + 120, t)
        else:
            self._draw_normal_eyes(screen, pg, lx, rx, eye_y, colour, blink_ratio)

        if state == "speaking":
            self._draw_mouth(screen, pg, cx, eye_y + 130, mouth_phase)
        elif state in ("happy", "surprised"):
            self._draw_smile(screen, pg, cx, eye_y + 130, state)

    def _draw_normal_eyes(self, screen, pg, lx, rx, ey, colour, blink_ratio):
        r = 36
        for ex in (lx, rx):
            # white sclera
            pg.draw.circle(screen, WHITE, (ex, ey), r)
            # blink lid (top down)
            lid_h = int(r * 2 * blink_ratio)
            if lid_h > 0:
                pg.draw.rect(screen, BG, (ex - r, ey - r, r * 2, lid_h))
            # iris
            pg.draw.circle(screen, colour, (ex, ey), int(r * 0.55))
            # pupil
            pg.draw.circle(screen, (0, 0, 0), (ex, ey), int(r * 0.25))
            # shine
            pg.draw.circle(screen, WHITE, (ex - 8, ey - 8), 6)

    def _draw_happy_eyes(self, screen, pg, lx, rx, ey, colour):
        r = 36
        for ex in (lx, rx):
            pg.draw.circle(screen, WHITE, (ex, ey), r)
            # cover bottom half
            pg.draw.rect(screen, BG, (ex - r - 2, ey, r * 2 + 4, r + 4))
            pg.draw.arc(screen, colour,
                        (ex - r, ey - r, r * 2, r * 2),
                        0, math.pi, 5)

    def _draw_surprised_eyes(self, screen, pg, lx, rx, ey, colour):
        r = 44
        for ex in (lx, rx):
            pg.draw.circle(screen, WHITE, (ex, ey), r)
            pg.draw.circle(screen, colour, (ex, ey), int(r * 0.6))
            pg.draw.circle(screen, (0, 0, 0), (ex, ey), int(r * 0.3))
            pg.draw.circle(screen, WHITE, (ex - 10, ey - 10), 7)
            # raised eyebrow
            pg.draw.line(screen, WHITE,
                         (ex - r + 4, ey - r - 12),
                         (ex + r - 4, ey - r - 18), 4)

    def _draw_angry_eyes(self, screen, pg, lx, rx, ey, colour, blink_ratio):
        self._draw_normal_eyes(screen, pg, lx, rx, ey, colour, blink_ratio)
        # V-shaped inner brows
        for ex, sign in ((lx, 1), (rx, -1)):
            inner = (ex + sign * 10, ey - 40)
            outer = (ex - sign * 30, ey - 55)
            pg.draw.line(screen, WHITE, inner, outer, 5)

    def _draw_sad_eyes(self, screen, pg, lx, rx, ey, colour, blink_ratio):
        self._draw_normal_eyes(screen, pg, lx, rx, ey, colour, blink_ratio)
        r = 36
        for ex, sign in ((lx, -1), (rx, 1)):
            outer = (ex + sign * (r - 4), ey - r + 10)
            inner = (ex - sign * (r - 14), ey - r - 8)
            pg.draw.line(screen, WHITE, inner, outer, 4)

    def _draw_mouth(self, screen, pg, cx, my, phase):
        opening = int(14 * abs(math.sin(phase)))
        pg.draw.ellipse(screen, WHITE,
                        (cx - 28, my - opening // 2, 56, max(4, opening)))

    def _draw_smile(self, screen, pg, cx, my, state):
        if state == "happy":
            pg.draw.arc(screen, WHITE,
                        (cx - 40, my - 20, 80, 40),
                        math.pi, 2 * math.pi, 5)
        elif state == "surprised":
            pg.draw.ellipse(screen, WHITE, (cx - 18, my - 10, 36, 30))

    def _draw_thinking_dots(self, screen, pg, cx, dy, t):
        for i in range(3):
            offset = math.sin(t * 4 + i * 1.2) * 8
            pg.draw.circle(screen, CYAN,
                           (cx - 24 + i * 24, int(dy + offset)), 7)
