import socket
import json
import threading
import logging

logger = logging.getLogger("ArmaConnector")
logger.setLevel(logging.DEBUG)  # Оставляем DEBUG для отладки
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

data = None
lock = threading.Lock()

def run_server():
    global data
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 12346))
    server.listen(1)
    logger.info("ARMA server запущен на порту 12346")
    while True:
        client, addr = server.accept()
        logger.debug(f"Подключение от {addr}")
        received = ""
        while True:
            chunk = client.recv(2048).decode('utf-8')
            if not chunk:
                break
            received += chunk
            if received.count('{') == received.count('}'):
                break
        logger.debug(f"Получены данные: {received}")
        if received and received.strip():
            try:
                parsed_data = json.loads(received)
                with lock:
                    data = parsed_data
                    logger.info("Данные от ARMA приняты успешно")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {e}")
        client.close()

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