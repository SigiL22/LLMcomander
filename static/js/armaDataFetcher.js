function setupArmaDataStream() {
    const source = new EventSource('/arma_data_stream');
    source.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.status === "success") {
            console.log("Данные от ARMA получены:");
            console.log("Вызываем updateData");
            window.unitLayer.updateData(data.data);
        }
    };
    source.onerror = function() {
        console.error("Ошибка соединения с сервером SSE");
        source.close();
    };
}
setupArmaDataStream();