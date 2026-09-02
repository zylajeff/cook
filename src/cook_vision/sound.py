"""Fire sound effect: one clip played per shot.

Playback runs on a daemon thread via a command-line player, never on the main
thread -- CLAUDE.md's performance notes are about a rig that is already
camera-limited at ~19ms of a 33ms frame budget, and shelling out to a player
process is not something to do inside that budget. A missing clip or a PATH
with no known player disables sound; it never blocks firing.
"""
import logging
import os
import shutil
import subprocess
import threading

LOGGER = logging.getLogger(__name__)

#: Tried in order; the first found on PATH wins. mpg123 decodes the shipped
#: mp3 clip directly. aplay is last because it needs wav/pcm, not mp3.
_PLAYERS = ("mpg123", "ffplay", "cvlc", "aplay")

_PLAYER_ARGS = {
    "mpg123": ("-q",),
    "ffplay": ("-nodisp", "-autoexit", "-loglevel", "quiet"),
    "cvlc": ("--play-and-exit", "-q"),
    "aplay": ("-q",),
}

#: Flag each player uses to pick an ALSA device by name (e.g. ``plughw:0,3``).
#: ffplay/cvlc take a device through different, more involved mechanisms not
#: worth wiring up for a fire-and-forget sound effect.
_DEVICE_FLAG = {
    "mpg123": "-a",
    "aplay": "-D",
}


class MockSoundBackend:
    """Records play requests instead of touching real audio; for tests."""

    name = "mock"

    def __init__(self):
        self.played = []

    def play(self, path):
        self.played.append(path)


class SystemSoundBackend:
    """Runs a command-line player in a daemon thread, non-blocking."""

    def __init__(self, player, device=""):
        self.name = player
        command = (player,) + _PLAYER_ARGS.get(player, ())
        device_flag = _DEVICE_FLAG.get(player)
        if device and device_flag:
            command += (device_flag, device)
        self._command = command

    def play(self, path):
        thread = threading.Thread(target=self._run, args=(path,), daemon=True)
        thread.start()

    def _run(self, path):
        try:
            result = subprocess.run(
                self._command + (path,),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            LOGGER.warning("Fire sound playback failed: %s", error)
            return
        if result.returncode != 0:
            LOGGER.debug("%s exited %d playing %s", self.name, result.returncode, path)


def build_backend(name="auto", device=""):
    """Return a sound backend; ``auto`` picks the first player found on PATH."""
    candidates = _PLAYERS if name == "auto" else (name,)
    for player in candidates:
        if shutil.which(player):
            return SystemSoundBackend(player, device)
    LOGGER.warning(
        "No usable sound player on PATH (tried %s); sound disabled.",
        ", ".join(candidates),
    )
    return MockSoundBackend()


class SoundBoard:
    """Plays the fire clip on shot. A missing file or backend is silent, not fatal."""

    def __init__(self, backend, config):
        self._backend = backend
        self._fire_clip = config.fire_clip
        self._enabled = config.enabled
        if self._enabled and not os.path.isfile(self._fire_clip):
            LOGGER.warning("Fire clip not found at %s; sound disabled.", self._fire_clip)
            self._enabled = False

    def play_fire(self):
        if self._enabled:
            self._backend.play(self._fire_clip)


def build_soundboard(config):
    if config.enabled:
        backend = build_backend(config.player, config.output_device)
    else:
        backend = MockSoundBackend()
    return SoundBoard(backend, config)
