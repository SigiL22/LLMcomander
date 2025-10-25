# --- START OF FILE server.py ---

import os
import logging
import logging.handlers
import sqlite3
import base64
import threading
import asyncio
import time
import json
import llm_tactical_controller
from flask import Flask, send_from_directory, abort, request, jsonify, Response
from concurrent.futures import Future # Необходимо для run_coroutine_threadsafe
from collections.abc import Coroutine

# Импортируем асинхронный коннектор
import arma_connector_async as arma_connector # Переименовали файл или импортируем с псевдонимом
from llm_client import LLMClient

# --- НАСТРОЙКА ЛОГИРОВАНИЯ (обновленная) ---
log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("Server")
logger.setLevel(logging.INFO)
logger.propagate = False
arma_logger = logging.getLogger("ArmaConnectorAsync")
arma_logger.setLevel(logging.INFO) # Устанавливаем уровень для логгера коннектора
arma_logger.propagate = False
# logging.getLogger("waitress").setLevel(logging.WARNING)
logging.getLogger("waitress").setLevel(logging.ERROR)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    arma_logger.addHandler(console_handler) # Добавляем тот же обработчик
    log_file = "server.log"
    file_handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    arma_logger.addHandler(file_handler) # Добавляем тот же обработчик
logger.info("=" * 10 + " Server Start " + "=" * 10)
# --- КОНЕЦ НАСТРОЙКИ ЛОГИРОВАНИЯ ---

# --- Константы и создание Flask app (без изменений) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DB_DIR = os.path.join(BASE_DIR, 'db')
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
logger.info("Объект Flask 'app' создан.")
TILES_FOLDER = "maps/chernarus/"
SNAPSHOTS_FOLDER = "snapshots"
CACHE_TIMEOUT = 86400
TRANSPARENT_TILE = "transparent.png"
os.makedirs(SNAPSHOTS_FOLDER, exist_ok=True); os.makedirs(DB_DIR, exist_ok=True)


# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ И УПРАВЛЕНИЕ ASYNCIO ЛУПОМ ---
update_interval = 10
update_thread = None
update_running = False
update_lock = threading.Lock()
llm_client = None
system_prompt_sent = False
arma_loop: asyncio.AbstractEventLoop | None = None # Цикл событий для arma_connector
arma_thread: threading.Thread | None = None      # Поток, в котором работает arma_loop
llm_assigned_side: str | None = None # Сторона, назначенная LLM
roll_call_interval_seconds = 300 # По умолчанию 5 минут
roll_call_thread = None
roll_call_running = False
roll_call_event = threading.Event() # Используем Event для прерывания сна

def roll_call_loop():
    global roll_call_running, llm_assigned_side, system_prompt_sent, llm_client, roll_call_interval_seconds
    logger.info("Поток 'переклички' для LLM запущен.")

    while roll_call_running:
        try:
            # Ждем либо таймаута, либо события
            # Это позволит нам мгновенно менять интервал
            roll_call_event.wait(timeout=roll_call_interval_seconds)
            roll_call_event.clear() # Сбрасываем событие после ожидания
            
            if not roll_call_running: break

            if llm_assigned_side and system_prompt_sent and llm_client:
                logger.info(f"Перекличка: запуск отчета для стороны {llm_assigned_side}")
                run_async_from_sync(
                    llm_tactical_controller.trigger_llm_report(
                        llm_client,
                        llm_assigned_side,
                        context_text="Periodic roll call. Current status of your forces"
                    )
                )
        except Exception as e:
            logger.error(f"Ошибка в цикле 'переклички': {e}")
            time.sleep(10)

    logger.info("Поток 'переклички' для LLM остановлен.")


# --- Функция для запуска asyncio loop в отдельном потоке ---
def run_arma_loop():
    global arma_loop
    logger.info("Запуск event loop asyncio для arma_connector в отдельном потоке...")
    try:
        # Получаем или создаем новый event loop для этого потока
        arma_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(arma_loop)
        # Запускаем сервер arma_connector и ждем его завершения (что не произойдет)
        arma_loop.run_until_complete(arma_connector.start_server())
        logger.info("Event loop arma_connector завершен.") # Не должно вызываться при нормальной работе
    except Exception as e:
        logger.exception("Критическая ошибка в потоке event loop arma_connector!")
    finally:
        if arma_loop and arma_loop.is_running():
            arma_loop.close()
        logger.info("Поток event loop arma_connector остановлен.")

# --- Хелпер для вызова async функций из sync контекста ---
def run_async_from_sync(coro: Coroutine) -> any: # <-- Исправлена аннотация
    """Безопасно запускает корутину в цикле arma_loop из синхронного потока."""
    if arma_loop is None or not arma_loop.is_running():
        logger.error("Event loop arma_connector не запущен! Невозможно выполнить async операцию.")
        # В зависимости от критичности, можно вернуть None, пустой объект или возбудить исключение
        # raise RuntimeError("Arma connector event loop is not running.")
        return None # Возвращаем None, обработчик маршрута должен это учесть

    # Отправляем корутину на выполнение в другой поток и ждем результат
    future: Future = asyncio.run_coroutine_threadsafe(coro, arma_loop)
    try:
        # Добавляем таймаут, чтобы не блокировать поток Flask навечно
        result = future.result(timeout=145) # Таймаут 15 секунд (настройте по необходимости)
        return result
    except TimeoutError:
        logger.error(f"Таймаут при ожидании результата async операции: {coro}")
        # Можно вернуть специальное значение или None, чтобы указать на таймаут
        return None # Возвращаем None при таймауте
    except Exception as e:
        # Логируем ошибку, которая произошла *внутри* корутины
        logger.exception(f"Ошибка при выполнении async операции {coro}: {e}")
        # Можно возбудить исключение дальше или вернуть None
        return None # Возвращаем None при другой ошибке
        
# --- ИНИЦИАЛИЗАЦИЯ (обновленная проверка LLM) ---
logger.info("Инициализация LLMClient...")
llm_client = None # Гарантированно None в начале
try:
    # Создаем экземпляр, __init__ сам проверит работоспособность и установит флаг
    llm_client_instance = LLMClient(config_file="config.json", system_prompt_file="system_prompt.txt")
    if llm_client_instance.is_operational: # Проверяем флаг
        session_id = "arma_session"
        if llm_client_instance.create_session(session_id):
            llm_client = llm_client_instance # Присваиваем только если все Ок
            logger.info("LLMClient и сессия 'arma_session' успешно созданы.")
        else:
            logger.error("Не удалось создать сессию LLM.")
            # llm_client остается None
    else:
        logger.error("LLMClient не инициализирован (API/геолокация?). Работа без LLM.")
        # llm_client остается None
except Exception as e:
    logger.exception(f"Критическая ошибка при создании объекта LLMClient: {e}")
    llm_client = None # Убедимся, что он None при любой ошибке

# Запускаем asyncio loop для arma_connector в отдельном потоке
logger.info("Запуск фоновых потоков...")
try:
    arma_thread = threading.Thread(target=run_arma_loop, daemon=True)
    arma_thread.start()
    logger.info("Поток для event loop arma_connector запущен.")
    # Дадим время циклу запуститься и установить arma_loop
    time.sleep(1) # Простая задержка, можно заменить на Event

    # Функция для потока обновления (ОСТАЕТСЯ СИНХРОННОЙ, вызывает async)
    def send_update_request():
        global update_running, update_interval
        # Ждем, пока arma_data появится (его установит асинхронный обработчик)
        while run_async_from_sync(arma_connector.get_arma_data_async()) is None:
             logger.debug("Ожидание данных миссии перед запуском send_update_request...")
             if not arma_loop or not arma_loop.is_running(): # Проверка, если цикл упал
                  logger.error("Цикл Arma Connector не работает, остановка send_update_request.")
                  return
             time.sleep(3)
        logger.info("Миссия стартовала, начинаем отправку update_data")

        while update_running:
            try:
                # Вызываем асинхронную функцию отправки из синхронного потока
                logger.debug("Вызов run_async_from_sync для отправки update_data")
                run_async_from_sync(
                    arma_connector.send_callback_to_arma_async({"command": "update_data"})
                )
                # Логирование успеха/неудачи теперь внутри send_callback_to_arma_async
                #logger.info(f"Команда update_data отправлена в ARMA (асинхронно), следующий вызов через {update_interval} сек")
                time.sleep(update_interval)
            except Exception as e:
                # Логируем ошибку самого цикла или run_async_from_sync
                logger.error(f"Ошибка в цикле send_update_request: {e}")
                time.sleep(1)
            if not update_running:
                logger.info("Остановка потока send_update_request.")
                break
            if not arma_loop or not arma_loop.is_running(): # Проверка, если цикл упал
                logger.error("Цикл Arma Connector перестал работать, остановка send_update_request.")
                update_running = False
                break
        logger.info("Поток send_update_request завершен.")

    # Добавляем асинхронную функцию для получения arma_data (для вызова из sync)
    async def get_arma_data_wrapper():
         async with arma_connector.data_lock:
             return arma_connector.arma_data

    # Добавляем в arma_connector.py:
    # async def get_arma_data_async():
    #    async with data_lock:
    #        return arma_data
    # (Или используем wrapper выше)

    update_running = True
    update_thread = threading.Thread(target=send_update_request, daemon=True)
    update_thread.start()
    roll_call_running = True
    roll_call_thread = threading.Thread(target=roll_call_loop, daemon=True)
    roll_call_thread.start()
    logger.info("Поток send_update_request запущен.")

except Exception as e:
    logger.exception(f"Ошибка при запуске фоновых потоков: {e}")
# --- КОНЕЦ ИНИЦИАЛИЗАЦИИ ---


# --- ОПРЕДЕЛЕНИЯ МАРШРУТОВ FLASK (@app.route) ---
# Маршруты, не требующие async вызовов, остаются без изменений

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route("/arma_data", methods=["GET"])
def get_arma_data():
    logger.debug("Запрос /arma_data")
    # Получаем данные через хелпер, который работает с async lock
    current_data = run_async_from_sync(get_arma_data_wrapper()) # Используем wrapper
    # или run_async_from_sync(arma_connector.get_arma_data_async()) # если добавили в коннектор

    if current_data is None and arma_loop is not None and arma_loop.is_running(): # Проверяем, что цикл жив
        return jsonify({"status": "no_data"}), 200
    elif current_data:
        return jsonify({"status": "success", "data": current_data}), 200
    else: # current_data is None и цикл не работает
         logger.error("Не удалось получить arma_data, возможно, цикл arma_connector не работает.")
         return jsonify({"status": "error", "message": "Failed to retrieve data"}), 500


@app.route("/arma_data_stream")
def arma_data_stream():
    logger.info("Новое подключение к /arma_data_stream")
    def event_stream():
        last_data_str = None
        while True:
            if not arma_loop or not arma_loop.is_running():
                logger.warning("SSE arma_data: Цикл Arma Connector не работает, разрыв соединения.")
                break # Прерываем цикл SSE

            # Получаем данные асинхронно
            current_data = run_async_from_sync(get_arma_data_wrapper())
            current_data_str = json.dumps(current_data) if current_data else None

            if current_data_str != last_data_str and current_data is not None:
                last_data_str = current_data_str
                try:
                    yield f"data: {json.dumps({'status': 'success', 'data': current_data})}\n\n"
                except Exception as e:
                    logger.error(f"Ошибка отправки SSE arma_data: {e}")
                    break # Разрываем соединение при ошибке
            time.sleep(0.1)
    return Response(event_stream(), mimetype="text/event-stream")


# --- Маршрут /reports_stream (обновлен) ---
@app.route("/reports_stream")
def reports_stream():
    logger.info("Новое подключение к /reports_stream")
    def event_stream():
        global system_prompt_sent
        while True:
            if not arma_loop or not arma_loop.is_running(): logger.warning("SSE reports: Цикл Arma не работает."); break
            report = None
            try:
                async def get_report_non_blocking(): # Хелпер для неблокирующего получения
                    try: return await asyncio.wait_for(arma_connector.reports_queue.get(), timeout=0.05)
                    except asyncio.TimeoutError: return None
                    except asyncio.QueueEmpty: return None
                report = run_async_from_sync(get_report_non_blocking()) # Получаем через мост

                if report:
                    log_msg_part = report.get('command', report.get('t', 'Unknown')) # Что логгировать
                    logger.info(f"ТОЧКА 2: Извлечено из очереди и отправляется клиенту: {report}")
                    report_type = report.get("t")
                    if report_type in ["enemy_detected", "waypoint_reached", "enemies_cleared", "vehicle_lost"] and system_prompt_sent:
                        if llm_assigned_side and system_prompt_sent and llm_client:
                            group_name = report.get("g") or report.get("ge")
                            if group_name:
                                context = f"Event report from group '{group_name}': {report_type.upper()}. Current status of this group"
                                # Запускаем асинхронную отправку отчета в фоне, не блокируя поток
                                asyncio.run_coroutine_threadsafe(
                                    llm_tactical_controller.trigger_llm_report(
                                        llm_client,
                                        llm_assigned_side,
                                        context_text=context,
                                        group_names=[group_name]
                                    ),
                                    arma_loop
                                )
                    # Обработка start_mission

                    
                    yield f"data: {json.dumps(report)}\n\n" # Отправляем клиенту
                    # Отмечаем репорт как обработанный в async очереди
                    #run_async_from_sync(arma_connector.mark_report_done())
                else:
                    time.sleep(0.1) # Пауза, если очередь пуста
            except Exception as e: logger.error(f"Ошибка в цикле reports_stream: {e}"); break
        logger.warning("Цикл event_stream для /reports_stream завершен.")
    return Response(event_stream(), mimetype="text/event-stream")


# --- Функция send_system_prompt (принимает markers, async) ---
async def send_system_prompt(markers: list = None):
    global system_prompt_sent, llm_client, llm_assigned_side
    
    if not llm_assigned_side:
        logger.error("(async) Попытка запустить send_system_prompt без выбранной стороны LLM. Отменено.")
        return False

    if not llm_client or not llm_client.is_operational:
         logger.error("(async) Невозможно отправить системный промпт: LLM клиент не готов.")
         return False

    # 1. Отправка системного промпта
    logger.info("(async) Отправка основного системного промпта в LLM...")
    prompt_response = await llm_client.send_system_prompt("arma_session")
    
    if not prompt_response:
        logger.error("(async) Не удалось отправить основной системный промпт или получен пустой ответ.")
        # Отправляем сообщение об ошибке в UI
        await arma_connector.reports_queue.put({
            "t": "llm_log",
            "message": "Ошибка: не удалось отправить системный промпт в LLM."
        })
        return False
    
    # Отправляем сообщение об успехе в очередь
    await arma_connector.reports_queue.put({"t": "llm_log", "message": "Системный промпт успешно отправлен."})
    await llm_tactical_controller.handle_llm_response(prompt_response)
    
    system_prompt_sent = True
    logger.info("(async) Основной системный промпт успешно отправлен.")

    # 2. Получаем свежие данные о силах
    async with arma_connector.data_lock:
        current_arma_data = arma_connector.arma_data
    
    filtered_forces = llm_tactical_controller.filter_data_for_llm(current_arma_data, llm_assigned_side)

    # 3. Формируем единое сообщение с маркерами и силами
    initial_data_payload = {}
    context_text = "Initial mission data."

    if markers:
        logger.info(f"(async) Оптимизируем и добавляем данные о {len(markers)} маркерах в первоначальный отчет.")
        
        optimized_markers = []
        for m in markers:
            marker_data = {
                "t": m.get("type"),
                "p": m.get("pos"),
                "text": m.get("text"),
            }
            
            # --- НОВАЯ ЛОГИКА ДЛЯ ПОЛЯ 'size' ---
            size = m.get("size")
            # Добавляем поле 'size' только если оно существует и не является точечным (1x1)
            if size and (size[0] > 1 or size[1] > 1):
                marker_data["size"] = size
            # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

            optimized_markers.append(marker_data)
            
        initial_data_payload["mission_markers"] = optimized_markers
    else:
        logger.warning("(async) Данные маркеров не предоставлены для первоначального отчета.")

    if filtered_forces:
        logger.info(f"(async) Добавляем данные о {len(filtered_forces)} группах в первоначальный отчет.")
        initial_data_payload["your_forces"] = filtered_forces
    else:
        logger.warning(f"(async) Нет данных о своих силах для первоначального отчета по стороне {llm_assigned_side}.")

    # 4. Отправляем единый отчет, если есть что отправлять
    if initial_data_payload:
        try:
            json_str = json.dumps(initial_data_payload, ensure_ascii=False)
            full_prompt = f"{context_text}\n{json_str}"
            
            response = await llm_client.send_message("arma_session", user_input=full_prompt)
            await llm_tactical_controller.handle_llm_response(response)
            
            await arma_connector.reports_queue.put({
                "t": "llm_log",
                "message": "Данные о маркерах и своих силах отправлены."
            })

        except Exception as e:
            logger.exception("(async) Ошибка при отправке данных маркеров и сил в LLM.")
    else:
        logger.error("(async) Нет данных ни по маркерам, ни по силам для отправки в LLM.")

    return system_prompt_sent

@app.route("/set_roll_call_interval", methods=["POST"])
def set_roll_call_interval_route():
    global roll_call_interval_seconds
    data = request.get_json()
    try:
        new_interval_mins = int(data["interval"])
        if new_interval_mins < 1:
             return jsonify({"status": "error", "message": "Интервал должен быть положительным"}), 400
        
        roll_call_interval_seconds = new_interval_mins * 60
        roll_call_event.set() # Прерываем сон потока, чтобы он сразу начал использовать новый интервал
        
        logger.info(f"Интервал переклички установлен на: {new_interval_mins} мин ({roll_call_interval_seconds} сек)")
        return jsonify({"status": "success", "interval": new_interval_mins}), 200
    except (ValueError, TypeError, KeyError):
         return jsonify({"status": "error", "message": "Неверное значение интервала"}), 400
    except Exception as e:
         logger.exception(f"Ошибка в /set_roll_call_interval: {e}")
         return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/send_callback", methods=["POST"])
def send_callback_endpoint():
    data = request.get_json()
    # ... (логика определения report_type и command остается) ...
    logger.debug(f"Получен POST /send_callback: {data}")
    if not data:
        logger.error("Неверные параметры в /send_callback (пустой JSON)")
        return jsonify({"status": "error", "message": "Invalid parameters"}), 400

    try:
        report_type = data.get("t", "").lower()
        command = data.get("command", "").lower()

        if report_type in ["enemy_detected", "vehicle_detected", "vehicle_destroyed", "enemies_cleared", "vehicle_lost"]:
             # Помещаем репорт в async очередь через мост
             success = run_async_from_sync(arma_connector.reports_queue.put(data))
             if success is not None: # run_async_from_sync вернет None при ошибке
                 logger.info(f"Репорт от LLMextension добавлен в очередь: {data}")
             else:
                 logger.error(f"Не удалось добавить репорт от LLMextension в очередь: {data}")
                 return jsonify({"status": "error", "message": "Failed to queue report"}), 500
        elif command and command != "update_data":
             # Отправляем команду через мост
             run_async_from_sync(arma_connector.send_callback_to_arma_async(data))
             # Логирование успеха/неудачи теперь внутри send_callback_to_arma_async
             logger.info(f"Callback команда отправлена в Arma (асинхронно): {data}")
        elif command == "update_data":
             logger.warning("Получена команда 'update_data' через /send_callback (игнорируется).")
        else:
             logger.warning(f"Неизвестный тип данных/команды в /send_callback: {data}")

        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.exception(f"Ошибка в /send_callback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Маршрут /set_update_interval остается СИНХРОННЫМ, т.к. меняет только переменную ---
@app.route("/set_update_interval", methods=["POST"])
def set_update_interval_route():
    global update_interval, update_lock # update_running, update_thread не меняем здесь
    data = request.get_json()
    # ... (логика валидации new_interval) ...
    try:
        new_interval = int(data["interval"])
        if new_interval < 1: #...
             return jsonify({"status": "error", "message": "Interval must be positive"}), 400
        with update_lock: # Блокировка на случай, если другой поток читает интервал
            update_interval = new_interval
        logger.info(f"Интервал обновления установлен на: {update_interval} секунд")
        return jsonify({"status": "success", "interval": update_interval}), 200
    except ValueError: #...
         return jsonify({"status": "error", "message": "Invalid interval value"}), 400
    except Exception as e: #...
         logger.exception(f"Ошибка в /set_update_interval: {e}")
         return jsonify({"status": "error", "message": str(e)}), 500

# --- Маршруты работы с БД и файлами ---
# Они остаются СИНХРОННЫМИ, но если БД станет узким местом,
# их можно перевести на async def и использовать aiosqlite или asyncio.to_thread

@app.after_request
# ... (без изменений) ...
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route("/")
# ... (без изменений) ...
def serve_index():
    logger.debug("Запрос / (index.html)")
    return app.send_static_file("index.html")

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
# ... (без изменений) ...
def get_tile(z, x, y):
    # ... (код получения тайла) ...
    if x < 0 or y < 0:
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)
    tile_rel_path = os.path.join(TILES_FOLDER, str(z), str(x), f"{y}.png")
    tile_abs_path = os.path.join(BASE_DIR, tile_rel_path)
    if os.path.exists(tile_abs_path):
        tile_dir_abs = os.path.dirname(tile_abs_path)
        tile_filename = os.path.basename(tile_abs_path)
        try:
            response = send_from_directory(tile_dir_abs, tile_filename)
            response.cache_control.max_age = CACHE_TIMEOUT
            response.cache_control.public = True
            return response
        except Exception as e:
             logger.error(f"Ошибка отправки тайла {tile_abs_path}: {e}")
             return send_from_directory(app.static_folder, TRANSPARENT_TILE)
    else:
        return send_from_directory(app.static_folder, TRANSPARENT_TILE)


@app.route("/save_snapshot", methods=["POST"])
# ... (без изменений) ...
def save_snapshot():
    # ... (код сохранения снимка) ...
    data = request.get_json()
    if not data or "image" not in data or "filename" not in data: abort(400) #...
    try:
        image_data_base64 = data["image"].split(',')[1]
        filename = os.path.basename(data["filename"])
        if not filename.lower().endswith(".png"): abort(400) #...
        file_path = os.path.join(SNAPSHOTS_FOLDER, filename)
        image_bytes = base64.b64decode(image_data_base64)
        with open(file_path, "wb") as f: f.write(image_bytes)
        return jsonify({"status": "success", "path": file_path}), 200
    except Exception as e: #...
        logger.exception(f"Ошибка сохранения снимка: {e}")
        abort(500)


@app.route("/names")
# ... (без изменений) ...
def get_names():
     # ... (код получения имен из БД) ...
    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path): return jsonify([])
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names")
        names_list = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify(names_list)
    except Exception as e: #...
        logger.exception(f"Ошибка чтения БД names: {e}")
        abort(500)

@app.route("/update_label", methods=["POST"])
# ... (без изменений) ...
def update_label():
     # ... (код обновления метки в БД) ...
    data = request.get_json()
    if not data or "id" not in data or "x" not in data or "y" not in data: abort(400)
    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path): return jsonify({"status": "error", "message": "DB not found"}), 404
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE names SET x = ?, y = ? WHERE id = ?", (data["x"], data["y"], data["id"]))
        conn.commit()
        updated_rows = cur.rowcount
        conn.close()
        if updated_rows > 0: return jsonify({"status": "success"}), 200
        else: return jsonify({"status": "error", "message": "Label not found"}), 404
    except Exception as e: #...
        logger.exception(f"Ошибка обновления надписи: {e}")
        abort(500)


@app.route("/add_label", methods=["POST"])
# ... (без изменений) ...
def add_label():
     # ... (код добавления метки в БД) ...
    data = request.get_json()
    if not data or "name" not in data or "type" not in data or "x" not in data or "y" not in data: abort(400)
    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path): return jsonify({"status": "error", "message": "DB not found"}), 404
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO names (name, type, x, y) VALUES (?, ?, ?, ?)",
                    (data["name"], data["type"], data["x"], data["y"]))
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return jsonify({"status": "success", "id": new_id}), 200
    except Exception as e: #...
        logger.exception(f"Ошибка добавления надписи: {e}")
        abort(500)

@app.route("/send_to_arma", methods=["POST"])
def send_to_arma_endpoint():
    """
    Этот эндпоинт теперь отправляет данные через тот же канал (порт 12347),
    что и /send_callback, так как порт 12345 больше не используется для отправки.
    Возможно, его стоит переименовать или удалить, если вся отправка идет через /send_callback.
    """
    data = request.get_json()
    logger.warning(f"Запрос /send_to_arma (отправка через порт 12347): {data}") # Логгируем предупреждение
    if not data: abort(400)
    try:
        # Используем ту же функцию, что и для коллбэков
        run_async_from_sync(arma_connector.send_callback_to_arma_async(data))
        logger.info(f"Данные отправлены в ARMA (порт 12347, асинхронно): {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.exception(f"Ошибка вызова отправки в ARMA (порт 12347): {e}")
        abort(500)


@app.route("/get_buildings", methods=["POST"])
# ... (без изменений) ...
def get_buildings():
     # ... (код получения зданий из БД) ...
    area = request.get_json()
    if not area or not all(k in area for k in ('minX', 'maxX', 'minY', 'maxY')): abort(400)
    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "buildings.db")
    if not os.path.exists(db_path): return jsonify([])
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, x, y, z, interior FROM buildings WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        buildings = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify(buildings)
    except Exception as e: #...
        logger.exception(f"Ошибка получения зданий: {e}")
        abort(500)


@app.route("/get_names_in_area", methods=["POST"])
# ... (без изменений) ...
def get_names_in_area():
    # ... (код получения имен из БД по области) ...
    area = request.get_json()
    if not area or not all(k in area for k in ('minX', 'maxX', 'minY', 'maxY')): abort(400)
    min_x, max_x, min_y, max_y = area['minX'], area['maxX'], area['minY'], area['maxY']
    db_path = os.path.join(DB_DIR, "name.db")
    if not os.path.exists(db_path): return jsonify([])
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, name, type, x, y FROM names WHERE x >= ? AND x <= ? AND y >= ? AND y <= ?",
                    (min_x, max_x, min_y, max_y))
        names = [dict(row) for row in cur.fetchall()]
        conn.close()
        return jsonify(names)
    except Exception as e: #...
        logger.exception(f"Ошибка получения названий: {e}")
        abort(500)


@app.route("/save_json", methods=["POST"])
# ... (без изменений) ...
def save_json():
    # ... (код сохранения JSON) ...
    data = request.get_json()
    if not data or "filename" not in data or "data" not in data: return jsonify({"status": "error", "message": "Invalid parameters"}), 400
    try:
        filename = os.path.basename(data["filename"])
        if not filename.lower().endswith(".json"): return jsonify({"status": "error", "message": "Filename must end with .json"}), 400
        content = data["data"]
        file_path = os.path.join(BASE_DIR, filename)
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(content, f, ensure_ascii=False, indent=4)
        return jsonify({"status": "success", "filename": filename}), 200
    except Exception as e: #...
        logger.exception(f"Ошибка сохранения JSON: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Маршруты LLM ---
@app.route("/initiate_llm_start", methods=["POST"])
def initiate_llm_start():
    """
    Инициирует отправку системного промпта, маркеров и данных о силах.
    Вызывается клиентом после выбора стороны LLM.
    """
    global system_prompt_sent, llm_assigned_side
    data = request.get_json()
    
    # Проверка, что сторона в запросе совпадает с сохраненной на сервере
    if not data or data.get("side") != llm_assigned_side or not llm_assigned_side:
        msg = "Ошибка: сторона не выбрана или не совпадает с серверной."
        logger.error(msg)
        return jsonify({"status": "error", "message": msg}), 400

    # Проверка, чтобы не запускать инициализацию повторно
    if system_prompt_sent:
        msg = "Процесс инициализации LLM уже был запущен ранее."
        logger.warning(msg)
        return jsonify({"status": "error", "message": msg}), 409 # 409 Conflict

    logger.info(f"Получен запрос на инициализацию LLM для стороны: {llm_assigned_side}. Запуск...")
    
    # Сбрасываем флаг перед запуском
    system_prompt_sent = False
    
    async def initialization_wrapper():
        # Ждем новые маркеры. Если они уже пришли, событие сработает мгновенно.
        # Если нет - будем ждать до 10 секунд.
        markers = await arma_connector.get_last_start_mission_markers_async(wait_for_new=True, timeout=10)

        if markers is None:
            logger.error("Не удалось получить маркеры миссии для инициализации LLM. Процесс прерван.")
            # Сообщаем пользователю об ошибке
            await arma_connector.reports_queue.put({
                "t": "llm_log",
                "message": "ОШИБКА: Не удалось получить маркеры от Arma. Инициализация LLM прервана."
            })
            return

        # Если маркеры получены, запускаем основной процесс
        await send_system_prompt(markers)

    # Запускаем нашу обертку в фоне
    if arma_loop:
        asyncio.run_coroutine_threadsafe(
            initialization_wrapper(),
            arma_loop
        )
    
    return jsonify({"status": "success", "message": "Процесс инициализации LLM запущен."})


@app.route("/set_llm_side", methods=["POST"])
def set_llm_side():
    """
    Устанавливает или сбрасывает сторону, за которую играет LLM.
    """
    global llm_assigned_side, system_prompt_sent
    data = request.get_json()
    if data is None or "side" not in data: # Проверка на None
        return jsonify({"status": "error", "message": "Параметр 'side' отсутствует"}), 400
    
    new_side = data.get("side")
    
    if new_side == "":
        llm_assigned_side = None
        system_prompt_sent = False # Сбрасываем флаг, если выбор стороны снят
        logger.info("Выбор стороны для LLM снят, флаг system_prompt_sent сброшен.")
    else:
        llm_assigned_side = new_side
        logger.info(f"Сторона для LLM установлена на: {llm_assigned_side}")

    return jsonify({"status": "success", "side": llm_assigned_side}), 200


@app.route("/llm_models", methods=["GET"])
def get_llm_models():
    global llm_client
    # ... (код без изменений, т.к. get_available_models синхронный) ...
    if not llm_client or not hasattr(llm_client, 'get_available_models'): #...
        return jsonify({"status": "error", "message": "LLMClient не инициализирован"}), 500
    try:
        models = llm_client.get_available_models()
        return jsonify({"status": "success", "models": models}), 200
    except Exception as e: #...
        logger.exception("Ошибка при получении списка LLM моделей")
        return jsonify({"status": "error", "message": "Ошибка получения списка моделей"}), 500

@app.route("/set_llm_model", methods=["POST"])
def set_llm_model():
    global llm_client
    # ... (код без изменений, т.к. set_model синхронный) ...
    data = request.get_json()
    if not llm_client or not hasattr(llm_client, 'set_model'): #...
         return jsonify({"status": "error", "message": "LLMClient не инициализирован"}), 500
    model_name = data.get("model")
    if not model_name: return jsonify({"status": "error", "message": "Отсутствует model"}), 400
    try:
        if llm_client.set_model(model_name):
            return jsonify({"status": "success", "model": model_name}), 200
        else:
            return jsonify({"status": "error", "message": "Ошибка смены модели"}), 500
    except Exception as e: #...
        logger.exception(f"Исключение при смене модели LLM")
        return jsonify({"status": "error", "message": "Внутренняя ошибка сервера"}), 500


@app.route("/llm_command", methods=["POST"])
# Маршрут остается СИНХРОННЫМ, но вызывает async llm_client.send_message
def llm_command():
    global llm_client, system_prompt_sent
    data = request.get_json()
    # ... (проверки llm_client, system_prompt_sent, data) ...
    if not llm_client or "arma_session" not in llm_client.chat_sessions: #...
        return jsonify({"status": "error", "message": "LLM сессия не инициалирована"}), 500
    if not system_prompt_sent: #...
        return jsonify({"status": "error", "message": "Системный промпт еще не отправлен"}), 503
    if not data or "json_input" not in data: #...
        return jsonify({"status": "error", "message": "Отсутствует json_input"}), 400

    json_input = data["json_input"]
    png_path = data.get("png_path")

    try:
        # Преобразуем словарь в строку JSON, если это необходимо
        if isinstance(json_input, dict):
            user_input_str = json.dumps(json_input, ensure_ascii=False)
        else:
            user_input_str = str(json_input)

        # Вызываем async функцию через мост, передавая СТРОКУ
        coro = llm_client.send_message("arma_session", user_input_str, png_path)
        response = run_async_from_sync(coro)

        if response:
            # Создаем сообщение для трансляции всем клиентам
            llm_response_message = {
                "t": "llm_response",
                "message": response  # response - это строка, которую вернул LLM
            }
            logger.info(f"ТОЧКА 1: Попытка поместить в очередь: {llm_response_message}")
            # Помещаем ответ в очередь reports_queue для трансляции
            if arma_loop:
                asyncio.run_coroutine_threadsafe(
                    arma_connector.reports_queue.put(llm_response_message), 
                    arma_loop
                )
            
            # Возвращаем простой успешный ответ, подтверждающий получение команды
            return jsonify({"status": "success", "message": "Command received and queued"}), 200
        elif response is None and arma_loop and arma_loop.is_running(): # Явно проверяем None от run_async_from_sync
             logger.error(f"Получен пустой ответ от LLM или ошибка/таймаут в run_async_from_sync.")
             return jsonify({"status": "error", "message": "Пустой ответ или ошибка LLM"}), 500
        else: # Цикл не работает
             logger.error("Не удалось выполнить команду LLM, т.к. цикл arma_connector не работает.")
             return jsonify({"status": "error", "message": "LLM command failed (connector loop down)"}), 500
    except Exception as e:
        logger.exception(f"Ошибка в llm_command: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- БЛОК if __name__ == "__main__": (ОСТАЕТСЯ ПУСТЫМ) ---
if __name__ == "__main__":
    logger.warning("Скрипт server.py запущен напрямую (не через waitress).")
    logger.warning("Для продакшена используйте: waitress-serve --host=0.0.0.0 --port=5000 server:app")
    # Если нужна отладка с Flask сервером, можно раскомментировать app.run,
    # но нужно убедиться, что поток run_arma_loop корректно запускается и останавливается.
    pass

# --- КОНЕЦ ФАЙЛА server.py ---