"""Colour naming for the detected shapes."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .config import Config


class ColorClassifier:
    """Names the colour of a shape: red, green, blue, black or white."""

    def __init__(self, config: Config):
        self._saturation_min = config.color_saturation_min
        self._black_white_value = config.black_white_value
        self._use_white_balance = config.use_white_balance

    def white_balance(self, image: np.ndarray) -> np.ndarray:
        """Per-channel gains that make the white paper neutral grey.

        The paper is the brightest large area, so the brightest 20 % of the
        pixels are used as the white reference. This removes the camera's
        green-yellow tint before colours are named.
        """
        if not self._use_white_balance:
            return np.ones(3)
        small = image[::8, ::8].reshape(-1, 3).astype(np.float32)
        brightness = small.sum(axis=1)
        bright = small[brightness >= np.percentile(brightness, 80)]
        reference = np.maximum(np.median(bright, axis=0), 1.0)
        return reference.mean() / reference

    def classify(self, image: np.ndarray, contour: np.ndarray,
                 gains: Optional[np.ndarray] = None) -> tuple:
        """Average colour inside the contour -> (name, (h, s, v)).

        Uses the whole shape (not one pixel) and ignores a thin band at the
        edges, where the shape's side wall and shadow are.
        """
        x, y, w, h = cv2.boundingRect(contour)
        crop = image[y:y + h, x:x + w]
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1, offset=(-x, -y))
        inner = cv2.erode(mask, np.ones((9, 9), np.uint8))
        if cv2.countNonZero(inner) > 0:
            mask = inner

        b, g, r, _ = cv2.mean(crop, mask=mask)
        bgr = np.array([b, g, r])
        if gains is not None:
            bgr = np.clip(bgr * gains, 0, 255)
        pixel = np.uint8([[np.round(bgr)]])
        hue, sat, val = (int(c) for c in cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0])
        return self.name_of(hue, sat, val), (hue, sat, val)

    def name_of(self, hue: int, sat: int, val: int) -> str:
        """Colour name from OpenCV HSV values (H 0-179, S and V 0-255)."""
        if sat < self._saturation_min:
            return "black" if val < self._black_white_value else "white"
        if val < 50:
            return "black"
        if hue < 25 or hue >= 150:
            return "red"
        if hue < 90:
            return "green"
        return "blue"
