import socket
import json
import threading
import logging

logger = logging.getLogger("ArmaConnector")
logger.setLevel(logging.DEBUG)
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
        try:
            client, addr = server.accept()
            logger.debug(f"Подключение от {addr}")
            received = bytearray()  # Используем bytearray для накопления байтов
            
            while True:
                chunk = client.recv(8192)  # Увеличиваем буфер до 8192
                if not chunk:
                    break
                received.extend(chunk)
                # Проверяем, закончился ли JSON (баланс фигурных скобок)
                try:
                    decoded = received.decode('utf-8')
                    if decoded.count('{') == decoded.count('}'):
                        break
                except UnicodeDecodeError:
                    continue  # Ждём следующую порцию данных, если декодирование не удалось
            
            logger.debug(f"Получены данные: {len(received)} байт")
            if received:
                try:
                    parsed_data = json.loads(received.decode('utf-8'))
                    with lock:
                        data = parsed_data
                        logger.info("Данные от ARMA приняты успешно")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON: {e}")
                except UnicodeDecodeError as e:
                    logger.error(f"Ошибка декодирования UTF-8: {e}")
            client.close()
        except Exception as e:
            logger.error(f"Ошибка в run_server: {e}")
            # Продолжаем работу, не завершая поток

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
        time.sleep(1)  # Держим основной поток активным для теста