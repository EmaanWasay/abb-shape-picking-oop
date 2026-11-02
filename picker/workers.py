"""
The two vision threads.

  InferenceWorker   (thread 1): camera picture -> AI inference -> detections
  TranslationWorker (thread 2): detections -> ArUco -> work object coordinates
                                -> annotated picture for the GUI

They are linked by a queue that only keeps the newest picture, so the
coordinate thread never works on an old frame.
"""
from __future__ import annotations

import queue
import threading
import time

import cv2

from .annotator import FrameAnnotator
from .aruco import ArucoLocator
from .camera import Camera
from .config import Config
from .detector import ShapeDetector
from .models import FrameResult, InferenceResult
from .store import ResultStore
from .translator import CoordinateTranslator


def put_newest(q: queue.Queue, item) -> None:
    """Put item in a size-1 queue, replacing anything older that is still there."""
    try:
        q.get_nowait()
    except queue.Empty:
        pass
    q.put(item)


class InferenceWorker(threading.Thread):
    """Thread 1 - AI inference: grabs a picture and runs the shape model on it."""

    def __init__(self, camera: Camera, detector: ShapeDetector, output: queue.Queue,
                 config: Config, stop_event: threading.Event):
        super().__init__(name="InferenceWorker", daemon=True)
        self._camera = camera
        self._detector = detector
        self._output = output
        self._max_ms = config.max_inference_ms
        self._stop_event = stop_event

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                image = self._camera.grab()
                if image is None:
                    continue
                detections, inference_ms = self._detector.detect(image)
                speed = "OK" if inference_ms <= self._max_ms else "TOO SLOW - limit is 3 s"
                print(f"AI inference time: {inference_ms:.0f} ms ({speed})")
                put_newest(self._output, InferenceResult(image, detections, inference_ms))
            except Exception as e:
                print(f"Inference error: {e}")
                time.sleep(0.1)


class TranslationWorker(threading.Thread):
    """Thread 2 - coordinate translation: finds the marker, converts every shape
    to work object coordinates and draws the picture for the GUI."""

    def __init__(self, inbox: queue.Queue, locator: ArucoLocator,
                 translator: CoordinateTranslator, annotator: FrameAnnotator,
                 store: ResultStore, config: Config, stop_event: threading.Event):
        super().__init__(name="TranslationWorker", daemon=True)
        self._inbox = inbox
        self._locator = locator
        self._translator = translator
        self._annotator = annotator
        self._store = store
        self._print_every_s = config.print_every_s
        self._stop_event = stop_event
        self._last_print = 0.0

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._inbox.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._store.update(self.process(item))
            except Exception as e:
                print(f"Coordinate error: {e}")

    def process(self, item: InferenceResult) -> FrameResult:
        """Everything this thread does with one picture."""
        marker = self._locator.locate(item.image)
        objects = self._translator.locate(item.detections, marker)

        display = self._annotator.draw(item.image, marker, objects, item.detections, item.inference_ms)
        ok, buf = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 80])

        if time.time() - self._last_print >= self._print_every_s:
            self._last_print = time.time()
            self._print(marker, objects)

        return FrameResult(objects=objects, marker=marker, inference_ms=item.inference_ms,
                           jpeg=buf.tobytes() if ok else None)

    @staticmethod
    def _print(marker, objects) -> None:
        if marker is None:
            print("   ArUco NOT found - no positions")
            return
        print(f"   ArUco found | scale {marker.px_per_mm:.2f} px/mm | {len(objects)} shapes:")
        for o in objects:
            print(f"   {o.label:20s} X={o.x_mm:7.1f}  Y={o.y_mm:7.1f} mm  "
                  f"angle={o.angle_deg:6.1f}  turn={o.rotation_deg:6.1f}  size {o.size_mm:.0f} mm")
