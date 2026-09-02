import os

from cook_vision.config import SoundConfig
from cook_vision.sound import MockSoundBackend, SoundBoard, build_soundboard

REAL_CLIP = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "assets", "sounds", "trouble_with_the_snap.mp3",
)


def test_plays_the_clip_on_fire():
    backend = MockSoundBackend()
    board = SoundBoard(backend, SoundConfig(enabled=True, fire_clip=REAL_CLIP))
    board.play_fire()
    assert backend.played == [REAL_CLIP]


def test_disabled_never_touches_the_backend():
    backend = MockSoundBackend()
    board = SoundBoard(backend, SoundConfig(enabled=False, fire_clip=REAL_CLIP))
    board.play_fire()
    assert backend.played == []


def test_missing_clip_disables_sound_instead_of_raising():
    backend = MockSoundBackend()
    board = SoundBoard(backend, SoundConfig(enabled=True, fire_clip="no/such/file.mp3"))
    board.play_fire()
    assert backend.played == []


def test_build_soundboard_disabled_never_touches_real_audio():
    board = build_soundboard(SoundConfig(enabled=False))
    board.play_fire()  # would raise/hang if this reached a real player
