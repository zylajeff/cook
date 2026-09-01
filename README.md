# Cook — Block-M Seeker

A Jetson Nano application that watches a Raspberry Pi camera feed for a
University of Michigan Block M, renders a missile-seeker HUD on the attached
display, and fires a pneumatic Nerf dart through a 12V solenoid — but only while
a physical toggle switch is held in the armed position.

```
camera ──▶ detector ──▶ tracker ──▶ interlocks ──▶ relay ──▶ solenoid
              │             │            │
              └─────────────┴────────────┴──────▶ seeker HUD ──▶ display
```

## Quick start

On a workstation with no hardware attached, everything runs against a synthetic
feed:

```bash
python -m pip install -e ".[dev]"
cook-vision --source synthetic --gpio mock --windowed
```

Press `a` to simulate flipping the arm switch, `f` to fire manually, `m` to see
the raw colour mask, `q` to quit.

On the Jetson:

```bash
python -m pip install -e ".[jetson]"     # NOT [dev]: keep the stock OpenCV
cook-vision
```

The camera source, GPIO backend, and display mode all default to `auto`, so the
bare command picks the CSI camera, real GPIO, and a fullscreen window.

## Safety

Firing is gated by eight interlocks, evaluated every frame and drawn along the
bottom of the HUD. All eight must pass:

| Interlock | Meaning |
|---|---|
| `startup` | 3s power-on lockout has elapsed |
| `arm switch` | the physical toggle is closed |
| `software safe` | the on-screen safety (`s`) is off |
| `target lock` | a track has persisted for 8 consecutive frames |
| `confidence` | the locked target scores ≥ 0.60 |
| `on bore` | the target is within 10% of frame width of the reticle |
| `cooldown` | ≥ 1.5s since the last shot |
| `relay idle` | the coil is not currently energised |

Three further protections are not interlocks but always apply:

- The relay pin is initialised to its **inactive** level, so bringing GPIO up
  cannot fire a dart.
- Every energise arms a watchdog timer that releases the coil after
  `max_pulse_seconds` (0.5s) even if the main loop stalls or crashes. A 12V
  solenoid held on will cook its coil.
- `atexit` and the shutdown path both de-energise the relay.

The launcher is fixed forward in this build — there is no pan/tilt yet — so the
`on bore` gate exists because a target the seeker can *see* is not necessarily a
target the barrel is *pointed at*.

## Detection

Two interchangeable backends behind one interface:

- **`color`** (default) — isolates the maize hue, then scores each blob against
  a rasterised Block-M template on four cues: `cv2.matchShapes` distance,
  bounding-box extent, convex-hull solidity, and aspect ratio. Needs no training
  data. On the synthetic bench a Block M scores ≈0.98 while a yellow disc scores
  ≈0.36 and a yellow square ≈0.26.
- **`onnx`** — a trained single-class YOLOv8 export. Drop it at
  `models/block-m.onnx` and run `cook-vision --model models/block-m.onnx`.

The colour backend is rotation-invariant by construction (Hu moments), which
also means an upside-down M reads as a match. If that matters, train the ONNX
model.

## Configuration

Every scalar in [`config.py`](src/cook_vision/config.py) is overridable as
`COOK_<SECTION>_<FIELD>`:

```bash
COOK_FIRING_PULSE_SECONDS=0.18 COOK_GPIO_RELAY_PIN=22 cook-vision
```

Useful ones: `COOK_DETECTOR_CONFIDENCE`, `COOK_DETECTOR_MAX_SHAPE_DISTANCE`,
`COOK_FIRING_AUTO_FIRE`, `COOK_FIRING_BORE_TOLERANCE`, `COOK_CAMERA_FLIP_METHOD`.

## Wiring

See [docs/wiring.md](docs/wiring.md). Short version: relay signal on pin 18,
arm switch on pin 16 to ground, and **the solenoid's 12V supply must not come
from the Jetson**.

## Tests

```bash
python -m pytest
```

54 tests covering detector discrimination, track lifecycle, every interlock, the
relay watchdog, switch debouncing, and an end-to-end run on the synthetic feed.

## Not yet built

Pan/tilt. The Lynxmotion kit is deliberately out of scope for round one; the
`on bore` interlock is the seam where it will attach.
