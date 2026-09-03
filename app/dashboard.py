import os
import logging

import praw
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTabWidget,
                             QStatusBar, QMessageBox, QSplitter)
from PyQt5.QtCore import Qt

from . import DATA_DIR
from .post_log import PostLog
from .favorites import FavoritesManager
from .flair_store import FlairStore
from .log_console import LogConsole
from .tabs.config_tab import ConfigTab
from .tabs.subreddits_tab import SubredditsTab
from .tabs.search_tab import SearchTab
from .tabs.import_tab import ImportTab
from .tabs.submit_tab import SubmitTab
from .tabs.karma_tab import KarmaTab
from .tabs.results_tab import ResultsTab

logger = logging.getLogger(__name__)

STYLESHEET = """
    QMainWindow { background-color: #f0f0f0; }
    QWidget { background-color: #ffffff; color: #2c3e50;
              font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; }
    QTabWidget::pane { border: 1px solid #bdc3c7; background-color: #ffffff; border-radius: 4px; }
    QTabBar::tab { background-color: #ecf0f1; color: #2c3e50; padding: 12px 24px;
                   margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px;
                   font-weight: 500; }
    QTabBar::tab:selected { background-color: #3498db; color: #ffffff; }
    QTabBar::tab:hover:!selected { background-color: #d5dbdb; }
    QLineEdit, QTextEdit, QSpinBox { background-color: #ffffff; border: 2px solid #bdc3c7;
                                      padding: 8px; border-radius: 4px; color: #2c3e50; }
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 2px solid #3498db; }
    QPushButton { background-color: #3498db; color: #ffffff; border: none;
                  padding: 10px 20px; border-radius: 4px; font-weight: bold; font-size: 9pt; }
    QPushButton:hover { background-color: #2980b9; }
    QPushButton:pressed { background-color: #21618c; }
    QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
    QPushButton.danger { background-color: #e74c3c; }
    QPushButton.danger:hover { background-color: #c0392b; }
    QTableWidget { background-color: #ffffff; alternate-background-color: #f8f9fa;
                   border: 1px solid #bdc3c7; gridline-color: #ecf0f1; }
    QTableWidget::item { padding: 8px; }
    QTableWidget::item:selected { background-color: #3498db; color: #ffffff; }
    QHeaderView::section { background-color: #34495e; color: #ffffff; padding: 10px;
                           border: none; font-weight: bold; }
    QGroupBox { border: 2px solid #bdc3c7; border-radius: 6px; margin-top: 12px;
                padding-top: 12px; font-weight: bold; color: #2c3e50; }
    QGroupBox::title { color: #3498db; subcontrol-origin: margin; left: 15px;
                       padding: 0 8px; background-color: #ffffff; }
    QProgressBar { border: 2px solid #bdc3c7; border-radius: 5px; text-align: center;
                   background-color: #ecf0f1; }
    QProgressBar::chunk { background-color: #3498db; border-radius: 3px; }
    QStatusBar { background-color: #34495e; color: #ffffff; }
    QCheckBox { spacing: 8px; }
    QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #bdc3c7;
                           border-radius: 3px; background-color: #ffffff; }
    QCheckBox::indicator:checked { background-color: #3498db; border-color: #3498db; }
"""


class RedditDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("=== Reddit Dashboard Starting ===")

        self._post_log = PostLog(filepath=os.path.join(DATA_DIR, 'reddit_posts_log.csv'))
        self._post_log.initialize()
        self._favorites = FavoritesManager(filepath=os.path.join(DATA_DIR, 'subreddit_favorites.json'))
        self._favorites.load()
        self._flair_store = FlairStore(filepath=os.path.join(DATA_DIR, 'subreddit_flairs.csv'))
        self._flair_store.initialize()
        self._flair_store.load()

        self._reddit = None
        self._reddit_creds = None

        self._build_ui()
        logger.info("=== Reddit Dashboard Initialized ===")

    def _build_ui(self):
        self.setWindowTitle('Reddit Dashboard')
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._tabs = QTabWidget()

        config_file = os.path.join(DATA_DIR, 'reddit_config.json')
        self._config_tab     = ConfigTab(config_file=config_file)
        self._subreddits_tab = SubredditsTab(self._favorites, self._get_reddit)
        self._search_tab     = SearchTab(self._get_reddit)
        self._import_tab     = ImportTab(self._get_reddit, self._flair_store, self._favorites)
        self._submit_tab     = SubmitTab(self._get_reddit, self._post_log,
                                         self._import_tab.get_posts)
        self._karma_tab      = KarmaTab(self._get_reddit, self._post_log)
        self._results_tab    = ResultsTab()

        self._tabs.addTab(self._config_tab,     "⚙️ Configuration")
        self._tabs.addTab(self._subreddits_tab, "⭐ Subreddits")
        self._tabs.addTab(self._search_tab,     "🔍 Search")
        self._tabs.addTab(self._import_tab,     "📂 Posts")
        self._tabs.addTab(self._submit_tab,     "🚀 Batch Submit")
        self._tabs.addTab(self._karma_tab,      "📊 Karma Stats")
        self._tabs.addTab(self._results_tab,    "✅ Results")

        self._config_tab.credentials_saved.connect(self._on_credentials_saved)
        self._config_tab.test_requested.connect(self._test_connection)
        self._submit_tab.submission_finished.connect(self._on_submission_finished)

        # Permanent log console below the tabs (shows logging output in-app —
        # handy for the packaged .exe, which has no terminal).
        self._log_console = LogConsole(level=logging.INFO)
        self._log_console.install()   # attach to the root logger

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._tabs)
        splitter.addWidget(self._log_console)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setCollapsible(0, False)
        splitter.setSizes([720, 160])
        layout.addWidget(splitter)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage('Ready - Load an Excel file to begin')

    def _get_reddit(self):
        creds = self._config_tab.credentials
        missing = [k for k, v in creds.items() if not v]
        if missing:
            QMessageBox.warning(self, 'Missing Information',
                                f"Please fill in: {', '.join(missing)}")
            return None

        current = (creds['client_id'], creds['client_secret'], creds['username'], creds['password'])
        if self._reddit is not None and self._reddit_creds == current:
            return self._reddit

        try:
            logger.info("Creating PRAW Reddit instance...")
            self._reddit = praw.Reddit(
                client_id=creds['client_id'],
                client_secret=creds['client_secret'],
                username=creds['username'],
                password=creds['password'],
                user_agent=f"RedditDashboard/2.0 by {creds['username']}"
            )
            self._reddit_creds = current
            logger.info("PRAW Reddit instance created")
            return self._reddit
        except Exception as e:
            msg = str(e)
            logger.error(f"Failed to init Reddit: {msg}", exc_info=True)
            if 'invalid_grant' in msg.lower():
                QMessageBox.critical(self, 'Authentication Failed',
                    'Invalid username or password.\n\n'
                    '• Username is case-sensitive\n'
                    '• Two-factor authentication must be disabled')
            elif '401' in msg or 'unauthorized' in msg.lower():
                QMessageBox.critical(self, 'Authorization Failed',
                    'Invalid Client ID or Client Secret.\n\n'
                    '• Check both values\n• App type must be "script"')
            else:
                QMessageBox.critical(self, 'Connection Error',
                    f'Failed to connect to Reddit:\n\n{msg}')
            return None

    def _on_credentials_saved(self):
        self._reddit = None
        self._reddit_creds = None
        self._status_bar.showMessage('✅ Configuration saved', 3000)

    def _test_connection(self):
        reddit = self._get_reddit()
        if not reddit:
            return
        try:
            user = reddit.user.me()
            karma = user.link_karma + user.comment_karma
            QMessageBox.information(self, '✅ Connection Successful',
                f'Connected to Reddit!\n\nUsername: {user.name}\n'
                f'Total Karma: {karma:,}\nLink Karma: {user.link_karma:,}\n'
                f'Comment Karma: {user.comment_karma:,}')
            self._status_bar.showMessage(f'✅ Connected as u/{user.name}', 5000)
        except Exception as e:
            QMessageBox.critical(self, 'Connection Failed', f'Connection test failed:\n{str(e)}')

    def _on_submission_finished(self, results):
        self._results_tab.show_results(results)
        self._tabs.setCurrentWidget(self._results_tab)
        ok = len(results['successful'])
        fail = len(results['failed'])
        self._status_bar.showMessage(f'✅ Completed: {ok} successful, {fail} failed', 10000)

    def closeEvent(self, event):
        logger.info("=== Application Closing ===")
        self._search_tab.stop_workers_on_close()
        self._import_tab.stop_worker_on_close()
        self._submit_tab.stop_worker_on_close()
        self._karma_tab.stop_workers_on_close()
        event.accept()
        logger.info("=== Application Closed ===")
