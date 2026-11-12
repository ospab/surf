"""Окно щита: сколько трекеров заблокировано и какие."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

try:
    from surf.i18n import tr
    from surf.utils.adblock import TrackingProtectionInterceptor
except ModuleNotFoundError:
    from i18n import tr
    from utils.adblock import TrackingProtectionInterceptor


class TrackingProtectionDialog(QDialog):
    """Показывает, какие трекеры и сколько раз были заблокированы за текущий сеанс."""

    def __init__(self, interceptor: TrackingProtectionInterceptor, parent=None):
        super().__init__(parent)
        self.interceptor = interceptor
        self.setWindowTitle(tr("shield_title"))
        self.setMinimumSize(420, 380)
        self._init_ui()
        self._refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.count_label = QLabel()
        self.count_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.count_label)

        layout.addWidget(QLabel(tr("shield_trackers_list")))

        self.trackers_list = QListWidget()
        self.trackers_list.setAlternatingRowColors(True)
        layout.addWidget(self.trackers_list, 1)

        buttons = QHBoxLayout()
        self.toggle_btn = QPushButton()
        self.toggle_btn.clicked.connect(self._toggle_protection)
        buttons.addWidget(self.toggle_btn)

        self.reset_btn = QPushButton(tr("btn_clear_list"))
        self.reset_btn.clicked.connect(self._reset)
        buttons.addWidget(self.reset_btn)

        buttons.addStretch()
        close_btn = QPushButton(tr("btn_close"))
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _refresh(self) -> None:
        count = self.interceptor.blocked_count
        self.count_label.setText(f"<h3>{tr('shield_title')}</h3><p>{tr('shield_blocked_text', count=count)}</p>")
        self.toggle_btn.setText(
            tr("shield_toggle_disable") if self.interceptor.is_enabled else tr("shield_toggle_enable")
        )

        self.trackers_list.clear()
        stats = sorted(self.interceptor.blocked_by_domain.items(), key=lambda item: item[1], reverse=True)
        if not stats:
            placeholder = QListWidgetItem(tr("shield_list_empty"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.trackers_list.addItem(placeholder)
            return
        for domain, hits in stats:
            self.trackers_list.addItem(f"{domain} — {tr('shield_requests', count=hits)}")

    def _toggle_protection(self) -> None:
        self.interceptor.is_enabled = not self.interceptor.is_enabled
        self._refresh()

    def _reset(self) -> None:
        self.interceptor.reset_count()
        self._refresh()
