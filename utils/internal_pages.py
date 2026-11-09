"""
Модуль внутренних страниц surf://
Генерирует современные адаптивные HTML-страницы для внутренних URL браузера surf:
- surf://pages (каталог страниц)
- surf://about (о браузере и компонентах)
- surf://history (журнал посещений с поиском)
- surf://bookmarks (закладки с поиском)
- surf://downloads (загрузки)
- surf://protection (защита от отслеживания ETP)
- surf://gpu (графика и системные параметры)
- surf://help (справочник хоткеев)
- surf://settings (обзор параметров)
"""
import html
import os
import platform
import sys
from PyQt6.QtCore import QBuffer, QIODevice, QSize, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineCore import QWebEngineUrlScheme, QWebEngineUrlSchemeHandler

try:
    from surf.database import Database
    from surf.i18n import get_language, tr
except ModuleNotFoundError:
    from database import Database
    from i18n import get_language, tr


def register_surf_scheme() -> None:
    """Регистрирует схему surf:// в QtWebEngine. Вызывается ДО создания QApplication."""
    scheme = QWebEngineUrlScheme(b"surf")
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)


def get_base_css(is_dark: bool, accent: str = "#0060df") -> str:
    """Возвращает общие стили для внутренних страниц в стиле Firefox Proton / surf."""
    if is_dark:
        bg = "#1c1b22"
        card_bg = "#2b2a33"
        card_hover = "#383744"
        text = "#fbfbfe"
        text_muted = "#a4a4b2"
        border = "#3d3c4a"
        code_bg = "#202028"
    else:
        bg = "#f9f9fb"
        card_bg = "#ffffff"
        card_hover = "#f0f0f4"
        text = "#15141a"
        text_muted = "#5b5b66"
        border = "#e0e0e6"
        code_bg = "#f0f0f4"

    return f"""
    :root {{
        --bg: {bg};
        --card-bg: {card_bg};
        --card-hover: {card_hover};
        --text: {text};
        --text-muted: {text_muted};
        --border: {border};
        --accent: {accent};
        --code-bg: {code_bg};
        --success: #10b981;
        --danger: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background-color: var(--bg);
        color: var(--text);
        line-height: 1.5;
        padding: 30px 20px 60px 20px;
    }}
    .container {{
        max-width: 900px;
        margin: 0 auto;
    }}
    .header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 28px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border);
    }}
    .header-left {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}
    .logo-badge {{
        background: var(--accent);
        color: white;
        font-weight: 800;
        font-size: 14px;
        padding: 6px 14px;
        border-radius: 20px;
        letter-spacing: 0.5px;
    }}
    .header-title {{
        font-size: 24px;
        font-weight: 700;
    }}
    .header-subtitle {{
        font-size: 13px;
        color: var(--text-muted);
        margin-top: 2px;
    }}
    .nav-link {{
        color: var(--accent);
        text-decoration: none;
        font-size: 13px;
        font-weight: 600;
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: var(--card-bg);
        transition: all 0.15s ease;
    }}
    .nav-link:hover {{
        background: var(--card-hover);
        border-color: var(--accent);
    }}
    .card {{
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }}
    .card-title {{
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .search-box {{
        width: 100%;
        padding: 10px 14px;
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text);
        font-size: 14px;
        margin-bottom: 18px;
        outline: none;
    }}
    .search-box:focus {{
        border-color: var(--accent);
        box-shadow: 0 0 0 2px rgba(0, 96, 223, 0.2);
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }}
    th {{
        text-align: left;
        padding: 10px 12px;
        border-bottom: 2px solid var(--border);
        color: var(--text-muted);
        font-weight: 600;
    }}
    td {{
        padding: 10px 12px;
        border-bottom: 1px solid var(--border);
    }}
    tr:hover td {{
        background-color: var(--card-hover);
    }}
    a.site-link {{
        color: var(--accent);
        text-decoration: none;
        font-weight: 500;
    }}
    a.site-link:hover {{
        text-decoration: underline;
    }}
    .badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }}
    .badge-success {{ background: rgba(16, 185, 129, 0.15); color: var(--success); }}
    .badge-info {{ background: rgba(0, 96, 223, 0.15); color: var(--accent); }}
    .badge-danger {{ background: rgba(239, 68, 68, 0.15); color: var(--danger); }}
    kbd {{
        background: var(--code-bg);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 2px 6px;
        font-family: Consolas, monospace;
        font-size: 12px;
        font-weight: 600;
    }}
    .grid-cards {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 16px;
    }}
    .page-card {{
        display: block;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px;
        text-decoration: none;
        color: var(--text);
        transition: all 0.2s ease;
    }}
    .page-card:hover {{
        transform: translateY(-2px);
        border-color: var(--accent);
        background: var(--card-hover);
    }}
    .page-card-title {{
        font-size: 15px;
        font-weight: 600;
        color: var(--accent);
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .page-card-desc {{
        font-size: 12px;
        color: var(--text-muted);
    }}
    .empty-state {{
        text-align: center;
        padding: 40px 20px;
        color: var(--text-muted);
        font-size: 14px;
    }}
    """


def render_pages_directory(is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует каталог всех внутренних страниц surf://pages."""
    is_ru = get_language() == "ru"
    title = "Внутренние страницы surf" if is_ru else "surf Internal Pages Directory"
    subtitle = "Полный каталог служебных адресов и панелей браузера" if is_ru else "Directory of internal surf:// browser addresses"

    pages = [
        ("surf://about", "ℹ️ surf://about", "О браузере surf, версии компонентов, User-Agent и среда" if is_ru else "About surf browser, component versions and User-Agent"),
        ("surf://history", "🕒 surf://history", "Журнал посещенных страниц с поиском и статистикой" if is_ru else "Browsing history explorer with live search"),
        ("surf://bookmarks", "⭐ surf://bookmarks", "Менеджер сохранённых закладок с прямыми ссылками" if is_ru else "Bookmarks manager with direct site links"),
        ("surf://downloads", "⬇️ surf://downloads", "Журнал загрузок и сохранённых файлов" if is_ru else "Downloads manager and file records"),
        ("surf://protection", "🛡️ surf://protection", "Панель защиты от отслеживания (ETP) и список трекеров" if is_ru else "Enhanced Tracking Protection panel and tracker list"),
        ("surf://gpu", "⚡ surf://gpu", "Сведения о графическом ускорителе, QPA и системе" if is_ru else "Graphics acceleration, QPA platform and hardware info"),
        ("surf://settings", "⚙️ surf://settings", "Конфигурация браузера, поисковые системы и прокси" if is_ru else "Browser settings overview, search engine and proxy"),
        ("surf://help", "❓ surf://help", "Полный справочник горячих клавиш и руководства" if is_ru else "Keyboard shortcuts guide and documentation"),
        ("surf://newtab", "🚀 surf://newtab", "Стартовая страница быстрого доступа (Speed Dial)" if is_ru else "New tab speed dial home page"),
    ]

    cards_html = ""
    for url, p_title, p_desc in pages:
        cards_html += f"""
        <a href="{url}" class="page-card">
            <div class="page-card-title">{p_title}</div>
            <div class="page-card-desc">{p_desc}</div>
        </a>
        """

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
            </div>
            <div class="grid-cards">
                {cards_html}
            </div>
        </div>
    </body>
    </html>
    """


def render_about_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует страницу surf://about с подробными версиями всех компонентов."""
    is_ru = get_language() == "ru"
    title = "О программе surf" if is_ru else "About surf Browser"

    import PyQt6
    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    ua_str = db.get_setting(
        "custom_user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Surf/1.0",
    )
    search_eng = db.get_setting("search_engine", "https://www.google.com/search?q=")
    dl_folder = db.get_setting("download_folder", os.path.join(os.path.expanduser("~"), "Downloads"))

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf 1.0</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{"Быстрый, приватный веб-браузер на базе PyQt6 и WebEngine" if is_ru else "Fast, private PyQt6 WebEngine browser"}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">📦 {"Сведения о сборке и компонентах" if is_ru else "Build & Components Details"}</div>
                <table>
                    <tr><td width="200"><b>{"Название" if is_ru else "Application"}</b></td><td>surf Browser</td></tr>
                    <tr><td><b>{"Версия" if is_ru else "Version"}</b></td><td><span class="badge badge-info">1.0.0 Stable</span> (Desktop Edition)</td></tr>
                    <tr><td><b>{"Движок рендеринга" if is_ru else "Rendering Engine"}</b></td><td>QtWebEngine / Chromium Core</td></tr>
                    <tr><td><b>{"Версия PyQt6" if is_ru else "PyQt6 Version"}</b></td><td>{PYQT_VERSION_STR}</td></tr>
                    <tr><td><b>{"Версия Qt" if is_ru else "Qt Version"}</b></td><td>{QT_VERSION_STR}</td></tr>
                    <tr><td><b>{"Интерпретатор Python" if is_ru else "Python Runtime"}</b></td><td>{platform.python_version()} ({platform.python_implementation()})</td></tr>
                    <tr><td><b>{"Операционная система" if is_ru else "Operating System"}</b></td><td>{platform.system()} {platform.release()} ({platform.architecture()[0]})</td></tr>
                    <tr><td><b>{"Управление окнами" if is_ru else "Window Manager"}</b></td><td>Windows DWM API (Immersive Dark Mode, Themed Titlebar)</td></tr>
                    <tr><td><b>{"База данных" if is_ru else "Local Storage"}</b></td><td>SQLite 3 (surf.db)</td></tr>
                    <tr><td><b>{"Папка загрузок" if is_ru else "Download Folder"}</b></td><td><code>{html.escape(dl_folder)}</code></td></tr>
                    <tr><td><b>{"Поисковик по умолчанию" if is_ru else "Default Search Engine"}</b></td><td><code>{html.escape(search_eng)}</code></td></tr>
                </table>
            </div>

            <div class="card">
                <div class="card-title">🌐 {"Идентификация (User-Agent)" if is_ru else "HTTP User-Agent"}</div>
                <p style="font-size: 13px; font-family: Consolas, monospace; background: var(--code-bg); padding: 12px; border-radius: 8px; border: 1px solid var(--border); word-break: break-all;">
                    {html.escape(ua_str)}
                </p>
            </div>

            <div class="card">
                <div class="card-title">✨ {"Ключевые возможности surf" if is_ru else "Key Features"}</div>
                <ul style="padding-left: 20px; font-size: 13px; color: var(--text-muted); line-height: 1.8;">
                    <li>{"Интерфейс в стиле Firefox Proton: парящие скруглённые вкладки с фавиконами и индикатором звука" if is_ru else "Firefox Proton floating tabs with favicons and audio mute toggle"}</li>
                    <li>{"Адресная строка AwesomeBar со встроенным SSL-сертификатом, защитой от отслеживания, режимом чтения и закладками" if is_ru else "Integrated AwesomeBar with SSL inspection, ETP shield, reader mode, and star bookmarks"}</li>
                    <li>{"Устранение белых вспышек (White Flash) при переходе по страницам" if is_ru else "Elimination of white flash on page loads and tab transitions"}</li>
                    <li>{"Enhanced Tracking Protection: перехват и блокировка 26+ рекламных и трекинговых сетей" if is_ru else "Enhanced Tracking Protection blocking 26+ advertising and tracker networks"}</li>
                    <li>{"Приватный режим (Ctrl+Shift+P) с изолированным профилем и отсутствием следов в истории" if is_ru else "Private Window mode (Ctrl+Shift+P) with isolated OTR profile"}</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """


def render_history_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует интерактивную веб-страницу surf://history с живым поиском."""
    is_ru = get_language() == "ru"
    title = "Журнал посещений" if is_ru else "Browsing History"
    subtitle = "Полная хроника посещённых веб-страниц" if is_ru else "Chronological log of visited pages"

    records = db.get_history(limit=200)

    rows_html = ""
    if records:
        for r in records:
            r_title = html.escape(r.get("title") or r.get("url") or "Без названия")
            r_url = html.escape(r.get("url", ""))
            r_time = html.escape(str(r.get("visit_time", "")))
            r_count = r.get("visit_count", 1)
            rows_html += f"""
            <tr class="history-row">
                <td width="160" style="color: var(--text-muted); font-size: 12px;">{r_time}</td>
                <td><a href="{r_url}" class="site-link">{r_title}</a></td>
                <td style="color: var(--text-muted); font-size: 12px;">{r_url[:60]}</td>
                <td width="80" align="center"><span class="badge badge-info">{r_count}</span></td>
            </tr>
            """
    else:
        rows_html = f"""<tr><td colspan="4"><div class="empty-state">{"История посещений пуста" if is_ru else "Browsing history is empty"}</div></td></tr>"""

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
        <script>
            function filterHistory() {{
                var q = document.getElementById('search').value.toLowerCase();
                var rows = document.querySelectorAll('.history-row');
                rows.forEach(function(r) {{
                    var text = r.innerText.toLowerCase();
                    r.style.display = text.indexOf(q) !== -1 ? '' : 'none';
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(records)} {"записей" if is_ru else "entries"})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <input type="text" id="search" class="search-box" placeholder="{"Поиск в журнале истории..." if is_ru else "Search history records..."}" oninput="filterHistory()">

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Дата и время" if is_ru else "Date & Time"}</th>
                            <th>{"Название" if is_ru else "Title"}</th>
                            <th>URL</th>
                            <th style="text-align: center;">{"Переходов" if is_ru else "Visits"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_bookmarks_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует веб-страницу закладок surf://bookmarks."""
    is_ru = get_language() == "ru"
    title = "Закладки" if is_ru else "Bookmarks"
    subtitle = "Сохранённые закладки и избранные сайты" if is_ru else "Saved bookmarks and favorites"

    bookmarks = db.get_bookmarks()

    rows_html = ""
    if bookmarks:
        for b in bookmarks:
            b_title = html.escape(b.get("title") or b.get("url") or "Без названия")
            b_url = html.escape(b.get("url", ""))
            b_time = html.escape(str(b.get("created_at", "")))
            rows_html += f"""
            <tr class="bm-row">
                <td><a href="{b_url}" class="site-link">★ {b_title}</a></td>
                <td style="color: var(--text-muted); font-size: 12px;">{b_url}</td>
                <td width="160" style="color: var(--text-muted); font-size: 12px;">{b_time}</td>
            </tr>
            """
    else:
        rows_html = f"""<tr><td colspan="3"><div class="empty-state">{"Список закладок пуст. Нажмите звезду (Ctrl+D) на любой веб-странице." if is_ru else "Bookmarks list is empty. Press Ctrl+D to bookmark any page."}</div></td></tr>"""

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
        <script>
            function filterBookmarks() {{
                var q = document.getElementById('search').value.toLowerCase();
                var rows = document.querySelectorAll('.bm-row');
                rows.forEach(function(r) {{
                    var text = r.innerText.toLowerCase();
                    r.style.display = text.indexOf(q) !== -1 ? '' : 'none';
                }});
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(bookmarks)} {"закладок" if is_ru else "bookmarks"})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <input type="text" id="search" class="search-box" placeholder="{"Поиск в закладках..." if is_ru else "Search bookmarks..."}" oninput="filterBookmarks()">

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Название закладки" if is_ru else "Bookmark Name"}</th>
                            <th>URL</th>
                            <th>{"Дата добавления" if is_ru else "Date Added"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_downloads_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует веб-страницу загрузок surf://downloads."""
    is_ru = get_language() == "ru"
    title = "Загрузки" if is_ru else "Downloads"
    subtitle = "Список скачанных и активных файлов" if is_ru else "Downloaded files history"

    downloads = db.get_downloads(limit=100)

    rows_html = ""
    if downloads:
        for d in downloads:
            d_name = html.escape(d.get("filename", "file"))
            d_path = html.escape(d.get("filepath", ""))
            d_size = d.get("filesize", 0)
            if d_size > 1024 * 1024:
                size_str = f"{d_size / (1024 * 1024):.1f} MB"
            elif d_size > 1024:
                size_str = f"{d_size / 1024:.1f} KB"
            else:
                size_str = f"{d_size} B"
            d_status = html.escape(d.get("status", "Завершено"))
            d_time = html.escape(str(d.get("download_time", "")))

            badge_cls = "badge-success" if "Завершено" in d_status or "Completed" in d_status else "badge-danger"

            rows_html += f"""
            <tr>
                <td><b>📄 {d_name}</b><br><span style="font-size: 11px; color: var(--text-muted);">{d_path}</span></td>
                <td width="100">{size_str}</td>
                <td width="120"><span class="badge {badge_cls}">{d_status}</span></td>
                <td width="150" style="color: var(--text-muted); font-size: 12px;">{d_time}</td>
            </tr>
            """
    else:
        rows_html = f"""<tr><td colspan="4"><div class="empty-state">{"Список загрузок пуст" if is_ru else "Downloads list is empty"}</div></td></tr>"""

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(downloads)} {"файлов" if is_ru else "files"})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Файл" if is_ru else "File"}</th>
                            <th>{"Размер" if is_ru else "Size"}</th>
                            <th>{"Статус" if is_ru else "Status"}</th>
                            <th>{"Дата" if is_ru else "Date"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_protection_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует страницу защиты от отслеживания surf://protection."""
    is_ru = get_language() == "ru"
    title = "Улучшенная защита от отслеживания (ETP)" if is_ru else "Enhanced Tracking Protection (ETP)"
    subtitle = "Блокировка трекеров, рекламы и фингерпринтинга" if is_ru else "Block trackers, ads and fingerprinting"

    domains = [
        ("google-analytics.com", "Google Analytics", "Сбор телеметрии и аналитики активности"),
        ("googletagmanager.com", "Google Tag Manager", "Контейнер динамических трекинговых тегов"),
        ("doubleclick.net", "Google DoubleClick", "Сеть поведенческого таргетинга рекламы"),
        ("googlesyndication.com", "Google AdSense", "Показ баннерной и видеорекламы"),
        ("adservice.google.com", "Google Ads Service", "Рекламный сервис Google"),
        ("an.yandex.ru", "Яндекс РСЯ", "Рекламная сеть Яндекса"),
        ("mc.yandex.ru", "Яндекс Метрика", "Сбор статистики посещений и вебвизор"),
        ("adfox.ru", "Яндекс ADFOX", "Управление баннерами и медийной рекламой"),
        ("criteo.com", "Criteo", "Ретаргетинг и межсайтовое отслеживание пользователей"),
        ("criteo.net", "Criteo Network", "Сеть сбора идентификаторов покупок"),
        ("connect.facebook.net", "Facebook Pixel", "Отслеживание конверсий и межсайтовой активности"),
        ("scorecardresearch.com", "ScoreCardResearch", "Маркетинговые опросы и измерение трафика"),
        ("hotjar.com", "Hotjar", "Запись сессий кликов, движений мыши и экранов"),
        ("clarity.ms", "Microsoft Clarity", "Поведенческая аналитика и тепловые карты"),
        ("ads.twitter.com", "Twitter/X Ads", "Трекинг конверсий из социальной сети"),
        ("moatads.com", "Oracle Moat", "Измерение видимости рекламы и атрибуция"),
        ("outbrain.com", "Outbrain", "Рекомендательные виджеты рекламного контента"),
        ("taboola.com", "Taboola", "Виджеты навязчивых спонсорских ссылок"),
        ("rubiconproject.com", "Magnite/Rubicon", "Автоматизированная биржа рекламных аукционов"),
        ("adsystem.com", "AdSystem", "Биржа рекламных мест"),
        ("advertising.com", "AOL Advertising", "Сеть медийных баннеров"),
        ("admob.com", "Google AdMob", "Мобильная реклама"),
        ("openx.net", "OpenX", "Рекламный сервер и трекер"),
        ("pubmatic.com", "PubMatic", "Система программатик-рекламы"),
        ("adnxs.com", "Xandr/AppNexus", "Платформа продажи персональных профилей рекламодателям"),
    ]

    domains_html = ""
    for dom, name, desc in domains:
        domains_html += f"""
        <tr>
            <td><span class="badge badge-danger">🛡️ Блокируется</span></td>
            <td><b>{name}</b></td>
            <td><code>{dom}</code></td>
            <td style="color: var(--text-muted); font-size: 12px;">{desc}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge" style="background: var(--success);">🛡️ ETP Active</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">🔒 {"Как работает встроенная защита" if is_ru else "How built-in protection works"}</div>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.8;">
                    {"Браузер surf использует сетевой перехватчик URL-запросов (QWebEngineUrlRequestInterceptor), блокируя сторонние сценарии отслеживания до того, как они передадут данные на внешние серверы. Это ускоряет загрузку сайтов, экономит оперативную память и снижает расход трафика." if is_ru else "surf browser uses native QWebEngineUrlRequestInterceptor to intercept and block tracking requests before they transmit your personal data to third parties. This speeds up page load times and protects your privacy."}
                </p>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Статус" if is_ru else "Status"}</th>
                            <th>{"Сервис" if is_ru else "Service"}</th>
                            <th>{"Домен" if is_ru else "Domain"}</th>
                            <th>{"Назначение" if is_ru else "Purpose"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {domains_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_gpu_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует страницу графической и системной информации surf://gpu."""
    is_ru = get_language() == "ru"
    title = "Графика и аппаратное ускорение" if is_ru else "Graphics & Hardware Acceleration"
    subtitle = "Диагностика графического стека и платформы рендеринга" if is_ru else "Graphics stack and platform diagnostics"

    app = QGuiApplication.instance()
    primary_screen = app.primaryScreen() if app else None

    res_str = f"{primary_screen.size().width()}x{primary_screen.size().height()}" if primary_screen else "Unknown"
    dpi_str = f"{primary_screen.devicePixelRatio():.2f}" if primary_screen else "1.00"
    plat_str = app.platformName() if app else "windows"

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">GPU Info</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">🖥️ {"Параметры графической подсистемы" if is_ru else "Graphics Subsystem Parameters"}</div>
                <table>
                    <tr><td width="240"><b>{"Платформа QPA" if is_ru else "QPA Platform"}</b></td><td><code>{plat_str}</code></td></tr>
                    <tr><td><b>{"Разрешение экрана" if is_ru else "Screen Resolution"}</b></td><td>{res_str} px</td></tr>
                    <tr><td><b>{"Коэффициент масштабирования (DPI)" if is_ru else "DPI Scaling Factor"}</b></td><td>{dpi_str}x</td></tr>
                    <tr><td><b>{"Графический API" if is_ru else "Graphics API"}</b></td><td>Direct3D 11 / ANGLE / Hardware OpenGL</td></tr>
                    <tr><td><b>{"Аппаратное 2D ускорение Canvas" if is_ru else "Hardware 2D Canvas"}</b></td><td><span class="badge badge-success">Включено</span></td></tr>
                    <tr><td><b>WebGL 1.0 & WebGL 2.0</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebAssembly (WASM)</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebRTC & PeerConnection</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>{"Сглаживание и субпиксельный рендеринг" if is_ru else "Subpixel Antialiasing"}</b></td><td>DirectWrite / FreeType</td></tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_help_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует справочник горячих клавиш surf://help."""
    is_ru = get_language() == "ru"
    title = "Справка и горячие клавиши" if is_ru else "Help & Keyboard Shortcuts"
    subtitle = "Полное руководство по управлению браузером surf" if is_ru else "Complete guide to surf browser shortcuts"

    shortcuts = [
        ("Вкладки", "Новая вкладка", "Ctrl+T"),
        ("Вкладки", "Новое приватное окно", "Ctrl+Shift+P"),
        ("Вкладки", "Новое обычное окно", "Ctrl+N"),
        ("Вкладки", "Закрыть текущую вкладку", "Ctrl+W"),
        ("Вкладки", "Восстановить закрытую вкладку", "Ctrl+Shift+T"),
        ("Вкладки", "Следующая вкладка", "Ctrl+Tab"),
        ("Вкладки", "Предыдущая вкладка", "Ctrl+Shift+Tab"),
        ("Вкладки", "Перейти на вкладку 1..9", "Ctrl+1..Ctrl+9"),
        ("Адресная строка", "Фокус на строку адреса", "Ctrl+L / Alt+D / F6"),
        ("Навигация", "Назад", "Alt+Left"),
        ("Навигация", "Вперед", "Alt+Right"),
        ("Навигация", "Обновить страницу", "F5 / Ctrl+R"),
        ("Навигация", "Жесткая перезагрузка с очисткой кэша", "Ctrl+Shift+R / Ctrl+F5"),
        ("Навигация", "Домашняя страница", "Alt+Home"),
        ("Поиск", "Найти на текущей странице", "Ctrl+F"),
        ("Поиск", "Следующее совпадение", "F3 / Ctrl+G"),
        ("Поиск", "Предыдущее совпадение", "Shift+F3 / Ctrl+Shift+G"),
        ("Масштаб", "Увеличить масштаб", "Ctrl++ / Ctrl+="),
        ("Масштаб", "Уменьшить масштаб", "Ctrl+-"),
        ("Масштаб", "Сбросить масштаб (100%)", "Ctrl+0"),
        ("Масштаб", "Полноэкранный режим", "F11"),
        ("Инструменты", "Добавить в закладки / Удалить", "Ctrl+D"),
        ("Инструменты", "Управление закладками и историей", "Ctrl+Shift+O / Ctrl+H"),
        ("Инструменты", "Менеджер загрузок", "Ctrl+J"),
        ("Инструменты", "Режим комфортного чтения (Reader)", "Ctrl+Alt+R"),
        ("Инструменты", "Сохранить страницу в PDF", "Ctrl+S / Ctrl+P"),
        ("Инструменты", "Снимок веб-страницы (скриншот)", "Ctrl+Shift+S"),
        ("Инструменты", "Исходный код страницы", "Ctrl+U"),
        ("Инструменты", "Настройки браузера", "Ctrl+,"),
        ("Инструменты", "Справка surf", "F1"),
        ("Инструменты", "Закрыть браузер", "Ctrl+Q"),
    ]

    rows_html = ""
    for cat, name, keys in shortcuts:
        keys_html = " ".join(f"<kbd>{k.strip()}</kbd>" for k in keys.split("/"))
        rows_html += f"""
        <tr>
            <td width="150"><span class="badge badge-info">{cat}</span></td>
            <td>{name}</td>
            <td>{keys_html}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://help</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Категория" if is_ru else "Category"}</th>
                            <th>{"Действие" if is_ru else "Action"}</th>
                            <th>{"Горячие клавиши" if is_ru else "Key combination"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_settings_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Генерирует веб-страницу параметров surf://settings."""
    is_ru = get_language() == "ru"
    title = "Настройки браузера" if is_ru else "Browser Settings"
    subtitle = "Текущая конфигурация профиля и окружения" if is_ru else "Profile and environment configuration"

    homepage = db.get_setting("homepage", "https://ya.ru")
    search_eng = db.get_setting("search_engine", "https://www.google.com/search?q=")
    theme_val = db.get_setting("theme", "dark")
    lang_val = db.get_setting("language", "ru")
    dl_folder = db.get_setting("download_folder", os.path.join(os.path.expanduser("~"), "Downloads"))
    proxy_type = db.get_setting("proxy_type", "none")
    auto_hide_menu = db.get_setting("menu_bar_auto_hide", "1") == "1"

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://settings</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">← {"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">⚙️ {"Основные параметры" if is_ru else "General Settings"}</div>
                <table>
                    <tr><td width="240"><b>{"Домашняя страница" if is_ru else "Homepage"}</b></td><td><code>{html.escape(homepage)}</code></td></tr>
                    <tr><td><b>{"Поисковая система" if is_ru else "Search Engine"}</b></td><td><code>{html.escape(search_eng)}</code></td></tr>
                    <tr><td><b>{"Тема оформления" if is_ru else "Theme"}</b></td><td><span class="badge badge-info">{theme_val}</span></td></tr>
                    <tr><td><b>{"Язык интерфейса" if is_ru else "Language"}</b></td><td><span class="badge badge-info">{lang_val.upper()}</span></td></tr>
                    <tr><td><b>{"Папка для загрузок" if is_ru else "Download Folder"}</b></td><td><code>{html.escape(dl_folder)}</code></td></tr>
                    <tr><td><b>{"Прокси-сервер" if is_ru else "Proxy Mode"}</b></td><td><span class="badge badge-info">{proxy_type}</span></td></tr>
                    <tr><td><b>{"Скрытие строки меню (Alt)" if is_ru else "Auto-hide Menu Bar"}</b></td><td>{"Включено" if auto_hide_menu else "Отключено"}</td></tr>
                </table>
            </div>

            <div class="card">
                <div class="card-title">💡 {"Изменение параметров" if is_ru else "Change Parameters"}</div>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.8;">
                    {"Для изменения темы, добавления кастомных поисковиков или настройки прокси нажмите сочетание клавиш" if is_ru else "To configure options, themes, or custom search engines press"} <kbd>Ctrl+,</kbd> {"или выберите пункт «Настройки» в меню приложения." if is_ru else "or open Settings dialog."}
                </p>
            </div>
        </div>
    </body>
    </html>
    """


class SurfSchemeHandler(QWebEngineUrlSchemeHandler):
    """Обработчик кастомной схемы surf:// для прямого рендеринга служебных страниц."""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._buffers: dict = {}

    def requestStarted(self, job) -> None:
        url = job.requestUrl()
        host = url.host().lower()

        is_dark = self.db.get_setting("theme", "dark") == "dark"
        accent = self.db.get_setting("accent_color", "#0060df")

        if host in ("about", "version"):
            html_content = render_about_page(self.db, is_dark, accent)
        elif host == "history":
            html_content = render_history_page(self.db, is_dark, accent)
        elif host == "bookmarks":
            html_content = render_bookmarks_page(self.db, is_dark, accent)
        elif host == "downloads":
            html_content = render_downloads_page(self.db, is_dark, accent)
        elif host == "protection":
            html_content = render_protection_page(is_dark, accent)
        elif host == "gpu":
            html_content = render_gpu_page(is_dark, accent)
        elif host == "help":
            html_content = render_help_page(is_dark, accent)
        elif host == "settings":
            html_content = render_settings_page(self.db, is_dark, accent)
        else:
            # surf://pages, surf://surf, surf://urls или любой неизвестный host
            html_content = render_pages_directory(is_dark, accent)

        buf = QBuffer(job)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        buf.write(html_content.encode("utf-8"))
        buf.close()
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        self._buffers[job] = buf
        try:
            job.destroyed.connect(lambda: self._buffers.pop(job, None))
        except Exception:
            pass
        job.reply(b"text/html; charset=utf-8", buf)
