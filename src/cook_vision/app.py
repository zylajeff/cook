"""Application entry point: capture -> detect -> track -> interlock -> display."""
import argparse
import logging
import signal
import sys
import time
from collections import deque

import cv2

from .camera import Camera
from .config import Config
from .detectors import build_detector
from .firing import FireController
from .hardware import ArmSwitch, MockGpioBackend, SolenoidRelay, build_backend
from .hud import SeekerHud
from .sound import build_soundboard
from .tracker import TargetTracker

LOGGER = logging.getLogger("cook")

HELP = """keys:  q/ESC quit   s software safety   f manual fire
       a toggle mock arm switch   m mask view   w windowed/fullscreen"""


def fit_to_display(frame, display):
    """Resize once, up front, so everything downstream shares one coordinate space.

    Drawing the HUD at the panel's native size is cheaper than drawing it large
    and letting the window scale it, and it keeps the text crisp instead of
    resampled. Detection, tracking, and the bore check then all agree on what
    "frame width" means.
    """
    if not display.width or not display.height:
        return frame
    height, width = frame.shape[:2]
    if (width, height) == (display.width, display.height):
        return frame
    # On CSI this is a no-op: the ISP already delivered the display size. It
    # only runs for V4L2, file, and synthetic sources. INTER_LINEAR throughout,
    # for the reason documented in DownscaledDetector._shrink.
    return cv2.resize(frame, (display.width, display.height),
                      interpolation=cv2.INTER_LINEAR)


class SeekerApp:
    def __init__(self, config: Config):
        self.config = config
        self.camera = Camera(config.camera)
        self.detector = build_detector(config.detector)
        self.tracker = TargetTracker(config.tracker)

        self.gpio = build_backend(config.gpio.backend)
        self.arm_switch = ArmSwitch(self.gpio, config.gpio)
        self.relay = SolenoidRelay(self.gpio, config.gpio, config.firing.max_pulse_seconds)
        self.controller = FireController(self.relay, self.arm_switch, config.firing)

        self.sound = build_soundboard(config.sound)
        self.hud = SeekerHud(config.display, config.firing)
        self._frame_times = deque(maxlen=30)
        self._show_mask = False
        self._running = True
        self._window_open = False

    # -- lifecycle -----------------------------------------------------------

    def _open_window(self):
        if self.config.display.headless or self._window_open:
            return
        name = self.config.display.window_name
        cv2.namedWindow(name, cv2.WINDOW_NORMAL)
        if self.config.display.fullscreen:
            cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        self._window_open = True

    def stop(self, *_):
        self._running = False

    def shutdown(self):
        """Make the rig safe, then release everything. Safe to call twice."""
        self.controller.safe()
        self.camera.release()
        self.detector.close()
        try:
            self.gpio.cleanup()
        except Exception as error:
            LOGGER.warning("GPIO cleanup failed: %s", error)
        if self._window_open:
            cv2.destroyAllWindows()
        LOGGER.info("Shutdown complete. %d shot(s) fired.", self.controller.shots)

    # -- input ---------------------------------------------------------------

    def _handle_key(self, key):
        if key in (ord("q"), 27):
            self.stop()
        elif key == ord("s"):
            self.controller.toggle_software_safe()
        elif key == ord("f"):
            self.controller.request_fire()
        elif key == ord("m"):
            self._show_mask = not self._show_mask
        elif key == ord("w"):
            self.config.display.fullscreen = not self.config.display.fullscreen
            cv2.setWindowProperty(
                self.config.display.window_name,
                cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN if self.config.display.fullscreen else cv2.WINDOW_NORMAL,
            )
        elif key == ord("a") and isinstance(self.gpio, MockGpioBackend):
            # Development only: simulate the operator flipping the toggle switch.
            pin = self.config.gpio.arm_switch_pin
            level = 0 if self.gpio.read(pin) else 1
            self.gpio.set_input_level(pin, level)

    def _fps(self):
        if len(self._frame_times) < 2:
            return 0.0
        span = self._frame_times[-1] - self._frame_times[0]
        return (len(self._frame_times) - 1) / span if span > 0 else 0.0

    # -- main loop -----------------------------------------------------------

    def run(self) -> int:
        LOGGER.info("Camera: %s", self.camera.description)
        LOGGER.info("Detector: %s | GPIO: %s", self.detector.name, self.gpio.name)
        LOGGER.info("Firing lockout for %.1fs", self.config.firing.startup_lockout_seconds)
        print(HELP)

        self._open_window()
        shots_before = self.controller.shots

        while self._running:
            ok, frame = self.camera.read()
            if not ok or frame is None:
                LOGGER.error("Camera read failed; stopping.")
                return 1

            frame = fit_to_display(frame, self.config.display)
            self._frame_times.append(time.monotonic())
            self.arm_switch.update()

            detections = self.detector.detect(frame)
            self.tracker.update(detections, frame.shape)
            decision = self.controller.update(self.tracker, frame.shape)

            if self.controller.shots != shots_before:
                self.hud.flash()
                self.sound.play_fire()
                shots_before = self.controller.shots

            if self.config.display.headless:
                continue

            if self._show_mask and hasattr(self.detector, "mask"):
                frame = cv2.cvtColor(self.detector.mask(frame), cv2.COLOR_GRAY2BGR)

            telemetry = {
                "fps": self._fps(),
                "backend": self.detector.name,
                "source": self.camera.source if hasattr(self.camera, "source") else "synthetic",
                "shots": self.controller.shots,
            }
            frame = self.hud.render(frame, self.tracker, decision, self.controller, telemetry)
            cv2.imshow(self.config.display.window_name, frame)
            self._handle_key(cv2.waitKey(1) & 0xFF)

        return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cook-vision",
        description="Block-M seeker and pneumatic dart launcher control.",
    )
    parser.add_argument("--source", choices=["auto", "csi", "v4l2", "file", "synthetic"])
    parser.add_argument("--device", help="camera index, or a path for --source file")
    parser.add_argument("--detector", choices=["color", "chroma", "onnx"])
    parser.add_argument("--model", help="path to the ONNX model")
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--no-auto-fire", action="store_true",
                        help="require the f key even when every interlock passes")
    parser.add_argument("--windowed", action="store_true")
    parser.add_argument("--headless", action="store_true",
                        help="run the pipeline with no display; for soak testing")
    parser.add_argument("--gpio", choices=["auto", "jetson", "mock"])
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser


def apply_args(config: Config, args) -> Config:
    if args.source:
        config.camera.source = args.source
    if args.device:
        config.camera.device = args.device
    if args.width:
        config.camera.width = args.width
    if args.height:
        config.camera.height = args.height
    if args.detector:
        config.detector.backend = args.detector
    if args.model:
        config.detector.model_path = args.model
        config.detector.backend = "onnx"
    if args.confidence is not None:
        config.detector.confidence = args.confidence
    if args.no_auto_fire:
        config.firing.auto_fire = False
    if args.windowed:
        config.display.fullscreen = False
    if args.headless:
        config.display.headless = True
    if args.gpio:
        config.gpio.backend = args.gpio
    return config


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = apply_args(Config.from_env(), args)
    LOGGER.debug("Configuration:\n%s", config.describe())

    app = SeekerApp(config)
    signal.signal(signal.SIGINT, app.stop)
    signal.signal(signal.SIGTERM, app.stop)
    try:
        return app.run()
    finally:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())
