from PIL import Image
from PyQt5.QtGui import QPixmap, QImage
import os

def pil_image_to_qpixmap(pil_image):
    pil_image = pil_image.convert("RGBA")
    data = pil_image.tobytes("raw", "RGBA")
    qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage)
    
def find_font_path(font_family, bold=False, italic=False, default_path="C:/Windows/Fonts/arial.ttf"):
    """Поиск пути к файлу шрифта по имени семейства и стилю на Windows."""
    font_dir = "C:/Windows/Fonts/"
    font_map = {
        "Arial": {
            (False, False): "arial.ttf",  # Обычный
            (True, False): "arialbd.ttf",  # Жирный
            (False, True): "ariali.ttf",   # Курсив
            (True, True): "arialbi.ttf"    # Жирный курсив
        },
        "Times New Roman": {
            (False, False): "times.ttf",
            (True, False): "timesbd.ttf",
            (False, True): "timesi.ttf",
            (True, True): "timesbi.ttf"
        },
        "Courier New": {
            (False, False): "cour.ttf",
            (True, False): "courbd.ttf",
            (False, True): "couri.ttf",
            (True, True): "courbi.ttf"
        },
        "Verdana": {
            (False, False): "verdana.ttf",
            (True, False): "verdanab.ttf",
            (False, True): "verdanai.ttf",
            (True, True): "verdanaz.ttf"
        }
    }
    
    style_key = (bold, italic)
    font_dict = font_map.get(font_family)
    if font_dict:
        font_filename = font_dict.get(style_key)
        if font_filename:
            full_path = os.path.join(font_dir, font_filename)
            if os.path.exists(full_path):
                return full_path
    
    # Fallback на обычный шрифт, если стиль не найден
    if font_family in font_map and (False, False) in font_map[font_family]:
        full_path = os.path.join(font_dir, font_map[font_family][(False, False)])
        if os.path.exists(full_path):
            return full_path
    
    # Fallback на default_path
    if os.path.exists(default_path):
        return default_path
    return None