import logging
import os
import re
import tempfile
import webbrowser
from datetime import datetime, timezone

import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QSpinBox, QCheckBox, QMessageBox, QAbstractItemView,
    QApplication, QDialog, QSizePolicy, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = 72
_ACTION_BTN_SIZE = 28   # px — copy / play buttons

FIELD_OPTIONS = [
    ("Any field",  ""),
    ("Title",      "title:"),
    ("URL",        "url:"),
    ("Author",     "author:"),
    ("Site",       "site:"),
    ("Flair",      "flair:"),
    ("Selftext",   "selftext:"),
    ("Subreddit",  "subreddit:"),
]

SORT_OPTIONS = [("Relevance", "relevance"), ("New", "new"), ("Hot", "hot"),
                ("Top", "top"), ("Comments", "comments")]
TIME_OPTIONS = [("All time", "all"), ("Past year", "year"), ("Past month", "month"),
                ("Past week", "week"), ("Past day", "day"), ("Past hour", "hour")]


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _SearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, reddit, subreddit, query, sort, time_filter, limit, nsfw_only):
        super().__init__()
        self.reddit      = reddit
        self.subreddit   = subreddit or 'all'
        self.query       = query
        self.sort        = sort
        self.time_filter = time_filter
        self.limit       = limit
        self.nsfw_only   = nsfw_only

    def run(self):
        try:
            q = self.query.strip()
            if self.nsfw_only and 'nsfw:' not in q.lower():
                q = (q + ' nsfw:yes').strip()

            sub = self.reddit.subreddit(self.subreddit)
            submissions = sub.search(q, syntax='lucene', sort=self.sort,
                                     time_filter=self.time_filter, limit=self.limit)
            results = []
            for s in submissions:
                results.append({
                    'id':          s.id,
                    'title':       s.title,
                    'url':         s.url,
                    'permalink':   f"https://reddit.com{s.permalink}",
                    'subreddit':   s.subreddit.display_name,
                    'author':      str(s.author) if s.author else '[deleted]',
                    'score':       s.score,
                    'comments':    s.num_comments,
                    'created_utc': s.created_utc,
                    'flair':       s.link_flair_text or '',
                    'thumbnail':   s.thumbnail,
                    'over_18':     s.over_18,
                })
            logger.info(f"Search returned {len(results)} results")
            self.results_ready.emit(results)
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            self.error.emit(str(e))


class _ThumbnailLoader(QThread):
    """Downloads thumbnails sequentially off the main thread."""
    thumbnail_ready = pyqtSignal(int, QPixmap)   # (row, pixmap)
    _NON_URL = {'self', 'default', 'image', 'spoiler', 'nsfw', ''}

    def __init__(self, items):   # items: list of (row, url)
        super().__init__()
        self.items      = items
        self.is_running = True

    def run(self):
        for row, url in self.items:
            if not self.is_running:
                break
            if not url or url in self._NON_URL:
                continue
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    px = QPixmap()
                    px.loadFromData(resp.content)
                    if not px.isNull():
                        px = px.scaled(THUMBNAIL_SIZE, THUMBNAIL_SIZE,
                                       Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.thumbnail_ready.emit(row, px)
            except Exception:
                pass

    def stop(self):
        self.is_running = False


# ---------------------------------------------------------------------------
# Per-row action widget  (copy URL  +  optional play button for Redgifs)
# ---------------------------------------------------------------------------

def _action_widget(post_url: str) -> QWidget:
    """Small widget with a 📋 copy button."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(6, 0, 6, 0)
    lay.setSpacing(6)
    w.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    # Copy URL button
    copy_btn = QPushButton("📋")
    copy_btn.setFixedSize(_ACTION_BTN_SIZE, _ACTION_BTN_SIZE)
    copy_btn.setToolTip(f"Copy link URL:\\n{post_url}")
    copy_btn.setStyleSheet(_COPY_STYLE)
    copy_btn.clicked.connect(lambda: _copy_to_clipboard(post_url, copy_btn))
    lay.addWidget(copy_btn)

    return w

_COPY_STYLE  = "font-size: 13pt; padding: 0; border-radius: 4px; background: #ecf0f1; border: 1px solid #bdc3c7;"
_CHECK_STYLE = "font-size: 13pt; padding: 0; border-radius: 4px; background: #d5f5e3; border: 1px solid #27ae60; color: #1e8449;"


def _copy_to_clipboard(url: str, btn: QPushButton):
    from PyQt5.QtCore import QTimer
    QApplication.clipboard().setText(url)
    btn.setText("✓")
    btn.setStyleSheet(_CHECK_STYLE)
    QTimer.singleShot(1500, lambda: (btn.setText("📋"), btn.setStyleSheet(_COPY_STYLE)))


# ---------------------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------------------

class SearchTab(QWidget):
    """Reddit search with Lucene field operators, thumbnail results,
    per-row copy and Redgifs player, and one-click load to the Import tab."""

    load_requested = pyqtSignal(list)

    def __init__(self, get_reddit):
        super().__init__()
        self._get_reddit    = get_reddit
        self._search_worker = None
        self._thumb_loader  = None
        self._results       = []
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Query builder ─────────────────────────────────────────────
        qgroup = QGroupBox("🔍 Query Builder")
        qlayout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Field:"))
        self.field_combo = QComboBox()
        self.field_combo.setMinimumWidth(110)
        for label, _ in FIELD_OPTIONS:
            self.field_combo.addItem(label)
        row1.addWidget(self.field_combo)

        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("Search term (Enter or + Add to append to query)")
        self.term_input.returnPressed.connect(self._append_token)
        row1.addWidget(self.term_input, 1)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedWidth(64)
        add_btn.clicked.connect(self._append_token)
        row1.addWidget(add_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(64)
        clear_btn.clicked.connect(lambda: self.query_input.clear())
        row1.addWidget(clear_btn)
        qlayout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Query:"))
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText(
            'e.g.  title:python url:github.com   OR   title:"machine learning"')
        self.query_input.returnPressed.connect(self._run_search)
        row2.addWidget(self.query_input, 1)
        qlayout.addLayout(row2)

        qgroup.setLayout(qlayout)
        layout.addWidget(qgroup)

        # ── Options ───────────────────────────────────────────────────
        ogroup = QGroupBox("⚙️ Options")
        olayout = QHBoxLayout()

        olayout.addWidget(QLabel("Subreddit:"))
        self.subreddit_input = QLineEdit("all")
        self.subreddit_input.setMaximumWidth(120)
        olayout.addWidget(self.subreddit_input)

        olayout.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        for label, val in SORT_OPTIONS:
            self.sort_combo.addItem(label, val)
        olayout.addWidget(self.sort_combo)

        olayout.addWidget(QLabel("Time:"))
        self.time_combo = QComboBox()
        for label, val in TIME_OPTIONS:
            self.time_combo.addItem(label, val)
        olayout.addWidget(self.time_combo)

        olayout.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(5, 100)
        self.limit_spin.setValue(25)
        olayout.addWidget(self.limit_spin)

        self.nsfw_check = QCheckBox("NSFW only")
        self.nsfw_check.setToolTip(
            "Appends nsfw:yes to show only NSFW-tagged posts.\n"
            "Leave unchecked to see all results (account preferences apply)."
        )
        olayout.addWidget(self.nsfw_check)

        olayout.addStretch()

        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.setMinimumHeight(36)
        self.search_btn.setMinimumWidth(110)
        self.search_btn.clicked.connect(self._run_search)
        olayout.addWidget(self.search_btn)

        ogroup.setLayout(olayout)
        layout.addWidget(ogroup)

        # ── Results header ────────────────────────────────────────────
        rheader = QHBoxLayout()
        self.results_label = QLabel("No search yet")
        self.results_label.setStyleSheet("font-weight: bold;")
        rheader.addWidget(self.results_label)
        rheader.addStretch()
        self.load_btn = QPushButton("📥 Load Selected to Import Tab")
        self.load_btn.setToolTip(
            "Load selected rows into the Posts spreadsheet.\n"
            "Nothing selected = load all results."
        )
        self.load_btn.clicked.connect(self._load_selected)
        self.load_btn.setEnabled(False)
        rheader.addWidget(self.load_btn)
        layout.addLayout(rheader)

        # ── Results table ─────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["", "Title", "Subreddit", "Author", "Score", "Comments", "Posted", "Actions"]
        )
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)            # thumbnail
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)           # title
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # subreddit
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # author
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # score
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # comments
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # posted
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)             # actions
        self.table.setColumnWidth(0, THUMBNAIL_SIZE + 8)
        self.table.setColumnWidth(7, _ACTION_BTN_SIZE * 2 + 20)    # room for 2 buttons
        self.table.verticalHeader().setDefaultSectionSize(THUMBNAIL_SIZE + 8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._open_post)
        layout.addWidget(self.table)

        note = QLabel(
            "Double-click a row to open on Reddit  ·  "
            "📋 copies the link URL"
        )
        note.setStyleSheet("color: #7f8c8d; font-size: 8pt;")
        layout.addWidget(note)

    # ------------------------------------------------------------------ query builder

    def _append_token(self):
        term = self.term_input.text().strip()
        if not term:
            return
        _, prefix = FIELD_OPTIONS[self.field_combo.currentIndex()]
        token = f'{prefix}"{term}"' if ' ' in term else f'{prefix}{term}'
        current = self.query_input.text().strip()
        self.query_input.setText((current + ' ' + token).strip())
        self.term_input.clear()
        self.term_input.setFocus()

    # ------------------------------------------------------------------ search

    def _run_search(self):
        reddit = self._get_reddit()
        if not reddit:
            return
        query = self.query_input.text().strip()
        if not query:
            QMessageBox.warning(self, 'Empty Query', 'Please enter a search query.')
            return

        self._stop_workers()
        self.search_btn.setEnabled(False)
        self.search_btn.setText("⏳ Searching…")
        self.table.setRowCount(0)
        self._results = []
        self.load_btn.setEnabled(False)
        self.results_label.setText("Searching…")

        self._search_worker = _SearchWorker(
            reddit      = reddit,
            subreddit   = self.subreddit_input.text().strip() or 'all',
            query       = query,
            sort        = self.sort_combo.currentData(),
            time_filter = self.time_combo.currentData(),
            limit       = self.limit_spin.value(),
            nsfw_only   = self.nsfw_check.isChecked(),
        )
        self._search_worker.results_ready.connect(self._on_results)
        self._search_worker.error.connect(self._on_error)
        self._search_worker.start()

    def _on_results(self, results):
        self._results = results
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 Search")
        n = len(results)
        self.results_label.setText(f"{n} result{'s' if n != 1 else ''}")
        self.load_btn.setEnabled(bool(results))

        self.table.setRowCount(n)
        thumb_queue = []

        for row, post in enumerate(results):
            url     = post['url']

            # Col 0 — thumbnail
            thumb_lbl = _thumb_placeholder(post['thumbnail'], post['over_18'])
            self.table.setCellWidget(row, 0, thumb_lbl)
            if thumb_lbl.text() == '…':
                thumb_queue.append((row, post['thumbnail']))

            # Col 1 — title
            title  = ('[NSFW] ' if post['over_18'] else '') + post['title']
            t_item = QTableWidgetItem(title)
            t_item.setData(Qt.UserRole, post['permalink'])
            if post['over_18']:
                t_item.setForeground(QColor('#c0392b'))
            self.table.setItem(row, 1, t_item)

            # Col 2, 3 — subreddit, author
            self.table.setItem(row, 2, QTableWidgetItem(f"r/{post['subreddit']}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"u/{post['author']}"))

            # Col 4, 5 — score, comments
            score_item = QTableWidgetItem(f"▲ {post['score']:,}")
            score_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, score_item)

            cmts_item = QTableWidgetItem(f"💬 {post['comments']:,}")
            cmts_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 5, cmts_item)

            # Col 6 — relative posted time
            posted_item = QTableWidgetItem(_relative_time(post['created_utc']))
            posted_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, posted_item)

            # Col 7 — copy button
            self.table.setCellWidget(row, 7, _action_widget(url))

        if thumb_queue:
            self._thumb_loader = _ThumbnailLoader(thumb_queue)
            self._thumb_loader.thumbnail_ready.connect(self._apply_thumbnail)
            self._thumb_loader.start()

    def _apply_thumbnail(self, row, pixmap):
        lbl = self.table.cellWidget(row, 0)
        if isinstance(lbl, QLabel):
            lbl.setPixmap(pixmap)
            lbl.setText("")
            lbl.setStyleSheet("background: transparent;")

    def _on_error(self, msg):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 Search")
        self.results_label.setText("Search failed")
        QMessageBox.critical(self, 'Search Failed', f'Search error:\n{msg}')

    # ------------------------------------------------------------------ row actions

    def _open_post(self, row, _col):
        item = self.table.item(row, 1)
        if item:
            url = item.data(Qt.UserRole)
            if url:
                webbrowser.open(url)

    def _load_selected(self):
        sel_rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        posts = [self._results[r] for r in (sel_rows or range(len(self._results)))
                 if r < len(self._results)]
        if not posts:
            return
        self.load_requested.emit(posts)
        QMessageBox.information(
            self, 'Loaded',
            f'Loaded {len(posts)} post{"s" if len(posts) != 1 else ""} into the Posts tab.\n'
            'Switch to the Posts tab to review before submitting.'
        )

    # ------------------------------------------------------------------ cleanup

    def _stop_workers(self):
        if self._thumb_loader and self._thumb_loader.isRunning():
            self._thumb_loader.stop()
            self._thumb_loader.wait(2000)
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.wait(2000)
            if self._search_worker.isRunning():
                self._search_worker.terminate()

    def stop_workers_on_close(self):
        self._stop_workers()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _thumb_placeholder(thumbnail_url: str, over_18: bool) -> QLabel:
    lbl = QLabel()
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)

    if over_18 and thumbnail_url == 'nsfw':
        lbl.setText("NSFW")
        lbl.setStyleSheet("background:#c0392b; color:white; font-weight:bold; font-size:9pt;")
    elif thumbnail_url == 'self':
        lbl.setText("📝")
        lbl.setStyleSheet("background:#ecf0f1; font-size:22pt;")
    elif thumbnail_url in ('default', '', 'image'):
        lbl.setText("🔗")
        lbl.setStyleSheet("background:#ecf0f1; font-size:22pt;")
    elif thumbnail_url == 'spoiler':
        lbl.setText("🚫")
        lbl.setStyleSheet("background:#ecf0f1; font-size:22pt;")
    else:
        lbl.setText("…")
        lbl.setStyleSheet("background:#ecf0f1; color:#95a5a6;")
    return lbl


def _relative_time(created_utc: float) -> str:
    diff = int(datetime.now(timezone.utc).timestamp() - created_utc)
    if diff < 60:        return "just now"
    if diff < 3600:      return f"{diff // 60}m ago"
    if diff < 86400:     return f"{diff // 3600}h ago"
    if diff < 86400*30:  return f"{diff // 86400}d ago"
    if diff < 86400*365: return f"{diff // (86400*30)}mo ago"
    return f"{diff // (86400*365)}y ago"
