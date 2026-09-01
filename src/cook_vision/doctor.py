"""Pre-flight checks for a fresh Jetson.

Run before the first launch, and any time the rig behaves oddly:

    ./run-on-jetson.sh --help      # confirms the tree imports
    python3 -m cook_vision.doctor  # confirms the platform underneath it

Every check is non-destructive. Nothing here touches the relay.
"""

import os
import platform
import subprocess
import sys

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_MARK = {PASS: "  ok  ", WARN: " warn ", FAIL: " FAIL "}


def _row(status, name, detail):
    print("[{0}] {1:<18} {2}".format(_MARK[status], name, detail))
    return status


def check_python():
    version = sys.version_info
    text = platform.python_version()
    if version < (3, 6):
        return _row(FAIL, "python", text + " (3.6 or newer required)")
    if version < (3, 7):
        # Expected on JetPack 4; the code is written to support it.
        return _row(PASS, "python", text + " (JetPack 4 baseline)")
    return _row(PASS, "python", text)


def check_dataclasses():
    try:
        import dataclasses  # noqa: F401
        return _row(PASS, "dataclasses", "available")
    except ImportError:
        return _row(FAIL, "dataclasses", "missing; run: sudo pip3 install dataclasses")


def check_numpy():
    try:
        import numpy
        return _row(PASS, "numpy", numpy.__version__)
    except ImportError as error:
        return _row(FAIL, "numpy", "{0}; run: sudo apt install python3-numpy".format(error))


def check_opencv():
    try:
        import cv2
    except ImportError as error:
        return _row(FAIL, "opencv", str(error))
    from .cvcompat import describe
    text = describe()
    status = PASS if int(cv2.__version__.split(".")[0]) >= 3 else FAIL
    return _row(status, "opencv", text)


def check_gstreamer():
    try:
        import cv2  # noqa: F401
    except ImportError:
        return _row(WARN, "gstreamer", "skipped; OpenCV unavailable")
    from .cvcompat import build_flag, has_feature
    detail = build_flag("GStreamer")
    if has_feature("GStreamer"):
        return _row(PASS, "gstreamer", detail[:80] or "enabled")
    return _row(
        FAIL, "gstreamer",
        "not built in; --source csi will not work (try --source v4l2)",
    )


def check_gpio():
    try:
        import Jetson.GPIO as GPIO
        return _row(PASS, "Jetson.GPIO", getattr(GPIO, "VERSION", "installed"))
    except ImportError:
        return _row(FAIL, "Jetson.GPIO", "missing; run: sudo pip3 install Jetson.GPIO")
    except Exception as error:
        return _row(WARN, "Jetson.GPIO", "imported with a warning: {0}".format(error))


def check_gpio_group():
    try:
        import grp
        groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
    except Exception as error:
        return _row(WARN, "gpio group", "could not read groups: {0}".format(error))
    if "gpio" in groups:
        return _row(PASS, "gpio group", "member")
    return _row(
        WARN, "gpio group",
        "not a member; GPIO will need sudo. Fix: sudo usermod -aG gpio $USER, then re-login",
    )


def check_video_devices():
    devices = sorted(p for p in os.listdir("/dev") if p.startswith("video"))
    if devices:
        return _row(PASS, "video devices", ", ".join("/dev/" + d for d in devices))
    return _row(WARN, "video devices", "none found; a CSI camera may still work via GStreamer")


def check_csi():
    binary = "/usr/bin/gst-launch-1.0"
    if not os.path.exists(binary):
        return _row(WARN, "csi camera", "gst-launch-1.0 not installed; skipped")
    try:
        proc = subprocess.Popen(
            [binary, "nvarguscamerasrc", "num-buffers=1", "!", "fakesink"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        output = proc.communicate()[0].decode("utf-8", "replace")
    except Exception as error:
        return _row(WARN, "csi camera", "probe failed: {0}".format(error))
    if "Setting pipeline to NULL" in output or "Freeing pipeline" in output:
        return _row(PASS, "csi camera", "nvarguscamerasrc opened and closed cleanly")
    return _row(WARN, "csi camera", "unexpected probe output; check the ribbon cable seating")


def check_display():
    display = os.environ.get("DISPLAY")
    if not display:
        return _row(WARN, "display", "DISPLAY unset; run with --headless, or export DISPLAY=:0")
    return _row(PASS, "display", display)


CHECKS = (
    check_python, check_dataclasses, check_numpy, check_opencv, check_gstreamer,
    check_gpio, check_gpio_group, check_video_devices, check_csi, check_display,
)


def main():
    print("cook-vision pre-flight\n" + "-" * 62)
    results = [check() for check in CHECKS]
    print("-" * 62)
    failed = results.count(FAIL)
    warned = results.count(WARN)
    if failed:
        print("{0} blocking problem(s). Fix those before running the app.".format(failed))
    elif warned:
        print("Ready, with {0} caveat(s) noted above.".format(warned))
    else:
        print("All checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
