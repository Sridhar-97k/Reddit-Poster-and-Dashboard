import csv
import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog,
                             QStyledItemDelegate, QComboBox)
from PyQt5.QtCore import Qt

from ..widgets.spreadsheet import SpreadsheetWidget
from ..workers import FlairFetchWorker
from ..csv_utils import safe_row

logger = logging.getLogger(__name__)

_COLS = ['subreddit', 'title', 'url', 'flair']
_INITIAL_ROWS = 20


class _ComboBoxDelegate(QStyledItemDelegate):
    """Editable combo-box cell editor whose options are computed per-cell.

    `choices_for` is a callable taking the cell's QModelIndex and returning the
    list of dropdown options. The editor stays editable so a custom value can
    still be typed."""

    def __init__(self, choices_for, parent=None):
        super().__init__(parent)
        self._choices_for = choices_for

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.addItem('')
        for text in self._choices_for(index):
            combo.addItem(text)
        return combo

    def setEditorData(self, editor, index):
        value = index.data() or ''
        i = editor.findText(value)
        if i >= 0:
            editor.setCurrentIndex(i)
        else:
            editor.setEditText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText().strip(), Qt.EditRole)


class ImportTab(QWidget):
    """Editable spreadsheet for composing posts. No separate Excel file needed."""

    def __init__(self, get_reddit, flair_store, favorites):
        super().__init__()
        self._get_reddit = get_reddit
        self._flair_store = flair_store
        self._favorites = favorites
        self._flair_worker = None
        self._flair_requested = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Brief format reminder
        info = QLabel(
            "Columns: <b>subreddit</b> (no r/) · <b>title</b> · <b>url</b> · <b>flair</b> (optional)  "
            "— edit directly here.  The Subreddit and Flair cells offer dropdowns "
            "(your favourites · fetched flairs).  Ctrl+C / Ctrl+V, Delete, and fill-handle drag all work."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        add_btn = QPushButton("➕ Add Row")
        add_btn.clicked.connect(self._add_row)
        add_btn.setMinimumHeight(32)

        remove_btn = QPushButton("🗑️ Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        remove_btn.setMinimumHeight(32)

        clear_btn = QPushButton("🧹 Clear All")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setMinimumHeight(32)

        self.get_flairs_btn = QPushButton("🎨 Get Flairs")
        self.get_flairs_btn.setToolTip(
            "Fetch current flairs from Reddit for every subreddit in the table\n"
            "and cache them so they appear as a dropdown in the Flair column."
        )
        self.get_flairs_btn.clicked.connect(self._get_flairs)
        self.get_flairs_btn.setMinimumHeight(32)

        toolbar.addWidget(add_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addWidget(self.get_flairs_btn)
        toolbar.addStretch()

        export_btn = QPushButton("📤 Export to CSV")
        export_btn.setToolTip("Save the current rows to a .csv file as a backup.")
        export_btn.clicked.connect(self._export_csv)
        export_btn.setMinimumHeight(32)

        toolbar.addWidget(export_btn)

        layout.addLayout(toolbar)

        # Spreadsheet
        self.spreadsheet = SpreadsheetWidget(rows=_INITIAL_ROWS, cols=len(_COLS))
        self.spreadsheet.setHorizontalHeaderLabels([c.capitalize() for c in _COLS])
        hdr = self.spreadsheet.horizontalHeader()
        for col in range(len(_COLS)):                                # equal width
            hdr.setSectionResizeMode(col, QHeaderView.Stretch)

        # Subreddit column: dropdown of your favourite subreddits (still editable)
        self._sub_delegate = _ComboBoxDelegate(
            lambda _index: self._favorite_names(), parent=self.spreadsheet)
        self.spreadsheet.setItemDelegateForColumn(0, self._sub_delegate)

        # Flair column: dropdown of that row's subreddit's cached flairs
        self._flair_delegate = _ComboBoxDelegate(
            self._flairs_for_index, parent=self.spreadsheet)
        self.spreadsheet.setItemDelegateForColumn(3, self._flair_delegate)

        layout.addWidget(self.spreadsheet)

    # ------------------------------------------------------------------ dropdown sources

    def _favorite_names(self):
        """Favourite subreddit names (alphabetical) — for the Subreddit dropdown."""
        return [f['name'] for f in self._favorites.sorted_by_name()]

    def _flairs_for_index(self, index):
        """Cached flairs for the subreddit in this row — for the Flair dropdown."""
        sub = (index.model().index(index.row(), 0).data() or '').strip()
        return self._flair_store.get_texts(sub) if sub else []

    # ------------------------------------------------------------------ public

    def get_posts(self):
        """Return a list of dicts for every row that has subreddit + title + url."""
        posts = []
        for row in range(self.spreadsheet.rowCount()):
            sub   = self._cell(row, 0)
            title = self._cell(row, 1)
            url   = self._cell(row, 2)
            flair = self._cell(row, 3)
            if sub and title and url:
                posts.append({'subreddit': sub, 'title': title, 'url': url, 'flair': flair})
        return posts

    # ------------------------------------------------------------------ flairs

    def _get_flairs(self):
        reddit = self._get_reddit()
        if not reddit:
            return

        seen = set()
        subs = []
        for row in range(self.spreadsheet.rowCount()):
            sub = self._cell(row, 0).lower()
            if sub and sub not in seen:
                seen.add(sub)
                subs.append(sub)
        if not subs:
            QMessageBox.warning(self, 'No Subreddits',
                'Enter at least one subreddit in the Subreddit column first.')
            return

        self._flair_requested = subs
        self.get_flairs_btn.setEnabled(False)
        self.get_flairs_btn.setText("⏳ Fetching…")

        self._flair_worker = FlairFetchWorker(reddit, subs)
        self._flair_worker.finished.connect(self._on_flairs_fetched)
        self._flair_worker.error.connect(self._on_flairs_error)
        self._flair_worker.start()
        logger.info("Fetching flairs for %d subreddit(s)", len(subs))

    def _on_flairs_fetched(self, result):
        self.get_flairs_btn.setEnabled(True)
        self.get_flairs_btn.setText("🎨 Get Flairs")

        for sub, flairs in result.items():
            self._flair_store.update(sub, flairs)

        total_flairs = sum(len(v) for v in result.values())
        failed = [s for s in self._flair_requested if s not in result]
        msg = (f"Fetched flairs for {len(result)} subreddit(s) — "
               f"{total_flairs} flair(s) total, saved to the flair database.")
        if failed:
            msg += "\n\nCouldn't fetch: " + ", ".join(f"r/{s}" for s in failed)
        msg += "\n\nClick a cell in the Flair column to pick from the dropdown."
        QMessageBox.information(self, 'Flairs Updated', msg)

    def _on_flairs_error(self, message):
        self.get_flairs_btn.setEnabled(True)
        self.get_flairs_btn.setText("🎨 Get Flairs")
        QMessageBox.critical(self, 'Flair Fetch Failed', f'Failed to fetch flairs:\n{message}')

    def stop_worker_on_close(self):
        """Call from closeEvent to clean up the flair worker thread."""
        if self._flair_worker and self._flair_worker.isRunning():
            self._flair_worker.stop()
            self._flair_worker.wait(3000)
            if self._flair_worker.isRunning():
                self._flair_worker.terminate()

    # ------------------------------------------------------------------ row ops

    def _add_row(self):
        self.spreadsheet.insertRow(self.spreadsheet.rowCount())

    def _remove_selected(self):
        rows = sorted({idx.row() for idx in self.spreadsheet.selectedIndexes()}, reverse=True)
        for row in rows:
            self.spreadsheet.removeRow(row)
        if self.spreadsheet.rowCount() == 0:
            self.spreadsheet.setRowCount(1)

    def _clear_all(self):
        reply = QMessageBox.question(self, 'Clear All',
            'Clear all rows?', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.spreadsheet.clearContents()
            self.spreadsheet.setRowCount(_INITIAL_ROWS)

    # ------------------------------------------------------------------ Excel export (backup)

    def _export_csv(self):
        posts = self.get_posts()
        if not posts:
            QMessageBox.warning(self, 'No Data', 'No valid rows to export (subreddit + title + url required).')
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "reddit_posts.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(_COLS)
                for post in posts:
                    writer.writerow(safe_row([post['subreddit'], post['title'], post['url'], post['flair']]))
            QMessageBox.information(self, 'Exported', f'Saved {len(posts)} posts to:\n{file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export:\n{str(e)}')

    # ------------------------------------------------------------------ helper

    def _cell(self, row, col):
        item = self.spreadsheet.item(row, col)
        return item.text().strip() if item else ''
