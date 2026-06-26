from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("📊 Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
            color:white;
        """)

        welcome = QLabel("MeWa ERP Professional'a Hoş Geldiniz")
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet("""
            font-size:18px;
            color:#bdbdbd;
        """)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(welcome)
        layout.addStretch()