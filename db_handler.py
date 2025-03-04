import sqlite3
import os

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    type TEXT,
    x REAL,
    y REAL
);
"""

def create_db(db_path, log_func=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(DB_SCHEMA)
    conn.commit()
    conn.close()
    if log_func:
        log_func(f"База создана или уже существует: {db_path}")

def parse_names_file(file_path, db_path, log_func=None):
    """
    Читает файл name.txt, где каждая строка имеет формат:
      1:05:07 "Локация: Черногорск | Тип: NameCityCapital | Позиция: [6731.21,2554.13]"
    и вставляет данные в базу данных.
    Координаты округляются до целого числа.
    Временная метка отброшена.
    """
    if not os.path.exists(file_path):
        if log_func:
            log_func(f"Файл с именами {file_path} не найден.")
        return

    create_db(db_path, log_func)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                # Находим содержимое внутри кавычек
                first_quote = line.find('"')
                last_quote = line.rfind('"')
                if first_quote == -1 or last_quote == -1 or first_quote == last_quote:
                    continue
                content = line[first_quote+1:last_quote]
                # Разбиваем по разделителю " | "
                parts = [p.strip() for p in content.split("|")]
                # Ожидаемый формат:
                # "Локация: Черногорск", "Тип: NameCityCapital", "Позиция: [6731.21,2554.13]"
                name = parts[0].split(":", 1)[1].strip()
                type_val = parts[1].split(":", 1)[1].strip()
                pos_str = parts[2].split(":", 1)[1].strip()  # "[6731.21,2554.13]"
                pos_str = pos_str.strip("[]")
                coords = pos_str.split(',')
                # Согласно инструкции: первая координата – X, вторая – Y
                x = round(float(coords[0].strip()))
                y = round(float(coords[1].strip()))
                cur.execute("INSERT INTO names (name, type, x, y) VALUES (?, ?, ?, ?)",
                            (name, type_val, x, y))
                if log_func:
                    log_func(f"Добавлена запись: {name}, {type_val}, x={x}, y={y}")
            except Exception as e:
                if log_func:
                    log_func(f"Ошибка при разборе строки: '{line}': {e}")
    conn.commit()
    conn.close()
    if log_func:
        log_func("Парсинг файла с именами завершен.")

def get_names(db_path, log_func=None):
    """
    Возвращает список записей из таблицы names в виде списка словарей.
    """
    if not os.path.exists(db_path):
        if log_func:
            log_func(f"База {db_path} не найдена.")
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM names")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]
