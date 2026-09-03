import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QLineEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QComboBox,
                             QProgressBar, QMessageBox, QAbstractItemView, QApplication)
from PyQt5.QtCore import Qt, QTimer

from ..workers import UserPostsWorker
from ..utils import export_table_to_csv

logger = logging.getLogger(__name__)


class KarmaTab(QWidget):
    def __init__(self, get_reddit, post_log):
        super().__init__()
        self._get_reddit = get_reddit
        self._post_log = post_log
        self._worker = None
        self._mode = None          # 'refresh' | 'sync' | 'search'
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Your Posts controls ───────────────────────────────────────
        controls = QGroupBox("⚙️ Your Posts")
        cl = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Show recent:"))
        self.num_posts_spinner = QSpinBox()
        self.num_posts_spinner.setRange(1, 100)
        self.num_posts_spinner.setValue(25)
        row1.addWidget(self.num_posts_spinner)
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        row1.addWidget(self.refresh_btn)
        self.open_log_btn = QPushButton("📂 Open Log")
        self.open_log_btn.clicked.connect(self._open_log)
        row1.addWidget(self.open_log_btn)
        self.export_btn = QPushButton("📊 Export CSV")
        self.export_btn.clicked.connect(self._export)
        row1.addWidget(self.export_btn)
        row1.addStretch()
        cl.addLayout(row1)

        row2 = QHBoxLayout()
        self.sync_btn = QPushButton("⬇️ Sync All Karma (full history)")
        self.sync_btn.setToolTip(
            "Fetch every post from your Reddit history and update its score and\n"
            "comment count in the post log. Can take a while for large histories.")
        self.sync_btn.setStyleSheet("background-color: #27ae60;")
        self.sync_btn.clicked.connect(self._sync_all)
        row2.addWidget(self.sync_btn)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        row2.addWidget(self.progress, 1)
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #7f8c8d;")
        row2.addWidget(self.progress_label)
        cl.addLayout(row2)

        controls.setLayout(cl)
        layout.addWidget(controls)

        # ── Search ────────────────────────────────────────────────────
        search = QGroupBox("🔍 Search Your Posts")
        sl = QHBoxLayout()
        sl.addWidget(QLabel("Subreddit:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g. python  (partial)")
        self.search_input.returnPressed.connect(self._search)
        sl.addWidget(self.search_input, 1)
        sl.addWidget(QLabel("Title has:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("words in the title")
        self.title_input.returnPressed.connect(self._search)
        sl.addWidget(self.title_input, 1)
        sl.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Newest", False)
        self.sort_combo.addItem("Top score", True)
        sl.addWidget(self.sort_combo)
        sl.addWidget(QLabel("Scan:"))
        self.scan_spinner = QSpinBox()
        self.scan_spinner.setRange(50, 1000)
        self.scan_spinner.setSingleStep(50)
        self.scan_spinner.setValue(200)
        self.scan_spinner.setToolTip("How many recent posts to scan through.")
        sl.addWidget(self.scan_spinner)
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self._search)
        sl.addWidget(self.search_btn)
        search.setLayout(sl)
        layout.addWidget(search)

        # ── Statistics ────────────────────────────────────────────────
        stats = QHBoxLayout()
        self.count_label = QLabel("Posts: --")
        self.total_label = QLabel("Total Score: --")
        self.avg_label = QLabel("Average: --")
        self.best_label = QLabel("Best: --")
        for lbl in (self.count_label, self.total_label, self.avg_label, self.best_label):
            lbl.setStyleSheet("font-weight: bold; padding: 4px 10px;")
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

        # ── Table ─────────────────────────────────────────────────────
        self.karma_table = QTableWidget()
        self.karma_table.setColumnCount(5)
        self.karma_table.setHorizontalHeaderLabels(
            ["Subreddit", "Title", "Score", "Comments", "Posted"])
        hdr = self.karma_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.karma_table.setAlternatingRowColors(True)
        self.karma_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.karma_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.karma_table.cellDoubleClicked.connect(self._copy_link)
        layout.addWidget(self.karma_table)

        self._note_default = "Double-click a row to copy its Reddit link to the clipboard."
        self.note = QLabel(self._note_default)
        self.note.setStyleSheet("color: #7f8c8d; font-size: 8pt;")
        layout.addWidget(self.note)

    # ------------------------------------------------------------------ actions

    def _refresh(self):
        self._start(mode='refresh', limit=self.num_posts_spinner.value(),
                    busy_text="Loading recent posts")

    def _sync_all(self):
        reply = QMessageBox.question(
            self, 'Sync All Karma',
            "Fetch your entire post history from Reddit and update the log?\n"
            "This may take a while for large accounts.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._start(mode='sync', limit=None, busy_text="Syncing full history")

    def _search(self):
        name = self.search_input.text().strip().lower().removeprefix('r/')
        title = self.title_input.text().strip()
        if not name and not title:
            QMessageBox.warning(self, 'Input Required',
                'Enter a subreddit name and/or some words from the title.')
            return
        parts = []
        if name:
            parts.append(f"r/{name}")
        if title:
            parts.append(f'title "{title}"')
        self._start(mode='search', limit=self.scan_spinner.value(),
                    subreddit_filter=name, title_filter=title,
                    sort_by_score=self.sort_combo.currentData(),
                    busy_text="Searching " + " · ".join(parts))

    def _start(self, mode, limit, subreddit_filter=None, title_filter=None,
               sort_by_score=False, busy_text=""):
        reddit = self._get_reddit()
        if not reddit:
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, 'Busy', 'Another operation is already running.')
            return

        self._mode = mode
        self._busy_text = busy_text
        self._set_busy(True, f"{busy_text}…")

        self._worker = UserPostsWorker(reddit, limit=limit,
                                       subreddit_filter=subreddit_filter,
                                       title_filter=title_filter,
                                       sort_by_score=sort_by_score)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ------------------------------------------------------------------ worker slots

    def _on_progress(self, scanned):
        self.progress_label.setText(f"{self._busy_text}… scanned {scanned}")

    def _on_finished(self, posts):
        self._set_busy(False)

        # Refresh and full-sync also write results back to the post log
        if self._mode in ('refresh', 'sync') and posts:
            self._post_log.upsert_posts(posts)

        self._display(posts)

        if self._mode == 'sync':
            QMessageBox.information(self, 'Sync Complete',
                f"Synced {len(posts)} post(s) into the log.")
        elif self._mode == 'search' and not posts:
            QMessageBox.information(self, 'No Posts Found',
                "No matching posts in the scanned range.\n"
                "Try increasing 'Scan', or check the subreddit name.")

    def _on_error(self, message):
        self._set_busy(False)
        QMessageBox.critical(self, 'Error', f'Operation failed:\n{message}')

    def _set_busy(self, busy, message=""):
        for btn in (self.refresh_btn, self.sync_btn, self.search_btn):
            btn.setEnabled(not busy)
        if busy:
            self.progress.setRange(0, 0)   # indeterminate
            self.progress.show()
            self.progress_label.setText(message)
        else:
            self.progress.hide()
            self.progress_label.setText("")

    # ------------------------------------------------------------------ table + stats

    def _display(self, posts):
        self.karma_table.setRowCount(0)
        if not posts:
            self._set_stats(0, 0, 0, '')
            return

        total = best_score = 0
        best_title = ''
        for post in posts:
            row = self.karma_table.rowCount()
            self.karma_table.insertRow(row)

            self.karma_table.setItem(row, 0, QTableWidgetItem(f"r/{post['subreddit']}"))
            title_item = QTableWidgetItem(post['title'])
            title_item.setData(Qt.UserRole, post.get('permalink', ''))
            self.karma_table.setItem(row, 1, title_item)
            self._num_cell(row, 2, post['score'])
            self._num_cell(row, 3, post['comments'])
            posted = post['created'].strftime("%Y-%m-%d %H:%M") if post.get('created') else ''
            self.karma_table.setItem(row, 4, QTableWidgetItem(posted))

            total += post['score']
            if post['score'] >= best_score:
                best_score = post['score']
                best_title = post['title']

        avg = total / len(posts)
        self._set_stats(len(posts), total, avg, f"{best_title[:40]} ({best_score:,})")
        logger.info("Displayed %d posts in karma table", len(posts))

    def _num_cell(self, row, col, value):
        item = QTableWidgetItem(f"{value:,}")
        item.setTextAlignment(Qt.AlignCenter)
        self.karma_table.setItem(row, col, item)

    def _set_stats(self, count, total, avg, best):
        self.count_label.setText(f"Posts: {count:,}")
        self.total_label.setText(f"Total Score: {total:,}")
        self.avg_label.setText(f"Average: {avg:.1f}")
        self.best_label.setText(f"Best: {best}" if best else "Best: --")

    def _copy_link(self, row, _col):
        item = self.karma_table.item(row, 1)
        url = item.data(Qt.UserRole) if item else ''
        if not url:
            return
        QApplication.clipboard().setText(url)
        self.note.setText(f"📋 Link copied to clipboard:  {url}")
        self.note.setStyleSheet("color: #27ae60; font-size: 8pt; font-weight: bold;")
        QTimer.singleShot(2000, self._reset_note)

    def _reset_note(self):
        self.note.setText(self._note_default)
        self.note.setStyleSheet("color: #7f8c8d; font-size: 8pt;")

    # ------------------------------------------------------------------ misc

    def _open_log(self):
        if not self._post_log.open_file():
            QMessageBox.warning(self, 'File Not Found',
                'The post log is empty. Post something or run "Sync All Karma" first.')

    def _export(self):
        if self.karma_table.rowCount() == 0:
            QMessageBox.warning(self, 'No Data', 'Nothing to export — refresh or search first.')
            return
        export_table_to_csv(self, self.karma_table, "Export Karma", "karma_stats")

    def stop_workers_on_close(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
