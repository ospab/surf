import os
import socket
import ssl
from urllib.parse import urlparse

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from surf.i18n import tr
except ModuleNotFoundError:
    from i18n import tr


def fetch_certificate_details(url: str, timeout: float = 3.5) -> dict:
    """Извлекает настоящие данные SSL/TLS сертификата узла через защищённый сокет."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)

    if not host:
        return {"status": "invalid", "host": url, "is_secure": False, "error": "Invalid URL"}

    if scheme != "https":
        return {
            "status": "insecure",
            "host": host,
            "port": port,
            "is_secure": False,
            "scheme": scheme.upper(),
        }

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()

                subject = {}
                for item in cert.get("subject", ()):
                    for k, v in item:
                        subject[k] = v

                issuer = {}
                for item in cert.get("issuer", ()):
                    for k, v in item:
                        issuer[k] = v

                sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]

                raw_serial = cert.get("serialNumber", "")
                if raw_serial and ":" not in raw_serial:
                    serial = ":".join(raw_serial[i : i + 2] for i in range(0, len(raw_serial), 2))
                else:
                    serial = raw_serial

                return {
                    "status": "secure",
                    "host": host,
                    "port": port,
                    "is_secure": True,
                    "version": version or "TLS",
                    "cipher": cipher[0] if cipher else "Unknown",
                    "cipher_bits": cipher[2] if cipher else 0,
                    "subject_cn": subject.get("commonName", host),
                    "subject_org": subject.get("organizationName", ""),
                    "issuer_cn": issuer.get("commonName", ""),
                    "issuer_org": issuer.get("organizationName", issuer.get("commonName", "Unknown CA")),
                    "valid_from": cert.get("notBefore", ""),
                    "valid_to": cert.get("notAfter", ""),
                    "serial_number": serial,
                    "sans": sans,
                }
    except Exception as e:
        return {
            "status": "error",
            "host": host,
            "port": port,
            "is_secure": False,
            "error": str(e),
        }


class CertificateDialog(QDialog):
    """Информативное диалоговое окно со всеми деталями SSL/TLS сертификата узла."""

    def __init__(self, url: str, cert_data: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("cert_dialog_title"))
        self.setMinimumSize(540, 480)
        self.resize(560, 520)

        self.url = url
        self.cert_data = cert_data or fetch_certificate_details(url)
        self._init_ui()

    def _render_vector_icon(self, path: str, color: str, size: int = 24) -> QPixmap:
        if not os.path.exists(path):
            return QPixmap()
        try:
            with open(path, "r", encoding="utf-8") as f:
                svg_text = f.read()
            svg_text = svg_text.replace("#fbfbfe", color).replace("#15141a", color).replace('stroke="white"', f'stroke="{color}"')
            renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
            pix = QPixmap(size, size)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            renderer.render(painter)
            painter.end()
            return pix
        except Exception:
            return QPixmap()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # 1. Верхний баннер статуса соединения
        banner = QWidget()
        banner.setObjectName("certBanner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 12, 14, 12)
        banner_layout.setSpacing(14)

        is_secure = self.cert_data.get("is_secure", False)
        status_color = "#10b981" if is_secure else "#ef4444"
        bg_color = "rgba(16, 185, 129, 0.12)" if is_secure else "rgba(239, 68, 68, 0.12)"
        badge_bg = "rgba(16, 185, 129, 0.22)" if is_secure else "rgba(239, 68, 68, 0.22)"

        banner.setStyleSheet(f"""
            QWidget#certBanner {{
                background-color: {bg_color};
                border: 1.5px solid {status_color};
                border-radius: 10px;
            }}
            #certBanner QLabel {{
                border: none;
                background: transparent;
            }}
            #certBanner QLabel#certIconBadge {{
                background-color: {badge_bg};
                border: 1px solid {status_color};
                border-radius: 21px;
            }}
        """)

        # Круглый бейдж 42x42 с векторной иконкой замка / щита
        icon_badge = QLabel()
        icon_badge.setObjectName("certIconBadge")
        icon_badge.setFixedSize(42, 42)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
        icon_path = os.path.join(icons_dir, "lock.svg" if is_secure else "shield.svg")
        pix = self._render_vector_icon(icon_path, status_color, 22)
        if not pix.isNull():
            icon_badge.setPixmap(pix)
        else:
            icon_badge.setText("🔒" if is_secure else "⚠️")

        banner_layout.addWidget(icon_badge)

        status_text_layout = QVBoxLayout()
        status_text_layout.setContentsMargins(0, 0, 0, 0)
        status_text_layout.setSpacing(2)

        status_title = QLabel(tr("cert_status_secure") if is_secure else tr("cert_status_insecure"))
        status_title.setFont(QFont("", 13, QFont.Weight.Bold))
        status_title.setStyleSheet(f"color: {status_color}; font-weight: bold;")

        host_label = QLabel(self.cert_data.get("host", self.url))
        host_label.setFont(QFont("", 11, QFont.Weight.Bold))

        status_desc = QLabel(tr("cert_status_secure_desc") if is_secure else tr("cert_status_insecure_desc"))
        status_desc.setWordWrap(True)
        status_desc.setStyleSheet("color: #a4a4b2; font-size: 11px;")

        status_text_layout.addWidget(status_title)
        status_text_layout.addWidget(host_label)
        status_text_layout.addWidget(status_desc)
        banner_layout.addLayout(status_text_layout, stretch=1)

        main_layout.addWidget(banner)

        # 2. Вкладки со сведениями
        if is_secure:
            tabs = QTabWidget()

            # Вкладка 1: Общие сведения
            tab_general = QWidget()
            t1_layout = QVBoxLayout(tab_general)
            t1_layout.setContentsMargins(10, 10, 10, 10)
            t1_layout.setSpacing(10)

            # Группа: Кому выдан
            grp_subject = QGroupBox(tr("cert_subject_header"))
            form_subj = QFormLayout(grp_subject)
            form_subj.setSpacing(6)
            form_subj.addRow(tr("cert_common_name"), QLabel(self.cert_data.get("subject_cn", "-")))
            if self.cert_data.get("subject_org"):
                form_subj.addRow(tr("cert_org"), QLabel(self.cert_data.get("subject_org")))
            sans = self.cert_data.get("sans", [])
            if sans:
                san_str = ", ".join(sans[:6])
                if len(sans) > 6:
                    san_str += f" (+{len(sans) - 6})"
                lbl_sans = QLabel(san_str)
                lbl_sans.setWordWrap(True)
                form_subj.addRow(tr("cert_sans"), lbl_sans)
            t1_layout.addWidget(grp_subject)

            # Группа: Кем выдан
            grp_issuer = QGroupBox(tr("cert_issuer_header"))
            form_iss = QFormLayout(grp_issuer)
            form_iss.setSpacing(6)
            if self.cert_data.get("issuer_org"):
                form_iss.addRow(tr("cert_org"), QLabel(self.cert_data.get("issuer_org")))
            form_iss.addRow(tr("cert_common_name"), QLabel(self.cert_data.get("issuer_cn", "-")))
            t1_layout.addWidget(grp_issuer)

            # Группа: Срок действия
            grp_valid = QGroupBox(tr("cert_validity_header"))
            form_val = QFormLayout(grp_valid)
            form_val.setSpacing(6)
            form_val.addRow(tr("cert_valid_from"), QLabel(self.cert_data.get("valid_from", "-")))
            form_val.addRow(tr("cert_valid_to"), QLabel(self.cert_data.get("valid_to", "-")))
            t1_layout.addWidget(grp_valid)

            tabs.addTab(tab_general, tr("cert_tab_general"))

            # Вкладка 2: Технические детали
            tab_details = QWidget()
            t2_layout = QVBoxLayout(tab_details)
            t2_layout.setContentsMargins(10, 10, 10, 10)
            t2_layout.setSpacing(10)

            grp_tech = QGroupBox(tr("cert_tab_details"))
            form_tech = QFormLayout(grp_tech)
            form_tech.setSpacing(8)

            form_tech.addRow(tr("cert_protocol"), QLabel(self.cert_data.get("version", "TLS")))
            form_tech.addRow(
                tr("cert_cipher"),
                QLabel(f"{self.cert_data.get('cipher', '-')} ({self.cert_data.get('cipher_bits', 0)} bit)"),
            )

            serial_text = QTextEdit(self.cert_data.get("serial_number", "-"))
            serial_text.setReadOnly(True)
            serial_text.setFixedHeight(48)
            form_tech.addRow(tr("cert_serial"), serial_text)

            t2_layout.addWidget(grp_tech)
            t2_layout.addStretch()

            tabs.addTab(tab_details, tr("cert_tab_details"))
            main_layout.addWidget(tabs)
        else:
            # Ошибка или HTTP
            err_box = QWidget()
            err_layout = QVBoxLayout(err_box)
            err_layout.setContentsMargins(12, 12, 12, 12)
            if self.cert_data.get("status") == "error":
                lbl_err = QLabel(tr("cert_error_fetch", error=self.cert_data.get("error", "Unknown error")))
                lbl_err.setWordWrap(True)
                err_layout.addWidget(lbl_err)
            else:
                lbl_warn = QLabel(tr("cert_status_insecure_desc"))
                lbl_warn.setWordWrap(True)
                err_layout.addWidget(lbl_warn)
            main_layout.addWidget(err_box)
            main_layout.addStretch()

        # 3. Кнопка Закрыть
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton(tr("btn_close"))
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        main_layout.addLayout(btn_box)
