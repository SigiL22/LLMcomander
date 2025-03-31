import os
import logging
import sqlite3
import base64
import threading
import asyncio
from flask import Flask, send_from_directory, abort, request, jsonify, Response
import arma_connector
import time
import json
from queue import Queue
from llm_client import LLMClient
from llm_data_processor import LLMDataProcessor  # Импорт нового модуля

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DB_DIR = os.path.join(BASE_DIR, 'db')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

logger = logging.getLogger("Server")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

TILES_FOLDER = "maps/chernarus/"
SNAPSHOTS_FOLDER = "snapshots"
CACHE_TIMEOUT = 86400
TRANSPARENT_TILE = "transparent.png"
os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True)

update_interval = 10  # По умолчанию 10 секунд
update_thread = None
update_running = False
update_lock = threading.Lock()

reports_queue = Queue()
llm_client = None
system_prompt_sent = False
llm_data_processor = None

# Хранилище настроек миссии
mission_settings = {
    "updateInterval": 60,
    "llmSide": "OPFOR",
    "preset": None,
    "displaySide": None,
    "llmModel": None,
    "llmUpdateInterval": 30  # Новый параметр для интервала отправки данных в LLM
}

# Инициализация LLM клиента и процессора данных
def initialize_llm():
    global llm_client, llm_data_processor
    llm_client = LLMClient("config.json")
    llm_client.start_session("arma_session")
    llm_data_processor = LLMDataProcessor("config.json", default_interval=mission_settings["llmUpdateInterval"])
    llm_data_processor.start(app)
    logger.info("LLM сессия и процессор данных успешно созданы")

def send_update_request():
    global update_running
    while arma_connector.data is None:
        time.sleep(3)
    logger.info("Миссия стартовала, начинаем отправку update_data")
    
    while update_running:
        try:
            arma_connector.send_callback_to_arma({"command": "update_data"})
            logger.info(f"Команда update_data отправлена в ARMA, следующий вызов через {update_interval} сек")
            time.sleep(update_interval)
        except Exception as e:
            logger.error(f"Ошибка отправки команды update_data: {e}")
            time.sleep(1)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route("/arma_data", methods=["GET"])
def get_arma_data():
    with arma_connector.lock:
        if arma_connector.data is None:
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
                    yield f"data: {json.dumps({'status': 'success', 'data': last_data})}\n\n"
            time.sleep(0.1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/reports_stream")
def reports_stream():
    def event_stream():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            if not arma_connector.reports_queue.empty():
                report = arma_connector.reports_queue.get()
                logger.debug(f"SSE: Sending report - {report}")
                if report.get("command") == "start_mission" and not system_prompt_sent:
                    loop.run_until_complete(send_system_prompt())
                yield f"data: {json.dumps(report)}\n\n"
            time.sleep(0.1)
    return Response(event_stream(), mimetype="text/event-stream")

async def send_system_prompt():
    global system_prompt_sent
    if llm_client and "arma_session" in llm_client.chat_sessions and not system_prompt_sent:
        logger.info("Отправка системного промпта в LLM...")
        await llm_client.send_system_prompt("arma_session")
        system_prompt_sent = True
        logger.info("Системный промпт успешно отправлен")

@app.route("/send_callback", methods=["POST"])
def send_callback_endpoint():
    data = request.get_json()
    if not data:
        logger.error("Неверные параметры в /send_callback")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400
    try:
        if "t" in data and data["t"] in ["enemy_detected", "vehicle_detected"]:
            reports_queue.put(data)
            logger.info(f"Получен доклад от LLMextension: {data}")
        elif data.get("command") != "update_data":
            arma_connector.send_callback_to_arma(data)
            logger.info(f"Callback отправлен в Arma: {data}")
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
    new_interval = min(max(int(data["interval"]), 1), 60)
    with update_lock:
        update_interval = new_interval
        mission_settings["updateInterval"] = new_interval  # Синхронизация с mission_settings
        if update_running:
            update_running = False
            if update_thread:
                update_thread.join()
        update_running = True
        update_thread = threading.Thread(target=send_update_request, daemon=True)
        update_thread.start()
    logger.info(f"Установлен интервал обновления игры: {update_interval} секунд")
    return jsonify({"status": "success", "interval": update_interval}), 200

@app.route("/set_llm_update_interval", methods=["POST"])
def set_llm_update_interval():
    data = request.get_json()
    if not data or "interval" not in data:
        return jsonify({"status": "error", "message": "Отсутствует параметр interval"}), 400
    interval = min(max(int(data["interval"]), 1), 300)
    mission_settings["llmUpdateInterval"] = interval
    logger.info(f"Установлен интервал обновления LLM: {interval} секунд")
    return jsonify({"status": "success", "interval": interval}), 200

@app.route("/get_mission_settings", methods=["GET"])
def get_mission_settings():
    return jsonify({"status": "success", "settings": mission_settings})

@app.route("/llm_command", methods=["POST"])
async def llm_command():
    global llm_client, system_prompt_sent
    if not llm_client or "arma_session" not in llm_client.chat_sessions:
        return jsonify({"status": "error", "message": "LLM сессия не инициализирована"}), 500
    
    if not system_prompt_sent:
        return jsonify({"status": "error", "message": "Системный промпт еще не отправлен, ждите начала миссии"}), 503
    
    data = request.get_json()
    if not data or "json_input" not in data:
        return jsonify({"status": "error", "message": "Отсутствует json_input"}), 400
    
    json_input = data["json_input"]
    png_path = data.get("png_path")
    
    json_input["side"] = mission_settings["llmSide"]
    
    try:
        response = await llm_client.send_message("arma_session", json_input, png_path)
        if response:
            return jsonify({"status": "success", "response": response}), 200
        else:
            return jsonify({"status": "error", "message": "Пустой ответ от LLM"}), 500
    except Exception as e:
        logger.error(f"Ошибка в llm_command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Оставшиеся маршруты остаются без изменений...

if __name__ == "__main__":
    logger.info("Запуск сервера...")
    initialize_llm()  # Инициализация LLM и процессора данных
    threading.Thread(target=arma_connector.run_server, daemon=True).start()
    update_running = True
    update_thread = threading.Thread(target=send_update_request, daemon=True)
    update_thread.start()
    logger.info("Сервер запущен на http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)