"""The colour+shape detector must separate a Block M from other yellow things."""
import cv2
import numpy as np
import pytest

from cook_vision.config import DetectorConfig
from cook_vision.detectors import ChromaShapeDetector, ColorShapeDetector, build_detector
from cook_vision.detectors.template import (
    TEMPLATE_ASPECT, TEMPLATE_EXTENT, TEMPLATE_SOLIDITY, render,
)

MAIZE = (5, 203, 255)   # BGR for #FFCB05
BLUE = (76, 39, 0)      # BGR for #00274C
# Low-saturation field colour: matches neither detection range regardless of
# hue, so it stands in for "not a target colour" now that both maize and blue
# are detected. (A solid-blue field, the old choice, would itself be a match.)
NEUTRAL = (40, 40, 40)
# Real camera measurement of a printed maize M in dim, warm-white-balanced
# light (see docs/status.md): brightness 113/255, hue pushed below HSV's
# maize band entirely. R-B is still 40, which is what the chroma backend
# exists to exploit.
MAIZE_DIM = (73, 88, 113)
# Michigan blue under the same dimming ratio (113/255 of the ideal swatch).
# No hardware measurement exists for this one; it is scaled from BLUE.
BLUE_DIM = (34, 17, 0)


@pytest.fixture
def detector():
    return ColorShapeDetector(DetectorConfig())


def scene(shape, size=160, pos=(200, 120), frame=(640, 480), color=MAIZE):
    image = np.zeros((frame[1], frame[0], 3), np.uint8)
    image[:] = NEUTRAL
    x, y = pos
    if shape == "m":
        image[y:y + size, x:x + size] = render(size, color, NEUTRAL)
    elif shape == "circle":
        cv2.circle(image, (x + size // 2, y + size // 2), size // 2, color, -1)
    elif shape == "square":
        cv2.rectangle(image, pos, (x + size, y + size), color, -1)
    elif shape == "empty":
        pass
    return image


def test_template_geometry_matches_the_block_m():
    assert 0.60 < TEMPLATE_EXTENT < 0.72
    assert 0.60 < TEMPLATE_SOLIDITY < 0.80
    assert TEMPLATE_ASPECT == pytest.approx(1.0, abs=0.05)


def test_detects_a_block_m(detector):
    detections = detector.detect(scene("m"))
    assert len(detections) == 1
    assert detections[0].label == "BLOCK-M"
    assert detections[0].confidence > 0.8
    left, top, width, height = detections[0].box
    assert (left, top) == pytest.approx((200, 120), abs=6)
    assert width == pytest.approx(160, abs=8)


def test_detects_a_blue_block_m(detector):
    """Some real Block Ms are Michigan blue, not maize."""
    detections = detector.detect(scene("m", color=BLUE))
    assert len(detections) == 1
    assert detections[0].label == "BLOCK-M"
    assert detections[0].confidence > 0.8


@pytest.mark.parametrize("shape", ["circle", "square", "empty"])
def test_rejects_non_m_shapes(detector, shape):
    assert detector.detect(scene(shape)) == []


def test_shape_score_ranks_m_far_above_decoys(detector):
    def best(shape):
        contours, _ = cv2.findContours(
            detector.mask(scene(shape)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        return max((detector.score(c) for c in contours), default=0.0)

    assert best("m") - max(best("circle"), best("square")) > 0.4


def test_ignores_colours_that_are_neither_maize_nor_blue(detector):
    image = np.zeros((480, 640, 3), np.uint8)
    image[:] = NEUTRAL
    image[120:280, 200:360] = render(160, (60, 60, 220), NEUTRAL)  # a red block M
    assert detector.detect(image) == []


def test_detection_boxes_stay_inside_the_frame(detector):
    # An M running off the left edge must not produce a negative origin.
    image = np.zeros((480, 640, 3), np.uint8)
    image[:] = NEUTRAL
    patch = render(160, MAIZE, NEUTRAL)
    image[100:260, 0:120] = patch[:, 40:]
    for detection in detector.detect(image):
        left, top, width, height = detection.box
        assert left >= 0 and top >= 0
        assert left + width <= 640 and top + height <= 480


@pytest.fixture
def chroma_detector():
    return ChromaShapeDetector(DetectorConfig())


def test_chroma_detects_a_block_m(chroma_detector):
    detections = chroma_detector.detect(scene("m"))
    assert len(detections) == 1
    assert detections[0].confidence > 0.8


def test_chroma_detects_a_blue_block_m(chroma_detector):
    detections = chroma_detector.detect(scene("m", color=BLUE))
    assert len(detections) == 1
    assert detections[0].confidence > 0.8


@pytest.mark.parametrize("shape", ["circle", "square", "empty"])
def test_chroma_rejects_non_m_shapes(chroma_detector, shape):
    assert chroma_detector.detect(scene(shape)) == []


def test_chroma_ignores_colours_off_the_r_minus_b_axis(chroma_detector):
    image = np.zeros((480, 640, 3), np.uint8)
    image[:] = NEUTRAL
    image[120:280, 200:360] = render(160, (0, 180, 0), NEUTRAL)  # a green block M
    assert chroma_detector.detect(image) == []


def test_chroma_cannot_tell_red_from_maize(chroma_detector):
    """Documented trade-off, not a bug: R-B alone can't see hue, only R vs B.

    HSV rejects this decoy on hue; chroma has no hue to check, so shape
    scoring is the only gate left. See the "Known limitation" note in
    chroma.py.
    """
    detections = chroma_detector.detect(scene("m", color=(60, 60, 220)))
    assert len(detections) == 1


def test_chroma_survives_dim_warm_light_where_hsv_fails(detector, chroma_detector):
    """The whole reason this backend exists: see MAIZE_DIM above."""
    dim_scene = scene("m", color=MAIZE_DIM)
    assert detector.detect(dim_scene) == []
    detections = chroma_detector.detect(dim_scene)
    assert len(detections) == 1
    assert detections[0].confidence > 0.8


def test_chroma_survives_dim_warm_blue_where_hsv_fails(detector, chroma_detector):
    dim_scene = scene("m", color=BLUE_DIM)
    assert detector.detect(dim_scene) == []
    detections = chroma_detector.detect(dim_scene)
    assert len(detections) == 1
    assert detections[0].confidence > 0.8


def test_build_detector_builds_the_chroma_backend():
    built = build_detector(DetectorConfig(backend="chroma", process_width=0))
    assert isinstance(built, ChromaShapeDetector)


def test_build_detector_rejects_an_unknown_backend():
    config = DetectorConfig(backend="magic")
    with pytest.raises(ValueError, match="Unknown detector backend"):
        build_detector(config)


# --- downscaled detection -------------------------------------------------

def test_downscaled_detector_returns_full_frame_coordinates():
    from cook_vision.detectors import DownscaledDetector

    config = DetectorConfig()
    wrapped = DownscaledDetector(ColorShapeDetector(config), 640)
    image = np.zeros((720, 1280, 3), np.uint8)
    image[:] = NEUTRAL
    image[200:440, 400:640] = render(240, MAIZE, NEUTRAL)

    detections = wrapped.detect(image)
    assert len(detections) == 1
    left, top, width, height = detections[0].box
    # Boxes must be reported against the full frame, not the shrunken copy.
    assert (left, top) == pytest.approx((400, 200), abs=12)
    assert width == pytest.approx(240, abs=16)
    assert detections[0].confidence > 0.8


def test_downscaling_is_skipped_when_the_frame_is_already_small():
    from cook_vision.detectors import DownscaledDetector

    wrapped = DownscaledDetector(ColorShapeDetector(DetectorConfig()), 640)
    small = scene("m", frame=(640, 480))
    assert wrapped._scale_for(small) is None
    assert len(wrapped.detect(small)) == 1


def test_downscaled_detector_still_rejects_decoys():
    from cook_vision.detectors import DownscaledDetector

    wrapped = DownscaledDetector(ColorShapeDetector(DetectorConfig()), 640)
    image = np.zeros((720, 1280, 3), np.uint8)
    image[:] = NEUTRAL
    cv2.circle(image, (500, 300), 110, MAIZE, -1)
    assert wrapped.detect(image) == []


def test_mask_view_survives_the_wrapper():
    from cook_vision.detectors import DownscaledDetector

    wrapped = DownscaledDetector(ColorShapeDetector(DetectorConfig()), 640)
    image = np.zeros((720, 1280, 3), np.uint8)
    image[:] = NEUTRAL
    image[200:440, 400:640] = render(240, MAIZE, NEUTRAL)
    mask = wrapped.mask(image)
    # The debug view must come back at full frame size for the HUD to show it.
    assert mask.shape == (720, 1280)


def test_build_detector_wraps_the_colour_backend():
    from cook_vision.detectors import DownscaledDetector

    built = build_detector(DetectorConfig(process_width=640))
    assert isinstance(built, DownscaledDetector)
    assert built.name == "color"
    assert not isinstance(build_detector(DetectorConfig(process_width=0)), DownscaledDetector)
