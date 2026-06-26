from PySide6.QtWidgets import QTabWidget, QWidget
from PySide6.QtCore import Qt


class TabManager(QTabWidget):
    def __init__(self):
        super().__init__()

        # Sekmeler kapatılabilir olsun
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.closeTab)

        # Sekmeler taşınabilsin
        self.setMovable(True)

        # Sekmeler belge görünümünde olsun
        self.setDocumentMode(True)

    def open_tab(self, widget: QWidget, title: str):
        """
        Aynı isimde sekme varsa tekrar açma.
        """
        for i in range(self.count()):
            if self.tabText(i) == title:
                self.setCurrentIndex(i)
                return

        self.addTab(widget, title)
        self.setCurrentWidget(widget)

    def closeTab(self, index):
        if self.count() > 1:
            self.removeTab(index)