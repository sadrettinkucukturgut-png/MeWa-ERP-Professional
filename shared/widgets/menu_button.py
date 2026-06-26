from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt

class MenuButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)

        self.setMinimumHeight(46)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet("""
            QPushButton{
                background-color:#2b2b2b;
                color:white;
                border:none;
                border-left:4px solid transparent;
                text-align:left;
                padding-left:18px;
                font-size:14px;
            }

            QPushButton:hover{
                background-color:#3b3b3b;
                border-left:4px solid #3daee9;
            }

            QPushButton:pressed{
                background-color:#4b4b4b;
            }
        """)