/*******************************************************
 * settings.js
 * Настройки карты и надписей (включая подписи из базы)
 *******************************************************/

// ---------------------------------------------------------------------------
// 1. Базовые проверки глобальных переменных, чтобы избежать ошибок "not defined"
// ---------------------------------------------------------------------------
if (typeof kmLineStyle === 'undefined') {
  var kmLineStyle = { color: "red", weight: 2, opacity: 0.8 };
}
if (typeof hmLineStyle === 'undefined') {
  var hmLineStyle = { color: "blue", weight: 1, opacity: 0.5 };
}
if (typeof labelFont === 'undefined') {
  var labelFont = "14px sans-serif";
}
if (typeof labelColor === 'undefined') {
  var labelColor = "black";
}
if (typeof labelOpacity === 'undefined') {
  var labelOpacity = 0.8;
}
if (typeof zoomThreshold === 'undefined') {
  var zoomThreshold = 4;
}
if (typeof showCellCoords === 'undefined') {
  var showCellCoords = false;
}
if (typeof cellCoordFontFamily === 'undefined') {
  var cellCoordFontFamily = "sans-serif";
}
if (typeof cellCoordFontSize === 'undefined') {
  var cellCoordFontSize = "12";
}
if (typeof cellCoordColor === 'undefined') {
  var cellCoordColor = "#000000";
}
if (typeof cellCoordOpacity === 'undefined') {
  var cellCoordOpacity = 0.8;
}

// ---------------------------------------------------------------------------
// 2. Значения по умолчанию для типов надписей (из базы). displayName — заголовок.
// ---------------------------------------------------------------------------
var defaultNameSettings = {
  "NameCityCapital": {
    displayName: "Столица",
    fontFamily: "Arial",
    fontSize: "16",   // без px
    color: "#FF0000",
    opacity: 100,     // 0..100
    minZoom: 4
  },
  "NameCity": {
    displayName: "Город",
    fontFamily: "Verdana",
    fontSize: "12",
    color: "#0000FF",
    opacity: 80,
    minZoom: 5
  },
  "NameVillage": {
    displayName: "Деревня",
    fontFamily: "'Times New Roman'",
    fontSize: "14",
    color: "#00AA00",
    opacity: 90,
    minZoom: 6
  },
  "Hill": {
    displayName: "Холм",
    fontFamily: "Arial",
    fontSize: "14",
    color: "#FFA500",
    opacity: 85,
    minZoom: 5
  },
  "NameLocal": {
    displayName: "Местность",
    fontFamily: "Courier New",
    fontSize: "12",
    color: "#800080",
    opacity: 80,
    minZoom: 6
  },
  "NameMarine": {
    displayName: "Вода",
    fontFamily: "Georgia",
    fontSize: "12",
    color: "#0000FF",
    opacity: 80,
    minZoom: 5
  }
};


// ---------------------------------------------------------------------------
// 3. Функции сохранения/загрузки настроек из localStorage
// ---------------------------------------------------------------------------
function saveSettings(settings) {
  localStorage.setItem('mapSettings', JSON.stringify(settings));
}

function loadSettings() {
  var stored = localStorage.getItem('mapSettings');
  var settings;
  if (stored) {
    settings = JSON.parse(stored);
  } else {
    // Значения по умолчанию, если в localStorage ничего нет
    settings = {
      islandWidth: 15360,
      islandHeight: 15360,
      kmColor: "#ff0000",
      kmWeight: 2,
      kmOpacity: 80,          // теперь 0..100
      hmColor: "#0000ff",
      hmWeight: 1,
      hmOpacity: 50,          // 0..100
      // Для обычных подписей
      labelFontFamily: "sans-serif",
      labelFontSize: "14",    // только цифры
      labelColor: "#000000",
      labelOpacity: 80,       // 0..100
      zoomThreshold: 4,       // уровень зума (2..9)
      // Для подписей в ячейках
      showCellCoords: false,
      cellCoordFontFamily: "sans-serif",
      cellCoordFontSize: "12",
      cellCoordColor: "#000000",
      cellCoordOpacity: 80    // 0..100
    };
  }
  // Если нет блока nameSettings, копируем из defaultNameSettings
  if (!settings.nameSettings) {
    settings.nameSettings = defaultNameSettings;
  }
  return settings;
}

// ---------------------------------------------------------------------------
// 4. Применение настроек: обновление глобальных переменных и объекта nameStyles
// ---------------------------------------------------------------------------
function applySettings(settings) {
  islandWidth = parseInt(settings.islandWidth);
  islandHeight = parseInt(settings.islandHeight);

  // kmLineStyle
  kmLineStyle.color = settings.kmColor;
  kmLineStyle.weight = parseFloat(settings.kmWeight);
  kmLineStyle.opacity = parseInt(settings.kmOpacity) / 100;  // переводим 0..100 -> 0..1

  // hmLineStyle
  hmLineStyle.color = settings.hmColor;
  hmLineStyle.weight = parseFloat(settings.hmWeight);
  hmLineStyle.opacity = parseInt(settings.hmOpacity) / 100;

  // Обычные подписи
  var lfSize = parseInt(settings.labelFontSize);
  labelFont = lfSize + "px " + settings.labelFontFamily;
  labelColor = settings.labelColor;
  labelOpacity = parseInt(settings.labelOpacity) / 100;
  zoomThreshold = parseInt(settings.zoomThreshold);

  // Подписи в ячейках
  showCellCoords = (settings.showCellCoords === "true" || settings.showCellCoords === true);
  var ccSize = parseInt(settings.cellCoordFontSize);
  cellCoordFontFamily = settings.cellCoordFontFamily;
  cellCoordFontSize = ccSize;
  cellCoordFont = ccSize + "px " + cellCoordFontFamily;
  cellCoordColor = settings.cellCoordColor;
  cellCoordOpacity = parseInt(settings.cellCoordOpacity) / 100;

  // Настройки для надписей из базы (nameStyles)
  // Здесь также переводим opacity (0..100 -> 0..1) и собираем font
  if (settings.nameSettings) {
    var result = {};
    for (var t in settings.nameSettings) {
      if (settings.nameSettings.hasOwnProperty(t)) {
        var item = settings.nameSettings[t];
        var sizeNum = parseInt(item.fontSize);
        var newObj = {
          font: sizeNum + "px " + item.fontFamily,
          color: item.color,
          opacity: parseInt(item.opacity) / 100,
          minZoom: parseInt(item.minZoom)
        };
        result[t] = newObj;
      }
    }
    nameStyles = result;
  }

  // Перерисовываем сетку, если инициализирована
  if (typeof gridLayer !== "undefined" && gridLayer._redraw) {
    gridLayer._redraw();
  }
}

// ---------------------------------------------------------------------------
// 5. Генерация HTML для настроек надписей из базы
//    - убираем "Отображаемое имя" и показываем лишь заголовок (displayName).
//    - шрифт (семейство) делаем select.
//    - размер шрифта делаем number.
//    - прозрачность 0..100 со слайдером и отобpажением значения.
// ---------------------------------------------------------------------------
function createNameSettingsHTML(settings) {
  var ns = settings.nameSettings;
  var html = '<h3>Настройки надписей из базы</h3>';
  for (var type in ns) {
    if (ns.hasOwnProperty(type)) {
      var item = ns[type];
      html += `
        <div class="name-setting">
          <strong>${item.displayName}</strong><br/>
          <label>Шрифт:</label>
          <select id="nameFontFamily_${type}" style="width:120px; margin-bottom:5px;">
            <option value="Arial" ${item.fontFamily === "Arial" ? "selected" : ""}>Arial</option>
            <option value="Verdana" ${item.fontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
            <option value="'Times New Roman'" ${item.fontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
            <option value="Georgia" ${item.fontFamily === "Georgia" ? "selected" : ""}>Georgia</option>
            <option value="Courier New" ${item.fontFamily === "Courier New" ? "selected" : ""}>Courier New</option>
            <option value="sans-serif" ${item.fontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
          </select><br/>

          <label>Размер шрифта:</label>
          <input type="number" id="nameFontSize_${type}" value="${parseInt(item.fontSize)}" style="width:60px;" /><br/>

          <label>Цвет:</label>
          <input type="color" id="nameColor_${type}" value="${item.color}" style="margin-bottom:5px;" /><br/>

          <label>Прозрачность:</label>
          <input type="range" id="nameOpacity_${type}" min="0" max="100" step="1" value="${item.opacity}" style="vertical-align: middle; width:100px;" />
          <span id="nameOpacityVal_${type}" style="display:inline-block;width:30px;text-align:center;">${item.opacity}</span><br/>

          <label>Минимальный зум:</label>
          <input type="number" id="nameMinZoom_${type}" value="${item.minZoom}" style="width:60px;" />
        </div>
      `;
    }
  }
  return html;
}

// ---------------------------------------------------------------------------
// 6. Создание тулбара и модального окна с настройками
// ---------------------------------------------------------------------------
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

// Создаём стили для модального окна и формы
(function createSettingsStyles() {
  const style = document.createElement('style');
  style.innerHTML = `
    /* Затемнённый фон уже задаём в JS, но при желании можно здесь */

    /* Модальное окно: ограничиваем высоту и включаем прокрутку */
    #settingsModal {
      max-height: 80vh;        /* ограничиваем по высоте */
      overflow-y: auto;        /* вертикальная прокрутка */
      width: 600px;            /* фиксированная ширина */
    }

    /* Общие стили для label */
    #settingsModal label {
      display: inline-block;
      width: 140px;            /* выравнивание подписей */
      margin-bottom: 5px;
      vertical-align: middle;
    }

    /* Отступы и выравнивание для инпутов */
    #settingsModal input[type="text"],
    #settingsModal input[type="number"],
    #settingsModal input[type="color"],
    #settingsModal input[type="range"],
    #settingsModal select {
      margin-bottom: 8px;
      vertical-align: middle;
    }

    /* Блоки настроек надписей */
    #settingsModal .name-setting {
      border: 1px solid #ccc;
      padding: 10px;
      margin-bottom: 10px;
    }
    #settingsModal .name-setting strong {
      display: block;
      margin-bottom: 5px;
      font-size: 16px;
    }

    /* Кнопки внизу */
    #settingsModal .buttons-container {
      text-align: right;
      margin-top: 10px;
    }
  `;
  document.head.appendChild(style);
})();

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
  // Остальные стили (max-height, width, overflow) заданы через CSS

  // Заголовок
  var title = document.createElement('h2');
  title.innerText = "Настройки карты";
  modal.appendChild(title);

  // Текущие настройки
  var settings = loadSettings();

  // Блок основной формы
  var formHTML = `
    <label>Размер острова (м):</label>
    <input type="number" id="islandWidth" value="${settings.islandWidth}" style="width:80px;" />
    <br/>

    <label></label>
    <input type="number" id="islandHeight" value="${settings.islandHeight}" style="width:80px;" />
    <br/><br/>

    <label>Километровая сетка:</label><br/>
    <label>Цвет:</label>
    <input type="color" id="kmColor" value="${settings.kmColor}" /><br/>
    <label>Толщина:</label>
    <input type="number" step="0.1" id="kmWeight" value="${settings.kmWeight}" style="width:60px;" /><br/>
    <label>Прозрачность:</label>
    <input type="range" id="kmOpacity" min="0" max="100" step="5" value="${settings.kmOpacity}" style="width:100px;" />
    <span id="kmOpacityVal" style="display:inline-block;width:30px;text-align:center;">${settings.kmOpacity}</span>
    <br/><br/>

    <label>Стометровая сетка:</label><br/>
    <label>Цвет:</label>
    <input type="color" id="hmColor" value="${settings.hmColor}" /><br/>
    <label>Толщина:</label>
    <input type="number" step="0.1" id="hmWeight" value="${settings.hmWeight}" style="width:60px;" /><br/>
    <label>Прозрачность:</label>
    <input type="range" id="hmOpacity" min="0" max="100" step="5" value="${settings.hmOpacity}" style="width:100px;" />
    <span id="hmOpacityVal" style="display:inline-block;width:30px;text-align:center;">${settings.hmOpacity}</span>
    <br/><br/>

    <label>Подписи (обычные):</label><br/>
    <label>Шрифт:</label>
    <select id="labelFontFamily" style="width:120px;">
      <option value="sans-serif" ${settings.labelFontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
      <option value="Arial" ${settings.labelFontFamily === "Arial" ? "selected" : ""}>Arial</option>
      <option value="Verdana" ${settings.labelFontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
      <option value="'Times New Roman'" ${settings.labelFontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
      <option value="Georgia" ${settings.labelFontFamily === "Georgia" ? "selected" : ""}>Georgia</option>
      <option value="Courier New" ${settings.labelFontFamily === "Courier New" ? "selected" : ""}>Courier New</option>
    </select><br/>
    <label>Размер шрифта:</label>
    <input type="number" id="labelFontSize" value="${parseInt(settings.labelFontSize)}" style="width:60px;" /><br/>
    <label>Цвет:</label>
    <input type="color" id="labelColor" value="${settings.labelColor}" /><br/>
    <label>Прозрачность:</label>
    <input type="range" id="labelOpacity" min="0" max="100" step="5" value="${settings.labelOpacity}" style="width:100px;" />
    <span id="labelOpacityVal" style="display:inline-block;width:30px;text-align:center;">${settings.labelOpacity}</span>
    <br/><br/>

    <label>Порог зума (для стометровой сетки):</label>
    <input type="range" id="zoomThreshold" min="2" max="9" step="1" value="${settings.zoomThreshold}" style="width:100px;" />
    <span id="zoomThresholdVal" style="display:inline-block;width:30px;text-align:center;">${settings.zoomThreshold}</span>
    <br/><br/>

    <label>Коорд. в ячейках:</label>
    <input type="checkbox" id="showCellCoords" ${settings.showCellCoords ? "checked" : ""} />
    <br/><br/>

    <label>Подписи в ячейках:</label><br/>
    <label>Шрифт:</label>
    <select id="cellCoordFontFamily" style="width:120px;">
      <option value="sans-serif" ${settings.cellCoordFontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
      <option value="Arial" ${settings.cellCoordFontFamily === "Arial" ? "selected" : ""}>Arial</option>
      <option value="Verdana" ${settings.cellCoordFontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
      <option value="'Times New Roman'" ${settings.cellCoordFontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
      <option value="Georgia" ${settings.cellCoordFontFamily === "Georgia" ? "selected" : ""}>Georgia</option>
      <option value="Courier New" ${settings.cellCoordFontFamily === "Courier New" ? "selected" : ""}>Courier New</option>
    </select><br/>
    <label>Размер шрифта:</label>
    <input type="number" id="cellCoordFontSize" value="${parseInt(settings.cellCoordFontSize)}" style="width:60px;" /><br/>
    <label>Цвет:</label>
    <input type="color" id="cellCoordColor" value="${settings.cellCoordColor}" /><br/>
    <label>Прозрачность:</label>
    <input type="range" id="cellCoordOpacity" min="0" max="100" step="5" value="${settings.cellCoordOpacity}" style="width:100px;" />
    <span id="cellCoordOpacityVal" style="display:inline-block;width:30px;text-align:center;">${settings.cellCoordOpacity}</span>
    <br/><br/>
  `;

  // Добавляем секцию настроек для надписей из базы
  formHTML += createNameSettingsHTML(settings);

  // Вставляем полученный HTML в модальное окно
  modal.innerHTML += formHTML;

  // Блок с кнопками OK/Отмена
  var btnContainer = document.createElement('div');
  btnContainer.classList.add('buttons-container');

  var btnOk = document.createElement('button');
  btnOk.innerText = "OK";
  btnOk.style.marginRight = "10px";
  btnOk.onclick = function() {
    // Собираем все значения
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
      cellCoordOpacity: document.getElementById('cellCoordOpacity').value,
      nameSettings: {}
    };

    // Сохраняем настройки надписей для каждого типа
    for (var t in settings.nameSettings) {
      if (settings.nameSettings.hasOwnProperty(t)) {
        newSettings.nameSettings[t] = {
          displayName: settings.nameSettings[t].displayName, // не редактируем
          fontFamily: document.getElementById('nameFontFamily_' + t).value,
          fontSize: document.getElementById('nameFontSize_' + t).value,
          color: document.getElementById('nameColor_' + t).value,
          opacity: document.getElementById('nameOpacity_' + t).value,
          minZoom: document.getElementById('nameMinZoom_' + t).value
        };
      }
    }

    // Сохраняем и применяем
    saveSettings(newSettings);
    applySettings(newSettings);
    document.body.removeChild(overlay);
  };

  var btnCancel = document.createElement('button');
  btnCancel.innerText = "Отмена";
  btnCancel.onclick = function() {
    document.body.removeChild(overlay);
  };

  btnContainer.appendChild(btnOk);
  btnContainer.appendChild(btnCancel);
  modal.appendChild(btnContainer);

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  // -------------------------------------------------------------------------
  // 7. Подключаем обработчики для слайдеров, чтобы выводить текущее значение
  // -------------------------------------------------------------------------
  function connectSlider(rangeId, labelId) {
    var rng = document.getElementById(rangeId);
    if (rng) {
      rng.addEventListener('input', function(e) {
        document.getElementById(labelId).innerText = e.target.value;
      });
    }
  }
  // Общие сетки
  connectSlider('kmOpacity', 'kmOpacityVal');
  connectSlider('hmOpacity', 'hmOpacityVal');
  connectSlider('labelOpacity', 'labelOpacityVal');
  connectSlider('cellCoordOpacity', 'cellCoordOpacityVal');
  // Порог зума
  var zoomRng = document.getElementById('zoomThreshold');
  if (zoomRng) {
    zoomRng.addEventListener('input', function(e) {
      document.getElementById('zoomThresholdVal').innerText = e.target.value;
    });
  }
  // Для каждого типа надписей из базы
  for (var t in settings.nameSettings) {
    if (settings.nameSettings.hasOwnProperty(t)) {
      connectSlider('nameOpacity_' + t, 'nameOpacityVal_' + t);
    }
  }
}

// ---------------------------------------------------------------------------
// 8. Инициализация: создаём тулбар и сразу применяем сохранённые настройки
// ---------------------------------------------------------------------------
createSettingsToolbar();
var initialSettings = loadSettings();
applySettings(initialSettings);