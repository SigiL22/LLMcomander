import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QGraphicsScene
from widgets import MapSettingsTab, MapTab, LogTab, ZoomableGraphicsView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Сервер подготовки карт и LLM")
        self.resize(1200, 800)
        self.scene = QGraphicsScene(self)
        self.view = ZoomableGraphicsView(self.scene, self)

        self.log_tab = LogTab(self)
        self.log_text_edit = self.log_tab.text_edit

        self.map_settings_tab = MapSettingsTab(self)
        self.map_tab = MapTab(self, self.map_settings_tab)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.map_settings_tab, "Настройки карты")
        self.tabs.addTab(self.map_tab, "Карта")
        self.tabs.addTab(self.log_tab, "Лог")

        self.setCentralWidget(self.tabs)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())