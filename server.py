import os
import logging
import sqlite3
import base64
import threading
from flask import Flask, send_from_directory, abort, request, jsonify, Response
import arma_connector
import time
import json

# Указываем путь к static и db явно
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DB_DIR = os.path.join(BASE_DIR, 'db')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

# Настройка логирования (только ошибки и инфо)
logger = logging.getLogger("Server")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Константы
TILES_FOLDER = "maps/chernarus/"
SNAPSHOTS_FOLDER = "snapshots"
CACHE_TIMEOUT = 86400
TRANSPARENT_TILE = "transparent.png"
os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True)

# Переменная для хранения интервала обновления (в секундах)
update_interval = 3  # По умолчанию 3 секунды
update_thread = None
update_running = False

def send_update_request():
    global update_running
    while update_running:
        try:
            arma_connector.send_callback_to_arma({"command": "update_data"})
            logger.info("Команда update_data отправлена в ARMA")
        except Exception as e:
            logger.error(f"Ошибка отправки команды update_data: {e}")
        time.sleep(update_interval)

# Явный маршрут для статических файлов
@app.route('/static/<path:filename>')
def serve_static(filename):
    logger.debug(f"Попытка отдать файл: {filename}")
    return send_from_directory(STATIC_DIR, filename)

@app.route("/arma_data", methods=["GET"])
def get_arma_data():
    with arma_connector.lock:
        logger.debug(f"GET /arma_data: Current data = {arma_connector.data}")
        if arma_connector.data is None:
            logger.info("GET /arma_data: No data available")
            return jsonify({"status": "no_data"}), 200
        return jsonify({"status": "success", "data": arma_connector.data}), 200

@app.route("/arma_data_stream")
def arma_data_stream():
    def event_stream():
        last_data = None
        while True:
            with arma_connector.lock:
                if arma_connector.data != last_data and arma_connector.data is not None:
                    last_data = arma_connector.data
                    logger.debug(f"SSE: Sending data - {last_data}")
                    yield f"data: {json.dumps({'status': 'success', 'data': last_data})}\n\n"
            time.sleep(0.1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/send_callback", methods=["POST"])
def send_callback_endpoint():
    data = request.get_json()
    if not data:
        logger.error("Неверные параметры в /send_callback")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400
    try:
        arma_connector.send_callback_to_arma(data)
        logger.info(f"Callback отправлен: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Ошибка в /send_callback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/set_update_interval", methods=["POST"])
def set_update_interval():
    global update_interval, update_running, update_thread
    data = request.get_json()
    if not data or "interval" not in data:
        logger.error("Неверные параметры в /set_update_interval")
        return jsonify({"status": "error", "message": "Missing interval"}), 400
    new_interval = int(data["interval"])
    if new_interval < 1:
        logger.error("Интервал должен быть больше 0")
        return jsonify({"status": "error", "message": "Interval must be positive"}), 400
    
    update_interval = new_interval
    if update_running:
        update_running = False
        update_thread.join()  # Ожидаем завершения старого потока
    update_running = True
    update_thread = threading.Thread(target=send_update_request, daemon=True)
    update_thread.start()
    logger.info(f"Установлен интервал обновления: {update_interval} секунд")
    return jsonify({"status": "success", "interval": update_interval}), 200

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
    if x < 0 or y < 0:
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)
    tile_dir = os.path.join(TILES_FOLDER, str(z), str(x))
    tile_filename = f"{y}.png"
    tile_path = os.path.join(tile_dir, tile_filename)
    if os.path.exists(tile_path):
        response = send_from_directory(tile_dir, tile_filename)
        response.cache_control.max_age = CACHE_TIMEOUT
        response.cache_control.public = True
        return response
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
        return jsonify({"status": "success", "path": file_path}), 200
    except Exception as e:
        logger.error(f"Ошибка сохранения снимка: {e}")
        abort(500)

@app.route("/names")
def get_names():
    db_path = os.path.join(DB_DIR, "name.db")
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
        logger.error(f"Ошибка чтения базы данных: {e}")
        abort(500)

@app.route("/update_label", methods=["POST"])
def update_label():
    data = request.get_json()
    if not data or "id" not in data or "x" not in data or "y" not in data:
        abort(400, "Неверные параметры")
    db_path = os.path.join(DB_DIR, "name.db")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE names SET x = ?, y = ? WHERE id = ?", (data["x"], data["y"], data["id"]))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Ошибка обновления надписи: {e}")
        abort(500)

@app.route("/add_label", methods=["POST"])
def add_label():
    data = request.get_json()
    if not data or "name" not in data or "type" not in data or "x" not in data or "y" not in data:
        abort(400, "Неверные параметры")
    db_path = os.path.join(DB_DIR, "name.db")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO names (name, type, x, y) VALUES (?, ?, ?, ?)", 
                    (data["name"], data["type"], data["x"], data["y"]))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return jsonify({"status": "success", "id": new_id}), 200
    except Exception as e:
        logger.error(f"Ошибка добавления надписи: {e}")
        abort(500)

@app.route("/send_to_arma", methods=["POST"])
def send_to_arma_endpoint():
    data = request.get_json()
    if not data:
        abort(400, "Неверные параметры")
    try:
        arma_connector.send_to_arma(data)
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Ошибка отправки в ARMA: {e}")
        abort(500)

# Новые эндпоинты для работы с базами зданий и названий
@app.route("/get_buildings", methods=["POST"])
def get_buildings():
    area = request.get_json()
    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "buildings.db")  # Путь к базе buildings.db
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, x, y, z, interior FROM buildings WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        buildings = [{'id': row['id'], 'name': row['name'], 'x': row['x'], 'y': row['y'], 'z': row['z'], 'interior': row['interior']} for row in cur.fetchall()]
        conn.close()
        logger.info(f"Получено зданий: {len(buildings)} для области {min_x},{min_y} - {max_x},{max_y}")
        return jsonify(buildings)
    except Exception as e:
        logger.error(f"Ошибка получения зданий: {e}")
        abort(500)

# Новый маршрут для названий в области
@app.route("/get_names_in_area", methods=["POST"])
def get_names_in_area():
    area = request.get_json()
    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "name.db")  # Путь к базе name.db
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        names = [{'id': row['id'], 'name': row['name'], 'type': row['type'], 'x': row['x'], 'y': row['y']} for row in cur.fetchall()]
        conn.close()
        logger.info(f"Получено названий: {len(names)} для области {min_x},{min_y} - {max_x},{max_y}")
        return jsonify(names)
    except Exception as e:
        logger.error(f"Ошибка получения названий: {e}")
        abort(500)

@app.route("/save_json", methods=["POST"])
def save_json():
    data = request.get_json()
    if not data or "filename" not in data or "data" not in data:
        logger.error("Неверные параметры в /save_json")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400
    filename = data["filename"]
    content = data["data"]
    file_path = os.path.join(BASE_DIR, filename)
    try:
        with open(file_path, 'w') as f:
            json.dump(content, f)
        logger.info(f"JSON сохранен: {file_path}")
        return jsonify({"status": "success", "filename": filename}), 200
    except Exception as e:
        logger.error(f"Ошибка сохранения JSON: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    threading.Thread(target=arma_connector.run_server, daemon=True).start()
    update_running = True
    update_thread = threading.Thread(target=send_update_request, daemon=True)
    update_thread.start()
    logger.info("Сервер запущен на http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)