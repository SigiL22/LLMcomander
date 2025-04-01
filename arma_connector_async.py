# --- START OF FILE arma_connector_async.py (с бесконечным переподключением) ---

import asyncio
import json
import logging
import time
from asyncio import StreamReader, StreamWriter, Lock, Queue

# --- Настройка логгера (без изменений) ---
logger = logging.getLogger("ArmaConnectorAsync")
# ---

# --- Глобальное состояние и примитивы asyncio (без изменений) ---
arma_data = None
data_lock = Lock()
reports_queue = Queue()
writer_12347: StreamWriter | None = None
# ---

# --- Функция handle_arma_connection (Без изменений) ---
async def handle_arma_connection(reader: StreamReader, writer: StreamWriter):
    # ... (код как в предыдущей версии) ...
    global arma_data; peername = writer.get_extra_info('peername'); logger.debug(f"Подключение от Arma {peername} (12346)")
    received = bytearray()
    try:
        while True:
            chunk = await reader.read(8192);
            if not chunk: logger.debug(f"Соединение {peername} закрыто Arma."); break
            received.extend(chunk)
            try:
                decoded_check = received.decode('utf-8')
                if decoded_check == "[start_mission]" or ('{' in decoded_check and decoded_check.count('{') == decoded_check.count('}')): break
            except UnicodeDecodeError: continue
        if received:
            try:
                decoded_data = received.decode('utf-8')
                if decoded_data == "[start_mission]":
                    async with data_lock: arma_data = None
                    await reports_queue.put({"command": "start_mission"}); logger.info("start_mission получен.")
                else:
                    parsed_data = json.loads(decoded_data)
                    if isinstance(parsed_data, dict) and "sides" in parsed_data:
                        async with data_lock: arma_data = parsed_data; logger.info("update_data принято.")
                    elif isinstance(parsed_data, list):
                        count = 0
                        for report in parsed_data:
                            if isinstance(report, list):
                                try: await reports_queue.put(dict(report)); count += 1
                                except Exception as e: logger.error(f"Ошибка репорта: {report}, {e}")
                            else: logger.error(f"Неверный формат репорта: {report}")
                        logger.info(f"Принято {count} репортов.")
                    else: logger.error(f"Неизвестный формат JSON: {type(parsed_data)}")
            except json.JSONDecodeError as e: logger.error(f"Ошибка JSON: {e}")
            except UnicodeDecodeError as e: logger.error(f"Ошибка UTF-8: {e}")
            except Exception as e: logger.exception(f"Ошибка обработки данных: {e}")
    except asyncio.IncompleteReadError: logger.warning(f"Соед. {peername} закрыто не полностью.")
    except ConnectionResetError: logger.warning(f"Соед. {peername} сброшено.")
    except Exception as e: logger.exception(f"Ошибка handle_arma_connection {peername}: {e}")
    finally:
        try: writer.close(); await writer.wait_closed()
        except Exception: pass; logger.debug(f"Соед. с {peername} закрыто.")

# --- ИЗМЕНЕННАЯ ФУНКЦИЯ УСТАНОВКИ СОЕДИНЕНИЯ ---
async def connect_to_arma(host: str, port: int, initial_delay: int = 3) -> StreamWriter:
    """
    Бесконечно пытается установить постоянное соединение с Arma для отправки.
    Возвращает StreamWriter только при успехе.
    """
    logger.info(f"Попытка установить постоянное соединение с Arma на {host}:{port} (бесконечные попытки)...")
    attempt = 0
    delay = initial_delay
    while True: # Бесконечный цикл попыток
        attempt += 1
        try:
            # Устанавливаем таймаут на саму операцию подключения
            # Это полезно, если ОС "замораживает" попытку надолго при недоступности хоста
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10.0)
            logger.info(f"УСПЕШНО установлено соединение с Arma на {host}:{port} (попытка {attempt})")
            return writer # Возвращаем writer ТОЛЬКО при успехе
        except ConnectionRefusedError:
            logger.warning(f"Соединение с {host}:{port} отклонено (Arma не запущена?). Попытка {attempt}. Повтор через {delay} сек...")
        except asyncio.TimeoutError:
             logger.warning(f"Таймаут при попытке подключения к {host}:{port}. Попытка {attempt}. Повтор через {delay} сек...")
        except OSError as e:
             logger.error(f"Ошибка сокета при подключении к {host}:{port}: {e}. Попытка {attempt}. Повтор через {delay} сек...")
        except Exception as e:
            logger.exception(f"Неизвестная ошибка при подключении к {host}:{port}: {e}. Попытка {attempt}. Повтор через {delay} сек...")

        # Ждем перед следующей попыткой
        await asyncio.sleep(delay)
        # Можно добавить логику увеличения задержки, но для локалхоста 3 сек достаточно
        # delay = min(delay + 1, 30) # Например, увеличиваем на 1 сек до макс. 30

# --- initialize_connections (без существенных изменений, но теперь вызывает новую connect_to_arma) ---
async def initialize_connections(host: str = '127.0.0.1'):
    """Инициализирует постоянное исходящее соединение (теперь с бесконечными попытками)."""
    global writer_12347
    logger.info("Инициализация исходящего соединения Arma (порт 12347)...")
    # connect_to_arma теперь будет пытаться бесконечно,
    # поэтому initialize_connections будет "висеть" здесь, пока не подключится.
    # Это нормально, т.к. вызывается один раз при старте в asyncio цикле.
    writer_12347 = await connect_to_arma(host, 12347)
    # Если мы дошли сюда, значит, соединение установлено
    logger.info("Исходящее соединение на порт 12347 инициализировано.")
    # logger.info("Инициализация исходящих соединений завершена.") # Это сообщение теперь излишне

# --- Асинхронные функции для отправки данных в Arma ---
# _send_message_persistent теперь полагается на connect_to_arma для переподключения
async def _send_message_persistent(writer: StreamWriter | None, host: str, port: int, message_data: bytes) -> StreamWriter | None:
    """Внутренняя функция для отправки через постоянное соединение с бесконечным переподключением."""
    current_writer = writer
    if current_writer is None or current_writer.is_closing():
        logger.warning(f"Соединение на {host}:{port} отсутствует/закрывается. Переподключение (бесконечные попытки)...")
        # connect_to_arma теперь будет пытаться бесконечно, пока не подключится
        current_writer = await connect_to_arma(host, port)
        # Если мы здесь, значит, переподключились успешно
        logger.info(f"Переподключение к {host}:{port} успешно.")

    # После успешного (пере)подключения, пытаемся отправить
    try:
        logger.debug(f"Отправка {len(message_data)} байт на {host}:{port}...")
        current_writer.write(message_data)
        await current_writer.drain()
        logger.debug(f"Данные успешно отправлены на {host}:{port}.")
        return current_writer # Возвращаем активный writer
    except (ConnectionResetError, BrokenPipeError, OSError) as e: # Добавили OSError
        logger.error(f"Ошибка соединения при отправке на {host}:{port}: {e}. Соединение будет восстановлено при следующей попытке.")
        try:
            current_writer.close()
            await current_writer.wait_closed()
        except Exception: pass
        # Возвращаем None, чтобы при следующей отправке сработала логика переподключения
        return None
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при отправке на {host}:{port}: {e}")
        try:
            current_writer.close()
            await current_writer.wait_closed()
        except Exception: pass
        return None # Тоже возвращаем None

# --- send_callback_to_arma_async (без изменений, вызывает _send_message_persistent) ---
async def send_callback_to_arma_async(message: dict | str, host: str = '127.0.0.1'):
    global writer_12347
    try:
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        encoded_data = json_data.encode('utf-8')
        # _send_message_persistent теперь сам обработает переподключение, если нужно
        new_writer = await _send_message_persistent(writer_12347, host, 12347, encoded_data)
        if new_writer:
             writer_12347 = new_writer # Обновляем глобальный writer, если он изменился
             logger.info(f"Callback отправлен в ARMA (12347): {json_data[:100]}...")
        else:
             # Если _send_message_persistent вернул None, значит отправка не удалась,
             # но он уже залоггировал ошибку. Устанавливаем writer_12347 в None.
             writer_12347 = None
             logger.error(f"Не удалось отправить callback в ARMA (12347) из-за ошибки соединения/отправки: {json_data[:100]}...")
    except Exception as e:
        logger.exception(f"Критическая ошибка в send_callback_to_arma_async: {e}")
        # При критической ошибке тоже сбрасываем writer
        if writer_12347:
             try: writer_12347.close(); await writer_12347.wait_closed()
             except Exception: pass
        writer_12347 = None

# --- Функция get_arma_data_async (без изменений) ---
async def get_arma_data_async():
    async with data_lock:
        return arma_data

# --- Функция mark_report_done (из прошлого шага, без изменений) ---
async def mark_report_done():
    try: reports_queue.task_done()
    except ValueError: logger.warning("Попытка task_done() для очереди репортов не к месту.")
    except Exception as e: logger.exception("Ошибка task_done() для очереди репортов.")


# --- Функция start_server (без изменений) ---
async def start_server(host: str = '127.0.0.1', port: int = 12346):
    server = await asyncio.start_server(handle_arma_connection, host, port)
    addr = server.sockets[0].getsockname()
    logger.info(f"Async ARMA сервер запущен и слушает на {addr}")
    await initialize_connections(host) # Ждем первого успешного подключения к 12347
    async with server:
        await server.serve_forever()

# --- Тестовый блок (если нужен) ---
if __name__ == '__main__':
    pass

# --- КОНЕЦ ФАЙЛА arma_connector_async.py (с бесконечным переподключением) ---