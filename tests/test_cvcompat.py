"""The OpenCV 3 / 4 shim. JetPack 4.2 ships OpenCV 3.3.1; dev boxes ship 4.x."""
import cv2
import numpy as np

from cook_vision.cvcompat import MATCH_I1, describe, find_contours


def _disc(size=120, radius=40):
    mask = np.zeros((size, size), np.uint8)
    cv2.circle(mask, (size // 2, size // 2), radius, 255, -1)
    return mask


def test_find_contours_returns_a_plain_contour_list():
    contours = find_contours(_disc())
    assert isinstance(contours, (list, tuple))
    assert len(contours) == 1
    # Must be an actual contour array, not the image OpenCV 3 returns first.
    assert contours[0].ndim == 3 and contours[0].shape[-1] == 2


def test_find_contours_survives_both_return_signatures(monkeypatch):
    mask = _disc()
    real = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = real[-2]

    # OpenCV 3.x: (image, contours, hierarchy)
    monkeypatch.setattr(cv2, "findContours", lambda *a, **k: (mask, contours, None))
    assert find_contours(mask) is contours

    # OpenCV 4.x: (contours, hierarchy)
    monkeypatch.setattr(cv2, "findContours", lambda *a, **k: (contours, None))
    assert find_contours(mask) is contours


def test_match_i1_is_the_documented_constant():
    assert MATCH_I1 == 1


def test_describe_reports_the_build():
    text = describe()
    assert "OpenCV" in text and "GStreamer" in text
