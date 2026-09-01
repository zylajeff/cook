"""End-to-end: the synthetic camera drives a real detect/track/fire cycle."""
import pytest

from cook_vision.app import SeekerApp, apply_args, build_parser
from cook_vision.config import Config
from cook_vision.hardware import LOW, MockGpioBackend


def headless_config():
    config = Config()
    config.camera.source = "synthetic"
    config.camera.width, config.camera.height = 640, 480
    config.gpio.backend = "mock"
    config.gpio.debounce_seconds = 0.0
    config.display.headless = True
    config.firing.startup_lockout_seconds = 0.0
    return config


@pytest.fixture
def app():
    instance = SeekerApp(headless_config())
    yield instance
    instance.shutdown()


def test_pipeline_detects_the_synthetic_block_m(app):
    ok, frame = app.camera.read()
    assert ok
    detections = app.detector.detect(frame)
    assert detections and detections[0].label == "BLOCK-M"


def test_the_decoy_disc_is_never_detected(app):
    # The synthetic feed draws a yellow circle in the lower left as a decoy.
    for _ in range(30):
        ok, frame = app.camera.read()
        for detection in app.detector.detect(frame):
            left, top, _, height = detection.box
            assert not (left < 240 and top + height > 300), "locked onto the decoy disc"


def test_a_disarmed_run_never_fires(app):
    for _ in range(90):
        ok, frame = app.camera.read()
        app.arm_switch.update()
        app.tracker.update(app.detector.detect(frame), frame.shape)
        app.controller.update(app.tracker, frame.shape)
    assert app.controller.shots == 0


def test_an_armed_run_eventually_fires(app):
    app.gpio.set_input_level(app.config.gpio.arm_switch_pin, LOW)
    for _ in range(200):
        ok, frame = app.camera.read()
        app.arm_switch.update()
        app.tracker.update(app.detector.detect(frame), frame.shape)
        app.controller.update(app.tracker, frame.shape)
        if app.controller.shots:
            break
    assert app.controller.shots >= 1


def test_shutdown_leaves_the_relay_de_energised(app):
    app.relay.pulse(0.4)
    app.shutdown()
    assert not app.relay.is_energised


def test_hud_renders_without_error():
    config = headless_config()
    config.display.headless = False
    instance = SeekerApp(config)
    try:
        ok, frame = instance.camera.read()
        instance.tracker.update(instance.detector.detect(frame), frame.shape)
        decision = instance.controller.update(instance.tracker, frame.shape)
        instance.hud.flash()
        rendered = instance.hud.render(
            frame, instance.tracker, decision, instance.controller,
            {"fps": 30.0, "backend": "color", "source": "synthetic", "shots": 1},
        )
        assert rendered.shape == frame.shape
    finally:
        instance.shutdown()


def test_cli_flags_reach_the_config():
    args = build_parser().parse_args(
        ["--source", "v4l2", "--confidence", "0.7", "--no-auto-fire", "--headless"]
    )
    config = apply_args(Config(), args)
    assert config.camera.source == "v4l2"
    assert config.detector.confidence == 0.7
    assert config.firing.auto_fire is False
    assert config.display.headless is True


def test_passing_a_model_selects_the_onnx_backend():
    args = build_parser().parse_args(["--model", "models/x.onnx"])
    config = apply_args(Config(), args)
    assert config.detector.backend == "onnx"
