"""Finding the ArUco reference marker in the camera picture."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .config import Config
from .models import MarkerPose


class ArucoLocator:
    """Finds the reference marker: its centre, angle and scale (px per mm)."""

    def __init__(self, config: Config):
        params = cv2.aruco.DetectorParameters()
        params.minMarkerPerimeterRate = 0.01
        params.maxMarkerPerimeterRate = 4.0
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 23
        params.adaptiveThreshWinSizeStep = 5
        params.minCornerDistanceRate = 0.01
        dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, config.aruco_dictionary))

        self._detector = cv2.aruco.ArucoDetector(dictionary, params)
        self._marker_id = config.aruco_id
        self._size_mm = config.aruco_size_mm

    def locate(self, image: np.ndarray) -> Optional[MarkerPose]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detector.detectMarkers(gray)
        if ids is None:
            return None

        matches = np.where(ids.flatten() == self._marker_id)[0]
        if len(matches) == 0:
            return None

        c = corners[matches[0]][0]                     # 4 corners: TL, TR, BR, BL
        center = (float(np.mean(c[:, 0])), float(np.mean(c[:, 1])))
        angle = float(np.degrees(np.arctan2(c[1][1] - c[0][1], c[1][0] - c[0][0])))
        edge_px = np.mean([np.linalg.norm(c[(i + 1) % 4] - c[i]) for i in range(4)])

        return MarkerPose(center_px=center, angle_deg=angle,
                          px_per_mm=float(edge_px / self._size_mm), corners=c)
