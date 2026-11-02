"""Tests for the robot server and the pick controller (with a fake robot)."""
import time

import pytest

from fakes import FakeRobot, free_port
from picker.config import Config
from picker.controller import PickController
from picker.models import Detection, FrameResult, LocatedObject, MarkerPose, PickCommand
from picker.robot_server import RobotServer
from picker.store import ResultStore

CONFIG = Config()


def make_object(index, shape, color, x, y, rot=0.0):
    det = Detection(shape=shape, color=color, hsv=(0, 0, 0), centroid_px=(0, 0), angle_deg=0.0,
                    size_px=250, contour=None, confidence=0.9)
    return LocatedObject(index=index, detection=det, x_mm=x, y_mm=y, angle_deg=0.0,
                         rotation_deg=rot, size_mm=55)


@pytest.fixture
def server():
    s = RobotServer("127.0.0.1", free_port(), timeout_s=5)
    s.start()
    time.sleep(0.2)
    return s


def connect(server, reply="done"):
    robot = FakeRobot(server._port, reply)
    for _ in range(50):
        if server.connected:
            break
        time.sleep(0.02)
    return robot


def test_message_format():
    assert PickCommand(133.891, 18.2, 1, -34.25).to_message() == "133.89,18.20,1,-34.25"


def test_not_connected(server):
    assert server.send_and_wait("1,2,3,4") == {"ok": False, "error": "Robot not connected"}


def test_done_reply(server):
    robot = connect(server)
    assert server.send_and_wait("1.00,2.00,3,4.00")["ok"] is True
    assert server.send_and_wait("5.00,6.00,1,0.00")["ok"] is True       # second cycle
    assert robot.received == ["1.00,2.00,3,4.00", "5.00,6.00,1,0.00"]


def test_error_reply(server):
    connect(server, reply="error")
    result = server.send_and_wait("999,999,1,0")
    assert result["ok"] is False and "refused" in result["error"]


def test_quit(server):
    robot = connect(server)
    assert server.send_quit() == {"ok": True}
    time.sleep(0.3)
    assert robot.received[-1] == "quit"
    assert not server.connected


@pytest.fixture
def controller(server):
    store = ResultStore()
    marker = MarkerPose(center_px=(0, 0), angle_deg=0.0, px_per_mm=4.7, corners=None)
    store.update(FrameResult(objects=[make_object(0, "triangle", "red", 133.9, 18.2, -34.2),
                                      make_object(1, "circle", "blue", 157.2, 393.1)],
                             marker=marker, inference_ms=420))
    return PickController(store, server, CONFIG), server


def test_colour_counts(controller):
    ctrl, _ = controller
    assert ctrl.color_counts() == [("red", 1), ("blue", 1)]    # in the order of Config.colors


def test_pick_sends_work_object_coordinates(controller):
    ctrl, server = controller
    robot = connect(server)
    result = ctrl.pick(0, "[1] red triangle", "red")
    assert result["ok"] is True
    assert robot.received == ["133.90,18.20,1,-34.20"]


def test_wrong_colour_is_refused(controller):
    ctrl, server = controller
    robot = connect(server)
    result = ctrl.pick(1, "[2] blue circle", "red")
    assert result == {"ok": False, "error": "That shape is not red"}
    assert robot.received == []


def test_changed_list_is_refused(controller):
    ctrl, _ = controller
    assert ctrl.pick(0, "[1] green square")["error"] == "Shapes changed - select again"
    assert ctrl.pick(7)["error"] == "Invalid shape selection"


def test_no_marker_is_refused(server):
    store = ResultStore()
    store.update(FrameResult(objects=[make_object(0, "circle", "red", 1, 2)], marker=None))
    assert PickController(store, server, CONFIG).pick(0)["error"] == "ArUco not detected"
