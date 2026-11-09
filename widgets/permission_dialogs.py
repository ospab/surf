"""
Модуль системных запросов разрешений на устройства и медиа (Permissions & Device Prompts).
Реализует:
- Выпадающую панель разрешения устройств (PermissionPromptBar) для микрофона, камеры, геолокации и т.д.
- Диалог выбора экрана/окна для демонстрации (DesktopMediaDialog)
- Подтверждение доступа к файловой системе (FileSystemAccessDialog)
"""
import html
import os
from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWebEngineCore import (
    QWebEngineDesktopMediaRequest,
    QWebEngineFileSystemAccessRequest,
    QWebEnginePage,
    QWebEnginePermission,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.i18n import get_language, tr
except ModuleNotFoundError:
    from i18n import get_language, tr


def normalize_origin(url: QUrl) -> str:
    """Возвращает нормализованную строку security origin: scheme://host[:port]."""
    scheme = url.scheme() or "https"
    host = url.host()
    if not host:
        return url.toString()
    port = url.port()
    if port > 0 and port not in (80, 443):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def get_feature_info(feature_or_type, is_ru: bool) -> tuple[str, str, str]:
    """
    Возвращает (feature_key, human_description, icon_filename)
    по переданному типу разрешения или фичи.
    """
    type_str = str(feature_or_type).lower()

    if "audio" in type_str and "video" in type_str:
        return (
            "media",
            "доступ к микрофону и камере" if is_ru else "access to microphone and camera",
            "camera.svg",
        )
    elif "audio" in type_str:
        return (
            "audio",
            "доступ к микрофону" if is_ru else "access to your microphone",
            "mic.svg",
        )
    elif "video" in type_str:
        return (
            "video",
            "доступ к камере" if is_ru else "access to your camera",
            "camera.svg",
        )
    elif "desktop" in type_str or "screen" in type_str:
        return (
            "screen",
            "доступ к демонстрации экрана" if is_ru else "access to share your screen",
            "display.svg",
        )
    elif "geolocation" in type_str or "location" in type_str:
        return (
            "geolocation",
            "доступ к вашему местоположению" if is_ru else "access to your location",
            "map-pin.svg",
        )
    elif "notification" in type_str:
        return (
            "notifications",
            "разрешение отправлять уведомления" if is_ru else "permission to show notifications",
            "bell.svg",
        )
    elif "clipboard" in type_str:
        return (
            "clipboard",
            "доступ к буферу обмена" if is_ru else "access to your clipboard",
            "star.svg",
        )
    elif "font" in type_str:
        return (
            "fonts",
            "доступ к системным шрифтам" if is_ru else "access to local fonts",
            "globe.svg",
        )
    elif "mouselock" in type_str or "pointerlock" in type_str:
        return (
            "mouselock",
            "захват указателя мыши" if is_ru else "pointer lock",
            "shield.svg",
        )
    return (
        "device",
        "доступ к системному устройству" if is_ru else "access to device",
        "settings.svg",
    )


def load_themed_icon(icon_name: str, color_hex: str = "#fbfbfe", size: int = 18) -> QPixmap:
    """Загружает SVG иконку с динамической перекраской."""
    icon_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
    icon_path = os.path.join(icon_dir, icon_name)
    if not os.path.exists(icon_path):
        icon_path = os.path.join(icon_dir, "settings.svg")

    try:
        with open(icon_path, "r", encoding="utf-8") as f:
            svg_data = f.read()
        # Заменяем stroke="currentColor" на нужный цвет
        svg_data = svg_data.replace('stroke="currentColor"', f'stroke="{color_hex}"')
        svg_data = svg_data.replace('fill="currentColor"', f'fill="{color_hex}"')

        renderer = QSvgRenderer(svg_data.encode("utf-8"))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(2.0)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        return pix


class PermissionPromptBar(QWidget):
    """
    Выпадающая плашка-промпт запроса доступа к девайсам
    (микрофон, камера, геолокация, уведомления и т.д.)
    """

    allowed = pyqtSignal(bool)   # remember: bool
    denied = pyqtSignal(bool)    # remember: bool
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = True
        self._accent = "#0060df"
        self._current_origin = ""
        self._current_feature_key = ""
        self._on_allow_cb = None
        self._on_deny_cb = None
        self._on_dismiss_cb = None

        self._init_ui()
        self.hide()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # Иконка устройства
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(20, 20)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Текст запроса
        self.text_label = QLabel(self)
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setFont(QFont("-apple-system, BlinkMacSystemFont, Segoe UI, Roboto", 10))
        layout.addWidget(self.text_label, 1)

        # Чекбокс «Запомнить выбор»
        self.remember_cb = QCheckBox(self)
        self.remember_cb.setChecked(True)
        self.remember_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.remember_cb)

        # Кнопка Заблокировать
        self.btn_deny = QPushButton(self)
        self.btn_deny.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_deny.clicked.connect(self._on_deny_clicked)
        layout.addWidget(self.btn_deny)

        # Кнопка Разрешить
        self.btn_allow = QPushButton(self)
        self.btn_allow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_allow.clicked.connect(self._on_allow_clicked)
        layout.addWidget(self.btn_allow)

        # Кнопка закрыть (крестик)
        self.btn_close = QPushButton("×", self)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Закрыть")
        self.btn_close.clicked.connect(self._on_dismiss_clicked)
        layout.addWidget(self.btn_close)

        self._apply_style()

    def update_theme(self, is_dark: bool, accent: str = "#0060df") -> None:
        self._is_dark = is_dark
        self._accent = accent
        self._apply_style()

    def _apply_style(self) -> None:
        if self._is_dark:
            bg = "#23222b"
            border = "#3d3c4a"
            text_color = "#fbfbfe"
            deny_bg = "#2e2d38"
            deny_hover = "#393846"
            close_hover = "#393846"
        else:
            bg = "#f0f0f4"
            border = "#d1d1d6"
            text_color = "#15141a"
            deny_bg = "#ffffff"
            deny_hover = "#e5e5ea"
            close_hover = "#e5e5ea"

        self.setStyleSheet(f"""
            PermissionPromptBar {{
                background-color: {bg};
                border-bottom: 1px solid {border};
            }}
            QLabel {{
                color: {text_color};
            }}
            QCheckBox {{
                color: {text_color};
                font-size: 12px;
            }}
            QPushButton#allowBtn {{
                background-color: {self._accent};
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 5px 16px;
            }}
            QPushButton#allowBtn:hover {{
                opacity: 0.9;
                background-color: {self._accent};
            }}
            QPushButton#denyBtn {{
                background-color: {deny_bg};
                color: {text_color};
                font-size: 12px;
                border: 1px solid {border};
                border-radius: 6px;
                padding: 5px 14px;
            }}
            QPushButton#denyBtn:hover {{
                background-color: {deny_hover};
            }}
            QPushButton#closeBtn {{
                background: transparent;
                color: {text_color};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }}
            QPushButton#closeBtn:hover {{
                background-color: {close_hover};
            }}
        """)
        self.btn_allow.setObjectName("allowBtn")
        self.btn_deny.setObjectName("denyBtn")
        self.btn_close.setObjectName("closeBtn")

    def show_prompt(
        self,
        origin_str: str,
        feature_type,
        on_allow=None,
        on_deny=None,
        on_dismiss=None,
    ) -> None:
        """Показывает плашку запроса доступа к девайсу."""
        self._current_origin = origin_str
        is_ru = get_language() == "ru"

        feature_key, friendly_text, icon_name = get_feature_info(feature_type, is_ru)
        self._current_feature_key = feature_key
        self._on_allow_cb = on_allow
        self._on_deny_cb = on_deny
        self._on_dismiss_cb = on_dismiss

        clean_host = QUrl(origin_str).host() or origin_str

        # Текст
        if is_ru:
            self.text_label.setText(
                f"Сайт <b>{html.escape(clean_host)}</b> запрашивает {friendly_text}"
            )
            self.remember_cb.setText("Запомнить выбор")
            self.btn_allow.setText("Разрешить")
            self.btn_deny.setText("Заблокировать")
        else:
            self.text_label.setText(
                f"<b>{html.escape(clean_host)}</b> requests {friendly_text}"
            )
            self.remember_cb.setText("Remember decision")
            self.btn_allow.setText("Allow")
            self.btn_deny.setText("Block")

        # Иконка
        color = "#fbfbfe" if self._is_dark else "#15141a"
        pixmap = load_themed_icon(icon_name, color, size=18)
        self.icon_label.setPixmap(pixmap)

        self.remember_cb.setChecked(True)
        self._apply_style()
        self.show()

    def close_prompt(self) -> None:
        """Скрывает плашку и очищает колбэки."""
        self.hide()
        self._on_allow_cb = None
        self._on_deny_cb = None
        self._on_dismiss_cb = None
        self._current_origin = ""
        self._current_feature_key = ""

    def _on_allow_clicked(self) -> None:
        remember = self.remember_cb.isChecked()
        cb = self._on_allow_cb
        self.close_prompt()
        if cb:
            cb(remember)
        self.allowed.emit(remember)

    def _on_deny_clicked(self) -> None:
        remember = self.remember_cb.isChecked()
        cb = self._on_deny_cb
        self.close_prompt()
        if cb:
            cb(remember)
        self.denied.emit(remember)

    def _on_dismiss_clicked(self) -> None:
        cb = self._on_dismiss_cb
        self.close_prompt()
        if cb:
            cb()
        self.dismissed.emit()


class DesktopMediaDialog(QDialog):
    """
    Системный диалог выбора экрана или окна приложения для демонстрации (getDisplayMedia).
    """

    def __init__(self, request: QWebEngineDesktopMediaRequest, is_dark: bool = True, accent: str = "#0060df", parent=None):
        super().__init__(parent)
        self.request = request
        self._is_dark = is_dark
        self._accent = accent
        self._answered = False

        is_ru = get_language() == "ru"
        self.setWindowTitle("Демонстрация экрана" if is_ru else "Share Screen")
        self.resize(540, 420)
        self._init_ui(is_ru)

    def _init_ui(self, is_ru: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Вкладки: Экраны / Окна
        self.tabs = QTabWidget(self)

        # 1: Экраны
        self.screens_view = QListView(self)
        self.screens_view.setViewMode(QListView.ViewMode.IconMode)
        self.screens_view.setIconSize(QSize(120, 80))
        self.screens_view.setGridSize(QSize(140, 110))
        self.screens_view.setSpacing(10)
        self.screens_view.setMovement(QListView.Movement.Static)
        if self.request.screensModel():
            self.screens_view.setModel(self.request.screensModel())
            if self.request.screensModel().rowCount() > 0:
                self.screens_view.setCurrentIndex(self.request.screensModel().index(0, 0))

        self.tabs.addTab(self.screens_view, "Экраны" if is_ru else "Screens")

        # 2: Окна
        self.windows_view = QListView(self)
        self.windows_view.setViewMode(QListView.ViewMode.IconMode)
        self.windows_view.setIconSize(QSize(120, 80))
        self.windows_view.setGridSize(QSize(140, 110))
        self.windows_view.setSpacing(10)
        self.windows_view.setMovement(QListView.Movement.Static)
        if self.request.windowsModel():
            self.windows_view.setModel(self.request.windowsModel())
            if self.request.windowsModel().rowCount() > 0:
                self.windows_view.setCurrentIndex(self.request.windowsModel().index(0, 0))

        self.tabs.addTab(self.windows_view, "Окна программ" if is_ru else "Application Windows")
        layout.addWidget(self.tabs, 1)

        # Нижняя панель кнопок
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена" if is_ru else "Cancel", self)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_share = QPushButton("Поделиться" if is_ru else "Share", self)
        self.btn_share.setDefault(True)
        self.btn_share.clicked.connect(self._on_share)
        btn_layout.addWidget(self.btn_share)

        layout.addLayout(btn_layout)
        self._apply_style()

    def _apply_style(self) -> None:
        bg = "#1c1b22" if self._is_dark else "#f9f9fb"
        card_bg = "#2b2a33" if self._is_dark else "#ffffff"
        border = "#3d3c4a" if self._is_dark else "#d1d1d6"
        text = "#fbfbfe" if self._is_dark else "#15141a"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {text};
            }}
            QTabWidget::pane {{
                border: 1px solid {border};
                background-color: {card_bg};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {bg};
                color: {text};
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {card_bg};
                border: 1px solid {border};
                border-bottom: none;
                font-weight: 600;
            }}
            QListView {{
                background-color: {card_bg};
                border: none;
                color: {text};
            }}
            QListView::item:selected {{
                background-color: {self._accent};
                border-radius: 6px;
                color: #ffffff;
            }}
            QPushButton {{
                padding: 6px 18px;
                border-radius: 6px;
                font-size: 13px;
                border: 1px solid {border};
                background-color: {card_bg};
                color: {text};
            }}
            QPushButton:hover {{
                background-color: {border};
            }}
        """)
        self.btn_share.setStyleSheet(f"""
            background-color: {self._accent};
            color: #ffffff;
            font-weight: 600;
            border: none;
            padding: 6px 20px;
            border-radius: 6px;
        """)

    def _on_share(self) -> None:
        self._answered = True
        idx = self.tabs.currentIndex()
        if idx == 0:
            cur = self.screens_view.currentIndex()
            if cur.isValid():
                self.request.selectScreen(cur)
            else:
                self.request.cancel()
        else:
            cur = self.windows_view.currentIndex()
            if cur.isValid():
                self.request.selectWindow(cur)
            else:
                self.request.cancel()
        self.accept()

    def _on_cancel(self) -> None:
        self._answered = True
        self.request.cancel()
        self.reject()

    def closeEvent(self, event) -> None:
        if not self._answered:
            self._answered = True
            self.request.cancel()
        super().closeEvent(event)


class FileSystemAccessDialog(QDialog):
    """Подтверждение доступа к локальной файловой системе (FileSystemAccess API)."""

    def __init__(self, request: QWebEngineFileSystemAccessRequest, is_dark: bool = True, accent: str = "#0060df", parent=None):
        super().__init__(parent)
        self.request = request
        self._is_dark = is_dark
        self._accent = accent
        self._answered = False

        is_ru = get_language() == "ru"
        self.setWindowTitle("Доступ к файлу" if is_ru else "File Access")
        self.resize(460, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        origin_str = request.origin().toString()
        file_path = request.filePath()

        msg = QLabel(
            f"Сайт <b>{html.escape(origin_str)}</b> запрашивает доступ к файлу:<br><br>"
            f"<code>{html.escape(file_path)}</code>"
            if is_ru else
            f"Site <b>{html.escape(origin_str)}</b> requests access to file:<br><br>"
            f"<code>{html.escape(file_path)}</code>",
            self,
        )
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setWordWrap(True)
        layout.addWidget(msg, 1)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        btn_reject = QPushButton("Отклонить" if is_ru else "Deny", self)
        btn_reject.clicked.connect(self._on_reject)
        btn_box.addWidget(btn_reject)

        btn_accept = QPushButton("Разрешить" if is_ru else "Allow", self)
        btn_accept.setDefault(True)
        btn_accept.clicked.connect(self._on_accept)
        btn_box.addWidget(btn_accept)

        layout.addLayout(btn_box)

    def _on_accept(self) -> None:
        self._answered = True
        self.request.accept()
        self.accept()

    def _on_reject(self) -> None:
        self._answered = True
        self.request.reject()
        self.reject()

    def closeEvent(self, event) -> None:
        if not self._answered:
            self._answered = True
            self.request.reject()
        super().closeEvent(event)
