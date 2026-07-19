import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QTextEdit, QProgressBar,
                             QSpinBox, QMessageBox)
from PyQt5.QtCore import pyqtSignal

from ..workers import RedditWorker

logger = logging.getLogger(__name__)


class SubmitTab(QWidget):
    submission_finished = pyqtSignal(dict)

    def __init__(self, get_reddit, post_log, favorites_manager, get_posts):
        super().__init__()
        self._get_reddit = get_reddit
        self._post_log = post_log
        self._favorites = favorites_manager
        self._get_posts = get_posts   # callable → list of post dicts from ImportTab
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        progress_group = QGroupBox("⏳ Progress")
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(30)
        self.progress_bar.setTextVisible(True)
        self.progress_label = QLabel("Ready to submit")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        delay_group = QGroupBox("⏱️ Rate Limiting")
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay between posts:"))
        self.delay_spinner = QSpinBox()
        self.delay_spinner.setMinimum(10)
        self.delay_spinner.setMaximum(3600)
        self.delay_spinner.setValue(30)
        self.delay_spinner.setSuffix(" seconds")
        self.delay_spinner.setMinimumWidth(130)
        delay_layout.addWidget(self.delay_spinner)
        delay_layout.addWidget(QLabel("  (Reddit enforces ~10 min between link posts for new accounts)"))
        delay_layout.addStretch()
        delay_group.setLayout(delay_layout)
        layout.addWidget(delay_group)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.start_btn = QPushButton("🚀 Start Batch Submission")
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setMinimumHeight(50)
        self.stop_btn = QPushButton("⏹️ Stop Submission")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setProperty("class", "danger")
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        layout.addLayout(button_layout)

        log_group = QGroupBox("📝 Submission Log")
        log_layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(250)
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        layout.addStretch()

    # ------------------------------------------------------------------ slots

    def _start(self):
        reddit = self._get_reddit()
        if not reddit:
            return

        posts = self._get_posts()
        if not posts:
            QMessageBox.warning(self, 'No Posts',
                'No valid posts found.\n\nFill in at least subreddit, title, and URL in the Import tab.')
            return

        reply = QMessageBox.question(
            self, 'Confirm Batch Submission',
            f'You are about to submit {len(posts)} posts to Reddit.\n\n'
            'This operation cannot be undone. Continue?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setMaximum(len(posts))
        self.progress_bar.setValue(0)
        self.log_view.clear()

        self._worker = RedditWorker(reddit, posts, delay_secs=self.delay_spinner.value())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()
        logger.info(f"Batch submission started: {len(posts)} posts")

    def _stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()
            self.log_view.append("\n⏹️ Submission stopped by user\n")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            logger.info("Batch submission stopped by user")

    def _on_progress(self, count, message):
        self.progress_bar.setValue(count)
        self.progress_label.setText(f"Processing: {count}/{self.progress_bar.maximum()}")
        self.log_view.append(message)
        cursor = self.log_view.textCursor()
        cursor.movePosition(cursor.End)
        self.log_view.setTextCursor(cursor)

    def _on_finished(self, results):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Log successful posts and update favorites usage
        for item in results['successful']:
            self._post_log.log_post({
                'id': item.get('id', ''),
                'subreddit': item.get('subreddit', ''),
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'permalink': item.get('permalink', ''),
                'score': 1,
                'comments': 0,
            })

        posted_subs = {item['subreddit'].lower() for item in results['successful']}
        self._favorites.increment_usage(posted_subs)

        logger.info(f"Submission done: {len(results['successful'])} ok, {len(results['failed'])} failed")
        self.submission_finished.emit(results)

    def _on_error(self, error_msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, 'Submission Error', f'An error occurred:\n{error_msg}')

    def stop_worker_on_close(self):
        """Call from closeEvent to clean up the worker thread."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
