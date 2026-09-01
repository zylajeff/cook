"""Target tracking and seeker lock state.

Detections are per-frame and jittery; a seeker needs continuity. Tracks are
matched by centre proximity, smoothed, and only promoted to LOCKED once they
have persisted for several frames. That dwell requirement is the main defence
against firing at a one-frame false positive.
"""
import itertools
import math
from typing import List, Optional, Tuple

SEARCHING = "SEARCHING"
TRACKING = "TRACKING"
LOCKED = "LOCKED"


class Track:
    """One persistent target."""

    _ids = itertools.count(1)

    def __init__(self, detection, smoothing):
        self.id = next(Track._ids)
        self.box = tuple(float(v) for v in detection.box)
        self.confidence = detection.confidence
        self.label = detection.label
        self.hits = 1
        self.missed = 0
        self._smoothing = smoothing

    def update(self, detection) -> None:
        alpha = self._smoothing
        self.box = tuple(
            alpha * new + (1.0 - alpha) * old for old, new in zip(self.box, detection.box)
        )
        # Confidence is smoothed harder than geometry so a single weak frame does
        # not drop a solid lock.
        self.confidence = 0.3 * detection.confidence + 0.7 * self.confidence
        self.label = detection.label
        self.hits += 1
        self.missed = 0

    def mark_missed(self) -> None:
        self.missed += 1
        self.hits = max(0, self.hits - 1)

    @property
    def center(self) -> Tuple[float, float]:
        left, top, width, height = self.box
        return left + width / 2.0, top + height / 2.0

    @property
    def int_box(self) -> Tuple[int, int, int, int]:
        return tuple(int(round(v)) for v in self.box)

    def is_locked(self, lock_frames: int) -> bool:
        return self.hits >= lock_frames and self.missed == 0


class TargetTracker:
    def __init__(self, config):
        self.config = config
        self.tracks: List[Track] = []

    def update(self, detections, frame_shape) -> List[Track]:
        height, width = frame_shape[:2]
        threshold = self.config.match_distance * math.hypot(width, height)

        unmatched = list(detections)
        for track in self.tracks:
            best, best_distance = None, threshold
            for detection in unmatched:
                # math.dist is 3.8+; the Jetson's JetPack 4 Python is 3.6.
                (tx, ty), (dx, dy) = track.center, detection.center
                distance = math.hypot(tx - dx, ty - dy)
                if distance < best_distance:
                    best, best_distance = detection, distance
            if best is None:
                track.mark_missed()
            else:
                track.update(best)
                unmatched.remove(best)

        self.tracks = [t for t in self.tracks if t.missed <= self.config.max_missed_frames]
        for detection in unmatched:
            self.tracks.append(Track(detection, self.config.smoothing))
        return self.tracks

    @property
    def primary(self) -> Optional[Track]:
        """The track the seeker is committed to: the strongest, best-established one."""
        candidates = [t for t in self.tracks if t.missed == 0]
        if not candidates:
            return None
        return max(candidates, key=lambda t: (t.hits >= self.config.lock_frames, t.confidence))

    @property
    def state(self) -> str:
        target = self.primary
        if target is None:
            return SEARCHING
        return LOCKED if target.is_locked(self.config.lock_frames) else TRACKING

    def lock_progress(self) -> float:
        """0..1 ramp toward lock, used to close the seeker brackets on screen."""
        target = self.primary
        if target is None:
            return 0.0
        return min(1.0, target.hits / float(self.config.lock_frames))
