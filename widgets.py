from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget, QFileDialog,
    QTextEdit, QFormLayout, QSpinBox, QLineEdit, QGraphicsScene, QGraphicsView,
    QComboBox, QColorDialog, QGroupBox, QGridLayout, QFontDialog, QGraphicsTextItem, QGraphicsItemGroup
)
from PyQt5.QtGui import QPixmap, QImage, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PIL import Image
import json
import os
from utils import pil_image_to_qpixmap, find_font_path
from map_processing import resize_image, draw_grid, draw_grid_region, extract_region, draw_names
from db_handler import parse_names_file
from name_editor import NameEditor

class CoordinateLabelSettingsWidget(QWidget):
    def __init__(self, default_font_size=20, default_color=(0, 0, 0, 255), default_font="Arial", parent=None):
        super().__init__(parent)
        self.font_size = QSpinBox()
        self.font_size.setRange(1, 100)
        self.font_size.setValue(default_font_size)

        self.font_color_edit = QLineEdit(",".join(map(str, default_color)))
        self.btn_select_color = QPushButton("Выбрать цвет")
        self.btn_select_color.clicked.connect(self.select_color)
        self.color_indicator = QLabel()
        self.color_indicator.setFixedSize(20, 20)
        self.update_color_indicator(self.color_indicator, default_color)

        self.btn_select_font = QPushButton("Выбрать шрифт")
        self.btn_select_font.clicked.connect(self.select_font)
        self.font_label = QLabel(default_font)
        self.selected_font = QFont(default_font)

        layout = QHBoxLayout()
        layout.addWidget(QLabel("Надписи координат:"))
        layout.addWidget(QLabel("Размер:"))
        layout.addWidget(self.font_size)
        layout.addWidget(QLabel("Цвет:"))
        layout.addWidget(self.font_color_edit)
        layout.addWidget(self.btn_select_color)
        layout.addWidget(self.color_indicator)
        layout.addWidget(QLabel("Шрифт:"))
        layout.addWidget(self.font_label)
        layout.addWidget(self.btn_select_font)
        self.setLayout(layout)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            text = f"{color.red()},{color.green()},{color.blue()},{color.alpha()}"
            self.font_color_edit.setText(text)
            self.update_color_indicator(self.color_indicator, (color.red(), color.green(), color.blue(), color.alpha()))

    def update_color_indicator(self, indicator, rgba):
        try:
            r, g, b, a = rgba
            indicator.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid black;")
        except (ValueError, TypeError) as e:
            self.parent.log_text_edit.append(f"Ошибка установки цвета индикатора: {e}")
            indicator.setStyleSheet("background-color: rgba(0, 0, 0, 255); border: 1px solid black;")  # Fallback

    def select_font(self):
        font, ok = QFontDialog.getFont(self.selected_font)
        if ok:
            self.selected_font = font
            self.font_label.setText(font.family())

    def get_settings(self):
        try:
            font_color = tuple(map(int, self.font_color_edit.text().split(',')))
        except ValueError:
            font_color = (0, 0, 0, 255)
        font_family = self.font_label.text()
        bold = self.selected_font.bold()
        italic = self.selected_font.italic()
        font_path = find_font_path(font_family, bold, italic)
        return {
            "font_size": self.font_size.value(),
            "font_color": font_color,
            "font": font_path if font_path else "C:/Windows/Fonts/arial.ttf"
        }

class NameSettingsWidget(QWidget):
    def __init__(self, type_name, default_font_size, default_color, default_font="arial.ttf", parent=None):
        super().__init__(parent)
        self.type_name = type_name

        self.font_size = QSpinBox()
        self.font_size.setRange(1, 100)
        self.font_size.setValue(default_font_size)

        self.font_color_edit = QLineEdit(",".join(map(str, default_color)))
        self.btn_select_color = QPushButton("Выбрать цвет")
        self.btn_select_color.clicked.connect(self.select_color)

        self.btn_select_font = QPushButton("Выбрать шрифт")
        self.btn_select_font.clicked.connect(self.select_font)
        self.font_label = QLabel(default_font)

        self.chk_bold = QCheckBox("Жирный")
        self.chk_italic = QCheckBox("Курсив")

        layout = QHBoxLayout()
        layout.addWidget(QLabel(type_name + ":"))
        layout.addWidget(QLabel("Размер:"))
        layout.addWidget(self.font_size)
        layout.addWidget(QLabel("Цвет:"))
        layout.addWidget(self.font_color_edit)
        layout.addWidget(self.btn_select_color)
        layout.addWidget(QLabel("Шрифт:"))
        layout.addWidget(self.font_label)
        layout.addWidget(self.btn_select_font)
        layout.addWidget(self.chk_bold)
        layout.addWidget(self.chk_italic)
        self.setLayout(layout)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            text = f"{color.red()},{color.green()},{color.blue()},{color.alpha()}"
            self.font_color_edit.setText(text)

    def select_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            self.font_label.setText(font.family())

    def get_settings(self):
        return {
            "font_size": self.font_size.value(),
            "font_color": tuple(map(int, self.font_color_edit.text().split(','))),
            "font": self.font_label.text(),
            "bold": self.chk_bold.isChecked(),
            "italic": self.chk_italic.isChecked()
        }

class ZoomableGraphicsView(QGraphicsView):
    item_moved = pyqtSignal(object)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self._zoom = 0
        self._dragging = False
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
            self._zoom += 1
        else:
            factor = zoom_out_factor
            self._zoom -= 1
        if self._zoom > 20:
            self._zoom = 20
            return
        elif self._zoom < -10:
            self._zoom = -10
            return
        self.scale(factor, factor)
        if self.parent().parent.log_text_edit:
            self.parent().parent.log_text_edit.append(f"Zoom changed: factor={self.transform().m11()}")

    def mousePressEvent(self, event):
        if self.parent().name_editor and self.parent().name_editor.is_editing:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())
            if item and isinstance(item, QGraphicsTextItem):
                self.parent().on_item_selected(item)
                self._dragging = True
                self.setDragMode(QGraphicsView.NoDrag)
                if self.parent().parent.log_text_edit:
                    self.parent().parent.log_text_edit.append(f"Mouse pressed: pos={event.pos()}, scene_pos={scene_pos}, item={item.rec_id}")
            else:
                if self.parent().parent.log_text_edit:
                    self.parent().parent.log_text_edit.append(f"Mouse pressed: pos={event.pos()}, scene_pos={scene_pos}, no item")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self.parent().name_editor and self.parent().name_editor.is_editing:
            item = self.parent().name_editor.selected_item
            if item:
                new_pos = self.mapToScene(event.pos())
                item.setPos(new_pos)
                self.parent().name_editor.item_moved(item)  # Обновляем позицию в реальном времени
                if self.parent().parent.log_text_edit:
                    self.parent().parent.log_text_edit.append(f"Mouse moved: new_pos={new_pos}")
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and self.parent().name_editor and self.parent().name_editor.is_editing:
            item = self.parent().name_editor.selected_item
            if item:
                self.item_moved.emit(item)
                if self.parent().parent.log_text_edit:
                    self.parent().parent.log_text_edit.append(f"Mouse released: item={item.rec_id}, pos={item.pos()}")
            self._dragging = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        super().mouseReleaseEvent(event)

class MapSettingsTab(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        main_layout = QFormLayout()

        self.output_width = QSpinBox()
        self.output_width.setRange(1, 20000)
        self.output_width.setValue(1000)
        main_layout.addRow("Выходное разрешение (ширина):", self.output_width)

        self.output_height = QSpinBox()
        self.output_height.setRange(1, 20000)
        self.output_height.setValue(1000)
        main_layout.addRow("Выходное разрешение (высота):", self.output_height)

        self.btn_apply_input = QPushButton("Принять входное разрешение")
        self.btn_apply_input.clicked.connect(self.apply_input_resolution)
        main_layout.addRow("", self.btn_apply_input)

        self.pixels_per_100m = QSpinBox()
        self.pixels_per_100m.setRange(1, 1000)
        self.pixels_per_100m.setValue(100)
        main_layout.addRow("Пикселей на 100 м:", self.pixels_per_100m)

        self.grid_thickness_100 = QSpinBox()
        self.grid_thickness_100.setRange(1, 100)
        self.grid_thickness_100.setValue(10)
        main_layout.addRow("Толщина линии 100 м:", self.grid_thickness_100)

        self.grid_thickness_1km = QSpinBox()
        self.grid_thickness_1km.setRange(1, 100)
        self.grid_thickness_1km.setValue(15)
        main_layout.addRow("Толщина линии 1 км:", self.grid_thickness_1km)

        self.margin = QSpinBox()
        self.margin.setRange(0, 100)
        self.margin.setValue(10)
        main_layout.addRow("Отступ от края (px):", self.margin)

        # Цвет линии 100 м
        self.color_100_edit = QLineEdit("0,255,0,128")
        self.btn_color_100 = QPushButton("Выбрать цвет")
        self.btn_color_100.clicked.connect(lambda: self._choose_color(self.color_100_edit, self.color_100_indicator))
        self.color_100_indicator = QLabel()
        self.color_100_indicator.setFixedSize(20, 20)
        self.update_color_indicator(self.color_100_indicator, (0, 255, 0, 128))
        color_100_layout = QHBoxLayout()
        color_100_layout.addWidget(self.color_100_edit)
        color_100_layout.addWidget(self.btn_color_100)
        color_100_layout.addWidget(self.color_100_indicator)
        main_layout.addRow("Цвет линии 100 м (R,G,B,A):", color_100_layout)

        # Цвет линии 1 км
        self.color_1km_edit = QLineEdit("255,0,0,200")
        self.btn_color_1km = QPushButton("Выбрать цвет")
        self.btn_color_1km.clicked.connect(lambda: self._choose_color(self.color_1km_edit, self.color_1km_indicator))
        self.color_1km_indicator = QLabel()
        self.color_1km_indicator.setFixedSize(20, 20)
        self.update_color_indicator(self.color_1km_indicator, (255, 0, 0, 200))
        color_1km_layout = QHBoxLayout()
        color_1km_layout.addWidget(self.color_1km_edit)
        color_1km_layout.addWidget(self.btn_color_1km)
        color_1km_layout.addWidget(self.color_1km_indicator)
        main_layout.addRow("Цвет линии 1 км (R,G,B,A):", color_1km_layout)

        self.coord_label_settings = CoordinateLabelSettingsWidget(
            default_font_size=20,
            default_color=(0, 0, 0, 255),
            default_font="Arial",
            parent=self
        )
        coord_group_box = QGroupBox("Настройки надписей координат")
        coord_layout = QVBoxLayout()
        coord_layout.addWidget(self.coord_label_settings)
        coord_group_box.setLayout(coord_layout)
        main_layout.addRow(coord_group_box)

        self.origin_combo = QComboBox()
        self.origin_combo.addItems(["top-left", "top-right", "bottom-left", "bottom-right"])
        main_layout.addRow("Начало координат:", self.origin_combo)

        self.center_col = QSpinBox()
        self.center_col.setRange(0, 999)
        self.center_col.setValue(5)
        main_layout.addRow("Центральная ячейка (X):", self.center_col)

        self.center_row = QSpinBox()
        self.center_row.setRange(0, 999)
        self.center_row.setValue(5)
        main_layout.addRow("Центральная ячейка (Y):", self.center_row)

        self.n_cells = QSpinBox()
        self.n_cells.setRange(1, 50)
        self.n_cells.setValue(3)
        main_layout.addRow("Размер участка (ячеек в сторону):", self.n_cells)

        name_types = ["NameCityCapital", "NameCity", "NameVillage", "Hill", "NameLocal", "NameMarine"]
        defaults = {
            "NameCityCapital": {"font_size": 16, "font_color": (255, 0, 0, 255), "font": "Arial"},
            "NameCity":        {"font_size": 14, "font_color": (0, 0, 255, 255), "font": "Arial"},
            "NameVillage":     {"font_size": 12, "font_color": (0, 128, 0, 255), "font": "Arial"},
            "Hill":            {"font_size": 10, "font_color": (128, 128, 128, 255), "font": "Arial"},
            "NameLocal":       {"font_size": 10, "font_color": (128, 0, 128, 255), "font": "Arial"},
            "NameMarine":      {"font_size": 10, "font_color": (0, 128, 128, 255), "font": "Arial"}
        }

        group_box = QGroupBox("Настройки надписей")
        grid = QGridLayout()
        grid.addWidget(QLabel("Тип"),            0, 0)
        grid.addWidget(QLabel("Размер"),         0, 1)
        grid.addWidget(QLabel("Цвет (R,G,B,A)"), 0, 2)
        grid.addWidget(QLabel(""),               0, 3)
        grid.addWidget(QLabel(""),               0, 4)  # Для индикатора
        grid.addWidget(QLabel("Шрифт"),          0, 5)
        grid.addWidget(QLabel(""),               0, 6)

        self.name_settings_widgets = {}
        row = 1
        for t in name_types:
            lbl_type = QLabel(t)
            sp_size = QSpinBox()
            sp_size.setRange(1, 100)
            sp_size.setValue(defaults[t]["font_size"])
            le_color = QLineEdit(",".join(map(str, defaults[t]["font_color"])))
            le_color.setMaximumWidth(70)
            btn_color = QPushButton("...")
            btn_color.setMaximumWidth(30)
            color_indicator = QLabel()
            color_indicator.setFixedSize(20, 20)
            self.update_color_indicator(color_indicator, defaults[t]["font_color"])
            lbl_font = QLabel(defaults[t]["font"])
            btn_font = QPushButton("...")
            btn_font.setMaximumWidth(30)

            btn_color.clicked.connect(lambda _, le=le_color, ci=color_indicator: self._choose_color(le, ci))
            btn_font.clicked.connect(lambda _, lf=lbl_font, tt=t: self._choose_font(lf, tt))

            grid.addWidget(lbl_type,       row, 0)
            grid.addWidget(sp_size,        row, 1)
            grid.addWidget(le_color,       row, 2)
            grid.addWidget(btn_color,      row, 3)
            grid.addWidget(color_indicator,row, 4)
            grid.addWidget(lbl_font,       row, 5)
            grid.addWidget(btn_font,       row, 6)

            self.name_settings_widgets[t] = {
                "spin_size": sp_size,
                "line_color": le_color,
                "color_indicator": color_indicator,
                "label_font": lbl_font,
                "selected_font": QFont(defaults[t]["font"])
            }
            row += 1

        group_box.setLayout(grid)
        main_layout.addRow(group_box)

        button_layout = QHBoxLayout()
        self.btn_save_settings = QPushButton("Сохранить настройки")
        self.btn_save_settings.clicked.connect(self.save_settings)
        self.btn_load_settings = QPushButton("Загрузить настройки")
        self.btn_load_settings.clicked.connect(self.load_settings)
        button_layout.addWidget(self.btn_save_settings)
        button_layout.addWidget(self.btn_load_settings)
        main_layout.addRow("", button_layout)

        self.setLayout(main_layout)

    def _choose_color(self, line_edit, indicator):
        color = QColorDialog.getColor()
        if color.isValid():
            text = f"{color.red()},{color.green()},{color.blue()},{color.alpha()}"
            line_edit.setText(text)
            self.update_color_indicator(indicator, (color.red(), color.green(), color.blue(), color.alpha()))

    def update_color_indicator(self, indicator, rgba):
        try:
            r, g, b, a = rgba
            indicator.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid black;")
        except (ValueError, TypeError) as e:
            self.parent.log_text_edit.append(f"Ошибка установки цвета индикатора: {e}")
            indicator.setStyleSheet("background-color: rgba(0, 0, 0, 255); border: 1px solid black;")  # Fallback

    def _choose_font(self, label_font, type_name):
        widget_dict = self.name_settings_widgets[type_name]
        font, ok = QFontDialog.getFont(widget_dict["selected_font"])
        if ok:
            widget_dict["selected_font"] = font
            label_font.setText(font.family())

    def apply_input_resolution(self):
        if self.parent.map_tab.input_map is None:
            self.parent.log_text_edit.append("Карта не загружена!")
            return
        w, h = self.parent.map_tab.input_map.size
        self.output_width.setMaximum(w)
        self.output_height.setMaximum(h)
        self.output_width.setValue(w)
        self.output_height.setValue(h)
        self.parent.log_text_edit.append(f"Принято входное разрешение: {w}x{h}")

    def get_parameters(self):
        name_settings = {}
        for t, wdict in self.name_settings_widgets.items():
            font_size = wdict["spin_size"].value()
            color_str = wdict["line_color"].text()
            font_family = wdict["label_font"].text()
            try:
                font_color = tuple(map(int, color_str.split(',')))
            except:
                font_color = (0, 0, 0, 255)
            bold = wdict["selected_font"].bold()
            italic = wdict["selected_font"].italic()
            font_path = find_font_path(font_family, bold, italic)
            name_settings[t] = {
                "font_size": font_size,
                "font_color": font_color,
                "font": font_path if font_path else "C:/Windows/Fonts/arial.ttf"
            }

        coord_settings = self.coord_label_settings.get_settings()

        params = {
            "output_resolution": (self.output_width.value(), self.output_height.value()),
            "pixels_per_100m": self.pixels_per_100m.value(),
            "grid_thickness_100": self.grid_thickness_100.value(),
            "grid_thickness_1km": self.grid_thickness_1km.value(),
            "margin": self.margin.value(),
            "color_100": tuple(map(int, self.color_100_edit.text().split(','))),
            "color_1km": tuple(map(int, self.color_1km_edit.text().split(','))),
            "font_size": coord_settings["font_size"],
            "font_color": coord_settings["font_color"],
            "font_path": coord_settings["font"],
            "origin": self.origin_combo.currentText(),
            "center_col": self.center_col.value(),
            "center_row": self.center_row.value(),
            "n_cells": self.n_cells.value(),
            "name_settings": name_settings,
            "last_map": self.parent.map_tab.last_map if self.parent.map_tab.last_map else None
        }
        return params

    def save_settings(self):
        params = self.get_parameters()
        params["output_width"] = self.output_width.value()
        params["output_height"] = self.output_height.value()
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить настройки", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=4)
            self.parent.log_text_edit.append(f"Настройки сохранены: {file_path}")
            # Сохраняем как последние настройки
            with open("last_settings.json", "w", encoding="utf-8") as f:
                json.dump(params, f, indent=4)
            self.parent.log_text_edit.append(f"Последние настройки сохранены: last_settings.json (last_map: {params['last_map']})")

    def load_settings(self, file_path=None):
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(self, "Загрузить настройки", "", "JSON Files (*.json)")
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                self.output_width.setValue(params.get("output_width", params["output_resolution"][0]))
                self.output_height.setValue(params.get("output_height", params["output_resolution"][1]))
                self.pixels_per_100m.setValue(params["pixels_per_100m"])
                self.grid_thickness_100.setValue(params["grid_thickness_100"])
                self.grid_thickness_1km.setValue(params["grid_thickness_1km"])
                self.margin.setValue(params["margin"])
                color_100 = params.get("color_100", (0, 255, 0, 128))
                self.color_100_edit.setText(",".join(map(str, color_100)))
                self.update_color_indicator(self.color_100_indicator, color_100)
                color_1km = params.get("color_1km", (255, 0, 0, 200))
                self.color_1km_edit.setText(",".join(map(str, color_1km)))
                self.update_color_indicator(self.color_1km_indicator, color_1km)
                self.origin_combo.setCurrentText(params["origin"])
                self.center_col.setValue(params["center_col"])
                self.center_row.setValue(params["center_row"])
                self.n_cells.setValue(params["n_cells"])

                self.coord_label_settings.font_size.setValue(params.get("font_size", 20))
                font_color = params.get("font_color", (0, 0, 0, 255))
                self.coord_label_settings.font_color_edit.setText(",".join(map(str, font_color)))
                self.coord_label_settings.update_color_indicator(self.coord_label_settings.color_indicator, font_color)
                font_path = params.get("font_path", "C:/Windows/Fonts/arial.ttf")
                font_family = os.path.splitext(os.path.basename(font_path))[0].capitalize()
                self.coord_label_settings.font_label.setText(font_family)

                if "name_settings" in params:
                    for t, sett in params["name_settings"].items():
                        if t in self.name_settings_widgets:
                            wdict = self.name_settings_widgets[t]
                            wdict["spin_size"].setValue(sett.get("font_size", wdict["spin_size"].value()))
                            fc = sett.get("font_color", (0,0,0,255))
                            wdict["line_color"].setText(",".join(map(str, fc)))
                            self.update_color_indicator(wdict["color_indicator"], fc)
                            font_path = sett.get("font", "C:/Windows/Fonts/arial.ttf")
                            font_family = os.path.splitext(os.path.basename(font_path))[0].capitalize()
                            wdict["label_font"].setText(font_family)

                if "last_map" in params:
                    self.parent.map_tab.set_last_map(params["last_map"])
                    self.parent.log_text_edit.append(f"Загружен путь последней карты: {params['last_map']}")

                self.parent.log_text_edit.append(f"Настройки загружены: {file_path}")
            except Exception as e:
                self.parent.log_text_edit.append(f"Ошибка загрузки настроек: {e}")

class MapTab(QWidget):
    def __init__(self, parent, map_settings_tab):
        super().__init__(parent)
        self.parent = parent
        self.map_settings_tab = map_settings_tab

        self.input_map = None
        self.processed_map = None  # Карта с сеткой и надписями
        self.image_with_grid = None  # Карта только с сеткой
        self.region_windows = []
        self.last_map = None
        self._updating_combo = False
        self.name_editor = None

        layout = QVBoxLayout()

        self.map_combo = QComboBox()
        self.update_map_list()
        self.map_combo.currentTextChanged.connect(self.load_map_from_combo)
        layout.addWidget(self.map_combo)

        btn_apply = QPushButton("Применить сетку")
        btn_apply.clicked.connect(self.apply_grid)
        layout.addWidget(btn_apply)

        btn_extract = QPushButton("Извлечь участок")
        btn_extract.clicked.connect(self.extract_region)
        layout.addWidget(btn_extract)

        btn_edit = QPushButton("Edit Names")
        btn_edit.clicked.connect(self.toggle_edit_mode)
        layout.addWidget(btn_edit)

        btn_save = QPushButton("Save Names")
        btn_save.clicked.connect(self.save_names)
        layout.addWidget(btn_save)

        btn_save_map = QPushButton("Сохранить карту")
        btn_save_map.clicked.connect(self.save_map)
        layout.addWidget(btn_save_map)

        self.scene = self.parent.scene
        self.view = ZoomableGraphicsView(self.scene, self)
        self.view.item_moved.connect(self.on_item_moved)
        layout.addWidget(self.view)

        self.setLayout(layout)

    def toggle_edit_mode(self):
        if not self.processed_map:
            self.parent.log_text_edit.append("Сначала примените сетку к карте!")
            return
        if not self.name_editor:
            params = self.map_settings_tab.get_parameters()
            self.name_editor = NameEditor(
                self, self.image_with_grid, self.input_map, os.path.join("db", "name.db"), 
                params["name_settings"], params["origin"], 
                params["output_resolution"][0] / self.input_map.size[0],
                self.processed_map.size[0], self.processed_map.size[1],
                params, self.parent.log_text_edit.append
            )
        if not self.name_editor.is_editing:
            self.name_editor.start_editing()
        else:
            self.name_editor.stop_editing()

    def save_names(self):
        if self.name_editor and self.name_editor.is_editing:
            self.name_editor.save_changes()
        else:
            self.parent.log_text_edit.append("Активируйте режим редактирования перед сохранением!")

    def on_item_selected(self, item):
        if self.name_editor and self.name_editor.is_editing:
            self.name_editor.select_item(item)

    def on_item_moved(self, item):
        if self.name_editor and self.name_editor.is_editing:
            self.name_editor.item_moved(item)
    def update_map_list(self):
        if self._updating_combo:
            return
        self._updating_combo = True
        maps_dir = "maps"
        if not os.path.exists(maps_dir):
            os.makedirs(maps_dir)
        map_files = [f for f in os.listdir(maps_dir) if f.endswith(".png")]
        current_text = self.map_combo.currentText()
        self.map_combo.blockSignals(True)  # Отключаем сигналы во время обновления
        self.map_combo.clear()
        self.map_combo.addItem("Выберите карту...")
        self.map_combo.addItems(map_files)
        if self.last_map and os.path.basename(self.last_map) in map_files:
            self.map_combo.setCurrentText(os.path.basename(self.last_map))
        elif current_text in map_files:
            self.map_combo.setCurrentText(current_text)
        self.map_combo.blockSignals(False)  # Включаем сигналы обратно
        self._updating_combo = False

    def load_map_from_combo(self, map_name):
        if map_name and map_name != "Выберите карту..." and not self._updating_combo:
            map_path = os.path.join("maps", map_name)
            self.load_map(map_path)
            self.last_map = map_path
            self.parent.log_text_edit.append(f"Выбрана карта: {map_path}")

    def load_map(self, file_path):
        if file_path and os.path.exists(file_path):
            Image.MAX_IMAGE_PIXELS = None
            self.input_map = Image.open(file_path).convert("RGBA")
            self.parent.log_text_edit.append(f"Карта загружена: {file_path}")
            self.update_view(self.input_map)
            self.last_map = file_path
            self.update_map_list()  # Обновляем список после загрузки

    def load_last_map(self):
        return self.last_map

    def set_last_map(self, map_path):
        self.last_map = map_path
        self.update_map_list()
        if map_path and os.path.exists(map_path):
            self.load_map(map_path)

    def apply_grid(self):
        if self.input_map is None:
            self.parent.log_text_edit.append("Сначала загрузите карту!")
            return

        params = self.map_settings_tab.get_parameters()
        output_resolution = params["output_resolution"]
        scale_factor = output_resolution[0] / self.input_map.size[0]
        resized = resize_image(self.input_map, output_resolution)
        pixels_per_100m_output = params["pixels_per_100m"] * scale_factor

        # Сохраняем карту с сеткой без надписей
        self.image_with_grid = draw_grid(
            resized.copy(), 
            pixels_per_100m_output, 
            params["grid_thickness_100"],
            params["grid_thickness_1km"], 
            params["color_100"], 
            params["color_1km"],
            params.get("label_mode_h", "0"), 
            params.get("label_mode_v", "0"), 
            params["font_size"],
            params["font_path"], 
            params["font_color"], 
            params["margin"], 
            params["origin"],
            log_func=self.parent.log_text_edit.append
        )
        
        # Полная карта с надписями
        self.processed_map = draw_names(
            self.image_with_grid.copy(),
            os.path.join("db", "name.db"),
            params["name_settings"],
            params["origin"],
            scale=scale_factor,
            global_width=self.image_with_grid.size[0],
            global_height=self.image_with_grid.size[1],
            log_func=self.parent.log_text_edit.append
        )
        self.update_view(self.processed_map)

        db_path = os.path.join("db", "name.db")
        name_file = "name.txt"
        if os.path.exists(name_file):
            parse_names_file(name_file, db_path, self.parent.log_text_edit.append)
        
        name_settings = params.get("name_settings", {
            "NameCityCapital": {"font_size": 16, "font_color": (255, 0, 0, 255)},
            "NameCity": {"font_size": 14, "font_color": (0, 0, 255, 255)},
            "NameVillage": {"font_size": 12, "font_color": (0, 128, 0, 255)},
            "Hill": {"font_size": 10, "font_color": (128, 128, 128, 255)},
            "NameLocal": {"font_size": 10, "font_color": (128, 0, 128, 255)},
            "NameMarine": {"font_size": 10, "font_color": (0, 128, 128, 255)}
        })
        global_size = self.processed_map.size
        self.processed_map = draw_names(
            self.processed_map,
            db_path,
            name_settings,
            params["origin"],
            scale=scale_factor,
            crop_offset=None,  # Для полной карты нет смещения
            global_width=global_size[0],
            global_height=global_size[1],
            log_func=self.parent.log_text_edit.append
        )
        self.update_view(self.processed_map)

        full_cols = int(self.processed_map.size[0] // pixels_per_100m_output)
        full_rows = int(self.processed_map.size[1] // pixels_per_100m_output)
        self.map_settings_tab.center_col.setRange(0, full_cols - 1)
        self.map_settings_tab.center_row.setRange(0, full_rows - 1)
        self.parent.log_text_edit.append(f"Границы карты: X=0-{full_cols-1}, Y=0-{full_rows-1}")

    def extract_region(self):
        if self.processed_map is None:
            self.parent.log_text_edit.append("Ошибка: сначала примените сетку к карте!")
            return

        params = self.map_settings_tab.get_parameters()
        center_cell = (params["center_col"], params["center_row"])
        n_cells = params["n_cells"]
        scale_factor = params["output_resolution"][0] / self.input_map.size[0]
        pixels_per_100m_output = params["pixels_per_100m"] * scale_factor

        # ... (логирование параметров остаётся без изменений) ...

        region, start_col, start_row, total_cols, total_rows, crop_box = extract_region(
            self.input_map.copy(),
            center_cell,
            n_cells,
            pixels_per_100m_output,
            params["origin"],
            self.parent.log_text_edit.append
        )
        # ... (логирование вырезки остаётся без изменений) ...

        offset_x = start_col
        offset_y = start_row
        self.parent.log_text_edit.append(f"Смещения: offset_x={offset_x}, offset_y={offset_y}")

        region_with_grid = draw_grid_region(
            region.copy(),
            pixels_per_100m_output,
            params["grid_thickness_100"],
            params["grid_thickness_1km"],
            params["color_100"],
            params["color_1km"],
            params.get("label_mode_h", "0"),
            params.get("label_mode_v", "0"),
            params["font_size"],
            params["font_path"],
            params["font_color"],
            params["margin"],
            params["origin"],
            offset_x=offset_x,
            offset_y=offset_y,
            log_func=self.parent.log_text_edit.append
        )

        crop_offset = (crop_box[0], crop_box[1])
        self.parent.log_text_edit.append(f"Crop offset: {crop_offset}")
        self.parent.log_text_edit.append(f"Перед вызовом draw_names: scale_factor={scale_factor}, origin={params['origin']}, "
                                        f"изображение вырезанного участка size={region_with_grid.size}")

        db_path = os.path.join("db", "name.db")
        name_settings = params.get("name_settings", {
            "NameCityCapital": {"font_size": 16, "font_color": (255, 0, 0, 255)},
            "NameCity": {"font_size": 14, "font_color": (0, 0, 255, 255)},
            "NameVillage": {"font_size": 12, "font_color": (0, 128, 0, 255)},
            "Hill": {"font_size": 10, "font_color": (128, 128, 128, 255)},
            "NameLocal": {"font_size": 10, "font_color": (128, 0, 128, 255)},
            "NameMarine": {"font_size": 10, "font_color": (0, 128, 128, 255)}
        })
        region_with_names = draw_names(
            region_with_grid,
            db_path,
            name_settings,
            params["origin"],
            scale=scale_factor,
            crop_offset=crop_offset,  # Учитываем смещение для участка
            global_width=self.processed_map.size[0],
            global_height=self.processed_map.size[1],
            log_func=self.parent.log_text_edit.append
        )
        
        self.parent.log_text_edit.append(
            f"Участок извлечён и отрисован: центр ({center_cell[0]}, {center_cell[1]}), "
            f"размер {n_cells} ячеек в сторону"
        )
        self.show_extracted_region(region_with_names, center_cell)

    def save_map(self):
        if self.processed_map is None:
            self.parent.log_text_edit.append("Нет обработанной карты для сохранения!")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить карту", "", "PNG Files (*.png)")
        if file_path:
            self.processed_map.save(file_path, format="PNG", dpi=self.input_map.info.get("dpi", (72, 72)))
            self.parent.log_text_edit.append(f"Карта сохранена: {file_path}")

    def update_view(self, pil_image):
        self.scene.clear()
        pixmap = pil_image_to_qpixmap(pil_image)
        self.scene.addPixmap(pixmap)

    def show_extracted_region(self, region_image, center_cell):
        window = QWidget()
        window.setWindowTitle(f"Извлечённый участок ({center_cell[0]}, {center_cell[1]})")
        layout = QVBoxLayout()
        
        scene = QGraphicsScene(window)
        view = ZoomableGraphicsView(scene, window)
        pixmap = pil_image_to_qpixmap(region_image)
        scene.addPixmap(pixmap)
        view.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
        layout.addWidget(view)

        btn_save_region = QPushButton("Сохранить участок")
        btn_save_region.clicked.connect(lambda: self.save_region(region_image))
        layout.addWidget(btn_save_region)

        window.setLayout(layout)
        window.resize(400, 400)
        window.show()
        
        self.region_windows.append(window)
        self.region_windows = [w for w in self.region_windows if w.isVisible()]

    def save_region(self, region_image):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить участок", "", "PNG Files (*.png)")
        if file_path:
            region_image.save(file_path, format="PNG", dpi=self.input_map.info.get("dpi", (72, 72)))
            self.parent.log_text_edit.append(f"Участок сохранен: {file_path}")

class LogTab(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
    
    def append(self, text):
        self.text_edit.append(text)