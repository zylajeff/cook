"""The interlock chain is the safety-critical part; test every gate."""
import time

import pytest

from cook_vision.config import FiringConfig, GpioConfig, TrackerConfig
from cook_vision.detectors import Detection
from cook_vision.firing import FireController
from cook_vision.hardware import ArmSwitch, MockGpioBackend, SolenoidRelay
from cook_vision.tracker import TargetTracker

SHAPE = (480, 640, 3)


@pytest.fixture
def rig():
    gpio_config = GpioConfig(debounce_seconds=0.0)
    firing_config = FiringConfig(
        startup_lockout_seconds=0.0, cooldown_seconds=1.0, pulse_seconds=0.01
    )
    backend = MockGpioBackend()
    switch = ArmSwitch(backend, gpio_config)
    relay = SolenoidRelay(backend, gpio_config, firing_config.max_pulse_seconds)
    controller = FireController(relay, switch, firing_config)
    tracker = TargetTracker(TrackerConfig(lock_frames=3))
    return backend, gpio_config, switch, relay, controller, tracker


def arm(backend, gpio_config, armed=True):
    """Drive the switch pin. Active-low: grounded (0) means armed."""
    backend.set_input_level(gpio_config.arm_switch_pin, 0 if armed else 1)


def acquire(tracker, x=320, confidence=0.9, frames=4):
    for _ in range(frames):
        tracker.update([Detection("BLOCK-M", confidence, (x - 40, 200, 80, 80))], SHAPE)


def test_will_not_fire_without_the_arm_switch(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    acquire(tracker)
    switch.update()
    decision = controller.update(tracker, SHAPE)
    assert not decision.ready
    assert "arm switch" in decision.blocking
    assert controller.shots == 0


def test_fires_when_every_interlock_passes(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker)
    decision = controller.update(tracker, SHAPE)
    assert decision.ready, decision.blocking
    assert controller.shots == 1


def test_will_not_fire_without_a_lock(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker, frames=1)
    decision = controller.update(tracker, SHAPE)
    assert "target lock" in decision.blocking
    assert controller.shots == 0


def test_will_not_fire_at_an_off_bore_target(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker, x=600)  # far right of a 640px frame
    decision = controller.update(tracker, SHAPE)
    assert "on bore" in decision.blocking
    assert controller.shots == 0


def test_will_not_fire_below_the_confidence_floor(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker, confidence=0.5)  # under the 0.60 fire threshold
    decision = controller.update(tracker, SHAPE)
    assert "confidence" in decision.blocking


def test_startup_lockout_blocks_an_immediate_shot():
    gpio_config = GpioConfig(debounce_seconds=0.0)
    firing_config = FiringConfig(startup_lockout_seconds=30.0)
    backend = MockGpioBackend()
    switch = ArmSwitch(backend, gpio_config)
    relay = SolenoidRelay(backend, gpio_config, firing_config.max_pulse_seconds)
    controller = FireController(relay, switch, firing_config)
    tracker = TargetTracker(TrackerConfig(lock_frames=3))
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker)
    assert "startup" in controller.update(tracker, SHAPE).blocking


def test_cooldown_prevents_a_second_shot(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker)
    controller.update(tracker, SHAPE)
    assert controller.shots == 1
    for _ in range(5):
        acquire(tracker, frames=1)
        controller.update(tracker, SHAPE)
    assert controller.shots == 1
    assert controller.cooldown_remaining > 0


def test_software_safety_blocks_firing(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    arm(backend, gpio_config)
    switch.update()
    controller.toggle_software_safe()
    acquire(tracker)
    assert "software safe" in controller.update(tracker, SHAPE).blocking


def test_manual_mode_needs_a_trigger_press(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    controller.config.auto_fire = False
    arm(backend, gpio_config)
    switch.update()
    acquire(tracker)
    controller.update(tracker, SHAPE)
    assert controller.shots == 0
    controller.request_fire()
    controller.update(tracker, SHAPE)
    assert controller.shots == 1


def test_a_refused_trigger_press_is_not_latched_for_later(rig):
    backend, gpio_config, switch, relay, controller, tracker = rig
    controller.config.auto_fire = False
    acquire(tracker)
    controller.request_fire()          # refused: not armed
    controller.update(tracker, SHAPE)
    arm(backend, gpio_config)          # now arm the rig
    switch.update()
    controller.update(tracker, SHAPE)
    assert controller.shots == 0, "a stale trigger press fired the launcher"
