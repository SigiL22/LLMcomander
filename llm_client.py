import json
import logging
import asyncio
import os
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List

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

    # Создаем директорию для логов, если необходимо
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
        self.is_operational = False  # Флаг работоспособности клиента
        self.model: Optional[genai.GenerativeModel] = None
        self.chat_sessions: Dict[str, genai.ChatSession] = {}
        self.model_name: Optional[str] = None
        self.system_prompt: Optional[str] = None
        self.config: Dict = {}

        logger.info("Инициализация LLMClient...")

        # --- 1. Проверка наличия библиотеки ---
        if not genai:
            logger.error("Библиотека google.generativeai не найдена. LLMClient будет нерабочим.")
            return

        # --- 2. Загрузка конфигурации и системного промпта ---
        self.config = self._load_config()
        self.gemini_api_key = self.config.get("geminy_api_key")
        if not self.gemini_api_key:
            logger.error(f"API ключ 'geminy_api_key' не найден или пуст в {self.config_file}.")
            return

        self.model_name = self.config.get("model", "gemini-1.5-flash-latest")
        if not self.model_name:
            logger.error(f"Имя модели 'model' не найдено или пусто в {self.config_file}.")
            return

        self.system_prompt = self._load_system_prompt()
        if not self.system_prompt:
            logger.error("Не удалось загрузить системный промпт. LLMClient не будет инициализирован.")
            return

        # --- 3. Конфигурация API и инициализация модели ---
        try:
            logger.info("Конфигурация Google API...")
            genai.configure(api_key=self.gemini_api_key)

            logger.info("Проверка доступности API и моделей...")
            available_models = self.get_available_models()
            if not available_models:
                raise RuntimeError("Не удалось получить список моделей от API. Проверьте ключ API и доступность API для вашего региона.")

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
        """Сохраняет текущую конфигурацию в config.json."""
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
        """Получает список доступных моделей от API."""
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
        """Проверяет доступность выбранной модели в предоставленном списке."""
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
        """Пытается отправить сообщение с ретраями при ошибках."""
        delays = [2, 5, 10]
        last_exception = None

        for attempt in range(max_retries):
            try:
                delay = delays[attempt]
                logger.info(f"LLM отправка (попытка {attempt + 1}/{max_retries})...")
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    content
                )
                if response and hasattr(response, 'text'):
                    logger.info(f"LLM ответ получен (попытка {attempt + 1}).")
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
        """Создает новую сессию чата."""
        if not self.is_operational or not self.model:
            logger.error("LLMClient не готов к работе, сессия не может быть создана.")
            return False

        if session_id in self.chat_sessions:
            logger.warning(f"Сессия {session_id} уже существует.")
            return True

        try:
            logger.info(f"Создание chat_session для {session_id}")
            chat_session = self.model.start_chat(history=[])
            self.chat_sessions[session_id] = chat_session
            logger.info(f"Сессия {session_id} успешно создана.")
            return True
        except Exception as e:
            logger.exception(f"Ошибка создания сессии {session_id}: {e}")
            return False

    async def send_system_prompt(self, session_id: str) -> bool:
        """Отправляет системный промпт в указанную сессию."""
        if not self.is_operational:
            logger.error("LLMClient не готов к работе, системный промпт не может быть отправлен.")
            return False

        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена для отправки системного промпта.")
            return False

        if not self.system_prompt:
            logger.error("Системный промпт не загружен.")
            return False

        try:
            logger.info(f"Отправка системного промпта для сессии {session_id}...")
            await self._retry_send_message(chat_session, self.system_prompt)
            logger.info(f"Системный промпт успешно отправлен для сессии {session_id}")
            return True
        except Exception as e:
            logger.error(f"Не удалось отправить системный промпт для сессии {session_id}.")
            return False

    async def send_message(self, session_id: str, user_input: str, png_path: Optional[str] = None) -> Optional[str]:
        """
        Отправляет сообщение пользователя (и опционально изображение) в сессию и возвращает ответ LLM.
        При этом запрос и ответ логируются в llm_client.log.
        """
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
            # Логирование запроса к LLM
            logger.info(f"LLM Request (session: {session_id}): текст='{user_input}', png_path='{png_path}'")
            content_parts = []
            if user_input:
                content_parts.append(user_input)
                logger.info(f"Подготовка к отправке: текст '{user_input[:50]}...'")

            if png_path:
                if os.path.exists(png_path) and os.path.isfile(png_path):
                    try:
                        with open(png_path, "rb") as f:
                            png_data = f.read()
                        content_parts.append(genai.types.Part.from_data(data=png_data, mime_type="image/png"))
                        logger.info(f"Изображение из {png_path} добавлено к сообщению.")
                    except Exception as img_e:
                        logger.error(f"Ошибка чтения или добавления изображения из {png_path}: {img_e}")
                else:
                    logger.warning(f"Файл изображения не найден или не является файлом: {png_path}")

            if not content_parts:
                logger.error("Нет контента (ни текста, ни изображения) для отправки.")
                return None

            # Отправка запроса и получение ответа от LLM
            answer_text = await self._retry_send_message(chat_session, content_parts)
            # Логирование ответа от LLM
            logger.info(f"LLM Response (session: {session_id}): {answer_text}")
            return answer_text

        except Exception as e:
            logger.error(f"Не удалось отправить сообщение для сессии {session_id}: {e}")
            return None

    def set_model(self, model_name: str) -> bool:
        """Изменяет активную модель LLM."""
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
