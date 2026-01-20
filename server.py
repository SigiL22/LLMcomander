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

def normalize_side(side_str: str) -> str:
    """
    Приводит различные варианты названий сторон в Arma 3 к единому стандарту (EAST, WEST, GUER, CIV).
    Используется для корректного сравнения сторон.
    """
    if not isinstance(side_str, str):
        return ""
    s = side_str.upper().strip()
    if s in ["EAST", "OPFOR", "RUS"]: return "EAST"
    if s in ["WEST", "BLUFOR", "USA"]: return "WEST"
    if s in ["GUER", "INDEPENDENT", "RESISTANCE", "IND"]: return "GUER"
    if s in ["CIV", "CIVILIAN"]: return "CIV"
    return s

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
llm_enemy_side: str | None = None    # <<< ДОБАВИТЬ ЭТУ ПЕРЕМЕННУЮ
last_auto_config_time = 0 # <<< ДОБАВИТЬ ЭТУ ПЕРЕМЕННУЮ
roll_call_interval_seconds = 300 # По умолчанию 5 минут
roll_call_thread = None
roll_call_running = False
roll_call_event = threading.Event() # Используем Event для прерывания сна
llm_report_batch_interval_seconds = 10  # Интервал сбора (сек), значение по умолчанию
llm_report_batch = []                   # Список для накопления докладов
batch_lock = asyncio.Lock()             # Lock для безопасного доступа к списку
batch_timer_task: asyncio.Task | None = None # Ссылка на задачу-таймер
current_mission_snapshots = [] # Список путей к актуальным снимкам

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

# --- НОВЫЙ МАРШРУТ ДЛЯ УСТАНОВКИ ИНТЕРВАЛА ---
@app.route("/set_llm_batch_interval", methods=["POST"])
def set_llm_batch_interval_route():
    global llm_report_batch_interval_seconds
    data = request.get_json()
    try:
        new_interval_secs = int(data["interval"])
        if new_interval_secs < 1:
             return jsonify({"status": "error", "message": "Интервал должен быть положительным"}), 400
        
        llm_report_batch_interval_seconds = new_interval_secs
        logger.info(f"Интервал сбора докладов LLM установлен на: {new_interval_secs} сек")
        return jsonify({"status": "success", "interval": new_interval_secs}), 200
    except (ValueError, TypeError, KeyError):
         return jsonify({"status": "error", "message": "Неверное значение интервала"}), 400
    except Exception as e:
         logger.exception(f"Ошибка в /set_llm_batch_interval: {e}")
         return jsonify({"status": "error", "message": str(e)}), 500

# 1. НОВАЯ вспомогательная асинхронная функция для таймера
async def batch_timer_coroutine():
    """
    Простая корутина, которая ждет заданный интервал,
    а затем вызывает обработчик пакета докладов.
    """
    global llm_report_batch_interval_seconds
    logger.debug(f"Таймер запущен, ожидание {llm_report_batch_interval_seconds} сек...")
    await asyncio.sleep(llm_report_batch_interval_seconds)
    await process_and_send_llm_batch()

# 2. ОБНОВЛЕННАЯ функция обработки пакета
async def process_and_send_llm_batch():
    """
    Вызывается по таймеру. Собирает накопленные доклады,
    отправляет их в контроллер и очищает пакет.
    """
    global llm_report_batch, batch_timer_task, llm_client, llm_assigned_side
    
    async with batch_lock:
        if not llm_report_batch:
            batch_timer_task = None
            logger.debug("Таймер сработал, но пакет пуст. Ничего не отправляем.")
            return
            
        reports_to_process = llm_report_batch[:]
        llm_report_batch.clear()
        # Сбрасываем задачу-таймер, чтобы можно было запустить новую
        batch_timer_task = None
        logger.info(f"Таймер сработал. Обработка пакета из {len(reports_to_process)} докладов.")

    if llm_client and llm_assigned_side:
        await llm_tactical_controller.trigger_llm_batch_report(
            llm_client,
            llm_assigned_side,
            reports_to_process
        )

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
        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        try:
            while True:
                if not arma_loop or not arma_loop.is_running():
                    logger.warning("SSE arma_data: Цикл Arma Connector не работает, разрыв соединения.")
                    break

                current_data = run_async_from_sync(get_arma_data_wrapper())
                current_data_str = json.dumps(current_data) if current_data else None

                if current_data_str != last_data_str and current_data is not None:
                    last_data_str = current_data_str
                    # `yield` может вызвать исключение при отключении клиента
                    yield f"data: {json.dumps({'status': 'success', 'data': current_data})}\n\n"
                
                time.sleep(0.1)
        # Ловим исключение, которое Flask/Waitress генерирует при отключении клиента
        except GeneratorExit:
            logger.info("Клиент /arma_data_stream отключился (GeneratorExit).")
        except Exception as e:
            # Ловим другие возможные ошибки, например BrokenPipeError
            logger.warning(f"Ошибка в цикле arma_data_stream (вероятно, клиент отключился): {e}")
        finally:
            logger.info("Завершение потока для /arma_data_stream.")
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
            
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/reports_stream")
def reports_stream():
    logger.info("Новое подключение к /reports_stream")
    def event_stream():
        # Добавляем llm_enemy_side в global
        global system_prompt_sent, llm_assigned_side, llm_enemy_side, llm_client, batch_timer_task
        try:
            while True:
                async def get_report_non_blocking():
                    try: 
                        return await asyncio.wait_for(arma_connector.reports_queue.get(), timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.QueueEmpty): 
                        return None

                report = run_async_from_sync(get_report_non_blocking())

                if report:
                    # --- НАЧАЛО ИЗМЕНЕНИЙ: Обработка start_mission и автозапуск ---
                    if report.get("command") == "start_mission":
                        # 1. Пытаемся получить конфиг из верхнего уровня (как планировали)
                        config_str = report.get("config", "")
                        
                        # 2. FALLBACK: Если наверху пусто, ищем внутри массива маркеров
                        if not config_str and "markers" in report:
                            logger.info("Конфиг не найден в корне, поиск внутри маркеров...")
                            for m in report["markers"]:
                                text = m.get("text", "")
                                if not text: continue
                                # Проверяем наличие ключевых флагов в тексте маркера
                                text_lower = text.lower()
                                if "l-" in text_lower and "a-" in text_lower:
                                    config_str = text
                                    logger.info(f"Конфиг найден внутри маркера '{m.get('name')}': {config_str}")
                                    break                                
                                    
                        report["config"] = config_str 
                        new_llm_side = None
                        new_enemy_side = None
                        
                        if config_str:
                            try:
                                # Пример строки: "a-opfor,d-blufor,l-opfor"
                                parts = config_str.split(',')
                                config_map = {}
                                for part in parts:
                                    if '-' in part:
                                        key, val = part.split('-', 1)
                                        config_map[key.strip().lower()] = val.strip().upper()
                                
                                # Если указана сторона LLM (l-)
                                if 'l' in config_map:
                                    raw_llm_side = config_map['l']
                                    new_llm_side = normalize_side(raw_llm_side)
                                    
                                    # Логика определения врага:
                                    if 'a' in config_map and normalize_side(config_map['a']) == new_llm_side:
                                        new_enemy_side = normalize_side(config_map.get('d', ''))
                                    elif 'd' in config_map and normalize_side(config_map['d']) == new_llm_side:
                                        new_enemy_side = normalize_side(config_map.get('a', ''))
                                  
                                logger.info(f"Распаршен конфиг миссии: {config_map}. LLM: {new_llm_side}, Враг: {new_enemy_side}")
                            except Exception as e:
                                logger.error(f"Ошибка парсинга конфига миссии '{config_str}': {e}")

                        # Применяем настройки
                        if new_llm_side:
                            llm_assigned_side = new_llm_side
                            llm_enemy_side = new_enemy_side
                            
                            global last_auto_config_time # Не забудьте добавить global в начале функции event_stream если нужно, но здесь python найдет её в module scope
                            last_auto_config_time = time.time() 
                            
                            # Сбрасываем сессию LLM (очистка истории)
                            if llm_client:
                                llm_client.create_session("arma_session")
                            
                            system_prompt_sent = False
                            
                            # АВТОМАТИЧЕСКИЙ ЗАПУСК
                            # Мы сохраняем сторону, но НЕ запускаем инициализацию LLM здесь.
                            # Теперь инициализацию запускает КЛИЕНТ (JS) после того, как сделает и загрузит снимки.
                            
                            # markers = report.get("markers", [])
                            # async def auto_start_wrapper(m):
                            #    ... 
                            #    await send_system_prompt(m)
                                
                            # if arma_loop:
                            #    asyncio.run_coroutine_threadsafe(auto_start_wrapper(markers), arma_loop)
                            
                            logger.info("Автоконфигурация стороны выполнена. Ждем снимки и команду старта от клиента.")
                        else:
                            llm_assigned_side = None
                            llm_enemy_side = None
                            logger.info("Конфиг не найден или не содержит 'l-', ожидание ручного выбора стороны.")

                    log_msg_part = report.get('command', report.get('t', 'Unknown'))
                    logger.info(f"ТОЧКА 2: Извлечено из очереди и отправляется клиенту: {log_msg_part}")
                    
                    report_type = report.get("t")
                    # Проверяем, что сторона совпадает (с учетом врага и своей стороны)
                    if system_prompt_sent and llm_assigned_side and report.get("s") and \
                       report_type and \
                       normalize_side(report.get("s")) == normalize_side(llm_assigned_side):
                        
                        async def manage_batch(new_report):
                            global batch_timer_task
                            async with batch_lock:
                                llm_report_batch.append(new_report)
                                if batch_timer_task is None or batch_timer_task.done():
                                    logger.info(f"Первый доклад в пакете. Запуск таймера.")
                                    batch_timer_task = asyncio.create_task(batch_timer_coroutine())
                        
                        run_async_from_sync(manage_batch(report))
                    
                    yield f"data: {json.dumps(report)}\n\n"
                else:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            logger.info("Клиент /reports_stream отключился (GeneratorExit).")
        except Exception as e:
            logger.warning(f"Ошибка в цикле reports_stream (вероятно, клиент отключился): {e}")
        finally:
            logger.info("Завершение потока для /reports_stream.")
            
    return Response(event_stream(), mimetype="text/event-stream")


# --- Функция send_system_prompt (принимает markers, async) ---
async def send_system_prompt(markers: list = None):
    # 1. Добавляем current_mission_snapshots в global
    global system_prompt_sent, llm_client, llm_assigned_side, llm_enemy_side, current_mission_snapshots
    
    if not llm_assigned_side:
        logger.error("ОШИБКА: Попытка инициализации без выбранной стороны LLM.")
        return False

    if not llm_client or not llm_client.is_operational:
         logger.error("ОШИБКА: LLM клиент не готов.")
         return False

    # Получаем текст системного промпта из памяти клиента
    sys_prompt_text = llm_client.system_prompt
    if not sys_prompt_text:
        logger.error("ОШИБКА: Системный промпт пуст.")
        return False

    logger.info(f"--- НАЧАЛО ИНИЦИАЛИЗАЦИИ МИССИИ ({llm_assigned_side}) ---")

    # 1. ЦИКЛ ОЖИДАНИЯ ДАННЫХ
    logger.info("Ждем данные о войсках от Arma...")
    data_received = False
    for i in range(10): # 10 попыток по 0.5 сек = 5 секунд
        async with arma_connector.data_lock:
            if arma_connector.arma_data is not None:
                data_received = True
                break
        await asyncio.sleep(0.5)

    if not data_received:
        logger.error("ВНИМАНИЕ: Тайм-аут ожидания данных о войсках! Отправляем только маркеры.")
    else:
        logger.info("Данные о войсках успешно получены.")

    # 2. Получаем и фильтруем данные
    async with arma_connector.data_lock:
        current_arma_data = arma_connector.arma_data
    
    # Фильтруем данные только для нашей стороны
    filtered_forces = llm_tactical_controller.filter_data_for_llm(current_arma_data, llm_assigned_side)

    # 3. Формируем единый JSON (Маркеры + Силы)
    initial_data_payload = {}

    # -- Добавляем маркеры --
    if markers:
        optimized_markers = []
        for m in markers:
            marker_data = {
                "t": m.get("type"),
                "p": m.get("pos"),
                "text": m.get("text"),
            }
            size = m.get("size")
            if size and (size[0] > 1 or size[1] > 1):
                marker_data["size"] = size
            optimized_markers.append(marker_data)
        initial_data_payload["mission_markers"] = optimized_markers
        logger.info(f"Добавлено маркеров: {len(optimized_markers)}")

    # -- Добавляем силы --
    if filtered_forces:
        initial_data_payload["your_forces"] = filtered_forces
        logger.info(f"Добавлено групп своих войск: {len(filtered_forces)}")
    else:
        logger.warning(f"Данные о войсках ПУСТЫ после фильтрации для стороны {llm_assigned_side}!")

    # 4. Формируем контекст (Текст заголовка)
    context_header = f"Initial mission data. You are commanding side: {llm_assigned_side}."
    if llm_enemy_side:
        context_header += f" Your primary enemy is: {llm_enemy_side}."

    # --- НОВАЯ ЛОГИКА ДЛЯ ИЗОБРАЖЕНИЙ ---
    images_to_send = []
    if current_mission_snapshots:
        logger.info(f"Прикрепляем {len(current_mission_snapshots)} снимков к запросу инициализации.")
        images_to_send = current_mission_snapshots
    else:
        logger.info("Снимки карты не были загружены клиентом. Отправляем только текстовые данные.")
    # -------------------------------------

    # 5. Склеиваем всё в одну строку для отправки и ОТПРАВЛЯЕМ
    try:
        json_str = json.dumps(initial_data_payload, ensure_ascii=False)
        
        full_combined_prompt = (
            f"{sys_prompt_text}\n\n"       # СИСТЕМНАЯ ИНСТРУКЦИЯ
            f"--- MISSION CONTEXT ---\n"
            f"{context_header}\n\n"        # КОНТЕКСТ СТОРОН
            f"--- MISSION DATA JSON ---\n"
            f"{json_str}"                  # JSON С ДАННЫМИ
        )
        
        logger.info(f"Отправка ОБЪЕДИНЕННОГО запроса в LLM ({len(full_combined_prompt)} символов + {len(images_to_send)} изображений)...")
        
        # --- ИЗМЕНЕННЫЙ ВЫЗОВ (добавлен image_paths) ---
        response = await llm_client.send_message(
            "arma_session", 
            user_input=full_combined_prompt,
            image_paths=images_to_send # Передаем список путей к картинкам
        )
        
        # Очищаем список снимков после отправки, чтобы они не ушли со следующим сообщением
        current_mission_snapshots = []
        
        # Обрабатываем ответ
        await llm_tactical_controller.handle_llm_response(response)
        
        system_prompt_sent = True 
        
        # Пишем в чат
        await arma_connector.reports_queue.put({
            "t": "llm_log",
            "message": f"Миссия инициализирована. Силы: {len(filtered_forces) if filtered_forces else 0} отрядов. Снимков карты: {len(images_to_send)}."
        })
        return True

    except Exception as e:
        logger.exception("Критическая ошибка при отправке объединенных данных в LLM.")
        # Даже при ошибке лучше очистить список снимков, чтобы не застрять
        current_mission_snapshots = []
        return False

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
    
    # --- ИСПРАВЛЕНИЕ: Нормализация сторон перед сравнением ---
    client_side_raw = data.get("side") if data else ""
    
    # Приводим обе стороны к единому формату (EAST, WEST...)
    normalized_client_side = normalize_side(client_side_raw)
    normalized_server_side = normalize_side(llm_assigned_side)

    # Проверка совпадения
    if not client_side_raw or normalized_client_side != normalized_server_side or not llm_assigned_side:
        msg = f"Ошибка: сторона не выбрана или не совпадает. Клиент: {client_side_raw} ({normalized_client_side}), Сервер: {llm_assigned_side} ({normalized_server_side})"
        logger.error(msg)
        return jsonify({"status": "error", "message": msg}), 400
    # ---------------------------------------------------------

    # Проверка, чтобы не запускать инициализацию повторно
    if system_prompt_sent:
        msg = "Процесс инициализации LLM уже был запущен ранее."
        logger.warning(msg)
        return jsonify({"status": "error", "message": msg}), 409

    logger.info(f"Получен запрос на инициализацию LLM для стороны: {llm_assigned_side}. Запуск...")
    
    system_prompt_sent = False
    
    async def initialization_wrapper():
        # Ждем новые маркеры (или берем последние)
        markers = await arma_connector.get_last_start_mission_markers_async(wait_for_new=False)
        
        # Если маркеров нет в памяти, пробуем подождать чуть-чуть
        if markers is None:
             markers = await arma_connector.get_last_start_mission_markers_async(wait_for_new=True, timeout=5)

        if markers is None:
            logger.error("Не удалось получить маркеры миссии. Инициализация LLM прервана.")
            await arma_connector.reports_queue.put({
                "t": "llm_log",
                "message": "ОШИБКА: Не удалось получить данные маркеров."
            })
            return

        await send_system_prompt(markers)

    if arma_loop:
        asyncio.run_coroutine_threadsafe(
            initialization_wrapper(),
            arma_loop
        )
    
    return jsonify({"status": "success", "message": "Процесс инициализации LLM запущен."})


@app.route("/set_llm_side", methods=["GET", "POST"]) # <<< Добавлен GET
def set_llm_side():
    """
    GET: Возвращает текущую установленную сторону LLM.
    POST: Устанавливает или сбрасывает сторону.
    """
    global llm_assigned_side, system_prompt_sent, last_auto_config_time, llm_client # добавлены global

    # --- НОВАЯ ЧАСТЬ: Обработка GET запроса ---
    if request.method == "GET":
        return jsonify({"status": "success", "side": llm_assigned_side}), 200
    # ------------------------------------------

    # Обработка POST (существующий код)
    data = request.get_json()
    if data is None or "side" not in data:
        return jsonify({"status": "error", "message": "Параметр 'side' отсутствует"}), 400
    
    new_side = data.get("side")
    
    if new_side == "":
        # Если с момента автоконфигурации прошло менее 5 секунд, игнорируем сброс
        if time.time() - last_auto_config_time < 5:
            logger.info(f"Игнорирование сброса стороны клиентом, так как активна автоконфигурация ({llm_assigned_side}).")
            return jsonify({"status": "ignored", "side": llm_assigned_side}), 200

        llm_assigned_side = None
        system_prompt_sent = False
        if llm_client:
            llm_client.create_session("arma_session")
        logger.info("Выбор стороны для LLM снят, сессия LLM и флаги сброшены.")
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
        
@app.route("/upload_mission_snapshots", methods=["POST"])
def upload_mission_snapshots():
    global current_mission_snapshots
    data = request.get_json()
    if not data or "snapshots" not in data:
        return jsonify({"status": "error", "message": "No snapshots data"}), 400
    
    saved_paths = []
    try:
        # Очищаем старые снимки из списка (но файлы можно оставить в папке snapshots для истории)
        current_mission_snapshots = []
        
        for i, snap in enumerate(data["snapshots"]):
            # snap: { "type": "strategic"/"tactical", "image": "base64...", "filename": "..." }
            image_data_b64 = snap["image"].split(',')[1]
            filename = snap.get("filename", f"snap_{i}.png")
            
            # Сохраняем во временную папку или snapshots
            file_path = os.path.join(SNAPSHOTS_FOLDER, filename)
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(image_data_b64))
            
            saved_paths.append(file_path)
        
        # Обновляем глобальную переменную
        current_mission_snapshots = saved_paths
        logger.info(f"Получено и сохранено {len(saved_paths)} снимков миссии от клиента.")
        
        return jsonify({"status": "success", "count": len(saved_paths)}), 200
    except Exception as e:
        logger.exception("Ошибка при сохранении снимков миссии")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- БЛОК if __name__ == "__main__": (ОСТАЕТСЯ ПУСТЫМ) ---
if __name__ == "__main__":
    logger.warning("Скрипт server.py запущен напрямую (не через waitress).")
    logger.warning("Для продакшена используйте: waitress-serve --host=0.0.0.0 --port=5000 server:app")
    # Если нужна отладка с Flask сервером, можно раскомментировать app.run,
    # но нужно убедиться, что поток run_arma_loop корректно запускается и останавливается.
    pass

# --- КОНЕЦ ФАЙЛА server.py ---