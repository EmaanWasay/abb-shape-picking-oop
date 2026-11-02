"""
Data classes that are passed between the parts of the system.

They only hold data - the work is done by the classes in the other files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Detection:
    """One shape found by the AI model, in camera pixels."""
    shape: str                  # "circle", "square" or "triangle"
    color: str                  # "red", "green", "blue", "black" or "white"
    hsv: tuple                  # measured colour (for tuning)
    centroid_px: tuple          # (x, y) centre in the camera image
    angle_deg: float            # how much the shape is turned in the image
    size_px: float              # longest side of the rotated bounding box
    contour: np.ndarray         # outline from the segmentation mask
    confidence: float           # model score 0..1


@dataclass
class MarkerPose:
    """Where the ArUco marker is in the camera image."""
    center_px: tuple            # (x, y) centre of the marker
    angle_deg: float            # rotation of the marker in the image
    px_per_mm: float            # scale, from the known marker size
    corners: np.ndarray         # the 4 corner points


@dataclass
class LocatedObject:
    """A detected shape with its position in the robot's work object."""
    index: int                  # position in the list (0, 1, 2 ...)
    detection: Detection
    x_mm: float                 # X in work object "white"
    y_mm: float                 # Y in work object "white"
    angle_deg: float            # orientation relative to the marker
    rotation_deg: float         # wrist turn needed to fit the slot
    size_mm: float

    @property
    def shape(self) -> str:
        return self.detection.shape

    @property
    def color(self) -> str:
        return self.detection.color

    @property
    def label(self) -> str:
        """Text shown on the video and in the GUI list, e.g. "[2] red circle"."""
        return f"[{self.index + 1}] {self.color} {self.shape}"


@dataclass
class PickCommand:
    """Everything the robot needs to pick one shape and place it."""
    x_mm: float
    y_mm: float
    shape_id: int
    rotation_deg: float

    def to_message(self) -> str:
        """Message format read by the RAPID program: "x,y,shapeID,rotation"."""
        return f"{self.x_mm:.2f},{self.y_mm:.2f},{self.shape_id},{self.rotation_deg:.2f}"


@dataclass
class InferenceResult:
    """Output of the AI thread: one picture and what the model found in it."""
    image: np.ndarray
    detections: list
    inference_ms: float


@dataclass
class FrameResult:
    """Output of the coordinate thread: everything the GUI shows."""
    objects: list = field(default_factory=list)     # LocatedObject list
    marker: Optional[MarkerPose] = None
    inference_ms: float = 0.0
    jpeg: Optional[bytes] = None                    # annotated picture for the web page
