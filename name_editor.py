from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsRectItem
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QFont, QPen, QColor, QBrush
import os
from db_handler import get_names, update_name_position
from map_processing import world_to_pixel, draw_grid
from utils import pil_image_to_qpixmap

class NameEditor:
    def __init__(self, map_tab, image_with_grid, image_without_names, db_path, type_settings, origin, scale, global_width, global_height, params, log_func=None):
        self.map_tab = map_tab
        self.image_with_grid = image_with_grid
        self.image_without_names = image_without_names
        self.db_path = db_path
        self.type_settings = type_settings
        self.origin = origin
        self.scale = scale
        self.global_width = global_width
        self.global_height = global_height
        self.log_func = log_func
        self.names = get_names(db_path, log_func)
        self.editable_items = {}  # Словарь для хранения надписей по id
        self.modified_items = {}  # Словарь для изменённых позиций
        self.scene = map_tab.scene
        self.is_editing = False
        self.selected_item = None
        self.selection_rect = None

    def start_editing(self):
        if self.is_editing:
            return
        self.is_editing = True
        self.scene.clear()
        self.editable_items.clear()  # Очищаем перед загрузкой
        
        # Добавляем карту как фон
        pixmap_item = self.scene.addPixmap(pil_image_to_qpixmap(self.image_with_grid))
        pixmap_item.setZValue(-1)  # Фон ниже надписей
        
        # Загружаем надписи из базы
        for rec in self.names:
            name = rec["name"]
            rec_type = rec["type"]
            world_x = float(rec["x"])
            world_y = float(rec["y"])
            px, py = self.world_to_pixel(world_x, world_y)
            
            settings = self.type_settings.get(rec_type, {"font_size": 12, "font_color": (0, 0, 0, 255)})
            font_size = settings["font_size"]
            
            text_item = QGraphicsTextItem(name)
            text_item.setFont(QFont("Arial", int(font_size * 0.85)))  # Уменьшаем шрифт для соответствия
            text_item.setDefaultTextColor(QColor(*settings["font_color"]))
            text_item.setPos(px, py)
            text_item.setFlag(QGraphicsTextItem.ItemIsSelectable, True)
            text_item.setFlag(QGraphicsTextItem.ItemIsMovable, False)
            text_item.rec_id = rec["id"]  # Уникальный ID из базы
            text_item.setZValue(1)  # Надписи поверх фона
            self.scene.addItem(text_item)
            self.editable_items[rec["id"]] = text_item
            
            if self.log_func:
                self.log_func(f"Добавлена надпись: id={rec['id']}, текст={name}, pos=({px}, {py})")

    def stop_editing(self):
        if not self.is_editing:
            return
        self.is_editing = False
        self.selected_item = None
        if self.selection_rect:
            self.scene.removeItem(self.selection_rect)
            self.selection_rect = None
        self.scene.clear()
        self.map_tab.update_view(self.map_tab.processed_map)
        if self.log_func:
            self.log_func("Режим редактирования завершён")

    def select_item(self, item):
        if self.is_editing and item in self.editable_items.values():
            if self.selected_item and self.selected_item != item:
                self.selected_item.setFlag(QGraphicsTextItem.ItemIsMovable, False)
                if self.selection_rect:
                    self.scene.removeItem(self.selection_rect)
                    self.selection_rect = None
            
            self.selected_item = item
            self.selected_item.setFlag(QGraphicsTextItem.ItemIsMovable, True)
            
            # Создаём или обновляем рамку
            if not self.selection_rect:
                bbox = item.boundingRect()
                self.selection_rect = QGraphicsRectItem(bbox)
                self.selection_rect.setPen(QPen(QColor(255, 0, 0, 255), 2))
                self.selection_rect.setBrush(QBrush(Qt.NoBrush))
                self.selection_rect.setZValue(2)  # Рамка выше надписей
                self.scene.addItem(self.selection_rect)
            self.selection_rect.setPos(item.pos())
            self.selection_rect.setRect(item.boundingRect())
            
            if self.log_func:
                self.log_func(f"Выбрана надпись: id={item.rec_id}, текст={item.toPlainText()}, pos={item.pos()}")

    def item_moved(self, item):
        if self.is_editing and item == self.selected_item:
            new_pos = item.pos()
            world_x, world_y = self.pixel_to_world(new_pos.x(), new_pos.y())
            self.modified_items[item.rec_id] = (world_x, world_y)
            if self.selection_rect:
                self.selection_rect.setPos(new_pos)  # Рамка следует за надписью
            if self.log_func:
                self.log_func(f"Надпись перемещена: id={item.rec_id}, новые координаты=({world_x:.2f}, {world_y:.2f})")

    def save_changes(self):
        if not self.modified_items:
            if self.log_func:
                self.log_func("Нет изменений для сохранения")
            return
        for rec_id, (world_x, world_y) in self.modified_items.items():
            update_name_position(self.db_path, rec_id, world_x, world_y, self.log_func)
        self.modified_items.clear()
        self.map_tab.apply_grid()  # Перерисовываем карту с обновлёнными позициями
        if self.log_func:
            self.log_func("Изменения сохранены в базу")

    def world_to_pixel(self, world_x, world_y):
        if self.origin == "bottom-left":
            px = world_x * self.scale
            py = self.global_height - world_y * self.scale
        # Добавьте другие варианты origin, если используются
        return px, py

    def pixel_to_world(self, px, py):
        if self.origin == "bottom-left":
            world_x = px / self.scale
            world_y = (self.global_height - py) / self.scale
        return world_x, world_y