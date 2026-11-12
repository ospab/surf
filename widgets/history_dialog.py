from PyQt6.QtCore import QDate, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
)

try:
    from surf.database import Database
    from surf.i18n import tr
    from surf.ui.ui_history import Ui_HistoryDialog
except ModuleNotFoundError:
    from database import Database
    from i18n import tr
    from ui.ui_history import Ui_HistoryDialog

# Пункты выпадающего списка периода (порядок совпадает с history.ui)
PERIOD_FILTERS = ("all", "today", "yesterday", "week", "range")
RANGE_INDEX = PERIOD_FILTERS.index("range")
DATE_FORMAT_SQL = "yyyy-MM-dd"


class HistoryDialog(QDialog, Ui_HistoryDialog):
    """Журнал: история, закладки и статистика. Форма сделана в Qt Designer (history.ui)."""

    # Способ 2: форма history.ui скомпилирована pyuic6 в ui_history.py
    open_url = pyqtSignal(str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.db = db

        self._retranslate_ui()
        self._setup_tables()
        self._setup_date_range()
        self._connect_signals()
        self.reload_all()

    def _setup_date_range(self) -> None:
        """Поля «с … по …» (QDateEdit с всплывающим QCalendarWidget) для режима «Диапазон дат»."""
        today = QDate.currentDate()
        self.dateFromEdit.setDate(today.addDays(-7))
        self.dateToEdit.setDate(today)
        self.dateFromEdit.setMaximumDate(today)
        self.dateToEdit.setMaximumDate(today)
        self._update_date_range_visibility()

    def _update_date_range_visibility(self) -> None:
        is_range = self.periodCombo.currentIndex() == RANGE_INDEX
        for widget in (self.dateFromEdit, self.dateDashLabel, self.dateToEdit):
            widget.setVisible(is_range)

    def _on_period_changed(self) -> None:
        self._update_date_range_visibility()
        self._reload_history()

    def _current_filter(self) -> tuple[str, str | None, str | None]:
        """Возвращает (период, дата_с, дата_по) в формате для Database."""
        period = PERIOD_FILTERS[self.periodCombo.currentIndex()]
        if period != "range":
            return period, None, None
        date_from = self.dateFromEdit.date()
        date_to = self.dateToEdit.date()
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return "all", date_from.toString(DATE_FORMAT_SQL), date_to.toString(DATE_FORMAT_SQL)

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("history_dialog_title"))
        self.tabs.setTabText(0, tr("tab_history"))
        self.tabs.setTabText(1, tr("tab_bookmarks"))
        self.tabs.setTabText(2, tr("tab_stats"))

        self.historySearchEdit.setPlaceholderText(tr("search_history_placeholder"))
        self.bookmarksSearchEdit.setPlaceholderText(tr("search_bookmarks_placeholder"))

        self.periodCombo.setItemText(0, tr("filter_all"))
        self.periodCombo.setItemText(1, tr("filter_today"))
        self.periodCombo.setItemText(2, tr("filter_yesterday"))
        self.periodCombo.setItemText(3, tr("filter_week"))
        self.periodCombo.setItemText(RANGE_INDEX, tr("filter_range"))

        self.exportHistoryCsvBtn.setText(tr("btn_export_csv"))
        self.deleteHistoryBtn.setText(tr("btn_delete_selected"))
        self.clearAllHistoryBtn.setText(tr("btn_clear_history"))
        self.openHistoryUrlBtn.setText(tr("btn_open_tab"))

        self.importBookmarksCsvBtn.setText(tr("btn_import_csv"))
        self.exportBookmarksCsvBtn.setText(tr("btn_export_csv"))
        self.deleteBookmarkBtn.setText(tr("btn_delete_bookmark"))
        self.openBookmarkUrlBtn.setText(tr("btn_open_tab"))

        self.statsInfoLabel.setText(tr("stats_info"))
        self.closeBtn.setText(tr("btn_close"))

    def _setup_tables(self) -> None:
        self.historyTable.setColumnCount(5)
        self.historyTable.setHorizontalHeaderLabels(
            [tr("col_id"), tr("col_title"), tr("col_url"), tr("col_time"), tr("col_visits")]
        )
        self.historyTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.historyTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.historyTable.setSelectionBehavior(self.historyTable.SelectionBehavior.SelectRows)
        self.historyTable.setSelectionMode(self.historyTable.SelectionMode.SingleSelection)
        self.historyTable.setColumnHidden(0, True)

        self.bookmarksTable.setColumnCount(5)
        self.bookmarksTable.setHorizontalHeaderLabels(
            [tr("col_id"), tr("col_title"), tr("col_url"), tr("col_folder"), tr("col_added")]
        )
        self.bookmarksTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.bookmarksTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.bookmarksTable.setSelectionBehavior(self.bookmarksTable.SelectionBehavior.SelectRows)
        self.bookmarksTable.setSelectionMode(self.bookmarksTable.SelectionMode.SingleSelection)
        self.bookmarksTable.setColumnHidden(0, True)

        self.statsTable.setColumnCount(3)
        self.statsTable.setHorizontalHeaderLabels([tr("col_rank"), tr("col_domain"), tr("col_views")])
        self.statsTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.statsTable.setSelectionBehavior(self.statsTable.SelectionBehavior.SelectRows)

    def _connect_signals(self) -> None:
        self.historySearchEdit.textChanged.connect(self._reload_history)
        self.periodCombo.currentIndexChanged.connect(self._on_period_changed)
        self.dateFromEdit.dateChanged.connect(self._reload_history)
        self.dateToEdit.dateChanged.connect(self._reload_history)
        self.deleteHistoryBtn.clicked.connect(self._delete_selected_history)
        self.clearAllHistoryBtn.clicked.connect(self._clear_history)
        self.exportHistoryCsvBtn.clicked.connect(self._export_history_csv)
        self.openHistoryUrlBtn.clicked.connect(self._open_history_selected)
        self.historyTable.cellDoubleClicked.connect(lambda r, c: self._open_history_selected())

        self.bookmarksSearchEdit.textChanged.connect(self._reload_bookmarks)
        self.deleteBookmarkBtn.clicked.connect(self._delete_selected_bookmark)
        self.exportBookmarksCsvBtn.clicked.connect(self._export_bookmarks_csv)
        self.importBookmarksCsvBtn.clicked.connect(self._import_bookmarks_csv)
        self.openBookmarkUrlBtn.clicked.connect(self._open_bookmark_selected)
        self.bookmarksTable.cellDoubleClicked.connect(lambda r, c: self._open_bookmark_selected())

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.closeBtn.clicked.connect(self.accept)

    def reload_all(self) -> None:
        self._reload_history()
        self._reload_bookmarks()
        self._reload_stats()

    def _on_tab_changed(self, index: int) -> None:
        if index == 0:
            self._reload_history()
        elif index == 1:
            self._reload_bookmarks()
        elif index == 2:
            self._reload_stats()

    # --- Обработка истории ---

    def _reload_history(self) -> None:
        search = self.historySearchEdit.text().strip()
        period, date_from, date_to = self._current_filter()
        records = self.db.get_history(search_query=search, date_filter=period, date_from=date_from, date_to=date_to)
        self.historyTable.setRowCount(len(records))

        for row_idx, row in enumerate(records):
            self.historyTable.setItem(row_idx, 0, QTableWidgetItem(str(row["id"])))
            self.historyTable.setItem(row_idx, 1, QTableWidgetItem(row["title"]))
            self.historyTable.setItem(row_idx, 2, QTableWidgetItem(row["url"]))
            self.historyTable.setItem(row_idx, 3, QTableWidgetItem(row["visit_time"]))
            self.historyTable.setItem(row_idx, 4, QTableWidgetItem(str(row["visit_count"])))

    def _delete_selected_history(self) -> None:
        row = self.historyTable.currentRow()
        if row < 0:
            return
        entry_id = int(self.historyTable.item(row, 0).text())
        self.db.delete_history_entry(entry_id)
        self._reload_history()

    def _clear_history(self) -> None:
        ans = QMessageBox.question(
            self,
            tr("clear_history_title"),
            tr("clear_history_prompt"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            # Удаляем только то, что сейчас видно в таблице
            period, date_from, date_to = self._current_filter()
            self.db.delete_history_filtered(period, date_from, date_to)
            self._reload_history()
            self._reload_stats()

    def _open_history_selected(self) -> None:
        row = self.historyTable.currentRow()
        if row >= 0:
            url = self.historyTable.item(row, 2).text()
            self.open_url.emit(url)
            self.accept()

    def _export_history_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("btn_export_csv"),
            "surf_history.csv",
            "CSV (*.csv);;All Files (*)",
        )
        if path:
            count = self.db.export_history_to_csv(path)
            QMessageBox.information(
                self,
                tr("msg_done_title"),
                tr("msg_history_exported", count=count, path=path),
            )

    # --- Обработка закладок ---

    def _reload_bookmarks(self) -> None:
        search = self.bookmarksSearchEdit.text().strip()
        bookmarks = self.db.get_bookmarks(search_query=search)
        self.bookmarksTable.setRowCount(len(bookmarks))

        for row_idx, b in enumerate(bookmarks):
            self.bookmarksTable.setItem(row_idx, 0, QTableWidgetItem(str(b["id"])))
            self.bookmarksTable.setItem(row_idx, 1, QTableWidgetItem(b["title"]))
            self.bookmarksTable.setItem(row_idx, 2, QTableWidgetItem(b["url"]))
            self.bookmarksTable.setItem(row_idx, 3, QTableWidgetItem(b["folder"]))
            self.bookmarksTable.setItem(row_idx, 4, QTableWidgetItem(b["added_time"]))

    def _delete_selected_bookmark(self) -> None:
        row = self.bookmarksTable.currentRow()
        if row < 0:
            return
        bm_id = int(self.bookmarksTable.item(row, 0).text())
        self.db.delete_bookmark(bm_id)
        self._reload_bookmarks()

    def _open_bookmark_selected(self) -> None:
        row = self.bookmarksTable.currentRow()
        if row >= 0:
            url = self.bookmarksTable.item(row, 2).text()
            self.open_url.emit(url)
            self.accept()

    def _export_bookmarks_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("btn_export_csv"),
            "surf_bookmarks.csv",
            "CSV (*.csv);;All Files (*)",
        )
        if path:
            count = self.db.export_bookmarks_to_csv(path)
            QMessageBox.information(
                self,
                tr("msg_done_title"),
                tr("msg_bookmarks_exported", count=count, path=path),
            )

    def _import_bookmarks_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("btn_import_csv"),
            "",
            "CSV (*.csv);;All Files (*)",
        )
        if path:
            count = self.db.import_bookmarks_from_csv(path)
            self._reload_bookmarks()
            QMessageBox.information(
                self,
                tr("msg_done_title"),
                tr("msg_bookmarks_imported", count=count, path=path),
            )

    # --- Статистика ---

    def _reload_stats(self) -> None:
        top_domains = self.db.get_top_domains(limit=15)
        self.statsTable.setRowCount(len(top_domains))

        for idx, (domain, count) in enumerate(top_domains, start=1):
            row_idx = idx - 1
            self.statsTable.setItem(row_idx, 0, QTableWidgetItem(str(idx)))
            self.statsTable.setItem(row_idx, 1, QTableWidgetItem(domain))
            self.statsTable.setItem(row_idx, 2, QTableWidgetItem(str(count)))
