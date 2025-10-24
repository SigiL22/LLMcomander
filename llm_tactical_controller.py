# --- START OF FILE llm_tactical_controller.py ---

import logging
import json
import asyncio

# Импортируем модули из основного потока
# Предполагается, что эти модули доступны
import arma_connector_async as arma_connector
from llm_client import LLMClient

logger = logging.getLogger("Server") # Используем тот же логгер, что и в server.py

def filter_data_for_llm(full_arma_data: dict, side: str, group_names: list = None) -> list:
    """
    Фильтрует полный JSON от Arma, оставляя только необходимые поля для LLM.
    
    :param full_arma_data: Полный словарь arma_data.
    :param side: Сторона, для которой нужно отфильтровать данные (напр., "OPFOR").
    :param group_names: (Опционально) Список имен групп для фильтрации. Если None, берутся все группы.
    :return: Список отфильтрованных словарей групп.
    """
    filtered_groups = []
    
    if not full_arma_data or "sides" not in full_arma_data or side not in full_arma_data["sides"]:
        return []

    groups_to_process = full_arma_data["sides"][side]
    
    # Если указаны конкретные группы, фильтруем их
    if group_names:
        groups_to_process = [g for g in groups_to_process if g.get("n") in group_names]

    for group in groups_to_process:
        filtered_group = {
            "n": group.get("n"),
            "p": group.get("p"),
            "c": group.get("c"),
            "u": [{"pw": u.get("pw", "")} for u in group.get("u", [])],
            "v": [
                {
                    "id": v.get("id"),
                    "vn": v.get("vn"),
                    "h": v.get("h"),
                    "p": v.get("p")
                } 
                for v in group.get("v", [])
            ]
        }
        filtered_groups.append(filtered_group)
        
    return filtered_groups

async def handle_llm_response(response_text: str):
    """
    Обрабатывает ответ от LLM: транслирует в чат и пытается выполнить как команду.
    """
    if not response_text:
        return

    # 1. Транслируем сырой ответ в чат для всех пользователей
    await arma_connector.reports_queue.put({
        "t": "llm_response",
        "message": response_text
    })

    # 2. Пытаемся распарсить и выполнить как команду
    try:
        response_json = json.loads(response_text)
        if isinstance(response_json, dict) and "command" in response_json:
            logger.info(f"LLM вернул команду, отправка в Arma: {response_json}")
            await arma_connector.send_callback_to_arma_async(response_json)
        elif isinstance(response_json, list):
             for cmd in response_json:
                 if isinstance(cmd, dict) and "command" in cmd:
                     logger.info(f"LLM вернул команду из списка, отправка в Arma: {cmd}")
                     await arma_connector.send_callback_to_arma_async(cmd)

    except json.JSONDecodeError:
        logger.info("Ответ LLM не является валидным JSON, команда не будет выполнена.")
    except Exception as e:
        logger.exception(f"Ошибка при обработке команды от LLM: {e}")


async def trigger_llm_report(llm_client: LLMClient, assigned_side: str, context_text: str, group_names: list = None):
    """
    Основная функция-триггер: получает данные, фильтрует и отправляет отчет в LLM.
    """
    if not llm_client or not llm_client.is_operational:
        logger.warning("LLM отчет не может быть отправлен: клиент не готов.")
        return

    # 1. Получаем самые свежие данные от Arma
    async with arma_connector.data_lock:
        current_arma_data = arma_connector.arma_data
    
    if not current_arma_data:
        logger.warning("LLM отчет не может быть отправлен: нет данных от Arma.")
        return
        
    # 2. Фильтруем данные
    filtered_data = filter_data_for_llm(current_arma_data, assigned_side, group_names)
    if not filtered_data:
        logger.info(f"Нет данных для отчета LLM по стороне {assigned_side} (группы: {group_names}).")
        return

    # 3. Формируем промпт и отправляем
    try:
        json_payload = json.dumps({"units": filtered_data}, ensure_ascii=False)
        full_prompt = f"{context_text}\n{json_payload}"
        
        logger.info(f"Отправка отчета в LLM для стороны {assigned_side}. Контекст: {context_text}")
        
        response = await llm_client.send_message("arma_session", user_input=full_prompt)
        
        # 4. Обрабатываем ответ
        await handle_llm_response(response)

    except Exception as e:
        logger.exception(f"Ошибка при отправке тактического отчета в LLM: {e}")

# --- END OF FILE llm_tactical_controller.py ---