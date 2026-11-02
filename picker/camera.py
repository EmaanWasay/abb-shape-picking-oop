"""
Camera access.

The rest of the program only uses the Camera interface, so another camera
(or a fake one for testing) can be used without changing any other file.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import cv2
import numpy as np


class Camera(ABC):
    """Anything that can deliver BGR pictures."""

    @abstractmethod
    def open(self) -> None:
        """Connect to the camera and start grabbing."""

    @abstractmethod
    def grab(self) -> Optional[np.ndarray]:
        """Return the newest picture (BGR), or None if grabbing failed."""

    @abstractmethod
    def close(self) -> None:
        """Stop grabbing and release the camera."""


class BaslerCamera(Camera):
    """Basler USB camera, accessed through pypylon."""

    def __init__(self, exposure_us: float):
        self._exposure_us = exposure_us
        self._pylon = None
        self._camera = None
        self._converter = None

    def open(self) -> None:
        # Imported here so the rest of the program can run (and be tested)
        # on a computer without the Basler software.
        from pypylon import pylon
        self._pylon = pylon

        try:
            self._camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        except Exception as e:
            raise SystemExit(f"Basler camera not found ({e}). Check the USB cable.")

        self._camera.Open()
        self._camera.ExposureTime.SetValue(self._exposure_us)
        self._camera.PixelFormat.SetValue("RGB8")

        self._converter = pylon.ImageFormatConverter()
        self._converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        self._converter.OutputBitAlignment.Value = "MsbAligned"

        print(f"Camera: {self._camera.GetDeviceInfo().GetModelName()}")
        self._camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    def grab(self) -> Optional[np.ndarray]:
        result = self._camera.RetrieveResult(5000, self._pylon.TimeoutHandling_ThrowException)
        try:
            if not result.GrabSucceeded():
                return None
            rgb = self._converter.Convert(result).GetArray()
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        finally:
            result.Release()

    def close(self) -> None:
        try:
            if self._camera is not None:
                self._camera.StopGrabbing()
                self._camera.Close()
        except Exception:
            pass
