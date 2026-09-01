# Wiring

Pin numbers are **BOARD** numbering on the Jetson Nano 40-pin header (physical
position), which is what `Jetson.GPIO` is configured for in
[`hardware.py`](../src/cook_vision/hardware.py).

## Defaults

| Signal | Pin | Notes |
|---|---|---|
| Relay IN1 | 18 | `COOK_GPIO_RELAY_PIN` — logic signal only |
| Relay DC+/DC- | — | **12V, from the same battery pack as the solenoid — not the Jetson.** The relay is a Songle SRD-12VDC-SL-C, a 12V-coil part; the board's own datasheet/silkscreen confirms it. Jetson only supplies IN1. |
| Jetson GND | any GND pin | Tie to the 12V pack's negative terminal — IN1's optocoupler needs a shared ground reference with DC-, same as the solenoid's ground-sharing requirement below. |
| Arm switch | 16 | `COOK_GPIO_ARM_SWITCH_PIN`, **needs an external 10kΩ pull-up to 3.3V** (pin 1 or 17) — see "The arm switch" below |
| Arm switch return | 14 | GND |

Relay terminal blocks, from the board itself:
- **`IN1` / `DC-` / `DC+`** (logic side) — `IN1` to Jetson pin 18. `DC+`/`DC-` to
  the 12V battery pack, **not** the Jetson header.
- **`NC` / `COM` / `NO`** (switched side) — `COM`/`NO` to the solenoid circuit
  per "The solenoid" below. `NC` unused.

There's also a small jumper on the board near a silkscreened `H` — likely the
active-high/active-low trigger select this module's "High/Low Level Trigger"
labeling refers to. Check its position/datasheet before relying on the
`relay_active_low` software default; if you can select the polarity in
hardware, make sure it agrees with the config rather than fighting it.

## Parts

- **Relay**: ANMBEST 1-channel opto-isolated relay module, 12V, high/low trigger.
- **Solenoid**: U.S. Solid 1/8" NPT electric solenoid valve, 12V DC, 2-way
  normally closed.
- **Display**: Hosyond 7" IPS touchscreen, 1024x600. HDMI video, powered over
  its own USB-C cable at 5V/0.62A (2.55W) — light enough to run off the
  Jetson's own USB port rather than a separate supply.
- **Camera**: Raspberry Pi CSI camera, connects to the Nano's CSI connector
  directly. No external power.
- **Arm switch**: RobotShop RB-Spa-709, illuminated toggle switch with missile
  cover, 12V 20A contacts, LED runs from as low as 3.3V. See "The arm switch"
  below — the lamp isn't wired up, so it draws nothing from any supply here.
  RobotShop's own datasheet has no pinout diagram, so confirm the switch-vs-LED
  terminals with a multimeter before wiring rather than trusting a labeled
  scheme — there isn't one.
- **Solenoid power**: Aobao 8×AA 12V battery holder, ON/OFF switch and leads
  built in (sold as a 3-pack — two spares).

(Sourced from the original planning note. PSI/orifice rating for the solenoid
wasn't captured there — read it off the valve body or its listing if a
firing-pressure calculation needs it.)

## Power plan

**One wall outlet, no custom mains wiring**, plus a battery pack that needs
none at all:

1. **Jetson's own 5V supply** (barrel jack, 5V/4A) — the only thing actually
   plugged into the wall. Powers the Nano, and the display piggybacks on it
   over USB, so no separate brick for the screen. The Jetson supplies nothing
   else — the relay's coil is a 12V part (see "Defaults" above), not 5V, so
   it can't be powered from the Jetson's own header either.
2. **The 12V rail runs on batteries**, not mains: the Aobao 8×AA holder above,
   in place of a wall adapter, powering *both* the solenoid coil and the
   relay's DC+/DC- terminals. Its built-in ON/OFF switch doubles as a
   physical kill switch on the whole firing circuit, independent of the arm
   toggle. Use alkaline cells, not rechargeable NiMH — 8 NiMH cells only give
   9.6V nominal, which under-drives both 12V-rated parts and risks weak or
   unreliable actuation.

Kept on two entirely separate supplies deliberately, mains or not: the
solenoid is an inductive load that puts a switching spike on whatever rail it
shares, and you don't want that landing on the Jetson's compute rail mid-frame.
Add an inline fuse (1-2A) between the battery pack and the relay board — it's
now covering both the relay coil and the solenoid coil, and a bare battery
pack has no overcurrent protection of its own the way a wall adapter would.

## The relay

The common blue opto-isolated relay boards are **active-low**: the coil pulls in
when IN is driven LOW. That is the default (`relay_active_low: True`). If your
board energises on HIGH instead, set `COOK_GPIO_RELAY_ACTIVE_LOW=0` — otherwise
the logic is inverted and the solenoid will sit energised at idle.

Confirm before connecting the solenoid:

```bash
PYTHONPATH=src python3 -c "
from cook_vision.config import GpioConfig
from cook_vision.hardware import SolenoidRelay, build_backend
r = SolenoidRelay(build_backend(), GpioConfig(), 0.5)
input('Relay should be OFF. Enter to pulse...'); r.pulse(0.3)
"
```

You should hear one click in, one click out. If it clicks in as soon as the
script starts, your `active_low` setting is wrong.

## The solenoid

**Do not power the 12V solenoid from the Jetson.** It draws far more than the
carrier board can supply, and the inductive kickback on release will find its
way into your GPIO. Use a separate 12V supply:

```
12V+ ──── solenoid ──── relay COM
                        relay NO ──── 12V−
```

Put a flyback diode (1N4007, cathode to 12V+) across the solenoid coil if the
relay board does not already have one. Tie the 12V supply ground to the Jetson
ground so the two share a reference.

### Feeding the relay and the solenoid from one battery pack

The relay's DC+/DC- and the solenoid circuit are separate loads sharing the
same 12V pack, not wired in series — each battery terminal fans out to more
than one destination:

```
                    ┌── fuse (1-2A) ──┬── relay DC+
battery 12V+ ───────┘                 └── solenoid (one lead)

solenoid (other lead) ──── relay COM

                    ┌── relay DC-
battery 12V− ───────┼── relay NO
                    └── Jetson GND
```

Do the fan-out with a small screw-terminal distribution block per rail (one
in, several out) rather than twisting/soldering bare leads together — cheap,
and easy to redo if you rewire later. Fuse goes on the **positive** lead,
between the battery and the distribution block, so it protects the whole 12V
rail (relay coil + solenoid coil) with one part.

### The barrel

The solenoid's air outlet is 1/8" NPT — much smaller than a 1/2" PVC barrel
sized for a Nerf dart, so it takes two fittings to step up. Permanent joint,
not swappable (a quick-connect coupler/plug pair would go here instead if
that changes):

```
solenoid outlet ── 1/8" NPT male-male nipple ── reducer bushing ── PVC female adapter ── PVC barrel
                    (already have)               1/2" NPT male ×    1/2" FPT × slip,     glued in
                                                  1/8" NPT female    threads onto bushing
```

- Reducer bushing: 1/2" NPT male × 1/8" NPT female.
- PVC adapter: 1/2" Schedule 40, female adapter, slip × FPT.

PTFE tape on both NPT joints (tapered thread, needs it to seal). Actual PVC
cement on the slip joint, not a dry press-fit — that joint holds the
regulator's pressure at the moment of firing, and an unglued PVC fitting can
pop off under a pressure pulse rather than just leak.

## The arm switch

RobotShop RB-Spa-709. **Three** posts, marked `+`, `LED`, and `ground`
(RobotShop's own sheet has no pinout diagram — this is read off the part
itself, plus a multimeter check). The switch's actual contacts are `+` and
`LED` — on this design the LED taps its power off the same post the switch
switches, it isn't a separate isolated circuit. Confirmed by testing: `+` and
`LED` showed continuity in both probe directions (rules out one of them
secretly being a diode/LED leg) and toggled open/closed with the lever (rules
out a fixed internal tie). `ground` is the LED's cathode only, untouched by
the switch action.

- **`+` and `LED`** — the switch. One to Jetson pin 16, the other to ground
  (pin 14) — it's a plain non-polarized contact, doesn't matter which post
  goes to which pin.
- **`ground`** — leave disconnected. It's the LED's return path, not Jetson
  ground, and not part of the switch action.
- If the lamp ever gets wired up later: `+`/`LED` would then be carrying
  whatever powers the lamp, so it can't also go straight to a 3.3V GPIO pin —
  same shared-node caveat this doc had originally, before an in-between draft
  briefly (and wrongly) called this a 4-terminal, fully-isolated part.

**Needs an external pull-up.** `Jetson.GPIO` on this JetPack version silently
ignores `setup()`'s `pull_up_down` argument (it'll even print
`UserWarning: Jetson.GPIO ignores setup()'s pull_up_down parameter` if you're
watching for it) — the internal pull-up the software asks for never actually
gets applied, so pin 16 is left floating when the switch is open rather than
held HIGH. Symptom: wiring and software both look correct, but arming doesn't
reliably toggle. Fix is a real external pull-up: **10kΩ resistor from pin 16
to a 3.3V pin (pin 1 or 17)**. With that in place, the software's
`arm_switch_active_low: True` default and the fail-safe "broken wire reads
SAFE" behavior work as originally intended — it's the internal pull-up
specifically that doesn't exist here, not the pull-up concept itself.

Debouncing is handled in software (50ms); no RC network needed.

### Probing the raw pin

`ArmSwitch` only logs when its *debounced* state changes, which hides
whether the raw pin is actually toggling at all. To watch the raw GPIO level
directly, bypassing debounce and the rest of the app entirely:

```bash
PYTHONPATH=src python3 -c "
import time
from cook_vision.config import GpioConfig
from cook_vision.hardware import build_backend

config = GpioConfig()
backend = build_backend('jetson')  # 'jetson' not 'auto': fail loudly if it falls back to mock
backend.setup_input(config.arm_switch_pin, pull_up=config.arm_switch_active_low)
print('Watching pin', config.arm_switch_pin, '- Ctrl+C to stop')
last = None
while True:
    level = backend.read(config.arm_switch_pin)
    if level != last:
        print(time.strftime('%H:%M:%S'), 'raw level =', level)
        last = level
    time.sleep(0.1)
"
```

Toggle the switch while this runs. If nothing prints, the raw pin genuinely
never changes — the fault is upstream in the wiring (switch, pull-up, or the
header connection), not in the software's debounce or active-low logic. If it
does print both levels correctly, the hardware path is fine and the bug is in
how the app interprets or displays that state instead.

## The display and camera

Two cables each, both to the Jetson, no external power:

- **Display** — HDMI (video) + USB-C (power + touch) into any Jetson USB port.
- **Camera** — CSI ribbon cable into the Nano's camera connector.

Neither needs anything from the 12V rail or the power plan above beyond the
Jetson's own 5V supply already covering them.

## First power-on checklist

0. Both supplies connected (Jetson 5V, solenoid 12V), solenoid and switch
   wired per above.
1. Solenoid **disconnected**. Run `cook-vision` and confirm the HUD shows `SAFE`.
2. Flip the toggle. The HUD should switch to a blinking red `ARMED` and the
   `ARM SWITCH` interlock dot should turn green.
3. Still disconnected, hold a Block M in front of the camera at centre frame.
   You should hear the relay click. If it does not, read the interlock row — it
   names exactly which gate is holding.
4. Only then connect the solenoid, and point it somewhere safe.
