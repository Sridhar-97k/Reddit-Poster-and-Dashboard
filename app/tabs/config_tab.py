import os
import json
import logging

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
                             QGroupBox, QLabel, QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import pyqtSignal

logger = logging.getLogger(__name__)


class ConfigTab(QWidget):
    credentials_saved = pyqtSignal()
    test_requested = pyqtSignal()

    def __init__(self, config_file='reddit_config.json'):
        super().__init__()
        self.config_file = config_file
        self._build_ui()
        self.load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        instructions_group = QGroupBox("📋 Setup Instructions")
        instructions_layout = QVBoxLayout()
        instructions = QLabel(
            "To use this Reddit Dashboard, you need to create a Reddit App:\n\n"
            "1. Go to https://www.reddit.com/prefs/apps\n"
            "2. Click 'Create App' or 'Create Another App'\n"
            "3. Choose 'script' as the app type\n"
            "4. Set redirect URI to: http://localhost:8080\n"
            "5. Copy the Client ID (shown under your app name)\n"
            "6. Copy the Client Secret (shown as 'secret')\n"
            "7. Enter your credentials below and save"
        )
        instructions.setWordWrap(True)
        instructions_layout.addWidget(instructions)
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)

        form_group = QGroupBox("🔑 Reddit API Configuration")
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter your Reddit app client ID")

        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(QLineEdit.Password)
        self.client_secret_input.setPlaceholderText("Enter your Reddit app client secret")

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Your Reddit username")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Your Reddit password")

        form_layout.addRow("Client ID:", self.client_id_input)
        form_layout.addRow("Client Secret:", self.client_secret_input)
        form_layout.addRow("Reddit Username:", self.username_input)
        form_layout.addRow("Reddit Password:", self.password_input)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save Configuration")
        save_btn.clicked.connect(self.save_config)
        save_btn.setMinimumHeight(40)

        test_btn = QPushButton("🔗 Test Connection")
        test_btn.clicked.connect(self.test_requested.emit)
        test_btn.setMinimumHeight(40)

        button_layout.addWidget(save_btn)
        button_layout.addWidget(test_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()

    @property
    def credentials(self):
        return {
            'client_id': self.client_id_input.text().strip(),
            'client_secret': self.client_secret_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text().strip(),
        }

    def save_config(self):
        creds = self.credentials
        if not all(creds.values()):
            reply = QMessageBox.question(
                self, 'Incomplete Configuration',
                'Some fields are empty. Save anyway?\n\nNote: All fields are required to connect.',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            with open(self.config_file, 'w') as f:
                json.dump(creds, f, indent=4)
            # Restrict to owner-only (no-op on filesystems without POSIX perms)
            try:
                os.chmod(self.config_file, 0o600)
            except OSError:
                pass
            self.credentials_saved.emit()
            QMessageBox.information(
                self, 'Success',
                'Configuration saved successfully!\n\nNext step: Click "Test Connection" to verify.'
            )
            logger.info("Configuration saved")
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save configuration:\n{str(e)}')

    def load_config(self):
        try:
            with open(self.config_file) as f:
                cfg = json.load(f)
            self.client_id_input.setText(cfg.get('client_id', ''))
            self.client_secret_input.setText(cfg.get('client_secret', ''))
            self.username_input.setText(cfg.get('username', ''))
            self.password_input.setText(cfg.get('password', ''))
            logger.info("Configuration loaded")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
