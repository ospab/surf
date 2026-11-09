import os
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from surf.database import Database


class DownloadManagerDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Загрузки")
        self.resize(680, 400)
        self._init_ui()
        self.reload_downloads()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Имя файла", "Размер", "Статус", "Дата", "Путь"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.open_folder_btn = QPushButton("Открыть папку с файлом")
        self.clear_btn = QPushButton("Очистить список")
        self.close_btn = QPushButton("Закрыть")

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

        for row_idx, d in enumerate(downloads):
            size_mb = f"{d['total_bytes'] / (1024 * 1024):.2f} МБ" if d["total_bytes"] > 0 else "—"
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
            QMessageBox.warning(self, "Ошибка", f"Папка не найдена:\n{folder}")

    def _clear_list(self) -> None:
        self.db.clear_downloads()
        self.reload_downloads()
