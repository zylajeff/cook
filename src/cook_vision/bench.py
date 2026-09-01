"""Per-stage timing, to find where the frame budget actually goes.

    python3 -m cook_vision.bench                     # synthetic feed
    python3 -m cook_vision.bench --source csi        # real camera
    python3 -m cook_vision.bench --source csi --show # include the imshow cost

Reports the median millisecond cost of each stage. The median rather than the
mean because the first few frames include one-off allocations.
"""

import argparse
import sys
import time

import cv2

from .app import fit_to_display
from .camera import Camera
from .config import Config
from .detectors import build_detector
from .firing import FireController
from .hardware import ArmSwitch, SolenoidRelay, build_backend
from .hud import SeekerHud
from .tracker import TargetTracker


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if not ordered:
        return 0.0
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _time(label, fn, repeats=25):
    fn()
    start = time.time()
    for _ in range(repeats):
        result = fn()
    print("    {0:<20} {1:7.2f} ms".format(label, (time.time() - start) / repeats * 1000))
    return result


def _deep(camera, detector, config):
    """Break the detector down on a real frame from this camera."""
    from .cvcompat import find_contours

    ok, frame = camera.read()
    if not ok:
        return
    inner = getattr(detector, "inner", detector)
    width = getattr(detector, "width", 0)

    print("-" * 46)
    print("  detector breakdown (frame {0}x{1})".format(frame.shape[1], frame.shape[0]))
    if width and frame.shape[1] > width:
        scaled = _time("resize to %d" % width, lambda: detector._shrink(
            frame, width / float(frame.shape[1])))
    else:
        scaled = frame
        print("    {0:<20} {1:>7}".format("resize", "skipped"))

    source = scaled
    if inner.config.blur:
        source = _time("GaussianBlur", lambda: cv2.GaussianBlur(scaled, (5, 5), 0))
    hsv = _time("cvtColor BGR2HSV", lambda: cv2.cvtColor(source, cv2.COLOR_BGR2HSV))
    _time("inRange maize", lambda: cv2.inRange(hsv, inner.maize_lower, inner.maize_upper))
    _time("inRange blue", lambda: cv2.inRange(hsv, inner.blue_lower, inner.blue_upper))
    mask = _time("mask (whole stage)", lambda: inner.mask(scaled))
    contours = _time("findContours", lambda: find_contours(mask))
    _time("scoring loop", lambda: [inner.score(c) for c in contours])
    print("    {0:<20} {1:7d}".format("contours", len(contours)))
    if contours:
        areas = sorted(cv2.contourArea(c) for c in contours)
        print("    {0:<20} min {1:.0f}  max {2:.0f}  (min_area_px {3})".format(
            "contour areas", areas[0], areas[-1], inner.config.min_area_px))
        best = max(inner.score(c) for c in contours)
        print("    {0:<20} {1:7.3f}".format("best score", best))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Time each pipeline stage")
    parser.add_argument("--source", default="synthetic")
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--show", action="store_true", help="include imshow in the timings")
    parser.add_argument("--deep", action="store_true",
                        help="also break the detector down stage by stage")
    args = parser.parse_args(argv)

    config = Config.from_env()
    config.camera.source = args.source
    if args.width:
        config.camera.width = args.width
    if args.height:
        config.camera.height = args.height
    config.gpio.backend = "mock"

    camera = Camera(config.camera)
    detector = build_detector(config.detector)
    tracker = TargetTracker(config.tracker)
    gpio = build_backend("mock")
    controller = FireController(
        SolenoidRelay(gpio, config.gpio, config.firing.max_pulse_seconds),
        ArmSwitch(gpio, config.gpio),
        config.firing,
    )
    hud = SeekerHud(config.display, config.firing)

    if args.show:
        cv2.namedWindow("bench", cv2.WINDOW_NORMAL)

    stages = {"read": [], "fit": [], "detect": [], "track": [], "hud": [], "show": []}
    ok, frame = camera.read()
    if not ok:
        print("camera read failed", file=sys.stderr)
        return 1
    print("source: {0}  frame: {1}x{2}  frames: {3}".format(
        camera.description, frame.shape[1], frame.shape[0], args.frames))

    for _ in range(args.frames):
        t0 = time.time()
        ok, frame = camera.read()
        t1 = time.time()
        if not ok:
            break
        frame = fit_to_display(frame, config.display)
        t1b = time.time()
        detections = detector.detect(frame)
        t2 = time.time()
        tracker.update(detections, frame.shape)
        decision = controller.update(tracker, frame.shape)
        t3 = time.time()
        rendered = hud.render(frame, tracker, decision, controller,
                              {"fps": 0.0, "backend": detector.name,
                               "source": args.source, "shots": 0})
        t4 = time.time()
        if args.show:
            cv2.imshow("bench", rendered)
            cv2.waitKey(1)
        t5 = time.time()

        stages["read"].append((t1 - t0) * 1000)
        stages["fit"].append((t1b - t1) * 1000)
        stages["detect"].append((t2 - t1) * 1000)
        stages["track"].append((t3 - t2) * 1000)
        stages["hud"].append((t4 - t3) * 1000)
        stages["show"].append((t5 - t4) * 1000)

    if args.deep:
        _deep(camera, detector, config)

    camera.release()
    if args.show:
        cv2.destroyAllWindows()

    print("-" * 46)
    total = 0.0
    for name in ("read", "fit", "detect", "track", "hud", "show"):
        if not stages[name] or (name == "show" and not args.show):
            continue
        value = _median(stages[name])
        total += value
        print("  {0:<8} {1:7.1f} ms".format(name, value))
    print("-" * 46)
    print("  {0:<8} {1:7.1f} ms  ({2:.1f} fps)".format(
        "total", total, 1000.0 / total if total else 0.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
