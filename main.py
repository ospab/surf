import os
import sys

from PyQt6.QtCore import QPoint, QSize, QStringListModel, Qt, QUrl
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtNetwork import QNetworkProxy
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
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

from surf.database import Database
from surf.widgets.browser_tab import BrowserTab
from surf.widgets.download_manager import DownloadManagerDialog
from surf.widgets.history_dialog import HistoryDialog
from surf.widgets.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("surf")
        self.resize(1200, 800)

        self.db = Database()
        self.zoom_factor = 1.0

        self._setup_network_and_profile()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_downloads()
        self._apply_theme()
        self._apply_menu_visibility()

        self.add_new_tab()

    def _get_icon(self, name: str) -> QIcon:
        path = os.path.join(os.path.dirname(__file__), "resources", "icons", f"{name}.svg")
        return QIcon(path)

    def _setup_network_and_profile(self) -> None:
        profile = QWebEngineProfile.defaultProfile()

        # User-Agent по умолчанию (современный десктопный браузер)
        ua_str = self.db.get_setting(
            "custom_user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        )
        profile.setHttpUserAgent(ua_str)
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

        # 2. Панель навигации (тулбар под вкладками)
        self._build_toolbar()

        # 3. Тонкий прогресс-бар загрузки
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.main_layout.addWidget(self.progress_bar)

        # 4. Контейнер отображения страниц (соответствует активной вкладке)
        self.tab_stack = QStackedWidget()
        self.main_layout.addWidget(self.tab_stack)

        self._build_find_bar()

        # 5. Строка состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.zoom_label = QLabel("100%")
        self.status_bar.addPermanentWidget(self.zoom_label)

    def _build_tab_strip(self) -> None:
        self.tab_container = QWidget()
        self.tab_container.setObjectName("tabBarContainer")
        layout = QHBoxLayout(self.tab_container)
        layout.setContentsMargins(6, 2, 6, 0)
        layout.setSpacing(4)

        # Панель вкладок со сжатием и прокруткой при 50-200 вкладках
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setTabsClosable(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        self.tab_bar.currentChanged.connect(self._on_tab_bar_current_changed)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._show_tab_context_menu)

        # Кнопка "+" рядом с вкладкой
        self.new_tab_btn = QToolButton()
        self.new_tab_btn.setObjectName("newTabBtn")
        self.new_tab_btn.setIcon(self._get_icon("plus"))
        self.new_tab_btn.setIconSize(QSize(14, 14))
        self.new_tab_btn.setToolTip("Новая вкладка (Ctrl+T)")
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
        self.btn_back.setToolTip("Назад (Alt+Left)")
        self.btn_back.clicked.connect(self._go_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setIcon(self._get_icon("forward"))
        self.btn_forward.setIconSize(QSize(16, 16))
        self.btn_forward.setToolTip("Вперед (Alt+Right)")
        self.btn_forward.clicked.connect(self._go_forward)

        self.btn_reload = QToolButton()
        self.btn_reload.setIcon(self._get_icon("reload"))
        self.btn_reload.setIconSize(QSize(16, 16))
        self.btn_reload.setToolTip("Обновить (F5 / Ctrl+R)")
        self.btn_reload.clicked.connect(self._reload_current)

        self.btn_home = QToolButton()
        self.btn_home.setIcon(self._get_icon("home"))
        self.btn_home.setIconSize(QSize(16, 16))
        self.btn_home.setToolTip("Домашняя страница (Alt+Home)")
        self.btn_home.clicked.connect(self._go_home)

        layout.addWidget(self.btn_back)
        layout.addWidget(self.btn_forward)
        layout.addWidget(self.btn_reload)
        layout.addWidget(self.btn_home)

        # Скруглённая адресная строка
        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setPlaceholderText("Поиск в интернете или ввод URL...")
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
        self.btn_bookmark.setToolTip("Добавить в закладки (Ctrl+D)")
        self.btn_bookmark.clicked.connect(self._toggle_bookmark)

        self.btn_reader = QToolButton()
        self.btn_reader.setIcon(self._get_icon("reader"))
        self.btn_reader.setIconSize(QSize(16, 16))
        self.btn_reader.setToolTip("Режим чтения (Ctrl+Alt+R)")
        self.btn_reader.clicked.connect(self._toggle_reader_mode)

        self.btn_downloads = QToolButton()
        self.btn_downloads.setIcon(self._get_icon("downloads"))
        self.btn_downloads.setIconSize(QSize(16, 16))
        self.btn_downloads.setToolTip("Загрузки (Ctrl+J)")
        self.btn_downloads.clicked.connect(self._open_downloads_dialog)

        self.btn_settings = QToolButton()
        self.btn_settings.setIcon(self._get_icon("settings"))
        self.btn_settings.setIconSize(QSize(16, 16))
        self.btn_settings.setToolTip("Настройки (Ctrl+,)")
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
        file_menu = self.main_menubar.addMenu("&Файл")
        act_new_tab = file_menu.addAction("Новая вкладка")
        act_new_tab.setShortcut(QKeySequence("Ctrl+T"))
        act_new_tab.triggered.connect(lambda: self.add_new_tab())

        act_close_tab = file_menu.addAction("Закрыть вкладку")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(lambda: self.close_tab(self.tab_bar.currentIndex()))

        file_menu.addSeparator()

        act_open_file = file_menu.addAction("Открыть HTML файл...")
        act_open_file.setShortcut(QKeySequence("Ctrl+O"))
        act_open_file.triggered.connect(self._open_local_file)

        act_save_page = file_menu.addAction("Сохранить страницу как...")
        act_save_page.setShortcut(QKeySequence("Ctrl+S"))
        act_save_page.triggered.connect(self._save_page)

        act_screenshot = file_menu.addAction("Сделать скриншот страницы...")
        act_screenshot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_screenshot.triggered.connect(self._capture_screenshot)

        file_menu.addSeparator()
        act_exit = file_menu.addAction("Выход")
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)

        # Правка
        edit_menu = self.main_menubar.addMenu("&Правка")
        act_find = edit_menu.addAction("Найти на этой странице...")
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self._show_find_bar)

        act_copy_url = edit_menu.addAction("Копировать адрес страницы")
        act_copy_url.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_copy_url.triggered.connect(self._copy_current_url)

        # Вид
        view_menu = self.main_menubar.addMenu("&Вид")
        act_reader = view_menu.addAction("Режим комфортного чтения")
        act_reader.setShortcut(QKeySequence("Ctrl+Alt+R"))
        act_reader.triggered.connect(self._toggle_reader_mode)

        act_source = view_menu.addAction("Исходный код страницы")
        act_source.setShortcut(QKeySequence("Ctrl+U"))
        act_source.triggered.connect(self._show_page_source)

        view_menu.addSeparator()
        act_zoom_in = view_menu.addAction("Увеличить масштаб")
        act_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        act_zoom_in.triggered.connect(self._zoom_in)

        act_zoom_out = view_menu.addAction("Уменьшить масштаб")
        act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        act_zoom_out.triggered.connect(self._zoom_out)

        act_zoom_reset = view_menu.addAction("Сбросить масштаб")
        act_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        act_zoom_reset.triggered.connect(self._zoom_reset)

        view_menu.addSeparator()
        act_fullscreen = view_menu.addAction("Полноэкранный режим")
        act_fullscreen.setShortcut(QKeySequence("F11"))
        act_fullscreen.triggered.connect(self._toggle_fullscreen)

        # Журнал
        history_menu = self.main_menubar.addMenu("&Журнал")
        act_history = history_menu.addAction("Показать всю историю")
        act_history.setShortcut(QKeySequence("Ctrl+H"))
        act_history.triggered.connect(self._open_history_dialog)

        act_clear_hist = history_menu.addAction("Очистить историю...")
        act_clear_hist.triggered.connect(self._quick_clear_history)

        # Закладки
        bm_menu = self.main_menubar.addMenu("&Закладки")
        act_add_bm = bm_menu.addAction("Добавить страницу в закладки")
        act_add_bm.setShortcut(QKeySequence("Ctrl+D"))
        act_add_bm.triggered.connect(self._toggle_bookmark)

        act_manage_bm = bm_menu.addAction("Управление закладками")
        act_manage_bm.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_manage_bm.triggered.connect(self._open_history_dialog)

        # Инструменты
        tools_menu = self.main_menubar.addMenu("&Инструменты")
        act_downloads = tools_menu.addAction("Загрузки")
        act_downloads.setShortcut(QKeySequence("Ctrl+J"))
        act_downloads.triggered.connect(self._open_downloads_dialog)

        act_settings = tools_menu.addAction("Настройки")
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self._open_settings_dialog)

        # Справка
        help_menu = self.main_menubar.addMenu("&Справка")
        act_help = help_menu.addAction("Справка surf")
        act_help.setShortcut(QKeySequence("F1"))
        act_help.triggered.connect(self._open_help)

        act_about = help_menu.addAction("О программе surf")
        act_about.triggered.connect(self._show_about)

    def _build_find_bar(self) -> None:
        self.find_bar = QWidget()
        self.find_bar.setObjectName("findBar")
        layout = QHBoxLayout(self.find_bar)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        lbl = QLabel("Поиск:")
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Найти на странице...")
        self.find_input.setFixedWidth(240)
        self.find_input.returnPressed.connect(self._find_next)

        btn_find_next = QPushButton("Далее")
        btn_find_next.clicked.connect(self._find_next)

        btn_find_prev = QPushButton("Назад")
        btn_find_prev.clicked.connect(self._find_prev)

        btn_close_find = QPushButton()
        btn_close_find.setIcon(self._get_icon("close"))
        btn_close_find.setFixedSize(24, 24)
        btn_close_find.clicked.connect(self._hide_find_bar)

        layout.addWidget(lbl)
        layout.addWidget(self.find_input)
        layout.addWidget(btn_find_next)
        layout.addWidget(btn_find_prev)
        layout.addStretch()
        layout.addWidget(btn_close_find)

        self.find_bar.setVisible(False)
        self.main_layout.addWidget(self.find_bar)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+L"), self, self._focus_address_bar)
        QShortcut(QKeySequence("Alt+D"), self, self._focus_address_bar)
        QShortcut(QKeySequence("F5"), self, self._reload_current)
        QShortcut(QKeySequence("Ctrl+R"), self, self._reload_current)
        QShortcut(QKeySequence("Alt+Left"), self, self._go_back)
        QShortcut(QKeySequence("Alt+Right"), self, self._go_forward)
        QShortcut(QKeySequence("Alt+Home"), self, self._go_home)
        QShortcut(QKeySequence("Escape"), self, self._handle_escape)
        QShortcut(QKeySequence("F10"), self, self._toggle_menu_visibility)

    def _setup_downloads(self) -> None:
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self._handle_download_requested)

    def _apply_theme(self) -> None:
        theme_name = self.db.get_setting("theme", "dark")
        style_file = f"{theme_name}.qss"
        style_path = os.path.join(os.path.dirname(__file__), "styles", style_file)

        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

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
        self.tab_bar.addTab("Новая вкладка")
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
            self.tab_bar.removeTab(index)
            widget = self.tab_stack.widget(index)
            if widget:
                self.tab_stack.removeWidget(widget)
                widget.deleteLater()
        else:
            current = self.current_tab()
            if current:
                current.show_speed_dial()

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
            self.tab_bar.setTabText(idx, short_title or "Без названия")
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
        act_reload = menu.addAction("Обновить вкладку")
        act_duplicate = menu.addAction("Дублировать вкладку")
        act_close = menu.addAction("Закрыть вкладку")
        act_close_others = menu.addAction("Закрыть другие вкладки")

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
            self.status_bar.showMessage("Закладка удалена", 2500)
        else:
            title, ok = QInputDialog.getText(
                self,
                "Добавить в закладки",
                "Название страницы:",
                QLineEdit.EchoMode.Normal,
                tab.current_title,
            )
            if ok and title:
                self.db.add_bookmark(title, tab.current_url)
                self._update_bookmark_icon(tab.current_url)
                self.status_bar.showMessage("Закладка сохранена в Избранное", 2500)

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

    # --- Масштаб ---

    def _zoom_in(self) -> None:
        if self.zoom_factor < 3.0:
            self.zoom_factor += 0.1
            self._apply_zoom()

    def _zoom_out(self) -> None:
        if self.zoom_factor > 0.4:
            self.zoom_factor -= 0.1
            self._apply_zoom()

    def _zoom_reset(self) -> None:
        self.zoom_factor = 1.0
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.web_view.setZoomFactor(self.zoom_factor)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")

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

    def _quick_clear_history(self) -> None:
        ans = QMessageBox.question(
            self,
            "Очистить историю",
            "Удалить всю историю посещений страниц?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.db.clear_history("all")
            self._refresh_completer()
            self.status_bar.showMessage("История посещений успешно очищена", 3000)

    def _open_local_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть файл",
            "",
            "HTML файлы (*.html *.htm);;Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if path:
            self.add_new_tab(QUrl.fromLocalFile(path).toString())

    def _save_page(self) -> None:
        tab = self.current_tab()
        if not tab or not tab.current_url:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить веб-страницу как PDF",
            "page.pdf",
            "PDF Документ (*.pdf)",
        )
        if path:
            tab.web_view.page().printToPdf(path)
            self.status_bar.showMessage(f"Страница сохранена в PDF: {path}", 3000)

    def _capture_screenshot(self) -> None:
        tab = self.current_tab()
        if tab:
            tab.capture_screenshot()

    def _copy_current_url(self) -> None:
        tab = self.current_tab()
        if tab and tab.current_url:
            QApplication.clipboard().setText(tab.current_url)
            self.status_bar.showMessage("URL скопирован в буфер обмена", 2500)

    def _open_help(self) -> None:
        self.add_new_tab("surf://help")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "О программе surf",
            "<h3>surf 1.0</h3>"
            "<p>Строгий веб-браузер на базе PyQt6 и WebEngine со скруглённым интерфейсом.</p>"
            "<p><b>Особенности:</b></p>"
            "<ul>"
            "<li>Многовкладочный интерфейс с прокруткой и компактным сужением</li>"
            "<li>Режим комфортного чтения без рекламы (Reader Mode)</li>"
            "<li>Журнал истории, закладок и загрузок на SQLite</li>"
            "<li>Экспорт и импорт данных в формате CSV</li>"
            "<li>Настройки прокси, приватности и User-Agent</li>"
            "</ul>",
        )

    # --- Загрузка файлов ---

    def _handle_download_requested(self, download) -> None:
        folder = self.db.get_setting("download_folder", os.path.expanduser("~/Downloads"))
        suggested = download.downloadFileName()
        full_path = os.path.join(folder, suggested)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить загружаемый файл",
            full_path,
            "Все файлы (*)",
        )
        if not file_path:
            download.cancel()
            return

        download.setDownloadDirectory(os.path.dirname(file_path))
        download.setDownloadFileName(os.path.basename(file_path))
        download.accept()

        url_str = download.url().toString()
        self.status_bar.showMessage(f"Началась загрузка: {os.path.basename(file_path)}", 4000)

        def on_finished():
            size = download.totalBytes()
            self.db.add_download(os.path.basename(file_path), file_path, url_str, size, "Завершено")
            self.status_bar.showMessage(f"Загрузка завершена: {os.path.basename(file_path)}", 5000)

        download.isFinishedChanged.connect(on_finished)

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
