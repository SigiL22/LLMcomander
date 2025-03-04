from PIL import Image, ImageDraw, ImageFont
import math
import os

def resize_image(input_image, output_size):
    return input_image.resize(output_size, resample=Image.LANCZOS)

def draw_grid(image, pixels_per_100m, grid_thickness_100, grid_thickness_1km, 
              color_100, color_1km, label_mode_h, label_mode_v, 
              font_size, font_path, font_color, margin, origin="top-left", 
              offset_x=0, offset_y=0, log_func=None):
    from PIL import Image, ImageDraw, ImageFont
    import math
    import os

    width, height = image.size
    interval = pixels_per_100m
    total_cols = math.floor(width / interval) + (1 if width % interval > 0 else 0)
    total_rows = math.floor(height / interval) + (1 if height % interval > 0 else 0)
    
    if log_func:
        log_func(f"draw_grid: size=({width},{height}), interval={interval}, total_cols={total_cols}, total_rows={total_rows}, origin={origin}, offset_x={offset_x}, offset_y={offset_y}")
    
    # Подготовка шрифта
    if not os.path.exists(font_path):
        if log_func:
            log_func(f"Шрифт не найден по пути: {font_path}, использую шрифт по умолчанию")
        font = ImageFont.load_default()
    else:
        try:
            font = ImageFont.truetype(font_path, font_size)
            if log_func:
                log_func(f"Шрифт успешно загружен: size={font_size}, path={font_path}")
        except Exception as e:
            if log_func:
                log_func(f"Ошибка загрузки шрифта '{font_path}': {e}, использую шрифт по умолчанию")
            font = ImageFont.load_default()
    
    # Определяем позиции линий и меток
    if origin in ("top-left", "bottom-left"):
        h_line_positions = [i * interval for i in range(total_cols + 1)]
        h_label_positions = [i * interval + interval / 2 for i in range(total_cols)]
        h_labels = [offset_x + i for i in range(total_cols)]
    else:
        h_line_positions = [width - i * interval for i in range(total_cols + 1)]
        h_label_positions = [width - (i * interval + interval / 2) for i in range(total_cols)]
        h_labels = [offset_x + i for i in range(total_cols)]
    
    if origin in ("top-left", "top-right"):
        v_line_positions = [i * interval for i in range(total_rows + 1)]
        v_label_positions = [i * interval + interval / 2 for i in range(total_rows)]
        v_labels = [offset_y + i for i in range(total_rows)]
    else:
        v_line_positions = [height - i * interval for i in range(total_rows + 1)]
        v_label_positions = [height - (i * interval + interval / 2) for i in range(total_rows)]
        v_labels = [offset_y + i for i in range(total_rows)]
    
    if log_func:
        log_func(f"Горизонтальные линии: позиции={h_line_positions}")
        log_func(f"Горизонтальные метки: значения={h_labels}")
        log_func(f"Горизонтальные метки: позиции={h_label_positions}")
        log_func(f"Вертикальные линии: позиции={v_line_positions}")
        log_func(f"Вертикальные метки: значения={v_labels}")
        log_func(f"Вертикальные метки: позиции={v_label_positions}")
    
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Отрисовка линий
    for pos in h_line_positions:
        if origin in ("top-left", "bottom-left"):
            local_index = int(pos // interval)
        else:
            local_index = int((width - pos) // interval)
        global_x = offset_x + local_index
        is_km_line = (global_x % 10 == 0)
        thickness = grid_thickness_1km if is_km_line else grid_thickness_100
        line_color = color_1km if is_km_line else color_100
        if log_func:
            log_func(f"Рисую горизонтальную линию: pos X={pos:.1f}, global_x={global_x}, км-линия={is_km_line}")
        draw_overlay.line([(pos, 0), (pos, height)], fill=line_color, width=thickness)
    
    for pos in v_line_positions:
        if origin in ("top-left", "top-right"):
            local_index = int(pos // interval)
        else:
            local_index = int((height - pos) // interval)
        global_y = offset_y + local_index
        is_km_line = (global_y % 10 == 0)
        thickness = grid_thickness_1km if is_km_line else grid_thickness_100
        line_color = color_1km if is_km_line else color_100
        if log_func:
            log_func(f"Рисую вертикальную линию: pos Y={pos:.1f}, global_y={global_y}, км-линия={is_km_line}")
        draw_overlay.line([(0, pos), (width, pos)], fill=line_color, width=thickness)
    
    # Отрисовка текста на отдельном слое
    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_text = ImageDraw.Draw(text_layer)
    
    for i, cx in enumerate(h_label_positions):
        if -margin <= cx <= width + margin:
            label = f"{(h_labels[i] if label_mode_h == '0' else h_labels[i] + 1):03d}"
            bbox = font.getbbox(label)
            text_width = bbox[2] - bbox[0]
            text_x = max(0, min(width - text_width, cx - text_width / 2))
            text_y = margin
            draw_text.text((text_x, text_y), label, font=font, fill=font_color)
            if log_func:
                log_func(f"Рисую горизонтальную метку: label='{label}', pos X={cx:.1f}, global_x={h_labels[i]}")
    
    for j, cy in enumerate(v_label_positions):
        if -margin <= cy <= height + margin:
            label = f"{(v_labels[j] if label_mode_v == '0' else v_labels[j] + 1):03d}"
            bbox = font.getbbox(label)
            text_height = bbox[3] - bbox[1]
            text_x = margin
            text_y = max(0, min(height - text_height, cy - text_height / 2))
            draw_text.text((text_x, text_y), label, font=font, fill=font_color)
            if log_func:
                log_func(f"Рисую вертикальную метку: label='{label}', pos Y={cy:.1f}, global_y={v_labels[j]}")
    
    # Комбинируем слои
    combined = Image.alpha_composite(image.convert("RGBA"), overlay)
    combined = Image.alpha_composite(combined, text_layer)
    if log_func:
        log_func("Сетка и метки успешно наложены на карту")
    return combined

# Аналогично обновим draw_grid_region
def draw_grid_region(image, pixels_per_100m, grid_thickness_100, grid_thickness_1km, 
                     color_100, color_1km, label_mode_h, label_mode_v, 
                     font_size, font_path, font_color, margin, origin="bottom-left", 
                     offset_x=0, offset_y=0, log_func=None):
    width, height = image.size
    interval = pixels_per_100m

    if log_func:
        log_func(f"Запуск draw_grid_region: width={width}, height={height}, interval={interval}, offset_x={offset_x}, offset_y={offset_y}, origin={origin}")

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    if not os.path.exists(font_path):
        if log_func:
            log_func(f"Шрифт не найден по пути: {font_path}, использую шрифт по умолчанию")
        font = ImageFont.load_default()
    else:
        try:
            font = ImageFont.truetype(font_path, font_size)
            if log_func:
                log_func(f"Шрифт успешно загружен: size={font_size}, path={font_path}")
        except Exception as e:
            if log_func:
                log_func(f"Ошибка загрузки шрифта '{font_path}': {e}, использую шрифт по умолчанию")
            font = ImageFont.load_default()

    def format_label(n, mode):
        base = n if mode == "0" else n + 1
        return f"{base:03d}"

    region_cols = int(width // interval) + (1 if width % interval > 0 else 0)
    h_line_positions = [i * interval for i in range(region_cols)]
    h_line_positions.append(width)
    h_labels = [offset_x + i for i in range(region_cols)]
    h_label_positions = [i * interval + interval / 2 for i in range(region_cols - 1)]
    last_label_x = ((region_cols - 1) * interval + width) / 2
    h_label_positions.append(last_label_x)

    for pos in h_line_positions:
        local_index = int(pos // interval)
        global_x = offset_x + local_index
        is_km_line = (global_x % 10 == 0)
        thickness = grid_thickness_1km if is_km_line else grid_thickness_100
        line_color = color_1km if is_km_line else color_100
        draw_overlay.line([(pos, 0), (pos, height)], fill=line_color, width=thickness)

    for i, cx in enumerate(h_label_positions):
        if -margin <= cx <= width + margin:
            label = format_label(h_labels[i], label_mode_h)
            bbox = font.getbbox(label)
            text_width = bbox[2] - bbox[0]
            text_x = max(0, min(width - text_width, cx - text_width / 2))
            text_y = margin
            draw_overlay.text((text_x, text_y), label, font=font, fill=font_color)

    if origin == "bottom-left":
        full_rows = int(height // interval)
        remainder = height - full_rows * interval
        if remainder > 0:
            region_rows = full_rows + 1
            v_line_positions = [height - i * interval for i in range(full_rows)]
            v_line_positions.append(height - full_rows * interval)
            v_line_positions.append(0)
        else:
            region_rows = full_rows
            v_line_positions = [height - i * interval for i in range(full_rows)]
            v_line_positions.append(0)
        v_label_positions = [(v_line_positions[i] + v_line_positions[i+1]) / 2 for i in range(len(v_line_positions)-1)]
        v_labels = [offset_y + i for i in range(len(v_label_positions))]
    else:
        region_rows = int(height // interval) + (1 if height % interval > 0 else 0)
        v_line_positions = [j * interval for j in range(region_rows + 1)]
        v_label_positions = [j * interval + interval / 2 for j in range(region_rows)]
        v_labels = [offset_y + j for j in range(region_rows)]

    for pos in v_line_positions:
        if origin == "bottom-left":
            local_index = int((height - pos) // interval)
            global_y = offset_y + local_index
        else:
            local_index = int(pos // interval)
            global_y = offset_y + local_index
        is_km_line = (global_y % 10 == 0)
        thickness = grid_thickness_1km if is_km_line else grid_thickness_100
        line_color = color_1km if is_km_line else color_100
        draw_overlay.line([(0, pos), (width, pos)], fill=line_color, width=thickness)

    for j, cy in enumerate(v_label_positions):
        label = format_label(v_labels[j], label_mode_v)
        bbox = font.getbbox(label)
        text_height = bbox[3] - bbox[1]
        text_x = margin
        text_y = max(0, min(height - text_height, cy - text_height / 2))
        draw_overlay.text((text_x, text_y), label, font=font, fill=font_color)

    combined = Image.alpha_composite(image.convert("RGBA"), overlay)
    return combined

# Другие функции (resize_image, world_to_pixel, etc.) остаются без изменений
    
def world_to_pixel(world_x, world_y, image_width, image_height, origin, scale=1.0):
    """
    Преобразует мировые координаты (в метрах) в пиксельные координаты на изображении.
    scale – коэффициент масштабирования.
    """
    if origin == "bottom-left":
        pixel_x = world_x * scale
        pixel_y = image_height - (world_y * scale)
    elif origin == "top-left":
        pixel_x = world_x * scale
        pixel_y = world_y * scale
    elif origin == "top-right":
        pixel_x = image_width - (world_x * scale)
        pixel_y = world_y * scale
    elif origin == "bottom-right":
        pixel_x = image_width - (world_x * scale)
        pixel_y = image_height - (world_y * scale)
    else:
        pixel_x, pixel_y = world_x * scale, world_y * scale
    return pixel_x, pixel_y

def draw_names(image, db_path, type_settings, origin, scale=1.0, crop_offset=None, 
               global_width=None, global_height=None, log_func=None):
    from PIL import ImageDraw, ImageFont
    import os
    try:
        from db_handler import get_names
    except Exception as e:
        if log_func:
            log_func(f"Ошибка импорта db_handler: {e}")
        return image

    names = get_names(db_path, log_func)
    
    # Создаём слой для текста
    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    
    if global_width is None or global_height is None:
        global_width, global_height = image.width, image.height

    for rec in names:
        try:
            name = rec["name"]
            rec_type = rec["type"]
            world_x = float(rec["x"])
            world_y = float(rec["y"])

            px, py = world_to_pixel(world_x, world_y, global_width, global_height, origin, scale)
            if crop_offset is not None:
                px -= crop_offset[0]
                py -= crop_offset[1]
            if not (0 <= px <= image.width and 0 <= py <= image.height):
                continue

            settings = type_settings.get(rec_type, {"font_size": 12, "font_color": (0, 0, 0, 255)})
            font_path = settings.get("font", "C:/Windows/Fonts/arial.ttf")
            if not os.path.exists(font_path):
                if log_func:
                    log_func(f"Шрифт не найден по пути: {font_path}, использую шрифт по умолчанию")
                font = ImageFont.load_default()
            else:
                try:
                    font = ImageFont.truetype(font_path, settings["font_size"])
                    if log_func:
                        log_func(f"Шрифт загружен для '{name}': size={settings['font_size']}, path={font_path}")
                except Exception as e:
                    if log_func:
                        log_func(f"Ошибка загрузки шрифта '{font_path}': {e}, использую шрифт по умолчанию")
                    font = ImageFont.load_default()
            draw.text((px, py), name, font=font, fill=settings["font_color"])
        except Exception as e:
            if log_func:
                log_func(f"Ошибка при отрисовке записи {rec}: {e}")
    
    # Комбинируем слой текста с изображением
    combined = Image.alpha_composite(image.convert("RGBA"), text_layer)
    if log_func:
        log_func("Названия успешно нанесены на карту")
    return combined

def extract_region(image, center_cell, n_cells, pixels_per_100m, origin="bottom-left", log_func=None):
    """
    Извлекает регион из глобальной карты, сохраняя глобальную нумерацию ячеек.
    Возвращает кортеж: (region, start_col, start_row, total_cols, total_rows, crop_box)
    где crop_box = (left, top, right, bottom) в пикселях глобальной карты.
    """
    interval = pixels_per_100m
    col, row = center_cell

    width, height = image.size
    total_cols = math.floor(width / interval) + (1 if width % interval > 0 else 0)
    total_rows = math.floor(height / interval) + (1 if height % interval > 0 else 0)
    
    cells = 2 * n_cells + 1

    # Расчет по оси X
    start_col = col - n_cells
    end_col = col + n_cells
    if start_col < 0:
        start_col = 0
        end_col = cells - 1
    if end_col >= total_cols:
        end_col = total_cols - 1
        start_col = end_col - (cells - 1)
        if start_col < 0:
            start_col = 0

    # Расчет по оси Y
    start_row = row - n_cells
    end_row = row + n_cells
    if origin == "bottom-left":
        if start_row < 0:
            start_row = 0
            end_row = cells - 1
        if end_row >= total_rows:
            end_row = total_rows - 1
            start_row = end_row - (cells - 1)
            if start_row < 0:
                start_row = 0
        # Для bottom-left: 0 – нижняя строка
        top = height - (end_row + 1) * interval
        bottom = height - start_row * interval
    else:  # top-left
        if start_row < 0:
            start_row = 0
            end_row = cells - 1
        if end_row >= total_rows:
            end_row = total_rows - 1
            start_row = end_row - (cells - 1)
            if start_row < 0:
                start_row = 0
        top = start_row * interval
        bottom = (end_row + 1) * interval

    left = start_col * interval
    right = (end_col + 1) * interval
    left = max(0, min(left, width))
    right = max(0, min(right, width))
    top = max(0, min(top, height))
    bottom = max(0, min(bottom, height))

    if log_func:
        log_func(
            f"Extract region: image size=({width},{height}), interval={interval}, total_cols={total_cols}, total_rows={total_rows}, "
            f"center_cell={center_cell}, n_cells={n_cells}, start_col={start_col}, end_col={end_col}, start_row={start_row}, end_row={end_row}, "
            f"crop box=({left}, {top}, {right}, {bottom})"
        )
    
    region = image.crop((left, top, right, bottom))
    crop_box = (left, top, right, bottom)
    return region, start_col, start_row, total_cols, total_rows, crop_box