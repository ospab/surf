import html
import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.i18n import tr
except ModuleNotFoundError:
    from i18n import tr


# src="//host/..." или src='//host/...'
PROTOCOL_RELATIVE_SRC = re.compile(r"""(\bsrc\s*=\s*["'])//""", re.IGNORECASE)


class ReaderViewWidget(QWidget):
    """Режим чтения на QTextBrowser: статья, исходный код страницы или справка."""

    open_link = pyqtSignal(str)
    close_reader = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_size = 17
        self._is_dark = True
        self._last_mode = ""
        self._last_data = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Панель сверху: заголовок, шрифт, закрыть
        self.toolbar = QWidget()
        self.toolbar.setObjectName("readerToolbar")
        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)

        self.title_label = QLabel(tr("reader_title"))
        self.title_label.setObjectName("readerTitleLabel")

        # У кнопок из темы отступы 5x12 px, в маленькую кнопку текст «A+» с ними не влезает
        self.zoom_out_btn = QPushButton("A−")
        self.zoom_out_btn.setFixedSize(40, 28)
        self.zoom_out_btn.setStyleSheet("padding: 0;")
        self.zoom_out_btn.clicked.connect(self._decrease_font)

        self.zoom_in_btn = QPushButton("A+")
        self.zoom_in_btn.setFixedSize(40, 28)
        self.zoom_in_btn.setStyleSheet("padding: 0;")
        self.zoom_in_btn.clicked.connect(self._increase_font)

        self.exit_btn = QPushButton(tr("reader_close_btn"))
        self.exit_btn.setObjectName("readerExitBtn")
        self.exit_btn.clicked.connect(self.close_reader.emit)

        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch()
        tb_layout.addWidget(self.zoom_out_btn)
        tb_layout.addWidget(self.zoom_in_btn)
        tb_layout.addSpacing(12)
        tb_layout.addWidget(self.exit_btn)

        # Сам текст статьи
        self.browser = QTextBrowser()
        self.browser.setObjectName("readerBrowser")
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(lambda qurl: self.open_link.emit(qurl.toString()))
        self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))

        layout.addWidget(self.toolbar)
        layout.addWidget(self.browser)

    def set_theme_mode(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        if self._last_mode == "article" and self._last_data:
            self.set_article(self._last_data["title"], self._last_data["content"], self._last_data["url"])
        elif self._last_mode == "source" and self._last_data:
            self.set_source_code(self._last_data["title"], self._last_data["raw_html"], self._last_data["url"])

    def set_article(self, title: str, content_html: str, source_url: str) -> None:
        """Показывает статью: цвета под тему, шрифт Georgia, ширина текста до 760 px."""
        # Страховка: адрес картинки //host/... на Windows открывается как сетевая папка
        # \\host, и QTextBrowser зависает. Дописываем https:
        content_html = PROTOCOL_RELATIVE_SRC.sub(r"\1https://", content_html)
        self._last_mode = "article"
        self._last_data = {"title": title, "content": content_html, "url": source_url}
        short = f"{title[:60]}..." if len(title) > 60 else title
        self.title_label.setText(tr("reader_prefix") + short)

        bg = "#1e1e24" if self._is_dark else "#ffffff"
        fg = "#fbfbfe" if self._is_dark else "#15141a"
        h1_color = "#ffffff" if self._is_dark else "#15141a"
        link_color = "#4ba0ff" if self._is_dark else "#0060df"
        source_color = "#63a9ff" if self._is_dark else "#0060df"
        hr_color = "#42414d" if self._is_dark else "#dcdce8"
        code_bg = "#1c1b22" if self._is_dark else "#f0f0f5"
        code_fg = "#50fa7b" if self._is_dark else "#0055aa"
        quote_color = "#cfcfd8" if self._is_dark else "#5b5b66"

        styled_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: {bg};
                    color: {fg};
                    font-family: Georgia, 'Times New Roman', serif;
                    font-size: {self._font_size}px;
                    line-height: 1.65;
                    margin: 0 auto;
                    max-width: 760px;
                    padding: 30px 20px;
                }}
                h1 {{
                    font-size: 1.8em;
                    color: {h1_color};
                    margin-bottom: 0.3em;
                    line-height: 1.25;
                }}
                .source-link {{
                    color: {source_color};
                    font-size: 0.85em;
                    text-decoration: none;
                    margin-bottom: 2em;
                    display: block;
                }}
                p {{
                    margin: 1.1em 0;
                }}
                a {{
                    color: {link_color};
                    text-decoration: underline;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 6px;
                }}
                pre, code {{
                    background: {code_bg};
                    color: {code_fg};
                    font-family: Consolas, monospace;
                    font-size: 0.9em;
                    padding: 2px 5px;
                    border-radius: 4px;
                }}
                pre {{
                    padding: 12px;
                    overflow-x: auto;
                }}
                blockquote {{
                    border-left: 3px solid {link_color};
                    padding-left: 14px;
                    margin-left: 0;
                    color: {quote_color};
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <h1>{html.escape(title)}</h1>
            <a class="source-link" href="{source_url}">{tr("reader_source_label")} {source_url}</a>
            <hr style="border: 0; border-top: 1px solid {hr_color}; margin: 15px 0 25px 0;" />
            {content_html}
        </body>
        </html>
        """
        self.browser.setHtml(styled_html)

    def set_source_code(self, title: str, raw_html: str, source_url: str) -> None:
        """Показывает исходный HTML страницы. Он экранируется, чтобы теги выводились текстом."""
        self._last_mode = "source"
        self._last_data = {"title": title, "raw_html": raw_html, "url": source_url}
        self.title_label.setText(tr("reader_source_prefix") + title[:50])
        escaped = html.escape(raw_html)

        bg = "#1c1b22" if self._is_dark else "#ffffff"
        fg = "#f8f8f2" if self._is_dark else "#15141a"
        url_color = "#8f8f9d" if self._is_dark else "#5b5b66"

        code_view_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: {bg};
                    color: {fg};
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: {self._font_size - 3}px;
                    line-height: 1.45;
                    padding: 20px;
                }}
                pre {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }}
            </style>
        </head>
        <body>
            <div style="color: {url_color}; margin-bottom: 15px;">URL: {source_url}</div>
            <pre>{escaped}</pre>
        </body>
        </html>
        """
        self.browser.setHtml(code_view_html)

    def _increase_font(self) -> None:
        if self._font_size < 30:
            self._font_size += 2
            self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))

    def _decrease_font(self) -> None:
        if self._font_size > 12:
            self._font_size -= 2
            self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))
