import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QDialog, QFileDialog

try:
    from surf.database import Database
    from surf.i18n import get_language, set_language, tr
except ModuleNotFoundError:
    from database import Database
    from i18n import get_language, set_language, tr

SEARCH_ENGINES = {
    0: ("google", "Google", "https://www.google.com/search?q="),
    1: ("yandex", "Яндекс", "https://yandex.ru/search/?text="),
    2: ("duckduckgo", "DuckDuckGo", "https://duckduckgo.com/?q="),
    3: ("bing", "Bing", "https://www.bing.com/search?q="),
}

USER_AGENTS = {
    0: ("surf", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Surf/1.0"),
    1: ("surf_pure", "Surf/1.0 (Windows NT 10.0; Win64; x64)"),
    2: ("chrome", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    3: ("firefox", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0"),
}

PROXY_TYPES = {
    0: "none",
    1: "system",
    2: "http",
    3: "socks5",
}


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        # Способ 1: динамическая загрузка .ui файла без предварительной компиляции
        ui_path = os.path.join(os.path.dirname(__file__), "..", "ui", "settings.ui")
        uic.loadUi(ui_path, self)

        self._load_current_settings()
        self._connect_signals()

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

        self.downloadPathEdit.setText(
            self.db.get_setting("download_folder", os.path.expanduser("~/Downloads"))
        )

        # Приватность и User-Agent
        ua_type = self.db.get_setting("user_agent_type", "surf")
        ua_string = self.db.get_setting("custom_user_agent", USER_AGENTS[0][1])

        found_idx = None
        for idx, (code, val) in USER_AGENTS.items():
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
        self.themeCombo.setCurrentIndex(0 if theme == "dark" else 1)

        self.accent_color = self.db.get_setting("accent_color", "#0060df")
        self._update_color_button(self.accent_color)

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
            "Выбор папки для загрузок",
            current_dir or os.path.expanduser("~"),
        )
        if chosen:
            self.downloadPathEdit.setText(chosen)

    def _choose_accent_color(self) -> None:
        initial = QColor(self.accent_color)
        color = QColorDialog.getColor(initial, self, "Выбор акцентного цвета интерфейса")
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
        self.themeCombo.setItemText(0, tr("theme_dark"))
        self.themeCombo.setItemText(1, tr("theme_light"))
        self.colorLabel.setText(tr("lbl_accent"))
        self.colorBtn.setText(tr("btn_accent"))

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
        self.db.set_setting("theme", "dark" if self.themeCombo.currentIndex() == 0 else "light")
        self.db.set_setting("accent_color", self.accent_color)

        self.settings_changed.emit()
        self.accept()
