# --- START OF FILE server.py ---

import os
import logging
import logging.handlers  # Добавлено для FileHandler
import sqlite3
import base64
import threading
import asyncio
from flask import Flask, send_from_directory, abort, request, jsonify, Response
import arma_connector
import time
import json
from queue import Queue  # Оставляем стандартную Queue, т.к. потоки используются синхронно
from llm_client import LLMClient

# --- НАСТРОЙКА ЛОГИРОВАНИЯ (ВЫНЕСЕНА НА ВЕРХНИЙ УРОВЕНЬ) ---
logger = logging.getLogger("Server")
logger.setLevel(logging.INFO)  # Установите INFO или DEBUG по необходимости
logger.propagate = False  # Предотвращаем дублирование логов

# Проверяем, есть ли уже обработчики, чтобы не добавлять их повторно
if not logger.handlers:
    # Форматтер для логов
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Обработчик для вывода в консоль (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    # Обработчик для вывода в файл (RotatingFileHandler)
    log_file = "server.log"  # Имя файла логов
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

logger.info("=" * 20 + " Модуль server.py загружен, логгер настроен " + "=" * 20)
# --- КОНЕЦ НАСТРОЙКИ ЛОГИРОВАНИЯ ---

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DB_DIR = os.path.join(BASE_DIR, 'db')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
logger.info("Объект Flask 'app' создан.")

TILES_FOLDER = "maps/chernarus/"
SNAPSHOTS_FOLDER = "snapshots"
CACHE_TIMEOUT = 86400
TRANSPARENT_TILE = "transparent.png"
os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True) # Убедимся, что папка db существует

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И ИНИЦИАЛИЗАЦИЯ (ВЫНЕСЕНЫ) ---
update_interval = 10  # По умолчанию 10 секунд
update_thread = None
update_running = False # Изначально False, установится в True перед запуском потока
update_lock = threading.Lock()  # Блокировка для управления потоком

reports_queue = arma_connector.reports_queue # Используем очередь из arma_connector напрямую

llm_client = None  # Инициализируется ниже
system_prompt_sent = False  # Флаг отправки системного промпта

# Инициализация LLM клиента
logger.info("Инициализация LLMClient...")
try:
    llm_client = LLMClient(config_file="config.json", system_prompt_file="system_prompt.txt")
    session_id = "arma_session"
    if not llm_client.create_session(session_id):
        logger.error("Не удалось создать сессию LLM. Сервер продолжает работу без LLM.")
    else:
        logger.info("LLM сессия 'arma_session' успешно создана")
except Exception as e:
    logger.exception(f"Критическая ошибка при инициализации LLMClient: {e}")
    # Возможно, стоит прервать запуск сервера, если LLM критичен
    # exit(1)

# Запуск фоновых потоков
logger.info("Запуск фоновых потоков...")
try:
    threading.Thread(target=arma_connector.run_server, daemon=True).start()
    logger.info("Поток arma_connector.run_server запущен.")

    # Функция для потока обновления (перенесена сюда для ясности)
    def send_update_request():
        global update_running, update_interval
        while arma_connector.data is None:
            logger.debug("Ожидание данных миссии перед запуском send_update_request...")
            time.sleep(3)
        logger.info("Миссия стартовала, начинаем отправку update_data")

        while update_running:
            try:
                arma_connector.send_callback_to_arma({"command": "update_data"})
                logger.info(f"Команда update_data отправлена в ARMA, следующий вызов через {update_interval} сек")
                time.sleep(update_interval)
            except Exception as e:
                logger.error(f"Ошибка отправки команды update_data: {e}")
                time.sleep(1) # Пауза перед повторной попыткой
            # Добавим проверку update_running внутри цикла для быстрой остановки
            if not update_running:
                logger.info("Остановка потока send_update_request.")
                break
        logger.info("Поток send_update_request завершен.")


    update_running = True # Теперь устанавливаем флаг перед запуском
    update_thread = threading.Thread(target=send_update_request, daemon=True)
    update_thread.start()
    logger.info("Поток send_update_request запущен.")

except Exception as e:
    logger.exception(f"Ошибка при запуске фоновых потоков: {e}")
# --- КОНЕЦ ГЛОБАЛЬНЫХ ПЕРЕМЕННЫХ И ИНИЦИАЛИЗАЦИИ ---


# --- ОПРЕДЕЛЕНИЯ МАРШРУТОВ FLASK (@app.route) ---

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route("/arma_data", methods=["GET"])
def get_arma_data():
    logger.debug("Запрос /arma_data")
    with arma_connector.lock:
        if arma_connector.data is None:
            return jsonify({"status": "no_data"}), 200
        # logger.debug(f"Отправка arma_data: {arma_connector.data}") # Может быть очень много данных
        return jsonify({"status": "success", "data": arma_connector.data}), 200

@app.route("/arma_data_stream")
def arma_data_stream():
    logger.info("Новое подключение к /arma_data_stream")
    def event_stream():
        last_data_str = None # Храним строку для сравнения
        while True:
            with arma_connector.lock:
                current_data = arma_connector.data
                # Преобразуем в строку для надежного сравнения (избегаем проблем с deep compare)
                current_data_str = json.dumps(current_data) if current_data else None

            if current_data_str != last_data_str and current_data is not None:
                last_data_str = current_data_str
                try:
                    # logger.debug(f"SSE arma_data: Отправка обновления данных.")
                    yield f"data: {json.dumps({'status': 'success', 'data': current_data})}\n\n"
                except Exception as e:
                    logger.error(f"Ошибка отправки SSE arma_data: {e}")
                    # Можно добавить логику разрыва соединения при ошибке
                    break
            time.sleep(0.1) # Небольшая пауза для снижения нагрузки CPU
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/reports_stream")
def reports_stream():
    logger.info("Новое подключение к /reports_stream")
    def event_stream():
        # Получаем текущий event loop или создаем новый, если его нет
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        global system_prompt_sent # Объявляем, что будем использовать глобальную переменную

        while True:
            try:
                if not arma_connector.reports_queue.empty():
                    report = arma_connector.reports_queue.get()
                    logger.info(f"SSE: Отправка репорта - {report}")

                    # Проверяем start_mission и отправляем системный промпт
                    if report.get("command") == "start_mission" and not system_prompt_sent:
                        # Выполняем асинхронную функцию в этом цикле событий
                        if llm_client and "arma_session" in llm_client.chat_sessions:
                             logger.info("Обнаружен start_mission, попытка отправки системного промпта...")
                             # Важно: run_until_complete блокирует, но здесь это ок, т.к. в потоке SSE
                             try:
                                 loop.run_until_complete(send_system_prompt())
                                 logger.info("Отправка системного промпта завершена.")
                             except Exception as e_prompt:
                                 logger.error(f"Ошибка при асинхронной отправке системного промпта: {e_prompt}")
                        else:
                            logger.warning("Получен start_mission, но LLM клиент или сессия не готовы.")

                    # Отправляем сам репорт клиенту
                    yield f"data: {json.dumps(report)}\n\n"
                    arma_connector.reports_queue.task_done() # Сообщаем очереди, что элемент обработан
                else:
                    time.sleep(0.1) # Ждем, если очередь пуста
            except Exception as e:
                logger.error(f"Ошибка в цикле reports_stream: {e}")
                # Возможно, стоит прервать цикл при определенных ошибках
                break
        logger.warning("Цикл event_stream для /reports_stream завершен.")

    return Response(event_stream(), mimetype="text/event-stream")

async def send_system_prompt():
    global system_prompt_sent, llm_client # Указываем глобальные переменные
    if llm_client and "arma_session" in llm_client.chat_sessions and not system_prompt_sent:
        logger.info("Отправка системного промпта в LLM...")
        success = await llm_client.send_system_prompt("arma_session")
        if success:
            system_prompt_sent = True # Устанавливаем флаг только при успехе
            logger.info("Системный промпт успешно отправлен в LLM")
        else:
            logger.error("Не удалось отправить системный промпт в LLM")
    elif system_prompt_sent:
         logger.info("Системный промпт уже был отправлен ранее.")
    else:
         logger.warning("Попытка отправить системный промпт, но LLM не готов.")


@app.route("/send_callback", methods=["POST"])
def send_callback_endpoint():
    data = request.get_json()
    logger.debug(f"Получен POST /send_callback: {data}")
    if not data:
        logger.error("Неверные параметры в /send_callback (пустой JSON)")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400
    try:
        # Преобразуем команду к нижнему регистру для надежности
        command = data.get("command", "").lower()
        report_type = data.get("t", "").lower() # Тип репорта от LLMextension

        # Проверяем репорты от LLMextension (предполагая, что они не команды для Arma)
        if report_type in ["enemy_detected", "vehicle_detected", "vehicle_destroyed", "enemies_cleared", "vehicle_lost"]:
            # Кладем репорт в ту же очередь, что и репорты от Arma
            # Это позволит централизованно обрабатывать все репорты
            arma_connector.reports_queue.put(data)
            logger.info(f"Репорт от LLMextension добавлен в очередь: {data}")
        # Проверяем команды для ARMA (исключаем 'update_data', т.к. он обрабатывается отдельно)
        elif command and command != "update_data":
             arma_connector.send_callback_to_arma(data)
             logger.info(f"Callback команда отправлена в Arma: {data}")
        elif command == "update_data":
             logger.warning("Получена команда 'update_data' через /send_callback, но она игнорируется (обрабатывается таймером).")
        else:
             logger.warning(f"Неизвестный тип данных или команды в /send_callback: {data}")
             # Можно вернуть ошибку, если это не ожидаемое поведение
             # return jsonify({"status": "error", "message": "Unknown command or report type"}), 400

        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.exception(f"Ошибка в /send_callback: {e}") # Используем exception для stack trace
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/set_update_interval", methods=["POST"])
def set_update_interval_route(): # Переименовано во избежание конфликта имен
    global update_interval, update_running, update_thread, update_lock
    data = request.get_json()
    logger.info(f"Запрос /set_update_interval: {data}")
    if not data or "interval" not in data:
        logger.error("Неверные параметры в /set_update_interval (отсутствует 'interval')")
        return jsonify({"status": "error", "message": "Missing interval"}), 400
    try:
        new_interval = int(data["interval"])
        if new_interval < 1:
            logger.error(f"Интервал должен быть > 0, получен: {new_interval}")
            return jsonify({"status": "error", "message": "Interval must be positive"}), 400

        with update_lock:
            old_interval = update_interval
            update_interval = new_interval
            logger.info(f"Интервал обновления изменен с {old_interval} на {update_interval} секунд.")
            # Перезапуск потока не требуется, т.к. он читает update_interval в каждой итерации
            # Если бы нужно было его перезапустить:
            # if update_running:
            #     update_running = False
            #     if update_thread and update_thread.is_alive():
            #         logger.info("Ожидание завершения старого потока send_update_request...")
            #         update_thread.join(timeout=2) # Даем потоку время завершиться
            #         if update_thread.is_alive():
            #              logger.warning("Старый поток send_update_request не завершился вовремя.")
            # update_running = True
            # update_thread = threading.Thread(target=send_update_request, daemon=True)
            # update_thread.start()
            # logger.info("Перезапущен поток send_update_request с новым интервалом.")

        return jsonify({"status": "success", "interval": update_interval}), 200
    except ValueError:
         logger.error(f"Неверное значение интервала: {data.get('interval')}")
         return jsonify({"status": "error", "message": "Invalid interval value"}), 400
    except Exception as e:
         logger.exception(f"Ошибка в /set_update_interval: {e}")
         return jsonify({"status": "error", "message": str(e)}), 500


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route("/")
def serve_index():
    logger.debug("Запрос / (index.html)")
    return app.send_static_file("index.html")

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    # logger.debug(f"Запрос тайла: z={z}, x={x}, y={y}") # Может быть слишком много логов
    if x < 0 or y < 0:
        # logger.debug("Отправка прозрачного тайла (отрицательные координаты)")
        # Используем относительный путь к прозрачному тайлу в static
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)

    # Формируем путь к тайлу относительно базовой директории скрипта
    # Убедитесь, что TILES_FOLDER указывает на правильное местоположение
    tile_rel_path = os.path.join(TILES_FOLDER, str(z), str(x), f"{y}.png")
    tile_abs_path = os.path.join(BASE_DIR, tile_rel_path)
    # logger.debug(f"Полный путь к тайлу: {tile_abs_path}")

    if os.path.exists(tile_abs_path):
        # Отправляем файл из директории, где он реально лежит
        tile_dir_abs = os.path.dirname(tile_abs_path)
        tile_filename = os.path.basename(tile_abs_path)
        # logger.debug(f"Отправка тайла: {tile_filename} из {tile_dir_abs}")
        try:
            response = send_from_directory(tile_dir_abs, tile_filename)
            response.cache_control.max_age = CACHE_TIMEOUT
            response.cache_control.public = True
            return response
        except Exception as e:
             logger.error(f"Ошибка отправки тайла {tile_abs_path}: {e}")
             # Отправляем прозрачный тайл в случае ошибки чтения файла
             return send_from_directory(app.static_folder, TRANSPARENT_TILE)
    else:
        # logger.debug("Файл тайла не найден, отправка прозрачного тайла.")
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)


@app.route("/save_snapshot", methods=["POST"])
def save_snapshot():
    data = request.get_json()
    logger.debug(f"Запрос /save_snapshot")
    if not data or "image" not in data or "filename" not in data:
        logger.error("Неверные параметры в /save_snapshot")
        abort(400, "Неверные параметры")

    try:
        image_data_base64 = data["image"].split(',')[1] # Убираем префикс 'data:image/png;base64,'
        filename = data["filename"]
        # Предотвращаем выход за пределы папки snapshots
        filename = os.path.basename(filename)
        if not filename.lower().endswith(".png"):
             logger.error(f"Недопустимое имя файла для снимка: {filename}")
             abort(400, "Имя файла должно оканчиваться на .png")

        file_path = os.path.join(SNAPSHOTS_FOLDER, filename)
        logger.info(f"Сохранение снимка в: {file_path}")

        image_bytes = base64.b64decode(image_data_base64)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        return jsonify({"status": "success", "path": file_path}), 200
    except base64.binascii.Error as b64e:
        logger.error(f"Ошибка декодирования Base64 в /save_snapshot: {b64e}")
        abort(400, "Ошибка декодирования Base64")
    except Exception as e:
        logger.exception(f"Ошибка сохранения снимка: {e}")
        abort(500, "Ошибка сервера при сохранении снимка")


@app.route("/names")
def get_names():
    db_path = os.path.join(DB_DIR, "name.db")
    logger.debug(f"Запрос /names (БД: {db_path})")
    if not os.path.exists(db_path):
        logger.error(f"База данных {db_path} не найдена.")
        return jsonify({"status": "error", "message": "Database not found"}), 404
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names")
        rows = cur.fetchall()
        names_list = [dict(row) for row in rows]
        conn.close()
        logger.info(f"Отправлено {len(names_list)} названий из БД.")
        return jsonify(names_list)
    except Exception as e:
        logger.exception(f"Ошибка чтения базы данных names: {e}")
        abort(500, "Ошибка сервера при чтении БД")


@app.route("/update_label", methods=["POST"])
def update_label():
    data = request.get_json()
    logger.debug(f"Запрос /update_label: {data}")
    if not data or "id" not in data or "x" not in data or "y" not in data:
        logger.error("Неверные параметры в /update_label")
        abort(400, "Неверные параметры")

    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path):
        logger.error(f"База данных {db_path} не найдена для обновления.")
        return jsonify({"status": "error", "message": "Database not found"}), 404
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE names SET x = ?, y = ? WHERE id = ?", (data["x"], data["y"], data["id"]))
        conn.commit()
        updated_rows = cur.rowcount
        conn.close()
        if updated_rows > 0:
            logger.info(f"Обновлена надпись id={data['id']} новыми координатами.")
            return jsonify({"status": "success"}), 200
        else:
            logger.warning(f"Надпись id={data['id']} не найдена для обновления.")
            return jsonify({"status": "error", "message": "Label not found"}), 404
    except Exception as e:
        logger.exception(f"Ошибка обновления надписи id={data.get('id')}: {e}")
        abort(500, "Ошибка сервера при обновлении надписи")


@app.route("/add_label", methods=["POST"])
def add_label():
    data = request.get_json()
    logger.debug(f"Запрос /add_label: {data}")
    if not data or "name" not in data or "type" not in data or "x" not in data or "y" not in data:
        logger.error("Неверные параметры в /add_label")
        abort(400, "Неверные параметры")

    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path):
        # Если БД нет, можно попробовать ее создать (или вернуть ошибку)
        logger.error(f"База данных {db_path} не найдена для добавления.")
        # Здесь можно добавить код создания БД и таблицы, если это нужно
        return jsonify({"status": "error", "message": "Database not found"}), 404
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO names (name, type, x, y) VALUES (?, ?, ?, ?)",
                    (data["name"], data["type"], data["x"], data["y"]))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        logger.info(f"Добавлена новая надпись '{data['name']}' с id={new_id}.")
        return jsonify({"status": "success", "id": new_id}), 200
    except Exception as e:
        logger.exception(f"Ошибка добавления надписи '{data.get('name')}': {e}")
        abort(500, "Ошибка сервера при добавлении надписи")


@app.route("/send_to_arma", methods=["POST"])
def send_to_arma_endpoint():
    data = request.get_json()
    logger.debug(f"Запрос /send_to_arma: {data}")
    if not data:
        logger.error("Пустые данные в /send_to_arma")
        abort(400, "Неверные параметры")
    try:
        arma_connector.send_to_arma(data) # Используем функцию из модуля
        logger.info(f"Данные успешно отправлены в ARMA (порт 12345): {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.exception(f"Ошибка отправки в ARMA (порт 12345): {e}")
        abort(500, "Ошибка сервера при отправке в ARMA")


@app.route("/get_buildings", methods=["POST"])
def get_buildings():
    area = request.get_json()
    logger.debug(f"Запрос /get_buildings для области: {area}")
    if not area or not all(k in area for k in ('minX', 'maxX', 'minY', 'maxY')):
         logger.error(f"Неверные параметры области в /get_buildings: {area}")
         abort(400, "Неверные параметры области")

    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "buildings.db")
    if not os.path.exists(db_path):
        logger.error(f"База данных {db_path} не найдена.")
        # Возвращаем пустой список, т.к. фронтенд может это ожидать
        return jsonify([]) # Возвращаем пустой список вместо ошибки 404
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Используем параметры для безопасности
        cur.execute("SELECT id, name, x, y, z, interior FROM buildings WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        buildings = [dict(row) for row in cur.fetchall()] # Преобразуем строки в словари
        conn.close()
        logger.info(f"Получено зданий: {len(buildings)} для области {min_x},{min_y} - {max_x},{max_y}")
        return jsonify(buildings)
    except Exception as e:
        logger.exception(f"Ошибка получения зданий: {e}")
        abort(500, "Ошибка сервера при получении зданий")


@app.route("/get_names_in_area", methods=["POST"])
def get_names_in_area():
    area = request.get_json()
    logger.debug(f"Запрос /get_names_in_area для области: {area}")
    if not area or not all(k in area for k in ('minX', 'maxX', 'minY', 'maxY')):
         logger.error(f"Неверные параметры области в /get_names_in_area: {area}")
         abort(400, "Неверные параметры области")

    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path):
        logger.error(f"База данных {db_path} не найдена.")
        return jsonify([]) # Возвращаем пустой список

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        names = [dict(row) for row in cur.fetchall()] # Преобразуем строки в словари
        conn.close()
        logger.info(f"Получено названий: {len(names)} для области {min_x},{min_y} - {max_x},{max_y}")
        return jsonify(names)
    except Exception as e:
        logger.exception(f"Ошибка получения названий: {e}")
        abort(500, "Ошибка сервера при получении названий")


@app.route("/save_json", methods=["POST"])
def save_json():
    data = request.get_json()
    logger.debug(f"Запрос /save_json")
    if not data or "filename" not in data or "data" not in data:
        logger.error("Неверные параметры в /save_json")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400

    try:
        filename = data["filename"]
        # Предотвращаем выход за пределы базовой директории
        filename = os.path.basename(filename)
        if not filename.lower().endswith(".json"):
             logger.error(f"Недопустимое имя файла для JSON: {filename}")
             return jsonify({"status": "error", "message": "Filename must end with .json"}), 400

        content = data["data"]
        file_path = os.path.join(BASE_DIR, filename) # Сохраняем в корень проекта
        logger.info(f"Сохранение JSON в файл: {file_path}")

        with open(file_path, 'w', encoding='utf-8') as f:
            # Используем indent для читаемости файла
            json.dump(content, f, ensure_ascii=False, indent=4)

        return jsonify({"status": "success", "filename": filename}), 200
    except Exception as e:
        logger.exception(f"Ошибка сохранения JSON в файл '{data.get('filename')}': {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/llm_models", methods=["GET"])
def get_llm_models():
    global llm_client
    logger.debug("Запрос /llm_models")
    if not llm_client or not hasattr(llm_client, 'get_available_models'):
        logger.error("LLMClient не инициализирован или не имеет метода get_available_models")
        return jsonify({"status": "error", "message": "LLMClient не инициализирован"}), 500
    try:
        models = llm_client.get_available_models()
        logger.info(f"Отправка списка доступных LLM моделей: {models}")
        return jsonify({"status": "success", "models": models}), 200
    except Exception as e:
        logger.exception("Ошибка при получении списка LLM моделей")
        return jsonify({"status": "error", "message": "Ошибка получения списка моделей"}), 500


@app.route("/set_llm_model", methods=["POST"])
def set_llm_model():
    global llm_client
    data = request.get_json()
    logger.debug(f"Запрос /set_llm_model: {data}")
    if not llm_client or not hasattr(llm_client, 'set_model'):
         logger.error("LLMClient не инициализирован или не имеет метода set_model")
         return jsonify({"status": "error", "message": "LLMClient не инициализирован"}), 500

    model_name = data.get("model")
    if not model_name:
        logger.error("Отсутствует параметр 'model' в /set_llm_model")
        return jsonify({"status": "error", "message": "Отсутствует model"}), 400

    try:
        if llm_client.set_model(model_name):
            logger.info(f"Модель LLM успешно изменена на: {model_name}")
            return jsonify({"status": "success", "model": model_name}), 200
        else:
            logger.error(f"Ошибка при попытке смены модели LLM на: {model_name}")
            return jsonify({"status": "error", "message": "Ошибка смены модели"}), 500
    except Exception as e:
        logger.exception(f"Исключение при смене модели LLM на {model_name}")
        return jsonify({"status": "error", "message": "Внутренняя ошибка сервера при смене модели"}), 500


@app.route("/llm_command", methods=["POST"])
async def llm_command(): # Делаем маршрут асинхронным
    global llm_client, system_prompt_sent
    data = request.get_json()
    logger.debug(f"Запрос /llm_command: {data}") # Не логгируем все данные, могут быть большими

    if not llm_client or "arma_session" not in llm_client.chat_sessions:
        logger.error("LLM сессия не инициализирована для /llm_command")
        return jsonify({"status": "error", "message": "LLM сессия не инициализирована"}), 500

    if not system_prompt_sent:
        logger.warning("Попытка выполнить llm_command до отправки системного промпта.")
        # Возвращаем 503 Service Unavailable, т.к. сервис временно не готов к обработке
        return jsonify({"status": "error", "message": "Системный промпт еще не отправлен, ждите начала миссии"}), 503

    if not data or "json_input" not in data:
        logger.error("Отсутствует 'json_input' в /llm_command")
        return jsonify({"status": "error", "message": "Отсутствует json_input"}), 400

    json_input = data["json_input"]
    png_path = data.get("png_path")  # Опционально

    try:
        # Вызываем асинхронный метод llm_client
        response = await llm_client.send_message("arma_session", json_input, png_path)

        if response:
            logger.info(f"Успешный ответ от LLM для команды: {json_input.get('command', 'N/A')}")
            # logger.debug(f"Ответ LLM: {response}") # Может быть слишком много текста
            return jsonify({"status": "success", "response": response}), 200
        else:
            logger.error(f"Получен пустой ответ от LLM для команды: {json_input.get('command', 'N/A')}")
            return jsonify({"status": "error", "message": "Пустой ответ от LLM"}), 500
    except Exception as e:
        logger.exception(f"Ошибка в llm_command при вызове LLM: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- БЛОК if __name__ == "__main__": (ТЕПЕРЬ ПОЧТИ ПУСТОЙ) ---
if __name__ == "__main__":
    # Этот блок НЕ будет выполняться при запуске через waitress-serve
    # Он нужен только если вы запускаете скрипт напрямую: python server.py
    # В нашем случае, вся инициализация вынесена наверх,
    # а запуск сервера делает waitress.
    logger.warning("Скрипт server.py запущен напрямую (не через waitress).")
    logger.warning("Для продакшена или стабильной работы используйте: waitress-serve --host=0.0.0.0 --port=5000 server:app")
    # Можно добавить запуск встроенного сервера Flask для отладки, если нужно
    # logger.info("Запуск встроенного сервера Flask для отладки...")
    # app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False) # debug=True для разработки
    pass

# --- КОНЕЦ ФАЙЛА server.py ---