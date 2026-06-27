import sys

from PySide6.QtWidgets import QApplication

from database.database import create_database
from shared.app_assets import get_company_logo_icon
from ui.main_window import MainWindow

create_database()

app = QApplication(sys.argv)
app.setWindowIcon(get_company_logo_icon())

window = MainWindow()
window.setWindowIcon(get_company_logo_icon())
window.show()

sys.exit(app.exec())