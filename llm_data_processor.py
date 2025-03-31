import asyncio
import json
import logging
from llm_client import LLMClient

logger = logging.getLogger("LLM_data_processor")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class LLMDataProcessor:
    def __init__(self, config_file="config.json", default_interval=60):
        self.llm_client = LLMClient(config_file)
        self.llm_client.start_session("arma_session")
        self.side = "OPFOR"  # Сторона по умолчанию
        self.interval = default_interval  # Интервал по умолчанию (в секундах)
        self.running = False
        self.last_data = None  # Кэш последних данных

    def filter_and_reduce_data(self, data):
        """Фильтрует и сокращает данные для указанной стороны."""
        if not data or "sides" not in data:
            logger.error("Неверный формат данных из /arma_data")
            return None

        filtered_data = {"sides": {}}
        if self.side in data["sides"]:
            filtered_sides = {}
            for group_data in data["sides"][self.side]:
                # Сокращаем данные о юнитах
                reduced_units = [
                    {"t": unit["t"], "pw": unit["pw"], "sw": unit["sw"]}
                    for unit in group_data["u"]
                ]
                # Копируем группу, заменяя юниты
                reduced_group = group_data.copy()
                reduced_group["u"] = reduced_units
                filtered_sides.setdefault(self.side, []).append(reduced_group)
            filtered_data["sides"] = filtered_sides
        else:
            logger.warning(f"Сторона {self.side} не найдена в данных")

        return filtered_data

    async def fetch_arma_data(self, app):
        """Получает данные из /arma_data."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: app.test_client().get('/arma_data').get_json()
            )
            if response["status"] == "success":
                return response["data"]
            else:
                logger.error("Не удалось получить данные из /arma_data")
                return None
        except Exception as e:
            logger.error(f"Ошибка получения данных из /arma_data: {e}")
            return None

    async def fetch_mission_settings(self, app):
        """Получает настройки миссии из /get_mission_settings."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: app.test_client().get('/get_mission_settings').get_json()
            )
            if response["status"] == "success":
                self.side = response["settings"].get("llmSide", self.side)
                self.interval = response["settings"].get("llmUpdateInterval", self.interval)
                logger.info(f"Обновлены настройки: side={self.side}, interval={self.interval}")
            else:
                logger.warning("Не удалось получить настройки миссии, используются значения по умолчанию")
        except Exception as e:
            logger.error(f"Ошибка получения настроек миссии: {e}")

    async def process_data_loop(self, app):
        """Основной цикл обработки данных и отправки в LLM."""
        self.running = True
        while self.running:
            try:
                # Получаем настройки миссии
                await self.fetch_mission_settings(app)

                # Получаем данные из /arma_data
                arma_data = await self.fetch_arma_data(app)
                if arma_data:
                    # Фильтруем и сокращаем данные
                    reduced_data = self.filter_and_reduce_data(arma_data)
                    if reduced_data and reduced_data != self.last_data:
                        # Отправляем данные в LLM
                        json_input = {"command": "update_data", "side": self.side, "arma_data": reduced_data}
                        response = await self.llm_client.send_message("arma_session", json_input)
                        if response:
                            logger.info(f"Данные отправлены в LLM: {json.dumps(json_input, ensure_ascii=False)}")
                            logger.info(f"Ответ от LLM: {response}")
                        else:
                            logger.warning("Пустой ответ от LLM")
                        self.last_data = reduced_data  # Кэшируем данные для сравнения
                    else:
                        logger.debug("Данные не изменились или пусты, пропускаем отправку")

                # Ждём следующий интервал
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Ошибка в цикле обработки данных: {e}")
                await asyncio.sleep(5)  # Пауза перед повторной попыткой

    def start(self, app):
        """Запускает цикл обработки данных в фоне."""
        if not self.running:
            asyncio.create_task(self.process_data_loop(app))
            logger.info("Запущен процесс обработки данных для LLM")

    def stop(self):
        """Останавливает цикл обработки данных."""
        self.running = False
        logger.info("Процесс обработки данных для LLM остановлен")

# Для тестирования отдельно
if __name__ == "__main__":
    from flask import Flask
    app = Flask(__name__)
    processor = LLMDataProcessor(default_interval=10)  # Фиксированный интервал 10 секунд для теста
    processor.start(app)
    asyncio.run(asyncio.sleep(60))  # Тестовый запуск на 60 секунд
    processor.stop()