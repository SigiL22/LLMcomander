// Функция преобразования LatLng в игровые координаты (в метрах)
function pixelToGame(latlng) {
  var conf = Config.get();
  var point7 = map.project(latlng, 7); // проецируем на уровень 7
  var gameX = point7.x / conf.scaleFactor;  // scaleFactor вычислен в Config
  var gameY = conf.islandHeight - (point7.y / conf.scaleFactor);
  return { x: gameX, y: gameY };
}

// Функция обновления панели координат
function updateCoordToolbar(latlng) {
  var gameCoords = pixelToGame(latlng);
  
  // Вычисляем номер ячейки (каждая ячейка = 100 м)
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

// Прикрепляем обработчик события мыши к карте для обновления панели координат
document.getElementById('map').addEventListener('mousemove', function(e) {
  var containerPoint = map.mouseEventToContainerPoint(e);
  var latlng = map.containerPointToLatLng(containerPoint);
  updateCoordToolbar(latlng);
});
