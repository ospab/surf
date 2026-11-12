"""Общие константы surf, которые используются в нескольких модулях."""

APP_NAME = "surf"
APP_VERSION = "1.0"

# Стартовая страница, которая открывается при первом запуске браузера
WELCOME_URL = "surf://welcome"

# User-Agent как у Chrome, но с пометкой Surf/1.0, чтобы сайты не ломались
SURF_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Surf/1.0"
)
