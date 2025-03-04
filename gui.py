import sys
import os
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

        # Автозагрузка последних настроек и карты
        last_settings_file = "last_settings.json"
        if os.path.exists(last_settings_file):
            try:
                self.map_settings_tab.load_settings(last_settings_file)
                last_map = self.map_tab.load_last_map()
                if last_map and os.path.exists(last_map):
                    self.map_tab.load_map(last_map)
                else:
                    self.log_text_edit.append(f"Последняя карта не найдена: {last_map}")
            except Exception as e:
                self.log_text_edit.append(f"Ошибка автозагрузки настроек: {e}")
        else:
            self.log_text_edit.append("Файл последних настроек не найден, используются настройки по умолчанию")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())