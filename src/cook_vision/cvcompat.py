"""Shims for the OpenCV version differences that matter to this project.

JetPack 4.2 (L4T 32.2, the 2019 Nano image) ships OpenCV 3.3.1, while a
development workstation almost certainly has OpenCV 4.x. The two differ in ways
that are silent until they crash.
"""

import cv2

#: OpenCV 3.x returns (image, contours, hierarchy); 4.x returns (contours,
#: hierarchy). Contours are second-to-last in both, which is what makes the
#: [-2] idiom below version-proof.
_OPENCV_MAJOR = int(cv2.__version__.split(".")[0])

#: cv2.CONTOURS_MATCH_I1 is missing from some 3.x Python builds. Its value has
#: always been 1.
MATCH_I1 = getattr(cv2, "CONTOURS_MATCH_I1", 1)


def find_contours(mask, mode=None, method=None):
    """cv2.findContours, normalised to return just the contour list."""
    mode = cv2.RETR_EXTERNAL if mode is None else mode
    method = cv2.CHAIN_APPROX_SIMPLE if method is None else method
    return cv2.findContours(mask, mode, method)[-2]


def build_flag(name):
    """Read one entry out of ``cv2.getBuildInformation()``.

    Two formats have to be handled. OpenCV 4 writes a single line::

        GStreamer:  YES (1.16.2)

    OpenCV 3 writes a bare header followed by an indented block::

        GStreamer:
          base:     YES (ver 1.14.5)
          video:    YES (ver 1.14.5)

    Grepping for lines containing the name only finds the empty header in the
    second form, which reads as a missing feature when it is actually present.
    """
    lines = cv2.getBuildInformation().split("\n")
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith(name):
            continue
        inline = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
        if inline:
            return inline
        # Bare header: gather the more-indented block beneath it.
        indent = len(line) - len(line.lstrip())
        block = []
        for follower in lines[index + 1:]:
            if not follower.strip():
                break
            if len(follower) - len(follower.lstrip()) <= indent:
                break
            block.append(follower.strip())
        return "; ".join(block) if block else ""
    return ""


def has_feature(name):
    """True when a build entry reports YES anywhere in its value or block."""
    return "YES" in build_flag(name).upper()


def describe():
    return "OpenCV {0} | GStreamer: {1} | CUDA: {2}".format(
        cv2.__version__,
        "yes" if has_feature("GStreamer") else "no",
        "yes" if has_feature("NVIDIA CUDA") else "no",
    )
