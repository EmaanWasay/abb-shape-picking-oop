"""The link between the GUI and the robot: what may be picked, and picking it."""
from __future__ import annotations

from .config import Config
from .models import LocatedObject, PickCommand
from .robot_server import RobotServer
from .store import ResultStore


class PickController:
    """Turns a choice on the GUI into a pick command for the robot.

    The GUI only talks to this class - it never talks to the robot server
    or the vision classes directly.
    """

    def __init__(self, store: ResultStore, robot: RobotServer, config: Config):
        self._store = store
        self._robot = robot
        self._shape_ids = config.shape_ids
        self._colors = config.colors

    def color_counts(self) -> list:
        """Colours on the sheet right now, e.g. [("red", 2), ("blue", 1)]."""
        objects = self._store.latest().objects
        counts = [(c, sum(1 for o in objects if o.color == c)) for c in self._colors]
        return [(c, n) for c, n in counts if n > 0]

    def pick(self, index, label: str = "", color: str = "any") -> dict:
        """Pick the object with this index, if it is still there and has the chosen colour."""
        frame = self._store.latest()
        if frame.marker is None:
            return {"ok": False, "error": "ArUco not detected"}
        if not isinstance(index, int) or not 0 <= index < len(frame.objects):
            return {"ok": False, "error": "Invalid shape selection"}

        obj = frame.objects[index]
        if label and label != obj.label:
            return {"ok": False, "error": "Shapes changed - select again"}
        if color not in (None, "", "any") and obj.color != color:
            return {"ok": False, "error": f"That shape is not {color}"}

        command = self.make_command(obj)
        print(f"Picking {obj.color} {obj.shape} at X={obj.x_mm:.1f} Y={obj.y_mm:.1f} "
              f"(colour choice: {color}) | AI inference time: {frame.inference_ms:.0f} ms")
        result = self._robot.send_and_wait(command.to_message())
        result["sent"] = command.to_message()
        return result

    def make_command(self, obj: LocatedObject) -> PickCommand:
        return PickCommand(x_mm=obj.x_mm, y_mm=obj.y_mm,
                           shape_id=self._shape_ids[obj.shape],
                           rotation_deg=obj.rotation_deg)

    def quit_robot(self) -> dict:
        return self._robot.send_quit()
