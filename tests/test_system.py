"""End-to-end test: the whole program with a fake camera, model and robot."""
import dataclasses
import time

import pytest

from fakes import FakeCamera, FakeRobot, FakeYoloModel, free_port
from picker.color import ColorClassifier
from picker.config import Config
from picker.detector import YoloShapeDetector
from picker.orientation import OrientationEstimator
from picker.system import ShapePickingSystem


@pytest.fixture(scope="module")
def system():
    config = dataclasses.replace(Config(), robot_host="127.0.0.1", robot_port=free_port(),
                                 web_port=free_port(), print_every_s=60)
    detector = YoloShapeDetector(config, ColorClassifier(config), OrientationEstimator(config),
                                 model=FakeYoloModel())
    s = ShapePickingSystem(config, camera=FakeCamera(), detector=detector)
    s.start()
    for _ in range(100):                       # wait for the first processed frame
        if s.store.latest().jpeg is not None:
            break
        time.sleep(0.05)
    yield s
    s.stop()


def test_threads_are_running(system):
    names = {t.name for t in __import__("threading").enumerate()}
    assert {"InferenceWorker", "TranslationWorker", "RobotServer", "WebGui"} <= names


def test_frame_has_objects_and_inference_time(system):
    frame = system.store.latest()
    assert frame.marker is not None
    assert len(frame.objects) == 4
    assert frame.inference_ms > 0
    assert frame.jpeg[:2] == b"\xff\xd8"       # a JPEG picture


def test_web_status(system):
    client = system.gui.app.test_client()
    data = client.get("/api/status").get_json()
    assert len(data["shapes"]) == 4
    assert {c["name"]: c["count"] for c in data["colors"]} == {"red": 2, "blue": 1, "green": 1}
    assert data["infer_ms"] >= 0
    assert data["aruco_found"] is True
    assert b'id="colorSelect"' in client.get("/").data


def test_pick_through_the_web_page(system):
    robot = FakeRobot(system.config.robot_port)
    for _ in range(50):
        if system.robot.connected:
            break
        time.sleep(0.02)
    client = system.gui.app.test_client()
    shapes = client.get("/api/status").get_json()["shapes"]
    red = next(s for s in shapes if s["color"] == "red")
    result = client.post("/api/send", json={"index": red["index"], "label": red["label"],
                                            "color": "red"}).get_json()
    assert result["ok"] is True
    x, y, shape_id, rotation = robot.received[0].split(",")
    assert float(x) == pytest.approx(red["x"], abs=0.06)
    assert float(y) == pytest.approx(red["y"], abs=0.06)
    robot.close()
