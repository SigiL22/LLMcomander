// js/namesLayer.js

var NamesLayer = L.Layer.extend({
  onAdd: function(map) {
    this._map = map;
    
    // Создаем canvas для отрисовки названий
    this._canvas = L.DomUtil.create('canvas', 'leaflet-names-layer');
    var size = map.getSize();
    this._canvas.width = size.x;
    this._canvas.height = size.y;
    var pane = map.getPane('overlayPane');
    pane.appendChild(this._canvas);
    this._canvas.style.zIndex = 1001;
    
    // Подписываемся на события карты
    map.on('moveend zoomend resize', this._reset, this);
    
    // Запрос данных с сервера
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
      .then(response => {
         return response.json();
      })
      .then(data => {
         self._names = data;
         self._redraw();
      })
      .catch(error => console.error("Ошибка при запросе /names:", error));
  },
  _redraw: function() {
    if (!this._names) {
      return;
    }
    var canvas = this._canvas;
    var ctx = canvas.getContext('2d');
    var size = this._map.getSize();
    ctx.clearRect(0, 0, size.x, size.y);
    
    var currentZoom = this._map.getZoom();
    
    if (typeof nameStyles === "undefined") {
      nameStyles = {
        "NameCityCapital": { font: "16px Arial", color: "#FF0000", opacity: 1, minZoom: 4 },
        "NameCity": { font: "12px Verdana", color: "#0000FF", opacity: 0.8, minZoom: 5 },
        "NameVillage": { font: "14px 'Times New Roman'", color: "#00AA00", opacity: 0.9, minZoom: 6 }
      };
      console.log("Используем значения по умолчанию для nameStyles:", nameStyles);
    }
    
    this._names.forEach(function(item) {
      var style = nameStyles[item.type];
      if (!style) {
         console.log("Стиль не найден для типа:", item.type);
         return;
      }
      if (currentZoom < style.minZoom) {
         return;
      }
      
      var pt = gameToContainerPoint(item.x, item.y);
      
      ctx.font = style.font;
      ctx.fillStyle = hexToRgba(style.color, style.opacity);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      
      ctx.fillText(item.name, pt.x, pt.y);
    });
    
    console.log("Отрисовка завершена");
  }
});
