import os
import math
import threading
import logging
from tkinter import Tk, Button, Text, END, filedialog, Label, Entry, StringVar, Scrollbar, RIGHT, Y, LEFT, BOTH, Frame
from PIL import Image

# Отключаем ограничение на максимальное число пикселей
Image.MAX_IMAGE_PIXELS = None

# Создаем логгер
logger = logging.getLogger("TileGenerator")
logger.setLevel(logging.DEBUG)

# Обработчик логов для Text виджета
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(END)
        self.text_widget.after(0, append)

# Функция нарезки тайлов с конвертацией в 8-битный режим
def generate_tiles(input_image_path, output_folder, max_zoom=7, tile_size=256):
    logger.info(f"Открываем изображение: {input_image_path}")
    try:
        img = Image.open(input_image_path).convert("RGBA")
    except Exception as e:
        logger.error(f"Ошибка открытия изображения: {e}")
        return

    orig_width, orig_height = img.size
    logger.info(f"Размер изображения: {orig_width}x{orig_height}")
    
    os.makedirs(output_folder, exist_ok=True)
    
    for z in range(0, max_zoom + 1):
        scale = 1 / (2 ** (max_zoom - z))
        level_width = math.ceil(orig_width * scale)
        level_height = math.ceil(orig_height * scale)
        logger.info(f"Уровень {z}: scale={scale:.4f}, размер {level_width}x{level_height}")
        
        level_img = img.resize((level_width, level_height), Image.LANCZOS)
        tiles_x = math.ceil(level_width / tile_size)
        tiles_y = math.ceil(level_height / tile_size)
        padded_width = tiles_x * tile_size
        padded_height = tiles_y * tile_size
        
        padded_img = Image.new("RGBA", (padded_width, padded_height), (0, 0, 0, 0))
        padded_img.paste(level_img, (0, 0))
        
        level_folder = os.path.join(output_folder, str(z))
        os.makedirs(level_folder, exist_ok=True)
        
        for x in range(tiles_x):
            x_folder = os.path.join(level_folder, str(x))
            os.makedirs(x_folder, exist_ok=True)
            for y in range(tiles_y):
                left = x * tile_size
                upper = y * tile_size
                right = left + tile_size
                lower = upper + tile_size
                tile = padded_img.crop((left, upper, right, lower))
                # Конвертируем в 8-битный режим
                tile8 = tile.convert("P", palette=Image.ADAPTIVE, colors=256)
                tile_path = os.path.join(x_folder, f"{y}.png")
                tile8.save(tile_path, optimize=True)
                logger.debug(f"Сохранен тайл: {tile_path}")
        logger.info(f"Уровень {z} завершён: {tiles_x}x{tiles_y} тайлов.")
    logger.info("Нарезка завершена.")

# Функции для работы с GUI
def start_generation():
    input_path = filedialog.askopenfilename(title="Выберите изображение", filetypes=[("PNG файлы", "*.png"), ("Все файлы", "*.*")])
    if not input_path:
        return
    input_label_var.set(input_path)
    
def run_generation():
    input_path = input_label_var.get()
    if not input_path:
        logger.error("Сначала выберите изображение!")
        return
    output_folder = output_folder_var.get()
    if not output_folder:
        logger.error("Укажите папку для сохранения тайлов!")
        return
    try:
        max_zoom_val = int(max_zoom_var.get())
    except ValueError:
        logger.error("Некорректное значение максимального зума!")
        return
    threading.Thread(target=generate_tiles, args=(input_path, output_folder, max_zoom_val, 256), daemon=True).start()

# Создаем главное окно
root = Tk()
root.title("Генератор тайлов для Leaflet")

input_label_var = StringVar()
output_folder_var = StringVar(value="maps/chernarus/")
max_zoom_var = StringVar(value="7")

frame = Frame(root)
frame.pack(padx=10, pady=10, fill=BOTH, expand=True)

Label(frame, text="Изображение:").pack(anchor="w")
input_entry = Entry(frame, textvariable=input_label_var, width=80)
input_entry.pack(anchor="w", fill="x")
Button(frame, text="Выбрать изображение", command=start_generation).pack(anchor="w", pady=(0,10))

Label(frame, text="Папка для тайлов:").pack(anchor="w")
output_entry = Entry(frame, textvariable=output_folder_var, width=80)
output_entry.pack(anchor="w", fill="x", pady=(0,10))

Label(frame, text="Максимальный зум:").pack(anchor="w")
max_zoom_entry = Entry(frame, textvariable=max_zoom_var, width=10)
max_zoom_entry.pack(anchor="w", pady=(0,10))

Button(frame, text="Начать генерацию тайлов", command=run_generation).pack(anchor="w", pady=(0,10))

log_frame = Frame(root)
log_frame.pack(padx=10, pady=10, fill=BOTH, expand=True)
scrollbar = Scrollbar(log_frame)
scrollbar.pack(side=RIGHT, fill=Y)
log_text = Text(log_frame, state='disabled', wrap='word')
log_text.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar.config(command=log_text.yview)

text_handler = TextHandler(log_text)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
text_handler.setFormatter(formatter)
logger.addHandler(text_handler)

root.mainloop()
