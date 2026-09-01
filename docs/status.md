# Bring-up status

Last updated: 28 Aug 2026.

## Done

- [x] Full pipeline: capture → detect → track → interlocks → HUD, 65 tests passing
- [x] Backported to Python 3.6 for JetPack 4.2
- [x] OpenCV 3.3.1 compatibility (`cvcompat.py`)
- [x] Deployed to `burninator@192.168.86.30`, runs from source
- [x] `doctor` pre-flight green except DISPLAY
- [x] CSI camera confirmed working — GStreamer 1.14.1 linked into OpenCV
- [x] GPIO permissions fixed (gpio group + NVIDIA's udev rule)
- [x] Performance: 3 → 29 fps, now camera-limited
- [x] HUD verified on the 1024×600 panel
- [x] Chroma backend (`R − B` instead of HSV) implemented as
  `ChromaShapeDetector` / `COOK_DETECTOR_BACKEND=chroma`, subclassing the color
  backend's shape-scoring so only the mask differs. Tests cover the dim/warm
  maize and blue conditions that broke HSV. Known trade-off: R-B alone can't
  distinguish maize from generic red the way hue could — shape scoring is the
  only gate against that decoy now (see chroma.py).
- [x] Tried, then reverted, the tighter `maize_lower`/`maize_upper`
  `(18,172,160)-(32,255,255)` that a crop analysis suggested two nights ago
  but never actually got written to `config.py`. It appeared to break live
  detection of a Block M shown on a phone screen, but turned out **not** to
  be the tightened threshold — turning off some background light fixed
  detection with the reverted (old, looser) default still in place. Real
  cause was ambient light competing with the phone screen, not the HSV range.
  Current default `(18,120,120)-(34,255,255)` is unchanged; the tighter,
  crop-measured range was never actually at fault and is worth retrying later
  with a real `calibrate.py` reading rather than assumption either way.
- **New failure mode, distinct from the dim-target one below:** too much
  *competing* ambient light can wash out a self-lit source (phone screen)
  even though the target itself is well within threshold. Opposite direction
  from the original blocker (a dim, under-lit printed target). Both are real;
  don't let a fix for one be assumed to cover the other.
- [x] **Arm switch verified on real hardware.** `SAFE`/`ARMED` toggles cleanly,
  confirmed both on the raw GPIO probe and the HUD, solenoid still
  disconnected. Root cause of the long-running flakiness: pin 16 (and 15,
  which was tried and ruled out as pin-specific) has an internal pull-*down*
  baked in at the hardware/pinmux level that `Jetson.GPIO` can't disable,
  strong enough that a 10kΩ external pull-up only reached ~1V open-circuit —
  below the HIGH threshold — instead of 3.3V. **1kΩ**, not 10kΩ, is what
  actually overpowers it; `docs/wiring.md` now says so.

## Blocked

**Detection on the real target, not yet re-verified on hardware.** A printed
paper Block M produced a black mask on the camera — it reported the maize as
dim brown (`B 73 G 88 R 113`, brightness 113/255) and HSV thresholding failed
completely in that regime. The chroma backend above is the fix for that, built
and unit-tested against the measured colour values, but **not yet run against
the real camera** — next session should point the Nano at the actual target
with `COOK_DETECTOR_BACKEND=chroma` and confirm.

Ran both backends offline over the 258 `__train/block_m` / 314 `not_block_m`
photos (`/mnt/d/model_data/__train/`) as a sanity check: recall was a wash
(color 38.8%, chroma 37.6%) and chroma's false-positive rate was worse (33.1%
vs 20.7%), matching its documented can't-tell-red-from-maize trade-off. Not
read as a verdict — that corpus is general Block-M photos (logos, jerseys,
screenshots, per the dataset-defect audit in CLAUDE.md), not shots of the actual printed
target under real lighting, so it doesn't exercise the dim/warm case chroma
targets. The on-hardware test above is still the real answer.

If chroma doesn't fully resolve it: **trained YOLOv8n** is the fallback. Weights
already exist but need a JetPack 4.6 reflash plus a TensorRT engine — OpenCV
3.3.1 has no ONNX, and 4.1.1 predates reliable YOLOv8 ONNX support. Clean the
dataset and retrain first; see CLAUDE.md.

Also unresolved: whether the camera is simply underexposed. Worth ruling out
regardless, because a dim image still costs contrast under chroma too.

## Not started

- **The rest of the firing chain.** Arm switch is now verified (above); relay
  and solenoid are still untested — every run so far used a disconnected
  solenoid or `--gpio mock`. Next step is the relay with the solenoid still
  **disconnected**, listening for the click, then the solenoid itself.
- Pan/tilt (deliberately out of scope for round one).
- systemd service for start-on-boot.
