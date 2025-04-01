# --- START OF FILE arma_connector_async.py (с бесконечным переподключением и обработкой маркеров) ---

import asyncio
import json
import logging
import time
from asyncio import StreamReader, StreamWriter, Lock, Queue

# --- Настройка логгера (из server.py) ---
# Логгер настраивается в server.py, здесь просто получаем его
logger = logging.getLogger("ArmaConnectorAsync")
# Уровень будет установлен в server.py
# ---

# --- Глобальное состояние и примитивы asyncio ---
arma_data = None
data_lock = Lock()
reports_queue = Queue()
writer_12347: StreamWriter | None = None
# ---

# --- Функция handle_arma_connection (с обработкой маркеров) ---
async def handle_arma_connection(reader: StreamReader, writer: StreamWriter):
    """Обрабатывает одно входящее подключение от Arma (порт 12346)."""
    global arma_data
    peername = writer.get_extra_info('peername')
    logger.debug(f"Подключение от Arma {peername} (12346)")
    received = bytearray()
    try:
        # Цикл чтения данных
        while True:
            chunk = await reader.read(8192)
            if not chunk:
                logger.debug(f"Соединение {peername} закрыто Arma.")
                break
            received.extend(chunk)
            try:
                # Проверяем, похожи ли данные на валидный JSON
                decoded_check = received.decode('utf-8')
                if '{' in decoded_check and decoded_check.count('{') == decoded_check.count('}'):
                   logger.debug(f"Получен полный JSON от {peername} ({len(received)} байт), обрабатываем...")
                   break
            except UnicodeDecodeError:
                # Неполный UTF-8 символ, читаем дальше
                continue

        # Обработка полученных данных
        if received:
            try:
                decoded_data = received.decode('utf-8')
                parsed_data = json.loads(decoded_data) # Сразу парсим JSON

                # Логика обработки разных типов сообщений
                if isinstance(parsed_data, dict) and parsed_data.get("command") == "start_mission":
                    # Новое сообщение о старте миссии с маркерами
                    mission_markers = parsed_data.get("markers", [])
                    async with data_lock:
                        arma_data = None # Сбрасываем данные
                    await reports_queue.put({"command": "start_mission", "markers": mission_markers})
                    logger.info(f"Получена команда start_mission от ARMA с {len(mission_markers)} маркерами.")

                elif isinstance(parsed_data, dict) and "sides" in parsed_data:
                    # Данные update_data
                    async with data_lock:
                        arma_data = parsed_data
                    logger.info("Данные от ARMA (update_data) приняты.")

                elif isinstance(parsed_data, list):
                     # Массив репортов от detectEvents
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
                            logger.error(f"Неверный формат репорта в массиве: {report}")
                    if report_count > 0:
                        logger.info(f"Принято {report_count} репортов от ARMA.")

                else:
                    logger.error(f"Неизвестный формат корневого JSON от Arma: {type(parsed_data)}")

            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON от {peername}: {e}. Данные: {received.decode('utf-8', errors='ignore')}")
            except UnicodeDecodeError as e:
                logger.error(f"Ошибка декодирования UTF-8 от {peername}: {e}")
            except Exception as e:
                 logger.exception(f"Непредвиденная ошибка при обработке данных от {peername}: {e}")

    # Обработка ошибок соединения
    except asyncio.IncompleteReadError:
        logger.warning(f"Соединение {peername} закрыто до получения полного сообщения.")
    except ConnectionResetError:
         logger.warning(f"Соединение {peername} было сброшено.")
    except Exception as e:
        logger.exception(f"Ошибка в handle_arma_connection для {peername}: {e}")
    finally:
        # Закрытие соединения
        logger.debug(f"Закрытие соединения с {peername}")
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e_close:
             logger.error(f"Ошибка при закрытии соединения с {peername}: {e_close}")

# --- Функция установки соединения (с бесконечными попытками) ---
async def connect_to_arma(host: str, port: int, initial_delay: int = 3) -> StreamWriter:
    """Бесконечно пытается установить постоянное соединение с Arma для отправки."""
    logger.info(f"Попытка установить постоянное соединение с Arma на {host}:{port} (бесконечные попытки)...")
    attempt = 0
    delay = initial_delay
    while True: # Бесконечный цикл попыток
        attempt += 1
        try:
            # Таймаут на подключение
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
        # Пауза перед следующей попыткой
        await asyncio.sleep(delay)
        # delay = min(delay + 1, 30) # Можно раскомментировать для увеличения задержки

# --- Инициализация исходящего соединения (порт 12347) ---
async def initialize_connections(host: str = '127.0.0.1'):
    """Инициализирует постоянное исходящее соединение на порт 12347."""
    global writer_12347
    logger.info("Инициализация исходящего соединения Arma (порт 12347)...")
    writer_12347 = await connect_to_arma(host, 12347) # Ждем успешного подключения
    logger.info("Исходящее соединение на порт 12347 инициализировано.")

# --- Отправка сообщения с переподключением ---
async def _send_message_persistent(writer: StreamWriter | None, host: str, port: int, message_data: bytes) -> StreamWriter | None:
    """Отправляет через постоянное соединение с бесконечным переподключением."""
    current_writer = writer
    if current_writer is None or current_writer.is_closing():
        logger.warning(f"Соединение на {host}:{port} отсутствует/закрывается. Переподключение...")
        current_writer = await connect_to_arma(host, port) # Пытаемся бесконечно
        logger.info(f"Переподключение к {host}:{port} успешно.")
    try:
        logger.debug(f"Отправка {len(message_data)} байт на {host}:{port}...")
        current_writer.write(message_data)
        await current_writer.drain()
        logger.debug(f"Данные успешно отправлены на {host}:{port}.")
        return current_writer # Возвращаем активный writer
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        logger.error(f"Ошибка соединения при отправке на {host}:{port}: {e}. Соединение будет восстановлено при следующей попытке.")
        try: current_writer.close(); await current_writer.wait_closed()
        except Exception: pass
        return None # Сигнализируем о необходимости переподключения
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при отправке на {host}:{port}: {e}")
        try: current_writer.close(); await current_writer.wait_closed()
        except Exception: pass
        return None # Сигнализируем о необходимости переподключения

# --- Отправка callback (порт 12347) ---
async def send_callback_to_arma_async(message: dict | str, host: str = '127.0.0.1'):
    """Асинхронно отправляет callback в Arma на порт 12347."""
    global writer_12347
    try:
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        encoded_data = json_data.encode('utf-8')
        new_writer = await _send_message_persistent(writer_12347, host, 12347, encoded_data)
        if new_writer:
             writer_12347 = new_writer # Обновляем глобальный writer
             logger.info(f"Callback отправлен в ARMA (12347): {json_data[:100]}...")
        else:
             writer_12347 = None # Сбрасываем writer при ошибке отправки
             logger.error(f"Не удалось отправить callback в ARMA (12347) из-за ошибки: {json_data[:100]}...")
    except Exception as e:
        logger.exception(f"Критическая ошибка в send_callback_to_arma_async: {e}")
        if writer_12347:
             try: writer_12347.close(); await writer_12347.wait_closed()
             except Exception: pass
        writer_12347 = None

# --- Получение данных Arma (для server.py) ---
async def get_arma_data_async():
    """Асинхронно и безопасно возвращает текущие данные arma_data."""
    async with data_lock:
        return arma_data

# --- Отметка об обработке репорта (для server.py) ---
async def mark_report_done():
    """Сообщает асинхронной очереди, что элемент обработан."""
    try:
        reports_queue.task_done()
    except ValueError:
        # Может возникнуть, если вызвать task_done() больше раз, чем было put()
        logger.warning("Попытка вызвать task_done() для очереди репортов, когда не ожидалось.")
    except Exception as e:
        logger.exception("Неизвестная ошибка при вызове task_done() для очереди репортов.")


# --- Запуск сервера (порт 12346) ---
async def start_server(host: str = '127.0.0.1', port: int = 12346):
    """Запускает сервер asyncio для прослушивания порта 12346 и инициализирует исходящие соединения."""
    server = await asyncio.start_server(handle_arma_connection, host, port)
    addr = server.sockets[0].getsockname()
    logger.info(f"Async ARMA сервер запущен и слушает на {addr}")
    # Инициализация исходящего соединения теперь будет ждать успеха
    await initialize_connections(host)
    async with server:
        await server.serve_forever()

# --- Тестовый блок ---
if __name__ == '__main__':
    print("Этот файл предназначен для импорта, а не для прямого запуска.")
    # Можно добавить код для простого теста, если нужно

# --- КОНЕЦ ФАЙЛА arma_connector_async.py ---