"""Firing control: the interlock chain between a locked target and the solenoid.

Every condition is evaluated on every frame and reported by name, so the HUD can
show the operator exactly which interlock is holding — never just "won't fire".
The hardware toggle switch is the outermost gate and is never bypassed in
software.
"""
import logging
import time
from collections import OrderedDict
from typing import Optional

from .tracker import LOCKED

LOGGER = logging.getLogger(__name__)


class FireDecision:
    """Result of evaluating the interlock chain for one frame."""

    def __init__(self, checks: "OrderedDict[str, bool]"):
        self.checks = checks

    @property
    def ready(self) -> bool:
        return all(self.checks.values())

    @property
    def blocking(self):
        """Names of the failed interlocks, in evaluation order."""
        return [name for name, passed in self.checks.items() if not passed]

    @property
    def first_block(self) -> Optional[str]:
        blocking = self.blocking
        return blocking[0] if blocking else None


class FireController:
    def __init__(self, relay, arm_switch, config):
        self.relay = relay
        self.arm_switch = arm_switch
        self.config = config
        self.shots = 0
        self.last_shot_at = None
        self._started_at = time.monotonic()
        #: Operator-held software safety, on top of the hardware switch.
        self.software_safe = False
        self._fire_requested = False

    # -- state ---------------------------------------------------------------

    def request_fire(self) -> None:
        """Latch a manual trigger press; consumed by the next :meth:`update`."""
        self._fire_requested = True

    def toggle_software_safe(self) -> bool:
        self.software_safe = not self.software_safe
        LOGGER.info("Software safety %s", "ON" if self.software_safe else "OFF")
        return self.software_safe

    @property
    def cooldown_remaining(self) -> float:
        if self.last_shot_at is None:
            return 0.0
        elapsed = time.monotonic() - self.last_shot_at
        return max(0.0, self.config.cooldown_seconds - elapsed)

    @property
    def startup_remaining(self) -> float:
        elapsed = time.monotonic() - self._started_at
        return max(0.0, self.config.startup_lockout_seconds - elapsed)

    def bore_error(self, track, frame_shape) -> Optional[float]:
        """Horizontal miss distance from the reticle, as a fraction of frame width.

        The launcher is fixed forward in this build, so a target the seeker has
        locked is only actually in front of the barrel when it is near centre.
        """
        if track is None:
            return None
        width = frame_shape[1]
        center_x = track.center[0]
        return abs(center_x - width / 2.0) / float(width)

    # -- interlocks ----------------------------------------------------------

    def evaluate(self, tracker, frame_shape) -> FireDecision:
        target = tracker.primary
        error = self.bore_error(target, frame_shape)
        checks = OrderedDict()
        checks["startup"] = self.startup_remaining <= 0.0
        checks["arm switch"] = self.arm_switch.is_armed
        checks["software safe"] = not self.software_safe
        checks["target lock"] = tracker.state == LOCKED
        checks["confidence"] = (
            target is not None and target.confidence >= self.config.fire_confidence
        )
        checks["on bore"] = error is not None and error <= self.config.bore_tolerance
        checks["cooldown"] = self.cooldown_remaining <= 0.0
        checks["relay idle"] = not self.relay.is_energised
        return FireDecision(checks)

    # -- main loop hook ------------------------------------------------------

    def update(self, tracker, frame_shape) -> FireDecision:
        """Evaluate interlocks and fire if permitted. Call once per frame."""
        self.relay.update()
        decision = self.evaluate(tracker, frame_shape)

        triggered = self.config.auto_fire or self._fire_requested
        if decision.ready and triggered:
            self._fire()
        elif self._fire_requested and not decision.ready:
            LOGGER.info("Manual trigger refused: %s", ", ".join(decision.blocking))

        self._fire_requested = False
        return decision

    def _fire(self) -> None:
        self.relay.pulse(self.config.pulse_seconds)
        self.last_shot_at = time.monotonic()
        self.shots += 1
        LOGGER.info("FIRE (shot %d)", self.shots)

    def safe(self) -> None:
        """Force the output to its inactive state; called on shutdown."""
        self.relay.deenergise()
