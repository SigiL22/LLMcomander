// js/namesLayer.js

console.log("namesLayer.js загружен"); // Глобальный лог при загрузке файла

var NamesLayer = L.Layer.extend({
  onAdd: function(map) {
    console.log("NamesLayer.onAdd вызван");
    this._map = map;
    
    // Создаем canvas для отрисовки названий
    this._canvas = L.DomUtil.create('canvas', 'leaflet-names-layer');
    var size = map.getSize();
    console.log("Размер карты в onAdd:", size);
    this._canvas.width = size.x;
    this._canvas.height = size.y;
    var pane = map.getPane('overlayPane');
    pane.appendChild(this._canvas);
    this._canvas.style.zIndex = 1001;
    
    // Подписываемся на события карты
    map.on('moveend zoomend resize', this._reset, this);
    
    // Запрос данных с сервера
    console.log("Запрос данных с /names");
    this._fetchNames();
  },
  onRemove: function(map) {
    console.log("NamesLayer.onRemove вызван");
    map.getPane('overlayPane').removeChild(this._canvas);
    map.off('moveend zoomend resize', this._reset, this);
  },
  _reset: function() {
    console.log("NamesLayer._reset вызван");
    var topLeft = this._map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(this._canvas, topLeft);
    this._redraw();
  },
  _fetchNames: function() {
    var self = this;
    fetch('/names')
      .then(response => {
         console.log("Ответ от /names получен:", response);
         return response.json();
      })
      .then(data => {
         console.log("Данные с /names:", data);
         self._names = data;
         self._redraw();
      })
      .catch(error => console.error("Ошибка при запросе /names:", error));
  },
  _redraw: function() {
    console.log("NamesLayer._redraw вызван");
    console.log("Текущие данные _names:", this._names);
    if (!this._names) {
      console.log("Данных для отрисовки нет, выходим из _redraw");
      return;
    }
    var canvas = this._canvas;
    var ctx = canvas.getContext('2d');
    var size = this._map.getSize();
    ctx.clearRect(0, 0, size.x, size.y);
    
    var currentZoom = this._map.getZoom();
    console.log("Текущий зум:", currentZoom);
    
    if (typeof nameStyles === "undefined") {
      nameStyles = {
        "NameCityCapital": { font: "16px Arial", color: "#FF0000", opacity: 1, minZoom: 4 },
        "NameCity": { font: "12px Verdana", color: "#0000FF", opacity: 0.8, minZoom: 5 },
        "NameVillage": { font: "14px 'Times New Roman'", color: "#00AA00", opacity: 0.9, minZoom: 6 }
      };
      console.log("Используем значения по умолчанию для nameStyles:", nameStyles);
    }
    
    this._names.forEach(function(item) {
      console.log("Обработка элемента:", item);
      var style = nameStyles[item.type];
      if (!style) {
         console.log("Стиль не найден для типа:", item.type);
         return;
      }
      if (currentZoom < style.minZoom) {
         console.log("Зум меньше минимального для элемента типа", item.type);
         return;
      }
      
      var pt = gameToContainerPoint(item.x, item.y);
      console.log("Отрисовка элемента", item.name, "в точке:", pt);
      
      ctx.font = style.font;
      ctx.fillStyle = hexToRgba(style.color, style.opacity);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      
      ctx.fillText(item.name, pt.x, pt.y);
    });
    
    console.log("Отрисовка завершена");
  }
});
