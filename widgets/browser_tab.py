import html
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from surf.database import Database
from surf.i18n import tr
from surf.widgets.reader_view import ReaderViewWidget


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
        logo_label.setStyleSheet("font-size: 46px; font-weight: 800; color: #fbfbfe; letter-spacing: 2px;")
        logo_layout.addWidget(logo_label)
        box_layout.addLayout(logo_layout)

        self.subtitle_label = QLabel(tr("app_subtitle"))
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("font-size: 13px; color: #8f8f9d; margin-bottom: 10px;")
        box_layout.addWidget(self.subtitle_label)

        # Поле поиска со скругленными краями (pill-shape)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("speedDialSearch")
        self.search_input.setPlaceholderText(tr("search_placeholder"))
        self.search_input.setMinimumHeight(48)
        self.search_input.returnPressed.connect(self._handle_search)
        box_layout.addWidget(self.search_input)

        main_layout.addWidget(center_box)

    def _handle_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        if "." in query and " " not in query:
            url = query if query.startswith("http://") or query.startswith("https://") else f"https://{query}"
        else:
            engine = self.db.get_setting("search_engine", "https://yandex.ru/search/?text=")
            url = f"{engine}{query}"
        self.open_url.emit(url)


class BrowserTab(QWidget):
    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(str)
    icon_changed = pyqtSignal(QIcon)
    load_progress = pyqtSignal(int)
    open_new_tab = pyqtSignal(str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_title = "Новая вкладка"
        self.current_url = ""
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Тема QT 5: Стопка клеток (QStackedWidget)
        self.stack = QStackedWidget()

        # 0: Веб-страница (QWebEngineView)
        self.web_view = QWebEngineView()
        self.browser_page = BrowserPage(QWebEngineProfile.defaultProfile(), self.web_view)
        self.web_view.setPage(self.browser_page)
        self.web_view.titleChanged.connect(self._on_title_changed)
        self.web_view.urlChanged.connect(self._on_url_changed)
        self.web_view.iconChanged.connect(self._on_icon_changed)
        self.web_view.loadProgress.connect(self.load_progress.emit)
        self.web_view.loadFinished.connect(self._on_load_finished)

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
                engine = self.db.get_setting("search_engine", "https://yandex.ru/search/?text=")
                url = f"{engine}{url}"

        self.stack.setCurrentIndex(0)
        self.web_view.load(QUrl(url))

    def show_speed_dial(self) -> None:
        self.stack.setCurrentIndex(1)
        self.current_title = "Новая вкладка"
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
        self.current_title = "Справка surf"
        self.current_url = "surf://help"
        self.title_changed.emit(self.current_title)
        self.url_changed.emit(self.current_url)

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
            "Сохранить скриншот страницы",
            "screenshot.png",
            "Изображения PNG (*.png);;Изображения JPEG (*.jpg *.jpeg)",
        )
        if file_path:
            pixmap.save(file_path)
            QMessageBox.information(self, "Скриншот сохранен", f"Снимок страницы сохранен:\n{file_path}")

    def _on_title_changed(self, title: str) -> None:
        if self.stack.currentIndex() == 0 and title:
            self.current_title = title
            self.title_changed.emit(title)
            if self.current_url:
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
        if ok and self.current_url and not self.current_url.startswith("surf://"):
            self.db.add_history_entry(self.current_url, self.current_title)
