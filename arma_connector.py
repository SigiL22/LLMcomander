import socket
import json
import threading
import logging

# Настройка логирования
logger = logging.getLogger("ArmaConnector")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Глобальные переменные модуля
data = None  # Переименуем для ясности, чтобы отличать от локальных переменных
lock = threading.Lock()

def run_server():
    """Запускает TCP-сервер для получения данных от ARMA 3 на порту 12346."""
    global data
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 12346))
    server.listen(1)
    logger.info("ARMA server listening on port 12346...")

    while True:
        try:
            client, addr = server.accept()
            received = client.recv(1024).decode('utf-8')
            if received:
                with lock:
                    try:
                        data = json.loads(received) if received.startswith('{') else received
                        logger.info(f"Received from ARMA: {data}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON from ARMA: {received}")
                        data = received
            client.close()
        except Exception as e:
            logger.error(f"Error in ARMA server: {e}")

def send_to_arma(message):
    """Отправляет данные в ARMA 3 на порт 12345."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 12345))
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        client.send(json_data.encode('utf-8'))
        client.close()
        logger.info(f"Sent to ARMA: {json_data}")
    except Exception as e:
        logger.error(f"Error sending to ARMA: {e}")

def send_callback_to_arma(message):
    """Отправляет данные для обратного вызова в ARMA на порт 12347."""
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 12347))
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        client.send(json_data.encode('utf-8'))
        client.close()
        logger.info(f"Sent callback to ARMA: {json_data}")
    except Exception as e:
        logger.error(f"Error sending callback to ARMA: {e}")