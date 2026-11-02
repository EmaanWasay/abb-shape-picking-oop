"""
AI inference: finding the shapes with the trained YOLO model.

ShapeDetector is the interface. YoloShapeDetector is the real one; the
rest of the program does not know which detector it is talking to.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Optional

import cv2
import numpy as np

from .color import ColorClassifier
from .config import Config
from .models import Detection
from .orientation import OrientationEstimator


class ShapeDetector(ABC):
    """Anything that can find shapes in a picture."""

    @abstractmethod
    def load(self) -> None:
        """Prepare the model (called once at start-up)."""

    @abstractmethod
    def detect(self, image: np.ndarray) -> tuple:
        """Return (list of Detection, inference time in ms)."""


class YoloShapeDetector(ShapeDetector):
    """Finds group 1's shapes with the trained YOLO segmentation model."""

    def __init__(self, config: Config, color_classifier: ColorClassifier,
                 orientation: OrientationEstimator, model=None):
        self._config = config
        self._colors = color_classifier
        self._orientation = orientation
        self._model = model         # can be given directly (tests); otherwise loaded in load()

    def load(self) -> None:
        if self._model is None:
            if not os.path.isdir(self._config.model_path):
                raise SystemExit(
                    f"Model folder not found: {self._config.model_path}\n"
                    "Put the 'best_ncnn_model' folder next to main.py.")
            print("Loading YOLO model...")
            from ultralytics import YOLO        # imported here: slow, and not needed in tests
            self._model = YOLO(self._config.model_path, task="segment")

        size = self._config.model_image_size
        self._model.predict(np.zeros((size, size, 3), np.uint8), imgsz=size, verbose=False)   # warm-up
        print("YOLO ready.")

    def detect(self, image: np.ndarray) -> tuple:
        # ---- AI inference (timed) ----
        start = time.perf_counter()
        result = self._model.predict(image, imgsz=self._config.model_image_size,
                                     conf=self._config.model_confidence, verbose=False)[0]
        inference_ms = (time.perf_counter() - start) * 1000.0

        detections = []
        if result.masks is None:
            return detections, inference_ms

        gains = self._colors.white_balance(image)
        for polygon, class_id, score in zip(result.masks.xy,
                                            result.boxes.cls.tolist(),
                                            result.boxes.conf.tolist()):
            shape = result.names[int(class_id)]
            if shape not in self._config.target_shapes:
                continue                            # not one of group 1's shapes
            detection = self._make_detection(image, polygon, shape, float(score), gains)
            if detection is not None:
                detections.append(detection)

        # Fixed order (left to right, then top to bottom) so the list does not jump around
        detections.sort(key=lambda d: (d.centroid_px[0] // 50, d.centroid_px[1]))
        return detections, inference_ms

    def _make_detection(self, image: np.ndarray, polygon, shape: str, score: float,
                        gains: np.ndarray) -> Optional[Detection]:
        """Turn one segmentation mask into a Detection (or None if it is not usable)."""
        contour = np.asarray(polygon, dtype=np.int32).reshape(-1, 1, 2)
        if len(contour) < 3:
            return None

        area = cv2.contourArea(contour)
        if not self._config.min_area_px <= area <= self._config.max_area_px:
            return None

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        img_h, img_w = image.shape[:2]
        cx = min(max(int(moments["m10"] / moments["m00"]), 0), img_w - 1)
        cy = min(max(int(moments["m01"] / moments["m00"]), 0), img_h - 1)

        color, hsv = self._colors.classify(image, contour, gains)
        width, height = cv2.minAreaRect(contour)[1]

        return Detection(
            shape=shape,
            color=color,
            hsv=hsv,
            centroid_px=(cx, cy),
            angle_deg=round(self._orientation.estimate(contour, shape), 2),
            size_px=max(width, height),
            contour=contour,
            confidence=score,
        )
