import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

try:
    from surf.database import Database
    from surf.i18n import tr
except ModuleNotFoundError:
    from database import Database
    from i18n import tr


class DownloadManagerDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(tr("downloads_title"))
        self.resize(680, 400)
        self._init_ui()
        self.reload_downloads()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [tr("col_dl_name"), tr("col_dl_size"), tr("col_dl_status"), tr("col_dl_time"), tr("col_dl_path")]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.open_folder_btn = QPushButton(tr("btn_open_folder"))
        self.clear_btn = QPushButton(tr("btn_clear_list"))
        self.close_btn = QPushButton(tr("btn_close"))

        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.open_folder_btn.clicked.connect(self._open_folder)
        self.clear_btn.clicked.connect(self._clear_list)
        self.close_btn.clicked.connect(self.accept)
        self.table.cellDoubleClicked.connect(lambda r, c: self._open_folder())

    def reload_downloads(self) -> None:
        downloads = self.db.get_downloads()
        self.table.setRowCount(len(downloads))

        unit = "MB" if tr("col_dl_size") == "Size" else "МБ"
        for row_idx, d in enumerate(downloads):
            size_mb = f"{d['total_bytes'] / (1024 * 1024):.2f} {unit}" if d["total_bytes"] > 0 else "—"
            self.table.setItem(row_idx, 0, QTableWidgetItem(d["file_name"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(size_mb))
            self.table.setItem(row_idx, 2, QTableWidgetItem(d["status"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(d["download_time"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(d["file_path"]))

    def _open_folder(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        path = self.table.item(row, 4).text()
        folder = os.path.dirname(path)
        if os.path.exists(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QMessageBox.warning(self, "Error", f"Folder not found:\n{folder}")

    def _clear_list(self) -> None:
        self.db.clear_downloads()
        self.reload_downloads()
