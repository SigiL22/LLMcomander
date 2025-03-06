// js/coordToolbar.js

// Функция преобразования LatLng в игровые координаты (в метрах)
// Здесь мы проецируем latlng на уровень 7 и переводим пиксели в метры.
function pixelToGame(latlng) {
  var point7 = map.project(latlng, 7); // точка на уровне 7
  var gameX = point7.x / scaleFactor;  // scaleFactor = mapImageWidth / islandWidth
  var gameY = islandHeight - (point7.y / scaleFactor);
  return { x: gameX, y: gameY };
}

// Функция обновления тулбара координат
function updateCoordToolbar(latlng) {
  var gameCoords = pixelToGame(latlng);
  
  // Номер ячейки (каждая ячейка = 100 м)
  var cellX = Math.floor(gameCoords.x / 100);
  var cellY = Math.floor(gameCoords.y / 100);
  var cellXStr = cellX.toString().padStart(3, '0');
  var cellYStr = cellY.toString().padStart(3, '0');
  document.getElementById("cellCoords").innerText = "Ячейка: " + cellYStr + " " + cellXStr;
  
  // Точные координаты в метрах
  var meterX = Math.round(gameCoords.x);
  var meterY = Math.round(gameCoords.y);
  document.getElementById("meterCoords").innerText = "Метры: X=" + meterX + "  Y=" + meterY;
}

// Прикрепляем обработчик непосредственно к элементу карты (#map)
document.getElementById('map').addEventListener('mousemove', function(e) {
  // Преобразуем событие мыши в контейнерную точку
  var containerPoint = map.mouseEventToContainerPoint(e);
  // Получаем LatLng для этой точки
  var latlng = map.containerPointToLatLng(containerPoint);
  updateCoordToolbar(latlng);
});
