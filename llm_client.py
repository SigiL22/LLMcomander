# --- START OF FILE llm_client.py ---

import json
import logging
import asyncio
import os
import PIL.Image
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, List

# --- ИМПОРТ НОВОГО SDK ---
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Загружаем переменные из .env
load_dotenv()

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
        self.client = None 
        self.chat_sessions: Dict[str, object] = {} 
        self.model_name: Optional[str] = None
        self.system_prompt: Optional[str] = None
        self.config: Dict = {}

        logger.info("Инициализация LLMClient (New google-genai SDK)...")

        if not SDK_AVAILABLE:
            logger.error("Библиотека `google-genai` не найдена. Установите: pip install google-genai")
            return

        # 1. Загрузка конфигов
        self.config = self._load_config()
        self.system_prompt = self._load_system_prompt()

        # 2. API Key
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or self.config.get("geminy_api_key")
        
        if not self.gemini_api_key or self.gemini_api_key == "INSERT_YOUR_KEY_HERE":
            logger.error("API ключ не найден! Проверьте .env или config.json.")
            return

        # 3. Model Name
        self.model_name = self.config.get("model") or os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

        if not self.system_prompt:
            logger.error("Системный промпт не загружен.")
            return

        try:
            self.client = genai.Client(api_key=self.gemini_api_key)
            self.is_operational = True
            logger.info(f"LLMClient инициализирован. Модель: {self.model_name}")
        except Exception as e:
            logger.exception(f"Ошибка инициализации клиента GenAI: {e}")

    def _load_config(self) -> Dict:
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфига: {e}")

    def _load_system_prompt(self) -> Optional[str]:
        try:
            with open(self.system_prompt_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Ошибка чтения системного промпта: {e}")
            return None

    def _get_generation_config(self):
        """Возвращает конфиг генерации для нового SDK."""
        return types.GenerateContentConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type="application/json", 
            system_instruction=self.system_prompt,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE
                ),
            ]
        )

    def get_available_models(self) -> List[str]:
        if not self.is_operational: return []
        try:
            models = self.client.models.list()
            model_names = [
                m.name.split('/')[-1] 
                for m in models 
                if "generateContent" in (m.supported_actions or [])
            ]
            return model_names
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []

    def create_session(self, session_id: str) -> bool:
        if not self.is_operational: return False
        
        try:
            chat = self.client.aio.chats.create(
                model=self.model_name,
                config=self._get_generation_config(),
                history=[] 
            )
            self.chat_sessions[session_id] = chat
            logger.info(f"Сессия '{session_id}' создана (New SDK).")
            return True
        except Exception as e:
            logger.exception(f"Ошибка создания сессии {session_id}: {e}")
            return False

    async def send_message(self, session_id: str, user_input: str, image_paths: List[str] = None) -> Optional[str]:
        if not self.is_operational:
            logger.error("LLMClient не готов.")
            return None

        chat = self.chat_sessions.get(session_id)
        
        if not chat:
            logger.warning(f"Сессия {session_id} не найдена, создаю новую.")
            if not self.create_session(session_id):
                return None
            chat = self.chat_sessions.get(session_id)

        # Сборка контента
        content_parts = []
        
        if user_input:
            content_parts.append(user_input)

        img_count = 0
        if image_paths:
            if isinstance(image_paths, str): image_paths = [image_paths]
            for path in image_paths:
                if os.path.exists(path):
                    try:
                        img = PIL.Image.open(path)
                        content_parts.append(img)
                        img_count += 1
                        logger.info(f"Добавлено изображение: {path}")
                    except Exception as e:
                        logger.error(f"Ошибка чтения картинки {path}: {e}")

        if not content_parts:
            return None

        # --- ЛОГИРОВАНИЕ ЗАПРОСА ---
        logger.info(f"LLM Request (session: {session_id}). Length: {len(user_input) if user_input else 0}. Images: {img_count}.\n"
                    f"--- Text Content ---\n{user_input}\n--- End Text Content ---")
        # ---------------------------

        # Ретрай логика
        for attempt in range(1, 4):
            try:
                response = await chat.send_message(content_parts)
                
                if response.text:
                    # --- ЛОГИРОВАНИЕ ОТВЕТА ---
                    logger.info(f"LLM Response (session: {session_id}):\n{response.text}")
                    # --------------------------
                    return response.text
                else:
                    logger.warning("Пустой ответ от модели.")
            
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str:
                    logger.warning(f"Rate Limit (429). Ждем {attempt * 2} сек...")
                    await asyncio.sleep(attempt * 2)
                elif "stop_reason" in err_str or "safety" in err_str:
                    logger.error(f"Блокировка Safety: {e}")
                    return json.dumps({"reasoning": "Запрос заблокирован системой безопасности.", "commands": []})
                else:
                    logger.error(f"Ошибка API (попытка {attempt}): {e}")
                    await asyncio.sleep(1)
        
        return None

    def set_model(self, model_name: str) -> bool:
        if self.model_name == model_name:
            return True
        
        logger.info(f"Смена модели на {model_name}...")
        try:
            self.model_name = model_name
            for session_id in list(self.chat_sessions.keys()):
                self.create_session(session_id)
            
            self.config["model"] = model_name
            self._save_config()
            return True
        except Exception as e:
            logger.exception(f"Ошибка смены модели: {e}")
            return False

# --- КОНЕЦ ФАЙЛА llm_client.py ---