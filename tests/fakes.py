"""
Fake camera, fake YOLO model and a synthetic test scene.

They let the whole program run on a normal computer, without the Basler
camera, the trained model or the robot.
"""
from __future__ import annotations

import socket
import threading
import time

import cv2
import numpy as np

from picker.camera import Camera

PX_PER_MM = 4.75                    # scale of the synthetic picture
MARKER_CENTER = (1000, 800)         # marker centre in pixels
CLASS_NAMES = {0: "circle", 1: "hexagon", 2: "square", 3: "star", 4: "triangle"}


def square(cx, cy, size_mm=55):
    s = size_mm * PX_PER_MM
    return np.array([[cx - s / 2, cy - s / 2], [cx + s / 2, cy - s / 2],
                     [cx + s / 2, cy + s / 2], [cx - s / 2, cy + s / 2]], np.float32)


def triangle(cx, cy, size_mm=55):
    s = size_mm * PX_PER_MM
    h = s * 0.866
    return np.array([[cx - s / 2, cy + h / 3], [cx + s / 2, cy + h / 3], [cx, cy - 2 * h / 3]], np.float32)


def circle(cx, cy, diameter_mm=55):
    r = diameter_mm * PX_PER_MM / 2
    a = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1).astype(np.float32)


# (outline, BGR colour, YOLO class id) - one hexagon that must be ignored,
# and one magnet-sized circle that must be filtered out by size
SCENE = [
    (triangle(300, 400), (40, 40, 200), 4),        # red triangle
    (circle(1650, 400), (190, 90, 30), 0),         # blue circle
    (square(400, 1250), (40, 40, 200), 2),         # red square
    (circle(1650, 1250), (60, 160, 40), 0),        # green circle
    (circle(1000, 230), (40, 40, 200), 1),         # "hexagon" - not group 1
    (circle(250, 900, 20), (30, 30, 30), 0),       # magnet (20 mm)
]


def make_scene_image() -> np.ndarray:
    """Tinted paper, a 101 mm ArUco marker and the shapes in SCENE."""
    img = np.full((1600, 2000, 3), (150, 172, 172), np.uint8)
    size = int(round(101 * PX_PER_MM))
    marker = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50), 0, size)
    x0 = MARKER_CENTER[0] - size // 2
    y0 = MARKER_CENTER[1] - size // 2
    img[y0:y0 + size, x0:x0 + size] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    for outline, color, _ in SCENE:
        cv2.fillPoly(img, [outline.astype(np.int32)], color)
    return img


class _List:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return list(self._values)


class _Result:
    """Looks like one ultralytics Results object."""
    def __init__(self, scene):
        self.names = CLASS_NAMES
        if scene:
            self.masks = type("Masks", (), {"xy": [o for o, _, _ in scene]})()
            self.boxes = type("Boxes", (), {"cls": _List([float(c) for _, _, c in scene]),
                                            "conf": _List([0.9] * len(scene))})()
        else:
            self.masks = None


class FakeYoloModel:
    """Answers predict() like the real YOLO model would for SCENE."""
    def __init__(self, scene=SCENE, delay_s=0.02):
        self._scene = scene
        self._delay_s = delay_s

    def predict(self, image, **kwargs):
        time.sleep(self._delay_s)
        return [_Result(self._scene)]


class FakeCamera(Camera):
    """Always returns the same synthetic picture."""
    def __init__(self, image=None):
        self._image = make_scene_image() if image is None else image
        self.opened = False

    def open(self):
        self.opened = True

    def grab(self):
        time.sleep(0.05)
        return self._image.copy()

    def close(self):
        self.opened = False


class FakeRobot:
    """Connects to the RobotServer like the RAPID program does.

    reply: "done" or "error" (what it answers after a command).
    """
    def __init__(self, port, reply="done"):
        self.received = []
        self._reply = reply
        self._sock = socket.create_connection(("127.0.0.1", port))
        self._sock.sendall(b"ready")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                data = self._sock.recv(100)
            except OSError:
                return
            if not data:
                return
            message = data.decode()
            self.received.append(message)
            if message == "quit":
                self._sock.close()
                return
            time.sleep(0.1)
            self._sock.sendall(self._reply.encode())
            self._sock.sendall(b"ready")

    def close(self):
        self._sock.close()


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
