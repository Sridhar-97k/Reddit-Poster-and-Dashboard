import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog)
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from ..widgets.spreadsheet import SpreadsheetWidget

logger = logging.getLogger(__name__)

_COLS = ['subreddit', 'title', 'url', 'flair']
_INITIAL_ROWS = 20


class ImportTab(QWidget):
    """Editable spreadsheet for composing posts. No separate Excel file needed."""

    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Brief format reminder
        info = QLabel(
            "Columns: <b>subreddit</b> (no r/) · <b>title</b> · <b>url</b> · <b>flair</b> (optional)  "
            "— edit directly or import from Excel.  "
            "Ctrl+C / Ctrl+V, Delete, and fill-handle drag all work."
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

        toolbar.addWidget(add_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()

        import_btn = QPushButton("📥 Import from Excel")
        import_btn.clicked.connect(self._import_excel)
        import_btn.setMinimumHeight(32)

        export_btn = QPushButton("📤 Export to Excel")
        export_btn.clicked.connect(self._export_excel)
        export_btn.setMinimumHeight(32)

        template_btn = QPushButton("📋 Download Template")
        template_btn.clicked.connect(self._download_template)
        template_btn.setMinimumHeight(32)

        toolbar.addWidget(import_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(template_btn)

        layout.addLayout(toolbar)

        # Spreadsheet
        self.spreadsheet = SpreadsheetWidget(rows=_INITIAL_ROWS, cols=len(_COLS))
        self.spreadsheet.setHorizontalHeaderLabels([c.capitalize() for c in _COLS])
        hdr = self.spreadsheet.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # subreddit
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)             # title
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)             # url
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)    # flair
        layout.addWidget(self.spreadsheet)

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

    # ------------------------------------------------------------------ public API

    def load_posts(self, posts):
        """Append a list of post dicts (from SearchTab) into the spreadsheet.
        Finds the first fully empty row and writes from there, growing the
        table if needed."""
        start = self._first_empty_row()
        needed = start + len(posts)
        if needed > self.spreadsheet.rowCount():
            self.spreadsheet.setRowCount(needed)
        for i, post in enumerate(posts):
            row = start + i
            self.spreadsheet._set_cell(row, 0, post.get('subreddit', ''))
            self.spreadsheet._set_cell(row, 1, post.get('title', ''))
            self.spreadsheet._set_cell(row, 2, post.get('url', ''))
            self.spreadsheet._set_cell(row, 3, post.get('flair', ''))

    def _first_empty_row(self):
        for row in range(self.spreadsheet.rowCount()):
            if not self._cell(row, 0) and not self._cell(row, 1) and not self._cell(row, 2):
                return row
        return self.spreadsheet.rowCount()

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

    # ------------------------------------------------------------------ Excel I/O

    def _import_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        try:
            wb = load_workbook(file_path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            if not rows:
                QMessageBox.warning(self, 'Empty File', 'No data rows found in the Excel file.')
                return

            self.spreadsheet.clearContents()
            self.spreadsheet.setRowCount(max(len(rows), _INITIAL_ROWS))

            for r, row in enumerate(rows):
                for c in range(min(len(row), len(_COLS))):
                    val = str(row[c]).strip() if row[c] is not None else ''
                    self.spreadsheet._set_cell(r, c, val)

            logger.info(f"Imported {len(rows)} rows from {file_path}")
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load Excel file:\n{str(e)}')

    def _export_excel(self):
        posts = self.get_posts()
        if not posts:
            QMessageBox.warning(self, 'No Data', 'No valid rows to export (subreddit + title + url required).')
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to Excel", "reddit_posts.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Reddit Posts"
            for col, header in enumerate(_COLS, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = header
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')
            for r, post in enumerate(posts, 2):
                ws.cell(row=r, column=1, value=post['subreddit'])
                ws.cell(row=r, column=2, value=post['title'])
                ws.cell(row=r, column=3, value=post['url'])
                ws.cell(row=r, column=4, value=post['flair'])
            ws.column_dimensions['A'].width = 20
            ws.column_dimensions['B'].width = 50
            ws.column_dimensions['C'].width = 60
            ws.column_dimensions['D'].width = 20
            wb.save(file_path)
            QMessageBox.information(self, 'Exported', f'Saved {len(posts)} posts to:\n{file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to export:\n{str(e)}')

    def _download_template(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Template", "reddit_posts_template.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Reddit Posts"
            for col, header in enumerate(_COLS, 1):
                cell = ws.cell(row=1, column=col)
                cell.value = header
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')
            examples = [
                ['python',      'Amazing automation script', 'https://github.com/example/script', 'Tutorial'],
                ['technology',  'New quantum computing breakthrough', 'https://news.example.com/quantum', 'News'],
                ['programming', 'Best practices for code review',     'https://blog.example.com/review',  ''],
            ]
            for r, row in enumerate(examples, 2):
                for c, val in enumerate(row, 1):
                    ws.cell(row=r, column=c, value=val)
            ws.column_dimensions['A'].width = 20
            ws.column_dimensions['B'].width = 50
            ws.column_dimensions['C'].width = 60
            ws.column_dimensions['D'].width = 20
            wb.save(file_path)
            QMessageBox.information(self, 'Template Saved', f'Template saved to:\n{file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to create template:\n{str(e)}')

    # ------------------------------------------------------------------ helper

    def _cell(self, row, col):
        item = self.spreadsheet.item(row, col)
        return item.text().strip() if item else ''
