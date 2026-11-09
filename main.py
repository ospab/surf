import os
import sys

# Поддержка прямого запуска 'python ./main.py' из папки проекта,
# а также запуска как модуля 'python -m surf.main' из внешнего каталога
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from PyQt6.QtCore import QByteArray, QEvent, QObject, QPoint, QSize, QStringListModel, Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtNetwork import QNetworkProxy
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.database import Database
    from surf.i18n import get_language, set_language, tr
    from surf.widgets.browser_tab import BrowserTab
    from surf.widgets.download_manager import DownloadManagerDialog
    from surf.widgets.history_dialog import HistoryDialog
    from surf.widgets.settings_dialog import SettingsDialog
except ModuleNotFoundError:
    from database import Database
    from i18n import get_language, set_language, tr
    from widgets.browser_tab import BrowserTab
    from widgets.download_manager import DownloadManagerDialog
    from widgets.history_dialog import HistoryDialog
    from widgets.settings_dialog import SettingsDialog


class ZoomWheelFilter(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            delta = event.angleDelta().y()
            if delta > 0:
                self.main_window._zoom_in()
            elif delta < 0:
                self.main_window._zoom_out()
            return True
        return False


class ClosableTabBar(QTabBar):
    """Панель вкладок с контрастной кнопкой закрытия и правильными отступами."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(False)
        self._is_dark = True
        icon_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
        self._close_icon_dark = QIcon(os.path.join(icon_dir, "close_dark.svg"))
        self._close_icon_light = QIcon(os.path.join(icon_dir, "close_light.svg"))

    def set_theme_mode(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        icon = self._close_icon_dark if is_dark else self._close_icon_light
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn and isinstance(btn, QToolButton):
                btn.setIcon(icon)

    def retranslate_close_buttons(self) -> None:
        tip = tr("act_close_tab")
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn and isinstance(btn, QToolButton):
                btn.setToolTip(tip)

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        btn = QToolButton(self)
        btn.setObjectName("tabCloseBtn")
        btn.setIcon(self._close_icon_dark if self._is_dark else self._close_icon_light)
        btn.setIconSize(QSize(12, 12))
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tr("act_close_tab"))
        btn.clicked.connect(lambda _, b=btn: self._on_close_clicked(b))
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)

    def _on_close_clicked(self, btn: QToolButton) -> None:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) == btn:
                self.tabCloseRequested.emit(i)
                break

    def tabLayoutChange(self) -> None:
        super().tabLayoutChange()
        self._adjust_close_buttons()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adjust_close_buttons()

    def paintEvent(self, event) -> None:
        self._adjust_close_buttons()
        super().paintEvent(event)

    def _adjust_close_buttons(self) -> None:
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn:
                r = self.tabRect(i)
                # Отступ 8px от правого края вкладки, чтобы не налезать на скругление
                target_x = r.right() - btn.width() - 8
                target_y = r.top() + (r.height() - btn.height()) // 2
                if btn.x() != target_x or btn.y() != target_y:
                    btn.move(target_x, target_y)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("surf")
        self.resize(1200, 800)

        self.db = Database()
        self.zoom_factor = 1.0
        self._active_downloads: list[QWebEngineDownloadRequest] = []
        self._recently_closed_urls: list[str] = []

        # Инициализация языка интерфейса
        user_lang = self.db.get_setting("language", "ru")
        set_language(user_lang)

        self._setup_network_and_profile()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_downloads()
        self._apply_theme()
        self._apply_menu_visibility()
        self._retranslate_ui()

        # Глобальный фильтр колесика мыши с зажатым Ctrl для масштабирования
        self.zoom_filter = ZoomWheelFilter(self)
        app = QApplication.instance()
        if app:
            app.installEventFilter(self.zoom_filter)

        self.add_new_tab()

    def _get_icon(self, name: str) -> QIcon:
        is_dark = self.db.get_setting("theme", "dark") == "dark"
        return self._render_themed_icon(name, is_dark)

    def _render_themed_icon(self, name: str, is_dark: bool) -> QIcon:
        path = os.path.join(os.path.dirname(__file__), "resources", "icons", f"{name}.svg")
        if not os.path.exists(path):
            return QIcon()

        try:
            with open(path, "r", encoding="utf-8") as f:
                svg_text = f.read()
        except Exception:
            return QIcon(path)

        stroke_color = "#fbfbfe" if is_dark else "#15141a"
        if not is_dark:
            svg_text = svg_text.replace("#cfcfd8", stroke_color)
            svg_text = svg_text.replace("#ffffff", stroke_color)
            svg_text = svg_text.replace('stroke="white"', f'stroke="{stroke_color}"')
            if name == "star_filled":
                accent = self.db.get_setting("accent_color", "#e5a50a")
                svg_text = svg_text.replace('fill="#f5c518"', f'fill="{accent}"')
        else:
            svg_text = svg_text.replace("#15141a", stroke_color)
            svg_text = svg_text.replace("#2b2a33", stroke_color)
            if name == "star_filled":
                accent = self.db.get_setting("accent_color", "#f5c518")
                svg_text = svg_text.replace('fill="#e5a50a"', f'fill="{accent}"')

        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        icon = QIcon()
        for sz in (16, 20, 24, 32, 48):
            pix = QPixmap(sz, sz)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pix)
        return icon

    def _setup_network_and_profile(self) -> None:
        profile = QWebEngineProfile.defaultProfile()

        # Фирменный User-Agent surf с полной веб-совместимостью
        ua_type = self.db.get_setting("user_agent_type", "surf")
        if ua_type == "surf" and "Surf/1.0" not in self.db.get_setting("custom_user_agent", ""):
            self.db.set_setting(
                "custom_user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Surf/1.0"
            )

        ua_str = self.db.get_setting(
            "custom_user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Surf/1.0",
        )
        profile.setHttpUserAgent(ua_str)

        folder = self.db.get_setting(
            "download_folder",
            os.path.join(os.path.expanduser("~"), "Downloads"),
        )
        os.makedirs(folder, exist_ok=True)
        profile.setDownloadPath(folder)

        self._apply_network_proxy()

    def _apply_network_proxy(self) -> None:
        p_type = self.db.get_setting("proxy_type", "none")
        if p_type == "none":
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        elif p_type == "system":
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.DefaultProxy))
        elif p_type in ("http", "socks5"):
            proxy = QNetworkProxy()
            proxy.setType(
                QNetworkProxy.ProxyType.HttpProxy if p_type == "http" else QNetworkProxy.ProxyType.Socks5Proxy
            )
            host = self.db.get_setting("proxy_host", "")
            port = int(self.db.get_setting("proxy_port", "8080") or "8080")
            user = self.db.get_setting("proxy_user", "")
            password = self.db.get_setting("proxy_password", "")
            if host:
                proxy.setHostName(host)
                proxy.setPort(port)
                if user:
                    proxy.setUser(user)
                    proxy.setPassword(password)
                QNetworkProxy.setApplicationProxy(proxy)

    def _setup_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._build_menu()

        # 1. Линия вкладок НАД панелью адреса
        self._build_tab_strip()

        # 2. Панель навигации
        self._build_toolbar()

        # 3. Тонкий прогресс-бар загрузки
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # 4. Контейнер страниц
        self.tab_stack = QStackedWidget()
        self.main_layout.addWidget(self.tab_stack)

        self._build_find_bar()

        # 5. Строка состояния с интерактивным масштабом
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.zoom_btn = QToolButton()
        self.zoom_btn.setObjectName("zoomBtn")
        self.zoom_btn.setText("100%")
        self.zoom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_btn.clicked.connect(self._zoom_reset)
        self.status_bar.addPermanentWidget(self.zoom_btn)

    def _build_tab_strip(self) -> None:
        self.tab_container = QWidget()
        self.tab_container.setObjectName("tabBarContainer")
        layout = QHBoxLayout(self.tab_container)
        layout.setContentsMargins(6, 2, 6, 0)
        layout.setSpacing(4)

        # Панель вкладок со сжатием и прокруткой при 50-200 вкладках
        self.tab_bar = ClosableTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        self.tab_bar.currentChanged.connect(self._on_tab_bar_current_changed)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

        # Кнопка "+" рядом с последней вкладкой
        self.new_tab_btn = QToolButton()
        self.new_tab_btn.setObjectName("newTabBtn")
        self.new_tab_btn.setIcon(self._get_icon("plus"))
        self.new_tab_btn.setIconSize(QSize(14, 14))
        self.new_tab_btn.setFixedSize(26, 24)
        self.new_tab_btn.clicked.connect(lambda: self.add_new_tab())

        layout.addWidget(self.tab_bar)
        layout.addWidget(self.new_tab_btn)
        layout.addStretch()

        self.main_layout.addWidget(self.tab_container)

    def _build_toolbar(self) -> None:
        self.nav_toolbar = QWidget()
        self.nav_toolbar.setObjectName("navToolbar")
        layout = QHBoxLayout(self.nav_toolbar)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(4)

        self.btn_back = QToolButton()
        self.btn_back.setIcon(self._get_icon("back"))
        self.btn_back.setIconSize(QSize(16, 16))
        self.btn_back.clicked.connect(self._go_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setIcon(self._get_icon("forward"))
        self.btn_forward.setIconSize(QSize(16, 16))
        self.btn_forward.clicked.connect(self._go_forward)

        self.btn_reload = QToolButton()
        self.btn_reload.setIcon(self._get_icon("reload"))
        self.btn_reload.setIconSize(QSize(16, 16))
        self.btn_reload.clicked.connect(self._reload_current)

        self.btn_home = QToolButton()
        self.btn_home.setIcon(self._get_icon("home"))
        self.btn_home.setIconSize(QSize(16, 16))
        self.btn_home.clicked.connect(self._go_home)

        layout.addWidget(self.btn_back)
        layout.addWidget(self.btn_forward)
        layout.addWidget(self.btn_reload)
        layout.addWidget(self.btn_home)

        # Скруглённая адресная строка
        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.returnPressed.connect(self._navigate_from_address_bar)

        self.completer_model = QStringListModel()
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.address_bar.setCompleter(self.completer)
        self._refresh_completer()

        layout.addWidget(self.address_bar)

        self.btn_bookmark = QToolButton()
        self.btn_bookmark.setIcon(self._get_icon("star"))
        self.btn_bookmark.setIconSize(QSize(16, 16))
        self.btn_bookmark.clicked.connect(self._toggle_bookmark)

        self.btn_reader = QToolButton()
        self.btn_reader.setIcon(self._get_icon("reader"))
        self.btn_reader.setIconSize(QSize(16, 16))
        self.btn_reader.clicked.connect(self._toggle_reader_mode)

        self.btn_downloads = QToolButton()
        self.btn_downloads.setIcon(self._get_icon("downloads"))
        self.btn_downloads.setIconSize(QSize(16, 16))
        self.btn_downloads.clicked.connect(self._open_downloads_dialog)

        self.btn_settings = QToolButton()
        self.btn_settings.setIcon(self._get_icon("settings"))
        self.btn_settings.setIconSize(QSize(16, 16))
        self.btn_settings.clicked.connect(self._open_settings_dialog)

        layout.addWidget(self.btn_bookmark)
        layout.addWidget(self.btn_reader)
        layout.addWidget(self.btn_downloads)
        layout.addWidget(self.btn_settings)

        self.main_layout.addWidget(self.nav_toolbar)

    def _build_menu(self) -> None:
        self.main_menubar = self.menuBar()
        self.main_menubar.triggered.connect(self._on_menu_action_triggered)

        # Файл
        self.file_menu = self.main_menubar.addMenu("")
        self.act_new_tab = self.file_menu.addAction("")
        self.act_new_tab.setShortcut(QKeySequence("Ctrl+T"))
        self.act_new_tab.triggered.connect(lambda: self.add_new_tab())

        self.act_close_tab = self.file_menu.addAction("")
        self.act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        self.act_close_tab.triggered.connect(lambda: self.close_tab(self.tab_bar.currentIndex()))

        self.file_menu.addSeparator()

        self.act_open_file = self.file_menu.addAction("")
        self.act_open_file.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open_file.triggered.connect(self._open_local_file)

        self.act_save_page = self.file_menu.addAction("")
        self.act_save_page.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_page.triggered.connect(self._save_page)

        self.act_screenshot = self.file_menu.addAction("")
        self.act_screenshot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_screenshot.triggered.connect(self._capture_screenshot)

        self.file_menu.addSeparator()
        self.act_exit = self.file_menu.addAction("")
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        # Правка
        self.edit_menu = self.main_menubar.addMenu("")
        self.act_find = self.edit_menu.addAction("")
        self.act_find.setShortcut(QKeySequence("Ctrl+F"))
        self.act_find.triggered.connect(self._show_find_bar)

        self.act_copy_url = self.edit_menu.addAction("")
        self.act_copy_url.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self.act_copy_url.triggered.connect(self._copy_current_url)

        # Вид
        self.view_menu = self.main_menubar.addMenu("")
        self.act_reader = self.view_menu.addAction("")
        self.act_reader.setShortcut(QKeySequence("Ctrl+Alt+R"))
        self.act_reader.triggered.connect(self._toggle_reader_mode)

        self.act_source = self.view_menu.addAction("")
        self.act_source.setShortcut(QKeySequence("Ctrl+U"))
        self.act_source.triggered.connect(self._show_page_source)

        view_menu_sep = self.view_menu.addSeparator()
        self.act_zoom_in = self.view_menu.addAction("")
        self.act_zoom_in.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+="), QKeySequence("Ctrl+Shift+=")])
        self.act_zoom_in.triggered.connect(self._zoom_in)

        self.act_zoom_out = self.view_menu.addAction("")
        self.act_zoom_out.setShortcuts([QKeySequence("Ctrl+-"), QKeySequence("Ctrl+_")])
        self.act_zoom_out.triggered.connect(self._zoom_out)

        self.act_zoom_reset = self.view_menu.addAction("")
        self.act_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        self.act_zoom_reset.triggered.connect(self._zoom_reset)

        self.view_menu.addSeparator()
        self.act_fullscreen = self.view_menu.addAction("")
        self.act_fullscreen.setShortcut(QKeySequence("F11"))
        self.act_fullscreen.triggered.connect(self._toggle_fullscreen)

        # Журнал
        self.history_menu = self.main_menubar.addMenu("")
        self.act_history = self.history_menu.addAction("")
        self.act_history.setShortcut(QKeySequence("Ctrl+H"))
        self.act_history.triggered.connect(self._open_history_dialog)

        self.act_clear_hist = self.history_menu.addAction("")
        self.act_clear_hist.triggered.connect(self._quick_clear_history)

        # Закладки
        self.bm_menu = self.main_menubar.addMenu("")
        self.act_add_bm = self.bm_menu.addAction("")
        self.act_add_bm.setShortcut(QKeySequence("Ctrl+D"))
        self.act_add_bm.triggered.connect(self._toggle_bookmark)

        self.act_manage_bm = self.bm_menu.addAction("")
        self.act_manage_bm.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.act_manage_bm.triggered.connect(self._open_history_dialog)

        # Инструменты
        self.tools_menu = self.main_menubar.addMenu("")
        self.act_downloads = self.tools_menu.addAction("")
        self.act_downloads.setShortcut(QKeySequence("Ctrl+J"))
        self.act_downloads.triggered.connect(self._open_downloads_dialog)

        self.act_download_url = self.tools_menu.addAction("")
        self.act_download_url.triggered.connect(self._download_from_url)

        self.act_settings = self.tools_menu.addAction("")
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.act_settings.triggered.connect(self._open_settings_dialog)

        # Справка
        self.help_menu = self.main_menubar.addMenu("")
        self.act_help = self.help_menu.addAction("")
        self.act_help.setShortcut(QKeySequence("F1"))
        self.act_help.triggered.connect(self._open_help)

        self.act_about = self.help_menu.addAction("")
        self.act_about.triggered.connect(self._show_about)

    def _build_find_bar(self) -> None:
        self.find_bar = QWidget()
        self.find_bar.setObjectName("findBar")
        layout = QHBoxLayout(self.find_bar)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        self.find_label = QLabel()
        self.find_input = QLineEdit()
        self.find_input.setFixedWidth(240)
        self.find_input.returnPressed.connect(self._find_next)

        self.btn_find_next = QPushButton()
        self.btn_find_next.clicked.connect(self._find_next)

        self.btn_find_prev = QPushButton()
        self.btn_find_prev.clicked.connect(self._find_prev)

        self.btn_close_find = QPushButton()
        self.btn_close_find.setIcon(self._get_icon("close"))
        self.btn_close_find.setFixedSize(24, 24)
        self.btn_close_find.clicked.connect(self._hide_find_bar)

        layout.addWidget(self.find_label)
        layout.addWidget(self.find_input)
        layout.addWidget(self.btn_find_next)
        layout.addWidget(self.btn_find_prev)
        layout.addStretch()
        layout.addWidget(self.btn_close_find)

        self.find_bar.setVisible(False)
        self.main_layout.addWidget(self.find_bar)

    def _retranslate_ui(self) -> None:
        # Меню
        self.file_menu.setTitle(tr("menu_file"))
        self.act_new_tab.setText(tr("act_new_tab"))
        self.act_close_tab.setText(tr("act_close_tab"))
        self.act_open_file.setText(tr("act_open_file"))
        self.act_save_page.setText(tr("act_save_page"))
        self.act_screenshot.setText(tr("act_screenshot"))
        self.act_exit.setText(tr("act_exit"))

        self.edit_menu.setTitle(tr("menu_edit"))
        self.act_find.setText(tr("act_find"))
        self.act_copy_url.setText(tr("act_copy_url"))

        self.view_menu.setTitle(tr("menu_view"))
        self.act_reader.setText(tr("act_reader"))
        self.act_source.setText(tr("act_source"))
        self.act_zoom_in.setText(tr("act_zoom_in"))
        self.act_zoom_out.setText(tr("act_zoom_out"))
        self.act_zoom_reset.setText(tr("act_zoom_reset"))
        self.act_fullscreen.setText(tr("act_fullscreen"))

        self.history_menu.setTitle(tr("menu_history"))
        self.act_history.setText(tr("act_show_history"))
        self.act_clear_hist.setText(tr("act_clear_history"))

        self.bm_menu.setTitle(tr("menu_bookmarks"))
        self.act_add_bm.setText(tr("act_add_bm"))
        self.act_manage_bm.setText(tr("act_manage_bookmarks"))

        self.tools_menu.setTitle(tr("menu_tools"))
        self.act_downloads.setText(tr("act_downloads"))
        self.act_download_url.setText(tr("act_download_url"))
        self.act_settings.setText(tr("act_settings"))

        self.help_menu.setTitle(tr("menu_help"))
        self.act_help.setText(tr("act_help"))
        self.act_about.setText(tr("act_about"))

        # Тулбар
        self.btn_back.setToolTip(tr("tip_back"))
        self.btn_forward.setToolTip(tr("tip_forward"))
        self.btn_reload.setToolTip(tr("tip_reload"))
        self.btn_home.setToolTip(tr("tip_home"))
        self.address_bar.setPlaceholderText(tr("address_placeholder"))
        self.btn_bookmark.setToolTip(tr("tip_bookmark"))
        self.btn_reader.setToolTip(tr("tip_reader"))
        self.btn_downloads.setToolTip(tr("tip_downloads"))
        self.btn_settings.setToolTip(tr("tip_settings"))
        self.new_tab_btn.setToolTip(tr("tip_new_tab"))
        self.zoom_btn.setToolTip(tr("act_zoom_reset"))

        # Панель поиска
        self.find_label.setText(tr("find_label"))
        self.find_input.setPlaceholderText(tr("find_placeholder"))
        self.btn_find_next.setText(tr("find_next"))
        self.btn_find_prev.setText(tr("find_prev"))

        # Обновление всех открытых страниц и заголовков вкладок
        for i in range(self.tab_bar.count()):
            tab = self.tab_stack.widget(i)
            if tab and isinstance(tab, BrowserTab):
                tab.retranslate_ui()
                if tab.stack.currentIndex() == 1 or not tab.current_url or tab.current_url.startswith("surf://newtab"):
                    self.tab_bar.setTabText(i, tr("new_tab"))
        self.tab_bar.retranslate_close_buttons()

    def _setup_shortcuts(self) -> None:
        # Навигация по вкладкам
        QShortcut(QKeySequence("Ctrl+T"), self, lambda: self.add_new_tab())
        QShortcut(QKeySequence("Ctrl+W"), self, lambda: self.close_tab(self.tab_bar.currentIndex()))
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, self._reopen_closed_tab)
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)

        # Переход к вкладкам 1-9
        for num in range(1, 9):
            QShortcut(QKeySequence(f"Ctrl+{num}"), self, lambda n=num: self._switch_to_tab(n - 1))
        QShortcut(QKeySequence("Ctrl+9"), self, lambda: self._switch_to_tab(self.tab_bar.count() - 1))

        # Адресная строка и фокус
        QShortcut(QKeySequence("Ctrl+L"), self, self._focus_address_bar)
        QShortcut(QKeySequence("Alt+D"), self, self._focus_address_bar)
        QShortcut(QKeySequence("F6"), self, self._focus_address_bar)

        # Обновление
        QShortcut(QKeySequence("F5"), self, self._reload_current)
        QShortcut(QKeySequence("Ctrl+R"), self, self._reload_current)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, self._hard_reload_current)
        QShortcut(QKeySequence("Ctrl+F5"), self, self._hard_reload_current)

        # Переходы
        QShortcut(QKeySequence("Alt+Left"), self, self._go_back)
        QShortcut(QKeySequence("Alt+Right"), self, self._go_forward)
        QShortcut(QKeySequence("Alt+Home"), self, self._go_home)

        # Диалоги и инструменты
        QShortcut(QKeySequence("Ctrl+H"), self, self._open_history_dialog)
        QShortcut(QKeySequence("Ctrl+J"), self, self._open_downloads_dialog)
        QShortcut(QKeySequence("Ctrl+D"), self, self._toggle_bookmark)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._open_history_dialog)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self._open_history_dialog)
        QShortcut(QKeySequence("Ctrl+P"), self, self._save_page)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_page)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_local_file)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._capture_screenshot)
        QShortcut(QKeySequence("Ctrl+U"), self, self._show_page_source)
        QShortcut(QKeySequence("Ctrl+Alt+R"), self, self._toggle_reader_mode)

        # Поиск
        QShortcut(QKeySequence("Ctrl+F"), self, self._show_find_bar)
        QShortcut(QKeySequence("F3"), self, self._find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self._find_prev)
        QShortcut(QKeySequence("Ctrl+G"), self, self._find_next)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._find_prev)

        # Масштаб
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+Shift+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+_"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)

        # Системные
        QShortcut(QKeySequence("Escape"), self, self._handle_escape)
        QShortcut(QKeySequence("F10"), self, self._toggle_menu_visibility)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)

    def _setup_downloads(self) -> None:
        profile = QWebEngineProfile.defaultProfile()
        try:
            profile.downloadRequested.disconnect()
        except Exception:
            pass
        profile.downloadRequested.connect(self._handle_download_requested)

    def _apply_theme(self) -> None:
        theme_name = self.db.get_setting("theme", "dark")
        is_dark = theme_name == "dark"
        accent = self.db.get_setting("accent_color", "#0060df")
        style_file = f"{theme_name}.qss"
        style_path = os.path.join(os.path.dirname(__file__), "styles", style_file)

        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                qss = f.read()
            # Динамически внедряем выбранный пользователем акцентный цвет
            qss = qss.replace("__ACCENT__", accent)
            self.setStyleSheet(qss)

        # Обновляем тему таббара
        if hasattr(self, "tab_bar") and isinstance(self.tab_bar, ClosableTabBar):
            self.tab_bar.set_theme_mode(is_dark)

        # Обновляем все тулбарные иконки в соответствии с темой (чёрные для светлой, белые для тёмной)
        if hasattr(self, "btn_back"):
            self.btn_back.setIcon(self._get_icon("back"))
            self.btn_forward.setIcon(self._get_icon("forward"))
            self.btn_reload.setIcon(self._get_icon("reload"))
            self.btn_home.setIcon(self._get_icon("home"))
            self.btn_bookmark.setIcon(self._get_icon("star"))
            self.btn_reader.setIcon(self._get_icon("reader"))
            self.btn_downloads.setIcon(self._get_icon("downloads"))
            self.btn_settings.setIcon(self._get_icon("settings"))
            self.new_tab_btn.setIcon(self._get_icon("plus"))

        if hasattr(self, "btn_close_find"):
            self.btn_close_find.setIcon(self._get_icon("close"))

        # Обновляем тему всех открытых вкладок и режима чтения
        if hasattr(self, "tab_stack"):
            for i in range(self.tab_stack.count()):
                tab = self.tab_stack.widget(i)
                if tab and hasattr(tab, "set_theme_mode"):
                    tab.set_theme_mode(is_dark)

    def _apply_menu_visibility(self) -> None:
        auto_hide = self.db.get_setting("menu_bar_auto_hide", "1") == "1"
        self.main_menubar.setVisible(not auto_hide)

    def _toggle_menu_visibility(self) -> None:
        if self.db.get_setting("menu_bar_auto_hide", "1") == "1":
            self.main_menubar.setVisible(self.main_menubar.isHidden())

    def _on_menu_action_triggered(self) -> None:
        if self.db.get_setting("menu_bar_auto_hide", "1") == "1":
            self.main_menubar.setVisible(False)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Alt, Qt.Key.Key_AltGr) and not event.isAutoRepeat():
            self._toggle_menu_visibility()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- Управление вкладками ---

    def add_new_tab(self, url: str = "") -> BrowserTab:
        tab = BrowserTab(self.db, self)
        idx = self.tab_stack.addWidget(tab)
        self.tab_bar.addTab(tr("new_tab"))
        self.tab_bar.setCurrentIndex(idx)

        tab.title_changed.connect(lambda title, t=tab: self._update_tab_title(t, title))
        tab.url_changed.connect(lambda u, t=tab: self._update_tab_url(t, u))
        tab.load_progress.connect(self._update_progress)
        tab.web_view.page().linkHovered.connect(self._on_link_hovered)

        if url:
            tab.load_url(url)
        else:
            tab.show_speed_dial()

        self._focus_address_bar()
        return tab

    def close_tab(self, index: int) -> None:
        if self.tab_bar.count() > 1:
            tab = self.tab_stack.widget(index)
            if tab and isinstance(tab, BrowserTab):
                url = tab.current_url
                if url and not url.startswith("surf://newtab") and url != "about:blank":
                    self._recently_closed_urls.append(url)

            self.tab_bar.removeTab(index)
            widget = self.tab_stack.widget(index)
            if widget:
                self.tab_stack.removeWidget(widget)
                widget.deleteLater()
        else:
            current = self.current_tab()
            if current:
                current.show_speed_dial()

    def _reopen_closed_tab(self) -> None:
        if self._recently_closed_urls:
            url = self._recently_closed_urls.pop()
            self.add_new_tab(url)

    def _next_tab(self) -> None:
        count = self.tab_bar.count()
        if count > 1:
            next_idx = (self.tab_bar.currentIndex() + 1) % count
            self.tab_bar.setCurrentIndex(next_idx)

    def _prev_tab(self) -> None:
        count = self.tab_bar.count()
        if count > 1:
            prev_idx = (self.tab_bar.currentIndex() - 1 + count) % count
            self.tab_bar.setCurrentIndex(prev_idx)

    def _switch_to_tab(self, index: int) -> None:
        if 0 <= index < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(index)

    def current_tab(self) -> BrowserTab | None:
        widget = self.tab_stack.currentWidget()
        if isinstance(widget, BrowserTab):
            return widget
        return None

    def _on_tab_bar_current_changed(self, index: int) -> None:
        if 0 <= index < self.tab_stack.count():
            self.tab_stack.setCurrentIndex(index)
            tab = self.current_tab()
            if tab:
                url = tab.current_url
                self.address_bar.setText("" if url.startswith("surf://newtab") else url)
                self._update_bookmark_icon(url)
                tab.web_view.setZoomFactor(self.zoom_factor)

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        widget = self.tab_stack.widget(from_idx)
        if widget:
            self.tab_stack.removeWidget(widget)
            self.tab_stack.insertWidget(to_idx, widget)
            self.tab_stack.setCurrentIndex(to_idx)

    def _update_tab_title(self, tab: BrowserTab, title: str) -> None:
        idx = self.tab_stack.indexOf(tab)
        if idx >= 0:
            short_title = (title[:20] + "...") if len(title) > 20 else title
            self.tab_bar.setTabText(idx, short_title or tr("untitled"))
            self.tab_bar.setTabToolTip(idx, title)
            self._refresh_completer()

    def _update_tab_url(self, tab: BrowserTab, url: str) -> None:
        if tab == self.current_tab():
            self.address_bar.setText("" if url.startswith("surf://newtab") else url)
            self._update_bookmark_icon(url)

    def _update_progress(self, progress: int) -> None:
        if progress < 100:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)
            self.btn_reload.setIcon(self._get_icon("stop"))
        else:
            self.progress_bar.setVisible(False)
            self.btn_reload.setIcon(self._get_icon("reload"))

    def _show_tab_context_menu(self, pos: QPoint) -> None:
        tab_idx = self.tab_bar.tabAt(pos)
        if tab_idx < 0:
            return

        menu = QMenu(self)
        act_reload = menu.addAction(tr("ctx_reload_tab"))
        act_duplicate = menu.addAction(tr("ctx_duplicate_tab"))
        act_close = menu.addAction(tr("ctx_close_tab"))
        act_close_others = menu.addAction(tr("ctx_close_others"))

        action = menu.exec(self.tab_bar.mapToGlobal(pos))
        if action == act_reload:
            tab = self.tab_stack.widget(tab_idx)
            if isinstance(tab, BrowserTab):
                tab.web_view.reload()
        elif action == act_duplicate:
            tab = self.tab_stack.widget(tab_idx)
            if isinstance(tab, BrowserTab):
                self.add_new_tab(tab.current_url)
        elif action == act_close:
            self.close_tab(tab_idx)
        elif action == act_close_others:
            for i in reversed(range(self.tab_bar.count())):
                if i != tab_idx:
                    self.close_tab(i)

    # --- Навигация ---

    def _navigate_from_address_bar(self) -> None:
        text = self.address_bar.text().strip()
        tab = self.current_tab()
        if tab and text:
            tab.load_url(text)

    def _go_back(self) -> None:
        tab = self.current_tab()
        if tab and tab.web_view.history().canGoBack():
            tab.web_view.back()

    def _go_forward(self) -> None:
        tab = self.current_tab()
        if tab and tab.web_view.history().canGoForward():
            tab.web_view.forward()

    def _reload_current(self) -> None:
        tab = self.current_tab()
        if tab:
            if self.progress_bar.isVisible():
                tab.web_view.stop()
            else:
                tab.web_view.reload()

    def _hard_reload_current(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.web_view.triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)

    def _go_home(self) -> None:
        tab = self.current_tab()
        if tab:
            home = self.db.get_setting("homepage", "https://ya.ru")
            tab.load_url(home)

    def _focus_address_bar(self) -> None:
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    def _on_link_hovered(self, url: str) -> None:
        self.status_bar.showMessage(url, 4000)

    # --- Закладки ---

    def _toggle_bookmark(self) -> None:
        tab = self.current_tab()
        if not tab or not tab.current_url or tab.current_url.startswith("surf://"):
            return

        if self.db.is_bookmarked(tab.current_url):
            self.db.delete_bookmark_by_url(tab.current_url)
            self._update_bookmark_icon(tab.current_url)
            self.status_bar.showMessage(tr("status_bookmark_removed"), 2500)
        else:
            title, ok = QInputDialog.getText(
                self,
                tr("bookmark_input_title"),
                tr("bookmark_input_label"),
                QLineEdit.EchoMode.Normal,
                tab.current_title,
            )
            if ok and title:
                self.db.add_bookmark(title, tab.current_url)
                self._update_bookmark_icon(tab.current_url)
                self.status_bar.showMessage(tr("status_bookmark_added"), 2500)

    def _update_bookmark_icon(self, url: str) -> None:
        if url and self.db.is_bookmarked(url):
            self.btn_bookmark.setIcon(self._get_icon("star_filled"))
        else:
            self.btn_bookmark.setIcon(self._get_icon("star"))

    # --- Режим чтения и исходный код ---

    def _toggle_reader_mode(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.toggle_reader_mode()

    def _show_page_source(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.show_page_source()

    # --- Поиск по странице ---

    def _show_find_bar(self) -> None:
        self.find_bar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def _hide_find_bar(self) -> None:
        self.find_bar.setVisible(False)
        tab = self.current_tab()
        if tab:
            tab.web_view.findText("")

    def _find_next(self) -> None:
        query = self.find_input.text()
        tab = self.current_tab()
        if tab and query:
            tab.web_view.findText(query)

    def _find_prev(self) -> None:
        query = self.find_input.text()
        tab = self.current_tab()
        if tab and query:
            tab.web_view.findText(query, QWebEnginePage.FindFlag.FindBackward)

    def _handle_escape(self) -> None:
        if self.find_bar.isVisible():
            self._hide_find_bar()
        elif self.main_menubar.isVisible() and self.db.get_setting("menu_bar_auto_hide", "1") == "1":
            self.main_menubar.setVisible(False)

    # --- Масштабирование ---

    def _zoom_in(self) -> None:
        if self.zoom_factor < 3.0:
            self.zoom_factor = round(self.zoom_factor + 0.1, 2)
            self._apply_zoom()

    def _zoom_out(self) -> None:
        if self.zoom_factor > 0.3:
            self.zoom_factor = round(self.zoom_factor - 0.1, 2)
            self._apply_zoom()

    def _zoom_reset(self) -> None:
        self.zoom_factor = 1.0
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.web_view.setZoomFactor(self.zoom_factor)
        pct = int(round(self.zoom_factor * 100))
        self.zoom_btn.setText(f"{pct}%")

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # --- Диалоги ---

    def _open_history_dialog(self) -> None:
        dlg = HistoryDialog(self.db, self)
        dlg.open_url.connect(lambda u: self.add_new_tab(u))
        dlg.exec()
        self._refresh_completer()

    def _open_downloads_dialog(self) -> None:
        dlg = DownloadManagerDialog(self.db, self)
        dlg.exec()

    def _open_settings_dialog(self) -> None:
        dlg = SettingsDialog(self.db, self)
        dlg.settings_changed.connect(self._on_settings_updated)
        dlg.exec()

    def _on_settings_updated(self) -> None:
        self._apply_theme()
        self._apply_menu_visibility()
        self._setup_network_and_profile()
        self._retranslate_ui()

    def _quick_clear_history(self) -> None:
        ans = QMessageBox.question(
            self,
            tr("clear_history_title"),
            tr("clear_history_prompt"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.db.clear_history("all")
            self._refresh_completer()
            self.status_bar.showMessage(tr("status_history_cleared"), 3000)

    def _open_local_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("open_file_dialog"),
            "",
            "HTML (*.html *.htm);;Text (*.txt);;All Files (*)",
        )
        if path:
            self.add_new_tab(QUrl.fromLocalFile(path).toString())

    def _save_page(self) -> None:
        tab = self.current_tab()
        if not tab or not tab.current_url:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_pdf_dialog"),
            "page.pdf",
            "PDF (*.pdf)",
        )
        if path:
            tab.web_view.page().printToPdf(path)
            self.status_bar.showMessage(tr("status_pdf_saved", path=path), 3000)

    def _capture_screenshot(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.capture_screenshot()

    def _copy_current_url(self) -> None:
        tab = self.current_tab()
        if tab and tab.current_url:
            QApplication.clipboard().setText(tab.current_url)
            self.status_bar.showMessage(tr("status_url_copied"), 2500)

    def _open_help(self) -> None:
        self.add_new_tab("surf://help")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("about_title"),
            tr("about_text"),
        )

    # --- Загрузка файлов ---

    def _download_from_url(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            tr("download_url_title"),
            tr("download_url_label"),
            QLineEdit.EchoMode.Normal,
            "https://",
        )
        if ok and url.strip():
            tab = self.current_tab()
            if tab:
                tab.web_view.page().download(QUrl(url.strip()))

    def _handle_download_requested(self, download: QWebEngineDownloadRequest) -> None:
        # Сохраняем ссылку, чтобы объект не уничтожился сборщиком мусора Python
        self._active_downloads.append(download)

        raw_folder = self.db.get_setting(
            "download_folder",
            os.path.join(os.path.expanduser("~"), "Downloads"),
        )
        folder = os.path.abspath(raw_folder)
        os.makedirs(folder, exist_ok=True)

        suggested = download.suggestedFileName() or download.downloadFileName() or "downloaded_file"
        suggested = os.path.basename(suggested)
        full_path = os.path.join(folder, suggested)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_download_dialog"),
            full_path,
            "All Files (*)",
        )
        if not file_path:
            download.cancel()
            if download in self._active_downloads:
                self._active_downloads.remove(download)
            return

        target_dir = os.path.dirname(os.path.abspath(file_path))
        target_name = os.path.basename(file_path)

        download.setDownloadDirectory(target_dir)
        download.setDownloadFileName(target_name)
        download.accept()

        url_str = download.url().toString()
        self.status_bar.showMessage(tr("status_download_started", name=target_name), 4000)

        def on_state_changed(state):
            if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                size = download.totalBytes()
                status_text = "Завершено" if get_language() == "ru" else "Completed"
                self.db.add_download(target_name, file_path, url_str, size, status_text)
                self.status_bar.showMessage(tr("status_download_finished", name=target_name), 5000)
                if download in self._active_downloads:
                    self._active_downloads.remove(download)
            elif state in (
                QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
                QWebEngineDownloadRequest.DownloadState.DownloadInterrupted,
            ):
                if download in self._active_downloads:
                    self._active_downloads.remove(download)
                self.status_bar.showMessage(f"Download cancelled/failed: {target_name}", 3000)

        download.stateChanged.connect(on_state_changed)

    def _refresh_completer(self) -> None:
        recent = self.db.get_history(limit=80)
        urls = list({r["url"] for r in recent})
        self.completer_model.setStringList(urls)

    def closeEvent(self, event) -> None:
        if self.db.get_setting("privacy_clear_on_exit", "0") == "1":
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            profile.cookieStore().deleteAllCookies()
            self.db.clear_history("all")
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("surf")
    app.setOrganizationName("surf-browser")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
