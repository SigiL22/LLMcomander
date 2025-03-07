console.log("Инициализация приложения...");

// Загружаем конфигурацию из Config (файл config.js должен быть подключён раньше)
Config.load();
var conf = Config.get();

// Извлекаем параметры из конфигурации
var islandWidth = conf.islandWidth,
    islandHeight = conf.islandHeight,
    mapImageWidth = conf.mapImageWidth,
    mapImageHeight = conf.mapImageHeight,
    scaleFactor = conf.scaleFactor,  // вычисляется в Config.load()/apply()
    kmStep = conf.kmStep,
    hmStep = conf.hmStep;

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

// Применяем границы для первоначального масштабирования
map.fitBounds(bounds);

// Подключаем тайловый слой с вашего сервера
var tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
  noWrap: true,
  attribution: "Карта Chernarus",
  updateWhenIdle: true,
  tileBuffer: 2,
  maxNativeZoom: 7,
  maxZoom: 9,
  getTileUrl: function(coords) {
    if (coords.x < 0 || coords.y < 0) {
      return '/transparent.png';
    }
    return L.Util.template(this._url, L.extend({
      z: coords.z,
      x: coords.x,
      y: coords.y
    }, this.options));
  }
}).addTo(map);

tileLayer.on('loading', function() {
  console.log("Началась загрузка тайлов...");
});

// Создаем и добавляем пользовательские слои
var gridLayer = new GridLayer();
gridLayer.addTo(map);

var namesLayer = new NamesLayer();
namesLayer.addTo(map);

// Обновляем сетку при изменении зума, перемещении или изменении размера
map.on('zoomend moveend resize', function() {
  if (gridLayer && typeof gridLayer._redraw === "function") {
    gridLayer._redraw();
  }
});

// Применяем настройки из конфигурации (пересчитываем производные параметры и перерисовываем слои)
Config.apply();

console.log("Приложение инициализировано.");
