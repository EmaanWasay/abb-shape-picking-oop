"""
All settings for the shape-picking system, in one place.

Change values here - not inside the other files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Folder that contains main.py (the project root)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Config:
    """Settings for every part of the system (read-only while running)."""

    # ----- AI model (YOLO segmentation, exported to NCNN) -----
    model_path: str = os.path.join(PROJECT_DIR, "best_ncnn_model")
    model_image_size: int = 640              # the model was exported at 640x640
    model_confidence: float = 0.5
    target_shapes: tuple = ("circle", "square", "triangle")    # group 1
    max_inference_ms: float = 3000.0         # requirement: under 3 seconds

    # ----- Camera -----
    exposure_us: float = 200000.0

    # ----- ArUco marker (the reference point on the sheet) -----
    aruco_dictionary: str = "DICT_5X5_50"
    aruco_id: int = 0
    aruco_size_mm: float = 101.0             # black square, measured edge to edge
    # Marker centre in the robot's work object "white". Measured by jogging the
    # cup to the middle of the marker (Work object = white). Re-measure if the
    # sheet is moved.
    marker_x_mm: float = 147.52
    marker_y_mm: float = 213.15

    # ----- Shape filters -----
    min_area_px: float = 6000
    max_area_px: float = 90000
    min_size_mm: float = 35.0                # smaller than this = a magnet, not a shape
    max_size_mm: float = 90.0

    # ----- Colours -----
    colors: tuple = ("red", "green", "blue", "black", "white")
    color_saturation_min: int = 70           # less saturated = black or white
    black_white_value: int = 120             # for those: darker = black, brighter = white
    use_white_balance: bool = True           # remove the camera's green-yellow tint

    # ----- Placing -----
    # After how many degrees each shape looks the same again
    symmetry: dict = field(default_factory=lambda: {
        "circle": 360, "square": 90, "triangle": 120})
    # The angle each slot "wants" the shape at (tune by trial)
    place_orientation: dict = field(default_factory=lambda: {
        "triangle": 90.0, "square": 0.0, "circle": 0.0})
    # Must match GetTarget() in RAPID
    shape_ids: dict = field(default_factory=lambda: {
        "triangle": 1, "circle": 2, "square": 3})

    # ----- Network -----
    robot_host: str = "0.0.0.0"              # listen on every IP the Pi has
    robot_port: int = 5000                   # must match SocketConnect in RAPID
    robot_timeout_s: float = 180.0           # max wait for "done" (includes yellow button)
    web_port: int = 5001                     # web page: http://<Pi IP>:5001

    # ----- Display -----
    display_width: int = 1400                # width of the video picture in pixels
    print_every_s: float = 3.0               # how often the shape list is printed
