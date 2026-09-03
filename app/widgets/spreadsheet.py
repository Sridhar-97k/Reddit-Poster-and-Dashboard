import logging

from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QRubberBand,
                              QAbstractItemView, QApplication, QWidget)
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QColor, QKeySequence

logger = logging.getLogger(__name__)

_HANDLE_SIZE = 8


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# Fill pattern helpers
# ---------------------------------------------------------------------------

def _detect_arithmetic(values):
    """Return (start, step) if values form an arithmetic sequence, else None."""
    stripped = [v.strip() for v in values]
    if len(stripped) < 2:
        return None
    try:
        nums = [float(v) for v in stripped]
    except ValueError:
        return None
    step = nums[1] - nums[0]
    for i in range(2, len(nums)):
        if abs((nums[i] - nums[i - 1]) - step) > 1e-9:
            return None
    return (nums[0], step)


def _apply_arithmetic(pattern, index):
    """Value at sequence position `index` for an arithmetic pattern."""
    start, step = pattern
    val = start + step * index
    return str(int(val)) if val == int(val) else str(val)


# ---------------------------------------------------------------------------
# Fill handle overlay widget
# ---------------------------------------------------------------------------

class _FillHandle(QWidget):
    """Small square drawn at the bottom-right corner of the current selection.
    Drag it to fill adjacent cells."""

    def __init__(self, table: 'SpreadsheetWidget'):
        super().__init__(table.viewport())
        self._table = table
        self._dragging = False
        self._drag_target = None          # (row, col) under the cursor
        self._rubber_band = QRubberBand(QRubberBand.Rectangle, table.viewport())
        self.setFixedSize(_HANDLE_SIZE, _HANDLE_SIZE)
        self.setCursor(Qt.CrossCursor)
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#2980b9'))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_target = None
            self.grabMouse()            # keep receiving events while mouse roams
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        vp_pos = self.mapToParent(event.pos())
        idx = self._table.indexAt(vp_pos)
        if idx.isValid():
            self._drag_target = (idx.row(), idx.column())
            self._update_rubber_band()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.releaseMouse()
            self._rubber_band.hide()
            if self._drag_target:
                self._table._do_fill(*self._drag_target)
            self._drag_target = None
            event.accept()

    def _update_rubber_band(self):
        if not self._drag_target:
            return
        bounds = self._table._selection_bounds()
        if not bounds:
            return
        src_top, src_left, src_bottom, src_right = bounds
        tgt_row, tgt_col = self._drag_target
        rb_top    = src_top
        rb_left   = src_left
        rb_bottom = max(src_bottom, tgt_row)
        rb_right  = max(src_right,  tgt_col)
        tl = self._table.visualRect(self._table.model().index(rb_top,    rb_left)).topLeft()
        br = self._table.visualRect(self._table.model().index(rb_bottom, rb_right)).bottomRight()
        self._rubber_band.setGeometry(QRect(tl, br).adjusted(0, 0, 1, 1))
        self._rubber_band.show()


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class SpreadsheetWidget(QTableWidget):
    """QTableWidget with Excel-like editing:
    - Multi-cell Ctrl+C / Ctrl+V (TSV, compatible with Excel clipboard)
    - Paste to a larger selection tiles the data
    - Paste from Excel (tab-separated rows) works directly
    - Delete / Backspace clears selected cells
    - Fill handle drag repeats values or continues arithmetic series
    """

    def __init__(self, rows=1, cols=4, parent=None):
        super().__init__(rows, cols, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.AnyKeyPressed |
            QAbstractItemView.EditKeyPressed
        )
        self.setAlternatingRowColors(True)

        # Drop the in-cell editor border entirely: the global stylesheet gives
        # every QLineEdit a 2px border + 8px padding, which looks bulky in a cell.
        self.setStyleSheet(
            "QLineEdit { border: none; border-radius: 0px; padding: 0px 2px; }"
            "QComboBox { border: none; border-radius: 0px; padding: 0px 2px; }"
        )

        self._fill_handle = _FillHandle(self)

        self.itemSelectionChanged.connect(self._reposition_handle)
        self.horizontalScrollBar().valueChanged.connect(self._reposition_handle)
        self.verticalScrollBar().valueChanged.connect(self._reposition_handle)

    # ------------------------------------------------------------------ keys

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy()
            return
        if event.matches(QKeySequence.Paste):
            self._paste()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # Only clear when not currently editing a cell
            if self.state() != QAbstractItemView.EditingState:
                self._delete_selected()
                return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------ copy

    def _copy(self):
        bounds = self._selection_bounds()
        if not bounds:
            return
        top, left, bottom, right = bounds
        lines = []
        for r in range(top, bottom + 1):
            cells = [self._cell_text(r, c) for c in range(left, right + 1)]
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))

    # ------------------------------------------------------------------ paste

    def _paste(self):
        text = QApplication.clipboard().text()
        if not text:
            return

        # Parse tab-separated clipboard (Excel format)
        paste_rows = [row.split('\t') for row in text.splitlines()]
        if not paste_rows:
            return

        bounds = self._selection_bounds()
        if not bounds:
            return

        sel_top, sel_left, sel_bottom, sel_right = bounds
        paste_h = len(paste_rows)
        paste_w = max(len(row) for row in paste_rows)
        sel_h   = sel_bottom - sel_top + 1
        sel_w   = sel_right  - sel_left + 1

        # If the selection is larger than the paste block, tile it to fill
        fill_h = sel_h if sel_h > paste_h else paste_h
        fill_w = sel_w if sel_w > paste_w else paste_w

        # Grow the table if the paste would go beyond the last row
        needed = sel_top + fill_h
        if needed > self.rowCount():
            self.setRowCount(needed)

        for dr in range(fill_h):
            for dc in range(fill_w):
                table_r = sel_top  + dr
                table_c = sel_left + dc
                if table_c >= self.columnCount():
                    continue
                pr = dr % paste_h
                pc = dc % paste_w
                value = paste_rows[pr][pc] if pc < len(paste_rows[pr]) else ''
                self._set_cell(table_r, table_c, value)

    # ------------------------------------------------------------------ delete

    def _delete_selected(self):
        for item in self.selectedItems():
            item.setText('')

    # ------------------------------------------------------------------ fill handle

    def _selection_bounds(self):
        """Return (top, left, bottom, right) of the current selection, or None."""
        ranges = self.selectedRanges()
        if not ranges:
            return None
        return (
            min(r.topRow()      for r in ranges),
            min(r.leftColumn()  for r in ranges),
            max(r.bottomRow()   for r in ranges),
            max(r.rightColumn() for r in ranges),
        )

    def _reposition_handle(self):
        bounds = self._selection_bounds()
        if not bounds:
            self._fill_handle.hide()
            return
        _, _, bottom, right = bounds
        cell_rect = self.visualRect(self.model().index(bottom, right))
        vp_rect   = self.viewport().rect()

        if not vp_rect.intersects(cell_rect):
            self._fill_handle.hide()
            return

        hs  = _HANDLE_SIZE
        pos = QPoint(
            _clamp(cell_rect.right()  - hs // 2, 0, vp_rect.right()  - hs),
            _clamp(cell_rect.bottom() - hs // 2, 0, vp_rect.bottom() - hs),
        )
        self._fill_handle.move(pos)
        self._fill_handle.show()
        self._fill_handle.raise_()

    def _do_fill(self, tgt_row, tgt_col):
        """Fill from the current selection toward (tgt_row, tgt_col)."""
        bounds = self._selection_bounds()
        if not bounds:
            return
        src_top, src_left, src_bottom, src_right = bounds

        # Grow table if needed
        if tgt_row + 1 > self.rowCount():
            self.setRowCount(tgt_row + 1)

        # Fill downward
        if tgt_row > src_bottom:
            for c in range(src_left, src_right + 1):
                src = [self._cell_text(r, c) for r in range(src_top, src_bottom + 1)]
                pat = _detect_arithmetic(src)
                for i, r in enumerate(range(src_bottom + 1, tgt_row + 1)):
                    val = _apply_arithmetic(pat, len(src) + i) if pat else src[i % len(src)]
                    self._set_cell(r, c, val)

        # Fill rightward
        if tgt_col > src_right:
            for r in range(src_top, src_bottom + 1):
                src = [self._cell_text(r, c) for c in range(src_left, src_right + 1)]
                pat = _detect_arithmetic(src)
                for i, c in enumerate(range(src_right + 1, tgt_col + 1)):
                    val = _apply_arithmetic(pat, len(src) + i) if pat else src[i % len(src)]
                    self._set_cell(r, c, val)

        self._reposition_handle()

    # ------------------------------------------------------------------ helpers

    def _cell_text(self, row, col):
        item = self.item(row, col)
        return item.text() if item else ''

    def _set_cell(self, row, col, value):
        item = self.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.setItem(row, col, item)
        item.setText(value)
