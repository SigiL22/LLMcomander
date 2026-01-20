# --- START OF FILE llm_client.py ---

import json
import logging
import asyncio
import os
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List

# Загружаем переменные из .env (если файл существует)
load_dotenv()

# Попытка импорта библиотеки Google
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
except ImportError:
    genai = None
    GenerationConfig = None

# --- Настройка логгера ---
logger = logging.getLogger("llm_client")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    log_dir = os.path.dirname("llm_client.log")
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = RotatingFileHandler("llm_client.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
# --- Конец настройки логгера ---

class LLMClient:
    def __init__(self, config_file: str = "config.json", system_prompt_file: str = "system_prompt.txt"):
        self.config_file = config_file
        self.system_prompt_file = system_prompt_file
        self.is_operational = False
        self.model: Optional[genai.GenerativeModel] = None
        self.chat_sessions: Dict[str, genai.ChatSession] = {}
        self.model_name: Optional[str] = None
        self.system_prompt: Optional[str] = None
        self.config: Dict = {}

        logger.info("Инициализация LLMClient...")

        if not genai:
            logger.error("Библиотека google.generativeai не найдена. LLMClient будет нерабочим.")
            return

        # 1. Загружаем JSON конфиг
        self.config = self._load_config()

        # --- ЛОГИКА ДЛЯ API КЛЮЧА (ПРИОРИТЕТ .ENV) ---
        # Сначала ищем в переменных окружения (безопасность)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        # Если нет, ищем в конфиге (совместимость)
        if not self.gemini_api_key:
            self.gemini_api_key = self.config.get("geminy_api_key")

        if not self.gemini_api_key or self.gemini_api_key == "INSERT_YOUR_KEY_HERE":
            logger.error(f"API ключ не найден! Проверьте файл .env (GEMINI_API_KEY).")
            return

        # --- ЛОГИКА ДЛЯ МОДЕЛИ (ПРИОРИТЕТ CONFIG.JSON) ---
        # Сначала ищем в конфиге (чтобы сохранить выбор пользователя из UI)
        self.model_name = self.config.get("model")
        
        # Если в конфиге пусто, берем дефолт из .env или хардкод
        if not self.model_name:
            self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")

        if not self.model_name:
            logger.error(f"Имя модели не найдено.")
            return

        self.system_prompt = self._load_system_prompt()
        if not self.system_prompt:
            logger.error("Не удалось загрузить системный промпт. LLMClient не будет инициализирован.")
            return

        try:
            logger.info("Конфигурация Google API...")
            genai.configure(api_key=self.gemini_api_key)

            logger.info("Проверка доступности API и моделей...")
            available_models = self.get_available_models()
            
            if not available_models:
                logger.warning("Не удалось получить список моделей. Пробуем инициализировать модель вслепую...")
            else:
                self._check_model_availability(available_models)

            logger.info(f"Попытка инициализации модели: {self.model_name}")
            generation_config = GenerationConfig(candidate_count=1)
            self.model = genai.GenerativeModel(self.model_name, generation_config=generation_config)
            logger.info(f"Объект модели {self.model_name} создан.")

            self.is_operational = True
            logger.info("LLMClient успешно инициализирован и готов к работе.")

        except Exception as e:
            logger.exception(f"Критическая ошибка инициализации LLMClient: {e}")

    def _load_config(self) -> Dict:
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл конфигурации {self.config_file} не найден.")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON в {self.config_file}: {e}")
            return {}
        except Exception as e:
            logger.exception(f"Неизвестная ошибка чтения {self.config_file}: {e}")
            return {}

    def _save_config(self):
        if not self.config_file:
            return
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            logger.info(f"Конфигурация сохранена в {self.config_file}")
        except Exception as e:
            logger.exception(f"Ошибка сохранения конфигурации: {e}")

    def _load_system_prompt(self) -> Optional[str]:
        try:
            with open(self.system_prompt_file, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if not text:
                    logger.warning(f"Файл системного промпта {self.system_prompt_file} пустой.")
                    return "Ты командир в Arma 3. Анализируй данные миссии и отдавай команды в формате JSON."
                logger.info(f"Системный промпт загружен из {self.system_prompt_file}.")
                return text
        except FileNotFoundError:
            logger.error(f"Файл системного промпта {self.system_prompt_file} не найден.")
            return None
        except Exception as e:
            logger.exception(f"Ошибка чтения системного промпта: {e}")
            return None

    def get_available_models(self) -> List[str]:
        if not genai:
            return []
        try:
            models_list = [
                m.name.split('/')[-1]
                for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]
            if not models_list:
                logger.warning("API вернуло пустой список моделей, поддерживающих generateContent.")
            else:
                logger.info(f"Доступные модели (generateContent): {models_list}")
            return models_list
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []

    def _check_model_availability(self, available_models: List[str]):
        if not self.model_name:
            logger.error("Имя модели не установлено для проверки доступности.")
            return
        if not available_models:
            logger.warning("Список доступных моделей пуст (возможно, из-за ошибки API). Проверка невозможна.")
        elif self.model_name not in available_models:
            logger.warning(f"Выбранная модель '{self.model_name}' не найдена в списке доступных: {available_models}")
        else:
            logger.info(f"Выбранная модель '{self.model_name}' доступна.")

    async def _retry_send_message(self, chat_session, content, max_retries=3) -> Optional[str]:
        delays = [2, 5, 10]
        last_exception = None

        for attempt in range(max_retries):
            try:
                delay = delays[attempt]
                logger.debug(f"LLM отправка (попытка {attempt + 1}/{max_retries})...")
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    content
                )
                if response and hasattr(response, 'text'):
                    logger.debug(f"LLM ответ получен (попытка {attempt + 1}).")
                    return response.text
                else:
                    logger.warning(f"LLM вернул пустой или некорректный ответ (попытка {attempt + 1}): {response}")
                    last_exception = ValueError("LLM returned an empty or invalid response.")
                    if attempt < max_retries - 1:
                        logger.info(f"Пауза {delay} сек перед следующей попыткой...")
                        await asyncio.sleep(delay)
                    continue
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                if "400 user location is not supported" in error_str:
                    logger.error(f"Ошибка геолокации API Gemini: {e}. Отправка невозможна из этого региона.")
                    raise e
                elif "503" in error_str or "429" in error_str or "500" in error_str:
                    if attempt < max_retries - 1:
                        logger.warning(f"Ошибка API ({type(e).__name__}), попытка {attempt + 1}/{max_retries}. Пауза {delay} сек: {e}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Превышено количество попыток ({max_retries}) после ошибки API: {e}")
                        raise e
                else:
                    logger.exception(f"Неизвестная ошибка при отправке в LLM (попытка {attempt + 1}): {e}")
                    raise e

        logger.error("Не удалось отправить сообщение в LLM после всех попыток.")
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("LLM: Неизвестная ошибка при отправке после всех ретраев.")
        return None

    def create_session(self, session_id: str) -> bool:
        if not self.is_operational or not self.model:
            logger.error("LLMClient не готов к работе, сессия не может быть создана.")
            return False

        if session_id in self.chat_sessions:
            # Логируем, что сессия будет пересоздана
            logger.warning(f"Сессия {session_id} уже существует. Пересоздание для сброса истории...")

        try:
            logger.info(f"Создание/пересоздание chat_session для {session_id}")
            # При каждом вызове создается новая сессия с пустой историей
            chat_session = self.model.start_chat(history=[])
            self.chat_sessions[session_id] = chat_session
            logger.info(f"Сессия {session_id} успешно создана/пересоздана.")
            return True
        except Exception as e:
            logger.exception(f"Ошибка создания сессии {session_id}: {e}")
            return False

    async def send_system_prompt(self, session_id: str) -> Optional[str]:
        if not self.is_operational:
            logger.error("LLMClient не готов к работе, системный промпт не может быть отправлен.")
            return None

        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена для отправки системного промпта.")
            return None

        if not self.system_prompt:
            logger.error("Системный промпт не загружен.")
            return None

        try:
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            # Логируем полный текст системного промпта перед отправкой
            logger.info(f"LLM Request (session: {session_id}):\n"
                        f"--- Start of System Prompt ---\n"
                        f"{self.system_prompt}\n"
                        f"--- End of System Prompt ---")
            
            response_text = await self._retry_send_message(chat_session, self.system_prompt)
            
            if response_text:
                # Логируем ответ
                logger.info(f"LLM Response (session: {session_id}): {response_text}")
                return response_text
            else:
                logger.error(f"LLM вернул пустой ответ на системный промпт для сессии {session_id}.")
                return None
        except Exception as e:
            logger.error(f"Не удалось отправить системный промпт для сессии {session_id}: {e}")
            return None

    async def send_message(self, session_id: str, user_input: str, png_path: Optional[str] = None) -> Optional[str]:
        if not self.is_operational:
            logger.error("LLMClient не готов к работе, сообщение не может быть отправлено.")
            return None

        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена для отправки сообщения.")
            return None

        if not user_input and not png_path:
            logger.warning("Попытка отправить пустое сообщение без изображения.")
            return None

        try:
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            # Формируем подробное лог-сообщение для запроса
            log_request_details = f"LLM Request (session: {session_id}):"
            
            # Пытаемся красиво отформатировать JSON, если это он
            if user_input:
                try:
                    parsed_json = json.loads(user_input)
                    pretty_json = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                    log_request_details += (f"\n--- Start of Text Payload (JSON) ---\n"
                                            f"{pretty_json}\n"
                                            f"--- End of Text Payload ---")
                except json.JSONDecodeError:
                    # Если не JSON, логируем как обычный текст
                    log_request_details += (f"\n--- Start of Text Payload (String) ---\n"
                                            f"{user_input}\n"
                                            f"--- End of Text Payload ---")
            
            # Добавляем информацию об изображении, если оно есть
            if png_path:
                if os.path.exists(png_path):
                    log_request_details += f"\n- Image Payload: {png_path} (exists)"
                else:
                    log_request_details += f"\n- Image Payload: {png_path} (NOT FOUND!)"

            # Записываем всё в лог
            logger.info(log_request_details)

            content_parts = []
            if user_input:
                content_parts.append(user_input)

            if png_path:
                if os.path.exists(png_path) and os.path.isfile(png_path):
                    try:
                        with open(png_path, "rb") as f:
                            png_data = f.read()
                        content_parts.append(genai.types.Part.from_data(data=png_data, mime_type="image/png"))
                    except Exception as img_e:
                        logger.error(f"Ошибка чтения или добавления изображения из {png_path}: {img_e}")
                else:
                    logger.warning(f"Файл изображения не найден или не является файлом: {png_path}")

            if not content_parts:
                logger.error("Нет контента (ни текста, ни изображения) для отправки.")
                return None

            answer_text = await self._retry_send_message(chat_session, content_parts)
            
            # Логируем ответ
            logger.info(f"LLM Response (session: {session_id}): {answer_text}")
            return answer_text

        except Exception as e:
            logger.error(f"Не удалось отправить сообщение для сессии {session_id}: {e}")
            return None

    def set_model(self, model_name: str) -> bool:
        if not self.is_operational:
            logger.error("LLMClient не был успешно инициализирован, смена модели невозможна.")
            return False
        if not genai:
            logger.error("Библиотека google.generativeai недоступна.")
            return False
        if self.model_name == model_name:
            logger.info(f"Модель уже установлена на {model_name}.")
            return True

        logger.info(f"Попытка смены модели на: {model_name}")
        try:
            available_models = self.get_available_models()
            if not available_models:
                logger.error("Не удалось получить список моделей для проверки перед сменой.")
                return False
            if model_name not in available_models:
                logger.error(f"Новая модель '{model_name}' не найдена в списке доступных: {available_models}")
                return False

            generation_config = GenerationConfig(candidate_count=1)
            new_model = genai.GenerativeModel(model_name, generation_config=generation_config)
            logger.info(f"Новый объект модели {model_name} создан.")

            self.model = new_model
            self.model_name = model_name

            logger.info("Обновление существующих сессий с новой моделью...")
            for session_id, old_session in list(self.chat_sessions.items()):
                try:
                    history_data = []
                    if hasattr(old_session, 'history') and isinstance(old_session.history, list):
                        history_data = old_session.history
                    else:
                        logger.warning(f"Не удалось получить историю для сессии {session_id}, сессия будет создана пустой.")
                    new_session = self.model.start_chat(history=history_data)
                    self.chat_sessions[session_id] = new_session
                    logger.info(f"Сессия {session_id} успешно обновлена с моделью {model_name}.")
                except Exception as session_e:
                    logger.error(f"Ошибка при обновлении сессии {session_id} с новой моделью: {session_e}. Сессия может быть потеряна.")
                    if session_id in self.chat_sessions:
                        del self.chat_sessions[session_id]

            self.config["model"] = model_name
            self._save_config()
            logger.info(f"Модель успешно изменена на {model_name} и сохранена в конфигурации.")
            return True

        except Exception as e:
            logger.exception(f"Ошибка смены модели на {model_name}: {e}")
            self.is_operational = False
            return False

# --- КОНЕЦ ФАЙЛА llm_client.py ---