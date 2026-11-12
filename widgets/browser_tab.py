import json
import re
import time
import urllib.parse
from urllib.parse import urlparse

from PyQt6.QtCore import QPoint, QRectF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineContextMenuRequest,
    QWebEngineDesktopMediaRequest,
    QWebEngineFileSystemAccessRequest,
    QWebEnginePage,
    QWebEnginePermission,
    QWebEngineProfile,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.database import Database
    from surf.i18n import tr
    from surf.utils.favicon_service import (
        FaviconService,
        create_circular_favicon_badge,
        generate_fallback_badge,
        get_clean_domain,
    )
    from surf.widgets.permission_dialogs import (
        DesktopMediaDialog,
        FileSystemAccessDialog,
        PermissionPromptBar,
        normalize_origin,
    )
    from surf.widgets.reader_view import ReaderViewWidget
except ModuleNotFoundError:
    from database import Database
    from i18n import tr
    from utils.favicon_service import (
        FaviconService,
        create_circular_favicon_badge,
        generate_fallback_badge,
        get_clean_domain,
    )
    from widgets.permission_dialogs import (
        DesktopMediaDialog,
        FileSystemAccessDialog,
        PermissionPromptBar,
        normalize_origin,
    )
    from widgets.reader_view import ReaderViewWidget


def format_search_url(engine_template: str, query: str) -> str:
    """Собирает адрес поиска. В шаблоне может быть %s, {query}, или запрос просто дописывается в конец."""
    encoded_query = urllib.parse.quote_plus(query)
    if "%s" in engine_template:
        return engine_template.replace("%s", encoded_query)
    elif "{query}" in engine_template:
        return engine_template.replace("{query}", encoded_query)
    else:
        if not (engine_template.endswith("=") or engine_template.endswith("/") or engine_template.endswith("?")):
            if "?" in engine_template:
                return f"{engine_template}&q={encoded_query}"
            else:
                return f"{engine_template}?q={encoded_query}"
        return f"{engine_template}{encoded_query}"


class BrowserPage(QWebEnginePage):
    def __init__(self, profile, parent=None, main_window=None, tab=None):
        super().__init__(profile, parent)
        self.main_window = main_window
        self.tab = tab

        # Запросы разрешений от сайта
        self.permissionRequested.connect(self._on_permission_requested)
        self.featurePermissionRequested.connect(self._on_feature_permission_requested)
        self.desktopMediaRequested.connect(self._on_desktop_media_requested)
        self.fileSystemAccessRequested.connect(self._on_file_system_access_requested)

    def _get_main_window(self):
        if self.main_window:
            return self.main_window
        p = self.parent()
        if p and hasattr(p, "window"):
            return p.window()
        return None

    def createWindow(self, window_type):
        win = self._get_main_window()
        if win and hasattr(win, "add_new_tab"):
            new_tab = win.add_new_tab()
            new_tab.stack.setCurrentIndex(0)
            return new_tab.web_view.page()
        return super().createWindow(window_type)

    def acceptNavigationRequest(self, url: QUrl, nav_type: QWebEnginePage.NavigationType, is_main_frame: bool) -> bool:
        modifiers = QApplication.keyboardModifiers()
        is_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        # Ctrl+клик по ссылке открывает её в новой вкладке
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked and is_ctrl:
            win = self._get_main_window()
            if win and hasattr(win, "add_new_tab"):
                win.add_new_tab(url.toString())
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def _permission_type_key(self, perm_type) -> str:
        s = str(perm_type).lower()
        if "audio" in s and "video" in s:
            return "media"
        elif "audio" in s:
            return "audio"
        elif "video" in s:
            return "video"
        elif "desktop" in s or "screen" in s:
            return "screen"
        elif "geolocation" in s or "location" in s:
            return "geolocation"
        elif "notification" in s:
            return "notifications"
        elif "clipboard" in s:
            return "clipboard"
        elif "font" in s:
            return "fonts"
        elif "mouselock" in s:
            return "mouselock"
        return "device"

    def _on_permission_requested(self, permission: QWebEnginePermission) -> None:
        origin_url = permission.origin()
        origin_str = normalize_origin(origin_url)
        feat_key = self._permission_type_key(permission.permissionType())

        db = self.tab.db if self.tab and hasattr(self.tab, "db") else None
        if db:
            if feat_key in ("media", "audio", "video"):
                dev_pref = db.get_site_device_preference(origin_str)
                if dev_pref:
                    if self.tab and hasattr(self.tab, "apply_device_config"):
                        self.tab.apply_device_config(dev_pref)
                    if dev_pref.get("allow_audio") or dev_pref.get("allow_video"):
                        permission.grant()
                    else:
                        permission.deny()
                    return

            saved = db.get_site_permission(origin_str, feat_key)
            if saved == "allow":
                if (
                    feat_key in ("media", "audio", "video")
                    and self.tab
                    and hasattr(self.tab, "apply_saved_device_preferences")
                ):
                    self.tab.apply_saved_device_preferences(origin_str)
                permission.grant()
                return
            elif saved == "deny":
                permission.deny()
                return

        if self.tab and hasattr(self.tab, "request_permission"):
            self.tab.request_permission(origin_str, feat_key, permission=permission)
        else:
            permission.grant()

    def _on_feature_permission_requested(self, security_origin: QUrl, feature: QWebEnginePage.Feature) -> None:
        origin_str = normalize_origin(security_origin)
        feat_key = self._permission_type_key(feature)

        db = self.tab.db if self.tab and hasattr(self.tab, "db") else None
        if db:
            if feat_key in ("media", "audio", "video"):
                dev_pref = db.get_site_device_preference(origin_str)
                if dev_pref:
                    if self.tab and hasattr(self.tab, "apply_device_config"):
                        self.tab.apply_device_config(dev_pref)
                    if dev_pref.get("allow_audio") or dev_pref.get("allow_video"):
                        self.setFeaturePermission(
                            security_origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                        )
                    else:
                        self.setFeaturePermission(
                            security_origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                        )
                    return

            saved = db.get_site_permission(origin_str, feat_key)
            if saved == "allow":
                if (
                    feat_key in ("media", "audio", "video")
                    and self.tab
                    and hasattr(self.tab, "apply_saved_device_preferences")
                ):
                    self.tab.apply_saved_device_preferences(origin_str)
                self.setFeaturePermission(
                    security_origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                )
                return
            elif saved == "deny":
                self.setFeaturePermission(
                    security_origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                )
                return

        if self.tab and hasattr(self.tab, "request_permission"):
            self.tab.request_permission(origin_str, feat_key, origin_url=security_origin, feature=feature)
        else:
            self.setFeaturePermission(security_origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)

    def _on_desktop_media_requested(self, request: QWebEngineDesktopMediaRequest) -> None:
        is_dark = True
        accent = "#0060df"
        if self.tab and hasattr(self.tab, "db"):
            is_dark = self.tab.db.get_setting("theme", "dark") == "dark"
            accent = self.tab.db.get_setting("accent_color", "#0060df")

        parent_win = self._get_main_window()
        dlg = DesktopMediaDialog(request, is_dark=is_dark, accent=accent, parent=parent_win)
        dlg.exec()

    def _on_file_system_access_requested(self, request: QWebEngineFileSystemAccessRequest) -> None:
        is_dark = True
        accent = "#0060df"
        if self.tab and hasattr(self.tab, "db"):
            is_dark = self.tab.db.get_setting("theme", "dark") == "dark"
            accent = self.tab.db.get_setting("accent_color", "#0060df")

        parent_win = self._get_main_window()
        dlg = FileSystemAccessDialog(request, is_dark=is_dark, accent=accent, parent=parent_win)
        dlg.exec()


def generate_tile_badge(title: str, url: str, is_add_btn: bool = False, is_dark: bool = True) -> QPixmap:
    """Круглый значок для плитки на новой вкладке."""
    if is_add_btn:
        pixmap = QPixmap(84, 84)
        pixmap.fill(Qt.GlobalColor.transparent)
        pixmap.setDevicePixelRatio(2.0)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle_rect = QRectF(2, 2, 38, 38)
        bg_col = QColor("#2a2a35" if is_dark else "#e5e5ea")
        border_col = QColor("#3f3f50" if is_dark else "#d1d1d6")
        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, 1.5))
        painter.drawEllipse(circle_rect)

        pen = QPen(QColor("#fbfbfe" if is_dark else "#15141a"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(21, 14, 21, 28)
        painter.drawLine(14, 21, 28, 21)
        painter.end()
        return pixmap

    cached_icon = FaviconService.instance().get_cached(url)
    if cached_icon is not None and not cached_icon.isNull():
        return create_circular_favicon_badge(cached_icon, is_dark=is_dark)

    domain = get_clean_domain(url)
    return generate_fallback_badge(title, domain, is_dark=is_dark)


class SpeedDialEditDialog(QDialog):
    """Окно добавления и изменения плитки."""

    def __init__(self, parent=None, title: str = "", url: str = "", is_new: bool = True):
        super().__init__(parent)
        self.is_new = is_new
        self.tile_title = title
        self.tile_url = url
        self.setObjectName("speedDialDialog")
        self.setWindowTitle(tr("speed_dial_dialog_add_title") if is_new else tr("speed_dial_dialog_edit_title"))
        self.setFixedWidth(400)
        self.setModal(True)
        self._init_ui(title, url)

    def _init_ui(self, title: str, url: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_name = QLabel(tr("speed_dial_name_label"))
        layout.addWidget(lbl_name)

        self.input_name = QLineEdit(title)
        self.input_name.setPlaceholderText(tr("speed_dial_name_placeholder"))
        self.input_name.setMinimumHeight(36)
        layout.addWidget(self.input_name)

        lbl_url = QLabel(tr("speed_dial_url_label"))
        layout.addWidget(lbl_url)

        self.input_url = QLineEdit(url)
        self.input_url.setPlaceholderText(tr("speed_dial_url_placeholder"))
        self.input_url.setMinimumHeight(36)
        self.input_url.returnPressed.connect(self._handle_save)
        layout.addWidget(self.input_url)

        layout.addSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setMinimumHeight(32)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(tr("btn_save"))
        self.btn_save.setObjectName("btnPrimary")
        self.btn_save.setMinimumHeight(32)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._handle_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _handle_save(self) -> None:
        url = self.input_url.text().strip()
        if not url:
            self.input_url.setFocus()
            return

        if not (
            url.startswith("http://")
            or url.startswith("https://")
            or url.startswith("surf://")
            or url.startswith("file://")
        ):
            url = f"https://{url}"

        name = self.input_name.text().strip()
        if not name:
            try:
                parsed = urlparse(url)
                name = parsed.netloc.replace("www.", "")
                if not name:
                    name = url
            except Exception:
                name = url

        self.tile_title = name
        self.tile_url = url
        self.accept()


class SpeedDialCard(QFrame):
    """Плитка сайта на новой вкладке."""

    clicked = pyqtSignal(str)
    open_new_tab = pyqtSignal(str)
    edit_requested = pyqtSignal(dict)
    delete_requested = pyqtSignal(dict)
    pin_requested = pyqtSignal(dict)

    def __init__(self, tile_data: dict, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.tile_data = tile_data
        self.is_dark = is_dark
        self._pressed = False
        self.domain = get_clean_domain(self.tile_data.get("url", ""))
        self.setObjectName("speedDialCard")
        self.setFixedSize(110, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

        # Когда скачается значок сайта, подменим картинку
        FaviconService.instance().favicon_loaded.connect(self._on_favicon_loaded)
        if self.domain:
            FaviconService.instance().request_favicon(self.domain)

    def _on_favicon_loaded(self, domain: str, pixmap: QPixmap) -> None:
        if domain == self.domain and not pixmap.isNull():
            badge = create_circular_favicon_badge(pixmap, is_dark=self.is_dark)
            self.icon_label.setPixmap(badge)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        pixmap = generate_tile_badge(
            self.tile_data.get("title", ""),
            self.tile_data.get("url", ""),
            is_add_btn=False,
            is_dark=self.is_dark,
        )
        self.icon_label.setPixmap(pixmap)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        title_text = self.tile_data.get("title", "")
        self.title_label = QLabel(self)
        self.title_label.setObjectName("speedDialCardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        metrics = QFontMetrics(self.title_label.font())
        elided = metrics.elidedText(title_text, Qt.TextElideMode.ElideRight, 96)
        self.title_label.setText(elided)
        layout.addWidget(self.title_label)

        url = self.tile_data.get("url", "")
        self.setToolTip(f"{title_text}\n{url}" if url else title_text)

        # Кнопка с тремя точками в углу
        self.menu_btn = QPushButton("···", self)
        self.menu_btn.setObjectName("tileMenuBtn")
        self.menu_btn.setFixedSize(20, 18)
        self.menu_btn.move(86, 3)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setToolTip(tr("speed_dial_edit"))
        self.menu_btn.clicked.connect(self._on_menu_clicked)

    def _on_menu_clicked(self) -> None:
        pos = self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height()))
        self._show_context_menu(pos)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit(self.tile_data.get("url", ""))
        super().mouseReleaseEvent(event)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)

        act_open = menu.addAction(tr("speed_dial_open"))
        act_open.triggered.connect(lambda: self.clicked.emit(self.tile_data.get("url", "")))

        act_tab = menu.addAction(tr("ctx_open_link_tab"))
        act_tab.triggered.connect(lambda: self.open_new_tab.emit(self.tile_data.get("url", "")))

        act_copy = menu.addAction(tr("ctx_copy_link"))
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(self.tile_data.get("url", "")))

        menu.addSeparator()

        if self.tile_data.get("is_fallback"):
            act_pin = menu.addAction(tr("speed_dial_pin"))
            act_pin.triggered.connect(lambda: self.pin_requested.emit(self.tile_data))
        else:
            act_edit = menu.addAction(tr("speed_dial_edit"))
            act_edit.triggered.connect(lambda: self.edit_requested.emit(self.tile_data))

        act_del = menu.addAction(tr("speed_dial_delete"))
        act_del.triggered.connect(lambda: self.delete_requested.emit(self.tile_data))

        menu.exec(global_pos)


class SpeedDialAddCard(QFrame):
    """Плитка добавления нового сайта (+)."""

    clicked = pyqtSignal()

    def __init__(self, is_dark: bool = True, parent=None):
        super().__init__(parent)
        self.is_dark = is_dark
        self._pressed = False
        self.setObjectName("speedDialAddCard")
        self.setFixedSize(110, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        pixmap = generate_tile_badge("", "", is_add_btn=True, is_dark=self.is_dark)
        self.icon_label.setPixmap(pixmap)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(tr("speed_dial_add"), self)
        self.title_label.setObjectName("speedDialAddTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title_label)

        self.setToolTip(tr("speed_dial_add"))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
        super().mouseReleaseEvent(event)


class SpeedDialWidget(QWidget):
    open_url = pyqtSignal(str)
    open_new_tab = pyqtSignal(str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("speedDialWidget")
        self._init_ui()
        self.refresh_tiles()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(40, 20, 40, 30)

        center_box = QWidget()
        center_box.setMaximumWidth(680)
        box_layout = QVBoxLayout(center_box)
        box_layout.setSpacing(18)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Логотип
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_label = QLabel("surf")
        logo_label.setObjectName("speedDialLogo")
        logo_layout.addWidget(logo_label)
        box_layout.addLayout(logo_layout)

        self.subtitle_label = QLabel(tr("app_subtitle"))
        self.subtitle_label.setObjectName("speedDialSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.subtitle_label)

        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setObjectName("speedDialSearch")
        self.search_input.setPlaceholderText(tr("search_placeholder"))
        self.search_input.setMinimumHeight(48)
        self.search_input.returnPressed.connect(self._handle_search)
        box_layout.addWidget(self.search_input)

        # Сетка плиток
        self.tiles_container = QWidget()
        self.tiles_container.setObjectName("speedDialContainer")
        self.tiles_layout = QGridLayout(self.tiles_container)
        self.tiles_layout.setSpacing(14)
        self.tiles_layout.setContentsMargins(0, 8, 0, 0)
        self.tiles_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        box_layout.addWidget(self.tiles_container)
        main_layout.addWidget(center_box)

    def refresh_tiles(self) -> None:
        """Заново строит сетку плиток."""
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        is_dark = self.db.get_setting("theme", "dark") == "dark"

        # Сначала закреплённые плитки из базы
        tiles = self.db.get_speed_dial_tiles()

        # Если их нет, показываем самые посещаемые сайты
        if not tiles:
            tiles = self.db.get_top_visited_sites(limit=6)

        columns = 4
        index = 0

        for tile in tiles:
            card = SpeedDialCard(tile, is_dark=is_dark, parent=self.tiles_container)
            card.clicked.connect(self.open_url.emit)
            card.open_new_tab.connect(self.open_new_tab.emit)
            card.edit_requested.connect(self._on_edit_tile)
            card.delete_requested.connect(self._on_delete_tile)
            card.pin_requested.connect(self._on_pin_tile)

            row = index // columns
            col = index % columns
            self.tiles_layout.addWidget(card, row, col)
            index += 1

        # Плитка «+»
        add_card = SpeedDialAddCard(is_dark=is_dark, parent=self.tiles_container)
        add_card.clicked.connect(self._on_add_tile)
        row = index // columns
        col = index % columns
        self.tiles_layout.addWidget(add_card, row, col)

    def _on_add_tile(self) -> None:
        dlg = SpeedDialEditDialog(self, title="", url="", is_new=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.db.add_speed_dial_tile(dlg.tile_title, dlg.tile_url)
            self.refresh_tiles()

    def _on_edit_tile(self, tile_data: dict) -> None:
        dlg = SpeedDialEditDialog(
            self,
            title=tile_data.get("title", ""),
            url=tile_data.get("url", ""),
            is_new=False,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tile_id = tile_data.get("id")
            if tile_id is not None:
                self.db.update_speed_dial_tile(tile_id, dlg.tile_title, dlg.tile_url)
            else:
                self.db.add_speed_dial_tile(dlg.tile_title, dlg.tile_url)
            self.refresh_tiles()

    def _on_delete_tile(self, tile_data: dict) -> None:
        tile_id = tile_data.get("id")
        if tile_id is not None:
            self.db.delete_speed_dial_tile(tile_id)
        else:
            url = tile_data.get("url")
            if url:
                self.db.delete_history_by_url(url)
        self.refresh_tiles()

    def _on_pin_tile(self, tile_data: dict) -> None:
        title = tile_data.get("title", "")
        url = tile_data.get("url", "")
        if url:
            self.db.add_speed_dial_tile(title, url)
            self.refresh_tiles()

    def retranslate_ui(self) -> None:
        self.subtitle_label.setText(tr("app_subtitle"))
        self.search_input.setPlaceholderText(tr("search_placeholder"))
        self.refresh_tiles()

    def _handle_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        if "." in query and " " not in query:
            url = query if query.startswith("http://") or query.startswith("https://") else f"https://{query}"
        else:
            engine = self.db.get_setting("search_engine", "https://www.google.com/search?q=")
            url = format_search_url(engine, query)
        self.open_url.emit(url)


class BrowserTab(QWidget):
    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(str)
    icon_changed = pyqtSignal(QIcon)
    load_progress = pyqtSignal(int)
    open_new_tab = pyqtSignal(str)
    audio_state_changed = pyqtSignal(bool, bool)
    pdf_saved = pyqtSignal(str)

    def __init__(self, db: Database, parent=None, profile: QWebEngineProfile | None = None):
        super().__init__(parent)
        self.main_window = parent
        self.db = db
        self.profile = profile or QWebEngineProfile.defaultProfile()
        self.current_title = tr("new_tab")
        self.current_url = ""
        # Когда вкладку последний раз открывали (для усыпления неактивных вкладок)
        self.last_active = time.monotonic()
        self._init_ui()

    def _init_ui(self) -> None:
        self._pending_perm_requests = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Плашка с запросом разрешения
        self.permission_bar = PermissionPromptBar(self)
        layout.addWidget(self.permission_bar)

        # Три экрана вкладки в QStackedWidget
        self.stack = QStackedWidget()

        # 0: страница
        self.web_view = QWebEngineView()
        self.browser_page = BrowserPage(self.profile, self.web_view, main_window=self.main_window, tab=self)
        self.web_view.setPage(self.browser_page)

        # Фон под цвет темы, чтобы при загрузке не мигало белым
        self._apply_background_color()

        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.iconChanged.connect(self._on_icon_changed)
        self.web_view.loadProgress.connect(self.load_progress.emit)
        self.web_view.loadFinished.connect(self._on_load_finished)

        # Своё контекстное меню и значок звука
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.web_view.customContextMenuRequested.connect(self._show_web_context_menu)
        self.browser_page.recentlyAudibleChanged.connect(self._on_audio_state_changed)
        self.browser_page.audioMutedChanged.connect(self._on_audio_state_changed)

        # 1: новая вкладка
        self.speed_dial = SpeedDialWidget(self.db)
        self.speed_dial.open_url.connect(self.load_url)
        self.speed_dial.open_new_tab.connect(self.open_new_tab.emit)

        # 2: режим чтения
        self.reader_view = ReaderViewWidget()
        self.reader_view.open_link.connect(self.load_url)
        self.reader_view.close_reader.connect(self.show_normal_view)

        self.stack.addWidget(self.web_view)  # Индекс 0
        self.stack.addWidget(self.speed_dial)  # Индекс 1
        self.stack.addWidget(self.reader_view)  # Индекс 2

        layout.addWidget(self.stack)
        self.show_speed_dial()

    def _apply_background_color(self) -> None:
        is_dark = self.db.get_setting("theme", "dark") == "dark"
        accent = self.db.get_setting("accent_color", "#0060df")
        col = QColor("#1c1b22" if is_dark else "#f2f2f7")
        self.web_view.page().setBackgroundColor(col)
        self.web_view.setStyleSheet(f"background-color: {col.name()};")
        if hasattr(self, "permission_bar"):
            self.permission_bar.update_theme(is_dark, accent)

    def _on_audio_state_changed(self) -> None:
        self.audio_state_changed.emit(
            self.browser_page.recentlyAudible(),
            self.browser_page.isAudioMuted(),
        )

    def toggle_audio_mute(self) -> None:
        muted = self.browser_page.isAudioMuted()
        self.browser_page.setAudioMuted(not muted)

    def _show_web_context_menu(self, pos: QPoint) -> None:
        req = self.web_view.lastContextMenuRequest()
        menu = QMenu(self)

        # Клик по ссылке
        if req and req.linkUrl().isValid() and req.linkUrl().toString():
            link_url = req.linkUrl().toString()
            act_tab = menu.addAction(tr("ctx_open_link_tab"))
            act_tab.triggered.connect(lambda: self.open_new_tab.emit(link_url))

            act_copy_link = menu.addAction(tr("ctx_copy_link"))
            act_copy_link.triggered.connect(lambda: QApplication.clipboard().setText(link_url))
            menu.addSeparator()

        # Клик по картинке
        if (
            req
            and req.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage
            and req.mediaUrl().isValid()
        ):
            img_url = req.mediaUrl().toString()
            act_img_tab = menu.addAction(tr("ctx_open_image_tab"))
            act_img_tab.triggered.connect(lambda: self.open_new_tab.emit(img_url))

            act_copy_img = menu.addAction(tr("ctx_copy_image_url"))
            act_copy_img.triggered.connect(lambda: QApplication.clipboard().setText(img_url))
            menu.addSeparator()

        # Выделен текст
        if req and req.selectedText():
            sel_text = req.selectedText().strip()
            act_copy = menu.addAction(tr("ctx_copy"))
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(sel_text))

            act_search = menu.addAction(tr("ctx_search_web", text=sel_text[:20]))
            act_search.triggered.connect(lambda: self._search_selected_text(sel_text))
            menu.addSeparator()

        # Остальные пункты
        act_back = menu.addAction(tr("tip_back"))
        act_back.setEnabled(self.web_view.history().canGoBack())
        act_back.triggered.connect(self.web_view.back)

        act_fwd = menu.addAction(tr("tip_forward"))
        act_fwd.setEnabled(self.web_view.history().canGoForward())
        act_fwd.triggered.connect(self.web_view.forward)

        act_reload = menu.addAction(tr("tip_reload"))
        act_reload.triggered.connect(self.web_view.reload)

        menu.addSeparator()
        act_save = menu.addAction(tr("act_save_page"))
        act_save.triggered.connect(self.save_page_pdf)

        act_reader = menu.addAction(tr("act_reader"))
        act_reader.triggered.connect(self.toggle_reader_mode)

        act_shot = menu.addAction(tr("act_screenshot"))
        act_shot.triggered.connect(self.capture_screenshot)

        menu.exec(self.web_view.mapToGlobal(pos))

    def _search_selected_text(self, text: str) -> None:
        engine = self.db.get_setting("search_engine", "https://www.google.com/search?q=")
        url = format_search_url(engine, text)
        self.open_new_tab.emit(url)

    def load_url(self, url: str) -> None:
        url = url.strip()
        if not url:
            return

        if url.startswith("surf://newtab") or url == "about:blank":
            self.show_speed_dial()
            return

        if not (
            url.startswith("http://")
            or url.startswith("https://")
            or url.startswith("file://")
            or url.startswith("surf://")
        ):
            if "." in url and " " not in url:
                url = f"https://{url}"
            else:
                engine = self.db.get_setting("search_engine", "https://www.google.com/search?q=")
                url = format_search_url(engine, url)

        self.current_url = url
        self.stack.setCurrentIndex(0)
        self.web_view.load(QUrl(url))
        self.url_changed.emit(url)

    def show_speed_dial(self) -> None:
        self.stack.setCurrentIndex(1)
        self.current_title = tr("new_tab")
        self.current_url = "surf://newtab"
        self.title_changed.emit(self.current_title)
        self.url_changed.emit("")
        self.speed_dial.refresh_tiles()

    def show_normal_view(self) -> None:
        if self.current_url and not self.current_url.startswith("surf://newtab"):
            self.stack.setCurrentIndex(0)
        else:
            self.show_speed_dial()

    def show_help(self) -> None:
        self.reader_view.set_help_content()
        self.stack.setCurrentIndex(2)
        self.current_title = tr("act_help")
        self.current_url = "surf://help"
        self.title_changed.emit(self.current_title)
        self.url_changed.emit(self.current_url)

    def retranslate_ui(self) -> None:
        self.speed_dial.retranslate_ui()
        if self.stack.currentIndex() == 1:
            self.current_title = tr("new_tab")
            self.title_changed.emit(self.current_title)

    def set_theme_mode(self, is_dark: bool) -> None:
        if hasattr(self, "reader_view"):
            self.reader_view.set_theme_mode(is_dark)
        if hasattr(self, "speed_dial"):
            self.speed_dial.refresh_tiles()

    def toggle_reader_mode(self) -> None:
        if self.stack.currentIndex() == 2:
            self.show_normal_view()
            return

        js_code = """
        (function() {
            var article = document.querySelector('article') || document.querySelector('.article')
                || document.querySelector('main') || document.body;
            var clone = article.cloneNode(true);
            var toRemove = clone.querySelectorAll('script, style, nav, footer, header, aside, .ads, .ad, iframe');
            for (var i = 0; i < toRemove.length; i++) {
                toRemove[i].remove();
            }
            return {
                title: document.title,
                html: clone.innerHTML
            };
        })();
        """

        def handle_extracted(data):
            if isinstance(data, dict):
                title = data.get("title", self.current_title)
                content = data.get("html", "")
                self.reader_view.set_article(title, content, self.current_url)
                self.stack.setCurrentIndex(2)

        self.web_view.page().runJavaScript(js_code, handle_extracted)

    def show_page_source(self) -> None:
        def handle_source(html_text):
            self.reader_view.set_source_code(self.current_title, html_text, self.current_url)
            self.stack.setCurrentIndex(2)

        self.web_view.page().toHtml(handle_source)

    def save_page_pdf(self) -> None:
        """Сохраняет текущую страницу в PDF (меню «Файл», Ctrl+S и контекстное меню страницы)."""
        if not self.current_url or self.stack.currentIndex() != 0:
            return
        safe_title = re.sub(r'[\\/:*?"<>|]+', " ", self.current_title).strip()[:80] or "page"
        path, _ = QFileDialog.getSaveFileName(self, tr("save_pdf_dialog"), f"{safe_title}.pdf", "PDF (*.pdf)")
        if path:
            self.web_view.page().printToPdf(path)
            self.pdf_saved.emit(path)

    def capture_screenshot(self) -> None:
        pixmap = self.web_view.grab()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_screenshot_dialog"),
            "screenshot.png",
            "PNG (*.png);;JPEG (*.jpg *.jpeg)",
        )
        if file_path:
            pixmap.save(file_path)
            QMessageBox.information(self, tr("screenshot_saved_title"), tr("screenshot_saved_msg", path=file_path))

    def _on_title_changed(self, title: str) -> None:
        if title:
            self.current_title = title
            self.title_changed.emit(title)
            # Только обновляем заголовок: посещение засчитывается один раз в _on_load_finished
            if self.current_url and not self.current_url.startswith("surf://") and not self.profile.isOffTheRecord():
                self.db.update_history_title(self.current_url, title)

    def _on_url_changed(self, qurl: QUrl) -> None:
        url_str = qurl.toString()
        if not url_str or url_str == "about:blank":
            return

        if hasattr(self, "permission_bar") and self.permission_bar.isVisible():
            new_origin = normalize_origin(qurl)
            if self.permission_bar._current_origin != new_origin:
                self.permission_bar.close_prompt()

        if url_str.startswith("surf://newtab"):
            self.show_speed_dial()
            return

        self.current_url = url_str
        self.stack.setCurrentIndex(0)
        self.url_changed.emit(url_str)

    def apply_device_config(self, config: dict) -> None:
        """Передаёт странице, какие микрофон и камеру использовать."""
        try:
            cfg_json = json.dumps(
                {
                    "allow_audio": bool(config.get("allow_audio", True)),
                    "selected_audio": str(config.get("selected_audio") or config.get("audio_device") or ""),
                    "allow_video": bool(config.get("allow_video", True)),
                    "selected_video": str(config.get("selected_video") or config.get("video_device") or ""),
                }
            )
            js_code = f"if (window.__surf_set_media_config) {{ window.__surf_set_media_config({cfg_json}); }}"
            self.browser_page.runJavaScript(js_code)
        except Exception:
            pass

    def apply_saved_device_preferences(self, url_str: str) -> None:
        """Ставит устройства, сохранённые для сайта, или устройства по умолчанию."""
        if not url_str or url_str.startswith("surf://") or url_str == "about:blank":
            return
        origin_str = normalize_origin(QUrl(url_str))
        dev_pref = self.db.get_site_device_preference(origin_str) if self.db else None
        if dev_pref:
            self.apply_device_config(dev_pref)
        else:
            def_audio = self.db.get_setting("default_audio_device", "") if self.db else ""
            def_video = self.db.get_setting("default_video_device", "") if self.db else ""
            if def_audio or def_video:
                self.apply_device_config(
                    {
                        "allow_audio": True,
                        "selected_audio": def_audio,
                        "allow_video": True,
                        "selected_video": def_video,
                    }
                )

    def request_permission(
        self,
        origin_str: str,
        feat_key: str,
        permission: QWebEnginePermission = None,
        origin_url: QUrl = None,
        feature: QWebEnginePage.Feature = None,
    ) -> None:
        """Показывает плашку с запросом разрешения и запоминает ответ."""
        req_key = f"{origin_str}:{feat_key}"
        if req_key not in self._pending_perm_requests:
            self._pending_perm_requests[req_key] = []

        item = {"permission": permission, "origin_url": origin_url, "feature": feature}
        self._pending_perm_requests[req_key].append(item)

        # Плашка для такого запроса уже висит, просто запомним его
        if hasattr(self, "permission_bar") and self.permission_bar.isVisible():
            if (
                self.permission_bar._current_origin == origin_str
                and self.permission_bar._current_feature_key == feat_key
            ):
                return

        def on_allow(result):
            if isinstance(result, dict):
                allow_audio = result.get("allow_audio", True)
                selected_audio = result.get("selected_audio", "")
                allow_video = result.get("allow_video", True)
                selected_video = result.get("selected_video", "")
                remember = result.get("remember", False)

                self.apply_device_config(result)

                if remember and self.db:
                    self.db.set_site_device_preference(
                        origin_str,
                        audio_device=selected_audio,
                        video_device=selected_video,
                        allow_audio=allow_audio,
                        allow_video=allow_video,
                    )
                    self.db.set_site_permission(
                        origin_str,
                        feat_key,
                        "allow" if (allow_audio or allow_video) else "deny",
                    )

                should_grant = bool(allow_audio or allow_video)
            else:
                should_grant = True
                remember = bool(result)
                if remember and self.db:
                    self.db.set_site_permission(origin_str, feat_key, "allow")

            items = self._pending_perm_requests.pop(req_key, [])
            for req in items:
                if req["permission"]:
                    try:
                        if should_grant:
                            req["permission"].grant()
                        else:
                            req["permission"].deny()
                    except Exception:
                        pass
                if req["origin_url"] and req["feature"] is not None:
                    try:
                        policy = (
                            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                            if should_grant
                            else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
                        )
                        self.browser_page.setFeaturePermission(req["origin_url"], req["feature"], policy)
                    except Exception:
                        pass

        def on_deny(remember: bool):
            items = self._pending_perm_requests.pop(req_key, [])
            for req in items:
                if req["permission"]:
                    try:
                        req["permission"].deny()
                    except Exception:
                        pass
                if req["origin_url"] and req["feature"] is not None:
                    try:
                        self.browser_page.setFeaturePermission(
                            req["origin_url"],
                            req["feature"],
                            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
                        )
                    except Exception:
                        pass
            if remember and self.db:
                self.db.set_site_permission(origin_str, feat_key, "deny")
                if feat_key in ("media", "audio", "video"):
                    self.db.set_site_device_preference(
                        origin_str,
                        audio_device="",
                        video_device="",
                        allow_audio=False,
                        allow_video=False,
                    )

        def on_dismiss():
            items = self._pending_perm_requests.pop(req_key, [])
            for req in items:
                if req["permission"]:
                    try:
                        req["permission"].deny()
                    except Exception:
                        pass
                if req["origin_url"] and req["feature"] is not None:
                    try:
                        self.browser_page.setFeaturePermission(
                            req["origin_url"],
                            req["feature"],
                            QWebEnginePage.PermissionPolicy.PermissionDeniedByUser,
                        )
                    except Exception:
                        pass

        if hasattr(self, "permission_bar"):
            is_dark = self.db.get_setting("theme", "dark") == "dark"
            accent = self.db.get_setting("accent_color", "#0060df")
            self.permission_bar.update_theme(is_dark, accent)
            self.permission_bar.show_prompt(
                origin_str=origin_str,
                feature_type=feat_key,
                on_allow=on_allow,
                on_deny=on_deny,
                on_dismiss=on_dismiss,
            )
        else:
            on_allow(False)

    def _on_icon_changed(self, icon: QIcon) -> None:
        self.icon_changed.emit(icon)
        if self.current_url and not self.current_url.startswith("surf://"):
            pix = icon.pixmap(64, 64)
            if not pix.isNull():
                FaviconService.instance().save_to_cache(self.current_url, pix)

    def _on_load_finished(self, ok: bool) -> None:
        if ok and self.current_url and not self.current_url.startswith("surf://"):
            self.apply_saved_device_preferences(self.current_url)
            if not self.profile.isOffTheRecord():
                self.db.add_history_entry(self.current_url, self.current_title)
