"""Tracks must persist across jitter and only lock after a dwell period."""
import pytest

from cook_vision.config import TrackerConfig
from cook_vision.detectors import Detection
from cook_vision.tracker import LOCKED, SEARCHING, TRACKING, TargetTracker

SHAPE = (480, 640, 3)


def detection(x=300, y=200, size=80, confidence=0.9):
    return Detection("BLOCK-M", confidence, (x, y, size, size))


@pytest.fixture
def tracker():
    return TargetTracker(TrackerConfig(lock_frames=5, max_missed_frames=3))


def test_starts_out_searching(tracker):
    tracker.update([], SHAPE)
    assert tracker.state == SEARCHING
    assert tracker.primary is None


def test_locks_only_after_the_dwell_period(tracker):
    for frame in range(1, 5):
        tracker.update([detection()], SHAPE)
        assert tracker.state == TRACKING, "locked after only {0} frames".format(frame)
    tracker.update([detection()], SHAPE)
    assert tracker.state == LOCKED


def test_a_moving_target_keeps_one_track_id(tracker):
    for step in range(8):
        tracker.update([detection(x=300 + step * 6)], SHAPE)
    assert len(tracker.tracks) == 1
    assert tracker.primary.hits == 8


def test_a_teleporting_target_starts_a_new_track(tracker):
    tracker.update([detection(x=50, y=50)], SHAPE)
    tracker.update([detection(x=600, y=440)], SHAPE)
    assert len(tracker.tracks) == 2


def test_a_track_survives_brief_dropouts_then_expires(tracker):
    for _ in range(6):
        tracker.update([detection()], SHAPE)
    for _ in range(3):
        tracker.update([], SHAPE)
    assert len(tracker.tracks) == 1
    tracker.update([], SHAPE)
    assert tracker.tracks == []
    assert tracker.state == SEARCHING


def test_a_dropout_breaks_the_lock(tracker):
    for _ in range(6):
        tracker.update([detection()], SHAPE)
    assert tracker.state == LOCKED
    tracker.update([], SHAPE)
    assert tracker.state != LOCKED


def test_lock_progress_ramps_to_one(tracker):
    assert tracker.lock_progress() == 0.0
    tracker.update([detection()], SHAPE)
    assert 0.0 < tracker.lock_progress() < 1.0
    for _ in range(6):
        tracker.update([detection()], SHAPE)
    assert tracker.lock_progress() == 1.0


def test_the_primary_track_is_the_most_confident_one(tracker):
    for _ in range(6):
        tracker.update(
            [detection(x=100, confidence=0.5), detection(x=500, confidence=0.95)], SHAPE
        )
    assert tracker.primary.center[0] == pytest.approx(540, abs=20)


def test_smoothing_damps_positional_jitter(tracker):
    tracker.update([detection(x=300)], SHAPE)
    tracker.update([detection(x=360)], SHAPE)  # inside the match radius
    # With smoothing < 1 the track lags the raw jump rather than snapping to it.
    assert 300 < tracker.primary.box[0] < 360
