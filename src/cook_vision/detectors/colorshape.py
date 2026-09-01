"""Colour + shape Block-M detector.

Requires no training data. The mark is isolated by its maize hue, then each
blob is scored against the Block-M template on four independent geometric
cues. A yellow blob only reads as a target if it is *also* M-shaped.
"""
from typing import List

import cv2
import numpy as np

from ..cvcompat import MATCH_I1, find_contours
from .base import Detection, Detector, clip_box
from .template import (
    TEMPLATE_ASPECT,
    TEMPLATE_CONTOUR,
    TEMPLATE_EXTENT,
    TEMPLATE_SOLIDITY,
)

#: Relative weight of each cue in the final confidence.
_WEIGHTS = {"shape": 0.45, "extent": 0.20, "solidity": 0.20, "aspect": 0.15}


def _tolerance_score(value: float, reference: float, tolerance: float) -> float:
    """1.0 when ``value`` equals ``reference``, falling to 0.0 at ``tolerance`` away."""
    if reference <= 0 or tolerance <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(value - reference) / (reference * tolerance))


class ColorShapeDetector(Detector):
    name = "color"

    def __init__(self, config) -> None:
        self.config = config
        self.maize_lower = np.array(config.maize_lower, dtype=np.uint8)
        self.maize_upper = np.array(config.maize_upper, dtype=np.uint8)
        self.blue_lower = np.array(config.blue_lower, dtype=np.uint8)
        self.blue_upper = np.array(config.blue_upper, dtype=np.uint8)
        size = max(1, config.morph_size)
        # RECT rather than ELLIPSE: measurably cheaper, and at this scale the
        # kernel shape makes no difference to the result.
        self._kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))

    def mask(self, frame: np.ndarray) -> np.ndarray:
        """Binary maize-or-blue mask. Exposed so the HUD can render a diagnostic view."""
        source = cv2.GaussianBlur(frame, (5, 5), 0) if self.config.blur else frame
        hsv = cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
        maize = cv2.inRange(hsv, self.maize_lower, self.maize_upper)
        blue = cv2.inRange(hsv, self.blue_lower, self.blue_upper)
        mask = cv2.bitwise_or(maize, blue)
        # Close first to bridge sensor speckle inside the mark, then open to drop
        # isolated noise pixels. Order matters: opening first would eat the thin
        # inner legs of the M. One iteration of each is enough post-downscale.
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        return mask

    def score(self, contour) -> float:
        """Confidence that ``contour`` is a Block M, in 0..1."""
        area = cv2.contourArea(contour)
        if area < self.config.min_area_px:
            return 0.0

        _, _, width, height = cv2.boundingRect(contour)
        if width <= 0 or height <= 0:
            return 0.0

        hull_area = cv2.contourArea(cv2.convexHull(contour))
        if hull_area <= 0:
            return 0.0

        distance = cv2.matchShapes(contour, TEMPLATE_CONTOUR, MATCH_I1, 0.0)
        if distance > self.config.max_shape_distance:
            return 0.0

        scores = {
            "shape": 1.0 - distance / self.config.max_shape_distance,
            "extent": _tolerance_score(area / (width * height), TEMPLATE_EXTENT, 0.45),
            "solidity": _tolerance_score(area / hull_area, TEMPLATE_SOLIDITY, 0.45),
            "aspect": _tolerance_score(width / float(height), TEMPLATE_ASPECT, 0.55),
        }
        return sum(_WEIGHTS[key] * value for key, value in scores.items())

    def detect(self, frame: np.ndarray) -> List[Detection]:
        height, width = frame.shape[:2]
        contours = find_contours(self.mask(frame))

        detections = []
        for contour in contours:
            confidence = self.score(contour)
            if confidence < self.config.confidence:
                continue
            box = clip_box(cv2.boundingRect(contour), width, height)
            if box[2] <= 0 or box[3] <= 0:
                continue
            detections.append(Detection("BLOCK-M", confidence, box))

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections
