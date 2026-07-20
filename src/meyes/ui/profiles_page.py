"""User-visible durable profile catalog and active binding preview."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.presentation import action_label, gesture_label
from meyes.ui.profile_controller import (
    ProfileController,
    ProfileOperationResult,
    binding_profile,
    profile_names,
    profile_operation,
)

_MAX_PROFILE_DISPLAY_CHARACTERS = 32


class ProfilesPage(QWidget):
    """Create safe profiles, activate them, and inspect active mappings."""

    def __init__(
        self,
        controller: ProfileController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, ProfileController):
            raise TypeError("Expected ProfileController")
        self._controller = controller
        self._build_ui()
        self._connect_signals()
        self._render_names(self._controller.profile_names)
        self._render_active(self._controller.active_profile)
        self._update_controls()
        if self._controller.catalog_warning:
            self._show_result(
                ProfileOperationResult(
                    True,
                    self._controller.catalog_warning,
                    warning=True,
                )
            )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("profilesPageScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("profilesPageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Profiles")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Create local configuration sets and choose which complete binding snapshot "
            "the Safe Mode simulation uses."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safe_banner = QLabel("SAFE MODE · Profile changes pause tracking · OS input disconnected")
        safe_banner.setObjectName("safeBanner")
        safe_banner.setWordWrap(True)
        self._feedback = QLabel()
        self._feedback.setObjectName("profileFeedback")
        self._feedback.setWordWrap(True)
        self._feedback.hide()

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(safe_banner)
        layout.addWidget(self._feedback)
        layout.addWidget(self._build_catalog_panel())
        layout.addWidget(self._build_binding_preview())
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_catalog_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Local profile catalog")
        heading.setObjectName("panelTitle")
        heading.setWordWrap(True)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setObjectName("refreshProfilesButton")
        self._refresh_button.setAccessibleName("Refresh local profiles")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        heading_row.addWidget(self._refresh_button)

        helper = QLabel(
            "New profiles start with all six gestures disabled. Creating one does not "
            "change the active profile."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        self._profile_list = QListWidget()
        self._profile_list.setObjectName("profileList")
        self._profile_list.setAccessibleName("Local binding profiles")
        self._profile_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._profile_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._profile_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._profile_list.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self._profile_list.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self._profile_list.setMinimumHeight(128)
        self._profile_list.setMaximumHeight(184)

        create_row = QHBoxLayout()
        create_row.setSpacing(8)
        self._name_input = QLineEdit()
        self._name_input.setObjectName("newProfileName")
        self._name_input.setAccessibleName("New profile name")
        self._name_input.setPlaceholderText("New profile name")
        self._create_button = QPushButton("Create disabled profile")
        self._create_button.setObjectName("createProfileButton")
        self._create_button.setAccessibleName("Create all-disabled profile")
        create_row.addWidget(self._name_input, stretch=1)
        create_row.addWidget(self._create_button)

        self._activate_button = QPushButton("Use selected profile and pause tracking")
        self._activate_button.setObjectName("activateProfileButton")
        self._activate_button.setAccessibleName("Use selected profile and pause tracking")
        self._activate_button.setProperty("primaryAction", True)

        self._storage_notice = QLabel(
            "Profile changes are unavailable in this session; the current snapshot remains visible."
        )
        self._storage_notice.setObjectName("warningBanner")
        self._storage_notice.setWordWrap(True)
        self._storage_notice.setVisible(not self._controller.can_manage)

        layout.addLayout(heading_row)
        layout.addWidget(helper)
        layout.addWidget(self._profile_list)
        layout.addLayout(create_row)
        layout.addWidget(self._activate_button)
        layout.addWidget(self._storage_notice)
        return panel

    def _build_binding_preview(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Active binding snapshot")
        heading.setObjectName("panelTitle")
        self._active_profile_value = QLabel("—")
        self._active_profile_value.setObjectName("activeProfileValue")
        self._active_profile_value.setWordWrap(True)
        self._active_profile_value.setAccessibleName("Active profile")
        helper = QLabel(
            "This preview is read-only in Phase 4D. Binding editing follows in the next "
            "iteration; no JSON editing is required for profile selection."
        )
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        self._binding_table = QTableWidget(len(BindableGesture), 2)
        self._binding_table.setObjectName("activeBindingsTable")
        self._binding_table.setAccessibleName("Active gesture bindings")
        self._binding_table.setHorizontalHeaderLabels(("Gesture", "Simulated action"))
        self._binding_table.verticalHeader().hide()
        self._binding_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._binding_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._binding_table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._binding_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        self._binding_table.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        header = self._binding_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._binding_table.setMinimumHeight(250)

        layout.addWidget(heading)
        layout.addWidget(self._active_profile_value)
        layout.addWidget(helper)
        layout.addWidget(self._binding_table)
        return panel

    def _connect_signals(self) -> None:
        self._controller.profiles_changed.connect(self._on_profiles_changed)
        self._controller.active_profile_changed.connect(self._on_active_profile_changed)
        self._controller.operation_finished.connect(self._on_operation_finished)
        self._profile_list.currentItemChanged.connect(self._on_selection_changed)
        self._name_input.textChanged.connect(self._update_controls)
        self._create_button.clicked.connect(self._create_profile)
        self._activate_button.clicked.connect(self._activate_selected)
        self._refresh_button.clicked.connect(self._controller.refresh)

    @Slot(object)
    def _on_profiles_changed(self, payload: object) -> None:
        self._render_names(profile_names(payload))

    @Slot(object)
    def _on_active_profile_changed(self, payload: object) -> None:
        self._render_active(binding_profile(payload))
        self._render_names(self._controller.profile_names)

    @Slot(object)
    def _on_operation_finished(self, payload: object) -> None:
        result = profile_operation(payload)
        self._show_result(result)
        if result.success and result.profile_name:
            self._select_profile(result.profile_name)
            self._name_input.clear()
        self._update_controls()

    @Slot()
    def _on_selection_changed(self) -> None:
        self._update_controls()

    @Slot()
    def _update_controls(self) -> None:
        can_manage = self._controller.can_manage
        selected = self._selected_profile_name()
        active = self._controller.active_profile.profile_name
        self._refresh_button.setEnabled(self._controller.storage_available)
        self._create_button.setEnabled(can_manage and bool(self._name_input.text().strip()))
        self._name_input.setEnabled(can_manage)
        self._activate_button.setEnabled(
            can_manage and selected is not None and selected.casefold() != active.casefold()
        )

    @Slot()
    def _create_profile(self) -> None:
        self._controller.create_disabled(self._name_input.text())

    @Slot()
    def _activate_selected(self) -> None:
        selected = self._selected_profile_name()
        if selected is not None:
            self._controller.activate(selected)

    def _render_names(self, names: tuple[str, ...]) -> None:
        selected = self._selected_profile_name()
        active = self._controller.active_profile.profile_name
        with QSignalBlocker(self._profile_list):
            self._profile_list.clear()
            for name in names:
                visible_name = _elide_middle(name)
                label = (
                    f"{visible_name} · Active"
                    if name.casefold() == active.casefold()
                    else visible_name
                )
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setToolTip(name)
                self._profile_list.addItem(item)
        self._select_profile(selected or active)
        self._update_controls()

    def _render_active(self, profile: BindingProfile) -> None:
        self._active_profile_value.setText(_elide_middle(profile.profile_name))
        self._active_profile_value.setToolTip(profile.profile_name)
        for row, gesture in enumerate(BindableGesture):
            gesture_item = QTableWidgetItem(gesture_label(gesture))
            action = action_label(profile.bindings[gesture])
            action_item = QTableWidgetItem(action)
            action_item.setToolTip(action)
            self._binding_table.setItem(row, 0, gesture_item)
            self._binding_table.setItem(row, 1, action_item)

    def _selected_profile_name(self) -> str | None:
        selected_items = self._profile_list.selectedItems()
        if not selected_items:
            return None
        item = selected_items[0]
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def _select_profile(self, profile_name: str) -> None:
        for row in range(self._profile_list.count()):
            item = self._profile_list.item(row)
            value = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(value, str) and value.casefold() == profile_name.casefold():
                self._profile_list.setCurrentRow(row)
                return

    def _show_result(self, result: ProfileOperationResult) -> None:
        status = "error" if not result.success else "warning" if result.warning else "success"
        self._feedback.setText(result.message)
        self._feedback.setProperty("feedbackStatus", status)
        self._feedback.style().unpolish(self._feedback)
        self._feedback.style().polish(self._feedback)
        self._feedback.show()


def _elide_middle(value: str) -> str:
    """Bound user profile names while retaining both identifying ends."""
    if len(value) <= _MAX_PROFILE_DISPLAY_CHARACTERS:
        return value
    visible_characters = _MAX_PROFILE_DISPLAY_CHARACTERS - 1
    prefix_length = (visible_characters + 1) // 2
    suffix_length = visible_characters // 2
    return f"{value[:prefix_length]}…{value[-suffix_length:]}"
