import sys

from PySide6.QtWidgets import QApplication

from database.database import create_database
from ui.main_window import MainWindow

create_database()

app = QApplication(sys.argv)

window = MainWindow()
window.show()

sys.exit(app.exec())