# --- START OF FILE llm_tactical_controller.py ---

import logging
import json
import asyncio
from collections import Counter # <<< ДОБАВЛЯЕМ ИМПОРТ

# Импортируем модули из основного потока
# Предполагается, что эти модули доступны
import arma_connector_async as arma_connector
from llm_client import LLMClient

logger = logging.getLogger("Server") # Используем тот же логгер, что и в server.py

def filter_data_for_llm(full_arma_data: dict, side: str, group_names: list = None) -> list:
    # Используем наш новый безопасный метод
    groups_to_process = get_side_data_safe(full_arma_data, side)
    
    if not groups_to_process:
        # Логируем только если данных нет, чтобы понимать контекст
        # (можно закомментировать, если спамит в лог)
        # logger.warning(f"Данные для стороны {side} не найдены.") 
        return []

    # Если указаны конкретные группы, фильтруем их
    if group_names:
        groups_to_process = [g for g in groups_to_process if g.get("n") in group_names]

    filtered_groups = []
    for group in groups_to_process:
        # ... (ДАЛЕЕ КОД БЕЗ ИЗМЕНЕНИЙ: подсчет оружия и формирование структуры) ...
        all_weapons = []
        for unit in group.get("u", []):
            primary = unit.get("pw")
            secondary = unit.get("sw")
            if primary: all_weapons.append(primary)
            if secondary: all_weapons.append(secondary)
        
        weapon_summary = Counter(all_weapons)
        
        filtered_group = {
            "n": group.get("n"),
            "p": group.get("p"),
            "c": group.get("c"),
            "co": len(group.get("u", [])),
            "u_summary": dict(weapon_summary),
            "v": [{"id": v.get("id"), "vn": v.get("vn"), "h": v.get("h"), "p": v.get("p")} for v in group.get("v", [])]
        }
        filtered_groups.append(filtered_group)
        
    return filtered_groups

async def handle_llm_response(response_text: str):
    """
    Обрабатывает ответ от LLM.
    Поддерживает формат { "reasoning": "...", "commands": [...] }
    """
    if not response_text:
        return
        
    # --- НОВОЕ: Очистка от Markdown ---
    cleaned_text = response_text.strip()
    
    # Удаляем ```json в начале
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]
    
    # Удаляем ``` в конце
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
        
    cleaned_text = cleaned_text.strip()
    # ----------------------------------

    # 1. Пытаемся распарсить JSON
    try:
        response_json = json.loads(cleaned_text) # <-- ИСПОЛЬЗУЕМ CLEANED_TEXT
    except json.JSONDecodeError as e:
        logger.error(f"Ответ LLM не является валидным JSON даже после очистки: {e}")
        logger.debug(f"Raw text: {response_text}")
        await arma_connector.reports_queue.put({
            "t": "llm_log",
            "message": "Ошибка: LLM прислала невалидный JSON (форматирование)."
        })
        return

    # 2. Логика обработки структуры
    commands_to_send = []
    reasoning_text = ""

    # СЦЕНАРИЙ А: Новый формат с пояснением
    if isinstance(response_json, dict) and "commands" in response_json:
        reasoning_text = response_json.get("reasoning", "")
        commands_raw = response_json.get("commands", [])
        
        if isinstance(commands_raw, list):
            commands_to_send = commands_raw
        else:
            logger.error("Поле 'commands' должно быть списком.")

    # СЦЕНАРИЙ Б: Старый формат (просто список команд)
    elif isinstance(response_json, list):
        commands_to_send = response_json
    
    # СЦЕНАРИЙ В: Одиночная команда (словарь без ключа commands)
    elif isinstance(response_json, dict) and "command" in response_json:
        commands_to_send = [response_json] # Оборачиваем в список

    # 3. Отправляем Пояснение в Чат (Web UI)
    # Мы используем тип 'llm_log', чтобы оно просто появилось в окне чата у пользователя
    if reasoning_text:
        logger.info(f"LLM Reasoning: {reasoning_text}")
        await arma_connector.reports_queue.put({
            "t": "llm_log",
            "message": f"💭 МЫСЛИ: {reasoning_text}"
        })
    
    # Также транслируем полный сырой ответ (опционально, если хотите видеть JSON в чате)
    # await arma_connector.reports_queue.put({
    #     "t": "llm_response",
    #     "message": response_text
    # })

    # 4. Отправляем Команды в Arma (SQF)
    if commands_to_send:
        logger.info(f"Отправка {len(commands_to_send)} команд в Arma.")
        # Отправляем список целиком в Арму
        await arma_connector.send_callback_to_arma_async(commands_to_send)
        
        # --- НОВОЕ: Дублируем команды Веб-клиенту для отрисовки маркеров ---
        # Формируем структуру, которую ждет armaDataFetcher.js
        # t="llm_response", message=JSON-строка с полем "commands"
        visualization_payload = {
            "t": "llm_response",
            "message": json.dumps({"commands": commands_to_send}, ensure_ascii=False)
        }
        await arma_connector.reports_queue.put(visualization_payload)
        logger.info("Команды продублированы веб-клиенту для визуализации.")
        # ------------------------------------------------------------------

    else:
        logger.warning("В ответе LLM не найдено команд для выполнения.")


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
        
        
async def trigger_llm_detection_report(llm_client: LLMClient, assigned_side: str, report: dict):
    """
    Формирует и отправляет в LLM отчет об обнаружении противника (пехоты или техники).
    """
    if not llm_client or not llm_client.is_operational:
        logger.warning("Отчет об обнаружении не может быть отправлен: LLM клиент не готов.")
        return

    # 1. Получаем самые свежие данные от Arma, чтобы найти инфо о нашем отряде
    async with arma_connector.data_lock:
        current_arma_data = arma_connector.arma_data
    
    if not current_arma_data:
        logger.warning("Отчет об обнаружении не может быть отправлен: нет данных от Arma.")
        return

    # 2. ИЩЕМ ДАННЫЕ О ДОКЛАДЧИКЕ (Используем нашу безопасную функцию!)
    reporting_group_name = report.get("g") or report.get("ge")
    reporting_group_data = None
    
    # Получаем список групп стороны безопасным способом
    side_groups = get_side_data_safe(current_arma_data, assigned_side)
    
    if side_groups:
        for group in side_groups:
            if group.get("n") == reporting_group_name:
                reporting_group_data = {
                    "name": group.get("n"),
                    "unit_count": group.get("co", 0)
                }
                break
    
    if not reporting_group_data:
        logger.warning(f"Не удалось найти данные для отряда '{reporting_group_name}' в текущем состоянии Arma.")
        # Все равно продолжим, отправим отчет без данных о докладчике
        reporting_group_data = {"name": reporting_group_name or "Unknown Group"}

    # 3. Формируем JSON-сообщение для LLM на основе типа доклада
    context_text = ""
    llm_payload = {
        "reporting_group": reporting_group_data
    }

    report_type = report.get("t")
    if report_type == "enemy_detected":
        context_text = "Your unit has detected enemy infantry."
        llm_payload["event"] = "infantry_spotted"
        llm_payload["detected_enemy"] = {
            "unit_count": report.get("ce"),
            "position": report.get("p")
        }
    elif report_type == "vehicle_detected":
        context_text = "Your unit has detected an enemy vehicle."
        llm_payload["event"] = "vehicle_spotted"
        llm_payload["detected_enemy"] = {
            "vehicle_name": report.get("vehicle_name") or report.get("vehicle_type"),
            "position": report.get("p")
        }
    else:
        logger.error(f"Неподдерживаемый тип доклада для trigger_llm_detection_report: {report_type}")
        return

    # 4. Отправляем сформированный отчет в LLM
    try:
        json_payload_str = json.dumps(llm_payload, ensure_ascii=False)
        full_prompt = f"{context_text}\n{json_payload_str}"
        
        logger.info(f"Отправка отчета об обнаружении в LLM. Контекст: {context_text}")
        
        response = await llm_client.send_message("arma_session", user_input=full_prompt)
        
        # 5. Обрабатываем ответ от LLM
        await handle_llm_response(response)

    except Exception as e:
        logger.exception(f"Ошибка при отправке отчета об обнаружении в LLM: {e}")
        
async def trigger_llm_event_report(llm_client: LLMClient, report: dict):
    """
    Формирует и отправляет в LLM отчет о событии (зачистка, потеря контакта, уничтожение).
    """
    if not llm_client or not llm_client.is_operational:
        logger.warning("Отчет о событии не может быть отправлен: LLM клиент не готов.")
        return

    # 1. Формируем базовую часть сообщения для LLM
    context_text = ""
    report_type = report.get("t")
    
    llm_payload = {
        "reporting_group": {
            "name": report.get("g"),
            "unit_count": report.get("co")
        },
        "event": report_type,
        "event_details": {}
    }

    # 2. Добавляем детали в зависимости от типа события
    if report_type == "enemies_cleared":
        context_text = "Your unit reports that the area is clear of enemies."
        llm_payload["event_details"]["position"] = report.get("p")
        
    elif report_type == "vehicle_lost":
        context_text = "Your unit reports losing contact with an enemy vehicle."
        llm_payload["event_details"]["vehicle_name"] = report.get("vehicle_name")
        llm_payload["event_details"]["last_known_position"] = report.get("p")
        
    elif report_type == "vehicle_destroyed":
        context_text = "Your unit reports destroying an enemy vehicle."
        llm_payload["event_details"]["vehicle_name"] = report.get("vehicle_name")
        llm_payload["event_details"]["position"] = report.get("p")
        
    else:
        logger.error(f"Неподдерживаемый тип доклада для trigger_llm_event_report: {report_type}")
        return

    # 3. Отправляем сформированный отчет в LLM
    try:
        json_payload_str = json.dumps(llm_payload, ensure_ascii=False)
        full_prompt = f"{context_text}\n{json_payload_str}"
        
        logger.info(f"Отправка отчета о событии в LLM. Контекст: {context_text}")
        
        response = await llm_client.send_message("arma_session", user_input=full_prompt)
        
        # 4. Обрабатываем ответ от LLM
        await handle_llm_response(response)

    except Exception as e:
        logger.exception(f"Ошибка при отправке отчета о событии в LLM: {e}")
        
async def trigger_llm_batch_report(llm_client: LLMClient, assigned_side: str, reports: list):
    """
    Обрабатывает пакет докладов, группирует их по отрядам и отправляет
    единым структурированным запросом в LLM.
    Дополняет отсутствующие данные (позиция, численность) из глобального состояния arma_data.
    """
    if not llm_client or not llm_client.is_operational:
        logger.warning("Пакетный отчет не может быть отправлен: LLM клиент не готов.")
        return
    if not reports:
        logger.info("Пакетный отчет пуст, отправка отменена.")
        return

    # 1. Получаем глобальные данные для обогащения информацией
    async with arma_connector.data_lock:
        current_arma_data = arma_connector.arma_data

    # Вспомогательная функция поиска группы в arma_data
    def find_group_info(g_name, side_name):
        if not current_arma_data: return None
        # Используем безопасный поиск стороны
        side_groups = get_side_data_safe(current_arma_data, side_name)
        if side_groups:
            for g in side_groups:
                if g.get("n") == g_name:
                    return g
        return None

    # 2. Создаем словарь для группировки докладов по имени отряда
    grouped_reports = {}

    for r in reports:
        group_name = r.get("g")
        if not group_name:
            continue

        # Если отряда еще нет в словаре, создаем для него запись
        if group_name not in grouped_reports:
            # Пытаемся взять данные из репорта
            pos = r.get("gp")
            count = r.get("co")
            
            # --- FIX: Если данных нет в репорте, ищем в глобальном кэше ---
            if not pos or not count:
                cached_group = find_group_info(group_name, assigned_side)
                if cached_group:
                    if not pos: pos = cached_group.get("p")
                    if not count: count = cached_group.get("co") # Или len(cached_group.get('u', []))
            # -------------------------------------------------------------

            grouped_reports[group_name] = {
                "position": pos,  
                "unit_count": count,
                "reports": []
            }
        
        # Обновляем данные, если в текущем репорте они свежее/есть, а в базе нет
        if r.get("co"):
            grouped_reports[group_name]["unit_count"] = r.get("co")
        if r.get("gp"):
            grouped_reports[group_name]["position"] = r.get("gp")

        # 3. Формируем компактный объект 'detail' для каждого доклада
        report_type = r.get("t")
        detail = {"event": report_type}

        if report_type == "enemy_detected":
            detail["detected_type"] = "infantry"
            detail["count"] = r.get("ce")
            detail["position"] = r.get("p")
        elif report_type == "vehicle_detected":
            detail["detected_type"] = "vehicle"
            detail["vehicle_name"] = r.get("vehicle_name") or r.get("vehicle_type")
            detail["position"] = r.get("p")
            detail["health"] = round(r.get("h", 1.0), 2)
        elif report_type == "vehicle_abandoned":
            detail["vehicle_name"] = r.get("vehicle_name")
            detail["position"] = r.get("p")
            detail["health"] = round(r.get("h", 1.0), 2)
        elif report_type == "vehicle_disabled":
            detail["vehicle_name"] = r.get("vehicle_name")
            detail["position"] = r.get("p")
            detail["health"] = round(r.get("h", 1.0), 2)
        elif report_type == "enemies_cleared":
            pass 
        elif report_type == "vehicle_lost":
            detail["vehicle_name"] = r.get("vehicle_name")
            detail["last_known_position"] = r.get("p")
            detail["last_known_health"] = round(r.get("h", 1.0), 2)
        elif report_type == "vehicle_destroyed":
            detail["vehicle_name"] = r.get("vehicle_name")
            detail["position"] = r.get("p")
        elif report_type == "waypoint_reached":
            detail["event"] = "waypoint_completed"
            detail["position"] = r.get("p")
        
        grouped_reports[group_name]["reports"].append(detail)

    if not grouped_reports:
        logger.info("В пакете не найдено докладов для отправки в LLM.")
        return

    # 4. Преобразуем словарь в итоговый список для JSON
    final_payload_list = [
        {
            "reporting_group": name,
            "position": data["position"],
            "unit_count": data["unit_count"],
            "reports": data["reports"]
        }
        for name, data in grouped_reports.items()
    ]
    
    summary_payload = {"group_reports": final_payload_list}

    # 5. Отправляем в LLM
    try:
        context_text = "Consolidated tactical reports from your units. Analyze the situation and issue commands if necessary."
        json_payload_str = json.dumps(summary_payload, ensure_ascii=False)
        full_prompt = f"{context_text}\n{json_payload_str}"
        
        logger.info(f"CONTENT of Report: {json_payload_str}") 
        logger.info(f"Отправка сгруппированного пакетного отчета в LLM ({len(reports)} докладов).")
        
        response = await llm_client.send_message("arma_session", user_input=full_prompt)
        await handle_llm_response(response)

    except Exception as e:
        logger.exception(f"Ошибка при отправке сгруппированного отчета в LLM: {e}")
        
def get_side_data_safe(full_arma_data: dict, side_name: str) -> list:
    """
    Безопасно извлекает список групп для стороны, проверяя все варианты названия
    (EAST, OPFOR, WEST, BLUFOR и т.д.).
    """
    if not full_arma_data or "sides" not in full_arma_data:
        return []

    # Карта синонимов
    side_mapping = {
        "EAST": ["OPFOR", "EAST", "Opfor", "East"],
        "WEST": ["BLUFOR", "WEST", "Blufor", "West"],
        "GUER": ["Independent", "GUER", "Guer", "Resistance", "RESISTANCE", "IND"],
        "CIV": ["CIV", "Civilian", "Civ"]
    }

    # Получаем список вариантов для запрошенной стороны (например, для "EAST")
    target_keys = side_mapping.get(side_name.upper(), [side_name])
    
    # Ищем, какой ключ реально существует в данных Arma
    for key in target_keys:
        if key in full_arma_data["sides"]:
            return full_arma_data["sides"][key] # Возвращаем данные
            
    return [] # Если ничего не нашли

# --- END OF FILE llm_tactical_controller.py ---