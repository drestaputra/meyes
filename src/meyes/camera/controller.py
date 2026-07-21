"""Qt bridge between the camera worker and responsive UI."""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QImage

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.interface import CameraBackend
from meyes.camera.metrics import FrameRateMeter
from meyes.camera.models import CameraDevice, CameraHealth, CameraOptions, CameraStatus, FramePacket
from meyes.camera.worker import CameraShutdownError, CameraWorker
from meyes.config.models import CameraSettings
from meyes.util.logging import get_logger


class CameraController(QObject):
    """Coordinate background capture, device discovery, and preview polling."""

    devices_changed = Signal(object)
    device_scan_changed = Signal(bool)
    device_scan_failed = Signal(str)
    health_changed = Signal(object)
    preview_changed = Signal(QImage)
    preview_fps_changed = Signal(float)
    settings_changed = Signal(object)

    def __init__(
        self,
        backend: CameraBackend,
        settings: CameraSettings,
        *,
        preview_interval_ms: int = 66,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = backend
        self._settings = settings
        self._frame_buffer = LatestFrameBuffer()
        self._preview_interval_ms = preview_interval_ms
        self._worker: CameraWorker | None = None
        self._last_preview_sequence = 0
        self._preview_fps = FrameRateMeter(window_size=30)
        self._enumeration_thread: threading.Thread | None = None
        self._shutting_down = threading.Event()
        self._logger = get_logger("CAMERA")

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(preview_interval_ms)
        self._preview_timer.timeout.connect(self._publish_latest_preview)

    @property
    def settings(self) -> CameraSettings:
        """Return the current persisted camera preferences."""
        return self._settings

    @property
    def frame_buffer(self) -> LatestFrameBuffer:
        """Expose raw, unmirrored frames to the vision pipeline."""
        return self._frame_buffer

    @property
    def status(self) -> CameraStatus:
        """Return the worker status or stopped when no worker exists."""
        if self._worker is None:
            return CameraStatus.STOPPED
        return self._worker.status

    @Slot()
    def refresh_devices(self) -> None:
        """Enumerate cameras outside the Qt main thread."""
        if self._enumeration_thread is not None and self._enumeration_thread.is_alive():
            return
        self._shutting_down.clear()
        self.device_scan_changed.emit(True)
        self._enumeration_thread = threading.Thread(
            target=self._enumerate_devices,
            name="meyes-camera-enumeration",
            daemon=True,
        )
        self._enumeration_thread.start()

    @Slot(int)
    def select_camera(self, camera_index: int) -> None:
        """Persist a new camera choice while capture is stopped."""
        if camera_index < 0 or camera_index == self._settings.camera_index:
            return
        if self.status is not CameraStatus.STOPPED:
            raise RuntimeError("Stop camera capture before changing devices")
        self._settings = self._settings.model_copy(update={"camera_index": camera_index})
        self.settings_changed.emit(self._settings)

    @Slot(bool)
    def set_mirror(self, enabled: bool) -> None:
        """Change preview mirroring without modifying processing frames."""
        if enabled == self._settings.mirror:
            return
        self._settings = self._settings.model_copy(update={"mirror": enabled})
        self.settings_changed.emit(self._settings)

    @Slot(object)
    def apply_settings(self, payload: object) -> None:
        """Replace validated capture settings only while the camera is stopped."""

        if not isinstance(payload, CameraSettings):
            raise TypeError("Expected CameraSettings")
        if self.status is not CameraStatus.STOPPED:
            raise RuntimeError("Stop camera capture before changing capture settings")
        if payload == self._settings:
            return
        self._settings = payload
        self.settings_changed.emit(self._settings)

    @Slot()
    def start(self) -> None:
        """Start capture with current settings."""
        if self._worker is not None and self._worker.status is not CameraStatus.STOPPED:
            return
        options = CameraOptions(
            camera_index=self._settings.camera_index,
            width=self._settings.width,
            height=self._settings.height,
            target_fps=self._settings.target_fps,
        )
        self._worker = CameraWorker(
            self._backend,
            options,
            frame_buffer=self._frame_buffer,
            health_callback=self._on_worker_health,
        )
        self._last_preview_sequence = 0
        self._preview_fps.reset()
        self._preview_timer.start(self._preview_interval_ms)
        self._worker.start()

    @Slot()
    def pause(self) -> None:
        """Pause capture and preview publication."""
        if self._worker is None:
            return
        self._worker.pause()
        self._preview_timer.stop()

    @Slot()
    def resume(self) -> None:
        """Resume a paused capture."""
        if self._worker is None:
            return
        self._preview_fps.reset()
        self._worker.resume()
        self._preview_timer.start(self._preview_interval_ms)

    @Slot()
    def stop(self) -> None:
        """Stop capture, clear preview timing, and publish stopped health."""
        self._preview_timer.stop()
        self._preview_fps.reset()
        self.preview_fps_changed.emit(0.0)
        worker, self._worker = self._worker, None
        if worker is None:
            return
        try:
            worker.stop()
        except CameraShutdownError as error:
            self._logger.exception("camera_shutdown_timeout")
            self.device_scan_failed.emit(str(error))

    def shutdown(self, timeout: float = 4.0) -> None:
        """Stop capture and wait briefly for explicit device discovery."""
        self._shutting_down.set()
        self.stop()
        enumeration_thread = self._enumeration_thread
        if enumeration_thread is not None and enumeration_thread.is_alive():
            enumeration_thread.join(timeout=timeout)
            if enumeration_thread.is_alive():
                self._logger.warning("camera_enumeration_shutdown_timeout")
        self._enumeration_thread = None

    def _enumerate_devices(self) -> None:
        try:
            devices = self._backend.enumerate_devices(max_index=8)
        except Exception as error:
            self._logger.exception("camera_enumeration_failed")
            if not self._shutting_down.is_set():
                self.device_scan_failed.emit(str(error))
        else:
            if not self._shutting_down.is_set():
                self.devices_changed.emit(devices)
        finally:
            if not self._shutting_down.is_set():
                self.device_scan_changed.emit(False)

    def _on_worker_health(self, health: CameraHealth) -> None:
        self.health_changed.emit(health)

    @Slot()
    def _publish_latest_preview(self) -> None:
        worker = self._worker
        if worker is None:
            return
        packet = worker.frame_buffer.latest()
        if packet is None or packet.sequence <= self._last_preview_sequence:
            return
        self._last_preview_sequence = packet.sequence
        image = self._to_qimage(packet)
        self.preview_changed.emit(image)
        self.preview_fps_changed.emit(self._preview_fps.tick(time.monotonic()))

    def _to_qimage(self, packet: FramePacket) -> QImage:
        rgb = cv2.cvtColor(packet.frame, cv2.COLOR_BGR2RGB)
        if self._settings.mirror:
            rgb = np.ascontiguousarray(rgb[:, ::-1])
        height, width, channels = rgb.shape
        bytes_per_line = width * channels
        return QImage(
            rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()


def camera_device_list(value: object) -> list[CameraDevice]:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, list) or not all(isinstance(item, CameraDevice) for item in value):
        raise TypeError("Expected a list of CameraDevice values")
    return value


def camera_health(value: object) -> CameraHealth:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, CameraHealth):
        raise TypeError("Expected CameraHealth")
    return value
