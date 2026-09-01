"""GPIO safety behaviour: idle levels, debouncing, and the relay watchdog."""
import time

import pytest

from cook_vision.config import GpioConfig
from cook_vision.hardware import HIGH, LOW, ArmSwitch, MockGpioBackend, SolenoidRelay


@pytest.fixture
def backend():
    return MockGpioBackend()


def test_relay_comes_up_inactive(backend):
    config = GpioConfig(relay_active_low=True)
    SolenoidRelay(backend, config, 0.5)
    # Active-low board: the pin must be HIGH at rest or the coil energises on boot.
    assert backend.read(config.relay_pin) == HIGH


def test_relay_comes_up_inactive_when_active_high(backend):
    config = GpioConfig(relay_active_low=False)
    SolenoidRelay(backend, config, 0.5)
    assert backend.read(config.relay_pin) == LOW


def test_pulse_energises_then_releases(backend):
    config = GpioConfig()
    relay = SolenoidRelay(backend, config, 0.5)
    relay.pulse(0.05)
    assert backend.read(config.relay_pin) == LOW  # active-low = energised
    assert relay.is_energised
    time.sleep(0.12)
    assert backend.read(config.relay_pin) == HIGH
    assert not relay.is_energised


def test_pulse_is_clamped_to_the_watchdog_ceiling(backend):
    relay = SolenoidRelay(backend, GpioConfig(), max_pulse_seconds=0.05)
    assert relay.pulse(10.0) == pytest.approx(0.05)


def test_watchdog_releases_a_stuck_coil(backend):
    config = GpioConfig()
    relay = SolenoidRelay(backend, config, max_pulse_seconds=0.02)
    relay.pulse(0.02)
    time.sleep(0.05)
    relay.update()
    assert backend.read(config.relay_pin) == HIGH


def test_deenergise_is_idempotent(backend):
    config = GpioConfig()
    relay = SolenoidRelay(backend, config, 0.5)
    relay.pulse(0.5)
    relay.deenergise()
    relay.deenergise()
    assert backend.read(config.relay_pin) == HIGH


def test_arm_switch_reads_safe_when_open(backend):
    config = GpioConfig(debounce_seconds=0.0)
    switch = ArmSwitch(backend, config)
    # Pulled up and open: HIGH means the operator has not flipped it.
    assert not switch.update()


def test_arm_switch_reads_armed_when_grounded(backend):
    config = GpioConfig(debounce_seconds=0.0)
    switch = ArmSwitch(backend, config)
    backend.set_input_level(config.arm_switch_pin, LOW)
    assert switch.update()


def test_debounce_rejects_a_transient_bounce(backend):
    config = GpioConfig(debounce_seconds=0.5)
    switch = ArmSwitch(backend, config)
    backend.set_input_level(config.arm_switch_pin, LOW)
    assert not switch.update(), "accepted a change before the debounce window closed"
    backend.set_input_level(config.arm_switch_pin, HIGH)
    assert not switch.update()


def test_debounce_accepts_a_settled_change(backend):
    config = GpioConfig(debounce_seconds=0.02)
    switch = ArmSwitch(backend, config)
    backend.set_input_level(config.arm_switch_pin, LOW)
    switch.update()
    time.sleep(0.05)
    assert switch.update()
