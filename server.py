import os
import logging
from flask import Flask, send_from_directory, abort, request

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TileServer")

# Папка с тайлами
TILES_FOLDER = "maps/chernarus/"
CACHE_TIMEOUT = 86400  # Время кеширования в секундах (24 часа)

@app.before_request
def log_request_info():
    logger.debug(f"Запрос: {request.method} {request.url} от {request.remote_addr}")

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def get_tile(z, x, y):
    logger.info(f"Запрос тайла: z={z}, x={x}, y={y}")
    tile_dir = os.path.join(TILES_FOLDER, str(z), str(x))
    tile_filename = f"{y}.png"
    tile_path = os.path.join(tile_dir, tile_filename)
    if os.path.exists(tile_path):
        logger.debug(f"Отправка файла: {tile_path}")
        response = send_from_directory(tile_dir, tile_filename)
        # Устанавливаем заголовок кеширования: 24 часа
        response.cache_control.max_age = CACHE_TIMEOUT
        response.cache_control.public = True
        return response
    else:
        logger.error(f"Тайл не найден: {tile_path}")
        abort(404)

if __name__ == "__main__":
    logger.info("Запуск сервера TileServer на http://localhost:5000")
    app.run(debug=True, port=5000)
