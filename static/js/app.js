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

var gridLayer = new GridLayer();
gridLayer.addTo(map);

// Используем глобальную переменную namesLayer
namesLayer.addTo(map);

map.on('zoomend moveend resize', function() {
  if (gridLayer && typeof gridLayer._redraw === "function") {
    gridLayer._redraw();
  }
});

Config.apply();

console.log("Приложение инициализировано.");