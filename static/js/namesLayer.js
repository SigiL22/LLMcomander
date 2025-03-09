// js/namesLayer.js

// Функция перевода игровых координат в LatLng (используется фиксированный зум 7)
function gameToLatLng(X, Y) {
  var conf = Config.get();
  var px = X * (conf.mapImageWidth / conf.islandWidth);
  var py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
  return map.unproject([px, py], 7);
}

// Функция для динамического обновления настроек типов на основе полученных надписей
function updateNameSettingsFromNames(namesArray) {
  var conf = Config.get();
  var settings = conf.nameSettings || {};
  var defaultStyle = {
    displayName: "",
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
    }
  });
  conf.nameSettings = settings;
  Config.set(conf);
  Config.save();
}

var NamesLayer = L.Layer.extend({
  initialize: function() {
    this._namesGroup = L.featureGroup(); // Создаем группу для маркеров
    this._names = [];
  },

  onAdd: function(map) {
    this._map = map;
    this._namesGroup.addTo(map); // Добавляем группу маркеров на карту
    map.on('zoomend', this._updateVisibility, this); // Обновляем видимость при зуме
    map.on('moveend resize', this._updateMarkers, this); // Обновляем маркеры при перемещении и изменении размера
    this._fetchNames(); // Загружаем данные
  },

  onRemove: function(map) {
    map.removeLayer(this._namesGroup); // Удаляем группу маркеров
    map.off('zoomend', this._updateVisibility, this);
    map.off('moveend resize', this._updateMarkers, this);
  },

  _fetchNames: function() {
    var self = this;
    fetch('/names')
      .then(response => response.json())
      .then(data => {
        self._names = data;
        updateNameSettingsFromNames(data); // Обновляем настройки типов
        self._createMarkers(); // Создаем маркеры
      })
      .catch(error => console.error("[NamesLayer] Ошибка при запросе /names:", error));
  },

  _createMarkers: function() {
    this._namesGroup.clearLayers(); // Очищаем существующие маркеры
    var conf = Config.get();
    var nameStyles = {};

    // Формируем стили для каждого типа надписей
    for (var t in conf.nameSettings) {
      if (conf.nameSettings.hasOwnProperty(t)) {
        var item = conf.nameSettings[t];
        nameStyles[t] = {
          font: `${item.fontSize}px ${item.fontFamily}`,
          color: item.color,
          opacity: item.opacity,
          minZoom: item.minZoom
        };
      }
    }

    // Создаем маркеры для каждой надписи
    this._names.forEach(function(item) {
      var style = nameStyles[item.type];
      if (!style) {
        return;
      }

      var latlng = gameToLatLng(item.x, item.y);
      var containerPoint = map.latLngToContainerPoint(latlng); // Преобразуем в контейнерные координаты
      var topStripeHeight = 35; // Высота верхней окантовки из gridLayer.js
      var leftStripeWidth = 40; // Ширина левой окантовки из gridLayer.js

      // Проверяем, попадает ли маркер в область окантовки
      var isInTopStripe = containerPoint.y <= topStripeHeight;
      var isInLeftStripe = containerPoint.x <= leftStripeWidth;

      if (isInTopStripe || isInLeftStripe) {
        return; // Пропускаем маркер, если он в окантовке
      }

      var icon = L.divIcon({
        className: 'name-label',
        html: `<div style="font:${style.font};color:${style.color};opacity:${style.opacity};display:flex;align-items:center;justify-content:center;">${item.name}</div>`,
        iconSize: [100, 30], // Размер иконки
        iconAnchor: [50, 15] // Центр иконки
      });

      var marker = L.marker(latlng, { icon: icon });
      marker.options.minZoom = style.minZoom; // Сохраняем минимальный зум
      marker.options.data = { id: item.id, name: item.name, type: item.type }; // Сохраняем данные
      this._namesGroup.addLayer(marker);
    }, this);

    this._updateVisibility(); // Обновляем видимость сразу после создания
  },

  _updateMarkers: function() {
    this._createMarkers(); // Пересоздаём маркеры при изменении вида карты
  },

  _updateVisibility: function() {
    var currentZoom = this._map.getZoom();
    this._namesGroup.eachLayer(function(layer) {
      if (currentZoom >= layer.options.minZoom) {
        layer.setOpacity(1); // Показываем маркер
      } else {
        layer.setOpacity(0); // Скрываем маркер
      }
    });
  },

  // Метод для обновления слоя (например, после редактирования)
  update: function() {
    this._fetchNames();
  }
});

// Экспорт для доступа из других модулей (например, labelsEditor.js)
window.namesLayer = new NamesLayer();