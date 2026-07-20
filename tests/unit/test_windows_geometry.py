from __future__ import annotations

import pytest

from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.cursor.windows_geometry import WindowsPrimaryScreenGeometryProvider


class _FakeGeometryApi:
    def __init__(
        self,
        rect: tuple[int, int, int, int] = (0, 0, 1920, 1080),
        *,
        query_error: Exception | None = None,
        restore_error: Exception | None = None,
    ) -> None:
        self.rect = rect
        self.query_error = query_error
        self.restore_error = restore_error
        self.calls: list[object] = []
        self.previous_context = 913

    def enter_physical_pixel_scope(self) -> object:
        self.calls.append("enter")
        return self.previous_context

    def primary_monitor_rect(self) -> tuple[int, int, int, int]:
        self.calls.append("query")
        if self.query_error is not None:
            raise self.query_error
        return self.rect

    def restore_dpi_scope(self, previous_context: object) -> None:
        self.calls.append(("restore", previous_context))
        if self.restore_error is not None:
            raise self.restore_error


def test_reads_primary_monitor_in_temporary_physical_pixel_scope() -> None:
    api = _FakeGeometryApi((-1600, -200, 0, 700))

    geometry = WindowsPrimaryScreenGeometryProvider(api).read()

    assert geometry == PhysicalScreenGeometry(-1600, -200, 1600, 900)
    assert api.calls == ["enter", "query", ("restore", api.previous_context)]


def test_restores_dpi_scope_when_monitor_query_fails() -> None:
    api = _FakeGeometryApi(query_error=OSError("query failed"))

    with pytest.raises(OSError, match="query failed"):
        WindowsPrimaryScreenGeometryProvider(api).read()

    assert api.calls == ["enter", "query", ("restore", api.previous_context)]


def test_restore_failure_prevents_geometry_result() -> None:
    api = _FakeGeometryApi(restore_error=OSError("restore failed"))

    with pytest.raises(OSError, match="restore failed"):
        WindowsPrimaryScreenGeometryProvider(api).read()

    assert api.calls == ["enter", "query", ("restore", api.previous_context)]


@pytest.mark.parametrize(
    ("rect", "error", "message"),
    [
        ((0, 0, 0, 1080), ValueError, "positive dimensions"),
        ((0, 0, 1920, 0), ValueError, "positive dimensions"),
        ((0, 0, True, 1080), TypeError, "four integers"),
    ],
)
def test_rejects_invalid_native_rect_after_restoring_scope(
    rect: tuple[int, int, int, int],
    error: type[Exception],
    message: str,
) -> None:
    api = _FakeGeometryApi(rect)

    with pytest.raises(error, match=message):
        WindowsPrimaryScreenGeometryProvider(api).read()

    assert api.calls[-1] == ("restore", api.previous_context)


def test_fails_closed_on_unsupported_platform_before_loading_native_api() -> None:
    with pytest.raises(OSError, match="only on Windows"):
        WindowsPrimaryScreenGeometryProvider(platform_name="posix")


def test_rejects_an_incomplete_injected_api() -> None:
    class _IncompleteApi:
        def enter_physical_pixel_scope(self) -> object:
            return 1

    with pytest.raises(TypeError, match="WindowsScreenGeometryApi"):
        WindowsPrimaryScreenGeometryProvider(_IncompleteApi())  # type: ignore[arg-type]
