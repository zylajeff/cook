"""The Block-M reference contour.

The mark is rasterised from a normalised polygon at import time so the template
is a real OpenCV contour: that is what ``cv2.matchShapes`` consumes, and it lets
the geometric reference values (extent, solidity) be measured rather than
guessed.
"""
import cv2
import numpy as np

from ..cvcompat import find_contours

#: Michigan Block M outline, normalised to a unit square with y pointing down.
#: Twelve vertices: two outer legs, two inner legs, and the central V.
BLOCK_M_POLYGON = np.array(
    [
        (0.00, 0.00),
        (0.26, 0.00),
        (0.50, 0.44),
        (0.74, 0.00),
        (1.00, 0.00),
        (1.00, 1.00),
        (0.76, 1.00),
        (0.76, 0.34),
        (0.50, 0.80),
        (0.24, 0.34),
        (0.24, 1.00),
        (0.00, 1.00),
    ],
    dtype=np.float32,
)

_RASTER = 256


def _build_template():
    canvas = np.zeros((_RASTER, _RASTER), dtype=np.uint8)
    points = np.round(BLOCK_M_POLYGON * (_RASTER - 1)).astype(np.int32)
    cv2.fillPoly(canvas, [points], 255)
    return max(find_contours(canvas), key=cv2.contourArea)


TEMPLATE_CONTOUR = _build_template()

_area = cv2.contourArea(TEMPLATE_CONTOUR)
_x, _y, _w, _h = cv2.boundingRect(TEMPLATE_CONTOUR)

#: Fraction of the bounding box the mark fills (~0.66 for the block M).
TEMPLATE_EXTENT = _area / float(_w * _h)
#: Fraction of the convex hull the mark fills (~0.72); the central V is the notch.
TEMPLATE_SOLIDITY = _area / float(cv2.contourArea(cv2.convexHull(TEMPLATE_CONTOUR)))
#: Width / height of the mark.
TEMPLATE_ASPECT = _w / float(_h)


def render(size: int = 256, color=(255, 255, 255), background=(0, 0, 0)) -> np.ndarray:
    """Draw the template as a BGR image. Used by tests and the synthetic camera."""
    canvas = np.zeros((size, size, 3), dtype=np.uint8)
    canvas[:] = background
    points = np.round(BLOCK_M_POLYGON * (size - 1)).astype(np.int32)
    cv2.fillPoly(canvas, [points], color)
    return canvas
