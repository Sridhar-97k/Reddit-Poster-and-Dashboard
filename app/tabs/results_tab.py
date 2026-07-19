import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox)
from PyQt5.QtGui import QColor

from ..utils import export_table_to_excel

logger = logging.getLogger(__name__)


class ResultsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        summary_group = QGroupBox("📋 Submission Summary")
        summary_layout = QVBoxLayout()
        self.summary_label = QLabel("No submissions yet")
        self.summary_label.setStyleSheet("font-size: 11pt; padding: 15px;")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["Status", "Subreddit", "Title", "Reddit Link", "Error"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.setAlternatingRowColors(True)
        layout.addWidget(self.results_table)

        export_btn = QPushButton("💾 Export Results to Excel")
        export_btn.clicked.connect(self._export)
        export_btn.setMinimumHeight(40)
        layout.addWidget(export_btn)

    def show_results(self, results):
        successful = results['successful']
        failed = results['failed']
        total = results['total']

        self.results_table.setRowCount(0)

        for item in successful:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            status = QTableWidgetItem("✅ Success")
            status.setForeground(QColor("#27ae60"))
            self.results_table.setItem(row, 0, status)
            self.results_table.setItem(row, 1, QTableWidgetItem(item['subreddit']))
            self.results_table.setItem(row, 2, QTableWidgetItem(item['title']))
            self.results_table.setItem(row, 3, QTableWidgetItem(item['permalink']))
            self.results_table.setItem(row, 4, QTableWidgetItem(""))

        for item in failed:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            status = QTableWidgetItem("❌ Failed")
            status.setForeground(QColor("#e74c3c"))
            self.results_table.setItem(row, 0, status)
            post = item.get('post', {})
            self.results_table.setItem(row, 1, QTableWidgetItem(post.get('subreddit', 'N/A')))
            self.results_table.setItem(row, 2, QTableWidgetItem(post.get('title', 'N/A')))
            self.results_table.setItem(row, 3, QTableWidgetItem(""))
            self.results_table.setItem(row, 4, QTableWidgetItem(item['reason']))

        rate = (len(successful) / total * 100) if total else 0
        self.summary_label.setText(
            f"Batch submission completed!\n\n"
            f"✅ Successful: {len(successful)}\n"
            f"❌ Failed: {len(failed)}\n"
            f"📊 Total: {total}\n"
            f"📈 Success Rate: {rate:.1f}%"
        )
        logger.info(f"Results displayed: {len(successful)}/{total} successful")

    def _export(self):
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, 'No Data', 'No results to export.')
            return
        export_table_to_excel(self, self.results_table, "Submission Results",
                              "Save Results", "submission_results")
