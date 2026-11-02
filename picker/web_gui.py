"""
The graphical user interface: a web page (open http://<Pi IP>:5001).

Shows the live picture with every shape's position and orientation, the AI
inference time, and lets the user choose a colour and a shape to pick.
"""
from __future__ import annotations

import logging
import threading
import time

from flask import Flask, Response, jsonify, request

from .config import Config
from .controller import PickController
from .robot_server import RobotServer
from .store import ResultStore


class WebGui:
    """Flask web page, running in its own thread."""

    def __init__(self, store: ResultStore, controller: PickController,
                 robot: RobotServer, config: Config):
        self._store = store
        self._controller = controller
        self._robot = robot
        self._config = config
        self.app = Flask(__name__)
        self._add_routes()

    def start(self) -> None:
        # Hide the line Flask prints for every request, so the inference
        # times stay readable in the terminal
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        threading.Thread(target=self._serve, name="WebGui", daemon=True).start()

    def _serve(self) -> None:
        self.app.run(host="0.0.0.0", port=self._config.web_port, threaded=True, use_reloader=False)

    # ----- routes -----
    def _add_routes(self) -> None:
        app = self.app
        app.add_url_rule("/", "index", lambda: INDEX_HTML)
        app.add_url_rule("/detection_feed", "feed", self._feed)
        app.add_url_rule("/api/status", "status", self._status)
        app.add_url_rule("/api/send", "send", self._send, methods=["POST"])
        app.add_url_rule("/api/quit", "quit", self._quit, methods=["POST"])

    def _feed(self) -> Response:
        """Live picture as a stream of JPEGs."""
        def frames():
            while True:
                jpeg = self._store.latest().jpeg
                if jpeg is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                time.sleep(0.05)
        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    def _status(self):
        frame = self._store.latest()
        return jsonify({
            "shapes": [{"index": o.index, "label": o.label, "color": o.color,
                        "x": round(o.x_mm, 1), "y": round(o.y_mm, 1),
                        "angle": round(o.angle_deg, 1)} for o in frame.objects],
            "colors": [{"name": c, "count": n} for c, n in self._controller.color_counts()],
            "infer_ms": round(frame.inference_ms),
            "max_infer_ms": self._config.max_inference_ms,
            "aruco_found": frame.marker is not None,
            "robot_connected": self._robot.connected,
            "robot_busy": self._robot.busy,
        })

    def _send(self):
        data = request.get_json(silent=True) or {}
        return jsonify(self._controller.pick(data.get("index"), data.get("label", ""),
                                             data.get("color", "any")))

    def _quit(self):
        return jsonify(self._controller.quit_robot())


INDEX_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shape Detection & Robot Control</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Arial, sans-serif; background:#1a1a1a; color:#fff;
         margin:0; padding:10px 16px; }
  h1 { color:#4CAF50; font-size:24px; margin:4px 0 10px; text-align:center; }
  .layout { display:flex; gap:16px; align-items:flex-start; justify-content:center;
            flex-wrap:wrap; }
  .feed { background:#2a2a2a; padding:6px; border-radius:8px;
          flex:1 1 700px; max-width:1400px; }
  .feed img { display:block; width:100%; height:auto; max-height:calc(100vh - 80px);
              object-fit:contain; border-radius:4px; cursor:zoom-in; }
  .hint { color:#888; font-size:13px; text-align:center; margin-top:4px; }
  .controls { background:#2a2a2a; padding:18px; border-radius:8px; flex:0 0 320px;
              font-size:18px; }
  .controls label { display:block; margin:6px 0 4px; }
  select, button { font-size:18px; padding:12px; border-radius:6px; border:none;
                   width:100%; margin:6px 0; }
  button { background:#4CAF50; color:white; cursor:pointer; }
  button.quit { background:#c0392b; }
  button:disabled { background:#555; cursor:not-allowed; }
  .info { margin-top:10px; }
  #status { margin-top:14px; font-size:16px; min-height:24px; word-wrap:break-word; }
  .ok { color:#4CAF50; }
  .bad { color:#e74c3c; }
  .busy { color:#f39c12; }
</style>
</head>
<body>
<h1>Shape Detection & Robot Control</h1>
<div class="layout">
  <div class="feed">
    <img id="video" src="/detection_feed" alt="Camera" onclick="fullScreen()">
    <div class="hint">Click the video for full screen (Esc to go back)</div>
  </div>
  <div class="controls">
    <label for="colorSelect">Colour to pick:</label>
    <select id="colorSelect" onchange="refresh(true)"><option value="any">Any colour</option></select>
    <label for="shapeSelect">Shape to pick:</label>
    <select id="shapeSelect"><option>Loading...</option></select>
    <button id="sendBtn" onclick="sendShape()">Send to Robot</button>
    <button id="quitBtn" class="quit" onclick="quitRobot()">Robot home (quit)</button>
    <div id="arucoStatus" class="info"></div>
    <div id="robotStatus" class="info"></div>
    <div id="inferStatus" class="info"></div>
    <div id="status"></div>
  </div>
</div>
<script>
let locked = false;
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

function fullScreen() {
  const v = document.getElementById('video');
  if (document.fullscreenElement) { document.exitFullscreen(); }
  else if (v.requestFullscreen) { v.requestFullscreen(); }
}

async function refresh(force) {
  const shapeSel = document.getElementById('shapeSelect');
  const colorSel = document.getElementById('colorSelect');
  if (locked) return;
  if (!force && (document.activeElement === shapeSel || document.activeElement === colorSel)) return;
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    showInfo(data);
    fillColors(data);
    fillShapes(data);
  } catch (e) {
    console.error(e);
  }
}

function showInfo(data) {
  const robot = document.getElementById('robotStatus');
  if (data.robot_busy)           { robot.textContent = 'Robot: BUSY';          robot.className = 'info busy'; }
  else if (data.robot_connected) { robot.textContent = 'Robot: Connected';     robot.className = 'info ok'; }
  else                           { robot.textContent = 'Robot: Not connected'; robot.className = 'info bad'; }

  const aruco = document.getElementById('arucoStatus');
  aruco.textContent = data.aruco_found ? 'ArUco: found' : 'ArUco: NOT found';
  aruco.className = 'info ' + (data.aruco_found ? 'ok' : 'bad');

  const inf = document.getElementById('inferStatus');
  inf.textContent = 'AI inference: ' + data.infer_ms + ' ms';
  inf.className = 'info ' + (data.infer_ms <= data.max_infer_ms ? 'ok' : 'bad');
}

// Colour list: only the colours on the sheet right now, with how many there are
function fillColors(data) {
  const sel = document.getElementById('colorSelect');
  const prev = sel.value || 'any';
  const items = [['any', 'Any colour (' + data.shapes.length + ')']];
  data.colors.forEach(c => items.push([c.name, cap(c.name) + ' (' + c.count + ')']));
  if (prev !== 'any' && !data.colors.some(c => c.name === prev)) {
    items.push([prev, cap(prev) + ' (0)']);          // keep the choice, show none are left
  }
  sel.innerHTML = '';
  items.forEach(([value, text]) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = text;
    sel.appendChild(opt);
  });
  sel.value = prev;
}

// Shape list: only shapes of the chosen colour
function fillShapes(data) {
  const sel = document.getElementById('shapeSelect');
  const color = document.getElementById('colorSelect').value;
  const shapes = data.shapes.filter(s => color === 'any' || s.color === color);
  const prev = sel.value;
  sel.innerHTML = '';
  if (shapes.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = color === 'any' ? 'No shapes detected' : 'No ' + color + ' shapes left';
    sel.appendChild(opt);
    return;
  }
  shapes.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.index;
    opt.textContent = s.label;
    sel.appendChild(opt);
  });
  if ([...sel.options].some(o => o.value === prev)) sel.value = prev;
}

async function sendShape() {
  const sel = document.getElementById('shapeSelect');
  if (sel.value === '' || sel.selectedIndex < 0) {
    setStatus('No shape selected', 'bad');
    return;
  }
  const label = sel.options[sel.selectedIndex].textContent;
  const color = document.getElementById('colorSelect').value;
  locked = true;
  document.getElementById('sendBtn').disabled = true;
  setStatus('Sent ' + label + '. Press the YELLOW button on the robot, then wait...', 'busy');
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({index: parseInt(sel.value), label: label, color: color})
    });
    const data = await res.json();
    if (data.ok) setStatus('Done! Sent: ' + data.sent + ' | Robot: ' + data.response, 'ok');
    else         setStatus('Error: ' + data.error, 'bad');
  } catch (e) {
    setStatus('Request failed: ' + e, 'bad');
  } finally {
    locked = false;
    document.getElementById('sendBtn').disabled = false;
  }
}

async function quitRobot() {
  if (!confirm('Send the robot home and stop the robot program?')) return;
  const res = await fetch('/api/quit', {method: 'POST'});
  const data = await res.json();
  setStatus(data.ok ? 'Robot told to quit.' : 'Error: ' + data.error, data.ok ? 'ok' : 'bad');
}

function setStatus(msg, cls) {
  const s = document.getElementById('status');
  s.className = cls;
  s.textContent = msg;
}

setInterval(refresh, 1000);
refresh(true);
</script>
</body>
</html>
"""
