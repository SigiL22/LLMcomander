# --- START OF FILE llm_client.py ---

import json
import logging
import asyncio
import os # Добавлен импорт os для проверки png_path
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List

# Попытка импорта библиотеки Google
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig # Импортируем отдельно
except ImportError:
    genai = None
    GenerationConfig = None # Определяем как None, если импорт не удался

# --- Настройка логгера ---
logger = logging.getLogger("llm_client")
logger.setLevel(logging.INFO)
logger.propagate = False # Предотвращаем дублирование

if not logger.handlers:
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    # Убедитесь, что директория для логов существует или создайте ее
    log_dir = os.path.dirname("llm_client.log")
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = RotatingFileHandler(
        "llm_client.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
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
            return # Выходим, is_operational останется False

        # --- 2. Загрузка конфигурации и промпта ---
        self.config = self._load_config()
        self.gemini_api_key = self.config.get("geminy_api_key") # Опечатка в ключе? Проверьте config.json
        if not self.gemini_api_key:
             logger.error(f"API ключ 'geminy_api_key' не найден или пуст в {self.config_file}.")
             return
        self.model_name = self.config.get("model", "gemini-1.5-flash-latest") # Используем модель по умолчанию или из конфига
        if not self.model_name:
            logger.error(f"Имя модели 'model' не найдено или пусто в {self.config_file}.")
            return

        self.system_prompt = self._load_system_prompt()
        if not self.system_prompt:
             logger.error("Не удалось загрузить системный промпт. LLMClient не будет инициализирован.")
             return

        # --- 3. Конфигурация и проверка API ---
        try:
            logger.info("Конфигурация Google API...")
            genai.configure(api_key=self.gemini_api_key)

            # Пытаемся получить список моделей как индикатор доступности API
            logger.info("Проверка доступности API и моделей...")
            available_models = self.get_available_models() # Эта функция теперь логгирует ошибки

            if not available_models: # Если список пуст (из-за ошибки API/геолокации)
                 # Ошибка уже залоггирована в get_available_models
                 raise RuntimeError("Не удалось получить список моделей от API. Проверьте ключ API и доступность API для вашего региона.")

            # Проверяем наличие нашей модели в списке
            self._check_model_availability(available_models) # Передаем полученный список

            # --- 4. Инициализация модели ---
            logger.info(f"Попытка инициализации модели: {self.model_name}")
            # Указываем generation_config с candidate_count=1 для стабильности
            generation_config = GenerationConfig(candidate_count=1)
            self.model = genai.GenerativeModel(
                self.model_name,
                generation_config=generation_config # Добавляем config
            )
            logger.info(f"Объект модели {self.model_name} создан.")

            # Если все прошло успешно, устанавливаем флаг
            self.is_operational = True
            logger.info("LLMClient успешно инициализирован и готов к работе.")

        except Exception as e:
             logger.exception(f"Критическая ошибка инициализации LLMClient: {e}")
             # is_operational остается False

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
        if not self.config_file: return
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
                    # Можно вернуть дефолтный промпт или None
                    return "Ты командир в Arma 3. Анализируй данные миссии и отдавай команды в формате JSON."
                logger.info(f"Системный промпт загружен из {self.system_prompt_file}.")
                return text
        except FileNotFoundError:
             logger.error(f"Файл системного промпта {self.system_prompt_file} не найден.")
             return None
        except Exception as e:
            logger.exception(f"Ошибка чтения системного промта: {e}")
            return None

    def get_available_models(self) -> List[str]:
        """Получает список доступных моделей от API."""
        if not genai: return []
        try:
            # Добавляем явный вызов list_models здесь, чтобы поймать ошибку геолокации
            # Фильтруем модели, поддерживающие генерацию контента
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
            # Логгируем ошибку, включая геолокацию (если она в тексте ошибки)
            logger.error(f"Ошибка получения списка моделей: {e}")
            return [] # Возвращаем пустой список при ошибке

    def _check_model_availability(self, available_models: List[str]):
        """Проверяет доступность выбранной модели в предоставленном списке."""
        if not self.model_name:
            logger.error("Имя модели не установлено для проверки доступности.")
            return
        if not available_models:
             logger.warning("Список доступных моделей пуст (возможно, из-за ошибки API). Проверка невозможна.")
             # Можно поднять исключение, если модель критична
             # raise ValueError("Cannot check model availability, API returned no models.")
        elif self.model_name not in available_models:
            logger.warning(f"Выбранная модель '{self.model_name}' не найдена в списке доступных: {available_models}")
            # Можно выбрать другую модель или поднять исключение
            # raise ValueError(f"Model '{self.model_name}' not found in available models.")
        else:
            logger.info(f"Выбранная модель '{self.model_name}' доступна.")

    async def _retry_send_message(self, chat_session, content, max_retries=3) -> Optional[str]:
        """Пытается отправить сообщение с ретраями при определенных ошибках."""
        # Увеличиваем базовую задержку и добавляем вариативность
        delays = [2, 5, 10] # Задержки в секундах
        last_exception = None

        for attempt in range(max_retries):
            try:
                delay = delays[attempt]
                logger.info(f"LLM отправка (попытка {attempt + 1}/{max_retries})...")
                # Используем asyncio.to_thread для запуска блокирующей функции send_message
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    content
                )
                # Проверяем наличие текста в ответе
                if response and hasattr(response, 'text'):
                    logger.info(f"LLM ответ получен (попытка {attempt + 1}).")
                    # logger.debug(f"LLM ответ: {response.text}") # Логгируем только если DEBUG
                    return response.text
                else:
                    logger.warning(f"LLM вернул пустой или некорректный ответ (попытка {attempt + 1}): {response}")
                    # Можно считать это ошибкой и перейти к следующей попытке или вернуть None
                    last_exception = ValueError("LLM returned an empty or invalid response.")
                    if attempt < max_retries - 1:
                        logger.info(f"Пауза {delay} сек перед следующей попыткой...")
                        await asyncio.sleep(delay)
                    continue # Переходим к следующей попытке

            except Exception as e:
                last_exception = e
                # Обрабатываем специфичные ошибки API (коды могут отличаться)
                # 503 Service Unavailable, 429 Too Many Requests, 500 Internal Server Error
                # Ошибку геолокации (400) обрабатывать ретраями бессмысленно
                error_str = str(e).lower()
                if "400 user location is not supported" in error_str:
                    logger.error(f"Ошибка геолокации API Gemini: {e}. Отправка невозможна из этого региона.")
                    raise e # Прерываем ретраи, ошибка фатальна для этого региона
                elif "503" in error_str or "429" in error_str or "500" in error_str:
                    if attempt < max_retries - 1:
                        logger.warning(f"Ошибка API ({type(e).__name__}), попытка {attempt + 1}/{max_retries}. Пауза {delay} сек: {e}")
                        await asyncio.sleep(delay)
                        continue # Переходим к следующей попытке
                    else:
                        logger.error(f"Превышено количество попыток ({max_retries}) после ошибки API: {e}")
                        raise e # Поднимаем ошибку после последней попытки
                else:
                    # Неизвестная ошибка, прерываем ретраи
                    logger.exception(f"Неизвестная ошибка при отправке в LLM (попытка {attempt + 1}): {e}")
                    raise e

        # Если все попытки не удались
        logger.error("Не удалось отправить сообщение в LLM после всех попыток.")
        if last_exception:
            raise last_exception # Поднимаем последнюю пойманную ошибку
        else:
            # Этого не должно произойти, но на всякий случай
            raise RuntimeError("LLM: Неизвестная ошибка при отправке после всех ретраев.")
        return None # Добавлено для ясности, хотя raise не даст сюда дойти

    def create_session(self, session_id: str) -> bool:
        """Создает новую сессию чата."""
        # Проверяем работоспособность клиента
        if not self.is_operational or not self.model:
            logger.error("LLMClient не готов к работе, сессия не может быть создана.")
            return False

        if session_id in self.chat_sessions:
            logger.warning(f"Сессия {session_id} уже существует.")
            # Можно пересоздать или просто вернуть True
            return True

        try:
            logger.info(f"Создание chat_session для {session_id}")
            # Начинаем с пустой истории
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
            # Отправляем промпт как первое сообщение
            await self._retry_send_message(chat_session, self.system_prompt)
            logger.info(f"Системный промпт успешно отправлен для сессии {session_id}")
            # Важно: Не добавляем системный промпт явно в history,
            # так как Gemini может обрабатывать его отдельно или в специальном формате.
            # Первый вызов send_message с промптом обычно инициализирует контекст.
            return True
        except Exception as e:
            # Ошибка уже залоггирована в _retry_send_message
            logger.error(f"Не удалось отправить системный промпт для сессии {session_id}.")
            return False

    async def send_message(self, session_id: str, user_input: str, png_path: Optional[str] = None) -> Optional[str]:
        """Отправляет сообщение пользователя (и опционально изображение) в сессию и возвращает ответ LLM."""
        if not self.is_operational:
            logger.error("LLMClient не готов к работе, сообщение не может быть отправлено.")
            return None

        chat_session = self.chat_sessions.get(session_id)
        if not chat_session:
            logger.error(f"Сессия {session_id} не найдена для отправки сообщения.")
            return None

        if not user_input and not png_path:
             logger.warning("Попытка отправить пустое сообщение без изображения.")
             return None # Не отправляем пустое сообщение

        try:
            content_parts = []
            # Добавляем текстовую часть, если она есть
            if user_input:
                 content_parts.append(user_input)
                 logger.info(f"Подготовка к отправке: текст '{user_input[:50]}...'")

            # Добавляем изображение, если путь указан и файл существует
            image_added = False
            if png_path:
                if os.path.exists(png_path) and os.path.isfile(png_path):
                    try:
                        with open(png_path, "rb") as f:
                            png_data = f.read()
                        # Используем Part.from_data для добавления изображения
                        content_parts.append(genai.types.Part.from_data(data=png_data, mime_type="image/png"))
                        image_added = True
                        logger.info(f"Изображение из {png_path} добавлено к сообщению.")
                    except Exception as img_e:
                         logger.error(f"Ошибка чтения или добавления изображения из {png_path}: {img_e}")
                else:
                     logger.warning(f"Файл изображения не найден или не является файлом: {png_path}")

            if not content_parts:
                 logger.error("Нет контента (ни текста, ни изображения) для отправки.")
                 return None

            # Отправляем собранный контент
            answer_text = await self._retry_send_message(chat_session, content_parts)

            # Возвращаем текстовый ответ (уже проверен на None в _retry_send_message)
            # Логирование ответа теперь происходит в _retry_send_message
            return answer_text

        except Exception as e:
            # Ошибка уже залоггирована в _retry_send_message
            logger.error(f"Не удалось отправить сообщение для сессии {session_id}.")
            return None

    def set_model(self, model_name: str) -> bool:
        """Изменяет активную модель LLM."""
        if not self.is_operational: # Проверяем изначальную готовность
            logger.error("LLMClient не был успешно инициализирован, смена модели невозможна.")
            return False
        if not genai: # Доп. проверка на библиотеку
             logger.error("Библиотека google.generativeai недоступна.")
             return False
        if self.model_name == model_name:
             logger.info(f"Модель уже установлена на {model_name}.")
             return True

        logger.info(f"Попытка смены модели на: {model_name}")
        try:
            # Проверяем доступность новой модели
            available_models = self.get_available_models()
            if not available_models:
                 logger.error("Не удалось получить список моделей для проверки перед сменой.")
                 return False
            if model_name not in available_models:
                logger.error(f"Новая модель '{model_name}' не найдена в списке доступных: {available_models}")
                return False

            # Инициализируем новую модель
            generation_config = GenerationConfig(candidate_count=1) # Используем тот же config
            new_model = genai.GenerativeModel(model_name, generation_config=generation_config)
            logger.info(f"Новый объект модели {model_name} создан.")

            # Обновляем модель и имя модели
            self.model = new_model
            self.model_name = model_name

            # Пересоздаем существующие сессии с НОВОЙ моделью, сохраняя историю
            logger.info("Обновление существующих сессий с новой моделью...")
            for session_id, old_session in list(self.chat_sessions.items()): # Используем list() для безопасной итерации при изменении словаря
                try:
                    # Копируем историю. Убедимся, что history это список нужного формата
                    history_data = []
                    if hasattr(old_session, 'history') and isinstance(old_session.history, list):
                         history_data = old_session.history
                         # Возможно, потребуется преобразовать элементы истории, если формат изменился
                         # history_data = [copy.deepcopy(msg) for msg in old_session.history]
                    else:
                         logger.warning(f"Не удалось получить историю для сессии {session_id}, сессия будет создана пустой.")

                    # Создаем новую сессию с той же историей, но с новой моделью
                    new_session = self.model.start_chat(history=history_data)
                    self.chat_sessions[session_id] = new_session
                    logger.info(f"Сессия {session_id} успешно обновлена с моделью {model_name}.")
                except Exception as session_e:
                    logger.error(f"Ошибка при обновлении сессии {session_id} с новой моделью: {session_e}. Сессия может быть потеряна.")
                    # Решаем, удалять ли сессию или оставлять старую
                    if session_id in self.chat_sessions:
                        del self.chat_sessions[session_id]

            # Сохраняем новую модель в конфиг
            self.config["model"] = model_name
            self._save_config()
            logger.info(f"Модель успешно изменена на {model_name} и сохранена в конфигурации.")
            return True

        except Exception as e:
            logger.exception(f"Ошибка смены модели на {model_name}: {e}")
            # Не откатываем self.model, так как он мог быть испорчен
            self.is_operational = False # Считаем клиент неработоспособным после ошибки
            return False

# --- КОНЕЦ ФАЙЛА llm_client.py ---