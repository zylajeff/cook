"""Missile-seeker head-up display.

Everything is drawn with OpenCV primitives so it runs on the Nano without a UI
toolkit. The visual language is deliberate: colour encodes seeker state, the
target brackets physically close as lock builds, and the interlock chain is
always on screen so the operator can see why the rig will or will not fire.
"""
import math
import time

import cv2

from .tracker import LOCKED, SEARCHING, TRACKING

FONT = cv2.FONT_HERSHEY_SIMPLEX
MONO = cv2.FONT_HERSHEY_PLAIN

#: BGR palette keyed by seeker state.
STATE_COLORS = {
    SEARCHING: (140, 255, 120),   # cool green: nothing held
    TRACKING: (60, 200, 255),     # amber: candidate acquired
    LOCKED: (60, 60, 255),        # red: committed
}
DIM = (90, 110, 90)
WHITE = (235, 240, 240)
RED = (60, 60, 255)
GREEN = (140, 255, 120)


def _text(frame, label, origin, color=WHITE, scale=0.45, thickness=1, font=FONT):
    cv2.putText(frame, label, origin, font, scale, color, thickness, cv2.LINE_AA)


class SeekerHud:
    def __init__(self, config, firing_config):
        self.config = config
        self.firing_config = firing_config
        self._scanlines = None
        self._flash_until = 0.0

    # -- effects -------------------------------------------------------------

    def flash(self, seconds=0.18):
        """Trigger the muzzle-flash overlay."""
        self._flash_until = time.monotonic() + seconds

    def _apply_scanlines(self, frame):
        """Multiply in a cached scanline + vignette mask.

        The mask is baked to uint8 and applied with cv2.multiply rather than a
        float broadcast: on a Jetson Nano the float version dominated the whole
        frame budget. Measured on a 1280x720 frame, uint8 multiply is ~11x
        faster than `frame * float_mask` followed by convertScaleAbs, and the
        two differ by at most 1 per channel.
        """
        if not self.config.effects:
            return frame
        height, width = frame.shape[:2]
        if self._scanlines is None or self._scanlines.shape[:2] != (height, width):
            import numpy as np

            mask = np.ones((height, width), dtype=np.float32)
            mask[::3] = 0.88
            # Corner vignette, so the eye is pulled to the reticle.
            ys = np.linspace(-1.0, 1.0, height).reshape(-1, 1)
            xs = np.linspace(-1.0, 1.0, width).reshape(1, -1)
            radius = np.sqrt(xs ** 2 + ys ** 2) / math.sqrt(2.0)
            mask *= np.clip(1.12 - 0.55 * radius ** 2, 0.0, 1.0)
            baked = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
            self._scanlines = cv2.cvtColor(baked, cv2.COLOR_GRAY2BGR)
        return cv2.multiply(frame, self._scanlines, scale=1 / 255.0)

    # -- chrome --------------------------------------------------------------

    def _reticle(self, frame, color, locked):
        height, width = frame.shape[:2]
        cx, cy = width // 2, height // 2
        gap, arm = 14, 34

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cv2.line(
                frame,
                (cx + dx * gap, cy + dy * gap),
                (cx + dx * (gap + arm), cy + dy * (gap + arm)),
                color, 1, cv2.LINE_AA,
            )
        cv2.circle(frame, (cx, cy), 3, color, -1, cv2.LINE_AA)

        # Bore-tolerance gate: targets inside this band are in front of the barrel.
        bore = int(self.firing_config.bore_tolerance * width)
        for sign in (-1, 1):
            x = cx + sign * bore
            cv2.line(frame, (x, cy - 26), (x, cy + 26), DIM, 1, cv2.LINE_AA)
            cv2.line(frame, (x, cy - 26), (x - sign * 6, cy - 26), DIM, 1, cv2.LINE_AA)
            cv2.line(frame, (x, cy + 26), (x - sign * 6, cy + 26), DIM, 1, cv2.LINE_AA)

        # Horizon ladder.
        for step in range(-2, 3):
            if step == 0:
                continue
            y = cy + step * 46
            length = 10 if step % 2 else 18
            cv2.line(frame, (cx - bore - 30, y), (cx - bore - 30 + length, y), DIM, 1)
            cv2.line(frame, (cx + bore + 30 - length, y), (cx + bore + 30, y), DIM, 1)

        if locked:
            ring = 52 + int(6 * math.sin(time.monotonic() * 9))
            cv2.circle(frame, (cx, cy), ring, color, 1, cv2.LINE_AA)

    def _target_brackets(self, frame, track, color, progress, locked):
        left, top, width, height = track.int_box
        right, bottom = left + width, top + height
        # Brackets start well outside the target and close onto it as lock builds.
        pad = int((1.0 - progress) * max(width, height) * 0.55)
        left, top, right, bottom = left - pad, top - pad, right + pad, bottom + pad
        arm = max(10, int(min(right - left, bottom - top) * 0.28))
        thickness = 2 if locked else 1

        corners = (
            ((left, top), (1, 1)),
            ((right, top), (-1, 1)),
            ((left, bottom), (1, -1)),
            ((right, bottom), (-1, -1)),
        )
        for (x, y), (sx, sy) in corners:
            cv2.line(frame, (x, y), (x + sx * arm, y), color, thickness, cv2.LINE_AA)
            cv2.line(frame, (x, y), (x, y + sy * arm), color, thickness, cv2.LINE_AA)

        cx, cy = (int(v) for v in track.center)
        cv2.drawMarker(frame, (cx, cy), color, cv2.MARKER_CROSS, 14, 1, cv2.LINE_AA)

        # Lead line from the reticle to the target, with the offset called out.
        fh, fw = frame.shape[:2]
        cv2.line(frame, (fw // 2, fh // 2), (cx, cy), DIM, 1, cv2.LINE_AA)

        tag = "TGT-{0:02d} {1:.0%}".format(track.id, track.confidence)
        _text(frame, tag, (left, max(14, top - 8)), color, 0.48, 1)
        _text(
            frame,
            "dX{0:+05d} dY{1:+05d}".format(cx - fw // 2, cy - fh // 2),
            (left, bottom + 18),
            DIM, 0.4, 1,
        )

        # Confidence bar under the tag.
        bar_w = 74
        cv2.rectangle(frame, (left, top - 6), (left + bar_w, top - 3), DIM, 1)
        filled = int(bar_w * min(1.0, track.confidence))
        cv2.rectangle(frame, (left, top - 6), (left + filled, top - 3), color, -1)

    def _status_bar(self, frame, state, color, telemetry):
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (width, 30), (18, 20, 18), -1)
        cv2.line(frame, (0, 30), (width, 30), color, 1)

        _text(frame, "COOK // SEEKER", (12, 20), color, 0.55, 1)
        _text(frame, state, (190, 20), color, 0.55, 2)

        right = [
            "{0:.0f} FPS".format(telemetry.get("fps", 0.0)),
            "DET:{0}".format(telemetry.get("backend", "?")),
            "SRC:{0}".format(telemetry.get("source", "?")),
            "SHOTS:{0}".format(telemetry.get("shots", 0)),
        ]
        x = width - 12
        for item in reversed(right):
            (tw, _), _ = cv2.getTextSize(item, FONT, 0.45, 1)
            x -= tw
            _text(frame, item, (x, 20), WHITE, 0.45, 1)
            x -= 18

    def _arm_indicator(self, frame, armed, safety):
        height, width = frame.shape[:2]
        if armed and not safety:
            blink = int(time.monotonic() * 3) % 2 == 0
            color = RED if blink else (40, 40, 150)
            label = "ARMED"
        else:
            color = GREEN
            label = "SAFE"

        (tw, th), _ = cv2.getTextSize(label, FONT, 0.7, 2)
        bottom = height - 34  # clear of the interlock strip
        x, y = width - tw - 26, bottom - 10
        cv2.rectangle(frame, (x - 12, y - th - 10), (width - 8, bottom), (18, 20, 18), -1)
        cv2.rectangle(frame, (x - 12, y - th - 10), (width - 8, bottom), color, 1)
        _text(frame, label, (x, y), color, 0.7, 2)

    def _interlocks(self, frame, decision):
        height, width = frame.shape[:2]
        labels = [name.upper() for name in decision.checks]

        # Fit the row to the frame. The Nano's panel is narrow, and an interlock
        # that runs off the edge is an interlock the operator cannot check.
        scale, gap, dot = 0.38, 30, 14
        for _ in range(8):
            widths = [cv2.getTextSize(text, FONT, scale, 1)[0][0] for text in labels]
            if sum(widths) + len(labels) * (dot + gap) <= width - 24:
                break
            scale *= 0.9
            gap = max(7, int(gap * 0.8))
            dot = max(12, int(dot * 0.85))

        # Opaque strip: the vignette dims the corners, and this row must stay legible
        # over whatever the camera happens to be looking at.
        strip = 26
        cv2.rectangle(frame, (0, height - strip), (width, height), (18, 20, 18), -1)
        cv2.line(frame, (0, height - strip), (width, height - strip), DIM, 1)
        _text(frame, "INTERLOCKS", (12, height - strip - 7), DIM, 0.4, 1)

        y = height - 9
        x = 12
        for (name, passed), text_width in zip(decision.checks.items(), widths):
            color = GREEN if passed else RED
            cv2.circle(frame, (x + 4, y - 4), 4, color, -1 if passed else 1, cv2.LINE_AA)
            _text(frame, name.upper(), (x + dot, y), DIM if passed else color, scale, 1)
            x += text_width + dot + gap

    def _cooldown(self, frame, controller):
        remaining = controller.cooldown_remaining
        if remaining <= 0:
            return
        width = frame.shape[1]
        total = max(1e-3, controller.config.cooldown_seconds)
        bar = int(160 * (1.0 - remaining / total))
        # Sits above the interlock row; keep the two from colliding.
        y = frame.shape[0] - 92
        cv2.rectangle(frame, (12, y), (172, y + 6), DIM, 1)
        cv2.rectangle(frame, (12, y), (12 + bar, y + 6), (60, 200, 255), -1)
        _text(frame, "RELOAD {0:.1f}s".format(remaining), (180, y + 7), (60, 200, 255), 0.4, 1)

    def _flash_overlay(self, frame):
        remaining = self._flash_until - time.monotonic()
        if remaining <= 0:
            return frame
        alpha = min(0.55, remaining * 2.4)
        overlay = frame.copy()
        overlay[:] = (80, 80, 255)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        height, width = frame.shape[:2]
        _text(frame, "FIRE", (width // 2 - 44, height // 2 - 70), (255, 255, 255), 1.1, 3)
        return frame

    # -- entry point ---------------------------------------------------------

    def render(self, frame, tracker, decision, controller, telemetry):
        frame = self._apply_scanlines(frame)
        state = tracker.state
        color = STATE_COLORS[state]
        progress = tracker.lock_progress()

        primary = tracker.primary
        for track in tracker.tracks:
            if track.missed:
                continue
            is_primary = track is primary
            self._target_brackets(
                frame,
                track,
                color if is_primary else DIM,
                progress if is_primary else 1.0,
                is_primary and state == LOCKED,
            )

        self._reticle(frame, color, state == LOCKED)
        self._status_bar(frame, state, color, telemetry)
        self._interlocks(frame, decision)
        self._cooldown(frame, controller)
        self._arm_indicator(frame, controller.arm_switch.is_armed, controller.software_safe)
        return self._flash_overlay(frame)
