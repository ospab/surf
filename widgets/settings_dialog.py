import os

from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.constants import SURF_USER_AGENT
    from surf.database import Database
    from surf.i18n import set_language, tr
    from surf.utils.device_service import DeviceService
except ModuleNotFoundError:
    from constants import SURF_USER_AGENT
    from database import Database
    from i18n import set_language, tr
    from utils.device_service import DeviceService

SEARCH_ENGINES = {
    0: ("google", "Google", "https://www.google.com/search?q="),
    1: ("yandex", "Яндекс", "https://yandex.ru/search/?text="),
    2: ("duckduckgo", "DuckDuckGo", "https://duckduckgo.com/?q="),
    3: ("bing", "Bing", "https://www.bing.com/search?q="),
}

USER_AGENTS = {
    0: (
        "surf",
        SURF_USER_AGENT,
    ),
    1: ("surf_pure", "Surf/1.0 (Windows NT 10.0; Win64; x64)"),
    2: (
        "chrome",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ),
    3: ("firefox", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"),
}

PROXY_TYPES = {
    0: "none",
    1: "system",
    2: "http",
    3: "socks5",
}

# id радиокнопок темы в QButtonGroup -> значение настройки "theme"
THEME_IDS = {0: "dark", 1: "light"}

# Через сколько минут неактивности вкладка «засыпает» (см. MainWindow._sleep_inactive_tabs)
TAB_SLEEP_MINUTES = 10


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        # Способ 1: .ui загружается во время работы, без pyuic6
        ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "settings.ui")
        uic.loadUi(ui_path, self)

        # Радиокнопки темы объединены в группу: выбрать можно только одну
        self.themeGroup = QButtonGroup(self)
        self.themeGroup.addButton(self.themeDarkRadio, 0)
        self.themeGroup.addButton(self.themeLightRadio, 1)

        self._setup_devices_tab()
        self._load_current_settings()
        self._connect_signals()

    def _setup_devices_tab(self) -> None:
        """Вкладка «Устройства»: микрофон и камера по умолчанию, разрешения сайтов."""
        self.devicesTab = QWidget()
        dev_layout = QVBoxLayout(self.devicesTab)
        dev_layout.setContentsMargins(16, 16, 16, 16)
        dev_layout.setSpacing(16)

        # 1. Группа устройств по умолчанию
        self.defaultDevGroup = QGroupBox(tr("group_default_devices"))
        grp_layout = QFormLayout(self.defaultDevGroup)
        grp_layout.setSpacing(12)

        self.defaultMicCombo = QComboBox()
        self.defaultCamCombo = QComboBox()

        self.lblDefaultMic = QLabel(tr("lbl_default_mic"))
        self.lblDefaultCam = QLabel(tr("lbl_default_camera"))
        grp_layout.addRow(self.lblDefaultMic, self.defaultMicCombo)
        grp_layout.addRow(self.lblDefaultCam, self.defaultCamCombo)
        dev_layout.addWidget(self.defaultDevGroup)

        # 2. Группа сохраненных разрешений сайтов
        self.siteDevGroup = QGroupBox(tr("group_site_devices"))
        site_layout = QVBoxLayout(self.siteDevGroup)
        site_layout.setSpacing(8)

        self.siteDevTable = QTableWidget()
        self.siteDevTable.setColumnCount(4)
        self.siteDevTable.setHorizontalHeaderLabels(
            [
                tr("col_site"),
                tr("col_microphone"),
                tr("col_camera"),
                tr("col_action"),
            ]
        )
        self.siteDevTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.siteDevTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.siteDevTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.siteDevTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.siteDevTable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.siteDevTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        site_layout.addWidget(self.siteDevTable)

        tbl_btn_row = QHBoxLayout()
        tbl_btn_row.addStretch()
        self.clearAllDevBtn = QPushButton(tr("btn_clear_all_devices"))
        self.clearAllDevBtn.clicked.connect(self._clear_all_site_devices)
        tbl_btn_row.addWidget(self.clearAllDevBtn)
        site_layout.addLayout(tbl_btn_row)

        dev_layout.addWidget(self.siteDevGroup, 1)

        self.settingsTabs.addTab(self.devicesTab, tr("tab_devices"))

    def _load_device_settings(self) -> None:
        """Загружает список устройств и текущие настройки микрофона и камеры."""
        svc = DeviceService.instance()

        # Микрофоны
        self.defaultMicCombo.clear()
        self.defaultMicCombo.addItem(tr("system_default_device"), "")
        for m in svc.get_audio_inputs():
            label = m["name"]
            if m.get("is_default"):
                label += f" ({tr('lbl_default')})"
            self.defaultMicCombo.addItem(label, m["name"])

        # Камеры
        self.defaultCamCombo.clear()
        self.defaultCamCombo.addItem(tr("system_default_device"), "")
        for c in svc.get_video_inputs():
            label = c["name"]
            if c.get("is_default"):
                label += f" ({tr('lbl_default')})"
            self.defaultCamCombo.addItem(label, c["name"])

        saved_mic = self.db.get_setting("default_audio_device", "")
        if saved_mic:
            idx = self.defaultMicCombo.findData(saved_mic)
            if idx >= 0:
                self.defaultMicCombo.setCurrentIndex(idx)

        saved_cam = self.db.get_setting("default_video_device", "")
        if saved_cam:
            idx = self.defaultCamCombo.findData(saved_cam)
            if idx >= 0:
                self.defaultCamCombo.setCurrentIndex(idx)

        self._load_site_device_table()

    def _load_site_device_table(self) -> None:
        """Заполняет таблицу сохранённых разрешений сайтов на микрофоны и камеры."""
        self.siteDevTable.setRowCount(0)
        prefs = self.db.get_all_site_device_preferences()
        self.siteDevTable.setRowCount(len(prefs))
        for row, item in enumerate(prefs):
            origin = item.get("origin", "")
            allow_a = item.get("allow_audio", True)
            dev_a = item.get("audio_device", "")
            allow_v = item.get("allow_video", True)
            dev_v = item.get("video_device", "")

            site_item = QTableWidgetItem(origin)
            self.siteDevTable.setItem(row, 0, site_item)

            mic_txt = dev_a if allow_a else tr("device_blocked")
            if allow_a and not dev_a:
                mic_txt = tr("system_default_device")
            mic_item = QTableWidgetItem(mic_txt)
            self.siteDevTable.setItem(row, 1, mic_item)

            cam_txt = dev_v if allow_v else tr("device_blocked")
            if allow_v and not dev_v:
                cam_txt = tr("system_default_device")
            cam_item = QTableWidgetItem(cam_txt)
            self.siteDevTable.setItem(row, 2, cam_item)

            del_btn = QPushButton(tr("btn_delete_perm"))
            del_btn.clicked.connect(lambda checked, orig=origin: self._delete_site_device(orig))
            self.siteDevTable.setCellWidget(row, 3, del_btn)

    def _delete_site_device(self, origin: str) -> None:
        self.db.delete_site_device_preference(origin)
        self.db.delete_site_permission(origin, "media")
        self.db.delete_site_permission(origin, "audio")
        self.db.delete_site_permission(origin, "video")
        self._load_site_device_table()

    def _clear_all_site_devices(self) -> None:
        self.db.clear_site_device_preferences()
        self._load_site_device_table()

    def _load_current_settings(self) -> None:
        # Основные
        self.homeEdit.setText(self.db.get_setting("homepage", "https://www.google.com"))

        current_engine = self.db.get_setting("search_engine", "https://www.google.com/search?q=")
        engine_type = self.db.get_setting("search_engine_type", "google")
        custom_engine = self.db.get_setting("custom_search_engine", "https://www.google.com/search?q=")

        found_idx = None
        for idx, (code, _, url) in SEARCH_ENGINES.items():
            if code == engine_type or url == current_engine:
                found_idx = idx
                break

        if found_idx is not None:
            self.searchCombo.setCurrentIndex(found_idx)
            self.searchCustomEdit.setText(SEARCH_ENGINES[found_idx][2])
            self.searchCustomEdit.setReadOnly(True)
        else:
            self.searchCombo.setCurrentIndex(4)  # Пользовательский
            self.searchCustomEdit.setText(current_engine or custom_engine)
            self.searchCustomEdit.setReadOnly(False)

        auto_hide_menu = self.db.get_setting("menu_bar_auto_hide", "1")
        self.menuBarCombo.setCurrentIndex(0 if auto_hide_menu == "1" else 1)

        lang = self.db.get_setting("language", "ru")
        set_language(lang)
        self.langCombo.setCurrentIndex(0 if lang == "ru" else 1)
        self._retranslate_ui()

        if not hasattr(self, "restoreSessionCheck"):
            self.restoreSessionCheck = QCheckBox(tr("pref_restore_session"))
            if self.homeGroup.layout():
                self.homeGroup.layout().addWidget(self.restoreSessionCheck)
        self.restoreSessionCheck.setChecked(self.db.get_setting("restore_session_on_startup", "1") == "1")

        if not hasattr(self, "tabSleepCheck"):
            self.tabSleepCheck = QCheckBox(tr("chk_tab_sleep", minutes=TAB_SLEEP_MINUTES))
            if self.homeGroup.layout():
                self.homeGroup.layout().addWidget(self.tabSleepCheck)
        self.tabSleepCheck.setChecked(self.db.get_setting("tab_sleep_enabled", "1") == "1")

        self.downloadPathEdit.setText(self.db.get_setting("download_folder", os.path.expanduser("~/Downloads")))

        # Приватность и User-Agent
        ua_type = self.db.get_setting("user_agent_type", "surf")
        ua_string = self.db.get_setting("custom_user_agent", USER_AGENTS[0][1])

        found_idx = None
        for idx, (code, _ua) in USER_AGENTS.items():
            if code == ua_type:
                found_idx = idx
                break

        if found_idx is not None:
            self.uaCombo.setCurrentIndex(found_idx)
            self.uaEdit.setText(USER_AGENTS[found_idx][1])
            self.uaEdit.setReadOnly(True)
        else:
            self.uaCombo.setCurrentIndex(4)
            self.uaEdit.setText(ua_string)
            self.uaEdit.setReadOnly(False)

        self.saveHistoryCheck.setChecked(self.db.get_setting("privacy_save_history", "1") == "1")
        self.clearExitCheck.setChecked(self.db.get_setting("privacy_clear_on_exit", "0") == "1")
        self.dntCheck.setChecked(self.db.get_setting("privacy_dnt", "1") == "1")

        # Прокси
        saved_proxy_type = self.db.get_setting("proxy_type", "none")
        for idx, p_name in PROXY_TYPES.items():
            if p_name == saved_proxy_type:
                self.proxyTypeCombo.setCurrentIndex(idx)
                break

        self.proxyHostEdit.setText(self.db.get_setting("proxy_host", ""))
        self.proxyPortSpin.setValue(int(self.db.get_setting("proxy_port", "8080") or "8080"))
        self.proxyUserEdit.setText(self.db.get_setting("proxy_user", ""))
        self.proxyPassEdit.setText(self.db.get_setting("proxy_password", ""))
        self._toggle_proxy_fields()

        # Оформление
        theme = self.db.get_setting("theme", "dark")
        (self.themeDarkRadio if theme == "dark" else self.themeLightRadio).setChecked(True)
        self.forceDarkSitesCheck.setChecked(self.db.get_setting("force_dark_sites", "0") == "1")

        self.accent_color = self.db.get_setting("accent_color", "#0060df")
        self._update_color_button(self.accent_color)

        # Устройства
        self._load_device_settings()

    def _connect_signals(self) -> None:
        self.browseDownloadBtn.clicked.connect(self._choose_download_dir)
        self.colorBtn.clicked.connect(self._choose_accent_color)
        self.searchCombo.currentIndexChanged.connect(self._on_search_engine_changed)
        self.uaCombo.currentIndexChanged.connect(self._on_ua_changed)
        self.proxyTypeCombo.currentIndexChanged.connect(self._toggle_proxy_fields)
        self.langCombo.currentIndexChanged.connect(self._on_lang_changed)
        self.buttonBox.accepted.connect(self._save_settings)
        self.buttonBox.rejected.connect(self.reject)

    def _on_search_engine_changed(self, index: int) -> None:
        if index in SEARCH_ENGINES:
            self.searchCustomEdit.setText(SEARCH_ENGINES[index][2])
            self.searchCustomEdit.setReadOnly(True)
        else:
            self.searchCustomEdit.setReadOnly(False)
            curr = self.searchCustomEdit.text().strip()
            preset_urls = [e[2] for e in SEARCH_ENGINES.values()]
            if not curr or curr in preset_urls:
                custom_saved = self.db.get_setting("custom_search_engine", "")
                if custom_saved and custom_saved not in preset_urls:
                    self.searchCustomEdit.setText(custom_saved)
                else:
                    self.searchCustomEdit.setText("https://")
            self.searchCustomEdit.setFocus()
            self.searchCustomEdit.selectAll()

    def _on_lang_changed(self, index: int) -> None:
        set_language("ru" if index == 0 else "en")
        self._retranslate_ui()

    def _on_ua_changed(self, index: int) -> None:
        if index in USER_AGENTS:
            self.uaEdit.setText(USER_AGENTS[index][1])
            self.uaEdit.setReadOnly(True)
        else:
            self.uaEdit.setReadOnly(False)
            self.uaEdit.setFocus()

    def _toggle_proxy_fields(self) -> None:
        idx = self.proxyTypeCombo.currentIndex()
        manual_proxy = idx in (2, 3)  # HTTP or SOCKS5
        self.proxyHostEdit.setEnabled(manual_proxy)
        self.proxyPortSpin.setEnabled(manual_proxy)
        self.proxyUserEdit.setEnabled(manual_proxy)
        self.proxyPassEdit.setEnabled(manual_proxy)

    def _choose_download_dir(self) -> None:
        current_dir = self.downloadPathEdit.text()
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Папка для загрузок",
            current_dir or os.path.expanduser("~"),
        )
        if chosen:
            self.downloadPathEdit.setText(chosen)

    def _choose_accent_color(self) -> None:
        initial = QColor(self.accent_color)
        color = QColorDialog.getColor(initial, self, "Цвет акцента")
        if color.isValid():
            self.accent_color = color.name()
            self._update_color_button(self.accent_color)

    def _update_color_button(self, hex_color: str) -> None:
        self.colorBtn.setStyleSheet(
            f"background-color: {hex_color}; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 4px 10px;"
        )

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings_title"))
        self.settingsTabs.setTabText(0, tr("tab_general"))
        self.settingsTabs.setTabText(1, tr("tab_privacy"))
        self.settingsTabs.setTabText(2, tr("tab_proxy"))
        self.settingsTabs.setTabText(3, tr("tab_appearance"))

        self.homeGroup.setTitle(tr("group_navigation"))
        self.homeLabel.setText(tr("lbl_homepage"))
        self.searchLabel.setText(tr("lbl_search_engine"))
        self.searchCustomLabel.setText(tr("lbl_search_url"))
        self.searchCombo.setItemText(0, tr("search_engine_google"))
        self.searchCombo.setItemText(1, tr("search_engine_yandex"))
        self.searchCombo.setItemText(2, tr("search_engine_duckduckgo"))
        self.searchCombo.setItemText(3, tr("search_engine_bing"))
        self.searchCombo.setItemText(4, tr("search_engine_custom"))
        self.searchCustomEdit.setPlaceholderText(tr("search_custom_placeholder"))
        self.menuLabel.setText(tr("lbl_menu_mode"))
        self.menuBarCombo.setItemText(0, tr("menu_mode_hide"))
        self.menuBarCombo.setItemText(1, tr("menu_mode_show"))
        self.langLabel.setText(tr("lbl_language"))

        self.downloadGroup.setTitle(tr("group_downloads"))
        self.browseDownloadBtn.setText(tr("btn_browse"))
        if hasattr(self, "restoreSessionCheck"):
            self.restoreSessionCheck.setText(tr("pref_restore_session"))

        self.uaGroup.setTitle(tr("group_user_agent"))
        self.uaCombo.setItemText(0, tr("ua_surf"))
        self.uaCombo.setItemText(1, tr("ua_surf_pure"))
        self.uaCombo.setItemText(2, tr("ua_chrome"))
        self.uaCombo.setItemText(3, tr("ua_firefox"))
        self.uaCombo.setItemText(4, tr("ua_custom"))

        self.historyPrivacyGroup.setTitle(tr("group_history_privacy"))
        self.saveHistoryCheck.setText(tr("chk_save_history"))
        self.clearExitCheck.setText(tr("chk_clear_exit"))
        self.dntCheck.setText(tr("chk_dnt"))

        self.proxyGroup.setTitle(tr("group_proxy"))
        self.proxyTypeLabel.setText(tr("lbl_proxy_type"))
        self.proxyTypeCombo.setItemText(0, tr("proxy_none"))
        self.proxyTypeCombo.setItemText(1, tr("proxy_system"))
        self.proxyTypeCombo.setItemText(2, tr("proxy_http"))
        self.proxyTypeCombo.setItemText(3, tr("proxy_socks5"))
        self.proxyHostLabel.setText(tr("lbl_proxy_host"))
        self.proxyPortLabel.setText(tr("lbl_proxy_port"))
        self.proxyUserLabel.setText(tr("lbl_proxy_user"))
        self.proxyPassLabel.setText(tr("lbl_proxy_pass"))

        self.appearanceGroup.setTitle(tr("group_style"))
        self.themeLabel.setText(tr("lbl_theme"))
        self.themeDarkRadio.setText(tr("theme_dark"))
        self.themeLightRadio.setText(tr("theme_light"))
        self.forceDarkSitesCheck.setText(tr("chk_force_dark"))
        if hasattr(self, "tabSleepCheck"):
            self.tabSleepCheck.setText(tr("chk_tab_sleep", minutes=TAB_SLEEP_MINUTES))
        self.colorLabel.setText(tr("lbl_accent"))
        self.colorBtn.setText(tr("btn_accent"))

        # Устройства
        self.settingsTabs.setTabText(4, tr("tab_devices"))
        if hasattr(self, "defaultDevGroup"):
            self.defaultDevGroup.setTitle(tr("group_default_devices"))
            self.lblDefaultMic.setText(tr("lbl_default_mic"))
            self.lblDefaultCam.setText(tr("lbl_default_camera"))
            self.siteDevGroup.setTitle(tr("group_site_devices"))
            self.siteDevTable.setHorizontalHeaderLabels(
                [
                    tr("col_site"),
                    tr("col_microphone"),
                    tr("col_camera"),
                    tr("col_action"),
                ]
            )
            self.clearAllDevBtn.setText(tr("btn_clear_all_devices"))

    def _save_settings(self) -> None:
        # Основные
        homepage = self.homeEdit.text().strip() or "https://www.google.com"
        self.db.set_setting("homepage", homepage)

        search_idx = self.searchCombo.currentIndex()
        if search_idx in SEARCH_ENGINES:
            engine_type = SEARCH_ENGINES[search_idx][0]
            engine_url = SEARCH_ENGINES[search_idx][2]
        else:
            engine_type = "custom"
            engine_url = self.searchCustomEdit.text().strip() or "https://www.google.com/search?q="
            self.db.set_setting("custom_search_engine", engine_url)

        self.db.set_setting("search_engine_type", engine_type)
        self.db.set_setting("search_engine", engine_url)
        self.db.set_setting("menu_bar_auto_hide", "1" if self.menuBarCombo.currentIndex() == 0 else "0")
        self.db.set_setting("download_folder", self.downloadPathEdit.text())
        if hasattr(self, "restoreSessionCheck"):
            self.db.set_setting("restore_session_on_startup", "1" if self.restoreSessionCheck.isChecked() else "0")
        if hasattr(self, "tabSleepCheck"):
            self.db.set_setting("tab_sleep_enabled", "1" if self.tabSleepCheck.isChecked() else "0")

        # Приватность и User-Agent
        ua_idx = self.uaCombo.currentIndex()
        if ua_idx in USER_AGENTS:
            ua_type = USER_AGENTS[ua_idx][0]
            ua_str = USER_AGENTS[ua_idx][1]
        else:
            ua_type = "custom"
            ua_str = self.uaEdit.text().strip() or USER_AGENTS[0][1]

        self.db.set_setting("user_agent_type", ua_type)
        self.db.set_setting("custom_user_agent", ua_str)
        self.db.set_setting("privacy_save_history", "1" if self.saveHistoryCheck.isChecked() else "0")
        self.db.set_setting("privacy_clear_on_exit", "1" if self.clearExitCheck.isChecked() else "0")
        self.db.set_setting("privacy_dnt", "1" if self.dntCheck.isChecked() else "0")

        # Прокси
        p_type = PROXY_TYPES.get(self.proxyTypeCombo.currentIndex(), "none")
        self.db.set_setting("proxy_type", p_type)
        self.db.set_setting("proxy_host", self.proxyHostEdit.text().strip())
        self.db.set_setting("proxy_port", str(self.proxyPortSpin.value()))
        self.db.set_setting("proxy_user", self.proxyUserEdit.text().strip())
        self.db.set_setting("proxy_password", self.proxyPassEdit.text())

        # Язык
        new_lang = "ru" if self.langCombo.currentIndex() == 0 else "en"
        self.db.set_setting("language", new_lang)
        set_language(new_lang)

        # Оформление
        self.db.set_setting("theme", THEME_IDS.get(self.themeGroup.checkedId(), "dark"))
        self.db.set_setting("force_dark_sites", "1" if self.forceDarkSitesCheck.isChecked() else "0")
        self.db.set_setting("accent_color", self.accent_color)

        # Устройства по умолчанию
        if hasattr(self, "defaultMicCombo"):
            def_mic = self.defaultMicCombo.currentData() or ""
            self.db.set_setting("default_audio_device", def_mic)
        if hasattr(self, "defaultCamCombo"):
            def_cam = self.defaultCamCombo.currentData() or ""
            self.db.set_setting("default_video_device", def_cam)

        self.settings_changed.emit()
        self.accept()
