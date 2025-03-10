// js/gridLayer.js

const TOP_STRIPE_HEIGHT = 25;
const LEFT_STRIPE_WIDTH = 30;

function hexToRgba(hex, alpha) {
  hex = hex.replace('#', '');
  if (hex.length === 3) {
    hex = hex.split('').map(h => h + h).join('');
  }
  const r = parseInt(hex.substr(0, 2), 16);
  const g = parseInt(hex.substr(2, 2), 16);
  const b = parseInt(hex.substr(4, 2), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function gameToContainerPoint(X, Y, map, conf) {
  const px = X * (conf.mapImageWidth / conf.islandWidth);
  const py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
  const latlng = map.unproject([px, py], 7);
  return map.latLngToContainerPoint(latlng);
}

var GridLayer = L.Layer.extend({
  initialize: function() {
    this._cache = {
      kmLines: { vertical: [], horizontal: [] },
      hmLines: { vertical: [], horizontal: [] },
      axisLabels: [],
      cellLabels: []
    };
    this._needsFullRedraw = true;
    this._lastDrawHm = null;
    this._lastShowCellCoords = null;
    this._renderScheduled = false;
  },

  onAdd: function(map) {
    this._map = map;
    this._canvas = L.DomUtil.create('canvas', 'leaflet-grid-layer');
    const size = map.getSize();
    this._canvas.width = size.x;
    this._canvas.height = size.y;
    map.getPane('overlayPane').appendChild(this._canvas);
    
    map.on('moveend zoomend resize', this._reset.bind(this));
    this._reset();
  },

  onRemove: function(map) {
    map.getPane('overlayPane').removeChild(this._canvas);
    map.off('moveend zoomend resize', this._reset.bind(this));
  },

  _reset: function() {
    const topLeft = this._map.containerPointToLayerPoint([0, 0]);
    L.DomUtil.setPosition(this._canvas, topLeft);
    const size = this._map.getSize();
    if (this._canvas.width !== size.x || this._canvas.height !== size.y) {
      this._canvas.width = size.x;
      this._canvas.height = size.y;
      this._needsFullRedraw = true;
    }
    this._scheduleRedraw();
  },

  _scheduleRedraw: function() {
    if (!this._renderScheduled) {
      this._renderScheduled = true;
      requestAnimationFrame(() => {
        this._redraw();
        this._renderScheduled = false;
      });
    }
  },

  _cacheGridLines: function() {
    const conf = Config.get();
    const islandWidth = conf.islandWidth;
    const islandHeight = conf.islandHeight;
    const kmStep = conf.kmStep;
    const hmStep = conf.hmStep;

    this._cache.kmLines.vertical = Array.from({ length: Math.ceil(islandWidth / kmStep) + 1 }, (_, i) => i * kmStep);
    this._cache.kmLines.horizontal = Array.from({ length: Math.ceil(islandHeight / kmStep) + 1 }, (_, i) => i * kmStep);
    this._cache.hmLines.vertical = Array.from({ length: Math.ceil(islandWidth / hmStep) + 1 }, (_, i) => i * hmStep).filter(x => x % kmStep !== 0);
    this._cache.hmLines.horizontal = Array.from({ length: Math.ceil(islandHeight / hmStep) + 1 }, (_, i) => i * hmStep).filter(y => y % kmStep !== 0);
  },

  _cacheAxisLabels: function(drawHm) {
    const conf = Config.get();
    const islandWidth = conf.islandWidth;
    const islandHeight = conf.islandHeight;
    const kmStep = conf.kmStep;
    const hmStep = conf.hmStep;

    this._cache.axisLabels = [];
    const step = drawHm ? hmStep : kmStep;

    for (let x = 0; x <= islandWidth; x += step) {
      const midX = x + step / 2;
      const cellIndex = Math.floor(x / hmStep);
      const label = cellIndex.toString().padStart(3, '0');
      this._cache.axisLabels.push({ x: midX, y: islandHeight / 2, text: label, isX: true });
    }
    for (let y = 0; y <= islandHeight; y += step) {
      const midY = y + step / 2;
      const cellIndex = Math.floor(y / hmStep);
      const label = cellIndex.toString().padStart(3, '0');
      this._cache.axisLabels.push({ x: islandWidth / 2, y: midY, text: label, isX: false });
    }
  },

  _cacheCellLabels: function() {
    const conf = Config.get();
    const islandWidth = conf.islandWidth;
    const islandHeight = conf.islandHeight;
    const hmStep = conf.hmStep;

    this._cache.cellLabels = [];
    for (let cx = 0; cx < islandWidth; cx += hmStep) {
      for (let cy = 0; cy < islandHeight; cy += hmStep) {
        const centerX = cx + hmStep / 2;
        const centerY = cy + hmStep / 2;
        const cellXVal = Math.floor(centerX / 100);
        const cellYVal = Math.floor(centerY / 100);
        const cellXStr = cellXVal.toString().padStart(3, '0');
        const cellYStr = cellYVal.toString().padStart(3, '0');
        this._cache.cellLabels.push({ x: centerX, y: centerY, textX: cellXStr, textY: cellYStr });
      }
    }
  },

  _redraw: function() {
    const conf = Config.get();
    const ctx = this._canvas.getContext('2d');
    const size = this._map.getSize();
    ctx.clearRect(0, 0, size.x, size.y);

    const currentZoom = this._map.getZoom();
    const drawHm = currentZoom >= conf.zoomThreshold;
    const showCellCoords = conf.cellCoordStyle.show;

    // Обновляем кэш при необходимости
    if (this._needsFullRedraw) {
      this._cacheGridLines();
      this._cacheCellLabels(); // Кэшируем подписи ячеек один раз
      this._needsFullRedraw = false;
    }
    if (this._lastDrawHm !== drawHm) {
      this._cacheAxisLabels(drawHm);
      this._lastDrawHm = drawHm;
    }
    if (this._lastShowCellCoords !== showCellCoords) {
      this._lastShowCellCoords = showCellCoords;
    }

    const islandSw = gameToContainerPoint(0, 0, this._map, conf);
    const islandNe = gameToContainerPoint(conf.islandWidth, conf.islandHeight, this._map, conf);
    const visibleLeft = Math.max(islandSw.x, 0);
    const visibleTop = Math.max(islandNe.y, 0);
    const visibleRight = Math.min(islandNe.x, size.x);
    const visibleBottom = Math.min(islandSw.y, size.y);

    // Отрисовка фоновых полос
    ctx.fillStyle = "white";
    ctx.globalAlpha = 0.9;
    const topStripeY = visibleTop > 0 ? visibleTop - TOP_STRIPE_HEIGHT : 0;
    const leftStripeX = visibleLeft > 0 ? visibleLeft - LEFT_STRIPE_WIDTH : 0;
    ctx.fillRect(visibleLeft, topStripeY, visibleRight - visibleLeft, TOP_STRIPE_HEIGHT);
    ctx.fillRect(leftStripeX, visibleTop, LEFT_STRIPE_WIDTH, visibleBottom - visibleTop);
    ctx.globalAlpha = 1.0;

    // Километровые линии одним путем
    ctx.strokeStyle = conf.kmLineStyle.color;
    ctx.lineWidth = conf.kmLineStyle.weight;
    ctx.globalAlpha = conf.kmLineStyle.opacity;
    ctx.beginPath();
    this._cache.kmLines.vertical.forEach(x => {
      const pt = gameToContainerPoint(x, conf.islandHeight / 2, this._map, conf);
      if (pt.x >= visibleLeft + LEFT_STRIPE_WIDTH && pt.x <= visibleRight) {
        ctx.moveTo(pt.x, visibleTop);
        ctx.lineTo(pt.x, visibleBottom);
      }
    });
    this._cache.kmLines.horizontal.forEach(y => {
      const pt = gameToContainerPoint(conf.islandWidth / 2, y, this._map, conf);
      if (pt.y >= visibleTop + TOP_STRIPE_HEIGHT && pt.y <= visibleBottom) {
        ctx.moveTo(visibleLeft, pt.y);
        ctx.lineTo(visibleRight, pt.y);
      }
    });
    ctx.stroke();
    ctx.globalAlpha = 1.0;

    // Сотометровые линии одним путем
    if (drawHm) {
      ctx.strokeStyle = conf.hmLineStyle.color;
      ctx.lineWidth = conf.hmLineStyle.weight;
      ctx.globalAlpha = conf.hmLineStyle.opacity;
      ctx.beginPath();
      this._cache.hmLines.vertical.forEach(x => {
        const pt = gameToContainerPoint(x, conf.islandHeight / 2, this._map, conf);
        if (pt.x >= visibleLeft + LEFT_STRIPE_WIDTH && pt.x <= visibleRight) {
          ctx.moveTo(pt.x, visibleTop);
          ctx.lineTo(pt.x, visibleBottom);
        }
      });
      this._cache.hmLines.horizontal.forEach(y => {
        const pt = gameToContainerPoint(conf.islandWidth / 2, y, this._map, conf);
        if (pt.y >= visibleTop + TOP_STRIPE_HEIGHT && pt.y <= visibleBottom) {
          ctx.moveTo(visibleLeft, pt.y);
          ctx.lineTo(visibleRight, pt.y);
        }
      });
      ctx.stroke();
      ctx.globalAlpha = 1.0;
    }

    // Подписи по осям
    ctx.globalAlpha = conf.labelStyle.opacity;
    ctx.fillStyle = conf.labelStyle.color;
    ctx.font = `${conf.labelStyle.fontSize}px ${conf.labelStyle.fontFamily}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    this._cache.axisLabels.forEach(label => {
      const pt = gameToContainerPoint(label.x, label.y, this._map, conf);
      if (label.isX && pt.x >= visibleLeft + LEFT_STRIPE_WIDTH && pt.x <= visibleRight) {
        ctx.fillText(label.text, pt.x, topStripeY + TOP_STRIPE_HEIGHT / 2);
      } else if (!label.isX && pt.y >= visibleTop + TOP_STRIPE_HEIGHT && pt.y <= visibleBottom) {
        ctx.fillText(label.text, leftStripeX + LEFT_STRIPE_WIDTH / 2, pt.y);
      }
    });

    // Подписи ячеек
    if (drawHm && showCellCoords) {
      const baseCellSize = conf.hmStep * conf.scaleFactor;
      const pt0 = gameToContainerPoint(0, conf.islandHeight / 2, this._map, conf);
      const pt1 = gameToContainerPoint(conf.hmStep, conf.islandHeight / 2, this._map, conf);
      const currentCellSize = pt1.x - pt0.x;
      const textScale = currentCellSize / baseCellSize;
      const scaledFontSize = Math.round(parseInt(conf.cellCoordStyle.fontSize) * textScale);
      ctx.font = `${scaledFontSize}px ${conf.cellCoordStyle.fontFamily}`;
      ctx.fillStyle = hexToRgba(conf.cellCoordStyle.color, conf.cellCoordStyle.opacity);
      const lineOffset = Math.round(24 * textScale);

      this._cache.cellLabels.forEach(label => {
        const pt = gameToContainerPoint(label.x, label.y, this._map, conf);
        if (pt.x >= leftStripeX + LEFT_STRIPE_WIDTH && pt.x <= visibleRight &&
            pt.y >= visibleTop + TOP_STRIPE_HEIGHT && pt.y <= visibleBottom) {
          ctx.fillText(label.textX, pt.x, pt.y - lineOffset);
          ctx.fillText(label.textY, pt.x, pt.y + lineOffset);
        }
      });
    }

    ctx.globalAlpha = 1.0;
  }
});