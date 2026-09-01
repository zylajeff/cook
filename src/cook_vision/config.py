"""Central configuration.

Every value can be overridden with a ``COOK_``-prefixed environment variable so
the rig can be retuned on the Jetson without editing source.
"""
import os
from dataclasses import dataclass, field, fields
from typing import Any, Tuple


def _env(name, cast, default):
    raw = os.getenv("COOK_" + name.upper())
    if raw is None:
        return default
    if cast is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return cast(raw)


def _env_tuple(name, default):
    """Parse a comma-separated triple, e.g. COOK_DETECTOR_MAIZE_LOWER='18,120,120'."""
    raw = os.getenv("COOK_" + name.upper())
    if raw is None:
        return default
    try:
        values = tuple(int(part.strip()) for part in raw.split(","))
    except ValueError:
        return default
    return values if len(values) == len(default) else default


@dataclass
class CameraConfig:
    #: ``csi`` (Pi camera via nvarguscamerasrc), ``v4l2``, ``file`` or ``synthetic``.
    source: str = "auto"
    device: str = "0"
    #: Sensor mode to capture in. The IMX219 offers 3264x2464, 3264x1848,
    #: 1920x1080 and 1280x720; pick one it actually supports.
    capture_width: int = 1280
    capture_height: int = 720
    #: What the pipeline hands to OpenCV. On CSI this scaling happens on the ISP
    #: for free, so matching it to the display costs nothing and saves a resize.
    width: int = 1024
    height: int = 600
    fps: int = 30
    #: CSI sensor rotation in 90-degree steps, as accepted by nvvidconv.
    flip_method: int = 0


@dataclass
class DetectorConfig:
    #: ``color`` (HSV, no training required), ``chroma`` (R-B difference, also
    #: no training, survives a dim/warm-white-balanced image where HSV can't),
    #: or ``onnx`` (trained YOLOv8 export).
    backend: str = "color"
    confidence: float = 0.45
    #: --- onnx backend ---
    model_path: str = "models/block-m.onnx"
    input_size: int = 640
    nms_threshold: float = 0.45
    #: --- color backend ---
    #: Michigan maize in OpenCV HSV (hue 0-179). Maize is a saturated warm yellow.
    #: This is the ideal-swatch guess, not a measured value -- a tighter range
    #: measured from 118 labelled training crops, (18,172,160)-(32,255,255),
    #: was tried and rolled back: it missed a real target this looser range
    #: caught. Revisit with real calibrate.py numbers before tightening again.
    maize_lower: Tuple[int, int, int] = (18, 120, 120)
    maize_upper: Tuple[int, int, int] = (34, 255, 255)
    #: Michigan blue, the other half of the block-M colourway. Measured from
    #: labelled training crops (__train/block_m), not the ideal swatch.
    blue_lower: Tuple[int, int, int] = (100, 78, 50)
    blue_upper: Tuple[int, int, int] = (124, 255, 255)
    min_area_px: int = 900
    #: Blur before the HSV threshold. The morphological open already removes
    #: speckle, so this is off by default; turn it on for a very noisy sensor.
    blur: bool = False
    #: Morphology kernel size. 3 is enough once the frame is downscaled.
    morph_size: int = 3
    #: Upper bound on cv2.matchShapes distance to the block-M template.
    max_shape_distance: float = 0.65
    #: --- chroma backend ---
    #: Minimum |R-B| (0-255) to call a pixel maize or Michigan blue. Measured
    #: dim maize (B 73 G 88 R 113) has R-B=40; this sits with margin below it.
    chroma_threshold: int = 30
    #: Run detection on a frame downscaled to this width, then rescale the boxes
    #: back. Detection cost falls with the square of the ratio, and a Block M big
    #: enough to shoot at is still tens of pixels across at 640. 0 disables it.
    process_width: int = 640


@dataclass
class TrackerConfig:
    #: Centre distance, as a fraction of frame diagonal, to treat as the same target.
    match_distance: float = 0.12
    #: Exponential smoothing applied to box corners; higher is snappier.
    smoothing: float = 0.45
    #: Consecutive frames a target must persist before the seeker declares LOCK.
    lock_frames: int = 8
    #: Frames a track survives without a matching detection before it is dropped.
    max_missed_frames: int = 6


@dataclass
class FiringConfig:
    #: Seconds the solenoid coil is energised per shot. Keep this short: the coil
    #: is not rated for continuous duty and will overheat if held on.
    pulse_seconds: float = 0.12
    #: Hard ceiling enforced by the watchdog regardless of pulse_seconds.
    max_pulse_seconds: float = 0.50
    #: Minimum seconds between shots.
    cooldown_seconds: float = 1.50
    #: Seconds after startup during which firing is refused, so a boot-time GPIO
    #: glitch cannot launch a dart before the operator is ready.
    startup_lockout_seconds: float = 3.0
    #: Confidence a locked target must exceed to be shot at.
    fire_confidence: float = 0.60
    #: Require the target centre to be within this fraction of the frame width of
    #: the reticle. The barrel is fixed in round one, so only centred targets are
    #: actually in front of it.
    bore_tolerance: float = 0.10
    #: Fire automatically on lock, or wait for the operator to press ``f``.
    auto_fire: bool = True


@dataclass
class GpioConfig:
    #: Jetson Nano 40-pin header numbers (GPIO.BOARD numbering).
    relay_pin: int = 18
    arm_switch_pin: int = 16
    #: Cheap opto-isolated relay boards energise on a LOW input.
    relay_active_low: bool = True
    #: Switch wired to ground and held high by the internal pull-up.
    arm_switch_active_low: bool = True
    #: Seconds the arm switch must hold a level before the change is accepted.
    debounce_seconds: float = 0.05
    #: ``auto`` uses Jetson.GPIO when importable and falls back to a mock.
    backend: str = "auto"


@dataclass
class DisplayConfig:
    fullscreen: bool = True
    window_name: str = "COOK // SEEKER"
    show_fps: bool = True
    #: Draw nothing and open no window; for headless soak testing.
    headless: bool = False
    #: Resize the frame to the panel before drawing the HUD. Drawing at the
    #: panel's native size costs less than drawing large and letting the window
    #: scale, and keeps the text crisp. 0 keeps the camera's resolution.
    width: int = 1024
    height: int = 600
    #: Scanlines and vignette. Cheap now, but still the first thing to drop if
    #: the frame budget gets tight.
    effects: bool = True


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    firing: FiringConfig = field(default_factory=FiringConfig)
    gpio: GpioConfig = field(default_factory=GpioConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """Build a config, letting ``COOK_<SECTION>_<FIELD>`` override any scalar."""
        config = cls()
        for section in fields(cls):
            group = getattr(config, section.name)
            for item in fields(group):
                current = getattr(group, item.name)
                name = "{0}_{1}".format(section.name, item.name)
                # Test the value, not the annotation: Field.type is a string under
                # `from __future__ import annotations` and a typing object without it.
                if isinstance(current, tuple):
                    setattr(group, item.name, _env_tuple(name, current))
                    continue
                cast = type(current)
                setattr(group, item.name, _env(name, cast, current))
        return config

    def describe(self) -> str:
        lines = []
        for section in fields(self):
            group = getattr(self, section.name)
            values = ", ".join(
                "{0}={1}".format(f.name, getattr(group, f.name)) for f in fields(group)
            )
            lines.append("  {0}: {1}".format(section.name, values))
        return "\n".join(lines)
