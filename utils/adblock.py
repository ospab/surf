"""
Модуль улучшенной защиты от отслеживания (Enhanced Tracking Protection).
Перехватывает сетевые запросы, блокирует известные рекламные и трекерные домены
и при включённой настройке отправляет сайтам заголовок Do Not Track.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

# Популярные трекеры и рекламные сети. Блокируются сами домены и все их поддомены.
BLOCKED_DOMAINS = frozenset(
    {
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
)


def find_blocked_domain(host: str) -> str | None:
    """Возвращает домен из списка блокировки, которому принадлежит host, или None.

    Проверяем сам host и все его родительские домены: для 'a.b.mc.yandex.ru'
    это 'a.b.mc.yandex.ru', 'b.mc.yandex.ru', 'mc.yandex.ru', 'yandex.ru', 'ru'.
    Так поиск идёт за O(число частей имени), а не перебором всего списка.
    """
    parts = host.lower().split(".")
    for i in range(len(parts)):
        candidate = ".".join(parts[i:])
        if candidate in BLOCKED_DOMAINS:
            return candidate
    return None


class TrackingProtectionInterceptor(QWebEngineUrlRequestInterceptor):
    blocked_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = True
        self.send_dnt = True
        self._blocked_count = 0
        # Сколько запросов заблокировано к каждому трекерному домену
        self.blocked_by_domain: dict[str, int] = {}

    @property
    def blocked_count(self) -> int:
        return self._blocked_count

    def reset_count(self) -> None:
        self._blocked_count = 0
        self.blocked_by_domain.clear()
        self.blocked_count_changed.emit(0)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:
        if self.send_dnt:
            info.setHttpHeader(b"DNT", b"1")
            info.setHttpHeader(b"Sec-GPC", b"1")

        if not self.is_enabled:
            return

        host = info.requestUrl().host()
        if not host:
            return

        domain = find_blocked_domain(host)
        if domain is not None:
            info.block(True)
            self._blocked_count += 1
            self.blocked_by_domain[domain] = self.blocked_by_domain.get(domain, 0) + 1
            self.blocked_count_changed.emit(self._blocked_count)
