#!/usr/bin/env python3
"""
Vision server for the ABB shape pick-and-place (runs on the Raspberry Pi).
Group 1: circle, square and triangle.

Run:
    python3 main.py

Then open the web page (the address is printed) and start the robot program.
All settings are in picker/config.py.
"""
from picker.config import Config
from picker.system import ShapePickingSystem


def main() -> None:
    ShapePickingSystem(Config()).run()


if __name__ == "__main__":
    main()
