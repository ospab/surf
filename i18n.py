"""
Модуль локализации (интернационализации) для браузера surf.
Поддерживает динамическое переключение между русским и английским языками.
"""

TRANSLATIONS = {
    "ru": {
        "app_title": "surf",
        "app_subtitle": "Быстрый, приватный и легковесный веб-серфинг",
        "search_placeholder": "Искать в интернете или ввести адрес веб-сайта...",
        "address_placeholder": "Поиск в интернете или ввод URL...",
        "new_tab": "Новая вкладка",
        "untitled": "Без названия",

        # Меню
        "menu_file": "&Файл",
        "menu_edit": "&Правка",
        "menu_view": "&Вид",
        "menu_history": "&Журнал",
        "menu_bookmarks": "&Закладки",
        "menu_tools": "&Инструменты",
        "menu_help": "&Справка",

        # Действия Файл
        "act_new_tab": "Новая вкладка",
        "act_close_tab": "Закрыть вкладку",
        "act_open_file": "Открыть HTML файл...",
        "act_save_page": "Сохранить страницу как PDF...",
        "act_screenshot": "Сделать скриншот страницы...",
        "act_exit": "Выход",

        # Действия Правка
        "act_find": "Найти на этой странице...",
        "act_copy_url": "Копировать адрес страницы",

        # Действия Вид
        "act_reader": "Режим комфортного чтения",
        "act_source": "Исходный код страницы",
        "act_zoom_in": "Увеличить масштаб",
        "act_zoom_out": "Уменьшить масштаб",
        "act_zoom_reset": "Сбросить масштаб",
        "act_fullscreen": "Полноэкранный режим",

        # Действия Журнал и Закладки
        "act_show_history": "Показать всю историю",
        "act_clear_history": "Очистить историю...",
        "act_add_bookmark": "Добавить страницу в закладки",
        "act_manage_bookmarks": "Управление закладками",

        # Действия Инструменты и Справка
        "act_downloads": "Загрузки",
        "act_download_url": "Скачать по прямой ссылке...",
        "download_url_title": "Скачивание файла",
        "download_url_label": "Введите прямой URL файла для загрузки:",
        "act_settings": "Настройки",
        "act_help": "Справка surf",
        "act_about": "О программе surf",

        # Подсказки кнопок (Tooltips)
        "tip_back": "Назад (Alt+Left)",
        "tip_forward": "Вперед (Alt+Right)",
        "tip_reload": "Обновить (F5 / Ctrl+R)",
        "tip_home": "Домашняя страница (Alt+Home)",
        "tip_bookmark": "Добавить в закладки (Ctrl+D)",
        "tip_reader": "Режим чтения (Ctrl+Alt+R)",
        "tip_downloads": "Загрузки (Ctrl+J)",
        "tip_settings": "Настройки (Ctrl+,)",
        "tip_new_tab": "Новая вкладка (Ctrl+T)",

        # Панель поиска по странице
        "find_label": "Поиск:",
        "find_placeholder": "Найти на странице...",
        "find_next": "Далее",
        "find_prev": "Назад",

        # Контекстное меню вкладки
        "ctx_reload_tab": "Обновить вкладку",
        "ctx_duplicate_tab": "Дублировать вкладку",
        "ctx_close_tab": "Закрыть вкладку",
        "ctx_close_others": "Закрыть другие вкладки",

        # Уведомления и строка состояния
        "status_bookmark_added": "Закладка сохранена в Избранное",
        "status_bookmark_removed": "Закладка удалена",
        "status_url_copied": "URL скопирован в буфер обмена",
        "status_history_cleared": "История посещений успешно очищена",
        "status_download_started": "Началась загрузка: {name}",
        "status_download_finished": "Загрузка завершена: {name}",
        "status_pdf_saved": "Страница сохранена в PDF: {path}",
        "screenshot_saved_title": "Скриншот сохранен",
        "screenshot_saved_msg": "Снимок страницы сохранен:\n{path}",
        "bookmark_input_title": "Добавить в закладки",
        "bookmark_input_label": "Название страницы:",
        "clear_history_title": "Очистить историю",
        "clear_history_prompt": "Удалить всю историю посещений страниц?",
        "open_file_dialog": "Открыть файл",
        "save_pdf_dialog": "Сохранить веб-страницу как PDF",
        "save_screenshot_dialog": "Сохранить скриншот страницы",
        "save_download_dialog": "Сохранить загружаемый файл",

        # Быстрый доступ (Speed Dial / Top Sites)
        "speed_dial_title": "Быстрый доступ",
        "speed_dial_open": "Открыть",
        "speed_dial_add": "Добавить сайт",
        "speed_dial_edit": "Редактировать...",
        "speed_dial_delete": "Удалить",
        "speed_dial_pin": "Закрепить на панели",
        "speed_dial_dialog_add_title": "Новый ярлык",
        "speed_dial_dialog_edit_title": "Редактировать ярлык",
        "speed_dial_name_label": "Название:",
        "speed_dial_name_placeholder": "Например, Google",
        "speed_dial_url_label": "Веб-адрес (URL):",
        "speed_dial_url_placeholder": "https://example.com",
        "btn_save": "Сохранить",
        "btn_cancel": "Отмена",

        # Восстановление сессий (Session Restore)
        "act_restore_session": "Восстановить предыдущую сессию",
        "tip_restore_session": "Открыть вкладки из предыдущего сеанса",
        "pref_restore_session": "Восстанавливать вкладки прошлого сеанса при запуске",
        "status_session_restored": "Восстановлено вкладок: {count}",
        "status_no_session": "Нет сохранённых сессий для восстановления",
        "btn_restore_session": "Восстановить прошлую сессию",

        # О программе
        "about_title": "О программе surf",
        "about_text": (
            "<h3>surf 1.0</h3>"
            "<p>Строгий веб-браузер на базе PyQt6 и WebEngine со скруглённым интерфейсом.</p>"
            "<p><b>Особенности:</b></p>"
            "<ul>"
            "<li>Многовкладочный интерфейс с прокруткой и компактным сужением</li>"
            "<li>Режим комфортного чтения без рекламы (Reader Mode)</li>"
            "<li>Журнал истории, закладок и загрузок на SQLite</li>"
            "<li>Экспорт и импорт данных в формате CSV</li>"
            "<li>Настройки прокси, приватности, User-Agent и мультиязычность (RU/EN)</li>"
            "</ul>"
        ),

        # Окно настроек
        "settings_title": "Настройки surf",
        "tab_general": "Основные",
        "tab_privacy": "Приватность и заголовок",
        "tab_proxy": "Прокси-сервер",
        "tab_appearance": "Оформление",
        "group_navigation": "Навигация и поиск",
        "lbl_homepage": "Домашняя страница:",
        "lbl_search_engine": "Поисковая система:",
        "lbl_search_url": "URL поисковика:",
        "search_engine_google": "Google (по умолчанию)",
        "search_engine_yandex": "Яндекс",
        "search_engine_duckduckgo": "DuckDuckGo",
        "search_engine_bing": "Bing",
        "search_engine_custom": "Пользовательский...",
        "search_custom_placeholder": "https://example.com/search?q=%s (%s для запроса)",
        "lbl_menu_mode": "Строка меню (Alt):",
        "menu_mode_hide": "Скрывать (по нажатию Alt)",
        "menu_mode_show": "Всегда показывать",
        "lbl_language": "Язык интерфейса / Language:",
        "group_downloads": "Загрузки",
        "btn_browse": "Обзор...",
        "group_user_agent": "User-Agent (идентификация браузера)",
        "ua_surf": "Surf 1.0 (современный веб, рекомендуется)",
        "ua_surf_pure": "Surf 1.0 (чистый идентификатор)",
        "ua_chrome": "Google Chrome",
        "ua_firefox": "Mozilla Firefox",
        "ua_custom": "Пользовательский...",
        "group_history_privacy": "Журнал и отслеживание",
        "chk_save_history": "Вести журнал посещенных страниц",
        "chk_clear_exit": "Очищать кэш и историю при выходе из браузера",
        "chk_dnt": "Отправлять веб-сайтам сигнал «Не отслеживать» (Do Not Track)",
        "group_proxy": "Конфигурация сети",
        "lbl_proxy_type": "Тип прокси:",
        "proxy_none": "Без прокси (прямое соединение)",
        "proxy_system": "Системные настройки Windows",
        "proxy_http": "HTTP прокси",
        "proxy_socks5": "SOCKS5 прокси",
        "lbl_proxy_host": "Хост / IP:",
        "lbl_proxy_port": "Порт:",
        "lbl_proxy_user": "Логин (опционально):",
        "lbl_proxy_pass": "Пароль (опционально):",
        "group_style": "Стиль интерфейса",
        "lbl_theme": "Цветовая схема:",
        "theme_dark": "Тёмная (surf Dark)",
        "theme_light": "Светлая (surf Light)",
        "lbl_accent": "Акцентный цвет кнопок:",
        "btn_accent": "Выбрать акцент...",

        # Окно истории и закладок
        "history_dialog_title": "Журнал и закладки",
        "tab_history": "История",
        "tab_bookmarks": "Закладки",
        "tab_stats": "Статистика сайтов",
        "search_history_placeholder": "Поиск в истории...",
        "search_bookmarks_placeholder": "Поиск по закладкам...",
        "filter_all": "За всё время",
        "filter_today": "За сегодня",
        "filter_yesterday": "За вчера",
        "filter_week": "За последнюю неделю",
        "btn_export_csv": "Экспорт в CSV...",
        "btn_import_csv": "Импорт CSV...",
        "btn_delete_selected": "Удалить выбранное",
        "btn_clear_history": "Очистить историю...",
        "btn_open_tab": "Открыть в новой вкладке",
        "btn_delete_bookmark": "Удалить закладку",
        "stats_info": "Топ самых посещаемых доменов по данным истории:",
        "btn_close": "Закрыть",
        "col_id": "ID",
        "col_title": "Заголовок",
        "col_url": "URL",
        "col_time": "Дата и время",
        "col_visits": "Визитов",
        "col_folder": "Папка",
        "col_added": "Дата добавления",
        "col_rank": "№",
        "col_domain": "Домен",
        "col_views": "Всего просмотров",

        # Окно загрузок
        "downloads_title": "Загрузки",
        "col_dl_name": "Имя файла",
        "col_dl_size": "Размер",
        "col_dl_status": "Статус",
        "col_dl_time": "Дата",
        "col_dl_path": "Путь",
        "btn_open_folder": "Открыть папку с файлом",
        "btn_clear_list": "Очистить список",

        # Режим чтения
        "reader_title": "Режим комфортного чтения",
        "reader_prefix": "Чтение: ",
        "reader_source_prefix": "Исходный код: ",
        "reader_close_btn": "Закрыть чтение",
        "reader_source_label": "Источник:",

        # Приватность, SSL, контекстное меню и интерфейс Firefox
        "menu_new_private_window": "Новое приватное окно",
        "private_badge": "Приватный режим",
        "private_window_title": "surf (Приватный режим)",
        "tip_ssl_secure": "Безопасное соединение (HTTPS)",
        "tip_ssl_insecure": "Незащищенное соединение (HTTP)",
        "ssl_secure_title": "Безопасность соединения",
        "ssl_secure_msg": "Соединение защищено шифрованием SSL/TLS.\nХост: {host}",
        "ssl_insecure_msg": "Внимание! Соединение не зашифровано.\nХост: {host}",
        "tip_shield_protection": "Улучшенная защита от отслеживания (ETP)",
        "shield_title": "Защита от отслеживания",
        "shield_blocked_text": "Заблокировано трекеров и рекламных запросов: {count}",
        "shield_toggle_enable": "Включить защиту",
        "shield_toggle_disable": "Отключить защиту",
        "tip_mute_tab": "Заглушить звук вкладки",
        "tip_unmute_tab": "Включить звук вкладки",
        "tip_menu_surf": "Меню приложения (Alt+F)",
        "ctx_open_link_tab": "Открыть ссылку в новой вкладке",
        "ctx_copy_link": "Копировать адрес ссылки",
        "ctx_open_image_tab": "Открыть изображение в новой вкладке",
        "ctx_copy_image_url": "Копировать адрес изображения",
        "ctx_copy": "Копировать",
        "ctx_search_web": "Искать «{text}» в сети",

        # Окно сведений о сертификате безопасности
        "cert_dialog_title": "Сведения о сертификате безопасности",
        "cert_status_secure": "Безопасное соединение",
        "cert_status_secure_desc": "Соединение с этим веб-сайтом защищено современным шифрованием SSL/TLS.",
        "cert_status_insecure": "Незащищенное соединение",
        "cert_status_insecure_desc": "Этот веб-сайт не использует шифрование (HTTP). Любая вводимая информация (пароли, сообщения, банковские данные) может быть перехвачена посторонними.",
        "cert_tab_general": "Общие сведения",
        "cert_tab_details": "Технические детали",
        "cert_subject_header": "Кому выдан (Веб-сайт)",
        "cert_issuer_header": "Кем выдан (Удостоверяющий центр / CA)",
        "cert_validity_header": "Срок действия сертификата",
        "cert_common_name": "Общее имя (CN):",
        "cert_org": "Организация:",
        "cert_valid_from": "Действителен с:",
        "cert_valid_to": "Действителен по:",
        "cert_protocol": "Протокол:",
        "cert_cipher": "Алгоритм шифрования:",
        "cert_key_length": "Длина ключа:",
        "cert_serial": "Серийный номер:",
        "cert_sans": "Альтернативные домены (SAN):",
        "cert_loading": "Получение сведений о сертификате...",
        "cert_error_fetch": "Не удалось получить сертификат узла: {error}",
    },
    "en": {
        "app_title": "surf",
        "app_subtitle": "Fast, private and lightweight web browsing",
        "search_placeholder": "Search the web or enter website URL...",
        "address_placeholder": "Search the web or enter address...",
        "new_tab": "New Tab",
        "untitled": "Untitled",

        # Menus
        "menu_file": "&File",
        "menu_edit": "&Edit",
        "menu_view": "&View",
        "menu_history": "&History",
        "menu_bookmarks": "&Bookmarks",
        "menu_tools": "&Tools",
        "menu_help": "&Help",

        # File actions
        "act_new_tab": "New Tab",
        "act_close_tab": "Close Tab",
        "act_open_file": "Open HTML File...",
        "act_save_page": "Save Page as PDF...",
        "act_screenshot": "Take Page Screenshot...",
        "act_exit": "Exit",

        # Edit actions
        "act_find": "Find in This Page...",
        "act_copy_url": "Copy Page Address",

        # View actions
        "act_reader": "Reader View",
        "act_source": "Page Source",
        "act_zoom_in": "Zoom In",
        "act_zoom_out": "Zoom Out",
        "act_zoom_reset": "Reset Zoom",
        "act_fullscreen": "Full Screen",

        # History and Bookmarks actions
        "act_show_history": "Show All History",
        "act_clear_history": "Clear History...",
        "act_add_bookmark": "Bookmark This Page",
        "act_manage_bookmarks": "Manage Bookmarks",

        # Tools and Help actions
        "act_downloads": "Downloads",
        "act_download_url": "Download from Direct URL...",
        "download_url_title": "Download File",
        "download_url_label": "Enter direct URL to download:",
        "act_settings": "Settings",
        "act_help": "surf Help",
        "act_about": "About surf",

        # Tooltips
        "tip_back": "Back (Alt+Left)",
        "tip_forward": "Forward (Alt+Right)",
        "tip_reload": "Reload (F5 / Ctrl+R)",
        "tip_home": "Homepage (Alt+Home)",
        "tip_bookmark": "Bookmark Page (Ctrl+D)",
        "tip_reader": "Reader Mode (Ctrl+Alt+R)",
        "tip_downloads": "Downloads (Ctrl+J)",
        "tip_settings": "Settings (Ctrl+,)",
        "tip_new_tab": "New Tab (Ctrl+T)",

        # Find bar
        "find_label": "Find:",
        "find_placeholder": "Find on page...",
        "find_next": "Next",
        "find_prev": "Previous",

        # Tab context menu
        "ctx_reload_tab": "Reload Tab",
        "ctx_duplicate_tab": "Duplicate Tab",
        "ctx_close_tab": "Close Tab",
        "ctx_close_others": "Close Other Tabs",

        # Status & notifications
        "status_bookmark_added": "Bookmark saved to Favorites",
        "status_bookmark_removed": "Bookmark removed",
        "status_url_copied": "URL copied to clipboard",
        "status_history_cleared": "Browsing history cleared successfully",
        "status_download_started": "Download started: {name}",
        "status_download_finished": "Download completed: {name}",
        "status_pdf_saved": "Page saved as PDF: {path}",
        "screenshot_saved_title": "Screenshot Saved",
        "screenshot_saved_msg": "Page screenshot saved:\n{path}",
        "bookmark_input_title": "Add Bookmark",
        "bookmark_input_label": "Page Title:",
        "clear_history_title": "Clear History",
        "clear_history_prompt": "Are you sure you want to delete all browsing history?",
        "open_file_dialog": "Open File",
        "save_pdf_dialog": "Save Web Page as PDF",
        "save_screenshot_dialog": "Save Page Screenshot",
        "save_download_dialog": "Save Downloaded File",

        # Speed Dial / Top Sites
        "speed_dial_title": "Top Sites",
        "speed_dial_open": "Open",
        "speed_dial_add": "Add Shortcut",
        "speed_dial_edit": "Edit...",
        "speed_dial_delete": "Delete",
        "speed_dial_pin": "Pin to Speed Dial",
        "speed_dial_dialog_add_title": "Add Shortcut",
        "speed_dial_dialog_edit_title": "Edit Shortcut",
        "speed_dial_name_label": "Name:",
        "speed_dial_name_placeholder": "e.g., Google",
        "speed_dial_url_label": "URL:",
        "speed_dial_url_placeholder": "https://example.com",
        "btn_save": "Save",
        "btn_cancel": "Cancel",

        # Session Restore
        "act_restore_session": "Restore Previous Session",
        "tip_restore_session": "Open tabs from previous session",
        "pref_restore_session": "Restore previous session tabs on startup",
        "status_session_restored": "Restored tabs: {count}",
        "status_no_session": "No saved session to restore",
        "btn_restore_session": "Restore Previous Session",

        # About
        "about_title": "About surf",
        "about_text": (
            "<h3>surf 1.0</h3>"
            "<p>A fast, private and lightweight web browser built on PyQt6 and WebEngine.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Tabbed interface with compact shrinking and scrolling</li>"
            "<li>Distraction-free Reader Mode without ads</li>"
            "<li>Local SQLite history, bookmarks and downloads</li>"
            "<li>One-click CSV data export and import</li>"
            "<li>Customizable Proxy, Privacy, User-Agent and Bilingual UI (RU/EN)</li>"
            "</ul>"
        ),

        # Settings
        "settings_title": "surf Settings",
        "tab_general": "General",
        "tab_privacy": "Privacy & Header",
        "tab_proxy": "Proxy Server",
        "tab_appearance": "Appearance",
        "group_navigation": "Navigation & Search",
        "lbl_homepage": "Homepage:",
        "lbl_search_engine": "Search Engine:",
        "lbl_search_url": "Search URL:",
        "search_engine_google": "Google (Default)",
        "search_engine_yandex": "Yandex",
        "search_engine_duckduckgo": "DuckDuckGo",
        "search_engine_bing": "Bing",
        "search_engine_custom": "Custom...",
        "search_custom_placeholder": "https://example.com/search?q=%s (%s for query)",
        "lbl_menu_mode": "Menu Bar (Alt):",
        "menu_mode_hide": "Hide (toggle with Alt key)",
        "menu_mode_show": "Always show",
        "lbl_language": "Language / Язык интерфейса:",
        "group_downloads": "Downloads",
        "btn_browse": "Browse...",
        "group_user_agent": "User-Agent (Browser Identification)",
        "ua_surf": "Surf 1.0 (Modern Web, Recommended)",
        "ua_surf_pure": "Surf 1.0 (Pure Identifier)",
        "ua_chrome": "Google Chrome",
        "ua_firefox": "Mozilla Firefox",
        "ua_custom": "Custom...",
        "group_history_privacy": "History & Tracking",
        "chk_save_history": "Remember browsing history",
        "chk_clear_exit": "Clear cache and history when closing browser",
        "chk_dnt": "Send websites a 'Do Not Track' request (DNT)",
        "group_proxy": "Network Configuration",
        "lbl_proxy_type": "Proxy Type:",
        "proxy_none": "No Proxy (Direct Connection)",
        "proxy_system": "System Windows Settings",
        "proxy_http": "HTTP Proxy",
        "proxy_socks5": "SOCKS5 Proxy",
        "lbl_proxy_host": "Host / IP:",
        "lbl_proxy_port": "Port:",
        "lbl_proxy_user": "Username (Optional):",
        "lbl_proxy_pass": "Password (Optional):",
        "group_style": "Interface Style",
        "lbl_theme": "Color Scheme:",
        "theme_dark": "Dark (surf Dark)",
        "theme_light": "Light (surf Light)",
        "lbl_accent": "Button Accent Color:",
        "btn_accent": "Choose Accent...",

        # History and Bookmarks
        "history_dialog_title": "History & Bookmarks",
        "tab_history": "History",
        "tab_bookmarks": "Bookmarks",
        "tab_stats": "Site Statistics",
        "search_history_placeholder": "Search history...",
        "search_bookmarks_placeholder": "Search bookmarks...",
        "filter_all": "All Time",
        "filter_today": "Today",
        "filter_yesterday": "Yesterday",
        "filter_week": "Past Week",
        "btn_export_csv": "Export CSV...",
        "btn_import_csv": "Import CSV...",
        "btn_delete_selected": "Delete Selected",
        "btn_clear_history": "Clear History...",
        "btn_open_tab": "Open in New Tab",
        "btn_delete_bookmark": "Delete Bookmark",
        "stats_info": "Top visited domains from history records:",
        "btn_close": "Close",
        "col_id": "ID",
        "col_title": "Title",
        "col_url": "URL",
        "col_time": "Date & Time",
        "col_visits": "Visits",
        "col_folder": "Folder",
        "col_added": "Date Added",
        "col_rank": "#",
        "col_domain": "Domain",
        "col_views": "Total Views",

        # Downloads
        "downloads_title": "Downloads",
        "col_dl_name": "File Name",
        "col_dl_size": "Size",
        "col_dl_status": "Status",
        "col_dl_time": "Date",
        "col_dl_path": "Path",
        "btn_open_folder": "Open Containing Folder",
        "btn_clear_list": "Clear List",

        # Reader View
        "reader_title": "Comfortable Reading Mode",
        "reader_prefix": "Reading: ",
        "reader_source_prefix": "Page Source: ",
        "reader_close_btn": "Close Reader",
        "reader_source_label": "Source:",

        # Privacy, SSL, context menu and Firefox interface
        "menu_new_private_window": "New Private Window",
        "private_badge": "Private Browsing",
        "private_window_title": "surf (Private Browsing)",
        "tip_ssl_secure": "Secure Connection (HTTPS)",
        "tip_ssl_insecure": "Insecure Connection (HTTP)",
        "ssl_secure_title": "Connection Security",
        "ssl_secure_msg": "Connection is encrypted with SSL/TLS.\nHost: {host}",
        "ssl_insecure_msg": "Warning: Connection is not encrypted.\nHost: {host}",
        "tip_shield_protection": "Enhanced Tracking Protection (ETP)",
        "shield_title": "Enhanced Tracking Protection",
        "shield_blocked_text": "Trackers and ad requests blocked: {count}",
        "shield_toggle_enable": "Enable Protection",
        "shield_toggle_disable": "Disable Protection",
        "tip_mute_tab": "Mute tab audio",
        "tip_unmute_tab": "Unmute tab audio",
        "tip_menu_surf": "Application Menu (Alt+F)",
        "ctx_open_link_tab": "Open Link in New Tab",
        "ctx_copy_link": "Copy Link Address",
        "ctx_open_image_tab": "Open Image in New Tab",
        "ctx_copy_image_url": "Copy Image Address",
        "ctx_copy": "Copy",
        "ctx_search_web": "Search web for '{text}'",

        # Security certificate details dialog
        "cert_dialog_title": "Security Certificate Details",
        "cert_status_secure": "Secure Connection",
        "cert_status_secure_desc": "Connection to this website is secured with modern SSL/TLS encryption.",
        "cert_status_insecure": "Insecure Connection",
        "cert_status_insecure_desc": "This website does not use encryption (HTTP). Any information you enter (passwords, messages, personal data) may be intercepted by third parties.",
        "cert_tab_general": "General",
        "cert_tab_details": "Technical Details",
        "cert_subject_header": "Issued To (Website)",
        "cert_issuer_header": "Issued By (Certificate Authority / CA)",
        "cert_validity_header": "Certificate Validity Period",
        "cert_common_name": "Common Name (CN):",
        "cert_org": "Organization:",
        "cert_valid_from": "Valid From:",
        "cert_valid_to": "Valid Until:",
        "cert_protocol": "Protocol:",
        "cert_cipher": "Cipher Suite:",
        "cert_key_length": "Key Length:",
        "cert_serial": "Serial Number:",
        "cert_sans": "Alternative Names (SAN):",
        "cert_loading": "Retrieving certificate details...",
        "cert_error_fetch": "Failed to retrieve host certificate: {error}",
    },
}

_current_lang = "ru"


def set_language(lang: str) -> None:
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def get_language() -> str:
    return _current_lang


def tr(key: str, **kwargs) -> str:
    lang_dict = TRANSLATIONS.get(_current_lang, TRANSLATIONS["ru"])
    text = lang_dict.get(key, TRANSLATIONS["ru"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text
