// Функция для запроса данных с сервера
function fetchArmaData() {
    fetch('/arma_data')
        .then(response => {
            console.log("Статус ответа сервера:", response.status); // Логируем HTTP-статус
            return response.json();
        })
        .then(data => {
            console.log("Полный ответ от сервера:", data); // Логируем весь JSON
            if (data.status === "success") {
                console.log("Данные от ARMA:", JSON.stringify(data.data, null, 2));
            } else {
                console.log("Нет данных от ARMA (статус:", data.status, ")");
            }
        })
        .catch(error => console.error("Ошибка при получении данных от ARMA:", error));
}

setInterval(fetchArmaData, 10000);
fetchArmaData();