"""GPIO: the arming switch input and the solenoid relay output.

Safety notes that drive the design here:

* The relay pin is configured with its **inactive** level as the initial value,
  so bringing the pin up as an output cannot glitch the solenoid.
* Every energise arms an independent watchdog timer that de-energises the coil
  even if the main loop stalls, crashes, or is killed. A 12V solenoid held on is
  a burnt coil.
* The arm switch is debounced and read as a hard interlock. Software never
  bypasses it.
"""
import atexit
import logging
import threading
import time

LOGGER = logging.getLogger(__name__)

HIGH = 1
LOW = 0


class MockGpioBackend:
    """In-memory GPIO for development. The arm switch can be toggled from the UI."""

    name = "mock"

    def __init__(self):
        self._levels = {}
        self._inputs = set()

    def setup_output(self, pin, initial):
        self._levels[pin] = initial

    def setup_input(self, pin, pull_up=True):
        self._inputs.add(pin)
        # Idle level of a pulled-up input with the switch open.
        self._levels.setdefault(pin, HIGH if pull_up else LOW)

    def read(self, pin):
        return self._levels.get(pin, HIGH)

    def write(self, pin, level):
        self._levels[pin] = level

    def cleanup(self):
        self._levels.clear()

    def set_input_level(self, pin, level):
        """Test/development hook: drive an input pin from software."""
        self._levels[pin] = level


class JetsonGpioBackend:
    """Real hardware, via the Jetson.GPIO library in BOARD pin numbering."""

    name = "jetson"

    def __init__(self):
        import Jetson.GPIO as GPIO  # noqa: N814

        self._gpio = GPIO
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

    def setup_output(self, pin, initial):
        self._gpio.setup(pin, self._gpio.OUT, initial=initial)

    def setup_input(self, pin, pull_up=True):
        pud = self._gpio.PUD_UP if pull_up else self._gpio.PUD_DOWN
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=pud)

    def read(self, pin):
        return self._gpio.input(pin)

    def write(self, pin, level):
        self._gpio.output(pin, level)

    def cleanup(self):
        self._gpio.cleanup()


def build_backend(name="auto"):
    """Return a GPIO backend; ``auto`` prefers real hardware when available."""
    if name in ("auto", "jetson"):
        try:
            return JetsonGpioBackend()
        except Exception as error:  # ImportError on a workstation, RuntimeError off-Jetson
            if name == "jetson":
                raise
            LOGGER.warning("Jetson.GPIO unavailable (%s); using the mock backend.", error)
    return MockGpioBackend()


class ArmSwitch:
    """Debounced read of the illuminated toggle switch."""

    def __init__(self, backend, config):
        self._backend = backend
        self._pin = config.arm_switch_pin
        self._active_low = config.arm_switch_active_low
        self._debounce = config.debounce_seconds
        backend.setup_input(self._pin, pull_up=self._active_low)
        self._stable = self._raw()
        self._candidate = self._stable
        self._changed_at = time.monotonic()

    def _raw(self) -> bool:
        level = self._backend.read(self._pin)
        return level == (LOW if self._active_low else HIGH)

    def update(self) -> bool:
        """Sample the pin. Returns the debounced armed state."""
        reading = self._raw()
        now = time.monotonic()
        if reading != self._candidate:
            self._candidate = reading
            self._changed_at = now
        # Not elif: with debouncing disabled a change must land on this same call,
        # not wait for the next one.
        if reading != self._stable and (now - self._changed_at) >= self._debounce:
            self._stable = reading
            LOGGER.info("Arm switch -> %s", "ARMED" if reading else "SAFE")
        return self._stable

    @property
    def is_armed(self) -> bool:
        return self._stable


class SolenoidRelay:
    """The firing relay, with a watchdog that guarantees the coil turns back off."""

    def __init__(self, backend, config, max_pulse_seconds):
        self._backend = backend
        self._pin = config.relay_pin
        self._active_low = config.relay_active_low
        self._max_pulse = max_pulse_seconds
        self._lock = threading.Lock()
        self._watchdog = None
        self._energised_at = None

        backend.setup_output(self._pin, self._inactive_level)
        atexit.register(self.deenergise)

    @property
    def _active_level(self):
        return LOW if self._active_low else HIGH

    @property
    def _inactive_level(self):
        return HIGH if self._active_low else LOW

    @property
    def is_energised(self) -> bool:
        return self._energised_at is not None

    def pulse(self, seconds: float) -> float:
        """Energise the coil for ``seconds``, clamped by the watchdog ceiling."""
        duration = max(0.0, min(seconds, self._max_pulse))
        with self._lock:
            if self._watchdog is not None:
                self._watchdog.cancel()
            self._backend.write(self._pin, self._active_level)
            self._energised_at = time.monotonic()
            self._watchdog = threading.Timer(duration, self.deenergise)
            self._watchdog.daemon = True
            self._watchdog.start()
        LOGGER.info("Relay energised for %.0f ms", duration * 1000)
        return duration

    def deenergise(self) -> None:
        with self._lock:
            if self._watchdog is not None:
                self._watchdog.cancel()
                self._watchdog = None
            self._backend.write(self._pin, self._inactive_level)
            self._energised_at = None

    def update(self) -> None:
        """Belt-and-braces de-energise from the main loop, independent of the timer."""
        started = self._energised_at
        if started is not None and (time.monotonic() - started) >= self._max_pulse:
            LOGGER.warning("Relay watchdog tripped from the main loop.")
            self.deenergise()
