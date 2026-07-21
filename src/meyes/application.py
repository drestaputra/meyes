"""Application composition root."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from meyes.bindings.repository import BindingProfileRepository
from meyes.camera.opencv_camera import OpenCVCameraBackend
from meyes.config.manager import ConfigManager
from meyes.ui.main_window import MainWindow
from meyes.util.logging import get_logger, setup_logging
from meyes.util.paths import AppPaths
from meyes.vision.face_landmarker import MediaPipeFaceLandmarker
from meyes.vision.hand_landmarker import MediaPipeHandLandmarker


def run(argv: Sequence[str] | None = None) -> int:
    """Configure and run the Qt application."""
    app_paths = AppPaths.for_user()
    config_manager = ConfigManager(app_paths)
    config_result = config_manager.load()
    setup_logging(app_paths, config_result.config.app.log_level)
    logger = get_logger("APP")

    logger.info("application_start", extra={"schema_version": config_result.config.schema_version})
    if config_result.warning:
        logger.warning(
            "configuration_recovered",
            extra={
                "warning": config_result.warning,
                "backup": str(config_result.recovered_from or ""),
            },
        )
    profile_repository = BindingProfileRepository(app_paths)
    profile_result = profile_repository.load(config_result.config.app.active_profile)
    if profile_result.warning:
        logger.warning(
            "binding_profile_recovered",
            extra={
                "warning": profile_result.warning,
                "backup": str(profile_result.recovered_from or ""),
            },
        )

    qt_app = QApplication(list(argv) if argv is not None else sys.argv)
    qt_app.setApplicationName("Meyes")
    qt_app.setOrganizationName("Meyes")
    qt_app.setApplicationVersion("0.1.0")

    window = MainWindow(
        config_result.config,
        camera_backend=OpenCVCameraBackend(),
        face_backend_factory=MediaPipeFaceLandmarker,
        hand_backend_factory=MediaPipeHandLandmarker,
        config_manager=config_manager,
        binding_profile=profile_result.profile,
        profile_repository=profile_repository,
    )
    window.show()
    window.enable_system_tray()
    window.show_first_run_if_needed()
    exit_code = qt_app.exec()
    logger.info("application_stop", extra={"exit_code": exit_code})
    return exit_code
