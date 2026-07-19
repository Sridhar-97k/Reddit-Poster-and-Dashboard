import logging
from datetime import datetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QLineEdit, QPushButton, QTableWidget,
                             QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox)
from PyQt5.QtCore import Qt

from ..workers import KarmaWorker, BulkKarmaUpdateWorker
from ..utils import export_table_to_excel

logger = logging.getLogger(__name__)

KARMA_COL_WIDTHS = {'A': 20, 'B': 60, 'C': 12, 'D': 12, 'E': 20, 'F': 60}


class KarmaTab(QWidget):
    def __init__(self, get_reddit, post_log):
        super().__init__()
        self._get_reddit = get_reddit
        self._post_log = post_log
        self._karma_worker = None
        self._bulk_worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        log_group = QGroupBox("📋 Post Log File")
        log_layout = QVBoxLayout()
        log_info = QLabel(
            "All your posts are automatically logged to an Excel file.\n"
            "Update karma to see current scores for all logged posts!"
        )
        log_info.setWordWrap(True)
        log_layout.addWidget(log_info)
        log_buttons = QHBoxLayout()
        open_log_btn = QPushButton("📂 Open Post Log File")
        open_log_btn.clicked.connect(self._open_log)
        open_log_btn.setMinimumHeight(40)
        self.update_log_btn = QPushButton("🔄 Update All Karma in Log")
        self.update_log_btn.clicked.connect(self._bulk_update_karma)
        self.update_log_btn.setMinimumHeight(40)
        self.update_log_btn.setStyleSheet("background-color: #27ae60;")
        log_buttons.addWidget(open_log_btn)
        log_buttons.addWidget(self.update_log_btn)
        log_layout.addLayout(log_buttons)
        self.log_stats_label = QLabel(f"Log file: {self._post_log.filepath}")
        self.log_stats_label.setStyleSheet("font-style: italic; color: #7f8c8d;")
        log_layout.addWidget(self.log_stats_label)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        control_group = QGroupBox("⚙️ Quick View Settings")
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Number of recent posts:"))
        self.num_posts_spinner = QSpinBox()
        self.num_posts_spinner.setMinimum(1)
        self.num_posts_spinner.setMaximum(100)
        self.num_posts_spinner.setValue(20)
        self.num_posts_spinner.setMinimumWidth(100)
        control_layout.addWidget(self.num_posts_spinner)
        self.refresh_btn = QPushButton("🔄 Refresh Stats")
        self.refresh_btn.clicked.connect(self._refresh_karma)
        self.refresh_btn.setMinimumHeight(35)
        control_layout.addWidget(self.refresh_btn)
        export_btn = QPushButton("📊 Export View to Excel")
        export_btn.clicked.connect(self._export_karma)
        export_btn.setMinimumHeight(35)
        control_layout.addWidget(export_btn)
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        search_group = QGroupBox("🔍 Search Posts by Subreddit")
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Subreddit:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter subreddit name (e.g., python)")
        search_layout.addWidget(self.search_input)
        self.search_limit = QSpinBox()
        self.search_limit.setMinimum(1)
        self.search_limit.setMaximum(100)
        self.search_limit.setValue(25)
        self.search_limit.setPrefix("Limit: ")
        search_layout.addWidget(self.search_limit)
        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self._search_by_subreddit)
        search_btn.setMinimumHeight(35)
        search_layout.addWidget(search_btn)
        export_search_btn = QPushButton("📊 Export Results")
        export_search_btn.clicked.connect(self._export_search)
        export_search_btn.setMinimumHeight(35)
        search_layout.addWidget(export_search_btn)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        stats_group = QGroupBox("📈 Quick Statistics")
        stats_layout = QHBoxLayout()
        self.total_label = QLabel("Total Score: --")
        self.avg_label = QLabel("Average Score: --")
        self.best_label = QLabel("Best Post: --")
        for lbl in (self.total_label, self.avg_label, self.best_label):
            lbl.setStyleSheet("font-size: 11pt; font-weight: bold; padding: 10px;")
            stats_layout.addWidget(lbl)
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        self.karma_table = QTableWidget()
        self.karma_table.setColumnCount(6)
        self.karma_table.setHorizontalHeaderLabels(
            ["Subreddit", "Title", "Score", "Comments", "Posted", "URL"]
        )
        self.karma_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.karma_table.setAlternatingRowColors(True)
        layout.addWidget(self.karma_table)

    # ------------------------------------------------------------------ karma

    def _refresh_karma(self):
        reddit = self._get_reddit()
        if not reddit:
            return
        if self._karma_worker and self._karma_worker.isRunning():
            self._karma_worker.wait()

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("⏳ Loading...")
        num = self.num_posts_spinner.value()

        self._karma_worker = KarmaWorker(reddit, num)
        self._karma_worker.finished.connect(self._display_karma)
        self._karma_worker.error.connect(self._on_karma_error)
        self._karma_worker.start()

    def _display_karma(self, posts):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh Stats")

        for post in posts:
            self._post_log.update_karma(post['id'], post['score'], post['comments'])

        self.karma_table.setRowCount(0)
        if not posts:
            QMessageBox.information(self, 'No Posts', 'No posts found.')
            return

        total = 0
        best_score = 0
        best_title = ''
        for post in posts:
            row = self.karma_table.rowCount()
            self.karma_table.insertRow(row)
            self.karma_table.setItem(row, 0, QTableWidgetItem(post['subreddit']))
            self.karma_table.setItem(row, 1, QTableWidgetItem(post['title']))
            score_item = QTableWidgetItem(str(post['score']))
            score_item.setTextAlignment(Qt.AlignCenter)
            self.karma_table.setItem(row, 2, score_item)
            comments_item = QTableWidgetItem(str(post['comments']))
            comments_item.setTextAlignment(Qt.AlignCenter)
            self.karma_table.setItem(row, 3, comments_item)
            self.karma_table.setItem(row, 4, QTableWidgetItem(post['created'].strftime("%Y-%m-%d %H:%M")))
            self.karma_table.setItem(row, 5, QTableWidgetItem(post['url']))
            total += post['score']
            if post['score'] > best_score:
                best_score = post['score']
                best_title = post['title'][:40] + "..."

        avg = total / len(posts)
        self.total_label.setText(f"Total Score: {total:,}")
        self.avg_label.setText(f"Average Score: {avg:.1f}")
        self.best_label.setText(f"Best Post: {best_title} ({best_score:,})")
        logger.info(f"Displayed {len(posts)} posts in karma table")

    def _on_karma_error(self, error_msg):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("🔄 Refresh Stats")
        QMessageBox.critical(self, 'Error', f'Failed to fetch karma stats:\n{error_msg}')

    # ------------------------------------------------------------------ search

    def _search_by_subreddit(self):
        reddit = self._get_reddit()
        if not reddit:
            return
        name = self.search_input.text().strip().lower().removeprefix('r/')
        if not name:
            QMessageBox.warning(self, 'Input Required', 'Please enter a subreddit name')
            return
        limit = self.search_limit.value()
        try:
            user = reddit.user.me()
            posts = []
            for submission in user.submissions.new(limit=200):
                if submission.subreddit.display_name.lower() == name:
                    posts.append({
                        'subreddit': submission.subreddit.display_name,
                        'title': submission.title,
                        'score': submission.score,
                        'comments': submission.num_comments,
                        'created': datetime.fromtimestamp(submission.created_utc),
                        'url': f"https://reddit.com{submission.permalink}",
                        'id': submission.id,
                    })
                    if len(posts) >= limit:
                        break
            if not posts:
                QMessageBox.information(self, 'No Posts Found',
                    f'No posts found in r/{name}\n\n'
                    '• Check the subreddit name\n'
                    '• You must have posted there\n'
                    '• Searches last 200 posts')
                return
            self._display_karma(posts)
            QMessageBox.information(self, 'Search Complete',
                f'Found {len(posts)} posts in r/{name}!')
        except Exception as e:
            QMessageBox.critical(self, 'Search Failed', f'Failed to search posts:\n{str(e)}')

    # ------------------------------------------------------------------ bulk karma update

    def _bulk_update_karma(self):
        reddit = self._get_reddit()
        if not reddit:
            return
        if self._bulk_worker and self._bulk_worker.isRunning():
            QMessageBox.information(self, 'Already Running', 'Karma update is already in progress.')
            return

        self.update_log_btn.setEnabled(False)
        self.update_log_btn.setText("⏳ Updating...")

        self._bulk_worker = BulkKarmaUpdateWorker(reddit, self._post_log.filepath)
        self._bulk_worker.progress.connect(self._on_bulk_progress)
        self._bulk_worker.finished.connect(self._on_bulk_finished)
        self._bulk_worker.error.connect(self._on_bulk_error)
        self._bulk_worker.start()

    def _on_bulk_progress(self, updated, failed):
        logger.debug(f"Bulk karma update: {updated} updated, {failed} failed")

    def _on_bulk_finished(self, updated, failed):
        self.update_log_btn.setEnabled(True)
        self.update_log_btn.setText("🔄 Update All Karma in Log")
        logger.info(f"Bulk karma update done: {updated} updated, {failed} failed")
        QMessageBox.information(self, 'Karma Update Complete',
            f'Updated karma for all logged posts!\n\n'
            f'✅ Updated: {updated}\n❌ Failed: {failed}\n\n'
            f'Open {self._post_log.filepath} to see results.')

    def _on_bulk_error(self, error_msg):
        self.update_log_btn.setEnabled(True)
        self.update_log_btn.setText("🔄 Update All Karma in Log")
        QMessageBox.critical(self, 'Error', f'Failed to update karma:\n{error_msg}')

    # ------------------------------------------------------------------ misc

    def _open_log(self):
        if not self._post_log.open_file():
            QMessageBox.warning(self, 'File Not Found', 'Post log file does not exist yet.')

    def _export_karma(self):
        if self.karma_table.rowCount() == 0:
            QMessageBox.warning(self, 'No Data', 'No karma data to export. Please refresh stats first.')
            return
        export_table_to_excel(self, self.karma_table, "Karma Stats", "Save Karma Stats",
                              "karma_stats", KARMA_COL_WIDTHS)

    def _export_search(self):
        if self.karma_table.rowCount() == 0:
            QMessageBox.warning(self, 'No Data', 'No results to export. Search for posts first!')
            return
        export_table_to_excel(self, self.karma_table, "Search Results", "Export Search Results",
                              "search_results", KARMA_COL_WIDTHS)

    def stop_workers_on_close(self):
        for worker in (self._karma_worker, self._bulk_worker):
            if worker and worker.isRunning():
                worker.wait(3000)
                if worker.isRunning():
                    worker.terminate()
