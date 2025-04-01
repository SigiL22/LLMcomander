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
    from google.generativeai.types import GenerationConfig, Part # Импортируем Part явно
except ImportError:
    genai = None
    GenerationConfig = None
    Part = None # Определяем как None, если импорт не удался

# --- Настройка логгера ---
logger = logging.getLogger("llm_client")
# Устанавливаем DEBUG для подробного логгирования запросов/ответов
# Если хотите меньше логов, измените на logging.INFO
logger.setLevel(logging.DEBUG)
logger.propagate = False # Предотвращаем дублирование

if not logger.handlers:
    log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    # Убедитесь, что директория для логов существует или создайте ее
    log_file = "llm_client.log"
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            # Обработка возможной ошибки race condition, если папка создана другим процессом
            if not os.path.isdir(log_dir):
                print(f"Error creating log directory {log_dir}: {e}") # Используем print, т.к. логгер может быть не готов

    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file handler for {log_file}: {e}") # Используем print, т.к. логгер может быть не готов
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
        if not genai or not GenerationConfig or not Part:
            logger.error("Библиотека google.generativeai или ее компоненты не найдены. LLMClient будет нерабочим.")
            return # Выходим, is_operational останется False

        # --- 2. Загрузка конфигурации и промпта ---
        self.config = self._load_config()
        # Проверяем правильность ключа (может быть 'geminy_api_key' или 'gemini_api_key')
        self.gemini_api_key = self.config.get("gemini_api_key") or self.config.get("geminy_api_key")
        if not self.gemini_api_key:
             logger.error(f"API ключ 'gemini_api_key' (или 'geminy_api_key') не найден или пуст в {self.config_file}.")
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
            # Убедимся, что сохраняем правильный ключ API, если он был исправлен при загрузке
            if "geminy_api_key" in self.config and "gemini_api_key" not in self.config:
                self.config["gemini_api_key"] = self.config.pop("geminy_api_key")

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
                    logger.warning(f"Файл системного промпта {self.system_prompt_file} пустой. Используется дефолтный промпт.")
                    # Можно вернуть дефолтный промпт или None
                    return "Ты командир в Arma 3. Анализируй данные миссии и отдавай команды в формате JSON."
                logger.info(f"Системный промпт загружен из {self.system_prompt_file}.")
                return text
        except FileNotFoundError:
             logger.error(f"Файл системного промпта {self.system_prompt_file} не найден. Используется дефолтный промпт.")
             return "Ты командир в Arma 3. Анализируй данные миссии и отдавай команды в формате JSON."
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
                m.name # Сохраняем полное имя модели (например, 'models/gemini-1.5-flash-latest')
                for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]
            if not models_list:
                logger.warning("API вернуло пустой список моделей, поддерживающих generateContent.")
            else:
                 # Логируем только короткие имена для читаемости
                 short_names = [name.split('/')[-1] for name in models_list]
                 logger.info(f"Доступные модели (generateContent): {short_names}")
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
        # Имя модели может быть коротким (gemini-1.5...) или полным (models/gemini-1.5...)
        # Приводим все к полному формату для сравнения
        full_model_name = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"

        if not available_models:
             logger.warning("Список доступных моделей пуст (возможно, из-за ошибки API). Проверка невозможна.")
             # Можно поднять исключение, если модель критична
             raise ValueError("Cannot check model availability, API returned no models.")
        elif full_model_name not in available_models:
            short_available = [name.split('/')[-1] for name in available_models]
            logger.warning(f"Выбранная модель '{self.model_name}' (полное имя: '{full_model_name}') не найдена в списке доступных: {short_available}")
            # Можно выбрать другую модель или поднять исключение
            raise ValueError(f"Model '{self.model_name}' not found in available models.")
        else:
            logger.info(f"Выбранная модель '{self.model_name}' доступна.")
            # Убедимся, что используем полное имя модели при инициализации
            self.model_name = full_model_name


    async def _retry_send_message(self, session_id: str, chat_session, content, max_retries=3) -> Optional[str]:
        """Пытается отправить сообщение с ретраями при определенных ошибках."""
        if not self.is_operational: # Добавим проверку здесь на всякий случай
            logger.error(f"LLMClient не готов к работе, отправка сообщения для сессии {session_id} прервана.")
            return None

        delays = [2, 5, 10] # Задержки в секундах
        last_exception = None

        for attempt in range(max_retries):
            try:
                delay = delays[attempt]

                # --- НАЧАЛО: Логирование запроса ---
                log_content_parts = []
                request_content_for_log = content # Используем локальную переменную
                if isinstance(request_content_for_log, list):
                    for part in request_content_for_log:
                        if isinstance(part, str):
                            # Обрезаем длинные строки для лога
                            log_part = f'"{part[:500]}..."' if len(part) > 500 else f'"{part}"'
                            log_content_parts.append(log_part)
                        elif isinstance(part, Part) and hasattr(part, 'mime_type') and 'image' in part.mime_type:
                            # Показываем, что это изображение (используем Part)
                            log_content_parts.append(f"[Image Data ({part.mime_type})]")
                        else:
                            # Другие возможные типы данных
                            log_content_parts.append(f"[Unknown Part Type: {type(part)}]")
                    log_content_str = f"[{', '.join(log_content_parts)}]"
                elif isinstance(request_content_for_log, str):
                    # Обрезаем длинные строки для лога
                    log_content_str = f'"{request_content_for_log[:500]}..."' if len(request_content_for_log) > 500 else f'"{request_content_for_log}"'
                else:
                    log_content_str = f"[Unknown Content Type: {type(request_content_for_log)}]"

                logger.debug(f"LLM Request (Session: {session_id}, Attempt: {attempt + 1}/{max_retries}): --> {log_content_str}")
                # --- КОНЕЦ: Логирование запроса ---

                logger.info(f"LLM отправка (Session: {session_id}, попытка {attempt + 1}/{max_retries})...") # Добавим сессию в INFO
                # Используем asyncio.to_thread для запуска блокирующей функции send_message
                response = await asyncio.to_thread(
                    chat_session.send_message,
                    request_content_for_log # Используем локальную переменную
                )
                # Проверяем наличие текста в ответе
                if response and hasattr(response, 'text'):
                    # --- НАЧАЛО: Логирование ответа ---
                    log_response_text = response.text
                    # Логируем ПОЛНЫЙ ответ на уровне DEBUG
                    logger.debug(f"LLM Response (Session: {session_id}, Attempt: {attempt + 1}): <-- {log_response_text}")
                    # --- КОНЕЦ: Логирование ответа ---

                    # Оставляем краткое сообщение INFO
                    logger.info(f"LLM ответ получен (Session: {session_id}, попытка {attempt + 1}).")
                    return response.text
                else:
                    # Логируем даже если нет 'text', чтобы понять, что пришло
                    logger.warning(f"LLM вернул ответ без 'text' (Session: {session_id}, попытка {attempt + 1}): {response}")
                    last_exception = ValueError("LLM returned an invalid response (missing 'text' attribute).")
                    if attempt < max_retries - 1:
                        logger.info(f"Пауза {delay} сек перед следующей попыткой (Session: {session_id})...")
                        await asyncio.sleep(delay)
                    continue # Переходим к следующей попытке

            except Exception as e:
                last_exception = e
                # Обрабатываем специфичные ошибки API (коды могут отличаться)
                # 503 Service Unavailable, 429 Too Many Requests, 500 Internal Server Error
                # Ошибку геолокации (400) обрабатывать ретраями бессмысленно
                error_str = str(e).lower()
                if "400 user location is not supported" in error_str:
                    logger.error(f"Ошибка геолокации API Gemini (Session: {session_id}): {e}. Отправка невозможна из этого региона.")
                    raise e # Прерываем ретраи, ошибка фатальна для этого региона
                elif "503" in error_str or "429" in error_str or "500" in error_str:
                    if attempt < max_retries - 1:
                        logger.warning(f"Ошибка API ({type(e).__name__}), попытка {attempt + 1}/{max_retries} (Session: {session_id}). Пауза {delay} сек: {e}")
                        await asyncio.sleep(delay)
                        continue # Переходим к следующей попытке
                    else:
                        logger.error(f"Превышено количество попыток ({max_retries}) после ошибки API (Session: {session_id}): {e}")
                        raise e # Поднимаем ошибку после последней попытки
                else:
                    # Неизвестная ошибка, прерываем ретраи
                    logger.exception(f"Неизвестная ошибка при отправке в LLM (Session: {session_id}, попытка {attempt + 1}): {e}")
                    raise e

        # Если все попытки не удались
        logger.error(f"Не удалось отправить сообщение в LLM для сессии {session_id} после всех попыток.")
        if last_exception:
            raise last_exception # Поднимаем последнюю пойманную ошибку
        else:
            # Этого не должно произойти, но на всякий случай
            raise RuntimeError(f"LLM: Неизвестная ошибка при отправке для сессии {session_id} после всех ретраев.")
        # return None # Добавлено для ясности, хотя raise не даст сюда дойти

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
            # Отправляем промпт как первое сообщение, передаем session_id в retry
            await self._retry_send_message(session_id, chat_session, self.system_prompt)
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
                 # Логируем только начало текста на уровне INFO
                 logger.info(f"Подготовка к отправке в LLM (Session: {session_id}): текст '{user_input[:50]}...'")

            # Добавляем изображение, если путь указан и файл существует
            image_added = False
            if png_path:
                if os.path.exists(png_path) and os.path.isfile(png_path):
                    try:
                        logger.info(f"Чтение изображения из {png_path}...")
                        with open(png_path, "rb") as f:
                            png_data = f.read()
                        # Используем Part.from_data для добавления изображения
                        content_parts.append(Part.from_data(data=png_data, mime_type="image/png"))
                        image_added = True
                        logger.info(f"Изображение из {png_path} добавлено к сообщению (Session: {session_id}).")
                    except Exception as img_e:
                         logger.error(f"Ошибка чтения или добавления изображения из {png_path} (Session: {session_id}): {img_e}")
                else:
                     logger.warning(f"Файл изображения не найден или не является файлом: {png_path} (Session: {session_id})")

            if not content_parts:
                 logger.error(f"Нет контента (ни текста, ни валидного изображения) для отправки (Session: {session_id}).")
                 return None

            # Отправляем собранный контент, передаем session_id в retry
            answer_text = await self._retry_send_message(session_id, chat_session, content_parts)

            # Возвращаем текстовый ответ (уже проверен на None в _retry_send_message)
            # Логирование ответа происходит в _retry_send_message
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
        if not genai or not GenerationConfig: # Доп. проверка на библиотеку
             logger.error("Библиотека google.generativeai или GenerationConfig недоступна.")
             return False

        # Приводим имя новой модели к полному формату
        full_new_model_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

        if self.model_name == full_new_model_name:
             logger.info(f"Модель уже установлена на {self.model_name.split('/')[-1]}.")
             return True

        logger.info(f"Попытка смены модели на: {model_name} (полное имя: {full_new_model_name})")
        try:
            # Проверяем доступность новой модели
            available_models = self.get_available_models()
            if not available_models:
                 logger.error("Не удалось получить список моделей для проверки перед сменой.")
                 return False
            if full_new_model_name not in available_models:
                short_available = [name.split('/')[-1] for name in available_models]
                logger.error(f"Новая модель '{model_name}' не найдена в списке доступных: {short_available}")
                return False

            # Инициализируем новую модель
            generation_config = GenerationConfig(candidate_count=1) # Используем тот же config
            new_model = genai.GenerativeModel(full_new_model_name, generation_config=generation_config)
            logger.info(f"Новый объект модели {full_new_model_name} создан.")

            # Обновляем модель и имя модели
            self.model = new_model
            self.model_name = full_new_model_name # Сохраняем полное имя

            # Пересоздаем существующие сессии с НОВОЙ моделью, сохраняя историю
            logger.info("Обновление существующих сессий с новой моделью...")
            active_session_ids = list(self.chat_sessions.keys()) # Копируем ключи перед итерацией
            for session_id in active_session_ids:
                old_session = self.chat_sessions.get(session_id)
                if not old_session: continue # На случай, если сессия удалилась во время итерации
                try:
                    # Копируем историю. Убедимся, что history это список нужного формата
                    history_data = []
                    if hasattr(old_session, 'history') and isinstance(old_session.history, list):
                         # Простая проверка на базовые типы данных в истории
                         if all(hasattr(msg, 'role') and hasattr(msg, 'parts') for msg in old_session.history):
                              history_data = old_session.history # Прямое копирование должно работать
                              # Если возникнут проблемы, можно использовать deepcopy:
                              # import copy
                              # history_data = copy.deepcopy(old_session.history)
                         else:
                              logger.warning(f"История сессии {session_id} имеет неожиданный формат, сессия будет создана пустой.")

                    else:
                         logger.warning(f"Не удалось получить историю для сессии {session_id}, сессия будет создана пустой.")

                    # Создаем новую сессию с той же историей, но с новой моделью
                    new_session = self.model.start_chat(history=history_data)
                    self.chat_sessions[session_id] = new_session
                    logger.info(f"Сессия {session_id} успешно обновлена с моделью {self.model_name.split('/')[-1]}.")
                except Exception as session_e:
                    logger.error(f"Ошибка при обновлении сессии {session_id} с новой моделью: {session_e}. Сессия удалена.")
                    # Удаляем сессию при ошибке пересоздания
                    if session_id in self.chat_sessions:
                        del self.chat_sessions[session_id]

            # Сохраняем новую модель в конфиг (короткое имя для читаемости в JSON)
            self.config["model"] = self.model_name.split('/')[-1]
            self._save_config()
            logger.info(f"Модель успешно изменена на {self.model_name.split('/')[-1]} и сохранена в конфигурации.")
            return True

        except Exception as e:
            logger.exception(f"Ошибка смены модели на {model_name}: {e}")
            # Не откатываем self.model, так как он мог быть испорчен
            # Считаем клиент неработоспособным после ошибки смены модели, т.к. состояние неопределенное
            self.is_operational = False
            logger.error("LLMClient помечен как неработоспособный после ошибки смены модели.")
            return False

# --- КОНЕЦ ФАЙЛА llm_client.py ---