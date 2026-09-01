"""Environment overrides must reach the nested config sections."""
import pytest

from cook_vision.config import Config, DetectorConfig

DEFAULT_MAIZE_LOWER = DetectorConfig().maize_lower
DEFAULT_MAIZE_UPPER = DetectorConfig().maize_upper


def test_defaults_are_safe():
    config = Config()
    assert config.firing.startup_lockout_seconds > 0
    assert config.firing.pulse_seconds <= config.firing.max_pulse_seconds
    assert config.gpio.relay_pin != config.gpio.arm_switch_pin


def test_env_overrides_scalars(monkeypatch):
    monkeypatch.setenv("COOK_FIRING_PULSE_SECONDS", "0.25")
    monkeypatch.setenv("COOK_GPIO_RELAY_PIN", "22")
    monkeypatch.setenv("COOK_DETECTOR_BACKEND", "onnx")
    config = Config.from_env()
    assert config.firing.pulse_seconds == 0.25
    assert config.gpio.relay_pin == 22
    assert config.detector.backend == "onnx"


@pytest.mark.parametrize("raw,expected", [("1", True), ("true", True), ("0", False), ("no", False)])
def test_env_parses_booleans(monkeypatch, raw, expected):
    monkeypatch.setenv("COOK_FIRING_AUTO_FIRE", raw)
    assert Config.from_env().firing.auto_fire is expected


def test_tuple_fields_are_left_alone(monkeypatch):
    monkeypatch.setenv("COOK_DETECTOR_MAIZE_LOWER", "nonsense")
    assert Config.from_env().detector.maize_lower == DEFAULT_MAIZE_LOWER


def test_describe_lists_every_section():
    text = Config().describe()
    for section in ("camera", "detector", "tracker", "firing", "gpio", "display"):
        assert section in text


def test_env_overrides_hsv_tuples(monkeypatch):
    monkeypatch.setenv("COOK_DETECTOR_MAIZE_LOWER", "10,80,80")
    monkeypatch.setenv("COOK_DETECTOR_MAIZE_UPPER", "40,255,255")
    config = Config.from_env()
    assert config.detector.maize_lower == (10, 80, 80)
    assert config.detector.maize_upper == (40, 255, 255)


def test_malformed_tuple_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("COOK_DETECTOR_MAIZE_LOWER", "10,80")       # too few
    monkeypatch.setenv("COOK_DETECTOR_MAIZE_UPPER", "a,b,c")       # not numbers
    config = Config.from_env()
    assert config.detector.maize_lower == DEFAULT_MAIZE_LOWER
    assert config.detector.maize_upper == DEFAULT_MAIZE_UPPER
