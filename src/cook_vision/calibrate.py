"""Sample the real colour of your Block M and suggest a threshold.

The default maize range is derived from the ideal swatch (#FFCB05). Real
printed maize, under real light, through a real sensor's white balance, can sit
well outside it. This measures what the camera actually sees.

    python3 -m cook_vision.calibrate --source csi

Hold the Block M so it fills the on-screen box, then press SPACE. With no
display attached, use --auto to sample after a countdown instead.
"""

import argparse
import sys
import time

import cv2
import numpy as np

from .camera import Camera
from .config import Config


def _percentiles(channel):
    return [float(np.percentile(channel, p)) for p in (2, 50, 98)]


#: Below these, a pixel carries no reliable hue -- it is grey or near-black, and
#: its "hue" is numerical noise that will wreck any percentile.
MIN_SAT, MIN_VAL = 60, 50

_BIN = 10  # hue bin width, in OpenCV's 0-179 scale


def _hue_clusters(hue):
    """Histogram hue into bins and return them commonest-first.

    Percentiles are the wrong summary for hue: it is circular, so red straddles
    both 0 and 179 and a p2/p98 spread reads as "every colour". Binning finds
    the actual clusters instead.
    """
    counts = np.bincount(hue // _BIN, minlength=180 // _BIN)
    total = float(counts.sum()) or 1.0
    order = np.argsort(counts)[::-1]
    return [(int(b * _BIN), int((b + 1) * _BIN), counts[b] / total)
            for b in order if counts[b]]


def report(roi):
    """Print what the sampled patch looks like, and a range that would catch it."""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    bgr = roi.reshape(-1, 3).mean(axis=0)
    pixels = hue.size

    colourful = (sat >= MIN_SAT) & (val >= MIN_VAL)
    fraction = colourful.sum() / float(pixels)

    print("\n" + "=" * 60)
    print("  mean BGR        B {0:.0f}  G {1:.0f}  R {2:.0f}"
          "        (maize should be ~5 / 203 / 255)".format(*bgr))
    print("  brightness      {0:.0f} / 255".format(float(val.mean())))
    print("  colourful px    {0:.0f}%   (saturation >= {1}, value >= {2})".format(
        fraction * 100, MIN_SAT, MIN_VAL))

    if fraction < 0.15:
        print("-" * 60)
        print("  Almost nothing in this patch carries a usable colour.")
        print("  Either the box is not filled by the M, or the image is too")
        print("  dark or washed out for colour thresholding to work at all.")
        print("=" * 60 + "\n")
        return None, None

    clusters = _hue_clusters(hue[colourful])
    print("-" * 60)
    print("  dominant hues among the colourful pixels:")
    for low, high, share in clusters[:4]:
        bar = "#" * int(share * 40)
        print("    {0:3d}-{1:<3d} ({2:5.1f} deg) {3:5.1f}%  {4}".format(
            low, high, (low + high), share * 100, bar))

    low, high, share = clusters[0]
    sub = colourful & (hue >= low) & (hue < high)
    # Generous floors: a threshold tuned tight to one sample will fail the
    # moment the light changes. Better to let the shape stage reject extras.
    s_lo = float(np.percentile(sat[sub], 5))
    v_lo = float(np.percentile(val[sub], 5))
    lower = (max(0, low - 8), max(50, int(s_lo) - 50), max(50, int(v_lo) - 50))
    upper = (min(179, high + 8), 255, 255)

    print("-" * 60)
    if 15 <= low <= 30:
        print("  That dominant cluster is in the yellow band. Good.")
    else:
        print("  Note: {0}-{1} is NOT the yellow band (expect ~18-30).".format(low, high))
        print("  Either the M is not maize-coloured to this camera, or white")
        print("  balance is shifting it. The range below still targets what the")
        print("  camera actually sees, which is what matters.")
    print("  Suggested settings:")
    print("    export COOK_DETECTOR_MAIZE_LOWER='{0},{1},{2}'".format(*lower))
    print("    export COOK_DETECTOR_MAIZE_UPPER='{0},{1},{2}'".format(*upper))
    print("=" * 60 + "\n")
    return lower, upper


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure the Block M's colour")
    parser.add_argument("--source", default="csi")
    parser.add_argument("--auto", action="store_true",
                        help="sample after a countdown instead of on a keypress")
    parser.add_argument("--delay", type=float, default=5.0)
    parser.add_argument("--save", help="write the sampled frame to this path")
    parser.add_argument("--box", type=float, default=0.12,
                        help="sample box size, as a fraction of the frame")
    args = parser.parse_args(argv)

    config = Config.from_env()
    config.camera.source = args.source
    camera = Camera(config.camera)

    ok, frame = camera.read()
    if not ok:
        print("camera read failed", file=sys.stderr)
        return 1
    height, width = frame.shape[:2]
    half_w, half_h = int(width * args.box / 2), int(height * args.box / 2)
    x0, y0 = width // 2 - half_w, height // 2 - half_h
    x1, y1 = width // 2 + half_w, height // 2 + half_h

    print("Camera: {0}".format(camera.description))
    print("Sampling the centre {0:.0f}% box. Fill it with the Block M.".format(args.box * 100))

    if args.auto:
        deadline = time.time() + args.delay
        announced = None
        while time.time() < deadline:
            ok, frame = camera.read()
            if not ok:
                break
            remaining = int(deadline - time.time()) + 1
            if remaining != announced:
                announced = remaining
                print("  sampling in {0}s...".format(remaining))
        if args.save:
            cv2.imwrite(args.save, frame)
            print("  saved frame to {0}".format(args.save))
        report(frame[y0:y1, x0:x1])
        camera.release()
        return 0

    print("SPACE to sample, q to quit.")
    window = "calibrate"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    while True:
        ok, frame = camera.read()
        if not ok:
            break
        preview = frame.copy()
        cv2.rectangle(preview, (x0, y0), (x1, y1), (0, 255, 255), 2)
        cv2.putText(preview, "fill this box, then SPACE", (x0, max(20, y0 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(window, preview)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord(" "):
            if args.save:
                cv2.imwrite(args.save, frame)
                print("  saved frame to {0}".format(args.save))
            report(frame[y0:y1, x0:x1])

    camera.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
