// js/gridLayer.js

// Размеры для фоновых полос подписей (окантовка)
var topStripeHeight = 25;   // высота верхней полосы для подписей оси X
var leftStripeWidth = 40;   // ширина левой полосы для подписей оси Y

// Функция преобразования hex-цвета в rgba-строку с указанной прозрачностью
function hexToRgba(hex, alpha) {
  hex = hex.replace('#', '');
  if (hex.length === 3) {
    hex = hex.split('').map(function(h) { return h + h; }).join('');
  }
  var r = parseInt(hex.substr(0,2), 16);
  var g = parseInt(hex.substr(2,2), 16);
  var b = parseInt(hex.substr(4,2), 16);
  return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
}

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
    // Используем глобальную переменную zoomThreshold для определения отображения стометровой сетки
    var drawHm = currentZoom >= zoomThreshold;

    // Вычисляем контейнерные координаты для углов острова (карты)
    var islandSw = gameToContainerPoint(0, 0);                // левый нижний угол
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
    var topStripeY = (visibleTop > 0) ? visibleTop - topStripeHeight : 0;
    var leftStripeX = (visibleLeft > 0) ? visibleLeft - leftStripeWidth : 0;
    ctx.fillRect(visibleLeft, topStripeY, visibleRight - visibleLeft, topStripeHeight);
    ctx.fillRect(leftStripeX, visibleTop, leftStripeWidth, visibleBottom - visibleTop);
    ctx.globalAlpha = 1.0;

    // Отрисовка километровых линий
    ctx.strokeStyle = kmLineStyle.color;
    ctx.lineWidth = kmLineStyle.weight;
    ctx.globalAlpha = kmLineStyle.opacity;
    // Вертикальные линии
    for (var x = 0; x <= islandWidth; x += kmStep) {
      var pt = gameToContainerPoint(x, islandHeight / 2);
      if (pt.x < visibleLeft || pt.x > visibleRight) continue;
      if (pt.x < visibleLeft + leftStripeWidth) continue;
      ctx.beginPath();
      ctx.moveTo(pt.x, visibleTop);
      ctx.lineTo(pt.x, visibleBottom);
      ctx.stroke();
    }
    // Горизонтальные линии
    for (var y = 0; y <= islandHeight; y += kmStep) {
      var pt = gameToContainerPoint(islandWidth / 2, y);
      if (pt.y < visibleTop || pt.y > visibleBottom) continue;
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
      ctx.globalAlpha = 1.0;
    }

    // Перед отрисовкой текста сбрасываем прозрачность на значение надписей (labelOpacity)
    ctx.globalAlpha = labelOpacity;
    ctx.fillStyle = labelColor;
    ctx.font = labelFont;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    
    if (!drawHm) {
      // Если стометровая сетка не видна, рисуем километровые подписи в окантовке
      for (var x = 0; x <= islandWidth; x += kmStep) {
        var midX = x + kmStep / 2;
        var pt = gameToContainerPoint(midX, islandHeight / 2);
        var labelY = topStripeY + topStripeHeight / 2;
        var cellIndex = Math.floor(x / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, pt.x, labelY);
      }
      for (var y = 0; y <= islandHeight; y += kmStep) {
        var midY = y + kmStep / 2;
        var pt = gameToContainerPoint(islandWidth / 2, midY);
        var labelX = leftStripeX + leftStripeWidth / 2;
        var cellIndex = Math.floor(y / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, labelX, pt.y);
      }
    } else {
      // Если стометровая сетка видна, рисуем подписи для каждой сотометровой ячейки
      for (var x = 0; x <= islandWidth; x += hmStep) {
        var midX = x + hmStep / 2;
        var pt = gameToContainerPoint(midX, islandHeight / 2);
        var labelY = topStripeY + topStripeHeight / 2;
        var cellIndex = Math.floor(x / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, pt.x, labelY);
      }
      for (var y = 0; y <= islandHeight; y += hmStep) {
        var midY = y + hmStep / 2;
        var pt = gameToContainerPoint(islandWidth / 2, midY);
        var labelX = leftStripeX + leftStripeWidth / 2;
        var cellIndex = Math.floor(y / hmStep);
        var label = cellIndex.toString().padStart(3, '0');
        ctx.fillText(label, labelX, pt.y);
      }
      
      // Отрисовка координат ячейки внутри каждой сотометровой ячейки, если включен чекбокс
      if (showCellCoords) {
        var baseCellSize = hmStep * scaleFactor;
        var pt0 = gameToContainerPoint(0, islandHeight / 2);
        var pt1 = gameToContainerPoint(hmStep, islandHeight / 2);
        var currentCellSize = pt1.x - pt0.x;
        var textScale = currentCellSize / baseCellSize;
        
        var baseFontSize = parseInt(cellCoordFontSize);
        var scaledFontSize = Math.round(baseFontSize * textScale) + "px";
        var finalCellFont = scaledFontSize + " " + cellCoordFontFamily;
        
        var finalCellColor = hexToRgba(cellCoordColor, cellCoordOpacity);
        
        ctx.fillStyle = finalCellColor;
        ctx.font = finalCellFont;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        
        var baseOffset = 24;
        var lineOffset = Math.round(baseOffset * textScale);
        
        for (var cx = 0; cx < islandWidth; cx += hmStep) {
          for (var cy = 0; cy < islandHeight; cy += hmStep) {
            var centerX = cx + hmStep / 2;
            var centerY = cy + hmStep / 2;
            var ptCenter = gameToContainerPoint(centerX, centerY);
            if (ptCenter.x < (leftStripeX + leftStripeWidth)) continue;
            if (ptCenter.y >= visibleTop && ptCenter.y <= visibleTop + topStripeHeight) continue;
            var cellXVal = Math.floor(centerX / 100);
            var cellYVal = Math.floor(centerY / 100);
            var cellXStr = cellXVal.toString().padStart(3, '0');
            var cellYStr = cellYVal.toString().padStart(3, '0');
            ctx.fillText(cellXStr, ptCenter.x, ptCenter.y - lineOffset);
            ctx.fillText(cellYStr, ptCenter.x, ptCenter.y + lineOffset);
          }
        }
      }
    }
    // После отрисовки текста можно восстановить globalAlpha, если требуется (например, 1.0)
    ctx.globalAlpha = 1.0;
    console.log("Отрисовка сетки завершена.");
  }
});
