import csv
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from urllib.parse import urlparse

try:
    from surf.constants import SURF_USER_AGENT
except ModuleNotFoundError:
    from constants import SURF_USER_AGENT

DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "surf.db")

DEFAULT_SETTINGS = {
    "homepage": "https://www.google.com",
    "search_engine": "https://www.google.com/search?q=",
    "search_engine_type": "google",
    "custom_search_engine": "https://www.google.com/search?q=",
    "theme": "dark",
    "accent_color": "#0060df",
    "language": "ru",
    "menu_bar_auto_hide": "1",
    "user_agent_type": "surf",
    "custom_user_agent": SURF_USER_AGENT,
    "privacy_save_history": "1",
    "privacy_clear_on_exit": "0",
    "privacy_dnt": "1",
    "proxy_type": "none",
    "proxy_host": "",
    "proxy_port": "8080",
    "proxy_user": "",
    "proxy_password": "",
    "download_folder": os.path.expanduser("~/Downloads"),
    "speed_dial_initialized": "0",
    "restore_session_on_startup": "1",
    "force_dark_sites": "0",
    "tab_sleep_enabled": "1",
    "first_run_done": "0",
}

DEFAULT_SPEED_DIAL_TILES = []


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_FILE):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Открывает соединение, фиксирует транзакцию и ОБЯЗАТЕЛЬНО закрывает его.

        Обычный `with sqlite3.connect(...)` только завершает транзакцию,
        но не закрывает соединение, из-за чего они копились.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    visit_time TEXT NOT NULL,
                    visit_count INTEGER NOT NULL DEFAULT 1
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    folder TEXT NOT NULL DEFAULT 'Избранное',
                    added_time TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    url TEXT NOT NULL,
                    total_bytes INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'completed',
                    download_time TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            for key, val in DEFAULT_SETTINGS.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, val),
                )

            # Миграция: поисковая система по умолчанию - Google
            cursor.execute("SELECT value FROM settings WHERE key = 'search_engine'")
            row = cursor.fetchone()
            if row and row[0] == "https://yandex.ru/search/?text=":
                cursor.execute(
                    "UPDATE settings SET value = 'https://www.google.com/search?q=' WHERE key = 'search_engine'"
                )
                cursor.execute("UPDATE settings SET value = 'google' WHERE key = 'search_engine_type'")
                cursor.execute(
                    "UPDATE settings SET value = 'https://www.google.com' WHERE key = 'homepage' AND value = 'https://ya.ru'"
                )

            # Плитки быстрого доступа (Speed Dial / Top Sites)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS speed_dial_tiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    icon TEXT NOT NULL DEFAULT '',
                    position INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            cursor.execute("SELECT value FROM settings WHERE key = 'speed_dial_initialized'")
            init_row = cursor.fetchone()
            dial_initialized = init_row is not None and init_row["value"] == "1"

            if not dial_initialized:
                # На новом браузере оставляем список шорткатов чистым/пустым
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('speed_dial_initialized', '1')")

            # Сессии открытых вкладок (Session Restore)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_tabs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    tab_index INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            # Системные разрешения сайтов на девайсы и API (микрофон, камера, геолокация и т.д.)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS site_permissions (
                    origin TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (origin, feature)
                )
                """
            )

            # Выбор конкретных устройств ввода (микрофон, камера) для сайтов
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS site_device_preferences (
                    origin TEXT PRIMARY KEY,
                    audio_device TEXT DEFAULT '',
                    video_device TEXT DEFAULT '',
                    allow_audio INTEGER DEFAULT 1,
                    allow_video INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Масштаб страницы, запомненный для каждого сайта (домена)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS site_zoom (
                    host TEXT PRIMARY KEY,
                    zoom REAL NOT NULL
                )
                """
            )

            conn.commit()

    # --- Масштаб сайтов ---

    def get_site_zoom(self, host: str) -> float | None:
        """Возвращает сохранённый масштаб для домена или None (значит 100%)."""
        if not host:
            return None
        with self._get_connection() as conn:
            row = conn.execute("SELECT zoom FROM site_zoom WHERE host = ?", (host,)).fetchone()
            return row["zoom"] if row else None

    def set_site_zoom(self, host: str, zoom: float) -> None:
        """Запоминает масштаб для домена. Масштаб 100% не храним — удаляем запись."""
        if not host:
            return
        with self._get_connection() as conn:
            if abs(zoom - 1.0) < 1e-6:
                conn.execute("DELETE FROM site_zoom WHERE host = ?", (host,))
            else:
                conn.execute(
                    "INSERT INTO site_zoom (host, zoom) VALUES (?, ?) "
                    "ON CONFLICT(host) DO UPDATE SET zoom = excluded.zoom",
                    (host, zoom),
                )

    # --- История ---

    def add_history_entry(self, url: str, title: str) -> None:
        if not url or url.startswith("data:") or url == "about:blank":
            return
        if self.get_setting("privacy_save_history", "1") == "0":
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = title.strip() if title else url

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, visit_count FROM history WHERE url = ? ORDER BY id DESC LIMIT 1",
                (url,),
            )
            row = cursor.fetchone()

            if row:
                entry_id, count = row["id"], row["visit_count"]
                cursor.execute(
                    "UPDATE history SET title = ?, visit_time = ?, visit_count = ? WHERE id = ?",
                    (title, now, count + 1, entry_id),
                )
            else:
                cursor.execute(
                    "INSERT INTO history (url, title, visit_time, visit_count) VALUES (?, ?, ?, 1)",
                    (url, title, now),
                )
            conn.commit()

    def update_history_title(self, url: str, title: str) -> None:
        """Обновляет заголовок последней записи истории для URL, не засчитывая новое посещение."""
        title = title.strip() if title else ""
        if not url or not title:
            return
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE history SET title = ? WHERE id = (SELECT MAX(id) FROM history WHERE url = ?)",
                (title, url),
            )

    def delete_history_by_url(self, url: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM history WHERE url = ?", (url,))

    def get_history(
        self,
        search_query: str = "",
        date_filter: str = "all",
        limit: int = 300,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """Возвращает историю. date_from/date_to ('YYYY-MM-DD', включительно) задают произвольный диапазон."""
        where, params = self._history_filter_sql(search_query, date_filter, date_from, date_to)
        query = (
            "SELECT id, url, title, visit_time, visit_count FROM history "
            f"WHERE {where} ORDER BY visit_time DESC LIMIT ?"
        )
        with self._get_connection() as conn:
            rows = conn.execute(query, [*params, limit]).fetchall()
            return [dict(row) for row in rows]

    def delete_history_filtered(
        self, date_filter: str = "all", date_from: str | None = None, date_to: str | None = None
    ) -> None:
        """Удаляет записи истории, подходящие под тот же фильтр, что и get_history."""
        where, params = self._history_filter_sql("", date_filter, date_from, date_to)
        with self._get_connection() as conn:
            conn.execute(f"DELETE FROM history WHERE {where}", params)

    @staticmethod
    def _history_filter_sql(
        search_query: str, date_filter: str, date_from: str | None, date_to: str | None
    ) -> tuple[str, list]:
        """Собирает условие WHERE и параметры для фильтров истории (общий код выборки и удаления)."""
        conditions = ["1=1"]
        params: list = []

        if search_query:
            conditions.append("(title LIKE ? OR url LIKE ?)")
            like = f"%{search_query}%"
            params.extend([like, like])

        now = datetime.now()
        today_start = now.strftime("%Y-%m-%d 00:00:00")
        if date_filter == "today":
            conditions.append("visit_time >= ?")
            params.append(today_start)
        elif date_filter == "yesterday":
            conditions.append("visit_time >= ? AND visit_time < ?")
            params.extend([(now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00"), today_start])
        elif date_filter == "week":
            conditions.append("visit_time >= ?")
            params.append((now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00"))

        if date_from:
            conditions.append("visit_time >= ?")
            params.append(f"{date_from} 00:00:00")
        if date_to:
            conditions.append("visit_time <= ?")
            params.append(f"{date_to} 23:59:59")

        return " AND ".join(conditions), params

    def delete_history_entry(self, entry_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()

    def clear_history(self, period: str = "all") -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if period == "all":
                cursor.execute("DELETE FROM history")
            elif period == "hour":
                limit_time = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM history WHERE visit_time >= ?", (limit_time,))
            elif period == "day":
                limit_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("DELETE FROM history WHERE visit_time >= ?", (limit_time,))
            conn.commit()

    def get_top_domains(self, limit: int = 8) -> list[tuple[str, int]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url, visit_count FROM history")
            domain_counts: dict[str, int] = {}

            for row in cursor.fetchall():
                try:
                    domain = urlparse(row["url"]).netloc
                    if domain:
                        domain_counts[domain] = domain_counts.get(domain, 0) + row["visit_count"]
                except Exception:
                    continue

            sorted_domains = sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)
            return sorted_domains[:limit]

    # --- Закладки ---

    def add_bookmark(self, title: str, url: str, folder: str = "Избранное") -> bool:
        if not url:
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = title.strip() if title else url
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bookmarks (title, url, folder, added_time) VALUES (?, ?, ?, ?)",
                    (title, url, folder, now),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def is_bookmarked(self, url: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM bookmarks WHERE url = ? LIMIT 1", (url,))
            return cursor.fetchone() is not None

    def get_bookmarks(self, search_query: str = "") -> list[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if search_query:
                query = "SELECT * FROM bookmarks WHERE title LIKE ? OR url LIKE ? ORDER BY id DESC"
                like = f"%{search_query}%"
                cursor.execute(query, (like, like))
            else:
                cursor.execute("SELECT * FROM bookmarks ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_bookmark(self, bookmark_id: int, title: str, url: str, folder: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bookmarks SET title = ?, url = ?, folder = ? WHERE id = ?",
                (title, url, folder, bookmark_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_bookmark(self, bookmark_id: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
            conn.commit()

    def delete_bookmark_by_url(self, url: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
            conn.commit()

    # --- Загрузки ---

    def add_download(
        self, file_name: str, file_path: str, url: str, total_bytes: int, status: str = "completed"
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO downloads (file_name, file_path, url, total_bytes, status, download_time)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (file_name, file_path, url, total_bytes, status, now),
            )
            conn.commit()

    def get_downloads(self, limit: int = 100) -> list[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads ORDER BY download_time DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def clear_downloads(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM downloads")
            conn.commit()

    # --- Настройки ---

    def get_setting(self, key: str, default: str | None = None) -> str:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row["value"]
            return default if default is not None else DEFAULT_SETTINGS.get(key, "")

    def set_setting(self, key: str, value: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    # --- Работа с файлами CSV / TXT ---

    def export_bookmarks_to_csv(self, filepath: str) -> int:
        bookmarks = self.get_bookmarks()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Title", "URL", "Folder", "AddedTime"])
            for b in bookmarks:
                writer.writerow([b["title"], b["url"], b["folder"], b["added_time"]])
        return len(bookmarks)

    def import_bookmarks_from_csv(self, filepath: str) -> int:
        imported = 0
        if not os.path.exists(filepath):
            return 0

        with open(filepath, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader, None)  # пропускаем строку заголовков
            for row in reader:
                if len(row) >= 2:
                    title, url = row[0], row[1]
                    folder = row[2] if len(row) > 2 else "Избранное"
                    if self.add_bookmark(title, url, folder):
                        imported += 1
        return imported

    def export_history_to_csv(self, filepath: str) -> int:
        history = self.get_history(limit=5000)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID", "Title", "URL", "VisitTime", "VisitCount"])
            for h in history:
                writer.writerow([h["id"], h["title"], h["url"], h["visit_time"], h["visit_count"]])
        return len(history)

    # --- Плитки быстрого доступа (Speed Dial / Top Sites) ---

    def get_speed_dial_tiles(self) -> list[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url, icon, position FROM speed_dial_tiles ORDER BY position ASC, id ASC")
            return [dict(row) for row in cursor.fetchall()]

    def add_speed_dial_tile(self, title: str, url: str, icon: str = "") -> int:
        if not url:
            return -1
        title = title.strip() if title else url
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM speed_dial_tiles")
            next_pos = cursor.fetchone()["next_pos"]
            cursor.execute(
                "INSERT INTO speed_dial_tiles (title, url, icon, position) VALUES (?, ?, ?, ?)",
                (title, url, icon, next_pos),
            )
            conn.commit()
            return cursor.lastrowid

    def update_speed_dial_tile(self, tile_id: int, title: str, url: str, icon: str = "") -> bool:
        if not url:
            return False
        title = title.strip() if title else url
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE speed_dial_tiles SET title = ?, url = ?, icon = ? WHERE id = ?",
                (title, url, icon, tile_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_speed_dial_tile(self, tile_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM speed_dial_tiles WHERE id = ?", (tile_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_top_visited_sites(self, limit: int = 6) -> list[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT url, title, SUM(visit_count) AS visits
                FROM history
                WHERE url NOT LIKE 'surf://%' AND url NOT LIKE 'about:%' AND url NOT LIKE 'data:%'
                GROUP BY url
                ORDER BY visits DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            result = []
            for row in rows:
                url = row["url"]
                title = (row["title"] or "").strip()
                if not title or title == url:
                    parsed = urlparse(url)
                    title = parsed.netloc.replace("www.", "") or url
                result.append(
                    {
                        "id": None,
                        "title": title,
                        "url": url,
                        "icon": "",
                        "position": 0,
                        "is_fallback": True,
                    }
                )
            return result

    get_most_visited_sites = get_top_visited_sites

    # --- Восстановление сессий (Session Restore) ---

    def save_session_tabs(self, tabs: list[dict]) -> None:
        """Сохраняет список вкладок текущей сессии."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_tabs")
            for t in tabs:
                url = t.get("url", "")
                if not url or url.startswith("data:"):
                    continue
                cursor.execute(
                    "INSERT INTO session_tabs (url, title, tab_index, is_active) VALUES (?, ?, ?, ?)",
                    (url, t.get("title", ""), t.get("tab_index", 0), 1 if t.get("is_active") else 0),
                )
            conn.commit()

    def get_saved_session_tabs(self) -> list[dict]:
        """Возвращает вкладки сохранённой сессии."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, url, title, tab_index, is_active FROM session_tabs ORDER BY tab_index ASC, id ASC"
            )
            res = []
            for row in cursor.fetchall():
                d = dict(row)
                d["is_active"] = bool(d.get("is_active", 0))
                res.append(d)
            return res

    def clear_saved_session(self) -> None:
        """Очищает сохранённую сессию."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM session_tabs")
            conn.commit()

    # --- Разрешения сайтов на системные устройства (Permissions) ---

    def get_site_permission(self, origin: str, feature: str) -> str | None:
        """Возвращает сохранённое решение ('allow' или 'deny') для источника и фичи/устройства."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT decision FROM site_permissions WHERE origin = ? AND feature = ?",
                (origin, feature),
            )
            row = cursor.fetchone()
            return row["decision"] if row else None

    def set_site_permission(self, origin: str, feature: str, decision: str) -> None:
        """Сохраняет решение ('allow' или 'deny') для источника."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO site_permissions (origin, feature, decision, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(origin, feature) DO UPDATE SET
                    decision = excluded.decision,
                    created_at = CURRENT_TIMESTAMP
                """,
                (origin, feature, decision),
            )
            conn.commit()

    def delete_site_permission(self, origin: str, feature: str) -> bool:
        """Удаляет сохранённое разрешение."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM site_permissions WHERE origin = ? AND feature = ?",
                (origin, feature),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_all_site_permissions(self) -> list[dict]:
        """Возвращает список всех сохранённых разрешений сайтов."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT origin, feature, decision, created_at FROM site_permissions ORDER BY origin ASC, feature ASC"
            )
            return [dict(r) for r in cursor.fetchall()]

    def clear_site_permissions(self, origin: str = None) -> None:
        """Очищает разрешения сайтов (все или для конкретного origin)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if origin:
                cursor.execute("DELETE FROM site_permissions WHERE origin = ?", (origin,))
            else:
                cursor.execute("DELETE FROM site_permissions")
            conn.commit()

    # --- Настройки конкретных устройств мультимедиа (микрофоны, камеры) ---

    def get_site_device_preference(self, origin: str) -> dict | None:
        """Возвращает настройки выбранных микрофона и камеры для источника."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT origin, audio_device, video_device, allow_audio, allow_video "
                "FROM site_device_preferences WHERE origin = ?",
                (origin,),
            )
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["allow_audio"] = bool(d.get("allow_audio", 1))
                d["allow_video"] = bool(d.get("allow_video", 1))
                return d
            return None

    def set_site_device_preference(
        self,
        origin: str,
        audio_device: str = "",
        video_device: str = "",
        allow_audio: bool = True,
        allow_video: bool = True,
    ) -> None:
        """Сохраняет выбранный микрофон и камеру для сайта."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO site_device_preferences
                    (origin, audio_device, video_device, allow_audio, allow_video, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(origin) DO UPDATE SET
                    audio_device = excluded.audio_device,
                    video_device = excluded.video_device,
                    allow_audio = excluded.allow_audio,
                    allow_video = excluded.allow_video,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (origin, audio_device, video_device, 1 if allow_audio else 0, 1 if allow_video else 0),
            )
            conn.commit()

    def delete_site_device_preference(self, origin: str) -> bool:
        """Удаляет сохранённую конфигурацию устройств для источника."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM site_device_preferences WHERE origin = ?", (origin,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_site_device_preferences(self) -> None:
        """Удаляет выбор устройств для всех сайтов и связанные решения по микрофону и камере."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM site_device_preferences")
            conn.execute("DELETE FROM site_permissions WHERE feature IN ('media', 'audio', 'video')")

    def get_all_site_device_preferences(self) -> list[dict]:
        """Возвращает список сохранённых конфигураций девайсов для всех сайтов."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT origin, audio_device, video_device, allow_audio, allow_video, updated_at "
                "FROM site_device_preferences ORDER BY origin ASC"
            )
            res = []
            for row in cursor.fetchall():
                d = dict(row)
                d["allow_audio"] = bool(d.get("allow_audio", 1))
                d["allow_video"] = bool(d.get("allow_video", 1))
                res.append(d)
            return res
