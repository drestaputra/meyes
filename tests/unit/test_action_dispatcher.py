"""Fail-closed, fake-only action dispatcher contract tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from meyes.bindings.defaults import disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyboardShortcutAction,
    KeyName,
    MouseButton,
    MouseClickAction,
    MouseDoubleClickAction,
    MouseDownAction,
    MouseScrollAction,
    MouseUpAction,
    PauseTrackingAction,
    ResumeTrackingAction,
    ToggleTrackingAction,
)
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.services.action_dispatcher import (
    ActionDispatcher,
    DispatcherState,
    DispatchStatus,
)


def event(
    event_type: GestureEventType,
    *,
    timestamp: float = 1.0,
    sequence: int = 1,
    duration_ms: float = 0.0,
) -> GestureEvent:
    return GestureEvent(event_type, timestamp, sequence, duration_ms)


def profile_with(
    updates: Mapping[BindableGesture, Action],
    *,
    name: str = "Dispatcher test",
) -> BindingProfile:
    bindings: dict[BindableGesture, Action] = {
        gesture: DisabledAction() for gesture in BindableGesture
    }
    bindings.update(updates)
    return BindingProfile(profile_name=name, bindings=bindings)


def make_dispatcher(
    updates: Mapping[BindableGesture, Action],
    *,
    executor: FakeInputExecutor | None = None,
    tracking_control: ManualTrackingControl | None = None,
    safe_mode: bool = False,
) -> tuple[ActionDispatcher, FakeInputExecutor]:
    fake = executor or FakeInputExecutor()
    dispatcher = ActionDispatcher(
        BindingManager(profile_with(updates)),
        fake,
        tracking_control=tracking_control,
        safe_mode=safe_mode,
    )
    return dispatcher, fake


class ManualTrackingControl:
    """Accept either lifecycle naming style while recording one semantic request."""

    def __init__(self) -> None:
        self.requests: list[str] = []

    def pause(self) -> None:
        self.requests.append("pause")

    def resume(self) -> None:
        self.requests.append("resume")

    def toggle(self) -> None:
        self.requests.append("toggle")

    def pause_tracking(self) -> None:
        self.pause()

    def resume_tracking(self) -> None:
        self.resume()

    def toggle_tracking(self) -> None:
        self.toggle()


class OneShotFailureExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_click = True

    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        if self.fail_next_click:
            self.fail_next_click = False
            raise RuntimeError("injected click failure")


class OneShotReleaseFailureExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.fail_next_release = True

    def release_all(self) -> None:
        if self.fail_next_release:
            self.fail_next_release = False
            self.release_all_calls += 1
            self.calls.append(InputCall("release_all"))
            raise RuntimeError("injected release failure")
        super().release_all()


class FailAfterKeyDownExecutor(FakeInputExecutor):
    def key_down(self, key: KeyName) -> None:
        super().key_down(key)
        raise RuntimeError("injected key-down failure")


class FailOnNegativeScrollExecutor(FakeInputExecutor):
    def mouse_scroll(self, amount: int) -> None:
        super().mouse_scroll(amount)
        if amount < 0:
            raise RuntimeError("injected continuous-scroll failure")


class ReentrantDispatchExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: ActionDispatcher | None = None
        self.nested_status: DispatchStatus | None = None

    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        assert self.dispatcher is not None
        nested = self.dispatcher.dispatch(
            event(GestureEventType.RIGHT_WINK, timestamp=1.0, sequence=1),
            current_timestamp=1.0,
        )
        self.nested_status = nested.status


class ReentrantPauseExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: ActionDispatcher | None = None
        self.pause_succeeded: bool | None = None
        self.pause_released: bool | None = None

    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        assert self.dispatcher is not None
        paused = self.dispatcher.pause("reentrant safety request")
        self.pause_succeeded = paused.success
        self.pause_released = paused.released


class ReentrantPollExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: ActionDispatcher | None = None
        self.nested_status: DispatchStatus | None = None

    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        assert self.dispatcher is not None
        nested = self.dispatcher.poll(1.0)
        assert len(nested) == 1
        self.nested_status = nested[0].status


class ReentrantReleaseExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: ActionDispatcher | None = None
        self.reenter_once = True
        self.nested_status: DispatchStatus | None = None

    def release_all(self) -> None:
        if self.reenter_once:
            self.reenter_once = False
            assert self.dispatcher is not None
            nested = self.dispatcher.dispatch(
                event(GestureEventType.LEFT_WINK),
                current_timestamp=1.0,
            )
            self.nested_status = nested.status
        super().release_all()


class FailingTrackingControl(ManualTrackingControl):
    def pause_tracking(self) -> None:
        super().pause_tracking()
        raise RuntimeError("injected tracking callback failure")


def test_safe_mode_starts_paused_and_requires_explicit_arm() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        safe_mode=True,
    )

    ignored = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)
    armed = dispatcher.arm()
    executed = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert ignored.status is DispatchStatus.INACTIVE
    assert armed.success is True
    assert armed.state is DispatcherState.ACTIVE
    assert executed.status is DispatchStatus.EXECUTED
    assert fake.calls[-1] == InputCall("mouse_click", (MouseButton.LEFT,))


@pytest.mark.parametrize(
    ("action", "expected_calls"),
    [
        (
            MouseClickAction(button=MouseButton.LEFT),
            [InputCall("mouse_click", (MouseButton.LEFT,))],
        ),
        (
            MouseDoubleClickAction(button=MouseButton.RIGHT),
            [
                InputCall("mouse_click", (MouseButton.RIGHT,)),
                InputCall("mouse_click", (MouseButton.RIGHT,)),
            ],
        ),
        (MouseUpAction(button=MouseButton.MIDDLE), [InputCall("mouse_up", (MouseButton.MIDDLE,))]),
        (MouseScrollAction(amount=-4), [InputCall("mouse_scroll", (-4,))]),
        (
            KeyboardKeyAction(key=KeyName.ENTER),
            [InputCall("key_down", (KeyName.ENTER,)), InputCall("key_up", (KeyName.ENTER,))],
        ),
        (
            KeyboardShortcutAction(keys=(KeyName.CTRL, KeyName.SHIFT, KeyName.A)),
            [
                InputCall("keyboard_shortcut", (KeyName.CTRL, KeyName.SHIFT, KeyName.A)),
                InputCall("key_down", (KeyName.CTRL,)),
                InputCall("key_down", (KeyName.SHIFT,)),
                InputCall("key_down", (KeyName.A,)),
                InputCall("key_up", (KeyName.A,)),
                InputCall("key_up", (KeyName.SHIFT,)),
                InputCall("key_up", (KeyName.CTRL,)),
            ],
        ),
    ],
)
def test_one_shot_actions_execute_exactly_once(
    action: Action,
    expected_calls: list[InputCall],
) -> None:
    dispatcher, fake = make_dispatcher({BindableGesture.LEFT_WINK: action})

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.EXECUTED
    assert fake.calls == expected_calls
    assert not fake.held_buttons
    assert not fake.held_keys


def test_disabled_action_is_explicit_and_side_effect_free() -> None:
    dispatcher, fake = make_dispatcher({})

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.DISABLED
    assert report.gesture is BindableGesture.LEFT_WINK
    assert report.action_type == "disabled"
    assert fake.calls == []


@pytest.mark.parametrize(
    ("action", "expected_request"),
    [
        (PauseTrackingAction(), "pause"),
        (ResumeTrackingAction(), "resume"),
        (ToggleTrackingAction(), "pause"),
    ],
)
def test_lifecycle_actions_use_tracking_control_not_input_executor(
    action: Action,
    expected_request: str,
) -> None:
    control = ManualTrackingControl()
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: action},
        tracking_control=control,
    )

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.LIFECYCLE_REQUESTED
    assert control.requests == [expected_request]
    assert all(call.operation != "mouse_click" for call in fake.calls)


def test_lifecycle_action_without_control_fails_closed_without_input() -> None:
    dispatcher, fake = make_dispatcher({BindableGesture.LEFT_WINK: ResumeTrackingAction()})

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.LIFECYCLE_UNAVAILABLE
    assert dispatcher.state is DispatcherState.PAUSED
    assert fake.release_all_calls == 1


def test_duplicate_and_stale_events_are_not_replayed() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )

    first = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=5),
        current_timestamp=2.0,
    )
    duplicate = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=5),
        current_timestamp=2.0,
    )
    stale = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=1.0, sequence=4),
        current_timestamp=2.0,
    )

    assert first.status is DispatchStatus.EXECUTED
    assert duplicate.status is DispatchStatus.DUPLICATE
    assert stale.status is DispatchStatus.STALE
    assert fake.calls.count(InputCall("mouse_click", (MouseButton.LEFT,))) == 1


def test_ordering_is_independent_between_left_and_right_channels() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_WINK: MouseClickAction(button=MouseButton.RIGHT),
        }
    )

    left = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, sequence=100), current_timestamp=1.0
    )
    right = dispatcher.dispatch(
        event(GestureEventType.RIGHT_WINK, sequence=1), current_timestamp=1.0
    )

    assert left.status is DispatchStatus.EXECUTED
    assert right.status is DispatchStatus.EXECUTED
    assert fake.calls[-1] == InputCall("mouse_click", (MouseButton.RIGHT,))


def test_tap_and_hold_share_one_ordering_channel_per_temple_side() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
            BindableGesture.LEFT_TEMPLE_TAP: MouseClickAction(button=MouseButton.RIGHT),
            BindableGesture.RIGHT_TEMPLE_TAP: MouseScrollAction(amount=1),
        }
    )

    started = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=10),
        current_timestamp=1.0,
    )
    stale_tap = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_TAP, timestamp=2.0, sequence=9),
        current_timestamp=2.0,
    )
    independent_right = dispatcher.dispatch(
        event(GestureEventType.RIGHT_TEMPLE_TAP, timestamp=2.0, sequence=1),
        current_timestamp=2.0,
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=3.0, sequence=11),
        current_timestamp=3.0,
    )

    assert started.status is DispatchStatus.HOLD_STARTED
    assert stale_tap.status is DispatchStatus.STALE
    assert independent_right.status is DispatchStatus.EXECUTED
    assert InputCall("mouse_click", (MouseButton.RIGHT,)) not in fake.calls
    assert fake.calls == [
        InputCall("mouse_down", (MouseButton.LEFT,)),
        InputCall("mouse_scroll", (1,)),
        InputCall("mouse_up", (MouseButton.LEFT,)),
    ]


def test_same_side_tap_during_active_hold_faults_and_releases() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
            BindableGesture.LEFT_TEMPLE_TAP: MouseClickAction(button=MouseButton.RIGHT),
        }
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=10),
        current_timestamp=1.0,
    )

    conflict = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_TAP, timestamp=2.0, sequence=11),
        current_timestamp=2.0,
    )
    stale_end = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=2.0, sequence=11),
        current_timestamp=2.0,
    )

    assert conflict.status is DispatchStatus.FAULTED
    assert stale_end.status is DispatchStatus.STALE
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.held_buttons == set()
    assert InputCall("mouse_click", (MouseButton.RIGHT,)) not in fake.calls
    assert fake.release_all_calls == 1


def test_same_identity_hold_start_then_end_is_valid_but_reverse_is_stale() -> None:
    action = MouseDownAction(button=MouseButton.LEFT)
    dispatcher, fake = make_dispatcher({BindableGesture.LEFT_TEMPLE_HOLD: action})

    started = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=7),
        current_timestamp=1.0,
    )
    ended = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=2.0, sequence=7),
        current_timestamp=2.0,
    )
    duplicate_end = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=2.0, sequence=7),
        current_timestamp=2.0,
    )

    reverse, other_fake = make_dispatcher({BindableGesture.LEFT_TEMPLE_HOLD: action})
    orphan = reverse.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, sequence=8),
        current_timestamp=1.0,
    )
    stale_start = reverse.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=8),
        current_timestamp=1.0,
    )

    assert started.status is DispatchStatus.HOLD_STARTED
    assert ended.status is DispatchStatus.HOLD_ENDED
    assert duplicate_end.status is DispatchStatus.DUPLICATE
    assert fake.calls == [
        InputCall("mouse_down", (MouseButton.LEFT,)),
        InputCall("mouse_up", (MouseButton.LEFT,)),
    ]
    assert orphan.status is DispatchStatus.ORPHAN_END
    assert stale_start.status is DispatchStatus.STALE
    assert other_fake.calls == []


def test_mouse_down_hold_uses_reference_counting_for_shared_button() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
        }
    )

    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )
    dispatcher.dispatch(
        event(GestureEventType.RIGHT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert fake.calls == [InputCall("mouse_down", (MouseButton.LEFT,))]
    assert BindableGesture.RIGHT_TEMPLE_HOLD in dispatcher.active_holds

    dispatcher.dispatch(
        event(GestureEventType.RIGHT_TEMPLE_HOLD_END, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert fake.calls[-1] == InputCall("mouse_up", (MouseButton.LEFT,))
    assert not dispatcher.active_holds


def test_new_start_for_an_active_gesture_faults_and_releases_without_second_down() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)}
    )

    first = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )
    conflict = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert first.status is DispatchStatus.HOLD_STARTED
    assert conflict.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.calls.count(InputCall("mouse_down", (MouseButton.LEFT,))) == 1
    assert fake.release_all_calls == 1


def test_click_cannot_compete_with_a_held_button_owner() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_WINK: MouseClickAction(button=MouseButton.LEFT),
        }
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )

    conflict = dispatcher.dispatch(
        event(GestureEventType.RIGHT_WINK, timestamp=2.0, sequence=1),
        current_timestamp=2.0,
    )

    assert conflict.status is DispatchStatus.RESOURCE_BUSY
    assert fake.calls == [InputCall("mouse_down", (MouseButton.LEFT,))]


def test_mouse_up_action_cancels_existing_owners_for_that_button() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_WINK: MouseUpAction(button=MouseButton.LEFT),
        }
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )

    released = dispatcher.dispatch(
        event(GestureEventType.RIGHT_WINK, timestamp=2.0, sequence=1),
        current_timestamp=2.0,
    )
    orphan = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, timestamp=3.0, sequence=2),
        current_timestamp=3.0,
    )

    assert released.status is DispatchStatus.EXECUTED
    assert orphan.status is DispatchStatus.ORPHAN_END
    assert fake.calls[-1] == InputCall("mouse_up", (MouseButton.LEFT,))
    assert not dispatcher.active_holds


def test_continuous_scroll_waits_for_deadline_and_never_catches_up() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=-2, interval_ms=100)}
    )

    started = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, timestamp=10.0, sequence=1),
        current_timestamp=10.0,
    )
    dispatcher.poll(10.099)
    dispatcher.poll(10.1)
    dispatcher.poll(10.55)

    assert started.status is DispatchStatus.CONTINUOUS_STARTED
    assert fake.calls == [InputCall("mouse_scroll", (-2,)), InputCall("mouse_scroll", (-2,))]
    assert dispatcher.next_poll_deadline == pytest.approx(10.65)


def test_continuous_failure_stops_later_side_and_faults_closed() -> None:
    fake = FailOnNegativeScrollExecutor()
    dispatcher, _ = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=-1, interval_ms=100),
            BindableGesture.RIGHT_TEMPLE_HOLD: ContinuousScrollAction(amount=1, interval_ms=100),
        },
        executor=fake,
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)
    dispatcher.dispatch(event(GestureEventType.RIGHT_TEMPLE_HOLD_START), current_timestamp=1.0)

    reports = dispatcher.poll(1.1)

    assert [report.status for report in reports] == [DispatchStatus.FAULTED]
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.calls.count(InputCall("mouse_scroll", (-1,))) == 1
    assert InputCall("mouse_scroll", (1,)) not in fake.calls
    assert fake.release_all_calls == 1


def test_exact_start_end_pair_produces_zero_continuous_scroll() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=2, interval_ms=25)}
    )

    started = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=3),
        current_timestamp=1.0,
    )
    ended = dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_END, sequence=3),
        current_timestamp=1.0,
    )
    dispatcher.poll(2.0)

    assert started.status is DispatchStatus.CONTINUOUS_STARTED
    assert ended.status is DispatchStatus.HOLD_ENDED
    assert fake.calls == []
    assert dispatcher.next_poll_deadline is None


def test_continuous_schedule_faults_when_clock_cannot_advance() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=1, interval_ms=100)}
    )

    report = dispatcher.dispatch(
        event(
            GestureEventType.LEFT_TEMPLE_HOLD_START,
            timestamp=1e308,
            sequence=1,
        ),
        current_timestamp=1e308,
    )

    assert report.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert InputCall("mouse_scroll", (1,)) not in fake.calls
    assert fake.release_all_calls == 1


def test_invalid_poll_preserves_deadline_and_has_no_side_effect() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=1, interval_ms=100)}
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)

    invalid = dispatcher.poll(float("nan"))
    regressed = dispatcher.poll(0.5)

    assert invalid[0].status is DispatchStatus.INVALID
    assert regressed[0].status is DispatchStatus.INVALID
    assert dispatcher.next_poll_deadline == pytest.approx(1.1)
    assert fake.calls == []

    dispatcher.poll(1.1)
    assert fake.calls == [InputCall("mouse_scroll", (1,))]


def test_poll_ticks_independent_holds_in_stable_left_to_right_order() -> None:
    dispatcher, fake = make_dispatcher(
        {
            BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(amount=-1, interval_ms=100),
            BindableGesture.RIGHT_TEMPLE_HOLD: ContinuousScrollAction(amount=1, interval_ms=100),
        }
    )
    dispatcher.dispatch(
        event(GestureEventType.RIGHT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )
    dispatcher.dispatch(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, sequence=1),
        current_timestamp=1.0,
    )

    dispatcher.poll(1.1)

    assert fake.calls == [InputCall("mouse_scroll", (-1,)), InputCall("mouse_scroll", (1,))]


def test_dispatcher_owns_profile_snapshot_and_switch_releases_first() -> None:
    original = profile_with(
        {BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)},
        name="Original",
    )
    manager = BindingManager(original)
    fake = FakeInputExecutor()
    dispatcher = ActionDispatcher(manager, fake, safe_mode=False)
    manager.activate(disabled_profile("External mutation"))
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)

    switched = dispatcher.activate_profile(disabled_profile("Replacement"))

    assert switched.success is True
    assert dispatcher.active_profile.profile_name == "Replacement"
    assert fake.calls[0] == InputCall("mouse_down", (MouseButton.LEFT,))
    assert fake.release_all_calls == 1
    assert not dispatcher.active_holds
    assert dispatcher.state is DispatcherState.PAUSED

    suppressed = dispatcher.dispatch(
        event(GestureEventType.RIGHT_WINK, timestamp=2.0, sequence=1),
        current_timestamp=2.0,
    )
    assert suppressed.status is DispatchStatus.INACTIVE

    assert dispatcher.arm().success is True
    enabled = dispatcher.dispatch(
        event(GestureEventType.RIGHT_WINK, timestamp=3.0, sequence=2),
        current_timestamp=3.0,
    )
    assert enabled.status is DispatchStatus.DISABLED


def test_profile_switch_failure_keeps_previous_profile_and_faults() -> None:
    fake = OneShotReleaseFailureExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
    )

    switched = dispatcher.activate_profile(disabled_profile("Not activated"))

    assert switched.success is False
    assert switched.error is not None
    assert dispatcher.state is DispatcherState.FAULTED
    assert dispatcher.active_profile.profile_name == "Dispatcher test"


def test_primitive_failure_faults_releases_and_never_replays() -> None:
    fake = OneShotFailureExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
    )

    failed = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)
    ignored = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert failed.status is DispatchStatus.FAULTED
    assert dispatcher.fault is not None
    assert ignored.status is DispatchStatus.FAULTED
    assert fake.release_all_calls == 1
    assert fake.calls.count(InputCall("mouse_click", (MouseButton.LEFT,))) == 1

    recovered = dispatcher.recover()

    assert recovered.success is True
    assert recovered.state is DispatcherState.PAUSED

    assert dispatcher.arm().success is True
    replay = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=2),
        current_timestamp=3.0,
    )
    assert replay.status is DispatchStatus.DUPLICATE
    assert fake.calls.count(InputCall("mouse_click", (MouseButton.LEFT,))) == 1


def test_executor_fault_best_effort_pauses_tracking_control() -> None:
    fake = OneShotFailureExecutor()
    control = ManualTrackingControl()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
        tracking_control=control,
    )

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert control.requests == ["pause"]
    assert fake.release_all_calls == 1


def test_partial_key_down_failure_attempts_key_up_then_global_release() -> None:
    fake = FailAfterKeyDownExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: KeyboardKeyAction(key=KeyName.A)},
        executor=fake,
    )

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.held_keys == set()
    assert fake.calls[:2] == [
        InputCall("key_down", (KeyName.A,)),
        InputCall("key_up", (KeyName.A,)),
    ]
    assert fake.release_all_calls == 1


def test_release_failure_retains_fault_until_successful_recovery() -> None:
    fake = OneShotReleaseFailureExecutor()
    control = ManualTrackingControl()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)},
        executor=fake,
        tracking_control=control,
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)

    paused = dispatcher.pause("injected release failure")

    assert paused.success is False
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.held_buttons == {MouseButton.LEFT}
    assert control.requests == ["pause"]

    recovered = dispatcher.recover()

    assert recovered.success is True
    assert recovered.state is DispatcherState.PAUSED
    assert fake.held_buttons == set()
    assert fake.release_all_calls == 2


def test_tracking_callback_failure_faults_and_runs_cleanup_again() -> None:
    control = FailingTrackingControl()
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: PauseTrackingAction()},
        tracking_control=control,
    )

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert control.requests == ["pause"]
    assert fake.release_all_calls == 2


@pytest.mark.parametrize(
    "bad_event",
    [
        event(GestureEventType.LEFT_WINK, timestamp=float("nan")),
        event(GestureEventType.LEFT_WINK, timestamp=-1.0),
        event(GestureEventType.LEFT_WINK, sequence=-1),
        event(GestureEventType.LEFT_WINK, sequence=cast(int, True)),
        event(GestureEventType.LEFT_WINK, duration_ms=float("inf")),
        event(GestureEventType.LEFT_WINK, duration_ms=-1.0),
        GestureEvent(cast(GestureEventType, "UNKNOWN"), 1.0, 1, 0.0),
    ],
)
def test_invalid_event_is_side_effect_free_and_does_not_consume_identity(
    bad_event: GestureEvent,
) -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )

    invalid = dispatcher.dispatch(bad_event, current_timestamp=1.0)
    valid = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert invalid.status is DispatchStatus.INVALID
    assert valid.status is DispatchStatus.EXECUTED
    assert fake.calls == [InputCall("mouse_click", (MouseButton.LEFT,))]


@pytest.mark.parametrize("current_timestamp", [float("nan"), float("inf"), -1.0])
def test_invalid_or_future_arrival_time_is_side_effect_free(
    current_timestamp: float,
) -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )

    invalid = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=1.0),
        current_timestamp=current_timestamp,
    )

    assert invalid.status is DispatchStatus.INVALID
    assert fake.calls == []


def test_unrepresentably_large_timestamp_is_rejected_without_exception() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )

    invalid = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK),
        current_timestamp=cast(float, 10**10000),
    )

    assert invalid.status is DispatchStatus.INVALID
    assert fake.calls == []


def test_future_event_and_regressing_arrival_clock_are_rejected() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )

    future = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0), current_timestamp=1.0
    )
    accepted = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=1.0), current_timestamp=1.0
    )
    regressed = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=0.5, sequence=2),
        current_timestamp=0.5,
    )

    assert future.status is DispatchStatus.INVALID
    assert accepted.status is DispatchStatus.EXECUTED
    assert regressed.status is DispatchStatus.INVALID
    assert fake.calls == [InputCall("mouse_click", (MouseButton.LEFT,))]


def test_begin_event_epoch_releases_and_accepts_low_sequences_again() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)}
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_WINK, sequence=100), current_timestamp=1.0)

    paused = dispatcher.pause("new producer")
    reset = dispatcher.begin_event_epoch()
    armed = dispatcher.arm()
    replay = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=1),
        current_timestamp=2.0,
    )

    assert paused.success is True
    assert reset.success is True
    assert armed.success is True
    assert replay.status is DispatchStatus.EXECUTED
    assert fake.release_all_calls == 3
    assert fake.calls.count(InputCall("mouse_click", (MouseButton.LEFT,))) == 2


def test_nested_dispatch_is_rejected_and_faults_outer_operation() -> None:
    fake = ReentrantDispatchExecutor()
    dispatcher, _ = make_dispatcher(
        {
            BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_WINK: MouseClickAction(button=MouseButton.RIGHT),
        },
        executor=fake,
    )
    fake.dispatcher = dispatcher

    outer = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert fake.nested_status is DispatchStatus.REENTRANT_REJECTED
    assert outer.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.calls.count(InputCall("mouse_click", (MouseButton.RIGHT,))) == 0
    assert fake.release_all_calls == 1


def test_reentrant_pause_is_deferred_and_coalesced_after_primitive() -> None:
    fake = ReentrantPauseExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
    )
    fake.dispatcher = dispatcher

    report = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert report.status is DispatchStatus.INACTIVE
    assert fake.pause_succeeded is True
    assert fake.pause_released is False
    assert dispatcher.state is DispatcherState.PAUSED
    assert fake.release_all_calls == 1


def test_nested_poll_is_rejected_and_faults_outer_operation() -> None:
    fake = ReentrantPollExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
    )
    fake.dispatcher = dispatcher

    outer = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)

    assert fake.nested_status is DispatchStatus.REENTRANT_REJECTED
    assert outer.status is DispatchStatus.FAULTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert fake.release_all_calls == 1


def test_reentrant_dispatch_during_release_cannot_arm_or_replay() -> None:
    fake = ReentrantReleaseExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT)},
        executor=fake,
        safe_mode=True,
    )
    fake.dispatcher = dispatcher

    armed = dispatcher.arm()

    assert armed.success is False
    assert fake.nested_status is DispatchStatus.REENTRANT_REJECTED
    assert dispatcher.state is DispatcherState.FAULTED
    assert InputCall("mouse_click", (MouseButton.LEFT,)) not in fake.calls

    assert dispatcher.recover().success is True
    assert dispatcher.arm().success is True
    replay = dispatcher.dispatch(event(GestureEventType.LEFT_WINK), current_timestamp=1.0)
    assert replay.status is DispatchStatus.DUPLICATE


def test_close_releases_holds_and_is_terminal() -> None:
    dispatcher, fake = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)}
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)

    closed = dispatcher.close()
    ignored = dispatcher.dispatch(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=2),
        current_timestamp=2.0,
    )

    assert closed.state is DispatcherState.CLOSED
    assert dispatcher.state is DispatcherState.CLOSED
    assert ignored.status is DispatchStatus.INACTIVE
    assert fake.release_all_calls == 1
    assert not fake.held_buttons


def test_close_remains_terminal_and_can_retry_failed_cleanup() -> None:
    fake = OneShotReleaseFailureExecutor()
    dispatcher, _ = make_dispatcher(
        {BindableGesture.LEFT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)},
        executor=fake,
    )
    dispatcher.dispatch(event(GestureEventType.LEFT_TEMPLE_HOLD_START), current_timestamp=1.0)

    failed = dispatcher.close()

    assert failed.success is False
    assert failed.state is DispatcherState.CLOSED
    assert fake.held_buttons == {MouseButton.LEFT}

    retried = dispatcher.close()

    assert retried.success is True
    assert retried.state is DispatcherState.CLOSED
    assert fake.held_buttons == set()
    assert fake.release_all_calls == 2
