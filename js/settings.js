// settings.js

// Функция для сохранения настроек в localStorage
function saveSettings(settings) {
  localStorage.setItem('mapSettings', JSON.stringify(settings));
}

// Функция для загрузки настроек из localStorage
function loadSettings() {
  var stored = localStorage.getItem('mapSettings');
  if (stored) {
    return JSON.parse(stored);
  }
  // Значения по умолчанию:
  return {
    islandWidth: 15360,
    islandHeight: 15360,
    kmColor: "#ff0000",
    kmWeight: 2,
    kmOpacity: 0.8,
    hmColor: "#0000ff",
    hmWeight: 1,
    hmOpacity: 0.5,
    // Для подписей координат (обычных)
    labelFontFamily: "sans-serif",
    labelFontSize: "14px",
    labelColor: "#000000",
    labelOpacity: 0.8,
    zoomThreshold: 4,  // уровень зума, начиная с которого показываются стометровые линии
    // Новая настройка: вывод координат ячейки внутри каждой сотометровой ячейки
    showCellCoords: false,
    cellCoordFontFamily: "sans-serif",
    cellCoordFontSize: "12px",
    cellCoordColor: "#000000",
    cellCoordOpacity: 0.8
  };
}

// Функция, которая применяет настройки (обновляет глобальные переменные)
function applySettings(settings) {
  islandWidth = parseInt(settings.islandWidth);
  islandHeight = parseInt(settings.islandHeight);
  kmLineStyle.color = settings.kmColor;
  kmLineStyle.weight = parseFloat(settings.kmWeight);
  kmLineStyle.opacity = parseFloat(settings.kmOpacity);
  hmLineStyle.color = settings.hmColor;
  hmLineStyle.weight = parseFloat(settings.hmWeight);
  hmLineStyle.opacity = parseFloat(settings.hmOpacity);
  // Объединяем выбранный размер и семейство шрифта для обычных подписей
  labelFont = settings.labelFontSize + " " + settings.labelFontFamily;
  labelColor = settings.labelColor;
  labelOpacity = parseFloat(settings.labelOpacity);
  zoomThreshold = parseInt(settings.zoomThreshold);
  
  // Новые настройки для надписей внутри ячеек
  showCellCoords = settings.showCellCoords === "true" || settings.showCellCoords === true;
  cellCoordFont = settings.cellCoordFontSize + " " + settings.cellCoordFontFamily;
  cellCoordColor = settings.cellCoordColor;
  cellCoordOpacity = parseFloat(settings.cellCoordOpacity);
  
  // Обновляем отображение сетки, если она уже инициализирована
  if (typeof gridLayer !== "undefined" && gridLayer._redraw) {
    gridLayer._redraw();
  }
}

// Функция создания левого тулбара с кнопкой "Настройки карты"
function createSettingsToolbar() {
  var toolbar = document.createElement('div');
  toolbar.id = "settingsToolbar";
  toolbar.style.position = "absolute";
  toolbar.style.top = "10px";
  toolbar.style.left = "10px";
  toolbar.style.zIndex = "1000";
  
  var btn = document.createElement('button');
  btn.innerText = "Настройки карты";
  btn.onclick = function() {
    showSettingsModal();
  };
  toolbar.appendChild(btn);
  document.body.appendChild(toolbar);
}

// Функция создания и отображения модального окна настроек
function showSettingsModal() {
  // Создаем затемненный фон
  var overlay = document.createElement('div');
  overlay.id = "settingsOverlay";
  overlay.style.position = "fixed";
  overlay.style.top = "0";
  overlay.style.left = "0";
  overlay.style.width = "100%";
  overlay.style.height = "100%";
  overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
  overlay.style.zIndex = "1100";

  // Создаем само модальное окно
  var modal = document.createElement('div');
  modal.id = "settingsModal";
  modal.style.position = "fixed";
  modal.style.top = "50%";
  modal.style.left = "50%";
  modal.style.transform = "translate(-50%, -50%)";
  modal.style.backgroundColor = "white";
  modal.style.padding = "20px";
  modal.style.boxShadow = "0 0 10px rgba(0,0,0,0.5)";
  modal.style.zIndex = "1200";
  modal.style.maxWidth = "400px";
  modal.style.width = "90%";

  // Заголовок
  var title = document.createElement('h2');
  title.innerText = "Настройки карты";
  modal.appendChild(title);

  // Получаем текущие настройки
  var settings = loadSettings();

  // Форма настроек
  var formHTML = `
    <label>Размер острова (м):</label><br/>
    Ширина: <input type="number" id="islandWidth" value="${settings.islandWidth}" /><br/>
    Высота: <input type="number" id="islandHeight" value="${settings.islandHeight}" /><br/><br/>

    <label>Километровая сетка:</label><br/>
    Цвет: <input type="color" id="kmColor" value="${settings.kmColor}" /><br/>
    Толщина: <input type="number" id="kmWeight" value="${settings.kmWeight}" step="0.1"/><br/>
    Прозрачность (0-1): <input type="range" id="kmOpacity" min="0" max="1" step="0.05" value="${settings.kmOpacity}" /><br/><br/>

    <label>Стометровая сетка:</label><br/>
    Цвет: <input type="color" id="hmColor" value="${settings.hmColor}" /><br/>
    Толщина: <input type="number" id="hmWeight" value="${settings.hmWeight}" step="0.1"/><br/>
    Прозрачность (0-1): <input type="range" id="hmOpacity" min="0" max="1" step="0.05" value="${settings.hmOpacity}" /><br/><br/>

    <label>Подписи (обычные):</label><br/>
    Шрифт (семейство): 
    <select id="labelFontFamily">
      <option value="sans-serif" ${settings.labelFontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
      <option value="Arial" ${settings.labelFontFamily === "Arial" ? "selected" : ""}>Arial</option>
      <option value="Verdana" ${settings.labelFontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
      <option value="'Times New Roman'" ${settings.labelFontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
    </select><br/>
    Размер шрифта: <input type="text" id="labelFontSize" value="${settings.labelFontSize}" /><br/>
    Цвет: <input type="color" id="labelColor" value="${settings.labelColor}" /><br/>
    Прозрачность (0-1): <input type="range" id="labelOpacity" min="0" max="1" step="0.05" value="${settings.labelOpacity}" /><br/><br/>

    <label>Порог зума для стометровой сетки:</label><br/>
    <input type="range" id="zoomThreshold" min="2" max="9" step="1" value="${settings.zoomThreshold}" />
    <span id="zoomThresholdVal">${settings.zoomThreshold}</span><br/><br/>

    <label>Выводить координаты ячейки внутри сотометровых ячеек:</label>
    <input type="checkbox" id="showCellCoords" ${settings.showCellCoords ? "checked" : ""} /><br/><br/>

    <label>Подписи в ячейках:</label><br/>
    Шрифт (семейство): 
    <select id="cellCoordFontFamily">
      <option value="sans-serif" ${settings.cellCoordFontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
      <option value="Arial" ${settings.cellCoordFontFamily === "Arial" ? "selected" : ""}>Arial</option>
      <option value="Verdana" ${settings.cellCoordFontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
      <option value="'Times New Roman'" ${settings.cellCoordFontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
    </select><br/>
    Размер шрифта: <input type="text" id="cellCoordFontSize" value="${settings.cellCoordFontSize}" /><br/>
    Цвет: <input type="color" id="cellCoordColor" value="${settings.cellCoordColor}" /><br/>
    Прозрачность (0-1): <input type="range" id="cellCoordOpacity" min="0" max="1" step="0.05" value="${settings.cellCoordOpacity}" /><br/><br/>
  `;
  modal.innerHTML += formHTML;

  // Кнопки OK и Отмена
  var btnOk = document.createElement('button');
  btnOk.innerText = "OK";
  btnOk.style.marginRight = "10px";
  btnOk.onclick = function() {
    var newSettings = {
      islandWidth: document.getElementById('islandWidth').value,
      islandHeight: document.getElementById('islandHeight').value,
      kmColor: document.getElementById('kmColor').value,
      kmWeight: document.getElementById('kmWeight').value,
      kmOpacity: document.getElementById('kmOpacity').value,
      hmColor: document.getElementById('hmColor').value,
      hmWeight: document.getElementById('hmWeight').value,
      hmOpacity: document.getElementById('hmOpacity').value,
      labelFontFamily: document.getElementById('labelFontFamily').value,
      labelFontSize: document.getElementById('labelFontSize').value,
      labelColor: document.getElementById('labelColor').value,
      labelOpacity: document.getElementById('labelOpacity').value,
      zoomThreshold: document.getElementById('zoomThreshold').value,
      showCellCoords: document.getElementById('showCellCoords').checked,
      cellCoordFontFamily: document.getElementById('cellCoordFontFamily').value,
      cellCoordFontSize: document.getElementById('cellCoordFontSize').value,
      cellCoordColor: document.getElementById('cellCoordColor').value,
      cellCoordOpacity: document.getElementById('cellCoordOpacity').value
    };
    saveSettings(newSettings);
    applySettings(newSettings);
    document.body.removeChild(overlay);
  };

  var btnCancel = document.createElement('button');
  btnCancel.innerText = "Отмена";
  btnCancel.onclick = function() {
    document.body.removeChild(overlay);
  };

  var btnContainer = document.createElement('div');
  btnContainer.style.textAlign = "right";
  btnContainer.style.marginTop = "10px";
  btnContainer.appendChild(btnOk);
  btnContainer.appendChild(btnCancel);
  modal.appendChild(btnContainer);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  // Обновление значения слайдера зума при изменении
  document.getElementById('zoomThreshold').addEventListener('input', function(e) {
    document.getElementById('zoomThresholdVal').innerText = e.target.value;
  });
}

// Инициализация: создаем левый тулбар с кнопкой настроек
function createSettingsToolbar() {
  var toolbar = document.createElement('div');
  toolbar.id = "settingsToolbar";
  toolbar.style.position = "absolute";
  toolbar.style.top = "10px";
  toolbar.style.left = "10px";
  toolbar.style.zIndex = "1000";
  
  var btn = document.createElement('button');
  btn.innerText = "Настройки карты";
  btn.onclick = function() {
    showSettingsModal();
  };
  toolbar.appendChild(btn);
  document.body.appendChild(toolbar);
}

// Вызываем создание тулбара при загрузке
createSettingsToolbar();

// При загрузке страницы применяем сохраненные настройки
var initialSettings = loadSettings();
applySettings(initialSettings);
