// js/armaDataFetcher.js
let reports = [];

function setupArmaDataStream() {
    const source = new EventSource('/arma_data_stream');
    source.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.status === "success") {
            //console.log("Получены данные arma_data:", data.data);
            window.unitLayer.updateData(data.data, reports);
            if (window.missionSettings && typeof window.missionSettings.updateSidesData === 'function') {
              window.missionSettings.updateSidesData(data.data);
            }
        }
		
    };
    source.onerror = function() {
        console.error("Ошибка соединения с сервером SSE для arma_data");
        source.close();
    };
}

function setupReportsStream() {
    const reportSource = new EventSource('/reports_stream');
    reportSource.onmessage = function(event) {
        const report = JSON.parse(event.data);
        // console.log("ТОЧКА 3: Получен объект report по SSE:", report);
		
        if (report.command === "start_mission") {
            console.log("Получена команда start_mission. Очистка состояния клиента...");
            window.missionMarkers = report.markers; 
            window.hasCapturedInitialSnapshots = false;
            
            reports = []; 
            if (window.llmChat && typeof window.llmChat.clearChat === 'function') {
                window.llmChat.clearChat(); 
            }
            if (window.missionSettings && typeof window.missionSettings.handleStartMission === 'function') {
                window.missionSettings.handleStartMission();
            }

            const configStr = report.config || "";
            if (configStr) {
                const parts = configStr.split(',');
                for (let part of parts) {
                    if (part.toLowerCase().includes('l-')) {
                        let sideRaw = part.split('-')[1].trim().toUpperCase();
                        if (sideRaw === 'EAST') sideRaw = 'OPFOR';
                        if (sideRaw === 'WEST') sideRaw = 'BLUFOR';
                        if (sideRaw === 'GUER' || sideRaw === 'RESISTANCE') sideRaw = 'Independent';
                        
                        if (window.missionSettings) {
                            window.missionSettings.llmSide = sideRaw;
                            const sideSelect = document.getElementById("llmSide");
                            if (sideSelect) sideSelect.value = sideRaw;
                        }
                    }
                }
            }
            window.unitLayer.updateReports([]);
        }
        else {
            // 1. ЛОГИ (Простые сообщения от сервера)
            if (report.t === "llm_log" && window.llmChat) {
                window.llmChat.addMessage(`[СЕРВЕР]: ${report.message}`);
            } 
            // 2. ОТВЕТ LLM (JSON)
            else if (report.t === "llm_response" && window.llmChat) {
                let responseText = report.message;
                let processed = false; // Флаг, обработали ли мы это как JSON

                try {
                    const jsonObject = JSON.parse(responseText);
                    
                    // А. Если есть команды - отправляем их на слой карты (всегда)
                    if (jsonObject.commands && Array.isArray(jsonObject.commands)) {
                        if (window.unitLayer && typeof window.unitLayer.processLLMCommands === 'function') {
                            window.unitLayer.processLLMCommands(jsonObject.commands);
                        }
                    } else if (Array.isArray(jsonObject)) {
                        // Поддержка старого формата (просто массив команд)
                         if (window.unitLayer && typeof window.unitLayer.processLLMCommands === 'function') {
                            window.unitLayer.processLLMCommands(jsonObject);
                        }
                    }

                    // Б. Если есть МЫСЛИ (reasoning) - выводим их в чат
                    if (jsonObject.reasoning) {
                        window.llmChat.addMessage(`[LLM Мысли]: ${jsonObject.reasoning}`);
                        processed = true;
                    } 
                    // В. Если мыслей нет, но были команды - считаем обработанным (чтобы не спамить сырым JSON)
                    else if (jsonObject.commands || Array.isArray(jsonObject)) {
                        processed = true;
                    }

                } catch (e) {
                    // Если не распарсилось, значит это не JSON, а просто текст
                }

                // Г. Если это не JSON (или JSON без спец полей) - выводим как есть
                if (!processed) {
                    window.llmChat.addMessage(`[LLM]:\n${responseText}`);
                }
            }
            
            // Добавляем в массив репортов
            reports.push(report);
            window.unitLayer.updateReports(reports);
        }
    };
    reportSource.onerror = function() {
        console.error("Ошибка соединения с сервером SSE для докладов");
        reportSource.close();
    };
}

setupArmaDataStream();
setupReportsStream();