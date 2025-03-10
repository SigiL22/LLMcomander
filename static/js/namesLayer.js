// js/namesLayer.js

function gameToLatLng(X, Y, conf) {
  const px = X * (conf.mapImageWidth / conf.islandWidth);
  const py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
  return map.unproject([px, py], 7);
}

function updateNameSettingsFromNames(namesArray) {
  const conf = Config.get();
  const settings = conf.nameSettings || {};
  const defaultStyle = {
    displayName: "",
    fontFamily: "sans-serif",
    fontSize: 14,
    color: "#000000",
    opacity: 1,
    minZoom: 4
  };
  namesArray.forEach(item => {
    if (!settings.hasOwnProperty(item.type)) {
      settings[item.type] = { ...defaultStyle, displayName: item.type };
    }
  });
  conf.nameSettings = settings;
  Config.set(conf);
  Config.save();
}

var NamesLayer = L.Layer.extend({
  initialize: function() {
    this._namesGroup = L.featureGroup();
    this._names = [];
    this._stylesCache = {};
    this._renderScheduled = false;
    this._topStripeHeight = 35; // Высота верхней полосы окантовки
    this._leftStripeWidth = 40; // Ширина левой полосы окантовки
  },

  onAdd: function(map) {
    this._map = map;
    this._namesGroup.addTo(map);
    map.on('zoomend moveend resize', this._scheduleUpdate.bind(this));
    this._fetchNames();
  },

  onRemove: function(map) {
    map.removeLayer(this._namesGroup);
    map.off('zoomend moveend resize', this._scheduleUpdate.bind(this));
  },

  _scheduleUpdate: function() {
    if (!this._renderScheduled) {
      this._renderScheduled = true;
      requestAnimationFrame(() => {
        this._updateVisibility();
        this._renderScheduled = false;
      });
    }
  },

  _fetchNames: function() {
    fetch('/names')
      .then(response => response.json())
      .then(data => {
        this._names = data;
        updateNameSettingsFromNames(data);
        this._cacheStyles();
        this._createMarkers();
      })
      .catch(error => console.error("[NamesLayer] Ошибка при запросе /names:", error));
  },

  _cacheStyles: function() {
    const conf = Config.get();
    this._stylesCache = {};
    for (const type in conf.nameSettings) {
      if (conf.nameSettings.hasOwnProperty(type)) {
        const item = conf.nameSettings[type];
        this._stylesCache[type] = {
          font: `${item.fontSize}px ${item.fontFamily}`,
          color: item.color,
          opacity: item.opacity,
          minZoom: item.minZoom,
          html: `<div style="font:${item.fontSize}px ${item.fontFamily};color:${item.color};opacity:${item.opacity};display:flex;align-items:center;justify-content:center;">`
        };
      }
    }
  },

  _createMarkers: function() {
    const conf = Config.get();

    // Создаем маркеры только один раз
    if (this._namesGroup.getLayers().length === 0) {
      this._names.forEach(item => {
        const style = this._stylesCache[item.type];
        if (!style) return;

        const latlng = gameToLatLng(item.x, item.y, conf);
        const icon = L.divIcon({
          className: 'name-label',
          html: `${style.html}${item.name}</div>`,
          iconSize: [100, 30],
          iconAnchor: [50, 15]
        });

        const marker = L.marker(latlng, { icon: icon });
        marker.options.minZoom = style.minZoom;
        marker.options.data = { id: item.id, name: item.name, type: item.type, latlng: latlng };
        this._namesGroup.addLayer(marker);
      });
    }

    this._updateVisibility();
  },

  _updateVisibility: function() {
    const currentZoom = this._map.getZoom();
    const bounds = this._map.getBounds();
    const size = this._map.getSize();
    const topStripeY = this._topStripeHeight;
    const leftStripeX = this._leftStripeWidth;

    this._namesGroup.eachLayer(layer => {
      const latlng = layer.options.data.latlng;
      const containerPoint = this._map.latLngToContainerPoint(latlng);
      const isInTopStripe = containerPoint.y <= topStripeY;
      const isInLeftStripe = containerPoint.x <= leftStripeX;
      const isVisible = currentZoom >= layer.options.minZoom && 
                        bounds.contains(latlng) && 
                        !isInTopStripe && 
                        !isInLeftStripe;
      layer.setOpacity(isVisible ? 1 : 0);
    });
  },

  update: function() {
    this._namesGroup.clearLayers();
    this._fetchNames();
  },

  updateStyles: function() {
    this._cacheStyles();
    this._namesGroup.eachLayer(layer => {
      const style = this._stylesCache[layer.options.data.type];
      if (style) {
        layer.setIcon(L.divIcon({
          className: 'name-label',
          html: `${style.html}${layer.options.data.name}</div>`,
          iconSize: [100, 30],
          iconAnchor: [50, 15]
        }));
      }
    });
    this._updateVisibility();
  }
});

window.namesLayer = new NamesLayer();