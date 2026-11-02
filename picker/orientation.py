"""Shape orientation (in the picture) and the wrist turn needed at the slot."""
from __future__ import annotations

import cv2
import numpy as np

from .config import Config


class OrientationEstimator:
    """Measures how much a shape is turned in the camera image (degrees)."""

    def __init__(self, config: Config):
        self._symmetry = config.symmetry

    def estimate(self, contour: np.ndarray, shape: str) -> float:
        if shape == "circle":
            return 0.0
        if shape == "triangle":
            return self._triangle_angle(contour)
        # square: rotated bounding box, wrapped to the shape's symmetry
        rect = cv2.minAreaRect(contour)
        return rect[2] % self._symmetry.get(shape, 360)

    @staticmethod
    def _triangle_angle(contour: np.ndarray) -> float:
        """Direction of the 3 corners seen from the centre, wrapped to 120 degrees."""
        perimeter = cv2.arcLength(contour, True)
        corners = cv2.approxPolyDP(contour, 0.05 * perimeter, True).reshape(-1, 2).astype(float)

        if len(corners) < 3:
            rect = cv2.minAreaRect(contour)
            return rect[2] % 120

        cx = np.mean(corners[:, 0])
        cy = np.mean(corners[:, 1])
        angles = [np.degrees(np.arctan2(py - cy, px - cx)) % 120 for px, py in corners]
        return float(np.median(angles))


class PlacementPlanner:
    """Works out how far the wrist must turn so the shape fits its slot."""

    def __init__(self, config: Config):
        self._symmetry = config.symmetry
        self._place_orientation = config.place_orientation

    def rotation(self, shape: str, angle_deg: float) -> float:
        """Shortest turn from the shape's angle to the slot's angle."""
        if shape == "circle":
            return 0.0
        period = self._symmetry.get(shape, 360)
        delta = (self._place_orientation.get(shape, 0.0) - angle_deg) % period
        if delta > period / 2:
            delta -= period
        return delta
