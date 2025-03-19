import socket
import json
import threading
import logging
import asyncio
from queue import Queue

logger = logging.getLogger("ArmaConnector")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

data = None
lock = threading.Lock()
reports_queue = Queue()

# Внешняя ссылка на llm_client и system_prompt_sent из server.py
from server import llm_client, system_prompt_sent

async def send_system_prompt_async():
    """Асинхронная отправка системного промпта."""
    global system_prompt_sent
    if llm_client and "arma_session" in llm_client.chat_sessions and not system_prompt_sent:
        try:
            await llm_client.send_system_prompt("arma_session")
            system_prompt_sent = True
        except Exception as e:
            logger.error(f"Ошибка при асинхронной отправке системного промпта: {e}")

def run_server():
    global data
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 12346))
    server.listen(1)
    logger.info("ARMA server запущен на порту 12346")
    
    while True:
        try:
            client, addr = server.accept()
            logger.debug(f"Подключение от {addr}")
            received = bytearray()
            
            while True:
                chunk = client.recv(8192)
                if not chunk:
                    break
                received.extend(chunk)
                try:
                    decoded = received.decode('utf-8')
                    if decoded.count('{') == decoded.count('}'):
                        break
                except UnicodeDecodeError:
                    continue
            
            logger.debug(f"Получены данные: {len(received)} байт")
            if received:
                try:
                    decoded_data = received.decode('utf-8')
                    if decoded_data == "[start_mission]":
                        with lock:
                            data = None  # Сбрасываем данные миссии
                        reports_queue.put({"command": "start_mission"})
                        logger.info("Получена команда start_mission от ARMA, данные миссии сброшены")
                        # Отправляем системный промпт асинхронно через цикл событий Flask
                        loop = asyncio.get_event_loop()
                        loop.create_task(send_system_prompt_async())
                    else:
                        parsed_data = json.loads(decoded_data)
                        if isinstance(parsed_data, dict) and "sides" in parsed_data:
                            with lock:
                                data = parsed_data
                                logger.info("Данные от ARMA (update_data) приняты успешно")
                        elif isinstance(parsed_data, list):
                            for report in parsed_data:
                                if isinstance(report, list):
                                    report_dict = dict(report)
                                    reports_queue.put(report_dict)
                                    logger.info(f"Репорт от ARMA принят: {report_dict}")
                                else:
                                    logger.error(f"Неверный формат репорта в массиве: {report}")
                        else:
                            logger.error("Неизвестный формат данных")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON: {e}")
                except UnicodeDecodeError as e:
                    logger.error(f"Ошибка декодирования UTF-8: {e}")
            client.close()
        except Exception as e:
            logger.error(f"Ошибка в run_server: {e}")

def send_to_arma(message):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 12345))
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        client.send(json_data.encode('utf-8'))
        client.close()
        logger.debug(f"Отправлено в ARMA: {json_data}")
    except Exception as e:
        logger.error(f"Ошибка отправки в ARMA: {e}")

def send_callback_to_arma(message):
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 12347))
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        client.send(json_data.encode('utf-8'))
        client.close()
        logger.debug(f"Callback отправлен в ARMA: {json_data}")
    except Exception as e:
        logger.error(f"Ошибка отправки callback в ARMA: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    while True:
        time.sleep(1)