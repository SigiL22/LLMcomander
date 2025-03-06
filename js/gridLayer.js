// js/gridLayer.js

// Размеры для фоновых полос подписей (окантовка)
var topStripeHeight = 20;   // высота верхней полосы для подписей оси X
var leftStripeWidth = 30;   // ширина левой полосы для подписей оси Y

// Функция преобразования игровой координаты (в метрах) в контейнерную точку
// (0,0) – левый нижний угол игры, (islandWidth, islandHeight) – правый верхний угол.
function gameToContainerPoint(X, Y) {
  var px = X * (mapImageWidth / islandWidth);
  var py = mapImageHeight - (Y * (mapImageHeight / islandHeight));
  var latlng = map.unproject([px, py], 7);
  return map.latLngToContainerPoint(latlng);
}

var GridLayer = L.Layer.extend({
  onAdd: function(map) {
    this._map = map;
    this._canvas = L.DomUtil.create('canvas', 'leaflet-grid-layer');
    var size = map.getSize();
    this._canvas.width = size.x;
    this._canvas.height = size.y;
    var pane = map.getPane('overlayPane');
    pane.appendChild(this._canvas);
    map.on('moveend zoomend resize', this._reset, this);
    this._reset();
    console.log("Размер контейнера: " + size.x + " x " + size.y + " пикселей");
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
  _redraw: function() {
    console.log("Начинается отрисовка сетки...");
    var canvas = this._canvas;
    var ctx = canvas.getContext('2d');
    var size = this._map.getSize();
    ctx.clearRect(0, 0, size.x, size.y);

    var currentZoom = this._map.getZoom();
    console.log("Текущий зум: " + currentZoom);
    var drawHm = currentZoom >= 4; // стометровые линии рисуем при зуме >= 4

    // Вычисляем контейнерные координаты для углов острова (карты)
    var islandSw = gameToContainerPoint(0, 0);              // левый нижний угол
    var islandNe = gameToContainerPoint(islandWidth, islandHeight); // правый верхний угол

    // Определяем видимые границы острова относительно контейнера
    var visibleLeft = (islandSw.x >= 0) ? islandSw.x : 0;
    var visibleTop = (islandNe.y >= 0) ? islandNe.y : 0;
    var visibleRight = (islandNe.x <= size.x) ? islandNe.x : size.x;
    var visibleBottom = (islandSw.y <= size.y) ? islandSw.y : size.y;
    console.log("Видимые границы острова: левый: " + visibleLeft.toFixed(2) +
                ", верх: " + visibleTop.toFixed(2) +
                ", правый: " + visibleRight.toFixed(2) +
                ", низ: " + visibleBottom.toFixed(2));

    // Рисуем фоновые полосы (окантовку) для подписей
    ctx.fillStyle = "white";
    ctx.globalAlpha = 0.9;
    // Верхняя полоса: если верхний край острова виден, рисуем её за ним, иначе – по верху контейнера
    var topStripeY = (visibleTop > 0) ? visibleTop - topStripeHeight : 0;
    // Левая полоса: аналогично
    var leftStripeX = (visibleLeft > 0) ? visibleLeft - leftStripeWidth : 0;
    ctx.fillRect(visibleLeft, topStripeY, visibleRight - visibleLeft, topStripeHeight);
    ctx.fillRect(leftStripeX, visibleTop, leftStripeWidth, visibleBottom - visibleTop);
    ctx.globalAlpha = 1.0;

    // Отрисовка линий (границы отрисовываются только внутри видимой области острова)
    ctx.strokeStyle = kmLineStyle.color;
    ctx.lineWidth = kmLineStyle.weight;
    ctx.globalAlpha = kmLineStyle.opacity;
    // Километровые вертикальные линии
    for (var x = 0; x <= islandWidth; x += kmStep) {
      var pt = gameToContainerPoint(x, islandHeight / 2);
      if (pt.x < visibleLeft || pt.x > visibleRight) continue;
      // Рисуем линию только в области, не покрытой окантовкой (слева)
      if (pt.x < visibleLeft + leftStripeWidth) continue;
      ctx.beginPath();
      ctx.moveTo(pt.x, visibleTop);
      ctx.lineTo(pt.x, visibleBottom);
      ctx.stroke();
    }
    // Километровые горизонтальные линии
    for (var y = 0; y <= islandHeight; y += kmStep) {
      var pt = gameToContainerPoint(islandWidth / 2, y);
      if (pt.y < visibleTop || pt.y > visibleBottom) continue;
      // Рисуем линию, если она не попадает в верхнюю окантовку
      if (pt.y >= visibleTop && pt.y <= visibleTop + topStripeHeight) continue;
      ctx.beginPath();
      ctx.moveTo(visibleLeft, pt.y);
      ctx.lineTo(visibleRight, pt.y);
      ctx.stroke();
    }
    ctx.globalAlpha = 1.0;

    if (drawHm) {
      ctx.strokeStyle = hmLineStyle.color;
      ctx.lineWidth = hmLineStyle.weight;
      ctx.globalAlpha = hmLineStyle.opacity;
      // Стометровые вертикальные линии
      for (var x = 0; x <= islandWidth; x += hmStep) {
        if (x % kmStep === 0) continue;
        var pt = gameToContainerPoint(x, islandHeight / 2);
        if (pt.x < visibleLeft || pt.x > visibleRight) continue;
        if (pt.x < visibleLeft + leftStripeWidth) continue;
        ctx.beginPath();
        ctx.moveTo(pt.x, visibleTop);
        ctx.lineTo(pt.x, visibleBottom);
        ctx.stroke();
      }
      // Стометровые горизонтальные линии
      for (var y = 0; y <= islandHeight; y += hmStep) {
        if (y % kmStep === 0) continue;
        var pt = gameToContainerPoint(islandWidth / 2, y);
        if (pt.y < visibleTop || pt.y > visibleBottom) continue;
        if (pt.y >= visibleTop && pt.y <= visibleTop + topStripeHeight) continue;
        ctx.beginPath();
        ctx.moveTo(visibleLeft, pt.y);
        ctx.lineTo(visibleRight, pt.y);
        ctx.stroke();
      }
    }

    // Отрисовка подписей
    ctx.fillStyle = labelColor;
    ctx.font = labelFont;
    
    // Если стометровая сетка не видна (зум < 4): отрисовываем километровые подписи
    if (!drawHm) {
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (var x = 0; x <= islandWidth; x += kmStep) {
        var midX = x + kmStep / 2;
        var pt = gameToContainerPoint(midX, islandHeight / 2);
        var labelY = topStripeY + topStripeHeight / 2;
        var cellIndex = Math.floor(x / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, pt.x, labelY);
      }
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (var y = 0; y <= islandHeight; y += kmStep) {
        var midY = y + kmStep / 2;
        var pt = gameToContainerPoint(islandWidth / 2, midY);
        var labelX = leftStripeX + leftStripeWidth / 2;
        var cellIndex = Math.floor(y / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, labelX, pt.y);
      }
    } else {
      // Если стометровая сетка видна (зум >= 4), отрисовываем подписи для каждой сотометровой ячейки
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (var x = 0; x <= islandWidth; x += hmStep) {
        var midX = x + hmStep / 2;
        var pt = gameToContainerPoint(midX, islandHeight / 2);
        var labelY = topStripeY + topStripeHeight / 2;
        var cellIndex = Math.floor(x / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, pt.x, labelY);
      }
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (var y = 0; y <= islandHeight; y += hmStep) {
        var midY = y + hmStep / 2;
        var pt = gameToContainerPoint(islandWidth / 2, midY);
        var labelX = leftStripeX + leftStripeWidth / 2;
        var cellIndex = Math.floor(y / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, labelX, pt.y);
      }
    }
    console.log("Отрисовка сетки завершена.");
  }
});
