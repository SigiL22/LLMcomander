// config.js
var Config = (function(){
  // Значения по умолчанию
  var defaults = {
    // Параметры карты
    islandWidth: 15360,
    islandHeight: 15360,
    mapImageWidth: 32768,
    mapImageHeight: 32768,
	maxZoom: 9,            // Максимальный зум
    // Интервалы для сетки
    kmStep: 1000,   // километровая сетка (1000 м)
    hmStep: 100,    // сотометровая сетка (100 м)
    // Стили линий
    kmLineStyle: { color: "#ff0000", weight: 2, opacity: 0.80 },  // opacity в диапазоне 0..1
    hmLineStyle: { color: "#0000ff", weight: 1, opacity: 0.50 },
    // Настройки обычных надписей (например, подписей границ)
    labelStyle: { fontFamily: "sans-serif", fontSize: 14, color: "#000000", opacity: 0.80 },
    // Порог зума для отображения сотометровой сетки
    zoomThreshold: 4,
    // Настройки подписей в ячейках
    cellCoordStyle: { show: false, fontFamily: "sans-serif", fontSize: 12, color: "#000000", opacity: 0.80 },
    // Настройки для надписей, получаемых из базы (по типам)
    nameSettings: {
      "NameCityCapital": { displayName: "Столица", fontFamily: "Arial", fontSize: 16, color: "#FF0000", opacity: 1, minZoom: 4 },
      "NameCity":        { displayName: "Город",   fontFamily: "Verdana", fontSize: 12, color: "#0000FF", opacity: 0.80, minZoom: 5 },
      "NameVillage":     { displayName: "Деревня", fontFamily: "'Times New Roman'", fontSize: 14, color: "#00AA00", opacity: 0.90, minZoom: 6 },
      "Hill":            { displayName: "Холм",    fontFamily: "Arial", fontSize: 14, color: "#FFA500", opacity: 0.85, minZoom: 5 },
      "NameLocal":       { displayName: "Местность", fontFamily: "Courier New", fontSize: 12, color: "#800080", opacity: 0.80, minZoom: 6 },
      "NameMarine":      { displayName: "Вода",    fontFamily: "Georgia", fontSize: 12, color: "#0000FF", opacity: 0.80, minZoom: 5 },
	  "Height":          { displayName: "Высота",    fontFamily: "Arial", fontSize: 16, color: "#FF0000", opacity: 1, minZoom: 4 },
    }
  };

  // Объект текущих настроек
  var settings = {};

  // Загрузка настроек из localStorage, либо использование значений по умолчанию
  function load() {
    var stored = localStorage.getItem('mapSettings');
    if (stored) {
      try {
        settings = JSON.parse(stored);
      } catch(e) {
        console.error("Ошибка парсинга настроек, используем значения по умолчанию", e);
        settings = JSON.parse(JSON.stringify(defaults));
      }
    } else {
      settings = JSON.parse(JSON.stringify(defaults));
    }
    // Гарантируем, что все ключи из defaults присутствуют
    for (var key in defaults) {
      if (defaults.hasOwnProperty(key) && typeof settings[key] === 'undefined') {
        settings[key] = defaults[key];
      }
    }
    // Вычисляем производные параметры, например scaleFactor
    settings.scaleFactor = settings.mapImageWidth / settings.islandWidth;
  }

  // Сохранение настроек в localStorage
  function save() {
    localStorage.setItem('mapSettings', JSON.stringify(settings));
  }

  // Применение настроек: здесь можно обновлять производные параметры,
  // а также вызывать методы перерисовки слоёв, если они уже инициализированы.
  function apply() {
    settings.scaleFactor = settings.mapImageWidth / settings.islandWidth;
    if (window.gridLayer && typeof gridLayer._redraw === "function") {
      gridLayer._redraw();
    }
    if (window.namesLayer && typeof namesLayer._redraw === "function") {
      namesLayer._redraw();
    }
  }

  // Публичное API: методы для загрузки, сохранения, применения и доступа к настройкам.
  return {
    load: load,
    save: save,
    apply: apply,
    get: function() { return settings; },
    set: function(newSettings) { settings = newSettings; }
  };
})();
