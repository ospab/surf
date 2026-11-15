"""
Служебные страницы surf://. HTML собирается в Python на лету:
- surf://welcome (стартовая страница первого запуска)
- surf://help (горячие клавиши)
- surf://about (версия и среда выполнения)
- surf://pages (список этих страниц)
Историю, закладки, загрузки и настройки показывают обычные окна, отдельные страницы для них не нужны.
"""

import html
import platform

from PyQt6.QtCore import QBuffer, QIODevice
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
            (
                None,
                "Защита от трекеров",
                "Рекламные счётчики блокируются сразу. Список — по значку щита в адресной строке.",
            ),
            (None, "История и закладки", "Ctrl+H. Поиск, фильтр по датам, выгрузка в CSV."),
            ("surf://help", "Горячие клавиши", "Все сочетания клавиш одним списком."),
            (None, "Настройки", "Тема, язык, поисковая система, папка загрузок. Ctrl+,"),
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
                None,
                "Tracking protection",
                "Ad trackers are blocked right away. Click the shield in the address bar for the list.",
            ),
            (None, "History and bookmarks", "Ctrl+H. Search, filter by dates, export to CSV."),
            ("surf://help", "Keyboard shortcuts", "Every shortcut in one list."),
            (None, "Settings", "Theme, language, search engine, downloads folder. Ctrl+,"),
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
        <{"a" if url else "div"} {f'href="{url}" ' if url else ""}class="page-card">
            <div class="page-card-title">{card_title}</div>
            <div class="page-card-desc">{desc}</div>
        </{"a" if url else "div"}>
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


class SurfSchemeHandler(QWebEngineUrlSchemeHandler):
    """Отдаёт служебные страницы по адресам surf://."""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._buffers: dict = {}

    def requestStarted(self, job) -> None:
        """Qt просит содержимое для адреса surf://...: собираем HTML нужной страницы и отдаём его."""
        url = job.requestUrl()
        host = url.host().lower()

        is_dark = self.db.get_setting("theme", "dark") == "dark"
        accent = self.db.get_setting("accent_color", "#0060df")

        if host in ("about", "version"):
            html_content = render_about_page(self.db, is_dark, accent)
        elif host == "help":
            html_content = render_help_page(is_dark, accent)
        elif host == "welcome":
            html_content = render_welcome_page(is_dark, accent)
        else:
            # surf://pages, surf://surf, surf://urls или любой неизвестный host
            html_content = render_pages_directory(is_dark, accent)

        # Qt читает ответ уже после выхода из функции. Родитель job держит буфер, пока жив запрос,
        # а ссылка в _buffers дополнительно страхует его и убирается, когда job удаляется
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
