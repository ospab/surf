"""
Модуль улучшенной защиты от отслеживания (Enhanced Tracking Protection).
Перехватывает сетевые запросы и блокирует известные рекламные и трекерные домены.
"""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor


class TrackingProtectionInterceptor(QWebEngineUrlRequestInterceptor):
    blocked_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_enabled = True
        self._blocked_count = 0
        self._blocked_domains = {
            # Популярные трекеры и рекламные сети
            "google-analytics.com",
            "googletagmanager.com",
            "doubleclick.net",
            "googlesyndication.com",
            "adservice.google.com",
            "an.yandex.ru",
            "mc.yandex.ru",
            "adfox.ru",
            "criteo.com",
            "criteo.net",
            "connect.facebook.net",
            "scorecardresearch.com",
            "hotjar.com",
            "clarity.ms",
            "ads.twitter.com",
            "moatads.com",
            "outbrain.com",
            "taboola.com",
            "rubiconproject.com",
            "adsystem.com",
            "advertising.com",
            "admob.com",
            "trafficjunky.com",
            "openx.net",
            "pubmatic.com",
            "adnxs.com",
        }

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self._is_enabled = value

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    def reset_count(self) -> None:
        self._blocked_count = 0
        self.blocked_count_changed.emit(0)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        if not self._is_enabled:
            return

        url = info.requestUrl()
        host = url.host().lower()
        if not host:
            return

        for domain in self._blocked_domains:
            if host == domain or host.endswith("." + domain):
                info.block(True)
                self._blocked_count += 1
                self.blocked_count_changed.emit(self._blocked_count)
                return
