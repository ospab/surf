import csv
import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse

DEFAULT_DB_FILE = "surf.db"

DEFAULT_SETTINGS = {
    "homepage": "https://ya.ru",
    "search_engine": "https://yandex.ru/search/?text=",
    "theme": "dark",
    "accent_color": "#0060df",
    "language": "ru",
    "menu_bar_auto_hide": "1",
    "user_agent_type": "surf",
    "custom_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Surf/1.0",
    "privacy_save_history": "1",
    "privacy_clear_on_exit": "0",
    "privacy_dnt": "1",
    "proxy_type": "none",
    "proxy_host": "",
    "proxy_port": "8080",
    "proxy_user": "",
    "proxy_password": "",
    "download_folder": os.path.expanduser("~/Downloads"),
}


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            conn.commit()

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

    def get_history(self, search_query: str = "", date_filter: str = "all", limit: int = 300) -> list[dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT id, url, title, visit_time, visit_count FROM history WHERE 1=1"
            params: list = []

            if search_query:
                query += " AND (title LIKE ? OR url LIKE ?)"
                like = f"%{search_query}%"
                params.extend([like, like])

            now = datetime.now()
            if date_filter == "today":
                start = now.strftime("%Y-%m-%d 00:00:00")
                query += " AND visit_time >= ?"
                params.append(start)
            elif date_filter == "yesterday":
                start = (now - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
                end = now.strftime("%Y-%m-%d 00:00:00")
                query += " AND visit_time >= ? AND visit_time < ?"
                params.extend([start, end])
            elif date_filter == "week":
                start = (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
                query += " AND visit_time >= ?"
                params.append(start)

            query += " ORDER BY visit_time DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

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

    def add_download(self, file_name: str, file_path: str, url: str, total_bytes: int, status: str = "completed") -> None:
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

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, None)
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
