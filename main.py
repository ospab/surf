import os
import sys
import time

# Поддержка прямого запуска 'python ./main.py' из папки проекта,
# а также запуска как модуля 'python -m surf.main' из внешнего каталога
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from PyQt6.QtCore import QByteArray, QPoint, QSize, QStringListModel, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtNetwork import QNetworkProxy
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.constants import SURF_USER_AGENT
    from surf.database import Database
    from surf.i18n import get_language, set_language, tr
    from surf.utils.adblock import TrackingProtectionInterceptor
    from surf.utils.internal_pages import SurfSchemeHandler, register_surf_scheme
    from surf.widgets.browser_tab import BrowserTab
    from surf.widgets.certificate_dialog import CertificateDialog, fetch_certificate_details
    from surf.widgets.download_manager import DownloadManagerDialog
    from surf.widgets.history_dialog import HistoryDialog
    from surf.widgets.settings_dialog import TAB_SLEEP_MINUTES, SettingsDialog
    from surf.widgets.tab_bar import ClosableTabBar, ZoomWheelFilter
    from surf.widgets.tracking_dialog import TrackingProtectionDialog
except ModuleNotFoundError:
    from constants import SURF_USER_AGENT
    from database import Database
    from i18n import get_language, set_language, tr
    from utils.adblock import TrackingProtectionInterceptor
    from utils.internal_pages import SurfSchemeHandler, register_surf_scheme
    from widgets.browser_tab import BrowserTab
    from widgets.certificate_dialog import CertificateDialog, fetch_certificate_details
    from widgets.download_manager import DownloadManagerDialog
    from widgets.history_dialog import HistoryDialog
    from widgets.settings_dialog import SettingsDialog
    from widgets.tab_bar import ClosableTabBar, ZoomWheelFilter
    from widgets.tracking_dialog import TrackingProtectionDialog

ICONS_DIR = os.path.join(CURRENT_DIR, "resources", "icons")
JS_DIR = os.path.join(CURRENT_DIR, "resources", "js")
STYLES_DIR = os.path.join(CURRENT_DIR, "styles")

# Шаг масштаба и его границы (Ctrl+колесо, Ctrl+=/-)
ZOOM_STEP = 0.1
ZOOM_MIN = 0.3
ZOOM_MAX = 3.0

# Как часто проверять, не пора ли усыпить неактивные вкладки
TAB_SLEEP_CHECK_MS = 60_000
SLEEPING_TAB_COLOR = "#8e8e9a"


def load_js(filename: str) -> str:
    """Читает JS-скрипт, внедряемый в страницы, из resources/js."""
    with open(os.path.join(JS_DIR, filename), encoding="utf-8") as f:
        return f.read()


def setup_chromium_environment() -> None:
    """Настраивает флаги Chromium для поддержки WebUSB, WebXR, WebRTC, устройств и ускорения."""
    flags = [
        "--enable-features=WebXR,WebXRGamepadSupport,WebUSB,WebBluetooth,WebHID,WebSerial,EnumerateDevices,UserMediaScreenCapturing",
        "--enable-experimental-web-platform-features",
        "--enable-gpu-rasterization",
        "--enable-zero-copy",
        "--enable-webgl-developer-extensions",
        "--enable-webgl-draft-extensions",
        "--enable-usermedia-screen-capturing",
        "--autoplay-policy=no-user-gesture-required",
    ]
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    flags_str = " ".join(flags)
    if existing:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{existing} {flags_str}".strip()
    else:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags_str


setup_chromium_environment()

PERSISTENT_PROFILE_NAME = "surf"
_persistent_profile: QWebEngineProfile | None = None


def get_persistent_profile() -> QWebEngineProfile:
    """Возвращает общий постоянный профиль для всех обычных (не приватных) окон.

    В Qt 6 QWebEngineProfile.defaultProfile() — приватный (off-the-record):
    cookies, кэш и разрешения не сохраняются на диск, а браузер считает
    каждое окно инкогнито и не пишет историю. Поэтому создаём именованный
    профиль. Он один на всё приложение: два профиля с одним именем
    одновременно Qt создать не даёт.
    """
    global _persistent_profile
    if _persistent_profile is None:
        _persistent_profile = QWebEngineProfile(PERSISTENT_PROFILE_NAME, QApplication.instance())
    return _persistent_profile


try:
    register_surf_scheme()
except Exception:
    pass


class MainWindow(QMainWindow):
    _open_windows: list["MainWindow"] = []

    def __init__(self, is_private: bool = False):
        super().__init__()
        self.is_private = is_private
        MainWindow._open_windows.append(self)

        self.setWindowTitle(tr("private_window_title") if self.is_private else tr("app_title"))
        self.resize(1200, 800)

        self.db = Database()
        self._active_tab: BrowserTab | None = None
        self._active_downloads: list[QWebEngineDownloadRequest] = []
        self._recently_closed_urls: list[str] = []
        self._cert_cache: dict[str, dict] = {}

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

        restored = 0
        if not self.is_private and self.db.get_setting("restore_session_on_startup", "1") == "1":
            restored = self.restore_previous_session()
        if restored == 0:
            self.add_new_tab()

        # Усыпление неактивных вкладок для экономии памяти
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setInterval(TAB_SLEEP_CHECK_MS)
        self._sleep_timer.timeout.connect(self._sleep_inactive_tabs)
        self._sleep_timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_dwm_titlebar()

    def _apply_dwm_titlebar(self) -> None:
        """Стилизует заголовок окна Windows (Title Bar), убирая чёрную полосу."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import byref, c_int, sizeof

            hwnd = int(self.winId())
            is_dark = self._is_dark_theme

            # 1. Тёмная/светлая тема для системных кнопок заголовка (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
            val = c_int(1 if is_dark else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(val), sizeof(val))

            # 2. Цвет плашки заголовка Windows (DWMWA_CAPTION_COLOR = 35) в формате BGR (0x00BBGGRR)
            # Тёмная тема: #1c1b22 -> 0x00221B1C; Светлая: #e5e5ea -> 0x00EAE5E5
            caption_color = c_int(0x00221B1C if is_dark else 0x00EAE5E5)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), sizeof(caption_color))

            # 3. Цвет текста заголовка (DWMWA_TEXT_COLOR = 36)
            text_color = c_int(0x00FEFBFB if is_dark else 0x001A1415)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text_color), sizeof(text_color))
        except Exception:
            pass

    def _get_icon(self, name: str) -> QIcon:
        """Иконка под текущую тему. Отрисовка SVG дорогая, поэтому результат кэшируется
        (иконка «стоп/обновить» запрашивается на каждый тик загрузки страницы)."""
        if not hasattr(self, "_icon_cache"):
            self._icon_cache: dict[str, QIcon] = {}
            self._is_dark_theme = self.db.get_setting("theme", "dark") == "dark"
        icon = self._icon_cache.get(name)
        if icon is None:
            icon = self._render_themed_icon(name, self._is_dark_theme)
            self._icon_cache[name] = icon
        return icon

    def _render_themed_icon(self, name: str, is_dark: bool) -> QIcon:
        path = os.path.join(ICONS_DIR, f"{name}.svg")
        if not os.path.exists(path):
            return QIcon()

        try:
            with open(path, encoding="utf-8") as f:
                svg_text = f.read()
        except Exception:
            return QIcon(path)

        stroke_color = "#fbfbfe" if is_dark else "#15141a"
        if not is_dark:
            svg_text = svg_text.replace("#cfcfd8", stroke_color)
            svg_text = svg_text.replace("#ffffff", stroke_color)
            svg_text = svg_text.replace("#fbfbfe", stroke_color)
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
        if self.is_private:
            self.profile = QWebEngineProfile(self)
        else:
            self.profile = get_persistent_profile()

        # Фирменная инъекция брендинга surf и ospab foundation в объект navigator:
        # Убирает упоминания Mozilla, Netscape, Gecko и Google Inc. на сайтах проверки (internet.yandex.ru и др.)
        branding_script = QWebEngineScript()
        branding_script.setName("surf_branding_overrides")
        branding_script.setSourceCode(load_js("branding.js"))
        branding_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        branding_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        branding_script.setRunsOnSubFrames(True)
        if not self.profile.scripts().find("surf_branding_overrides"):
            self.profile.scripts().insert(branding_script)

        # Скрипт маршрутизации медиаустройств (микрофоны, камеры) для WebRTC
        if not self.profile.scripts().find("surf_device_routing"):
            device_script = QWebEngineScript()
            device_script.setName("surf_device_routing")
            device_script.setSourceCode(load_js("device_routing.js"))
            device_script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
            device_script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            device_script.setRunsOnSubFrames(True)
            self.profile.scripts().insert(device_script)

        # Enhanced Tracking Protection (ETP) - перехватчик трекеров.
        # Один на профиль: обычные окна делят общий профиль, и новое окно не должно
        # подменять перехватчик (и обнулять счётчик) у уже открытых окон.
        self.tracking_interceptor = getattr(self.profile, "surf_interceptor", None)
        if self.tracking_interceptor is None:
            self.tracking_interceptor = TrackingProtectionInterceptor(self.profile)
            self.profile.setUrlRequestInterceptor(self.tracking_interceptor)
            self.profile.surf_interceptor = self.tracking_interceptor
        self.tracking_interceptor.blocked_count_changed.connect(self._on_blocked_count_changed)

        # Конфигурация WebEngineSettings: аппаратное ускорение, WebGL, WebRTC, захват экрана
        web_settings = self.profile.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.WebRTCPublicInterfacesOnly, False)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, True)

        # Политика хранения разрешений на устройства и системные API
        if not self.is_private:
            self.profile.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.StoreOnDisk)
        else:
            self.profile.setPersistentPermissionsPolicy(QWebEngineProfile.PersistentPermissionsPolicy.StoreInMemory)

        # Обработчик служебных внутренних страниц surf:// (тоже один на профиль:
        # повторная установка для той же схемы Qt отклоняет)
        self.scheme_handler = self.profile.urlSchemeHandler(b"surf")
        if self.scheme_handler is None:
            self.scheme_handler = SurfSchemeHandler(self.db, self.profile, interceptor=self.tracking_interceptor)
            self.profile.installUrlSchemeHandler(b"surf", self.scheme_handler)

        self._apply_profile_settings()

    def _apply_profile_settings(self) -> None:
        """Применяет изменяемые настройки к УЖЕ созданному профилю.

        Вызывается при старте и после сохранения настроек. Профиль, скрипты,
        перехватчик трекеров и обработчик surf:// здесь не пересоздаются —
        иначе открытые вкладки остались бы на старом профиле.
        """
        # Фирменный User-Agent surf с полной веб-совместимостью
        default_ua = SURF_USER_AGENT
        ua_type = self.db.get_setting("user_agent_type", "surf")
        if ua_type in ("surf", "surf_pure"):
            self.db.set_setting("user_agent_type", "surf")
            self.db.set_setting("custom_user_agent", default_ua)

        ua_str = self.db.get_setting("custom_user_agent", default_ua)
        self.profile.setHttpUserAgent(ua_str)

        folder = self.db.get_setting(
            "download_folder",
            os.path.join(os.path.expanduser("~"), "Downloads"),
        )
        os.makedirs(folder, exist_ok=True)
        self.profile.setDownloadPath(folder)

        # Do Not Track / Global Privacy Control
        self.tracking_interceptor.send_dnt = self.db.get_setting("privacy_dnt", "1") == "1"

        # Тёмная тема для всех сайтов (Chromium сам затемняет светлые страницы)
        force_dark = self.db.get_setting("force_dark_sites", "0") == "1"
        self.profile.settings().setAttribute(QWebEngineSettings.WebAttribute.ForceDarkMode, force_dark)

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

        # 1. Линия парящих вкладок НАД панелью адреса (surf)
        self._build_tab_strip()

        # 2. Панель навигации со встроенным AwesomeBar
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

        # Панель вкладок со сжатием и прокруткой
        self.tab_bar = ClosableTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setMovable(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        self.tab_bar.currentChanged.connect(self._on_tab_bar_current_changed)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.tabAudioMuteRequested.connect(self._toggle_tab_audio_mute)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.tabDetachRequested.connect(self._detach_tab_to_new_window)
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
        layout.setSpacing(6)

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

        # Скруглённая адресная строка AwesomeBar со встроенными экшенами (SSL, Shield, Reader, Star)
        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("addressBar")
        self.address_bar.setMinimumHeight(28)
        self.address_bar.returnPressed.connect(self._navigate_from_address_bar)

        # Ведущая кнопка (слева): Замок SSL/TLS или иконка поиска
        self.act_ssl = self.address_bar.addAction(self._get_icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        self.act_ssl.setToolTip(tr("tip_ssl_secure"))
        self.act_ssl.triggered.connect(self._show_security_info)

        # Завершающие кнопки (справа, порядок появления слева-направо: Shield, Reader, Star):
        # 1. Крайняя правая кнопка (Star)
        self.act_star = self.address_bar.addAction(self._get_icon("star"), QLineEdit.ActionPosition.TrailingPosition)
        self.act_star.setToolTip(tr("tip_bookmark"))
        self.act_star.triggered.connect(self._toggle_bookmark)

        # 2. Средняя кнопка (Reader)
        self.act_reader = self.address_bar.addAction(
            self._get_icon("reader"), QLineEdit.ActionPosition.TrailingPosition
        )
        self.act_reader.setToolTip(tr("tip_reader"))
        self.act_reader.triggered.connect(self._toggle_reader_mode)

        # 3. Левая кнопка в правой группе (Shield - Enhanced Tracking Protection)
        self.act_shield = self.address_bar.addAction(
            self._get_icon("shield"), QLineEdit.ActionPosition.TrailingPosition
        )
        self.act_shield.setToolTip(tr("tip_shield_protection"))
        self.act_shield.triggered.connect(self._show_tracking_protection_dialog)

        self.completer_model = QStringListModel()
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.address_bar.setCompleter(self.completer)
        self._refresh_completer()

        layout.addWidget(self.address_bar)

        self.btn_downloads = QToolButton()
        self.btn_downloads.setIcon(self._get_icon("downloads"))
        self.btn_downloads.setIconSize(QSize(16, 16))
        self.btn_downloads.clicked.connect(self._open_downloads_dialog)

        self.btn_settings = QToolButton()
        self.btn_settings.setIcon(self._get_icon("settings"))
        self.btn_settings.setIconSize(QSize(16, 16))
        self.btn_settings.clicked.connect(self._open_settings_dialog)

        layout.addWidget(self.btn_downloads)
        layout.addWidget(self.btn_settings)

        # Бейдж приватного режима (surf Private Window)
        if self.is_private:
            self.lbl_private = QLabel(f" {tr('private_badge')} ")
            self.lbl_private.setStyleSheet(
                "background-color: #7c3aed; color: #ffffff; border-radius: 4px; "
                "font-weight: bold; font-size: 11px; padding: 2px 6px;"
            )
            layout.addWidget(self.lbl_private)

        # Кнопка меню-гамбургер (≡)
        self.btn_menu = QToolButton()
        self.btn_menu.setObjectName("btnMenu")
        self.btn_menu.setIcon(self._get_icon("menu_burger"))
        self.btn_menu.setIconSize(QSize(16, 16))
        self.btn_menu.setToolTip(tr("tip_menu_surf"))
        self.btn_menu.clicked.connect(self._show_hamburger_menu)
        layout.addWidget(self.btn_menu)

        self.main_layout.addWidget(self.nav_toolbar)

    def _build_menu(self) -> None:
        self.main_menubar = self.menuBar()
        self.main_menubar.triggered.connect(self._on_menu_action_triggered)

        # Файл
        self.file_menu = self.main_menubar.addMenu("")
        self.act_new_tab = self.file_menu.addAction("")
        self.act_new_tab.setShortcut(QKeySequence("Ctrl+T"))
        self.act_new_tab.triggered.connect(lambda: self.add_new_tab())

        self.act_new_private = self.file_menu.addAction("")
        self.act_new_private.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_new_private.triggered.connect(self._open_private_window)

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
        self.act_reader_menu = self.view_menu.addAction("")
        self.act_reader_menu.setShortcut(QKeySequence("Ctrl+Alt+R"))
        self.act_reader_menu.triggered.connect(self._toggle_reader_mode)

        self.act_source = self.view_menu.addAction("")
        self.act_source.setShortcut(QKeySequence("Ctrl+U"))
        self.act_source.triggered.connect(self._show_page_source)

        self.view_menu.addSeparator()
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

        # Ctrl+Shift+T — «вернуть закрытую вкладку» (см. _setup_shortcuts), а при
        # пустом списке закрытых вкладок он сам восстанавливает сессию
        self.act_restore_session = self.history_menu.addAction("")
        self.act_restore_session.triggered.connect(self.restore_previous_session)

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

        self.act_pages = self.help_menu.addAction("")
        self.act_pages.triggered.connect(lambda: self.add_new_tab("surf://pages"))

        self.act_about = self.help_menu.addAction("")
        self.act_about.triggered.connect(self._show_about)

        # Привязываем действия меню ещё и к самому окну: при скрытой строке меню
        # их сочетания клавиш продолжают работать. Дублировать их через QShortcut
        # нельзя — при видимом меню Qt считает такие сочетания неоднозначными
        # и не выполняет ни одно из них.
        for menu in (
            self.file_menu,
            self.edit_menu,
            self.view_menu,
            self.history_menu,
            self.bm_menu,
            self.tools_menu,
            self.help_menu,
        ):
            for action in menu.actions():
                if not action.isSeparator():
                    self.addAction(action)

    def _show_hamburger_menu(self) -> None:
        """Всплывающее главное меню при клике на гамбургер ≡."""
        menu = QMenu(self)

        act_nt = menu.addAction(tr("act_new_tab"))
        act_nt.setShortcut(QKeySequence("Ctrl+T"))
        act_nt.triggered.connect(lambda: self.add_new_tab())

        act_np = menu.addAction(tr("menu_new_private_window"))
        act_np.setShortcut(QKeySequence("Ctrl+Shift+P"))
        act_np.triggered.connect(self._open_private_window)

        menu.addSeparator()

        zoom_menu = menu.addMenu(tr("menu_view"))
        act_zin = zoom_menu.addAction(tr("act_zoom_in"))
        act_zin.triggered.connect(self._zoom_in)
        act_zout = zoom_menu.addAction(tr("act_zoom_out"))
        act_zout.triggered.connect(self._zoom_out)
        act_zreset = zoom_menu.addAction(tr("act_zoom_reset"))
        act_zreset.triggered.connect(self._zoom_reset)
        act_full = zoom_menu.addAction(tr("act_fullscreen"))
        act_full.triggered.connect(self._toggle_fullscreen)

        menu.addSeparator()

        act_bms = menu.addAction(tr("menu_bookmarks"))
        act_bms.setShortcut(QKeySequence("Ctrl+Shift+O"))
        act_bms.triggered.connect(self._open_history_dialog)

        act_hist = menu.addAction(tr("menu_history"))
        act_hist.setShortcut(QKeySequence("Ctrl+H"))
        act_hist.triggered.connect(self._open_history_dialog)

        act_rest = menu.addAction(tr("act_restore_session"))
        act_rest.triggered.connect(self.restore_previous_session)

        act_dl = menu.addAction(tr("act_downloads"))
        act_dl.setShortcut(QKeySequence("Ctrl+J"))
        act_dl.triggered.connect(self._open_downloads_dialog)

        menu.addSeparator()

        act_find = menu.addAction(tr("act_find"))
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self._show_find_bar)

        act_save = menu.addAction(tr("act_save_page"))
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save_page)

        act_shot = menu.addAction(tr("act_screenshot"))
        act_shot.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_shot.triggered.connect(self._capture_screenshot)

        menu.addSeparator()

        act_sett = menu.addAction(tr("act_settings"))
        act_sett.setShortcut(QKeySequence("Ctrl+,"))
        act_sett.triggered.connect(self._open_settings_dialog)

        act_help = menu.addAction(tr("act_help"))
        act_help.triggered.connect(self._open_help)

        act_about = menu.addAction(tr("act_about"))
        act_about.triggered.connect(self._show_about)

        menu.addSeparator()
        act_exit = menu.addAction(tr("act_exit"))
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)

        menu.exec(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height())))
        menu.deleteLater()

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
        self.act_new_private.setText(tr("menu_new_private_window"))
        self.act_close_tab.setText(tr("act_close_tab"))
        self.act_open_file.setText(tr("act_open_file"))
        self.act_save_page.setText(tr("act_save_page"))
        self.act_screenshot.setText(tr("act_screenshot"))
        self.act_exit.setText(tr("act_exit"))

        self.edit_menu.setTitle(tr("menu_edit"))
        self.act_find.setText(tr("act_find"))
        self.act_copy_url.setText(tr("act_copy_url"))

        self.view_menu.setTitle(tr("menu_view"))
        self.act_reader_menu.setText(tr("act_reader"))
        self.act_source.setText(tr("act_source"))
        self.act_zoom_in.setText(tr("act_zoom_in"))
        self.act_zoom_out.setText(tr("act_zoom_out"))
        self.act_zoom_reset.setText(tr("act_zoom_reset"))
        self.act_fullscreen.setText(tr("act_fullscreen"))

        self.history_menu.setTitle(tr("menu_history"))
        self.act_history.setText(tr("act_show_history"))
        if hasattr(self, "act_restore_session"):
            self.act_restore_session.setText(tr("act_restore_session"))
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
        if hasattr(self, "act_pages"):
            self.act_pages.setText("surf://pages (" + ("Все страницы" if get_language() == "ru" else "All Pages") + ")")
        self.act_about.setText(tr("act_about"))

        # Тулбар
        self.btn_back.setToolTip(tr("tip_back"))
        self.btn_forward.setToolTip(tr("tip_forward"))
        self.btn_reload.setToolTip(tr("tip_reload"))
        self.btn_home.setToolTip(tr("tip_home"))
        self.address_bar.setPlaceholderText(tr("address_placeholder"))
        self.btn_downloads.setToolTip(tr("tip_downloads"))
        self.btn_settings.setToolTip(tr("tip_settings"))
        self.btn_menu.setToolTip(tr("tip_menu_surf"))
        self.new_tab_btn.setToolTip(tr("tip_new_tab"))
        self.zoom_btn.setToolTip(tr("act_zoom_reset"))

        self.act_reader.setToolTip(tr("tip_reader"))
        self.act_star.setToolTip(tr("tip_bookmark"))

        # Заголовок окна
        self.setWindowTitle(tr("private_window_title") if self.is_private else tr("app_title"))
        if hasattr(self, "lbl_private"):
            self.lbl_private.setText(f" {tr('private_badge')} ")

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
        # Здесь только сочетания, которых НЕТ у действий меню (см. _build_menu):
        # Ctrl+T, Ctrl+W, Ctrl+F, Ctrl+S, зум, F11 и т.п. обрабатываются QAction меню.

        # Навигация по вкладкам
        QShortcut(QKeySequence("Ctrl+N"), self, lambda: self._open_new_window())
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
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, self._open_history_dialog)
        QShortcut(QKeySequence("Ctrl+P"), self, self._save_page)

        # Поиск
        QShortcut(QKeySequence("F3"), self, self._find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self._find_prev)
        QShortcut(QKeySequence("Ctrl+G"), self, self._find_next)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._find_prev)

        # Системные
        QShortcut(QKeySequence("Escape"), self, self._handle_escape)
        QShortcut(QKeySequence("F10"), self, self._toggle_menu_visibility)

    def _setup_downloads(self) -> None:
        try:
            self.profile.downloadRequested.disconnect()
        except Exception:
            pass
        self.profile.downloadRequested.connect(self._handle_download_requested)

    def _apply_theme(self) -> None:
        theme_name = self.db.get_setting("theme", "dark")
        is_dark = theme_name == "dark"
        accent = self.db.get_setting("accent_color", "#0060df")

        # Тема или акцент могли измениться — иконки нужно перерисовать
        self._icon_cache = {}
        self._is_dark_theme = is_dark
        style_file = f"{theme_name}.qss"
        style_path = os.path.join(STYLES_DIR, style_file)

        if os.path.exists(style_path):
            with open(style_path, encoding="utf-8") as f:
                qss = f.read()
            # Динамически внедряем выбранный пользователем акцентный цвет
            qss = qss.replace("__ACCENT__", accent)
            self.setStyleSheet(qss)

        # Обновляем тему таббара
        if hasattr(self, "tab_bar") and isinstance(self.tab_bar, ClosableTabBar):
            vol_icon = self._get_icon("volume-2")
            vol_x_icon = self._get_icon("volume-x")
            self.tab_bar.set_theme_mode(is_dark, vol_icon, vol_x_icon)

        # Обновляем все тулбарные иконки в соответствии с темой
        if hasattr(self, "btn_back"):
            self.btn_back.setIcon(self._get_icon("back"))
            self.btn_forward.setIcon(self._get_icon("forward"))
            self.btn_reload.setIcon(self._get_icon("reload"))
            self.btn_home.setIcon(self._get_icon("home"))
            self.btn_downloads.setIcon(self._get_icon("downloads"))
            self.btn_settings.setIcon(self._get_icon("settings"))
            self.btn_menu.setIcon(self._get_icon("menu_burger"))
            self.new_tab_btn.setIcon(self._get_icon("plus"))

        if hasattr(self, "btn_close_find"):
            self.btn_close_find.setIcon(self._get_icon("close"))

        if hasattr(self, "act_reader"):
            self.act_reader.setIcon(self._get_icon("reader"))

        # Обновляем значки безопасности и закладок в строке адреса
        tab = self.current_tab()
        current_url = tab.current_url if tab else ""
        self._update_bookmark_icon(current_url)
        self._update_security_and_shield_icons(current_url)

        # Обновляем тему всех открытых вкладок и режима чтения
        if hasattr(self, "tab_stack"):
            for i in range(self.tab_stack.count()):
                t = self.tab_stack.widget(i)
                if t and hasattr(t, "set_theme_mode"):
                    t.set_theme_mode(is_dark)

        self._apply_dwm_titlebar()

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
        tab = BrowserTab(self.db, self, profile=self.profile)
        idx = self.tab_stack.addWidget(tab)
        self.tab_bar.addTab(tr("new_tab"))
        self.tab_bar.setTabIcon(idx, self._get_icon("globe"))
        self.tab_bar.setCurrentIndex(idx)

        tab.title_changed.connect(lambda title, t=tab: self._update_tab_title(t, title))
        tab.url_changed.connect(lambda u, t=tab: self._update_tab_url(t, u))
        tab.icon_changed.connect(lambda icon, t=tab: self._on_tab_icon_changed(t, icon))
        tab.audio_state_changed.connect(lambda aud, mut, t=tab: self._on_tab_audio_state_changed(t, aud, mut))
        tab.load_progress.connect(lambda p, t=tab: self._on_tab_progress(t, p))
        tab.open_new_tab.connect(lambda u: self.add_new_tab(u))
        tab.web_view.loadFinished.connect(lambda ok, t=tab: self._on_tab_load_finished(t, ok))
        tab.web_view.page().linkHovered.connect(self._on_link_hovered)

        if url:
            tab.load_url(url)
        else:
            tab.show_speed_dial()

        self._focus_address_bar()
        return tab

    def close_tab(self, index: int, save_to_recent: bool = True) -> None:
        if self.tab_bar.count() > 1:
            tab = self.tab_stack.widget(index)
            if tab and isinstance(tab, BrowserTab):
                url = tab.current_url
                if save_to_recent and url and not url.startswith("surf://newtab") and url != "about:blank":
                    self._recently_closed_urls.append(url)

            # Сначала убираем виджет из стека, затем вкладку из таббара: иначе
            # currentChanged от removeTab() сработает, пока индексы стека ещё сдвинуты
            widget = self.tab_stack.widget(index)
            if widget:
                self.tab_stack.removeWidget(widget)
            self.tab_bar.removeTab(index)
            if widget:
                widget.deleteLater()
            self._on_tab_bar_current_changed(self.tab_bar.currentIndex())
            self.tab_bar.update_movable_state()
        else:
            current = self.current_tab()
            if current:
                current.show_speed_dial()
            self.tab_bar.update_movable_state()

    def _detach_tab_to_new_window(self, tab_idx: int, drop_pos: QPoint) -> None:
        """Отрывает вкладку и открывает её в отдельном новом окне браузера."""
        if self.tab_bar.count() <= 1:
            return
        if not (0 <= tab_idx < self.tab_stack.count()):
            return

        old_tab = self.tab_stack.widget(tab_idx)
        if not old_tab or not isinstance(old_tab, BrowserTab):
            return

        url = old_tab.current_url

        # Создаем новое окно браузера
        new_win = MainWindow(is_private=self.is_private)
        new_win.resize(self.size())

        # Позиционируем окно в месте сброса курсора
        target_x = max(20, drop_pos.x() - 140)
        target_y = max(20, drop_pos.y() - 30)
        new_win.move(target_x, target_y)

        # Закрываем вкладку в исходном окне
        self.close_tab(tab_idx, save_to_recent=False)

        # Открываем перенесённый URL в новом окне
        target_tab = new_win.current_tab()
        if target_tab:
            if url and not url.startswith("surf://newtab") and url != "about:blank":
                target_tab.load_url(url)
            else:
                target_tab.show_speed_dial()

        new_win.show()
        new_win.raise_()
        new_win.activateWindow()

    def _save_current_session(self) -> None:
        """Сохраняет список открытых вкладок текущего окна для восстановления."""
        if self.is_private:
            return
        tabs = []
        for i in range(self.tab_bar.count()):
            tab = self.tab_stack.widget(i)
            if tab and isinstance(tab, BrowserTab):
                url = tab.current_url
                if url and not url.startswith("data:"):
                    tabs.append(
                        {
                            "url": url,
                            "title": tab.current_title,
                            "tab_index": i,
                            "is_active": (i == self.tab_bar.currentIndex()),
                        }
                    )
        if tabs:
            self.db.save_session_tabs(tabs)

    def restore_previous_session(self) -> int:
        """Восстанавливает вкладки сохранённой сессии."""
        if self.is_private:
            return 0
        saved_tabs = self.db.get_saved_session_tabs()
        if not saved_tabs:
            self.status_bar.showMessage(tr("status_no_session"), 3000)
            return 0

        # Если текущая единственная вкладка пустая/speed dial, закроем её после восстановления
        cur_tab = self.current_tab()
        initial_is_blank = (
            self.tab_bar.count() == 1
            and cur_tab is not None
            and (
                not cur_tab.current_url
                or cur_tab.current_url.startswith("surf://newtab")
                or cur_tab.current_url == "about:blank"
            )
        )

        active_idx = 0
        restored = 0
        for item in saved_tabs:
            url = item.get("url")
            if url:
                tab = self.add_new_tab(url)
                if item.get("is_active"):
                    active_idx = self.tab_stack.indexOf(tab)
                restored += 1

        if initial_is_blank and self.tab_bar.count() > 1:
            self.close_tab(0)

        if 0 <= active_idx < self.tab_bar.count():
            self.tab_bar.setCurrentIndex(active_idx)

        self.status_bar.showMessage(tr("status_session_restored", count=restored), 4000)
        return restored

    def _reopen_closed_tab(self) -> None:
        if self._recently_closed_urls:
            url = self._recently_closed_urls.pop()
            self.add_new_tab(url)
        else:
            self.restore_previous_session()

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
                self._update_security_and_shield_icons(url)
                self._remember_tab_activity(tab)
                self._wake_tab(tab)
                self._apply_site_zoom(tab)
                self._update_progress(getattr(tab, "load_progress_value", 100))

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
        self._apply_site_zoom(tab)
        if tab == self.current_tab():
            self.address_bar.setText("" if url.startswith("surf://newtab") else url)
            self._update_bookmark_icon(url)
            self._update_security_and_shield_icons(url)

    def _on_tab_icon_changed(self, tab: BrowserTab, icon: QIcon) -> None:
        idx = self.tab_stack.indexOf(tab)
        if idx >= 0:
            self.tab_bar.setTabIcon(idx, icon if not icon.isNull() else self._get_icon("globe"))

    def _on_tab_audio_state_changed(self, tab: BrowserTab, audible: bool, muted: bool) -> None:
        idx = self.tab_stack.indexOf(tab)
        if idx >= 0:
            self.tab_bar.set_tab_audio(idx, audible, muted)

    def _toggle_tab_audio_mute(self, index: int) -> None:
        tab = self.tab_stack.widget(index)
        if tab and isinstance(tab, BrowserTab):
            tab.toggle_audio_mute()

    def _on_tab_progress(self, tab: BrowserTab, progress: int) -> None:
        """Запоминает прогресс вкладки; общий индикатор показывает только активную."""
        tab.load_progress_value = progress
        if tab is self.current_tab():
            self._update_progress(progress)

    def _update_progress(self, progress: int) -> None:
        loading = progress < 100
        self.progress_bar.setValue(progress)
        # isHidden(), а не isVisible(): пока окно не показано, isVisible() всегда False
        if loading == self.progress_bar.isHidden():
            # Меняем видимость и иконку только при смене состояния, а не на каждый тик
            self.progress_bar.setVisible(loading)
            self.btn_reload.setIcon(self._get_icon("stop" if loading else "reload"))

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

    # --- Навигация и адресная строка ---

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
            if getattr(tab, "load_progress_value", 100) < 100:
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

    # --- Безопасность и защита от отслеживания ---

    def _prefetch_certificate(self, url: str) -> None:
        if not url.startswith("https://"):
            return
        host = QUrl(url).host()
        if not host or host in self._cert_cache:
            return

        import threading

        def worker():
            try:
                data = fetch_certificate_details(url, timeout=3.0)
                self._cert_cache[host] = data
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_tab_load_finished(self, tab: BrowserTab, ok: bool) -> None:
        # Загрузка завершена (в т.ч. остановлена/с ошибкой) — прогресс не должен «зависнуть»
        self._on_tab_progress(tab, 100)
        if ok and tab.current_url:
            self._prefetch_certificate(tab.current_url)
            self._apply_site_zoom(tab)

    def _update_security_and_shield_icons(self, url: str) -> None:
        if not hasattr(self, "act_ssl") or not hasattr(self, "act_shield"):
            return

        is_new_tab = not url or url.startswith("surf://newtab") or url == "about:blank"
        is_internal = url.startswith("surf://")

        if is_new_tab:
            # На новой вкладке / главной странице скрываем специфичные веб-значки
            self.act_ssl.setIcon(self._get_icon("search"))
            self.act_ssl.setToolTip(tr("search_placeholder"))
            self.act_shield.setVisible(False)
            self.act_reader.setVisible(False)
            self.act_star.setVisible(False)
            return

        if is_internal:
            # На внутренних страницах surf:// (about, history, settings, help, pages и др.)
            self.act_ssl.setIcon(self._get_icon("globe"))
            self.act_ssl.setToolTip(f"surf 1.0 — {url}")
            self.act_shield.setVisible(False)
            self.act_reader.setVisible(False)
            self.act_star.setVisible(False)
            return

        # На реальных веб-страницах показываем весь инструментарий
        self.act_shield.setVisible(True)
        self.act_reader.setVisible(True)
        self.act_star.setVisible(True)

        if url.startswith("https://"):
            self.act_ssl.setIcon(self._get_icon("lock"))
            self.act_ssl.setToolTip(tr("tip_ssl_secure"))
        elif url.startswith("http://"):
            self.act_ssl.setIcon(self._get_icon("lock"))
            self.act_ssl.setToolTip(tr("tip_ssl_insecure"))
        else:
            self.act_ssl.setIcon(self._get_icon("globe"))
            self.act_ssl.setToolTip(tr("app_title"))

        blocked_count = self.tracking_interceptor.blocked_count if self.tracking_interceptor else 0
        self.act_shield.setIcon(self._get_icon("shield"))
        self.act_shield.setToolTip(f"{tr('tip_shield_protection')}\n{tr('shield_blocked_text', count=blocked_count)}")

    def _on_blocked_count_changed(self, count: int) -> None:
        tab = self.current_tab()
        current_url = tab.current_url if tab else ""
        self._update_security_and_shield_icons(current_url)

    def _show_security_info(self) -> None:
        tab = self.current_tab()
        url = tab.current_url if tab else ""
        if not url or url.startswith("surf://newtab") or url == "about:blank":
            return

        host = QUrl(url).host() or url
        cert_data = self._cert_cache.get(host)
        if not cert_data:
            cert_data = fetch_certificate_details(url)
            self._cert_cache[host] = cert_data

        dlg = CertificateDialog(url, cert_data=cert_data, parent=self)
        dlg.exec()

    def _show_tracking_protection_dialog(self) -> None:
        TrackingProtectionDialog(self.tracking_interceptor, self).exec()

        tab = self.current_tab()
        self._update_security_and_shield_icons(tab.current_url if tab else "")

    def _open_private_window(self) -> None:
        """Открывает новое приватное окно surf (Off-The-Record)."""
        win = MainWindow(is_private=True)
        win.show()

    def _open_new_window(self) -> None:
        win = MainWindow(is_private=False)
        win.show()

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
        if not hasattr(self, "act_star"):
            return
        if url and self.db.is_bookmarked(url):
            self.act_star.setIcon(self._get_icon("star_filled"))
        else:
            self.act_star.setIcon(self._get_icon("star"))

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

    # --- Масштабирование (запоминается отдельно для каждого сайта) ---

    @staticmethod
    def _site_host(url: str) -> str:
        """Домен сайта, для которого храним масштаб ('' для служебных страниц)."""
        if not url or url.startswith("surf://"):
            return ""
        return QUrl(url).host().lower()

    @property
    def zoom_factor(self) -> float:
        """Масштаб текущей вкладки."""
        tab = self.current_tab()
        return round(tab.web_view.zoomFactor(), 2) if tab else 1.0

    def _zoom_in(self) -> None:
        self._set_zoom(min(ZOOM_MAX, self.zoom_factor + ZOOM_STEP))

    def _zoom_out(self) -> None:
        self._set_zoom(max(ZOOM_MIN, self.zoom_factor - ZOOM_STEP))

    def _zoom_reset(self) -> None:
        self._set_zoom(1.0)

    def _set_zoom(self, zoom: float) -> None:
        """Меняет масштаб текущей вкладки и запоминает его для сайта (кроме приватного окна)."""
        tab = self.current_tab()
        if not tab:
            return
        zoom = round(zoom, 2)
        tab.web_view.setZoomFactor(zoom)
        host = self._site_host(tab.current_url)
        if host and not self.is_private:
            self.db.set_site_zoom(host, zoom)
        self._update_zoom_label()

    def _apply_site_zoom(self, tab: BrowserTab) -> None:
        """Ставит вкладке сохранённый для её сайта масштаб (по умолчанию 100%)."""
        zoom = self.db.get_site_zoom(self._site_host(tab.current_url)) or 1.0
        if abs(tab.web_view.zoomFactor() - zoom) > 0.001:
            tab.web_view.setZoomFactor(zoom)
        if tab is self.current_tab():
            self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self.zoom_btn.setText(f"{int(round(self.zoom_factor * 100))}%")

    # --- Усыпление неактивных вкладок ---

    def _remember_tab_activity(self, new_active: BrowserTab) -> None:
        """Отмечает время, когда вкладка была активной в последний раз."""
        now = time.monotonic()
        if self._active_tab is not None and self._active_tab is not new_active:
            self._active_tab.last_active = now
        new_active.last_active = now
        self._active_tab = new_active

    def _sleep_inactive_tabs(self) -> None:
        """Выгружает из памяти вкладки, которые давно не открывали (как в Chrome/Edge)."""
        if self.db.get_setting("tab_sleep_enabled", "1") != "1":
            return
        now = time.monotonic()
        limit_seconds = TAB_SLEEP_MINUTES * 60
        current = self.current_tab()
        for index in range(self.tab_stack.count()):
            tab = self.tab_stack.widget(index)
            if not isinstance(tab, BrowserTab) or tab is current:
                continue
            page = tab.web_view.page()
            is_web_page = tab.stack.currentIndex() == 0 and tab.current_url.startswith(("http://", "https://"))
            if (
                not is_web_page
                or page.lifecycleState() != QWebEnginePage.LifecycleState.Active
                or page.recentlyAudible()  # не усыпляем вкладку, где играет звук
                or now - getattr(tab, "last_active", now) < limit_seconds
            ):
                continue
            page.setLifecycleState(QWebEnginePage.LifecycleState.Discarded)
            if page.lifecycleState() == QWebEnginePage.LifecycleState.Discarded:
                self.tab_bar.setTabTextColor(index, QColor(SLEEPING_TAB_COLOR))
                self.tab_bar.setTabToolTip(index, tr("tip_tab_sleeping"))

    def _wake_tab(self, tab: BrowserTab) -> None:
        """Будит усыплённую вкладку: Chromium заново загружает страницу."""
        page = tab.web_view.page()
        if page.lifecycleState() != QWebEnginePage.LifecycleState.Active:
            page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
        index = self.tab_stack.indexOf(tab)
        if index >= 0:
            self.tab_bar.setTabTextColor(index, QColor())  # вернуть цвет из темы
            self.tab_bar.setTabToolTip(index, tab.current_title)

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
        self._apply_profile_settings()
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
        self.add_new_tab("surf://about")

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
        if self in MainWindow._open_windows:
            MainWindow._open_windows.remove(self)

        if not self.is_private and self.db.get_setting("privacy_clear_on_exit", "0") != "1":
            self._save_current_session()

        if self.is_private:
            self.profile.clearHttpCache()
            self.profile.cookieStore().deleteAllCookies()
        elif self.db.get_setting("privacy_clear_on_exit", "0") == "1":
            self.profile.clearHttpCache()
            self.profile.cookieStore().deleteAllCookies()
            self.db.clear_history("all")
            self.db.clear_saved_session()
        super().closeEvent(event)


def main():
    try:
        register_surf_scheme()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("surf")
    app.setOrganizationName("surf-browser")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
