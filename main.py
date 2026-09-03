import sys
import logging
import os

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from app import ICON_PATH
from app.dashboard import RedditDashboard

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# These libraries log per-request DEBUG lines; prawcore in particular can include
# request bodies (the OAuth token request carries the password). Keep them at
# WARNING so credentials/URLs never reach the logs, and to cut the noise.
for _noisy in ('urllib3', 'requests', 'prawcore', 'praw'):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Reddit Dashboard")
    app.setOrganizationName("RedditTools")
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    dashboard = RedditDashboard()
    dashboard.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
