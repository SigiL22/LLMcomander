console.log("Инициализация приложения...");

// Глобальные переменные для системы координат и карты
// Размер острова (игровая область) в метрах
var islandWidth = 15360,
    islandHeight = 15360;
// Размер исходного изображения (в пикселях) – теперь 32768×32768
var mapImageWidth = 32768,
    mapImageHeight = 32768;
// Коэффициент преобразования: 1 метр = scaleFactor пикселей
var scaleFactor = mapImageWidth / islandWidth;  // ~2.1333

// Интервалы для сетки
var kmStep = 1000;  // километровая сетка (1000 м)
var hmStep = 100;   // стометровая сетка (100 м)

// Параметры стилей (по умолчанию)
var kmLineStyle = { color: "red", weight: 2, opacity: 0.8 };
var hmLineStyle = { color: "blue", weight: 1, opacity: 0.5 };
var labelFont = "14px sans-serif";
var labelColor = "black";
var labelOpacity = 0.8;

// Инициализация карты с использованием CRS.Simple
var map = L.map('map', {
  crs: L.CRS.Simple,
  minZoom: 2,
  maxZoom: 9,
  updateWhenIdle: true,
  updateWhenZooming: false,
  zoomControl: false
});

// Вычисляем границы карты через unproject для уровня зума 7
var southWest = map.unproject([0, mapImageHeight], 7);
var northEast = map.unproject([mapImageWidth, 0], 7);
var bounds = new L.LatLngBounds(southWest, northEast);

// Применяем границы для первоначального масштабирования (без ограничения перемещения)
map.fitBounds(bounds);

// Подключаем тайловый слой с вашего сервера
var tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
  noWrap: true,
  attribution: "Карта Chernarus",
  updateWhenIdle: true,
  tileBuffer: 2,
  maxNativeZoom: 7, // Тайлы предоставляются до зума 7
  maxZoom: 9        // Но пользователю доступны зумы до 9
}).addTo(map);

tileLayer.on('loading', function() {
  console.log("Началась загрузка тайлов...");
});
// Логи для tileload и tileerror оставлены минимальными

// Создаем и добавляем пользовательский слой сетки (реализован в js/gridLayer.js)
var gridLayer = new GridLayer();
gridLayer.addTo(map);

// Обновляем сетку при изменении зума или перемещении
map.on('zoomend moveend resize', function() {
  gridLayer._redraw();
});

console.log("Приложение инициализировано.");
