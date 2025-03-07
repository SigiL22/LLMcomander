import os
import logging
import sqlite3
import base64
import os
from flask import Flask, send_from_directory, abort, request, jsonify

app = Flask(__name__, static_folder="static", static_url_path="")

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TileServer")

# Папка с тайлами
TILES_FOLDER = "maps/chernarus/"
SNAPSHOTS_FOLDER = "snapshots"
CACHE_TIMEOUT = 86400  # 24 часа
TRANSPARENT_TILE = "transparent.png"  # Файл должен находиться в папке static

os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True)

@app.before_request
def log_request_info():
    logger.debug(f"Запрос: {request.method} {request.url} от {request.remote_addr}")

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route("/")
def serve_index():
    return app.send_static_file("index.html")

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    #logger.info(f"Запрос тайла: z={z}, x={x}, y={y}")
    if x < 0 or y < 0:
        logger.error(f"Отрицательные индексы тайла: x={x}, y={y}")
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)
        
    tile_dir = os.path.join(TILES_FOLDER, str(z), str(x))
    tile_filename = f"{y}.png"
    tile_path = os.path.join(tile_dir, tile_filename)
    if os.path.exists(tile_path):
        #logger.debug(f"Отправка файла: {tile_path}")
        response = send_from_directory(tile_dir, tile_filename)
        response.cache_control.max_age = CACHE_TIMEOUT
        response.cache_control.public = True
        return response
    else:
        logger.error(f"Тайл не найден: {tile_path}")
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)

@app.route("/save_snapshot", methods=["POST"])
def save_snapshot():
    data = request.get_json()
    if not data or "image" not in data or "filename" not in data:
        abort(400, "Неверные параметры")
    
    image_data = data["image"].split(',')[1]
    filename = data["filename"]
    file_path = os.path.join(SNAPSHOTS_FOLDER, filename)
    
    try:
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(image_data))
        logger.info(f"Снимок сохранен: {file_path}")
        return jsonify({"status": "success", "path": file_path}), 200
    except Exception as e:
        logger.error(f"Ошибка сохранения снимка: {e}")
        abort(500)
        
@app.route("/names")
def get_names():
    db_path = os.path.join("db", "name.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names")
        rows = cur.fetchall()
        names_list = [dict(row) for row in rows]
        conn.close()
        return jsonify(names_list)
    except Exception as e:
        logger.error("Ошибка при чтении базы данных: %s", e)
        abort(500)

# Новый эндпоинт для обновления существующей надписи
@app.route("/update_label", methods=["POST"])
def update_label():
    data = request.get_json()
    if not data or "id" not in data or "x" not in data or "y" not in data:
        abort(400, "Неверные параметры")
    db_path = os.path.join("db", "name.db")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE names SET x = ?, y = ? WHERE id = ?", (data["x"], data["y"], data["id"]))
        conn.commit()
        conn.close()
        logger.info(f"Надпись id={data['id']} обновлена: x={data['x']}, y={data['y']}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error("Ошибка при обновлении надписи: %s", e)
        abort(500)

# Новый эндпоинт для добавления новой надписи
@app.route("/add_label", methods=["POST"])
def add_label():
    data = request.get_json()
    if not data or "name" not in data or "type" not in data or "x" not in data or "y" not in data:
        abort(400, "Неверные параметры")
    db_path = os.path.join("db", "name.db")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO names (name, type, x, y) VALUES (?, ?, ?, ?)",
                    (data["name"], data["type"], data["x"], data["y"]))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        logger.info(f"Добавлена новая надпись id={new_id}: {data}")
        return jsonify({"status": "success", "id": new_id}), 200
    except Exception as e:
        logger.error("Ошибка при добавлении надписи: %s", e)
        abort(500)
        
# Папка для сохранения снимков
SNAPSHOTS_FOLDER = "snapshots"
os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True)

if __name__ == "__main__":
    logger.info("Запуск сервера TileServer на http://localhost:5000")
    app.run(debug=True, port=5000)
