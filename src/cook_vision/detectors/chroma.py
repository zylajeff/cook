"""Chroma Block-M detector.

HSV thresholding needs a pixel to carry enough saturation and value to place
its hue reliably. A dim, warm-white-balanced image pushes real maize toward
"dim brown" (measured: B 73 G 88 R 113, brightness 113/255) and HSV misses it
outright -- 0.000 confidence where a red-minus-blue chroma difference scored
0.997 under the same simulated conditions (see docs/status.md).

The raw R-B difference survives darkening because it does not route through
hue at all: maize stays R-heavy and Michigan blue stays B-heavy however dim
the frame gets, right up until the image is actually black. Everything past
the mask -- shape scoring, morphology, box extraction -- is identical to
:class:`ColorShapeDetector`, so this only overrides ``mask``.

Known limitation: R-B alone cannot tell maize from generic red, or Michigan
blue from violet/magenta, the way HSV's hue check can -- both maize and red
have R well above B. Gating on G-B too would rule red out, but the measured
dim-maize sample above has G-B of only 15 against R-B's 40, so that gate would
throw away the exact case this backend exists for. Shape scoring is the only
thing standing between a red decoy and a false positive here; that is an
acceptable trade for a mark that otherwise reads as a black hole.
"""
import cv2
import numpy as np

from .colorshape import ColorShapeDetector


class ChromaShapeDetector(ColorShapeDetector):
    name = "chroma"

    def mask(self, frame: np.ndarray) -> np.ndarray:
        source = cv2.GaussianBlur(frame, (5, 5), 0) if self.config.blur else frame
        blue, _green, red = cv2.split(source)
        # cv2.subtract saturates at 0 instead of wrapping, so each call keeps
        # only the pixels where that channel actually leads.
        maize = cv2.subtract(red, blue)
        michigan_blue = cv2.subtract(blue, red)
        threshold = self.config.chroma_threshold
        _, maize_mask = cv2.threshold(maize, threshold, 255, cv2.THRESH_BINARY)
        _, blue_mask = cv2.threshold(michigan_blue, threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_or(maize_mask, blue_mask)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        return mask
