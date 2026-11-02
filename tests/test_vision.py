"""Tests for detection, colours, orientation and coordinate translation."""
import pytest

from fakes import MARKER_CENTER, PX_PER_MM, FakeYoloModel, make_scene_image
from picker.aruco import ArucoLocator
from picker.color import ColorClassifier
from picker.config import Config
from picker.detector import YoloShapeDetector
from picker.models import MarkerPose
from picker.orientation import OrientationEstimator, PlacementPlanner
from picker.translator import CoordinateTranslator

CONFIG = Config()


@pytest.fixture(scope="module")
def scene():
    image = make_scene_image()
    detector = YoloShapeDetector(CONFIG, ColorClassifier(CONFIG), OrientationEstimator(CONFIG),
                                 model=FakeYoloModel())
    detections, inference_ms = detector.detect(image)
    marker = ArucoLocator(CONFIG).locate(image)
    return image, detections, inference_ms, marker


def test_inference_time_is_measured(scene):
    _, _, inference_ms, _ = scene
    assert 15 < inference_ms < 1000           # the fake model sleeps 20 ms


def test_only_group_1_shapes_are_detected(scene):
    _, detections, _, _ = scene
    assert {d.shape for d in detections} <= {"circle", "square", "triangle"}
    assert len(detections) == 5               # hexagon skipped; magnet still here (size filter comes later)


def test_colours_are_named(scene):
    _, detections, _, _ = scene
    named = sorted((d.color, d.shape) for d in detections if d.size_px > 100)
    assert named == [("blue", "circle"), ("green", "circle"), ("red", "square"), ("red", "triangle")]


def test_marker_scale_uses_101_mm(scene):
    _, _, _, marker = scene
    assert marker.px_per_mm == pytest.approx(PX_PER_MM, rel=0.01)
    assert marker.center_px[0] == pytest.approx(MARKER_CENTER[0], abs=2)


def test_magnet_is_filtered_by_size(scene):
    _, detections, _, marker = scene
    objects = CoordinateTranslator(CONFIG, PlacementPlanner(CONFIG)).locate(detections, marker)
    assert len(objects) == 4
    assert all(35 <= o.size_mm <= 90 for o in objects)
    assert [o.index for o in objects] == [0, 1, 2, 3]


def test_marker_centre_maps_to_configured_position():
    marker = MarkerPose(center_px=(1000, 800), angle_deg=0.0, px_per_mm=5.0, corners=None)
    t = CoordinateTranslator(CONFIG, PlacementPlanner(CONFIG))
    assert t.to_work_object((1000, 800), marker) == pytest.approx((CONFIG.marker_x_mm, CONFIG.marker_y_mm))


def test_picture_down_is_robot_x_and_right_is_robot_y():
    marker = MarkerPose(center_px=(1000, 800), angle_deg=0.0, px_per_mm=5.0, corners=None)
    t = CoordinateTranslator(CONFIG, PlacementPlanner(CONFIG))
    x, y = t.to_work_object((1000, 800 + 500), marker)             # 100 mm down
    assert (x, y) == pytest.approx((CONFIG.marker_x_mm + 100, CONFIG.marker_y_mm))
    x, y = t.to_work_object((1000 + 250, 800), marker)             # 50 mm right
    assert (x, y) == pytest.approx((CONFIG.marker_x_mm, CONFIG.marker_y_mm + 50))


def test_marker_rotation_is_removed():
    # Marker turned 90 degrees: a point "right" of it in the picture is "down" in the marker's frame
    marker = MarkerPose(center_px=(1000, 800), angle_deg=90.0, px_per_mm=5.0, corners=None)
    t = CoordinateTranslator(CONFIG, PlacementPlanner(CONFIG))
    dx, dy = t.offset_from_marker_mm((1000 + 250, 800), marker)
    assert dx == pytest.approx(0, abs=1e-6)
    assert dy == pytest.approx(-50)


@pytest.mark.parametrize("shape, angle, expected", [
    ("circle", 37.0, 0.0),
    ("square", 10.0, -10.0),
    ("square", 80.0, 10.0),            # shortest way round
    ("triangle", 90.0, 0.0),
    ("triangle", 30.0, 60.0),
    ("triangle", 20.0, -50.0),
])
def test_placement_rotation(shape, angle, expected):
    assert PlacementPlanner(CONFIG).rotation(shape, angle) == pytest.approx(expected)


def test_color_names():
    c = ColorClassifier(CONFIG)
    assert c.name_of(0, 200, 200) == "red"
    assert c.name_of(60, 200, 150) == "green"
    assert c.name_of(110, 200, 200) == "blue"
    assert c.name_of(30, 30, 80) == "black"       # shiny black: grey-ish, dark
    assert c.name_of(20, 10, 200) == "white"
