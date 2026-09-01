"""Block-M detection backends."""
import cv2

from .base import Detection, Detector, clip_box
from .chroma import ChromaShapeDetector
from .colorshape import ColorShapeDetector
from .onnx import OnnxYoloDetector

__all__ = [
    "Detection",
    "Detector",
    "ColorShapeDetector",
    "ChromaShapeDetector",
    "OnnxYoloDetector",
    "DownscaledDetector",
    "build_detector",
    "clip_box",
]


class DownscaledDetector(Detector):
    """Run an inner detector on a smaller copy of the frame.

    Detection cost falls with the square of the scale, which is the difference
    between a usable frame rate and an unusable one on a Jetson Nano. Boxes come
    back in full-frame coordinates, so nothing downstream knows this happened.

    Note that ``min_area_px`` is therefore measured at the processing width, not
    the camera width -- which makes it stable when the camera resolution changes.
    """

    def __init__(self, inner, width):
        self.inner = inner
        self.width = width

    @property
    def name(self):
        return self.inner.name

    def _scale_for(self, frame):
        height, width = frame.shape[:2]
        if self.width <= 0 or width <= self.width:
            return None
        return self.width / float(width)

    def _shrink(self, frame, scale):
        height, width = frame.shape[:2]
        size = (int(round(width * scale)), int(round(height * scale)))
        # INTER_LINEAR, not INTER_AREA. AREA is the textbook downscale filter,
        # but measured on this workload it costs 4.6x more for an identical
        # shape score -- the target is a large flat colour region, not detail.
        return cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)

    def detect(self, frame):
        scale = self._scale_for(frame)
        if scale is None:
            return self.inner.detect(frame)
        height, width = frame.shape[:2]
        inverse = 1.0 / scale
        scaled = []
        for found in self.inner.detect(self._shrink(frame, scale)):
            box = [value * inverse for value in found.box]
            scaled.append(
                Detection(found.label, found.confidence, clip_box(box, width, height))
            )
        return scaled

    def mask(self, frame):
        """Pass the diagnostic mask view through, at the processing size."""
        inner_mask = getattr(self.inner, "mask", None)
        if inner_mask is None:
            raise AttributeError("inner detector has no mask view")
        scale = self._scale_for(frame)
        source = frame if scale is None else self._shrink(frame, scale)
        small = inner_mask(source)
        if scale is None:
            return small
        return cv2.resize(small, (frame.shape[1], frame.shape[0]),
                          interpolation=cv2.INTER_NEAREST)

    def close(self):
        self.inner.close()


def build_detector(config) -> Detector:
    """Instantiate the backend named by ``config.backend``."""
    backends = {
        "color": ColorShapeDetector,
        "chroma": ChromaShapeDetector,
        "onnx": OnnxYoloDetector,
    }
    try:
        detector = backends[config.backend](config)
    except KeyError:
        raise ValueError(
            "Unknown detector backend {0!r}; expected one of {1}".format(
                config.backend, sorted(backends)
            )
        )
    width = getattr(config, "process_width", 0)
    # The ONNX backend already resizes to its own input size; wrapping it would
    # just add a redundant resize.
    if width and config.backend != "onnx":
        return DownscaledDetector(detector, width)
    return detector
