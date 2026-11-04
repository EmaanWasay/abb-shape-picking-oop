# ABB shape pick-and-place - Basler Vision

A Raspberry Pi 4 with a Basler camera finds **circles, squares and triangles**
with a trained YOLO segmentation model, converts their positions into the
robot's work object coordinates, and sends them to an ABB robot that picks
each shape and places it in its slot with the correct orientation.

## Run

```bash
bash setup_pi.sh        # only once on a new Pi (installs everything, ~15 min)
bash run.sh             # start the program
```

Then open the web page:

* on the Pi itself: `http://localhost:5001`
* from the PC: `http://<Pi IP>:5001` (the address is printed at start-up)

Start the Python program first, then the robot program.

## Files

```
main.py                    starts the program
picker/
  config.py                ALL settings (marker size and position, IPs, colours, ...)
  models.py                data classes passed between the parts
  camera.py                Camera interface + BaslerCamera
  detector.py              ShapeDetector interface + YoloShapeDetector (timed AI inference)
  color.py                 ColorClassifier (white balance + colour names)
  orientation.py           OrientationEstimator (shape angle) + PlacementPlanner (wrist turn)
  aruco.py                 ArucoLocator (reference marker: centre, angle, px per mm)
  translator.py            CoordinateTranslator (pixel -> X/Y in work object "white")
  annotator.py             FrameAnnotator (draws the results on the picture)
  store.py                 ResultStore (thread-safe newest result)
  robot_server.py          RobotServer (TCP server, the robot is the client)
  controller.py            PickController (GUI choice -> pick command)
  workers.py               InferenceWorker + TranslationWorker (threads)
  web_gui.py               WebGui (Flask web page)
  system.py                ShapePickingSystem (creates and connects everything)
robot/
  MainModule.mod           RAPID pick-and-place program
  ServerCommuncatio.sys    RAPID socket client
tests/                     tests with a fake camera, model and robot
best_ncnn_model/           the trained AI model
```

## Threads

| Thread | Class | Job |
|---|---|---|
| 1 | `InferenceWorker` | grabs a picture, runs the AI model, **prints the inference time** |
| 2 | `TranslationWorker` | finds the ArUco marker, converts pixels to work object X/Y, draws the picture |
| 3 | `RobotServer` | communication with the robot |
| 4 | `WebGui` | the graphical user interface |

Threads 1 and 2 are linked by a queue that only keeps the newest picture.
Thread 2 writes its result to the `ResultStore`, which the GUI reads.

## Design (object-oriented)

* **One job per class** – e.g. `ColorClassifier` only names colours,
  `CoordinateTranslator` only converts coordinates, `RobotServer` only talks
  to the robot.
* **Interfaces** – `Camera` and `ShapeDetector` are abstract classes. The rest
  of the program only uses these interfaces, so the camera or the model can be
  replaced without changing other files (the tests use a fake camera and a
  fake model this way).
* **Dependencies are passed in** – every class gets what it needs in its
  constructor. Objects are only created in `ShapePickingSystem`.
* **Settings in one place** – `Config` (read-only data class).
* **Data classes** – `Detection`, `MarkerPose`, `LocatedObject`, `PickCommand`,
  `FrameResult` carry the data between the parts.

## Message to the robot

```
x,y,shapeID,rotation        e.g.  133.89,18.20,1,-34.25
```

* `x, y` – pick position in mm in work object `white`
* `shapeID` – 1 = triangle, 2 = circle, 3 = square
* `rotation` – wrist turn in degrees at the slot

The robot answers `done` after placing, or `error` if it refuses the command
(for example a position outside the sheet).

## Coordinate translation

1. The ArUco marker (101 mm) gives the scale in pixels per mm and its angle.
2. The shape's centre is measured from the marker centre and turned into the
   marker's axes.
3. The marker centre's position in work object `white` (measured by jogging the
   robot to it) is added: down in the picture is +X, right is +Y.

## Exam-day checklist

1. Re-teach `tsuc`, `white`, `empty` and the robot targets if the bench is different. (However the tsuc the suction cup tool is already calibrated / saved on mainmodule code)
2. Jog the cup to the middle of the marker (Work object = white) and put X/Y in
   `marker_x_mm` / `marker_y_mm` in `picker/config.py`.
3. Check the Pi's 192.168.125.x (.207 for my case) address (`hostname -I`) matches `SocketConnect` in RAPID.
4. Make the Pack-and-Go of the robot station before leaving.

## Tests

```bash
pip install pytest
python3 -m pytest tests
```
