import json
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List

try:
    import google.generativeai as genai
except ImportError:
    genai = None

logger = logging.getLogger("llm_client")
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    "llm_client.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

class LLMClient:
    def __init__(self, config_file: str = "config.json", system_prompt_file: str = "system_prompt.txt"):
        self.config_file = config_file
        self.system_prompt_file = system_prompt_file
        self.config = self._load_config()
        self.gemini_api_key = self.config.get("geminy_api_key", "")
        self.model_name = self.config.get("model", "gemini-exp-1206")  # Загружаем последнюю модель из конфига
        self.system_prompt = self._load_system_prompt()

        if not genai:
            self.model = None
            logger.warning("Библиотека google.generativeai не найдена. LLMClient будет нерабочим.")
            return

        genai.configure(api_key=self.gemini_api_key)
        self._check_model_availability()
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"Инициализирована модель {self.model_name}")
        self.chat_sessions: Dict[str, genai.ChatSession] = {}

    def _load_config(self) -> Dict:
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения {self.config_file}: {e}")
            return {}

    def _save_config(self):
        """Сохраняет текущую конфигурацию в config.json."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logger.info(f"Конфигурация сохранена в {self.config_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")

    def _load_system_prompt(self) -> str:
        try:
            with open(self.system_prompt_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if not text:
                    raise ValueError("system_prompt.txt пустой")
                return text
        except Exception as e:
            logger.error(f"Ошибка чтения системного промта: {e}")
            return "Ты командир в Arma 3. Анализируй данные миссии и отдавай команды в формате JSON."

    def _check_model_availability(self):
        try:
            available_models = self.get_available_models()
            if self.model_name not in available_models:
                logger.warning(f"Модель {self.model_name} не найдена в списке доступных: {available_models}")
            else:
                logger.info(f"Модель {self.model_name} доступна")
        except Exception as e:
            logger.error(f"Ошибка проверки доступных моделей: {e}")

    def get_available_models(self) -> List[str]:
        if not genai:
            return []
        try:
            return [m.name.split('/')[-1] for m in genai.list_models()]
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []

    async def _retry_send_message(self, chat_session, content, max_retries=3) -> Optional[str]:
        delays = [1, 3, 10]
        last_exception = None

        for attempt, delay in enumerate(delays, 1):
            try:
                logger.info(f"LLM отправка (попытка {attempt}): {content}")
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    content
                    # Убираем generation_config, чтобы получить текст
                )
                logger.info(f"LLM ответ: {response.text}")
                return response.text
            except Exception as e:
                if "503" in str(e) and attempt < max_retries:
                    logger.warning(f"Ошибка 503, ждём {delay} сек: {e}")
                    await asyncio.sleep(delay)
                    last_exception = e
                else:
                    raise e
        
        if last_exception:
            raise last_exception
        raise RuntimeError("LLM: Неизвестная ошибка при отправке")

    def create_session(self, session_id: str) -> bool:
        if not self.model:
            logger.error("LLMClient: Модель не инициализирована")
            return False
        
        if session_id in self.chat_sessions:
            logger.warning(f"Сессия {session_id} уже существует.")
            return True

        try:
            logger.info(f"Создание chat_session для {session_id}")
            chat_session = self.model.start_chat(history=[])
            self.chat_sessions[session_id] = chat_session
            logger.info(f"Сессия {session_id} создана")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return False

    async def send_system_prompt(self, session_id: str) -> bool:
        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена для отправки системного промпта.")
            return False
        try:
            await self._retry_send_message(chat_session, self.system_prompt)
            logger.info(f"Системный промпт отправлен для сессии {session_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки системного промпта: {e}")
            return False

    async def send_message(self, session_id: str, json_input: dict, png_path: Optional[str] = None) -> Optional[dict]:
        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена.")
            return None

        try:
            json_str = json.dumps({"role": "user", "parts": [json_input]}, ensure_ascii=False)
            content = [json_str]
            
            if png_path and os.path.exists(png_path):
                with open(png_path, "rb") as f:
                    png_data = f.read()
                content.append(genai.types.Part.from_data(data=png_data, mime_type="image/png"))
                logger.info(f"Добавлено изображение из {png_path}")

            answer = await self._retry_send_message(chat_session, content)
            # Возвращаем текст как есть, без парсинга в JSON
            return {"response": answer} if answer else None
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return None

    def set_model(self, model_name: str) -> bool:
        if not genai:
            logger.error("LLMClient: Библиотека genai не доступна")
            return False
        try:
            self.model_name = model_name
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Модель изменена на {model_name}")
            # Обновляем существующие сессии без пересоздания
            for session_id, chat_session in self.chat_sessions.items():
                # Создаем новую сессию с той же историей
                new_session = self.model.start_chat(history=chat_session.history)
                self.chat_sessions[session_id] = new_session
                logger.info(f"Сессия {session_id} обновлена с моделью {model_name}")
            # Сохраняем модель в конфиг
            self.config["model"] = model_name
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"Ошибка смены модели: {e}")
            return False