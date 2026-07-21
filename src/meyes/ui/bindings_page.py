"""Responsive, no-execution editor for isolated binding drafts."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from meyes.bindings.editor import (
    EditableActionKind,
    action_accepts_parameters,
    action_kind_for,
    action_kind_label,
    action_parameter_hint,
    editable_action_kinds,
    format_action_parameters,
)
from meyes.bindings.models import BindableGesture
from meyes.bindings.presentation import action_label, gesture_label
from meyes.ui.binding_editor_controller import (
    BindingDraftState,
    BindingEditorController,
    BindingSaveResult,
    binding_draft_state,
    binding_save_result,
)

_MAX_PROFILE_DISPLAY_CHARACTERS = 32


@dataclass(slots=True)
class _BindingRow:
    gesture: BindableGesture
    action_combo: QComboBox
    parameter_input: QLineEdit
    error_label: QLabel
    reset_button: QPushButton


class BindingsPage(QWidget):
    """Edit eight bindings as a draft and save only as a new profile."""

    def __init__(
        self,
        controller: BindingEditorController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, BindingEditorController):
            raise TypeError("Expected BindingEditorController")
        self._controller = controller
        self._rows: dict[BindableGesture, _BindingRow] = {}
        self._skip_row_sync = False
        self._force_row_sync = False
        self._state = controller.state
        self._build_ui()
        self._feedback_scroll_timer = QTimer(self)
        self._feedback_scroll_timer.setSingleShot(True)
        self._feedback_scroll_timer.timeout.connect(self._ensure_feedback_visible)
        self._connect_signals()
        self._render_state(self._state, sync_rows=True)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("bindingsPageScroll")
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("bindingsPageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Bindings")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Map each semantic gesture to a validated Safe Mode action without editing JSON."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safe_banner = QLabel("DRAFT ONLY · Saving creates a new profile · No action is executed")
        safe_banner.setObjectName("safeBanner")
        safe_banner.setWordWrap(True)
        self._feedback = QLabel()
        self._feedback.setObjectName("bindingFeedback")
        self._feedback.setWordWrap(True)
        self._feedback.hide()

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(safe_banner)
        layout.addWidget(self._build_source_panel())
        layout.addWidget(self._build_editor_panel())
        layout.addWidget(self._build_preview_panel())
        layout.addWidget(self._build_save_panel())
        layout.addStretch(1)
        self._scroll.setWidget(content)
        root.addWidget(self._scroll)

    def _build_source_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Draft source")
        heading.setObjectName("panelTitle")
        values = QGridLayout()
        values.setHorizontalSpacing(12)
        values.setVerticalSpacing(8)
        source_label = QLabel("Source snapshot")
        active_label = QLabel("Runtime active")
        self._source_value = QLabel("—")
        self._source_value.setObjectName("draftSourceValue")
        self._source_value.setAccessibleName("Draft source profile")
        self._active_value = QLabel("—")
        self._active_value.setObjectName("draftActiveValue")
        self._active_value.setAccessibleName("Runtime active profile")
        values.addWidget(source_label, 0, 0)
        values.addWidget(self._source_value, 0, 1)
        values.addWidget(active_label, 1, 0)
        values.addWidget(self._active_value, 1, 1)
        values.setColumnStretch(1, 1)

        self._draft_status = QLabel()
        self._draft_status.setObjectName("draftStatus")
        self._draft_status.setAccessibleName("Binding draft status")
        self._outdated_notice = QLabel(
            "The draft source differs from the runtime active profile. Runtime bindings were "
            "not changed; save another copy or explicitly discard the draft and load active."
        )
        self._outdated_notice.setObjectName("warningBanner")
        self._outdated_notice.setWordWrap(True)
        self._storage_notice = QLabel(
            "Profile storage is unavailable in this session. Editing and preview remain local "
            "to this draft, but saving is disabled."
        )
        self._storage_notice.setObjectName("warningBanner")
        self._storage_notice.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self._reset_all_button = QPushButton("Reset all to source")
        self._reset_all_button.setObjectName("resetAllBindingsButton")
        self._reset_all_button.setAccessibleName("Reset all bindings to source snapshot")
        self._load_active_button = QPushButton("Discard draft and load active snapshot")
        self._load_active_button.setObjectName("loadActiveBindingsButton")
        self._load_active_button.setAccessibleName(
            "Discard binding draft and load active profile snapshot"
        )
        button_row.addWidget(self._reset_all_button)
        button_row.addWidget(self._load_active_button)

        layout.addWidget(heading)
        layout.addLayout(values)
        layout.addWidget(self._draft_status)
        layout.addWidget(self._outdated_notice)
        layout.addWidget(self._storage_notice)
        layout.addLayout(button_row)
        return panel

    def _build_editor_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Eight gesture bindings")
        heading.setObjectName("panelTitle")
        helper = QLabel(
            "Parameter examples appear inside each field. Invalid text never replaces the last "
            "valid draft value."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(helper)
        for gesture in BindableGesture:
            layout.addWidget(self._build_binding_row(gesture))
        return panel

    def _build_binding_row(self, gesture: BindableGesture) -> QFrame:
        frame = QFrame()
        frame.setObjectName("bindingRow")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(gesture_label(gesture))
        title.setObjectName("bindingRowTitle")
        reset_button = QPushButton("Reset row")
        reset_button.setObjectName(f"resetBinding_{gesture.value}")
        reset_button.setAccessibleName(f"Reset {gesture_label(gesture)} binding")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(reset_button)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        action_caption = QLabel("Action")
        parameter_caption = QLabel("Parameters")
        action_combo = QComboBox()
        action_combo.setObjectName(f"bindingAction_{gesture.value}")
        action_combo.setAccessibleName(f"Action for {gesture_label(gesture)}")
        for kind in editable_action_kinds(gesture):
            action_combo.addItem(action_kind_label(kind), kind.value)
        parameter_input = QLineEdit()
        parameter_input.setObjectName(f"bindingParameters_{gesture.value}")
        parameter_input.setAccessibleName(f"Parameters for {gesture_label(gesture)}")
        error_label = QLabel()
        error_label.setObjectName("bindingError")
        error_label.setAccessibleName(f"Validation for {gesture_label(gesture)}")
        error_label.setWordWrap(True)
        error_label.hide()
        form.addWidget(action_caption, 0, 0)
        form.addWidget(action_combo, 0, 1)
        form.addWidget(parameter_caption, 1, 0)
        form.addWidget(parameter_input, 1, 1)
        form.addWidget(error_label, 2, 1)
        form.setColumnStretch(1, 1)

        layout.addLayout(header)
        layout.addLayout(form)
        self._rows[gesture] = _BindingRow(
            gesture=gesture,
            action_combo=action_combo,
            parameter_input=parameter_input,
            error_label=error_label,
            reset_button=reset_button,
        )
        return frame

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Isolated draft preview")
        heading.setObjectName("panelTitle")
        helper = QLabel(
            "This table describes the last valid draft snapshot only. It does not dispatch, "
            "simulate, activate, or test any action."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        self._preview_table = QTableWidget(len(BindableGesture), 2)
        self._preview_table.setObjectName("draftBindingsTable")
        self._preview_table.setAccessibleName("Isolated draft binding preview")
        self._preview_table.setHorizontalHeaderLabels(("Gesture", "Draft action"))
        self._preview_table.verticalHeader().hide()
        self._preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._preview_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._preview_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._preview_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self._preview_table.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        header = self._preview_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._preview_table.setMinimumHeight(250)

        layout.addWidget(heading)
        layout.addWidget(helper)
        layout.addWidget(self._preview_table)
        return panel

    def _build_save_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Save as a new profile")
        heading.setObjectName("panelTitle")
        helper = QLabel(
            "Saving never activates the new profile. Select it later from Profiles, which will "
            "pause tracking before changing runtime bindings."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        self._profile_name_input = QLineEdit()
        self._profile_name_input.setObjectName("bindingCopyName")
        self._profile_name_input.setAccessibleName("New profile name for binding draft")
        self._profile_name_input.setPlaceholderText("New profile name")
        self._save_button = QPushButton("Save draft as new profile")
        self._save_button.setObjectName("saveBindingDraftButton")
        self._save_button.setAccessibleName("Save binding draft as a new inactive profile")
        self._save_button.setProperty("primaryAction", True)

        layout.addWidget(heading)
        layout.addWidget(helper)
        layout.addWidget(self._profile_name_input)
        layout.addWidget(self._feedback)
        layout.addWidget(self._save_button)
        return panel

    def _connect_signals(self) -> None:
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.operation_finished.connect(self._on_operation_finished)
        self._reset_all_button.clicked.connect(self._reset_all)
        self._load_active_button.clicked.connect(self._load_active)
        self._profile_name_input.textChanged.connect(self._update_controls)
        self._save_button.clicked.connect(self._save_as_copy)
        for gesture, row in self._rows.items():
            row.action_combo.currentIndexChanged.connect(
                lambda _index, selected=gesture: self._edit_row(selected)
            )
            row.parameter_input.textChanged.connect(
                lambda _text, selected=gesture: self._edit_row(selected)
            )
            row.reset_button.clicked.connect(
                lambda _checked=False, selected=gesture: self._reset_row(selected)
            )

    @Slot(object)
    def _on_state_changed(self, payload: object) -> None:
        self._state = binding_draft_state(payload)
        sync_rows = not self._skip_row_sync and (self._force_row_sync or not self._state.errors)
        self._force_row_sync = False
        self._render_state(self._state, sync_rows=sync_rows)

    @Slot(object)
    def _on_operation_finished(self, payload: object) -> None:
        result = binding_save_result(payload)
        self._show_result(result)
        self._feedback_scroll_timer.start(0)
        if result.success:
            self._profile_name_input.clear()
        self._update_controls()

    @Slot()
    def _update_controls(self) -> None:
        self._reset_all_button.setEnabled(self._state.dirty)
        self._load_active_button.setEnabled(self._state.dirty or self._state.source_outdated)
        self._profile_name_input.setEnabled(self._state.storage_available)
        self._save_button.setEnabled(
            self._state.can_save and bool(self._profile_name_input.text().strip())
        )

    @Slot()
    def _ensure_feedback_visible(self) -> None:
        self._scroll.ensureWidgetVisible(self._feedback, 0, 16)

    def _edit_row(self, gesture: BindableGesture) -> None:
        row = self._rows[gesture]
        kind = self._selected_kind(row.action_combo)
        self._update_parameter_affordance(row, kind)
        if not action_accepts_parameters(kind) and row.parameter_input.text():
            with QSignalBlocker(row.parameter_input):
                row.parameter_input.clear()
        self._skip_row_sync = True
        try:
            self._controller.edit_binding(gesture, kind, row.parameter_input.text())
        finally:
            self._skip_row_sync = False

    @Slot()
    def _reset_all(self) -> None:
        self._force_row_sync = True
        self._controller.reset_all()

    @Slot()
    def _load_active(self) -> None:
        self._force_row_sync = True
        self._controller.load_active()

    def _reset_row(self, gesture: BindableGesture) -> None:
        self._force_row_sync = True
        self._controller.reset_binding(gesture)

    @Slot()
    def _save_as_copy(self) -> None:
        self._controller.save_as_copy(self._profile_name_input.text())

    def _render_state(self, state: BindingDraftState, *, sync_rows: bool) -> None:
        source_name = state.source_profile.profile_name
        self._source_value.setText(_elide_middle(source_name))
        self._source_value.setToolTip(source_name)
        self._active_value.setText(_elide_middle(state.active_profile_name))
        self._active_value.setToolTip(state.active_profile_name)
        if state.errors:
            status_text = f"Draft has {len(state.errors)} validation error(s)"
            status = "error"
        elif state.dirty:
            status_text = "Unsaved draft changes"
            status = "dirty"
        else:
            status_text = "Draft matches its source snapshot"
            status = "clean"
        self._draft_status.setText(status_text)
        self._draft_status.setProperty("draftState", status)
        _refresh_style(self._draft_status)
        self._outdated_notice.setVisible(state.source_outdated)
        self._storage_notice.setVisible(not state.storage_available)

        for gesture, row in self._rows.items():
            if sync_rows:
                action = state.draft_profile.bindings[gesture]
                kind = action_kind_for(action)
                with QSignalBlocker(row.action_combo):
                    row.action_combo.setCurrentIndex(row.action_combo.findData(kind.value))
                with QSignalBlocker(row.parameter_input):
                    row.parameter_input.setText(format_action_parameters(action))
                self._update_parameter_affordance(row, kind)
            error = state.error_for(gesture)
            row.error_label.setText(error or "")
            row.error_label.setVisible(error is not None)
            row.parameter_input.setProperty("invalid", error is not None)
            _refresh_style(row.parameter_input)
            row.reset_button.setEnabled(
                error is not None
                or state.draft_profile.bindings[gesture] != state.source_profile.bindings[gesture]
            )

        for table_row, gesture in enumerate(BindableGesture):
            gesture_item = QTableWidgetItem(gesture_label(gesture))
            action_text = action_label(state.draft_profile.bindings[gesture])
            action_item = QTableWidgetItem(action_text)
            action_item.setToolTip(action_text)
            self._preview_table.setItem(table_row, 0, gesture_item)
            self._preview_table.setItem(table_row, 1, action_item)
        self._update_controls()

    def _update_parameter_affordance(
        self,
        row: _BindingRow,
        kind: EditableActionKind,
    ) -> None:
        accepts_parameters = action_accepts_parameters(kind)
        row.parameter_input.setEnabled(accepts_parameters)
        row.parameter_input.setPlaceholderText(action_parameter_hint(kind))
        row.parameter_input.setToolTip(action_parameter_hint(kind))

    @staticmethod
    def _selected_kind(combo: QComboBox) -> EditableActionKind:
        value = combo.currentData()
        if not isinstance(value, str):
            raise TypeError("Binding action choice is invalid")
        return EditableActionKind(value)

    def _show_result(self, result: BindingSaveResult) -> None:
        self._feedback.setText(result.message)
        self._feedback.setProperty("feedbackStatus", "success" if result.success else "error")
        _refresh_style(self._feedback)
        self._feedback.show()


def _elide_middle(value: str) -> str:
    if len(value) <= _MAX_PROFILE_DISPLAY_CHARACTERS:
        return value
    visible_characters = _MAX_PROFILE_DISPLAY_CHARACTERS - 1
    prefix_length = (visible_characters + 1) // 2
    suffix_length = visible_characters // 2
    return f"{value[:prefix_length]}…{value[-suffix_length:]}"


def _refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
