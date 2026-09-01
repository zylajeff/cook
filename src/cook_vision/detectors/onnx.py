"""YOLOv8 ONNX Block-M detector.

Drop a trained single-class export at ``models/block-m.onnx`` and select it with
``COOK_DETECTOR_BACKEND=onnx``. Everything downstream is unchanged.
"""
from pathlib import Path
from typing import List

import cv2
import numpy as np

from .base import Detection, Detector, clip_box


class OnnxYoloDetector(Detector):
    name = "onnx"

    def __init__(self, config) -> None:
        self.config = config
        self.model_path = Path(config.model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(
                "ONNX model not found: {0}. Train one, or run with "
                "COOK_DETECTOR_BACKEND=color.".format(self.model_path)
            )
        self.network = cv2.dnn.readNetFromONNX(str(self.model_path))
        # OpenCV picks CUDA when the Jetson's OpenCV is built with it; otherwise
        # this is a no-op and inference stays on the CPU.
        try:
            self.network.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.network.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        except cv2.error:
            pass

    def detect(self, frame: np.ndarray) -> List[Detection]:
        height, width = frame.shape[:2]
        size = self.config.input_size
        blob = cv2.dnn.blobFromImage(
            frame, 1 / 255.0, (size, size), swapRB=True, crop=False
        )
        self.network.setInput(blob)
        predictions = np.squeeze(self.network.forward()).T
        if predictions.ndim != 2 or predictions.shape[1] < 5:
            return []

        scale_x = width / float(size)
        scale_y = height / float(size)
        boxes, scores = [], []
        for prediction in predictions:
            confidence = float(np.max(prediction[4:]))
            if confidence < self.config.confidence:
                continue
            center_x, center_y, box_width, box_height = prediction[:4]
            boxes.append(
                [
                    int((center_x - box_width / 2) * scale_x),
                    int((center_y - box_height / 2) * scale_y),
                    int(box_width * scale_x),
                    int(box_height * scale_y),
                ]
            )
            scores.append(confidence)

        if not boxes:
            return []

        keep = cv2.dnn.NMSBoxes(
            boxes, scores, self.config.confidence, self.config.nms_threshold
        )
        detections = [
            Detection("BLOCK-M", scores[i], clip_box(boxes[i], width, height))
            for i in np.array(keep).reshape(-1)
        ]
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections
