// settings.js
(function(){
  // Создание тулбара для открытия настроек
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

  // Создание стилей для модального окна и формы настроек
  function createSettingsStyles() {
    var style = document.createElement('style');
    style.innerHTML = `
      /* Модальное окно: ограничиваем высоту и включаем прокрутку */
      #settingsModal {
        max-height: 80vh;
        overflow-y: auto;
        width: 600px;
      }
      /* Стили для label */
      #settingsModal label {
        display: inline-block;
        width: 140px;
        margin-bottom: 5px;
        vertical-align: middle;
      }
      /* Поля ввода и select */
      #settingsModal input[type="number"],
      #settingsModal input[type="color"],
      #settingsModal input[type="range"],
      #settingsModal select {
        margin-bottom: 8px;
        vertical-align: middle;
        width: 80px;
      }
      /* Для слайдеров – немного шире */
      #settingsModal input[type="range"] {
        width: 100px;
      }
      /* Блоки настроек для надписей из базы */
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
  }

  // Генерация HTML для настроек надписей из базы (nameSettings)
  function createNameSettingsHTML(conf) {
    var ns = conf.nameSettings;
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
            <label>Размер:</label>
            <input type="number" id="nameFontSize_${type}" value="${item.fontSize}" style="width:60px;" /><br/>
            <label>Цвет:</label>
            <input type="color" id="nameColor_${type}" value="${item.color}" /><br/>
            <label>Прозр.:</label>
            <input type="range" id="nameOpacity_${type}" min="0" max="100" step="1" value="${item.opacity * 100}" style="width:100px;" />
            <span id="nameOpacityVal_${type}" style="display:inline-block;width:30px;text-align:center;">${item.opacity * 100}</span><br/>
            <label>Мин. зум:</label>
            <input type="number" id="nameMinZoom_${type}" value="${item.minZoom}" style="width:60px;" />
          </div>
        `;
      }
    }
    return html;
  }

  // Отображение модального окна настроек
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

    // Создаем модальное окно
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

    // Заголовок
    var title = document.createElement('h2');
    title.innerText = "Настройки карты";
    modal.appendChild(title);

    // Получаем текущие настройки из Config
    var conf = Config.get();

    // Формируем HTML формы с использованием настроек из конфигурации
    var formHTML = `
      <label>Остров (ширина):</label>
      <input type="number" id="islandWidth" value="${conf.islandWidth}" style="width:80px;" /><br/>
      <label>Остров (высота):</label>
      <input type="number" id="islandHeight" value="${conf.islandHeight}" style="width:80px;" /><br/><br/>

      <label>Км-сетка, цвет:</label>
      <input type="color" id="kmColor" value="${conf.kmLineStyle.color}" /><br/>
      <label>Км-сетка, толщина:</label>
      <input type="number" step="0.1" id="kmWeight" value="${conf.kmLineStyle.weight}" style="width:60px;" /><br/>
      <label>Км-сетка, прозр.:</label>
      <input type="range" id="kmOpacity" min="0" max="100" step="5" value="${conf.kmLineStyle.opacity * 100}" style="width:100px;" />
      <span id="kmOpacityVal" style="display:inline-block;width:30px;text-align:center;">${conf.kmLineStyle.opacity * 100}</span><br/><br/>

      <label>Сот-сетка, цвет:</label>
      <input type="color" id="hmColor" value="${conf.hmLineStyle.color}" /><br/>
      <label>Сот-сетка, толщина:</label>
      <input type="number" step="0.1" id="hmWeight" value="${conf.hmLineStyle.weight}" style="width:60px;" /><br/>
      <label>Сот-сетка, прозр.:</label>
      <input type="range" id="hmOpacity" min="0" max="100" step="5" value="${conf.hmLineStyle.opacity * 100}" style="width:100px;" />
      <span id="hmOpacityVal" style="display:inline-block;width:30px;text-align:center;">${conf.hmLineStyle.opacity * 100}</span><br/><br/>

      <label>Подписи, шрифт:</label>
      <select id="labelFontFamily" style="width:120px;">
        <option value="sans-serif" ${conf.labelStyle.fontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
        <option value="Arial" ${conf.labelStyle.fontFamily === "Arial" ? "selected" : ""}>Arial</option>
        <option value="Verdana" ${conf.labelStyle.fontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
        <option value="'Times New Roman'" ${conf.labelStyle.fontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
        <option value="Georgia" ${conf.labelStyle.fontFamily === "Georgia" ? "selected" : ""}>Georgia</option>
        <option value="Courier New" ${conf.labelStyle.fontFamily === "Courier New" ? "selected" : ""}>Courier New</option>
      </select><br/>
      <label>Подписи, размер:</label>
      <input type="number" id="labelFontSize" value="${conf.labelStyle.fontSize}" style="width:60px;" /><br/>
      <label>Подписи, цвет:</label>
      <input type="color" id="labelColor" value="${conf.labelStyle.color}" /><br/>
      <label>Подписи, прозр.:</label>
      <input type="range" id="labelOpacity" min="0" max="100" step="5" value="${conf.labelStyle.opacity * 100}" style="width:100px;" />
      <span id="labelOpacityVal" style="display:inline-block;width:30px;text-align:center;">${conf.labelStyle.opacity * 100}</span><br/><br/>

      <label>Порог зума:</label>
      <input type="range" id="zoomThreshold" min="2" max="9" step="1" value="${conf.zoomThreshold}" style="width:100px;" />
      <span id="zoomThresholdVal" style="display:inline-block;width:30px;text-align:center;">${conf.zoomThreshold}</span><br/><br/>

      <label>Подписи в ячейках:</label>
      <input type="checkbox" id="showCellCoords" ${conf.cellCoordStyle.show ? "checked" : ""} /><br/><br/>

      <label>Ячейка, шрифт:</label>
      <select id="cellCoordFontFamily" style="width:120px;">
        <option value="sans-serif" ${conf.cellCoordStyle.fontFamily === "sans-serif" ? "selected" : ""}>Sans-serif</option>
        <option value="Arial" ${conf.cellCoordStyle.fontFamily === "Arial" ? "selected" : ""}>Arial</option>
        <option value="Verdana" ${conf.cellCoordStyle.fontFamily === "Verdana" ? "selected" : ""}>Verdana</option>
        <option value="'Times New Roman'" ${conf.cellCoordStyle.fontFamily === "'Times New Roman'" ? "selected" : ""}>Times New Roman</option>
        <option value="Georgia" ${conf.cellCoordStyle.fontFamily === "Georgia" ? "selected" : ""}>Georgia</option>
        <option value="Courier New" ${conf.cellCoordStyle.fontFamily === "Courier New" ? "selected" : ""}>Courier New</option>
      </select><br/>
      <label>Ячейка, размер:</label>
      <input type="number" id="cellCoordFontSize" value="${conf.cellCoordStyle.fontSize}" style="width:60px;" /><br/>
      <label>Ячейка, цвет:</label>
      <input type="color" id="cellCoordColor" value="${conf.cellCoordStyle.color}" /><br/>
      <label>Ячейка, прозр.:</label>
      <input type="range" id="cellCoordOpacity" min="0" max="100" step="5" value="${conf.cellCoordStyle.opacity * 100}" style="width:100px;" />
      <span id="cellCoordOpacityVal" style="display:inline-block;width:30px;text-align:center;">${conf.cellCoordStyle.opacity * 100}</span>
      <br/><br/>
    `;
    // Добавляем секцию настроек для надписей из базы
    formHTML += createNameSettingsHTML(conf);
    modal.innerHTML += formHTML;

    // Блок с кнопками OK/Отмена
    var btnContainer = document.createElement('div');
    btnContainer.classList.add('buttons-container');

    var btnOk = document.createElement('button');
    btnOk.innerText = "OK";
    btnOk.style.marginRight = "10px";
    btnOk.onclick = function() {
      // Собираем новые настройки из формы (редактируемые поля)
      var newSettings = {
        islandWidth: parseInt(document.getElementById('islandWidth').value, 10) || conf.islandWidth,
        islandHeight: parseInt(document.getElementById('islandHeight').value, 10) || conf.islandHeight,
        kmLineStyle: {
          color: document.getElementById('kmColor').value,
          weight: parseFloat(document.getElementById('kmWeight').value) || conf.kmLineStyle.weight,
          opacity: parseFloat(document.getElementById('kmOpacity').value) / 100 || conf.kmLineStyle.opacity
        },
        hmLineStyle: {
          color: document.getElementById('hmColor').value,
          weight: parseFloat(document.getElementById('hmWeight').value) || conf.hmLineStyle.weight,
          opacity: parseFloat(document.getElementById('hmOpacity').value) / 100 || conf.hmLineStyle.opacity
        },
        labelStyle: {
          fontFamily: document.getElementById('labelFontFamily').value,
          fontSize: parseInt(document.getElementById('labelFontSize').value, 10) || conf.labelStyle.fontSize,
          color: document.getElementById('labelColor').value,
          opacity: parseFloat(document.getElementById('labelOpacity').value) / 100 || conf.labelStyle.opacity
        },
        zoomThreshold: parseInt(document.getElementById('zoomThreshold').value, 10) || conf.zoomThreshold,
        cellCoordStyle: {
          show: document.getElementById('showCellCoords').checked,
          fontFamily: document.getElementById('cellCoordFontFamily').value,
          fontSize: parseInt(document.getElementById('cellCoordFontSize').value, 10) || conf.cellCoordStyle.fontSize,
          color: document.getElementById('cellCoordColor').value,
          opacity: parseFloat(document.getElementById('cellCoordOpacity').value) / 100 || conf.cellCoordStyle.opacity
        },
        nameSettings: {}
      };

      // Собираем настройки для каждого типа надписей из базы
      for (var t in conf.nameSettings) {
        if (conf.nameSettings.hasOwnProperty(t)) {
          newSettings.nameSettings[t] = {
            displayName: conf.nameSettings[t].displayName, // не редактируем
            fontFamily: document.getElementById('nameFontFamily_' + t).value,
            fontSize: parseInt(document.getElementById('nameFontSize_' + t).value, 10) || conf.nameSettings[t].fontSize,
            color: document.getElementById('nameColor_' + t).value,
            opacity: parseFloat(document.getElementById('nameOpacity_' + t).value) / 100 || conf.nameSettings[t].opacity,
            minZoom: parseInt(document.getElementById('nameMinZoom_' + t).value, 10) || conf.nameSettings[t].minZoom
          };
        }
      }

      // Получаем текущую конфигурацию и объединяем с новыми настройками,
      // чтобы сохранить неизменяемые поля (например, mapImageWidth, mapImageHeight, kmStep, hmStep)
      var current = Config.get();
      var merged = {
        mapImageWidth: current.mapImageWidth,
        mapImageHeight: current.mapImageHeight,
        kmStep: current.kmStep,
        hmStep: current.hmStep,
        islandWidth: newSettings.islandWidth,
        islandHeight: newSettings.islandHeight,
        kmLineStyle: newSettings.kmLineStyle,
        hmLineStyle: newSettings.hmLineStyle,
        labelStyle: newSettings.labelStyle,
        zoomThreshold: newSettings.zoomThreshold,
        cellCoordStyle: newSettings.cellCoordStyle,
        nameSettings: newSettings.nameSettings
      };

	Config.set(merged);
	Config.save();
	Config.apply();
	if (namesLayer && typeof namesLayer._createMarkers === "function") {
		namesLayer.updateStyles(); // Пересоздаем маркеры с новыми стилями
	}
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

    // Обработчики для слайдеров, чтобы обновлять отображаемое значение
    function connectSlider(rangeId, labelId) {
      var rng = document.getElementById(rangeId);
      if (rng) {
        rng.addEventListener('input', function(e) {
          document.getElementById(labelId).innerText = e.target.value;
        });
      }
    }
    connectSlider('kmOpacity', 'kmOpacityVal');
    connectSlider('hmOpacity', 'hmOpacityVal');
    connectSlider('labelOpacity', 'labelOpacityVal');
    connectSlider('cellCoordOpacity', 'cellCoordOpacityVal');
    var zoomRng = document.getElementById('zoomThreshold');
    if (zoomRng) {
      zoomRng.addEventListener('input', function(e) {
        document.getElementById('zoomThresholdVal').innerText = e.target.value;
      });
    }
    var confNow = Config.get();
    for (var t in confNow.nameSettings) {
      if (confNow.nameSettings.hasOwnProperty(t)) {
        connectSlider('nameOpacity_' + t, 'nameOpacityVal_' + t);
      }
    }
  }
  
	function createSettingsToolbar() {
		var toolbar = document.createElement('div');
		toolbar.id = "settingsToolbar";
		toolbar.style.position = "absolute";
		toolbar.style.top = "10px";
		toolbar.style.left = "320px";
		toolbar.style.zIndex = "1000";
		toolbar.style.display = "flex"; // Выравниваем кнопки горизонтально
		toolbar.style.gap = "10px"; // Отступ между кнопками

		var mapBtn = document.createElement('button');
		mapBtn.innerText = "Настройки карты";
		mapBtn.style.padding = "5px 10px"; // Улучшаем внешний вид кнопки
		mapBtn.onclick = function() {
			showSettingsModal();
		};
		toolbar.appendChild(mapBtn);

		document.body.appendChild(toolbar);

		// Динамически корректируем позицию после создания чата
		const chatContainer = document.getElementById('llmChatContainer');
		if (chatContainer) {
			const chatWidth = chatContainer.offsetWidth;
			toolbar.style.left = `${chatWidth + 20}px`; // 20px отступ от чата
		}
	}

  // Инициализация: создаем стили и тулбар настроек
  createSettingsStyles();
  createSettingsToolbar();
})();
