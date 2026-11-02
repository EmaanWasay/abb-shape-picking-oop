"""
Puts all the parts together and starts the threads.

This is the only place where objects are created and connected; every
other class receives what it needs in its constructor.
"""
from __future__ import annotations

import queue
import subprocess
import threading
import time
from typing import Optional

from .annotator import FrameAnnotator
from .aruco import ArucoLocator
from .camera import BaslerCamera, Camera
from .color import ColorClassifier
from .config import Config
from .controller import PickController
from .detector import ShapeDetector, YoloShapeDetector
from .orientation import OrientationEstimator, PlacementPlanner
from .robot_server import RobotServer
from .store import ResultStore
from .translator import CoordinateTranslator
from .web_gui import WebGui
from .workers import InferenceWorker, TranslationWorker


class ShapePickingSystem:
    """The whole Raspberry Pi program.

    Threads (one per required function):
      1. InferenceWorker   - camera + AI inference
      2. TranslationWorker - pixel -> work object coordinates (+ picture for the GUI)
      3. RobotServer       - communication with the robot
      4. WebGui            - the graphical user interface
    """

    def __init__(self, config: Config, camera: Optional[Camera] = None,
                 detector: Optional[ShapeDetector] = None):
        self.config = config
        self.camera = camera or BaslerCamera(config.exposure_us)
        self.detector = detector or YoloShapeDetector(
            config, ColorClassifier(config), OrientationEstimator(config))

        self.store = ResultStore()
        self.robot = RobotServer(config.robot_host, config.robot_port, config.robot_timeout_s)
        self.controller = PickController(self.store, self.robot, config)
        self.gui = WebGui(self.store, self.controller, self.robot, config)

        self._stop_event = threading.Event()
        frames = queue.Queue(maxsize=1)            # newest picture only
        self.inference_worker = InferenceWorker(
            self.camera, self.detector, frames, config, self._stop_event)
        self.translation_worker = TranslationWorker(
            frames, ArucoLocator(config),
            CoordinateTranslator(config, PlacementPlanner(config)),
            FrameAnnotator(config), self.store, config, self._stop_event)

    def start(self) -> None:
        self.detector.load()
        self.camera.open()
        self.robot.start()
        self.inference_worker.start()
        self.translation_worker.start()
        self.gui.start()
        self._print_addresses()

    def stop(self) -> None:
        self._stop_event.set()
        self.inference_worker.join(timeout=3)
        self.translation_worker.join(timeout=3)
        self.camera.close()
        print("Stopped.")

    def run(self) -> None:
        """Start everything and keep running until Ctrl+C."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def _print_addresses(self) -> None:
        try:
            out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3)
            ips = [ip for ip in out.stdout.split() if "." in ip]
        except Exception:
            ips = []

        port = self.config.web_port
        print("\n" + "=" * 60)
        print("Web page:")
        print(f"   on this Pi:  http://localhost:{port}")
        for ip in ips:
            print(f"   from the PC: http://{ip}:{port}")
        if ips:
            print("Robot: SocketConnect in RAPID must use the 192.168.125.x address above.")
        print("Start the robot program now.")
        print("=" * 60 + "\n")
