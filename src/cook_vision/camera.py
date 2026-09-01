"""Frame sources.

The Pi camera on a Jetson Nano is a CSI sensor reached through the NVIDIA
GStreamer stack, not a plain V4L2 device, so it needs a purpose-built pipeline.
The other sources exist so the whole application can be developed and soaked on
a workstation with no camera attached.
"""
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


def csi_pipeline(capture_width, capture_height, output_width, output_height,
                 fps, flip_method, sensor_id=0) -> str:
    """GStreamer pipeline for an IMX219/IMX477 on the Nano's CSI connector.

    Capture and output sizes are separate on purpose. The sensor only offers a
    few fixed modes, so we capture in one of those and let **nvvidconv scale on
    the ISP** to whatever the display wants. That scale is free: doing the same
    resize with cv2.resize on the ARM cores measured 17ms a frame, which was
    more than the entire rest of the pipeline.
    """
    return (
        "nvarguscamerasrc sensor-id={sensor} ! "
        "video/x-raw(memory:NVMM), width=(int){cw}, height=(int){ch}, "
        "framerate=(fraction){fps}/1 ! "
        "nvvidconv flip-method={flip} ! "
        "video/x-raw, width=(int){ow}, height=(int){oh}, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink drop=true max-buffers=2 sync=false".format(
            sensor=sensor_id, cw=capture_width, ch=capture_height,
            ow=output_width, oh=output_height, fps=fps, flip=flip_method
        )
    )


class SyntheticCamera:
    """A moving Block M on a neutral field, for development without hardware."""

    def __init__(self, width=1280, height=720, fps=30):
        from .detectors.template import render

        self.width, self.height, self.fps = width, height, fps
        self._size = max(80, height // 6)
        # Low-saturation field: matches neither the maize nor the blue
        # detection range, since blue is itself a valid Block-M colour.
        self._patch = render(self._size, (5, 203, 255), (40, 40, 40))
        self._frame_index = 0

    def read(self):
        import math

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (40, 40, 40)
        phase = self._frame_index / 45.0
        left = int((self.width - self._size) * (0.5 + 0.42 * math.sin(phase)))
        top = int((self.height - self._size) * (0.5 + 0.30 * math.cos(phase * 0.7)))
        frame[top:top + self._size, left:left + self._size] = self._patch
        # A decoy: a yellow disc the shape stage must reject.
        cv2.circle(frame, (int(self.width * 0.15), int(self.height * 0.8)), 40, (5, 203, 255), -1)
        self._frame_index += 1
        return True, frame

    def release(self):
        pass

    @property
    def description(self):
        return "synthetic {0}x{1}".format(self.width, self.height)


class Camera:
    """Uniform frame source over CSI, V4L2, a video file, or the synthetic feed."""

    def __init__(self, config):
        self.config = config
        self._capture = None
        self._synthetic = None
        self._open()

    def _open(self):
        source = self.config.source
        if source == "auto":
            source = "csi" if self._try_csi() else "synthetic"
            if source == "synthetic" and self._try_v4l2():
                source = "v4l2"
        self.source = source

        if source == "synthetic":
            self._synthetic = SyntheticCamera(
                self.config.width, self.config.height, self.config.fps
            )
            LOGGER.warning("No camera found; using the synthetic feed.")
            return

        if source == "csi":
            pipeline = csi_pipeline(
                self.config.capture_width,
                self.config.capture_height,
                self.config.width,
                self.config.height,
                self.config.fps,
                self.config.flip_method,
                int(self.config.device) if self.config.device.isdigit() else 0,
            )
            self._capture = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        elif source == "v4l2":
            device = int(self.config.device) if self.config.device.isdigit() else self.config.device
            self._capture = cv2.VideoCapture(device)
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.config.fps)
            # A one-frame buffer keeps the seeker looking at now, not 200ms ago.
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        elif source == "file":
            self._capture = cv2.VideoCapture(self.config.device)
        else:
            raise ValueError("Unknown camera source {0!r}".format(source))

        if not self._capture.isOpened():
            raise RuntimeError(
                "Unable to open {0} camera ({1})".format(source, self.config.device)
            )

    def _try_csi(self) -> bool:
        pipeline = csi_pipeline(
            self.config.capture_width, self.config.capture_height,
            self.config.width, self.config.height,
            self.config.fps, self.config.flip_method,
        )
        probe = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        opened = probe.isOpened()
        probe.release()
        return opened

    def _try_v4l2(self) -> bool:
        device = int(self.config.device) if self.config.device.isdigit() else 0
        probe = cv2.VideoCapture(device)
        opened = probe.isOpened()
        probe.release()
        return opened

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._synthetic is not None:
            return self._synthetic.read()
        ok, frame = self._capture.read()
        if not ok and self.source == "file":
            # Loop recorded footage so soak tests run indefinitely.
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        return ok, frame

    def release(self) -> None:
        if self._synthetic is not None:
            self._synthetic.release()
        elif self._capture is not None:
            self._capture.release()

    @property
    def description(self) -> str:
        if self._synthetic is not None:
            return self._synthetic.description
        return "{0} {1}x{2}@{3}".format(
            self.source, self.config.width, self.config.height, self.config.fps
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
