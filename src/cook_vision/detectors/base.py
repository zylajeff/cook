"""Detector interface shared by every backend."""
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass(frozen=True)
class Detection:
    """One candidate target in image space."""

    label: str
    confidence: float
    #: (left, top, width, height) in pixels.
    box: Tuple[int, int, int, int]

    @property
    def center(self) -> Tuple[float, float]:
        left, top, width, height = self.box
        return left + width / 2.0, top + height / 2.0

    @property
    def area(self) -> int:
        return self.box[2] * self.box[3]


class Detector:
    """Base class; backends override :meth:`detect`."""

    name = "detector"

    def detect(self, frame: np.ndarray) -> List[Detection]:
        raise NotImplementedError

    def close(self) -> None:
        pass


def clip_box(box, width, height) -> Tuple[int, int, int, int]:
    """Clamp a (left, top, w, h) box to the frame, never returning a negative size."""
    left, top, box_width, box_height = (int(v) for v in box)
    left = max(0, min(left, width))
    top = max(0, min(top, height))
    right = max(left, min(left + box_width, width))
    bottom = max(top, min(top + box_height, height))
    return left, top, right - left, bottom - top
