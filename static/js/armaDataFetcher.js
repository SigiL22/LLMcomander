// js/armaDataFetcher.js
let reports = [];

function setupArmaDataStream() {
    const source = new EventSource('/arma_data_stream');
    source.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.status === "success") {
            console.log("Получены данные arma_data:", data.data);
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
        //console.log("ТОЧКА 3: Получен объект report по SSE:", report);
		
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

            // Парсим конфиг на клиенте
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
                            //console.log("Клиент авто-настроен на сторону:", sideRaw);
                            const sideSelect = document.getElementById("llmSide");
                            if (sideSelect) sideSelect.value = sideRaw;
                        }
                    }
                }
            }

            window.unitLayer.updateReports([]);
        }
        else {
            // 1. ЛОГИ (МЫСЛИ) - ЭТО ОСТАВЛЯЕМ В ЧАТЕ
            if (report.t === "llm_log" && window.llmChat) {
                window.llmChat.addMessage(`[СЕРВЕР]: ${report.message}`);
            } 
            // 2. ОТВЕТ LLM (КОМАНДЫ) - ЭТО СКРЫВАЕМ ИЗ ЧАТА, ЕСЛИ ЭТО JSON С КОМАНДАМИ
            else if (report.t === "llm_response" && window.llmChat) {
                let isTechnicalData = false;
                let responseText = report.message;
                
                try {
                    const jsonObject = JSON.parse(responseText);
                    
                    // Если это команды для карты
                    if (jsonObject.commands && Array.isArray(jsonObject.commands)) {
                        //console.log("[DataFetcher] Команды LLM получены и переданы в UnitLayer.");
                        if (window.unitLayer && typeof window.unitLayer.processLLMCommands === 'function') {
                            window.unitLayer.processLLMCommands(jsonObject.commands);
                        }
                        isTechnicalData = true; // Помечаем как технические данные
                    }
                    else if (Array.isArray(jsonObject)) {
                         if (window.unitLayer && typeof window.unitLayer.processLLMCommands === 'function') {
                            window.unitLayer.processLLMCommands(jsonObject);
                        }
                        isTechnicalData = true;
                    }

                } catch (e) {
                    // Если не JSON, значит просто текст - его можно показать
                }

                // --- ИЗМЕНЕНИЕ: Если это технические данные (команды), НЕ пишем в чат ---
                if (!isTechnicalData) {
                    window.llmChat.addMessage(`[LLM]:\n${responseText}`);
                }
                // -----------------------------------------------------------------------
            }
            
            // Добавляем в массив репортов (для отображения иконок событий на карте)
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