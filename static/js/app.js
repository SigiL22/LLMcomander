console.log("Инициализация приложения...");

Config.load();
var conf = Config.get();

var islandWidth = conf.islandWidth,
    islandHeight = conf.islandHeight,
    mapImageWidth = conf.mapImageWidth,
    mapImageHeight = conf.mapImageHeight,
    scaleFactor = conf.scaleFactor,
    kmStep = conf.kmStep,
    hmStep = conf.hmStep;

var map = L.map('map', {
  crs: L.CRS.Simple,
  minZoom: 2,
  maxZoom: conf.maxZoom,
  updateWhenIdle: true,
  updateWhenZooming: false,
  zoomControl: false,
  doubleClickZoom: false // Отключаем зум по двойному клику глобально
});

var southWest = map.unproject([0, mapImageHeight], 7);
var northEast = map.unproject([mapImageWidth, 0], 7);
var bounds = new L.LatLngBounds(southWest, northEast);

map.fitBounds(bounds);

L.CustomTileLayer = L.TileLayer.extend({
  createTile: function(coords, done) {
    if (coords.x < 0 || coords.y < 0) {
      var tile = document.createElement('img');
      tile.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='; // Прозрачный 1x1 PNG
      tile.style.width = '256px';
      tile.style.height = '256px';
      setTimeout(function() {
        done(null, tile);
      }, 0);
      return tile;
    }
    return L.TileLayer.prototype.createTile.call(this, coords, done);
  }
});

// Регистрируем кастомный слой
L.customTileLayer = function(url, options) {
  return new L.CustomTileLayer(url, options);
};

var tileLayer = L.customTileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
  noWrap: true,
  attribution: "Карта Chernarus",
  updateWhenIdle: true,
  tileBuffer: 2,
  maxNativeZoom: 7,
  maxZoom: 9
}).addTo(map);

tileLayer.on('loading', function() {
  console.log("Началась загрузка тайлов...");
});

var gridLayer = new GridLayer();
gridLayer.addTo(map);

// Используем глобальную переменную namesLayer
namesLayer.addTo(map);
unitLayer.addTo(map); // Добавляем слой юнитов

map.on('zoomend moveend resize', function() {
  if (gridLayer && typeof gridLayer._redraw === "function") {
    gridLayer._redraw();
  }
});

Config.apply();

console.log("Приложение инициализировано.");