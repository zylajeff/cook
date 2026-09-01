# Cook — working notes

A Jetson Nano fires a pneumatic Nerf dart when a camera identifies a University
of Michigan Block M. Vision, HUD, and firing interlocks are all in
`src/cook_vision/`. See [README.md](README.md) for what it does and
[docs/wiring.md](docs/wiring.md) for the electrical side.

## Target platform — read this before changing anything

The Nano is **JetPack 4.2.1** (2019), not 4.6. That is the whole reason for
several odd-looking choices:

| Constraint | Consequence |
|---|---|
| Python **3.6.9** | No `from __future__ import annotations`, no stdlib `dataclasses`, no `math.dist`, no walrus, no f-string `=`. |
| OpenCV **3.3.1** | `findContours` returns 3 values, not 2. Use `cvcompat.find_contours`, never `cv2.findContours`. |
| OpenCV 3.3.1 | **No ONNX support.** `readNetFromONNX` is 3.4+. The `onnx` detector backend cannot run on the Nano as it stands. |
| numpy **1.13.3** (apt) | Matches the OpenCV build. Never let pip upgrade it — that produces `numpy.core.multiarray failed to import`. |
| setuptools < PEP 621 | `pip install -e .` cannot read `pyproject.toml` there. Run from source instead. |

`python3 -m cook_vision.doctor` checks all of this on the box.

## Running it

```bash
./sync-to-jetson.sh                                  # tar over ssh; the Nano has no rsync
./run-on-jetson.sh --source csi --gpio mock          # on the Nano
python3 -m cook_vision.doctor                        # pre-flight
python3 -m cook_vision.bench --source csi --deep     # per-stage timings
python3 -m cook_vision.calibrate --source csi        # measure the target's real colour
```

`run-on-jetson.sh` finds the X session itself. The desktop is on **DISPLAY `:1`**
(gdm puts a greeter on `:0`) with the cookie at `/run/user/1000/gdm/Xauthority`.

## Performance — measure, don't assume

The Nano went 3 → 29 fps through four changes, and x86 timings predicted none of
them well (one stage was 58× slower there than local timings suggested). Always
confirm with `bench --deep` on the actual hardware.

What mattered, largest first:

1. **HUD overlay**: a float mask multiply plus `convertScaleAbs` over 2.7M pixels
   every frame. Baking the mask to uint8 and using `cv2.multiply` is ~11× faster
   for a max difference of 1 per channel.
2. **CSI scaling on the ISP**: `nvvidconv` scales 1280×720 → 1024×600 for free.
   The same resize in `cv2.resize` cost 17 ms/frame on the ARM cores.
3. **Detect at 640 wide** (`DownscaledDetector`), boxes rescaled back.
4. **INTER_LINEAR, not INTER_AREA** — 4.6× cheaper here for an identical score.

The rig is now camera-limited, not CPU-limited: ~19 ms of compute against a 33 ms
frame interval. `COOK_CAMERA_FPS=60` if more is ever needed.

## Detection

`Detector` has three implementations behind one interface, chosen by
`COOK_DETECTOR_BACKEND`:

- **`color`** (default) — HSV maize threshold plus Block-M shape scoring. No
  training data. **Known weakness:** HSV fails outright on a dim, warm-white-
  balanced image — measured 0.000 against 0.997 for a red-minus-blue chroma
  difference under the same conditions.
- **`chroma`** — same Block-M shape scoring, but masks on raw `R − B` instead
  of HSV hue. Fixes the weakness above: R stays above B for maize (and B above
  R for Michigan blue) well past the point where hue becomes unreliable. Trade-
  off: it can't tell maize from generic red, or blue from violet, the way hue
  can — shape scoring is the only thing standing between a red decoy and a
  false positive. See `detectors/chroma.py`.
- **`onnx`** — YOLOv8 export. Cannot run on JetPack 4.2 (see above).

The user has an existing labelled dataset and trained weights outside this repo,
at `/mnt/d/model_data/blockm_yolo` and `~/WSL_Coding/runs/detect/`. Best run is
`blockm_yolov8n9` (mAP50 0.579), and that number is depressed by dataset defects,
not by the task being hard — 163 of 488 train images actually carry a box, and
some boxes are labelled `person`.

## Safety

Eight interlocks gate the relay; all are drawn on the HUD so the operator can see
which one is holding. Beyond them: the relay pin initialises to its inactive
level, every energise arms a watchdog timer that releases the coil even if the
main loop dies, and `atexit` de-energises. Tests in `tests/test_firing.py` and
`tests/test_hardware.py` cover each gate — keep them passing.

**The firing chain has never been tested on real hardware.** Everything so far has
run with `--gpio mock`.
