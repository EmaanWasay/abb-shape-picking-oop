"""Drawing the results on the camera picture for the GUI."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .config import Config
from .models import MarkerPose

MAGENTA = (255, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)


class FrameAnnotator:
    """Draws outlines, positions and orientations on a smaller copy of the picture.

    The picture is made smaller FIRST and the text is drawn after, so the
    text keeps its size and stays readable in the browser.
    """

    def __init__(self, config: Config):
        self._width = config.display_width
        self._marker_mm = config.aruco_size_mm

    def draw(self, image: np.ndarray, marker: Optional[MarkerPose], objects: list,
             detections: list, inference_ms: float) -> np.ndarray:
        img_h, img_w = image.shape[:2]
        k = self._width / img_w
        display = cv2.resize(image, (self._width, int(round(img_h * k))), interpolation=cv2.INTER_AREA)

        def to_display(x, y):
            return int(round(x * k)), int(round(y * k))

        def scaled(contour):
            return np.round(contour.astype(np.float32) * k).astype(np.int32)

        if marker is not None:
            m = to_display(*marker.center_px)
            cv2.polylines(display, [scaled(marker.corners.reshape(-1, 1, 2))], True, MAGENTA, 3)
            cv2.circle(display, m, 7, MAGENTA, -1)
            self._label(display, f"ArUco  {marker.px_per_mm:.2f} px/mm", (m[0] + 12, m[1] - 12),
                        MAGENTA, 0.6)

            for obj in objects:
                c = to_display(*obj.detection.centroid_px)
                contour = scaled(obj.detection.contour)
                x, y, w, h = cv2.boundingRect(contour)

                cv2.line(display, m, c, MAGENTA, 1, cv2.LINE_AA)
                cv2.drawContours(display, [contour], -1, GREEN, 3)
                cv2.circle(display, c, 6, RED, -1)

                self._label(display, obj.label, (x, y - 12), WHITE, 0.8)
                line = self._label(display, f"X={obj.x_mm:.1f}  Y={obj.y_mm:.1f} mm",
                                   (x, y + h + 28), YELLOW, 0.65)
                self._label(display, f"angle={obj.angle_deg:.1f}  turn={obj.rotation_deg:.1f} deg",
                            (x, y + h + 28 + line), YELLOW, 0.65)

            status = (f"Shapes: {len(objects)}  |  Scale: {marker.px_per_mm:.2f} px/mm  |  "
                      f"Marker: {self._marker_mm:.0f} mm  |  AI: {inference_ms:.0f} ms")
            status_color = GREEN
        else:
            for det in detections:
                cv2.drawContours(display, [scaled(det.contour)], -1, GREEN, 3)
                cv2.circle(display, to_display(*det.centroid_px), 6, RED, -1)
            status = f"Shapes: {len(detections)}  |  ArUco NOT DETECTED  |  AI: {inference_ms:.0f} ms"
            status_color = RED

        self._label(display, status, (12, 36), status_color, 0.85)
        return display

    @staticmethod
    def _label(img: np.ndarray, text: str, org: tuple, color: tuple,
               scale: float = 0.7, thickness: int = 2) -> int:
        """Text on a black box, readable on any background. Returns the line height."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), base = cv2.getTextSize(text, font, scale, thickness)
        x = max(4, min(int(org[0]), img.shape[1] - tw - 6))
        y = max(th + 6, min(int(org[1]), img.shape[0] - base - 4))
        cv2.rectangle(img, (x - 4, y - th - 6), (x + tw + 4, y + base + 3), (0, 0, 0), -1)
        cv2.putText(img, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)
        return th + base + 12
