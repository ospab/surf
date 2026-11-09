import html
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class ReaderViewWidget(QWidget):
    open_link = pyqtSignal(str)
    close_reader = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_url = ""
        self._font_size = 17
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Верхняя панель управления режимом чтения
        self.toolbar = QWidget()
        self.toolbar.setObjectName("readerToolbar")
        tb_layout = QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)

        self.title_label = QLabel("Режим комфортного чтения")
        self.title_label.setStyleSheet("font-weight: bold; color: #8f8f9d;")

        self.zoom_out_btn = QPushButton("A-")
        self.zoom_out_btn.setFixedSize(32, 28)
        self.zoom_out_btn.clicked.connect(self._decrease_font)

        self.zoom_in_btn = QPushButton("A+")
        self.zoom_in_btn.setFixedSize(32, 28)
        self.zoom_in_btn.clicked.connect(self._increase_font)

        self.exit_btn = QPushButton("Закрыть чтение")
        self.exit_btn.setObjectName("readerExitBtn")
        self.exit_btn.clicked.connect(self.close_reader.emit)

        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch()
        tb_layout.addWidget(self.zoom_out_btn)
        tb_layout.addWidget(self.zoom_in_btn)
        tb_layout.addSpacing(12)
        tb_layout.addWidget(self.exit_btn)

        # Сам QTextBrowser (Тема QT 4)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(lambda qurl: self.open_link.emit(qurl.toString()))
        self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))

        layout.addWidget(self.toolbar)
        layout.addWidget(self.browser)

    def set_article(self, title: str, content_html: str, source_url: str) -> None:
        self._current_url = source_url
        self.title_label.setText(f"Чтение: {title[:60]}..." if len(title) > 60 else f"Чтение: {title}")

        styled_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: #2b2a33;
                    color: #fbfbfe;
                    font-family: Georgia, 'Times New Roman', serif;
                    font-size: {self._font_size}px;
                    line-height: 1.65;
                    margin: 0 auto;
                    max-width: 760px;
                    padding: 30px 20px;
                }}
                h1 {{
                    font-size: 1.8em;
                    color: #ffffff;
                    margin-bottom: 0.3em;
                    line-height: 1.25;
                }}
                .source-link {{
                    color: #00ddff;
                    font-size: 0.85em;
                    text-decoration: none;
                    margin-bottom: 2em;
                    display: block;
                }}
                p {{
                    margin: 1.1em 0;
                }}
                a {{
                    color: #80ebff;
                    text-decoration: underline;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 6px;
                }}
                pre, code {{
                    background: #1c1b22;
                    color: #50fa7b;
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
                    border-left: 3px solid #00ddff;
                    padding-left: 14px;
                    margin-left: 0;
                    color: #cfcfd8;
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <h1>{html.escape(title)}</h1>
            <a class="source-link" href="{source_url}">Источник: {source_url}</a>
            <hr style="border: 0; border-top: 1px solid #42414d; margin: 15px 0 25px 0;" />
            {content_html}
        </body>
        </html>
        """
        self.browser.setHtml(styled_html)

    def set_source_code(self, title: str, raw_html: str, source_url: str) -> None:
        self._current_url = source_url
        self.title_label.setText(f"Исходный код: {title[:50]}")
        escaped = html.escape(raw_html)

        code_view_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: #1c1b22;
                    color: #f8f8f2;
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
            <div style="color: #8f8f9d; margin-bottom: 15px;">URL: {source_url}</div>
            <pre>{escaped}</pre>
        </body>
        </html>
        """
        self.browser.setHtml(code_view_html)

    def set_help_content(self) -> None:
        self.title_label.setText("Справка surf")
        help_html = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: #2b2a33;
                    color: #fbfbfe;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: {self._font_size - 1}px;
                    line-height: 1.6;
                    max-width: 740px;
                    margin: 0 auto;
                    padding: 30px 20px;
                }}
                h1, h2 {{ color: #ffffff; }}
                h1 {{ font-size: 2em; border-bottom: 1px solid #42414d; padding-bottom: 10px; }}
                h2 {{ font-size: 1.3em; margin-top: 25px; }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 15px 0;
                }}
                th, td {{
                    border: 1px solid #42414d;
                    padding: 8px 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #1c1b22;
                }}
                code {{
                    background-color: #1c1b22;
                    color: #00ddff;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-family: Consolas, monospace;
                }}
            </style>
        </head>
        <body>
            <h1>Браузер surf</h1>
            <p><strong>surf</strong> — полнофункциональный легковесный веб-браузер со строгим стилем Firefox, разработанный на PyQt6.</p>
            
            <h2>Горячие клавиши</h2>
            <table>
                <tr><th>Сочетание</th><th>Действие</th></tr>
                <tr><td><code>Ctrl + T</code></td><td>Открыть новую вкладку</td></tr>
                <tr><td><code>Ctrl + W</code></td><td>Закрыть активную вкладку</td></tr>
                <tr><td><code>Ctrl + R</code> / <code>F5</code></td><td>Перезагрузить страницу</td></tr>
                <tr><td><code>Ctrl + L</code> / <code>Alt + D</code></td><td>Фокус в адресную строку</td></tr>
                <tr><td><code>Ctrl + H</code></td><td>Журнал истории и закладок</td></tr>
                <tr><td><code>Ctrl + D</code></td><td>Добавить текущую страницу в закладки</td></tr>
                <tr><td><code>Ctrl + F</code></td><td>Поиск текста на странице</td></tr>
                <tr><td><code>Ctrl + +</code> / <code>Ctrl + -</code></td><td>Увеличение / уменьшение масштаба</td></tr>
                <tr><td><code>Ctrl + 0</code></td><td>Сброс масштаба на 100%</td></tr>
                <tr><td><code>F11</code></td><td>Полноэкранный режим</td></tr>
            </table>

            <h2>Режим чтения</h2>
            <p>Включается кнопкой в адресной строке или меню «Вид». Очищает страницу от рекламы, боковых меню и баннеров, оставляя только текст статьи и иллюстрации в удобной типографике.</p>
        </body>
        </html>
        """
        self.browser.setHtml(help_html)

    def _increase_font(self) -> None:
        if self._font_size < 30:
            self._font_size += 2
            self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))

    def _decrease_font(self) -> None:
        if self._font_size > 12:
            self._font_size -= 2
            self.browser.document().setDefaultFont(QFont("Georgia", self._font_size))
