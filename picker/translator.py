"""
Coordinate translation: camera pixels -> robot work object "white" (mm).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .config import Config
from .models import LocatedObject, MarkerPose
from .orientation import PlacementPlanner


class CoordinateTranslator:
    """Converts pixel positions into the robot's work object coordinates.

    The ArUco marker is the reference:
      - its known size gives the scale (pixels per mm),
      - its angle lines the camera up with the sheet,
      - its centre has a measured position in work object "white"
        (Config.marker_x_mm / marker_y_mm).
    """

    def __init__(self, config: Config, planner: PlacementPlanner):
        self._config = config
        self._planner = planner

    def offset_from_marker_mm(self, point_px: tuple, marker: MarkerPose) -> tuple:
        """Distance from the marker centre in mm, along the marker's own axes.

        Returns (dx, dy): dx = to the right in the picture, dy = down.
        """
        dx_px = point_px[0] - marker.center_px[0]
        dy_px = point_px[1] - marker.center_px[1]

        a = np.radians(-marker.angle_deg)          # undo the marker's rotation
        dx_rot = dx_px * np.cos(a) - dy_px * np.sin(a)
        dy_rot = dx_px * np.sin(a) + dy_px * np.cos(a)
        return dx_rot / marker.px_per_mm, dy_rot / marker.px_per_mm

    def to_work_object(self, point_px: tuple, marker: MarkerPose) -> tuple:
        """Pixel -> (X, Y) in mm in work object "white"."""
        dx_mm, dy_mm = self.offset_from_marker_mm(point_px, marker)
        # Down in the picture is the robot's +X, right in the picture is +Y
        return self._config.marker_x_mm + dy_mm, self._config.marker_y_mm + dx_mm

    def locate(self, detections: list, marker: Optional[MarkerPose]) -> list:
        """Give every usable detection its work object position and wrist turn."""
        if marker is None:
            return []                              # no reference, no positions

        objects = []
        for det in detections:
            size_mm = det.size_px / marker.px_per_mm
            if not self._config.min_size_mm <= size_mm <= self._config.max_size_mm:
                continue                           # too small or too big (e.g. a magnet)

            x_mm, y_mm = self.to_work_object(det.centroid_px, marker)
            angle = det.angle_deg - marker.angle_deg
            objects.append(LocatedObject(
                index=len(objects),
                detection=det,
                x_mm=x_mm,
                y_mm=y_mm,
                angle_deg=angle,
                rotation_deg=self._planner.rotation(det.shape, angle),
                size_mm=size_mm,
            ))
        return objects
