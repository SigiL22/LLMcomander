# --- START OF FILE arma_connector_async.py (Без порта 12345) ---

import asyncio
import json
import logging
import time
from asyncio import StreamReader, StreamWriter, Lock, Queue

# --- Настройка логгера (без изменений) ---
logger = logging.getLogger("ArmaConnectorAsync")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
# ---

# --- Глобальное состояние и примитивы asyncio ---
arma_data = None
data_lock = Lock()
reports_queue = Queue()

# --- УДАЛЕНО: writer_12345 ---
writer_12347: StreamWriter | None = None # Оставляем только writer для callback'ов
# ---

# --- Функция handle_arma_connection (Без изменений) ---
# Обрабатывает входящие подключения от Arma на порт 12346
async def handle_arma_connection(reader: StreamReader, writer: StreamWriter):
    global arma_data
    peername = writer.get_extra_info('peername')
    logger.debug(f"Подключение от Arma {peername} (на порт 12346)")
    received = bytearray()
    try:
        while True:
            chunk = await reader.read(8192)
            if not chunk:
                logger.debug(f"Соединение {peername} закрыто Arma.")
                break
            received.extend(chunk)
            try:
                decoded_check = received.decode('utf-8')
                if decoded_check == "[start_mission]" or \
                   ('{' in decoded_check and decoded_check.count('{') == decoded_check.count('}')):
                   logger.debug(f"Предположительно получено полное сообщение от {peername} ({len(received)} байт), обрабатываем...")
                   break
            except UnicodeDecodeError:
                continue
        # --- (Остальная логика обработки полученных данных без изменений) ---
        if received:
            try:
                decoded_data = received.decode('utf-8')
                if decoded_data == "[start_mission]":
                    async with data_lock:
                        arma_data = None
                    await reports_queue.put({"command": "start_mission"})
                    logger.info("Получена команда start_mission от ARMA.")
                else:
                    parsed_data = json.loads(decoded_data)
                    if isinstance(parsed_data, dict) and "sides" in parsed_data:
                        async with data_lock:
                            arma_data = parsed_data
                        logger.info("Данные от ARMA (update_data) приняты.")
                    elif isinstance(parsed_data, list):
                        report_count = 0
                        for report in parsed_data:
                            if isinstance(report, list):
                                try:
                                    report_dict = dict(report)
                                    await reports_queue.put(report_dict)
                                    report_count += 1
                                except (ValueError, TypeError) as e:
                                    logger.error(f"Ошибка преобразования репорта: {report}, {e}")
                            else:
                                logger.error(f"Неверный формат репорта: {report}")
                        logger.info(f"Принято {report_count} репортов от ARMA.")
                    else:
                        logger.error(f"Неизвестный формат данных JSON от Arma: {type(parsed_data)}")
            # ... (обработка ошибок JSON, Unicode) ...
            except json.JSONDecodeError as e: logger.error(f"Ошибка JSON: {e}")
            except UnicodeDecodeError as e: logger.error(f"Ошибка UTF-8: {e}")
            except Exception as e: logger.exception(f"Ошибка обработки данных: {e}")
    # ... (обработка ошибок соединения) ...
    except asyncio.IncompleteReadError: logger.warning(f"Соединение {peername} закрыто не полностью.")
    except ConnectionResetError: logger.warning(f"Соединение {peername} сброшено.")
    except Exception as e: logger.exception(f"Ошибка handle_arma_connection {peername}: {e}")
    finally:
        # ... (закрытие writer) ...
        try: writer.close(); await writer.wait_closed()
        except Exception: pass
        logger.debug(f"Соединение с {peername} закрыто.")

# --- Функции для установки и управления исходящими соединениями ---
# connect_to_arma остается без изменений
async def connect_to_arma(host: str, port: int, max_retries: int = 5, delay: int = 2) -> StreamWriter | None:
    logger.info(f"Попытка установить постоянное соединение с Arma на {host}:{port}...")
    retries = 0
    while retries < max_retries:
        try:
            _, writer = await asyncio.open_connection(host, port)
            logger.info(f"Успешно установлено соединение с Arma на {host}:{port}")
            return writer
        except ConnectionRefusedError:
            logger.warning(f"Соединение с {host}:{port} отклонено. Попытка {retries + 1}/{max_retries}. Повтор через {delay} сек...")
        # ... (остальная обработка ошибок) ...
        except OSError as e: logger.error(f"Ошибка сокета {host}:{port}: {e}. Попытка {retries + 1}/{max_retries}.")
        except Exception as e: logger.exception(f"Ошибка подключения {host}:{port}: {e}. Попытка {retries + 1}/{max_retries}.")
        retries += 1
        if retries < max_retries: await asyncio.sleep(delay); delay = min(delay * 2, 30)
    logger.error(f"Не удалось подключиться к Arma на {host}:{port} после {max_retries} попыток.")
    return None

# initialize_connections теперь подключается только к порту 12347
async def initialize_connections(host: str = '127.0.0.1'):
    global writer_12347 # Убрали writer_12345
    logger.info("Инициализация исходящего соединения Arma (порт 12347)...")
    writer_12347 = await connect_to_arma(host, 12347)
    if writer_12347:
        logger.info("Исходящее соединение на порт 12347 установлено.")
    else:
        logger.error("Не удалось установить исходящее соединение на порт 12347.")
    logger.info("Инициализация исходящих соединений завершена.")

# --- Асинхронные функции для отправки данных в Arma ---
# _send_message_persistent остается без изменений
async def _send_message_persistent(writer: StreamWriter | None, host: str, port: int, message_data: bytes) -> StreamWriter | None:
    current_writer = writer
    if current_writer is None or current_writer.is_closing():
        logger.warning(f"Соединение на {host}:{port} отсутствует/закрывается. Переподключение...")
        current_writer = await connect_to_arma(host, port)
        if current_writer is None:
            logger.error(f"Не удалось переподключиться к {host}:{port} для отправки.")
            return None
    try:
        logger.debug(f"Отправка {len(message_data)} байт на {host}:{port}...")
        current_writer.write(message_data)
        await current_writer.drain()
        logger.debug(f"Данные успешно отправлены на {host}:{port}.")
        return current_writer
    # ... (обработка ошибок) ...
    except (ConnectionResetError, BrokenPipeError) as e:
        logger.error(f"Ошибка соединения при отправке на {host}:{port}: {e}.")
        try: current_writer.close(); await current_writer.wait_closed()
        except Exception: pass
        return None
    except Exception as e:
        logger.exception(f"Ошибка отправки на {host}:{port}: {e}")
        try: current_writer.close(); await current_writer.wait_closed()
        except Exception: pass
        return None

async def mark_report_done():
    """Асинхронная обертка для reports_queue.task_done()."""
    try:
        reports_queue.task_done()
    except ValueError:
        # task_done() может вызвать ValueError, если вызван для пустой очереди
        # или больше раз, чем было put. Логгируем это.
        logger.warning("Попытка вызвать task_done() для очереди репортов, когда это не ожидалось.")
    except Exception as e:
        logger.exception("Неожиданная ошибка при вызове task_done() для очереди репортов.")

# send_callback_to_arma_async остается без изменений (отправляет на 12347)
async def send_callback_to_arma_async(message: dict | str, host: str = '127.0.0.1'):
    global writer_12347
    try:
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        encoded_data = json_data.encode('utf-8')
        writer_12347 = await _send_message_persistent(writer_12347, host, 12347, encoded_data)
        if writer_12347:
             logger.info(f"Callback отправлен в ARMA (12347): {json_data[:100]}...")
        else:
             logger.error(f"Не удалось отправить callback в ARMA (12347): {json_data[:100]}...")
    except Exception as e:
        logger.exception(f"Критическая ошибка в send_callback_to_arma_async: {e}")

# --- Функция get_arma_data_async (добавлена ранее) ---
async def get_arma_data_async():
    """Асинхронно и безопасно возвращает текущие данные arma_data."""
    async with data_lock:
        return arma_data

# --- Функция start_server (слушает только 12346) ---
async def start_server(host: str = '127.0.0.1', port: int = 12346):
    server = await asyncio.start_server(handle_arma_connection, host, port)
    addr = server.sockets[0].getsockname()
    logger.info(f"Async ARMA сервер запущен и слушает на {addr}")
    await initialize_connections(host) # Инициализируем исходящее на 12347
    async with server:
        await server.serve_forever()

# --- Тестовый блок (если нужен) ---
if __name__ == '__main__':
    # ... (можно оставить для тестов) ...
    pass

# --- КОНЕЦ ФАЙЛА arma_connector_async.py (Без порта 12345) ---