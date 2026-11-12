"""
Модуль внутренних страниц surf://
Собирает HTML служебных страниц surf://:
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

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineCore import QWebEngineUrlScheme, QWebEngineUrlSchemeHandler

try:
    from surf.database import Database
    from surf.i18n import get_language
except ModuleNotFoundError:
    from database import Database
    from i18n import get_language


def register_surf_scheme() -> None:
    """Регистрирует схему surf:// в QtWebEngine. Вызывается ДО создания QApplication."""
    scheme = QWebEngineUrlScheme(b"surf")
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)


def get_base_js() -> str:
    """Общий скрипт служебных страниц: Ctrl+клик и средняя кнопка открывают ссылку в новой вкладке."""
    return """
    <script>
    document.addEventListener('click', function(e) {
        var a = e.target.closest('a');
        if (!a || !a.href) return;
        if (e.ctrlKey || e.metaKey || e.button === 1) {
            e.preventDefault();
            e.stopPropagation();
            window.open(a.href, '_blank');
        }
    });
    </script>
    """


def get_base_css(is_dark: bool, accent: str = "#0060df") -> str:
    """Возвращает общие стили для внутренних страниц surf."""
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
    """Страница surf://pages со списком всех служебных страниц."""
    is_ru = get_language() == "ru"
    title = "Служебные страницы" if is_ru else "Internal Pages"
    subtitle = "Список внутренних адресов surf://" if is_ru else "List of internal surf:// addresses"

    pages = [
        ("surf://welcome", "surf://welcome", "Стартовая страница" if is_ru else "Welcome page"),
        (
            "surf://about",
            "surf://about",
            "Версия и среда выполнения" if is_ru else "Browser and runtime environment details",
        ),
        ("surf://history", "surf://history", "Журнал посещений" if is_ru else "Browsing history"),
        ("surf://bookmarks", "surf://bookmarks", "Сохранённые закладки" if is_ru else "Saved bookmarks"),
        ("surf://downloads", "surf://downloads", "Журнал загрузок" if is_ru else "Download records"),
        ("surf://protection", "surf://protection", "Защита от отслеживания" if is_ru else "Tracking protection"),
        ("surf://gpu", "surf://gpu", "Видеокарта и отрисовка" if is_ru else "Graphics and GPU diagnostics"),
        ("surf://settings", "surf://settings", "Настройки браузера" if is_ru else "Browser settings"),
        ("surf://help", "surf://help", "Горячие клавиши" if is_ru else "Keyboard shortcuts"),
        ("surf://newtab", "surf://newtab", "Новая вкладка" if is_ru else "New tab"),
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
        {get_base_js()}
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


def render_welcome_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Стартовая страница surf://welcome, которая открывается при первом запуске браузера."""
    is_ru = get_language() == "ru"
    if is_ru:
        title = "Добро пожаловать в surf"
        subtitle = "С чего начать"
        intro = (
            "surf — браузер на PyQt6. Страницы показывает Chromium, а вкладки, история, закладки, "
            "режим чтения и остальное сделаны отдельно. Ниже несколько вещей, которые пригодятся сразу."
        )
        cards = [
            ("surf://newtab", "Новая вкладка", "Поиск и плитки любимых сайтов. Плитку добавляет кнопка «+»."),
            ("surf://protection", "Защита от трекеров", "Рекламные счётчики блокируются сразу. Список видно по щиту."),
            ("surf://history", "История и закладки", "Ctrl+H. Поиск, фильтр по датам, выгрузка в CSV."),
            ("surf://help", "Горячие клавиши", "Все сочетания клавиш одним списком."),
            ("surf://settings", "Настройки", "Тема, язык, поисковая система, папка загрузок. Ctrl+,"),
            ("surf://pages", "Служебные страницы", "Все адреса surf:// в одном месте."),
        ]
        tips_title = "Ещё пара мелочей"
        tips = [
            "Значок книжки в адресной строке включает режим чтения (Ctrl+Alt+R).",
            "Ctrl+Shift+P открывает приватное окно: после закрытия из него ничего не остаётся.",
            "Масштаб (Ctrl+колесо) запоминается для каждого сайта.",
            "Вкладки, которые долго не открывали, засыпают и не занимают память.",
        ]
        footer = "Эта страница открывается только при первом запуске. Вернуться к ней можно по адресу surf://welcome."
    else:
        title = "Welcome to surf"
        subtitle = "Getting started"
        intro = (
            "surf is a PyQt6 browser. Chromium renders the pages; tabs, history, bookmarks, reader view "
            "and the rest are built on top. Here are a few things worth knowing right away."
        )
        cards = [
            ("surf://newtab", "New tab", "Search and tiles for your favourite sites. Add a tile with “+”."),
            (
                "surf://protection",
                "Tracking protection",
                "Ad trackers are blocked right away. See the list under the shield.",
            ),
            ("surf://history", "History and bookmarks", "Ctrl+H. Search, filter by dates, export to CSV."),
            ("surf://help", "Keyboard shortcuts", "Every shortcut in one list."),
            ("surf://settings", "Settings", "Theme, language, search engine, downloads folder. Ctrl+,"),
            ("surf://pages", "Internal pages", "All surf:// addresses in one place."),
        ]
        tips_title = "A few more things"
        tips = [
            "The book icon in the address bar turns on reader view (Ctrl+Alt+R).",
            "Ctrl+Shift+P opens a private window: nothing is kept after you close it.",
            "Zoom (Ctrl+wheel) is remembered for each site.",
            "Tabs you have not opened for a while go to sleep and free their memory.",
        ]
        footer = "This page opens only on first launch. You can come back to it at surf://welcome."

    cards_html = "".join(
        f"""
        <a href="{url}" class="page-card">
            <div class="page-card-title">{card_title}</div>
            <div class="page-card-desc">{desc}</div>
        </a>
        """
        for url, card_title, desc in cards
    )
    tips_html = "".join(f"<li>{tip}</li>" for tip in tips)

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
        {get_base_js()}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://welcome</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
            </div>
            <div class="card">
                <p style="margin: 0; font-size: 15px; line-height: 1.6;">{intro}</p>
            </div>
            <div class="grid-cards">
                {cards_html}
            </div>
            <div class="card" style="margin-top: 20px;">
                <div class="card-title">{tips_title}</div>
                <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">{tips_html}</ul>
            </div>
            <p style="color: var(--text-muted); font-size: 13px; margin-top: 16px;">{footer}</p>
        </div>
    </body>
    </html>
    """


def render_about_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Страница surf://about: версия, движок и среда выполнения."""
    is_ru = get_language() == "ru"
    title = "О программе surf" if is_ru else "About surf"

    from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    ua_str = db.get_setting(
        "custom_user_agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Surf/1.0",
    )

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>
            {get_base_css(is_dark, accent)}
            body {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 85vh;
                padding: 40px 20px;
            }}
            .about-container {{
                width: 100%;
                max-width: 600px;
                margin: 0 auto;
            }}
            .about-card {{
                background: var(--card-bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 40px 36px 36px 36px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
            }}
            .app-title {{
                font-size: 46px;
                font-weight: 900;
                letter-spacing: -1.5px;
                margin: 0 0 8px 0;
                color: var(--text);
                line-height: 1.1;
            }}
            .app-divider {{
                width: 42px;
                height: 3px;
                background: var(--accent);
                border-radius: 2px;
                margin: 0 auto 18px auto;
            }}
            .app-motto {{
                font-size: 15px;
                line-height: 1.6;
                color: var(--text);
                margin-bottom: 22px;
                font-weight: 500;
            }}
            .app-links {{
                display: flex;
                justify-content: center;
                flex-wrap: wrap;
                gap: 16px;
                padding: 16px 0;
                border-top: 1px solid var(--border);
                border-bottom: 1px solid var(--border);
                margin-bottom: 22px;
            }}
            .app-links a {{
                color: var(--accent);
                text-decoration: none;
                font-size: 13px;
                font-weight: 600;
            }}
            .app-links a:hover {{
                text-decoration: underline;
            }}
            .specs-box {{
                text-align: left;
                background: var(--code-bg);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 14px 18px;
                font-size: 12px;
            }}
            .specs-box summary {{
                cursor: pointer;
                font-weight: 600;
                color: var(--text-muted);
                outline: none;
                user-select: none;
            }}
            .specs-table {{
                width: 100%;
                margin-top: 12px;
                border-collapse: collapse;
            }}
            .specs-table td {{
                padding: 6px 0;
                color: var(--text);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            .specs-table td.dim {{
                color: var(--text-muted);
                width: 170px;
            }}
        </style>
        {get_base_js()}
    </head>
    <body>
        <div class="about-container">
            <div class="about-card">
                <h1 class="app-title">surf</h1>
                <div class="app-divider"></div>

                <div class="app-motto">
                    {"Браузер на PyQt6." if is_ru else "A browser built with PyQt6."}
                </div>

                <div class="app-links">
                    <a href="surf://pages">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
                    <a href="surf://settings">{"Настройки" if is_ru else "Settings"}</a>
                    <a href="surf://protection">{"Защита от трекеров" if is_ru else "Tracking Protection"}</a>
                    <a href="surf://gpu">{"Графика и GPU" if is_ru else "Graphics & GPU"}</a>
                    <a href="surf://help">{"Справка" if is_ru else "Help & Docs"}</a>
                </div>

                <details class="specs-box" open>
                    <summary>{"Сведения о сборке и среде выполнения" if is_ru else "Build & Runtime Details"}</summary>
                    <table class="specs-table">
                        <tr><td class="dim">{"Движок рендеринга" if is_ru else "Rendering Engine"}</td><td>SurfEngine (Chromium / QtWebEngine Core)</td></tr>
                        <tr><td class="dim">{"Среда выполнения" if is_ru else "Runtime"}</td><td>Python {platform.python_version()} • PyQt6 {PYQT_VERSION_STR} • Qt {QT_VERSION_STR}</td></tr>
                        <tr><td class="dim">{"Платформа" if is_ru else "Operating System"}</td><td>{platform.system()} {platform.release()} ({platform.architecture()[0]})</td></tr>
                        <tr><td class="dim">{"Менеджер окон" if is_ru else "Window Manager"}</td><td>Windows DWM API</td></tr>
                        <tr><td class="dim">{"База данных" if is_ru else "Local Storage"}</td><td>SQLite3</td></tr>
                        <tr><td class="dim">{"Идентификация" if is_ru else "User-Agent"}</td><td style="font-family: Consolas, monospace; font-size: 11px; word-break: break-all;">{html.escape(ua_str)}</td></tr>
                    </table>
                </details>
            </div>
        </div>
    </body>
    </html>
    """


def render_history_page(db: Database, is_dark: bool, accent: str = "#0060df") -> str:
    """Страница surf://history."""
    is_ru = get_language() == "ru"
    title = "Журнал посещений" if is_ru else "Browsing History"
    subtitle = "История переходов" if is_ru else "Chronological log of visited pages"

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
        {get_base_js()}
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
                    <span class="logo-badge">surf://history</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(records)})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <input type="text" id="search" class="search-box" placeholder="{"Поиск в истории..." if is_ru else "Search history..."}" oninput="filterHistory()">

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
    """Страница surf://bookmarks."""
    is_ru = get_language() == "ru"
    title = "Закладки" if is_ru else "Bookmarks"
    subtitle = "Сохранённые закладки" if is_ru else "Saved bookmarks"

    bookmarks = db.get_bookmarks()

    rows_html = ""
    if bookmarks:
        for b in bookmarks:
            b_title = html.escape(b.get("title") or b.get("url") or "Без названия")
            b_url = html.escape(b.get("url", ""))
            b_time = html.escape(str(b.get("created_at", "")))
            rows_html += f"""
            <tr class="bm-row">
                <td><a href="{b_url}" class="site-link">{b_title}</a></td>
                <td style="color: var(--text-muted); font-size: 12px;">{b_url}</td>
                <td width="160" style="color: var(--text-muted); font-size: 12px;">{b_time}</td>
            </tr>
            """
    else:
        rows_html = f"""<tr><td colspan="3"><div class="empty-state">{"Список закладок пуст" if is_ru else "Bookmarks list is empty"}</div></td></tr>"""

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
        {get_base_js()}
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
                    <span class="logo-badge">surf://bookmarks</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(bookmarks)})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <input type="text" id="search" class="search-box" placeholder="{"Поиск в закладках..." if is_ru else "Search bookmarks..."}" oninput="filterBookmarks()">

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Название" if is_ru else "Title"}</th>
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
    """Страница surf://downloads."""
    is_ru = get_language() == "ru"
    title = "Загрузки" if is_ru else "Downloads"
    subtitle = "Список загруженных файлов" if is_ru else "Downloaded files history"

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
                <td><b>{d_name}</b><br><span style="font-size: 11px; color: var(--text-muted);">{d_path}</span></td>
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
        {get_base_js()}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://downloads</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle} ({len(downloads)})</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
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


def render_protection_page(is_dark: bool, accent: str = "#0060df", interceptor=None) -> str:
    """Страница surf://protection."""
    is_ru = get_language() == "ru"
    title = "Защита от отслеживания" if is_ru else "Tracking Protection"
    subtitle = "Какие трекеры блокирует surf" if is_ru else "Which trackers surf blocks"

    blocked_count = interceptor.blocked_count if interceptor and hasattr(interceptor, "blocked_count") else 0
    is_enabled = interceptor.is_enabled if interceptor and hasattr(interceptor, "is_enabled") else True

    filter_rules = [
        ("google-analytics.com", "Аналитика" if is_ru else "Analytics", "Сбор телеметрии"),
        ("googletagmanager.com", "Аналитика" if is_ru else "Analytics", "Контейнер динамических тегов"),
        ("doubleclick.net", "Реклама" if is_ru else "Advertising", "Рекламный трекинг"),
        ("googlesyndication.com", "Реклама" if is_ru else "Advertising", "Рекламная сеть"),
        ("adservice.google.com", "Реклама" if is_ru else "Advertising", "Рекламный сервис"),
        ("an.yandex.ru", "Реклама" if is_ru else "Advertising", "Рекламная сеть Яндекса"),
        ("mc.yandex.ru", "Аналитика" if is_ru else "Analytics", "Сбор метрик и вебвизор"),
        ("adfox.ru", "Реклама" if is_ru else "Advertising", "Управление баннерами"),
        ("criteo.com", "Трекер" if is_ru else "Tracker", "Ретаргетинг"),
        ("criteo.net", "Трекер" if is_ru else "Tracker", "Идентификаторы пользователей"),
        ("connect.facebook.net", "Соцсети" if is_ru else "Social", "Межсайтовое отслеживание"),
        ("scorecardresearch.com", "Аналитика" if is_ru else "Analytics", "Измерение аудитории"),
        ("hotjar.com", "Аналитика" if is_ru else "Analytics", "Запись активности"),
        ("clarity.ms", "Аналитика" if is_ru else "Analytics", "Тепловые карты и сессии"),
        ("ads.twitter.com", "Соцсети" if is_ru else "Social", "Трекинг конверсий"),
        ("moatads.com", "Реклама" if is_ru else "Advertising", "Атрибуция рекламы"),
        ("outbrain.com", "Реклама" if is_ru else "Advertising", "Рекламные виджеты"),
        ("taboola.com", "Реклама" if is_ru else "Advertising", "Спонсорские блоки"),
        ("rubiconproject.com", "Реклама" if is_ru else "Advertising", "Рекламная биржа"),
        ("adsystem.com", "Реклама" if is_ru else "Advertising", "Рекламная сеть"),
        ("advertising.com", "Реклама" if is_ru else "Advertising", "Медийная реклама"),
        ("admob.com", "Реклама" if is_ru else "Advertising", "Мобильная реклама"),
        ("trafficjunky.com", "Реклама" if is_ru else "Advertising", "Рекламная сеть"),
        ("openx.net", "Реклама" if is_ru else "Advertising", "Рекламный сервер"),
        ("pubmatic.com", "Реклама" if is_ru else "Advertising", "Программатик-платформа"),
        ("adnxs.com", "Реклама" if is_ru else "Advertising", "Платформа монетизации"),
    ]

    rules_html = ""
    for dom, cat, purpose in filter_rules:
        rules_html += f"""
        <tr>
            <td><code>{dom}</code></td>
            <td width="140"><span class="badge badge-info">{cat}</span></td>
            <td style="color: var(--text-muted); font-size: 12px;">{purpose}</td>
        </tr>
        """

    status_badge = (
        '<span class="badge badge-success">Включена</span>'
        if is_enabled
        else '<span class="badge badge-danger">Отключена</span>'
    )

    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>{get_base_css(is_dark, accent)}</style>
        {get_base_js()}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://protection</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">{"Параметры защиты" if is_ru else "Protection Parameters"}</div>
                <table>
                    <tr><td width="240"><b>{"Состояние защиты" if is_ru else "Protection Status"}</b></td><td>{status_badge}</td></tr>
                    <tr><td><b>{"Заблокировано в текущей сессии" if is_ru else "Blocked in Current Session"}</b></td><td><span class="badge badge-info">{blocked_count}</span></td></tr>
                    <tr><td><b>{"Механизм перехвата" if is_ru else "Interception Mechanism"}</b></td><td><code>QWebEngineUrlRequestInterceptor</code></td></tr>
                    <tr><td><b>{"Активных правил" if is_ru else "Active Rules"}</b></td><td>{len(filter_rules)}</td></tr>
                </table>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Доменный шаблон" if is_ru else "Domain Pattern"}</th>
                            <th>{"Категория" if is_ru else "Category"}</th>
                            <th>{"Назначение" if is_ru else "Purpose"}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rules_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_gpu_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Страница surf://gpu."""
    is_ru = get_language() == "ru"
    title = "Графика" if is_ru else "Graphics"
    subtitle = "Видеокарта, экран и отрисовка" if is_ru else "Graphics card, screen and rendering"

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
        {get_base_js()}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-left">
                    <span class="logo-badge">surf://gpu</span>
                    <div>
                        <div class="header-title">{title}</div>
                        <div class="header-subtitle">{subtitle}</div>
                    </div>
                </div>
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">{"Параметры графической подсистемы" if is_ru else "Graphics Subsystem Parameters"}</div>
                <table>
                    <tr><td width="240"><b>{"Платформа QPA" if is_ru else "QPA Platform"}</b></td><td><code>{plat_str}</code></td></tr>
                    <tr><td><b>{"Разрешение экрана" if is_ru else "Screen Resolution"}</b></td><td>{res_str} px</td></tr>
                    <tr><td><b>{"Коэффициент масштабирования (DPI)" if is_ru else "DPI Scaling Factor"}</b></td><td>{dpi_str}x</td></tr>
                    <tr><td><b>{"Графический API" if is_ru else "Graphics API"}</b></td><td>Direct3D 11 / ANGLE / Hardware OpenGL</td></tr>
                    <tr><td><b>{"Аппаратное 2D ускорение Canvas" if is_ru else "Hardware 2D Canvas"}</b></td><td><span class="badge badge-success">Включено</span></td></tr>
                    <tr><td><b>WebGL 1.0 & WebGL 2.0</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebAssembly (WASM)</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebRTC & PeerConnection</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebXR & Gamepad API</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>WebUSB & WebHID API</b></td><td><span class="badge badge-success">Поддерживается</span></td></tr>
                    <tr><td><b>{"Захват экрана (Screen Capture)" if is_ru else "Screen Capture API"}</b></td><td><span class="badge badge-success">{"Включено" if is_ru else "Enabled"}</span></td></tr>
                    <tr><td><b>{"Сглаживание шрифтов" if is_ru else "Font Antialiasing"}</b></td><td>DirectWrite / FreeType</td></tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


def render_help_page(is_dark: bool, accent: str = "#0060df") -> str:
    """Страница surf://help со списком горячих клавиш."""
    is_ru = get_language() == "ru"
    title = "Горячие клавиши" if is_ru else "Keyboard Shortcuts"
    subtitle = "Сочетания клавиш браузера" if is_ru else "Key combinations reference"

    shortcuts = [
        ("Вкладки" if is_ru else "Tabs", "Новая вкладка" if is_ru else "New tab", "Ctrl+T"),
        ("Вкладки" if is_ru else "Tabs", "Новое приватное окно" if is_ru else "New private window", "Ctrl+Shift+P"),
        ("Вкладки" if is_ru else "Tabs", "Новое окно" if is_ru else "New window", "Ctrl+N"),
        ("Вкладки" if is_ru else "Tabs", "Закрыть текущую вкладку" if is_ru else "Close tab", "Ctrl+W"),
        (
            "Вкладки" if is_ru else "Tabs",
            "Восстановить закрытую вкладку" if is_ru else "Reopen closed tab",
            "Ctrl+Shift+T",
        ),
        ("Вкладки" if is_ru else "Tabs", "Следующая вкладка" if is_ru else "Next tab", "Ctrl+Tab"),
        ("Вкладки" if is_ru else "Tabs", "Предыдущая вкладка" if is_ru else "Previous tab", "Ctrl+Shift+Tab"),
        ("Вкладки" if is_ru else "Tabs", "Перейти на вкладку 1..9" if is_ru else "Go to tab 1..9", "Ctrl+1..Ctrl+9"),
        (
            "Адресная строка" if is_ru else "Address Bar",
            "Фокус на строку адреса" if is_ru else "Focus address bar",
            "Ctrl+L / Alt+D / F6",
        ),
        ("Навигация" if is_ru else "Navigation", "Назад" if is_ru else "Back", "Alt+Left"),
        ("Навигация" if is_ru else "Navigation", "Вперед" if is_ru else "Forward", "Alt+Right"),
        ("Навигация" if is_ru else "Navigation", "Обновить страницу" if is_ru else "Reload", "F5 / Ctrl+R"),
        (
            "Навигация" if is_ru else "Navigation",
            "Перезагрузка без кэша" if is_ru else "Hard reload",
            "Ctrl+Shift+R / Ctrl+F5",
        ),
        ("Навигация" if is_ru else "Navigation", "Домашняя страница" if is_ru else "Home", "Alt+Home"),
        ("Поиск" if is_ru else "Search", "Найти на странице" if is_ru else "Find in page", "Ctrl+F"),
        ("Поиск" if is_ru else "Search", "Следующее совпадение" if is_ru else "Find next", "F3 / Ctrl+G"),
        (
            "Поиск" if is_ru else "Search",
            "Предыдущее совпадение" if is_ru else "Find previous",
            "Shift+F3 / Ctrl+Shift+G",
        ),
        ("Масштаб" if is_ru else "Zoom", "Увеличить масштаб" if is_ru else "Zoom in", "Ctrl++ / Ctrl+="),
        ("Масштаб" if is_ru else "Zoom", "Уменьшить масштаб" if is_ru else "Zoom out", "Ctrl+-"),
        ("Масштаб" if is_ru else "Zoom", "Сбросить масштаб" if is_ru else "Reset zoom", "Ctrl+0"),
        ("Масштаб" if is_ru else "Zoom", "Полноэкранный режим" if is_ru else "Fullscreen", "F11"),
        ("Инструменты" if is_ru else "Tools", "Добавить закладку" if is_ru else "Bookmark page", "Ctrl+D"),
        (
            "Инструменты" if is_ru else "Tools",
            "Закладки и история" if is_ru else "Bookmarks & History",
            "Ctrl+Shift+O / Ctrl+H",
        ),
        ("Инструменты" if is_ru else "Tools", "Загрузки" if is_ru else "Downloads", "Ctrl+J"),
        ("Инструменты" if is_ru else "Tools", "Режим чтения" if is_ru else "Reader view", "Ctrl+Alt+R"),
        ("Инструменты" if is_ru else "Tools", "Печать / Экспорт в PDF" if is_ru else "Print / PDF", "Ctrl+P"),
        ("Инструменты" if is_ru else "Tools", "Снимок страницы" if is_ru else "Screenshot", "Ctrl+Shift+S"),
        ("Инструменты" if is_ru else "Tools", "Исходный код страницы" if is_ru else "View source", "Ctrl+U"),
        ("Инструменты" if is_ru else "Tools", "Настройки" if is_ru else "Settings", "Ctrl+,"),
        ("Инструменты" if is_ru else "Tools", "Справка" if is_ru else "Help", "F1"),
        ("Инструменты" if is_ru else "Tools", "Закрыть браузер" if is_ru else "Quit", "Ctrl+Q"),
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
        {get_base_js()}
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
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <table>
                    <thead>
                        <tr>
                            <th>{"Категория" if is_ru else "Category"}</th>
                            <th>{"Действие" if is_ru else "Action"}</th>
                            <th>{"Сочетание клавиш" if is_ru else "Keys"}</th>
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
    """Страница surf://settings."""
    is_ru = get_language() == "ru"
    title = "Настройки" if is_ru else "Settings"
    subtitle = "Что выбрано сейчас" if is_ru else "What is selected now"

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
        {get_base_js()}
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
                <a href="surf://pages" class="nav-link">{"Каталог страниц" if is_ru else "Pages Directory"}</a>
            </div>

            <div class="card">
                <div class="card-title">{"Основные параметры" if is_ru else "General Settings"}</div>
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
                <div class="card-title">{"Как поменять" if is_ru else "How to change"}</div>
                <p style="font-size: 13px; color: var(--text-muted); line-height: 1.8;">
                    {"Откройте окно настроек:" if is_ru else "Open the Settings window:"} <kbd>Ctrl+,</kbd>
                </p>
            </div>
        </div>
    </body>
    </html>
    """


class SurfSchemeHandler(QWebEngineUrlSchemeHandler):
    """Отдаёт служебные страницы по адресам surf://."""

    def __init__(self, db: Database, parent=None, interceptor=None):
        super().__init__(parent)
        self.db = db
        self.interceptor = interceptor
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
            html_content = render_protection_page(is_dark, accent, self.interceptor)
        elif host == "gpu":
            html_content = render_gpu_page(is_dark, accent)
        elif host == "help":
            html_content = render_help_page(is_dark, accent)
        elif host == "settings":
            html_content = render_settings_page(self.db, is_dark, accent)
        elif host == "welcome":
            html_content = render_welcome_page(is_dark, accent)
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
