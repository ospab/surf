import html
import urllib.parse
from urllib.parse import urlparse

from PyQt6.QtCore import QEvent, QPoint, QRectF, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineContextMenuRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
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
    from surf.widgets.reader_view import ReaderViewWidget
    from surf.utils.favicon_service import (
        FaviconService,
        create_circular_favicon_badge,
        generate_fallback_badge,
        get_clean_domain,
    )
except ModuleNotFoundError:
    from database import Database
    from i18n import tr
    from widgets.reader_view import ReaderViewWidget
    from utils.favicon_service import (
        FaviconService,
        create_circular_favicon_badge,
        generate_fallback_badge,
        get_clean_domain,
    )


def format_search_url(engine_template: str, query: str) -> str:
    """Форматирует URL поискового запроса с поддержкой шаблонов %s, {query} и прямого добавления."""
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
    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window

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
        # Если клик по ссылке был с зажатой клавишей Ctrl — открываем в новой вкладке
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked and is_ctrl:
            win = self._get_main_window()
            if win and hasattr(win, "add_new_tab"):
                win.add_new_tab(url.toString())
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


def generate_tile_badge(title: str, url: str, is_add_btn: bool = False, is_dark: bool = True) -> QPixmap:
    """Генерирует высокочеткую круглую иконку для плитки быстрого доступа."""
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
    """Модальное окно добавления или редактирования плитки быстрого доступа."""

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

        # Поле Название
        lbl_name = QLabel(tr("speed_dial_name_label"))
        layout.addWidget(lbl_name)

        self.input_name = QLineEdit(title)
        self.input_name.setPlaceholderText(tr("speed_dial_name_placeholder"))
        self.input_name.setMinimumHeight(36)
        layout.addWidget(self.input_name)

        # Поле URL
        lbl_url = QLabel(tr("speed_dial_url_label"))
        layout.addWidget(lbl_url)

        self.input_url = QLineEdit(url)
        self.input_url.setPlaceholderText(tr("speed_dial_url_placeholder"))
        self.input_url.setMinimumHeight(36)
        self.input_url.returnPressed.connect(self._handle_save)
        layout.addWidget(self.input_url)

        layout.addSpacing(6)

        # Кнопки действия
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

        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("surf://") or url.startswith("file://")):
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
    """Интерактивная плитка веб-сайта с реальной фавиконкой с сайта."""

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

        # Автоматическое подтягивание фавиконки сайта
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

        # Круглая иконка
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

        # Название сайта
        title_text = self.tile_data.get("title", "")
        self.title_label = QLabel(self)
        self.title_label.setObjectName("speedDialCardTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        metrics = QFontMetrics(self.title_label.font())
        elided = metrics.elidedText(title_text, Qt.TextElideMode.ElideRight, 96)
        self.title_label.setText(elided)
        layout.addWidget(self.title_label)

        # Подсказка с полным адресом
        url = self.tile_data.get("url", "")
        self.setToolTip(f"{title_text}\n{url}" if url else title_text)

        # Кнопка меню (три точки) в верхнем правом углу
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

        # Круг с плюсом
        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        pixmap = generate_tile_badge("", "", is_add_btn=True, is_dark=self.is_dark)
        self.icon_label.setPixmap(pixmap)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        # Текст Добавить
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

        # Минималистичный логотип surf
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

        # Поле поиска со скругленными краями (pill-shape)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("speedDialSearch")
        self.search_input.setPlaceholderText(tr("search_placeholder"))
        self.search_input.setMinimumHeight(48)
        self.search_input.returnPressed.connect(self._handle_search)
        box_layout.addWidget(self.search_input)

        # Сетка плиток быстрого доступа
        self.tiles_container = QWidget()
        self.tiles_container.setObjectName("speedDialContainer")
        self.tiles_layout = QGridLayout(self.tiles_container)
        self.tiles_layout.setSpacing(14)
        self.tiles_layout.setContentsMargins(0, 8, 0, 0)
        self.tiles_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        box_layout.addWidget(self.tiles_container)
        main_layout.addWidget(center_box)

    def refresh_tiles(self) -> None:
        """Перезагружает сетку плиток из БД (или топа истории) с кнопкой добавления."""
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        is_dark = self.db.get_setting("theme", "dark") == "dark"

        # 1. Загрузка закрепленных плиток из базы данных
        tiles = self.db.get_speed_dial_tiles()

        # 2. Если закрепленных плиток нет, автоматически отображаем топ посещаемых сайтов
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

        # Плитка добавления (+)
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
                with self.db._get_connection() as conn:
                    conn.cursor().execute("DELETE FROM history WHERE url = ?", (url,))
                    conn.commit()
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

    def __init__(self, db: Database, parent=None, profile: QWebEngineProfile | None = None):
        super().__init__(parent)
        self.main_window = parent
        self.db = db
        self.profile = profile or QWebEngineProfile.defaultProfile()
        self.current_title = tr("new_tab")
        self.current_url = ""
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Стопка клеток (QStackedWidget)
        self.stack = QStackedWidget()

        # 0: Веб-страница (QWebEngineView)
        self.web_view = QWebEngineView()
        self.browser_page = BrowserPage(self.profile, self.web_view, main_window=self.main_window)
        self.web_view.setPage(self.browser_page)

        # Устранение белой вспышки (White Flash)
        self._apply_background_color()

        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.iconChanged.connect(self._on_icon_changed)
        self.web_view.loadProgress.connect(self.load_progress.emit)
        self.web_view.loadFinished.connect(self._on_load_finished)

        # Контекстное меню и отслеживание аудио
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.web_view.customContextMenuRequested.connect(self._show_web_context_menu)
        self.browser_page.recentlyAudibleChanged.connect(self._on_audio_state_changed)
        self.browser_page.audioMutedChanged.connect(self._on_audio_state_changed)

        # 1: Стартовая панель быстрого поиска
        self.speed_dial = SpeedDialWidget(self.db)
        self.speed_dial.open_url.connect(self.load_url)
        self.speed_dial.open_new_tab.connect(self.open_new_tab.emit)

        # 2: Режим чтения (QTextBrowser)
        self.reader_view = ReaderViewWidget()
        self.reader_view.open_link.connect(self.load_url)
        self.reader_view.close_reader.connect(self.show_normal_view)

        self.stack.addWidget(self.web_view)      # Индекс 0
        self.stack.addWidget(self.speed_dial)     # Индекс 1
        self.stack.addWidget(self.reader_view)    # Индекс 2

        layout.addWidget(self.stack)
        self.show_speed_dial()

    def _apply_background_color(self) -> None:
        is_dark = self.db.get_setting("theme", "dark") == "dark"
        col = QColor("#1c1b22" if is_dark else "#f2f2f7")
        self.web_view.page().setBackgroundColor(col)
        self.web_view.setStyleSheet(f"background-color: {col.name()};")

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

        # 1. Если клик по ссылке
        if req and req.linkUrl().isValid() and req.linkUrl().toString():
            link_url = req.linkUrl().toString()
            act_tab = menu.addAction(tr("ctx_open_link_tab"))
            act_tab.triggered.connect(lambda: self.open_new_tab.emit(link_url))

            act_copy_link = menu.addAction(tr("ctx_copy_link"))
            act_copy_link.triggered.connect(lambda: QApplication.clipboard().setText(link_url))
            menu.addSeparator()

        # 2. Если клик по изображению
        if req and req.mediaType() == QWebEngineContextMenuRequest.MediaType.MediaTypeImage and req.mediaUrl().isValid():
            img_url = req.mediaUrl().toString()
            act_img_tab = menu.addAction(tr("ctx_open_image_tab"))
            act_img_tab.triggered.connect(lambda: self.open_new_tab.emit(img_url))

            act_copy_img = menu.addAction(tr("ctx_copy_image_url"))
            act_copy_img.triggered.connect(lambda: QApplication.clipboard().setText(img_url))
            menu.addSeparator()

        # 3. Если выделен текст
        if req and req.selectedText():
            sel_text = req.selectedText().strip()
            act_copy = menu.addAction(tr("ctx_copy"))
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(sel_text))

            act_search = menu.addAction(tr("ctx_search_web", text=sel_text[:20]))
            act_search.triggered.connect(lambda: self._search_selected_text(sel_text))
            menu.addSeparator()

        # 4. Навигация и общие действия
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
        act_save.triggered.connect(self._save_page_pdf)

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

        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://") or url.startswith("surf://")):
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
            var article = document.querySelector('article') || document.querySelector('.article') || document.querySelector('main') || document.body;
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
            if self.current_url and not self.current_url.startswith("surf://") and not self.profile.isOffTheRecord():
                self.db.add_history_entry(self.current_url, title)

    def _on_url_changed(self, qurl: QUrl) -> None:
        url_str = qurl.toString()
        if not url_str or url_str == "about:blank":
            return

        if url_str.startswith("surf://newtab"):
            self.show_speed_dial()
            return

        self.current_url = url_str
        self.stack.setCurrentIndex(0)
        self.url_changed.emit(url_str)

    def _on_icon_changed(self, icon: QIcon) -> None:
        self.icon_changed.emit(icon)
        if self.current_url and not self.current_url.startswith("surf://"):
            pix = icon.pixmap(64, 64)
            if not pix.isNull():
                FaviconService.instance().save_to_cache(self.current_url, pix)

    def _on_load_finished(self, ok: bool) -> None:
        if ok and self.current_url and not self.current_url.startswith("surf://") and not self.profile.isOffTheRecord():
            self.db.add_history_entry(self.current_url, self.current_title)
