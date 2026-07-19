import sys
import logging

from PyQt5.QtWidgets import QApplication

from app.dashboard import RedditDashboard

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
# urllib3 and requests flood the log with per-request DEBUG lines; keep them quiet
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Reddit Dashboard")
    app.setOrganizationName("RedditTools")

    dashboard = RedditDashboard()
    dashboard.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
