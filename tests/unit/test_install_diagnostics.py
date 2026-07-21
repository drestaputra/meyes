"""Safe installed-artifact command diagnostics."""

from __future__ import annotations

import json

import pytest

from meyes.__main__ import main
from meyes.install_diagnostics import collect_install_diagnostics


def test_version_command_does_not_start_application(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert "MEYES 0.1.0" in capsys.readouterr().out


def test_install_diagnostics_verify_platform_python_and_models() -> None:
    result = collect_install_diagnostics()

    assert result["overall_pass"] is True
    assert result["supported_python"] is True
    assert result["supported_platform"] is True
    assert [model["verified"] for model in result["models"]] == [True, True]


def test_diagnostic_command_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--diagnose-install"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_pass"] is True
    assert "No GUI, camera" in payload["safety"]
