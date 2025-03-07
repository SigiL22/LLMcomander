// js/namesLayer.js

// Функция перевода игровых координат в latlng (используется фиксированный зум 7)
function gameToLatLng(X, Y) {
  var conf = Config.get();
  var px = X * (conf.mapImageWidth / conf.islandWidth);
  var py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
  return map.unproject([px, py], 7);
}

// Функция для динамического обновления настроек типов на основе полученных надписей.
// Если для какого-то типа еще нет настроек, создаем их со значениями по умолчанию.
function updateNameSettingsFromNames(namesArray) {
  var conf = Config.get();
  var settings = conf.nameSettings || {};
  // Значения по умолчанию для нового типа
  var defaultStyle = {
    displayName: "", // запишем сам тип
    fontFamily: "sans-serif",
    fontSize: 14,
    color: "#000000",
    opacity: 1,
    minZoom: 4
  };
  namesArray.forEach(function(item) {
    if (!settings.hasOwnProperty(item.type)) {
      var newStyle = Object.assign({}, defaultStyle);
      newStyle.displayName = item.type;
      settings[item.type] = newStyle;
      console.log("Добавлен новый тип в конфигурацию:", item.type, newStyle);
    }
  });
  conf.nameSettings = settings;
  Config.set(conf);
  Config.save();
}

var NamesLayer = L.Layer.extend({
  onAdd: function(map) {
    this._map = map;
    
    // Создаем canvas для отрисовки надписей
    this._canvas = L.DomUtil.create('canvas', 'leaflet-names-layer');
    var size = map.getSize();
    this._canvas.width = size.x;
    this._canvas.height = size.y;
    var pane = map.getPane('overlayPane');
    pane.appendChild(this._canvas);
    this._canvas.style.zIndex = 1001;
    
    // Подписываемся на события карты для перерисовки
    map.on('moveend zoomend resize', this._reset, this);
    
    // Запрашиваем данные с сервера
    this._fetchNames();
  },
  onRemove: function(map) {
    map.getPane('overlayPane').removeChild(this._canvas);
    map.off('moveend zoomend resize', this._reset, this);
  },
  _reset: function() {
    var topLeft = this._map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(this._canvas, topLeft);
    this._redraw();
  },
  _fetchNames: function() {
    var self = this;
    fetch('/names')
      .then(response => response.json())
      .then(data => {
         self._names = data;
         // Динамически обновляем настройки типов надписей
         updateNameSettingsFromNames(data);
         self._redraw();
      })
      .catch(error => console.error("Ошибка при запросе /names:", error));
  },
  _redraw: function() {
    if (!this._names) return;
    
    var canvas = this._canvas;
    var ctx = canvas.getContext('2d');
    var size = this._map.getSize();
    ctx.clearRect(0, 0, size.x, size.y);
    
    var currentZoom = this._map.getZoom();
    
    // Получаем настройки для надписей из Config
    var conf = Config.get();
    var nameStyles = {};
    for (var t in conf.nameSettings) {
      if (conf.nameSettings.hasOwnProperty(t)) {
        var item = conf.nameSettings[t];
        nameStyles[t] = {
          font: item.fontSize + "px " + item.fontFamily,
          color: item.color,
          opacity: item.opacity, // значение в диапазоне 0..1
          minZoom: item.minZoom
        };
      }
    }
    
    // Отрисовка надписей для каждого элемента из базы
    this._names.forEach(function(item) {
      var style = nameStyles[item.type];
      if (!style) {
         console.log("Стиль не найден для типа:", item.type);
         return;
      }
      if (currentZoom < style.minZoom) return;
      
      // Вычисляем latlng через gameToLatLng, затем переводим в container point
      var latlng = gameToLatLng(item.x, item.y);
      var pt = map.latLngToContainerPoint(latlng);
      
      ctx.font = style.font;
      ctx.fillStyle = hexToRgba(style.color, style.opacity);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      
      ctx.fillText(item.name, pt.x, pt.y);
    });
    
    console.log("Отрисовка надписей завершена");
  }
});
