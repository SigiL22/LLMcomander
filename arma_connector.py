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

# Глобальная переменная для хранения данных от ARMA
arma_data = None
data_lock = threading.Lock()

def run_server():
    """Запускает TCP-сервер для получения данных от ARMA 3 на порту 12346."""
    global arma_data
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Разрешаем повторное использование порта
    server.bind(('127.0.0.1', 12346))
    server.listen(1)
    logger.info("ARMA server listening on port 12346...")

    while True:
        try:
            client, addr = server.accept()
            data = client.recv(1024).decode('utf-8')
            if data:
                with data_lock:
                    try:
                        arma_data = json.loads(data) if data.startswith('{') else data
                        logger.info(f"Received from ARMA: {arma_data}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON from ARMA: {data}")
                        arma_data = data
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
    """
    Отправляет данные для обратного вызова в ARMA на порт 12347.
    Это используется DLL для асинхронного уведомления игры.
    """
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 12347))
        json_data = json.dumps(message) if isinstance(message, dict) else str(message)
        client.send(json_data.encode('utf-8'))
        client.close()
        logger.info(f"Sent callback to ARMA: {json_data}")
    except Exception as e:
        logger.error(f"Error sending callback to ARMA: {e}")

# Запуск сервера для приема данных от ARMA в отдельном потоке
threading.Thread(target=run_server, daemon=True).start()

if __name__ == "__main__":
    # Тестовые вызовы
    send_to_arma({"command": "test", "data": "Hello from Python"})
    send_callback_to_arma({"command": "serverUpdate", "data": {"info": "Update from server"}})
