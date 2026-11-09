import html
import urllib.parse
from urllib.parse import urlparse

from PyQt6.QtCore import QEvent, QPoint, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWebEngineCore import (
    QWebEngineContextMenuRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
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
except ModuleNotFoundError:
    from database import Database
    from i18n import tr
    from widgets.reader_view import ReaderViewWidget


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
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def createWindow(self, window_type):
        view = self.view()
        if view:
            win = view.window()
            if hasattr(win, "add_new_tab"):
                new_tab = win.add_new_tab()
                return new_tab.web_view.page()
        return super().createWindow(window_type)


class SpeedDialWidget(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("speedDialWidget")
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)

        center_box = QWidget()
        center_box.setMaximumWidth(680)
        box_layout = QVBoxLayout(center_box)
        box_layout.setSpacing(20)

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

        main_layout.addWidget(center_box)

    def retranslate_ui(self) -> None:
        self.subtitle_label.setText(tr("app_subtitle"))
        self.search_input.setPlaceholderText(tr("search_placeholder"))

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
        self.browser_page = BrowserPage(self.profile, self.web_view)
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

        if url.startswith("surf://help"):
            self.show_help()
            return

        if url.startswith("surf://newtab") or url == "about:blank":
            self.show_speed_dial()
            return

        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
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

    def show_normal_view(self) -> None:
        if self.current_url and not self.current_url.startswith("surf://"):
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
        if self.stack.currentIndex() == 0 and title:
            self.current_title = title
            self.title_changed.emit(title)
            if self.current_url and not self.profile.isOffTheRecord():
                self.db.add_history_entry(self.current_url, title)

    def _on_url_changed(self, qurl: QUrl) -> None:
        url_str = qurl.toString()
        if self.stack.currentIndex() == 0:
            self.current_url = url_str
            self.url_changed.emit(url_str)

    def _on_icon_changed(self, icon: QIcon) -> None:
        if self.stack.currentIndex() == 0:
            self.icon_changed.emit(icon)

    def _on_load_finished(self, ok: bool) -> None:
        if ok and self.current_url and not self.current_url.startswith("surf://") and not self.profile.isOffTheRecord():
            self.db.add_history_entry(self.current_url, self.current_title)
