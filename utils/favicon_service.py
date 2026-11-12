import os
import re
import threading
import urllib.request
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap

try:
    from surf.constants import SURF_USER_AGENT
except ModuleNotFoundError:
    from constants import SURF_USER_AGENT


def get_clean_domain(url_or_domain: str) -> str:
    """Извлекает чистый домен из URL или строки хоста (без 'www.' и порта)."""
    text = (url_or_domain or "").strip()
    if not text:
        return ""
    if not text.startswith("http://") and not text.startswith("https://") and not text.startswith("//"):
        text = "https://" + text
    try:
        parsed = urlparse(text)
        domain = (parsed.hostname or parsed.netloc or "").lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def get_cache_dir() -> str:
    """Возвращает абсолютный путь к папке кэша фавиконок."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_path = os.path.join(base, "cache", "favicons")
    os.makedirs(cache_path, exist_ok=True)
    return cache_path


def get_cache_file_path(domain: str) -> str:
    """Возвращает путь к кэшированному PNG-файлу для указанного домена."""
    safe_name = re.sub(r"[^a-zA-Z0-9.-]", "_", domain.lower())
    return os.path.join(get_cache_dir(), f"{safe_name}.png")


def create_circular_favicon_badge(pixmap: QPixmap, is_dark: bool = True, size: int = 42) -> QPixmap:
    """Круглый значок 42x42 с иконкой сайта в центре."""
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # Круглая подложка бейджа
    circle_rect = QRectF(1.5, 1.5, size - 3.0, size - 3.0)
    bg_color = QColor("#282834") if is_dark else QColor("#ffffff")
    border_color = QColor("#3f3f50") if is_dark else QColor("#d0d0d8")

    painter.setBrush(QBrush(bg_color))
    painter.setPen(QPen(border_color, 1.2))
    painter.drawEllipse(circle_rect)

    # Размещение фавиконки по центру
    if not pixmap.isNull():
        icon_size = 24
        scaled = pixmap.scaled(
            icon_size,
            icon_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = int((size - scaled.width()) / 2.0)
        y = int((size - scaled.height()) / 2.0)
        painter.drawPixmap(x, y, scaled)

    painter.end()
    return result


def generate_fallback_badge(title: str, domain: str, is_dark: bool = True, size: int = 42) -> QPixmap:
    """Цветной кружок с первой буквой сайта, если иконки нет."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    circle_rect = QRectF(2, 2, size - 4, size - 4)

    palette = [
        "#0060df",
        "#00875a",
        "#e53e3e",
        "#805ad5",
        "#dd6b20",
        "#319795",
        "#0284c7",
        "#d946ef",
        "#059669",
        "#d97706",
        "#2563eb",
        "#7c3aed",
    ]
    key = domain or title or "site"
    color_hex = palette[abs(hash(key)) % len(palette)]

    painter.setBrush(QBrush(QColor(color_hex)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(circle_rect)

    letter = ""
    for ch in title.strip() or domain.strip():
        if ch.isalnum():
            letter = ch.upper()
            break
    if not letter:
        letter = "?"

    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(circle_rect, Qt.AlignmentFlag.AlignCenter, letter)
    painter.end()
    return pixmap


class FaviconService(QObject):
    """Скачивает значки сайтов в фоне и хранит их на диске."""

    favicon_loaded = pyqtSignal(str, QPixmap)  # domain, pixmap
    _instance: Optional["FaviconService"] = None

    @classmethod
    def instance(cls) -> "FaviconService":
        if cls._instance is None:
            cls._instance = FaviconService()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._memory_cache: dict[str, QPixmap] = {}
        self._fetching_domains: set[str] = set()
        self._lock = threading.Lock()

    def get_cached(self, url_or_domain: str) -> QPixmap | None:
        """Возвращает кэшированную фавиконку из оперативной памяти или с диска, если есть."""
        domain = get_clean_domain(url_or_domain)
        if not domain:
            return None

        # Сначала кэш в памяти
        if domain in self._memory_cache:
            return self._memory_cache[domain]

        # Потом на диске
        file_path = get_cache_file_path(domain)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            pix = QPixmap(file_path)
            if not pix.isNull():
                self._memory_cache[domain] = pix
                return pix

        return None

    def save_to_cache(self, url_or_domain: str, pixmap: QPixmap) -> None:
        """Сохраняет фавиконку в память и на диск."""
        domain = get_clean_domain(url_or_domain)
        if not domain or pixmap.isNull():
            return

        self._memory_cache[domain] = pixmap
        file_path = get_cache_file_path(domain)
        try:
            pixmap.save(file_path, "PNG")
        except Exception:
            pass

    def request_favicon(self, url_or_domain: str) -> None:
        """Возвращает значок сайта. Если его нет в кэше, скачивает в фоне."""
        domain = get_clean_domain(url_or_domain)
        if not domain:
            return

        cached = self.get_cached(domain)
        if cached is not None:
            self.favicon_loaded.emit(domain, cached)
            return

        with self._lock:
            if domain in self._fetching_domains:
                return
            self._fetching_domains.add(domain)

        # Запускаем фоновый поток для скачивания
        thread = threading.Thread(
            target=self._download_worker,
            args=(domain,),
            daemon=True,
            name=f"FaviconFetch-{domain}",
        )
        thread.start()

    def _download_worker(self, domain: str) -> None:
        file_path = get_cache_file_path(domain)
        pix = None

        headers = {"User-Agent": SURF_USER_AGENT}

        # Сначала спрашиваем сервис значков Google, он отдаёт PNG 64x64
        api_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = resp.read()
                if len(data) > 120:  # Больше дефолтной заглушки
                    p = QPixmap()
                    if p.loadFromData(data):
                        pix = p
                        p.save(file_path, "PNG")
        except Exception:
            pix = None

        # Не вышло, берём https://домен/favicon.ico
        if pix is None:
            for scheme in ("https", "http"):
                try:
                    direct_url = f"{scheme}://{domain}/favicon.ico"
                    req = urllib.request.Request(direct_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=2.5) as resp:
                        data = resp.read()
                        if len(data) > 64:
                            p = QPixmap()
                            if p.loadFromData(data):
                                pix = p
                                p.save(file_path, "PNG")
                                break
                except Exception:
                    continue

        with self._lock:
            self._fetching_domains.discard(domain)

        if pix is not None and not pix.isNull():
            self._memory_cache[domain] = pix
            self.favicon_loaded.emit(domain, pix)
