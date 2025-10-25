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
        console.log("ТОЧКА 3: Получен объект report по SSE:", report);
		
        if (report.command === "start_mission") {
            console.log("Получена команда start_mission. Очистка состояния клиента...");
            reports = []; // Очищаем массив докладов
            if (window.llmChat && typeof window.llmChat.clearChat === 'function') {
                window.llmChat.clearChat(); // Очищаем окно чата
            }
            if (window.missionSettings && typeof window.missionSettings.handleStartMission === 'function') {
                window.missionSettings.handleStartMission();
            }
            // Вызываем updateReports с пустым массивом, чтобы немедленно стереть маркеры с карты
            window.unitLayer.updateReports([]);
        } 
        // --- НАЧАЛО ИЗМЕНЕНИЙ ---
        // Обрабатываем все остальные сообщения
        else {
            if (report.t === "llm_log" && window.llmChat) {
                console.log("Обработка как llm_log");
                window.llmChat.addMessage(`[СЕРВЕР]: ${report.message}`);
            } else if (report.t === "llm_response" && window.llmChat) {
                console.log("Обработка как llm_response");
                let responseText = report.message;
                try {
                    const jsonObject = JSON.parse(responseText);
                    responseText = JSON.stringify(jsonObject, null, 2);
                } catch (e) {
                    // ...
                }
                window.llmChat.addMessage(`[LLM]:\n${responseText}`);
            }
            // Добавляем в массив только обычные репорты, а не команду start_mission
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