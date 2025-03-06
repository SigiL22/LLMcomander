import os
import logging
import sqlite3
from flask import Flask, send_from_directory, abort, request, jsonify

# Создаем приложение, указывая папку для статических файлов
app = Flask(__name__, static_folder="static", static_url_path="")

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TileServer")

# Папка с тайлами
TILES_FOLDER = "maps/chernarus/"
CACHE_TIMEOUT = 86400  # 24 часа

@app.before_request
def log_request_info():
    logger.debug(f"Запрос: {request.method} {request.url} от {request.remote_addr}")

# Маршрут для корневого URL, отдающий index.html из папки static
@app.route("/")
def serve_index():
    return app.send_static_file("index.html")

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    logger.info(f"Запрос тайла: z={z}, x={x}, y={y}")
    tile_dir = os.path.join(TILES_FOLDER, str(z), str(x))
    tile_filename = f"{y}.png"
    tile_path = os.path.join(tile_dir, tile_filename)
    if os.path.exists(tile_path):
        logger.debug(f"Отправка файла: {tile_path}")
        response = send_from_directory(tile_dir, tile_filename)
        response.cache_control.max_age = CACHE_TIMEOUT
        response.cache_control.public = True
        return response
    else:
        logger.error(f"Тайл не найден: {tile_path}")
        abort(404)

# Эндпоинт для получения названий из базы данных
@app.route("/names")
def get_names():
    db_path = os.path.join("db", "name.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Позволяет обращаться к строкам как к словарям
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names")
        rows = cur.fetchall()
        names_list = [dict(row) for row in rows]
        conn.close()
        return jsonify(names_list)
    except Exception as e:
        logger.error("Ошибка при чтении базы данных: %s", e)
        abort(500)

if __name__ == "__main__":
    logger.info("Запуск сервера TileServer на http://localhost:5000")
    app.run(debug=True, port=5000)
