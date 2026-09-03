import csv
import logging
from datetime import datetime

from PyQt5.QtWidgets import QFileDialog, QMessageBox

from .csv_utils import safe_row

logger = logging.getLogger(__name__)


def export_table_to_csv(parent, table, dialog_title, filename_prefix):
    """Save a QTableWidget's contents to a user-chosen .csv file."""
    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        dialog_title,
        f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "CSV Files (*.csv)"
    )
    if not file_path:
        return

    try:
        col_count = table.columnCount()
        # utf-8-sig so Excel opens the file with the right encoding
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            headers = []
            for col in range(col_count):
                header_item = table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column {col + 1}")
            writer.writerow(headers)

            for row in range(table.rowCount()):
                writer.writerow(safe_row(
                    (table.item(row, col).text() if table.item(row, col) else '')
                    for col in range(col_count)
                ))

        QMessageBox.information(parent, 'Success', f'Exported successfully!\n\n{file_path}')
        logger.info("Exported table to %s", file_path)

    except Exception as e:
        QMessageBox.critical(parent, 'Error', f'Failed to export:\n{str(e)}')
