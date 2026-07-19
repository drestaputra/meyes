"""Camera lifecycle state-machine tests."""

from __future__ import annotations

import pytest

from meyes.camera.models import CameraStatus
from meyes.camera.state import CameraStateMachine, InvalidCameraTransition


def test_happy_path_transitions_are_explicit() -> None:
    state = CameraStateMachine()

    state.transition(CameraStatus.STARTING)
    state.transition(CameraStatus.RUNNING)
    state.transition(CameraStatus.PAUSED)
    state.transition(CameraStatus.STARTING)
    state.transition(CameraStatus.RUNNING)
    state.transition(CameraStatus.STOPPING)
    state.transition(CameraStatus.STOPPED)

    assert state.status is CameraStatus.STOPPED


def test_invalid_transition_is_rejected() -> None:
    state = CameraStateMachine()

    with pytest.raises(InvalidCameraTransition, match=r"stopped.*running"):
        state.transition(CameraStatus.RUNNING)
