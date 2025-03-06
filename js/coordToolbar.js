// js/coordToolbar.js

// Функция преобразования контейнерной точки в игровые координаты (в метрах)
function pixelToGame(point) {
  var gameX = point.x / scaleFactor;
  var gameY = islandHeight - (point.y / scaleFactor);
  return { x: gameX, y: gameY };
}

// Функция обновления тулбара координат
function updateCoordToolbar(e) {
  var containerPoint = map.latLngToContainerPoint(e.latlng);
  var gameCoords = pixelToGame(containerPoint);
  
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

// Прикрепляем обработчик к событию mousemove карты
map.on('mousemove', updateCoordToolbar);
