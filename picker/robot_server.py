"""
Server communication with the ABB robot.

The robot is the client: it connects to this server, says "ready", receives
"x,y,shapeID,rotation" and answers "done" (or "error") after placing.
"""
from __future__ import annotations

import queue
import socket
import threading
import time


class RobotServer:
    """TCP server the robot connects to.

    One thread (started by start()) is the ONLY place that reads from the
    robot socket; everything it receives goes into an inbox queue.
    send_and_wait() sends a command and waits in that inbox for "done".
    """

    def __init__(self, host: str, port: int, timeout_s: float):
        self._host = host
        self._port = port
        self._timeout_s = timeout_s

        self._conn = None
        self._conn_lock = threading.Lock()     # protects self._conn
        self._send_lock = threading.Lock()     # one command at a time
        self._inbox = queue.Queue()            # messages from the robot
        self._busy = False

    # ----- status for the GUI -----
    @property
    def connected(self) -> bool:
        with self._conn_lock:
            return self._conn is not None

    @property
    def busy(self) -> bool:
        return self._busy

    # ----- thread -----
    def start(self) -> None:
        threading.Thread(target=self._run, name="RobotServer", daemon=True).start()

    def _run(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self._host, self._port))
        except OSError as e:
            print(f"\n*** Cannot open port {self._port}: {e}")
            print("*** Is the program already running? Close it and start again.\n")
            return
        server.listen(1)
        print(f"Robot server listening on port {self._port}")

        while True:
            print("Waiting for robot to connect...")
            conn, addr = server.accept()
            conn.settimeout(None)
            self._clear_inbox()                # forget messages from an old connection
            with self._conn_lock:
                self._conn = conn
            print(f"Robot connected from {addr[0]}")
            self._read_until_closed(conn)

    def _read_until_closed(self, conn: socket.socket) -> None:
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break                      # robot closed the connection
                message = data.decode("latin-1").strip()
                if message:
                    print(f"Robot says: {message}")
                    self._inbox.put(message)
        except OSError as e:
            print(f"Robot connection error: {e}")
        finally:
            with self._conn_lock:
                self._conn = None
            try:
                conn.close()
            except OSError:
                pass
            self._inbox.put(None)              # wake up anyone waiting for "done"
            print("Robot disconnected.")

    # ----- commands -----
    def send_and_wait(self, message: str) -> dict:
        """Send one command and wait until the robot answers "done"."""
        if not self._send_lock.acquire(blocking=False):
            return {"ok": False, "error": "Robot is busy"}
        try:
            with self._conn_lock:
                conn = self._conn
            if conn is None:
                return {"ok": False, "error": "Robot not connected"}

            self._busy = True
            self._clear_inbox()                # ignore old "ready" messages
            conn.sendall(message.encode("ascii"))
            print(f"Sent to robot: {message}")
            return self._wait_for_done()
        except OSError as e:
            return {"ok": False, "error": str(e)}
        finally:
            self._busy = False
            self._send_lock.release()

    def send_quit(self) -> dict:
        """Tell the robot to go home and stop its program."""
        if not self._send_lock.acquire(blocking=False):
            return {"ok": False, "error": "Robot is busy"}
        try:
            with self._conn_lock:
                conn = self._conn
            if conn is None:
                return {"ok": False, "error": "Robot not connected"}
            conn.sendall(b"quit")
            print("Sent to robot: quit")
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": str(e)}
        finally:
            self._send_lock.release()

    def _wait_for_done(self) -> dict:
        deadline = time.time() + self._timeout_s
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return {"ok": False, "error": "Timeout waiting for robot"}
            try:
                message = self._inbox.get(timeout=remaining)
            except queue.Empty:
                return {"ok": False, "error": "Timeout waiting for robot"}

            if message is None:
                return {"ok": False, "error": "Robot disconnected"}
            if "done" in message:
                return {"ok": True, "response": "done"}
            if "error" in message:
                return {"ok": False, "error": "Robot refused the command - see the FlexPendant for the reason"}
            # "ready" or anything else: keep waiting

    def _clear_inbox(self) -> None:
        while not self._inbox.empty():
            try:
                self._inbox.get_nowait()
            except queue.Empty:
                break
