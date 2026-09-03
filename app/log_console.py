"""In-app log console.

A read-only panel that mirrors Python ``logging`` output inside the GUI, so the
packaged .exe (which has no terminal) still shows what the app is doing.

Log records can arrive from worker threads, so records are marshalled to the GUI
thread through a QObject signal (Qt delivers cross-thread signals safely via the
event loop) before touching any widget.
"""

import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QPlainTextEdit)
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont

_LEVEL_COLORS = {
    'WARNING':  '#e67e22',
    'ERROR':    '#e74c3c',
    'CRITICAL': '#ff6b6b',
}


class _LogBridge(QObject):
    """Carries formatted log lines from any thread to the GUI thread."""
    message = pyqtSignal(str, str)   # (formatted_message, levelname)


class _QtLogHandler(logging.Handler):
    def __init__(self, bridge):
        super().__init__()
        self._bridge = bridge

    def emit(self, record):
        try:
            self._bridge.message.emit(self.format(record), record.levelname)
        except Exception:
            self.handleError(record)


class LogConsole(QWidget):
    """A read-only log panel. Call :meth:`install` to attach it to a logger."""

    def __init__(self, level=logging.INFO, max_lines=2000, parent=None):
        super().__init__(parent)
        self._build_ui(max_lines)

        self._bridge = _LogBridge()
        self._bridge.message.connect(self._append)   # queued from worker threads
        self._handler = _QtLogHandler(self._bridge)
        self._handler.setLevel(level)
        self._handler.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-7s %(name)s: %(message)s', datefmt='%H:%M:%S'))

    def _build_ui(self, max_lines):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        title = QLabel("📜 Log")
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("padding: 3px 14px; font-weight: normal;")
        clear_btn.clicked.connect(lambda: self.view.clear())
        header.addWidget(clear_btn)
        layout.addLayout(header)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(max_lines)   # cap memory
        self.view.setFont(QFont('Consolas', 8))
        self.view.setStyleSheet(
            "QPlainTextEdit { background:#1e1e1e; color:#dcdcdc;"
            " border:1px solid #bdc3c7; border-radius:4px; }")
        layout.addWidget(self.view)

    def install(self, logger=None):
        """Attach the handler to `logger` (the root logger by default)."""
        (logger or logging.getLogger()).addHandler(self._handler)

    def _append(self, message, levelname):
        sb = self.view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4

        color = _LEVEL_COLORS.get(levelname)
        if color:
            safe = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            self.view.appendHtml(f'<span style="color:{color};">{safe}</span>')
        else:
            self.view.appendPlainText(message)

        if at_bottom:   # keep following the tail unless the user scrolled up
            sb.setValue(sb.maximum())
