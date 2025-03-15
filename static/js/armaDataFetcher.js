// js/armaDataFetcher.js
let reports = [];

function setupArmaDataStream() {
    const source = new EventSource('/arma_data_stream');
    source.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.status === "success") {
            console.log("Получены данные arma_data:", data.data);
            window.unitLayer.updateData(data.data, reports);
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
        console.log("Получен новый доклад:", report);
        reports.push(report);
        window.unitLayer.updateReports(reports); // Передаем полный массив репортов
    };
    reportSource.onerror = function() {
        console.error("Ошибка соединения с сервером SSE для докладов");
        reportSource.close();
    };
}

setupArmaDataStream();
setupReportsStream();