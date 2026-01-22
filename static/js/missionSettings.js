(function() {
  // Переменные для хранения данных миссии
  window.missionSettings = window.missionSettings || {
    updateInterval: 30, // По умолчанию 60 секунд
	rollCallInterval: 5, // <<< НОВОЕ ПОЛЕ, в минутах
	llmBatchInterval: 30, // Добавил дефолт, чтобы не было undefined
    llmSide: null,      // Сторона LLM
    preset: null,       // Предустановка (сторона или группа)
    displaySide: null,  // Отображаемая сторона
    llmModel: null,     // Выбранная модель LLM
	waypointSource: 'game', // <<< ДОБАВЛЕНО: 'game' или 'llm'
    updateSidesData: function(newArmaData) {
      if (newArmaData && newArmaData.sides) {
        // Простое сравнение, чтобы не перерисовывать лишний раз
        if (JSON.stringify(sidesData) !== JSON.stringify(newArmaData.sides)) {
         // console.log("MissionSettings: Получены обновленные данные о сторонах.");
          sidesData = newArmaData.sides;
        }
      }
    },
    handleStartMission: function() {
      console.log("MissionSettings: Получена команда start_mission. Сброс настроек.");
      this.llmSide = null;
      this.preset = null;
      // Сохраняем сброшенные настройки
      saveSettings();
      // Уведомляем сервер, что выбор стороны сброшен
      fetch('/set_llm_side', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ side: "" })
      });
    }
  };
  let sidesData = {};   // Данные о сторонах и группах
  let availableModels = []; // Список доступных моделей LLM


  // Создание тулбара для открытия настроек миссии
  function createMissionSettingsToolbar() {
    const toolbar = document.getElementById("settingsToolbar");
    const btn = document.createElement('button');
    btn.innerText = "Настройки миссии";
    btn.style.marginLeft = "10px";
    btn.onclick = showMissionSettingsModal;
    toolbar.appendChild(btn);
  }

  // Загрузка настроек из localStorage и данных о моделях LLM
  function loadSettings() {
    const stored = localStorage.getItem('missionSettings');
    if (stored) {
      try {
        // Загружаем только сохраненные настройки, не трогая функцию
        const parsedSettings = JSON.parse(stored);
        Object.assign(window.missionSettings, parsedSettings);
      } catch (e) {
        console.error("Ошибка парсинга настроек миссии, используются значения по умолчанию", e);
      }
    }
/*   // Загрузка данных о сторонах
    fetch('/arma_data')
      .then(response => response.json())
      .then(data => {
        if (data.status === "success" && data.data.sides) {
          sidesData = data.data.sides;
          console.log("Данные о сторонах загружены:", sidesData);
        }
      })
      .catch(err => console.error("Ошибка загрузки данных о сторонах:", err));
*/
    // Загрузка списка моделей LLM
    fetch('/llm_models')
      .then(response => response.json())
      .then(data => {
        if (data.status === "success") {
          availableModels = data.models;
          console.log("Доступные модели LLM:", availableModels);
        } else {
          console.error("Ошибка получения моделей LLM:", data);
        }
      })
      .catch(err => console.error("Ошибка запроса списка моделей LLM:", err));
  }

  // Сохранение настроек в localStorage
  function saveSettings() {
    localStorage.setItem('missionSettings', JSON.stringify(window.missionSettings));
  }

  // Отображение модального окна настроек миссии
  function showMissionSettingsModal() {
    const overlay = document.createElement('div');
    overlay.id = "missionSettingsOverlay";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    overlay.style.zIndex = "1100";

    const modal = document.createElement('div');
    modal.id = "missionSettingsModal";
    modal.style.position = "fixed";
    modal.style.top = "50%";
    modal.style.left = "50%";
    modal.style.transform = "translate(-50%, -50%)";
    modal.style.backgroundColor = "white";
    modal.style.padding = "20px";
    modal.style.boxShadow = "0 0 10px rgba(0,0,0,0.5)";
    modal.style.zIndex = "1200";
    modal.style.width = "600px";
    modal.style.maxHeight = "80vh";
    modal.style.overflowY = "auto";

    const title = document.createElement('h2');
    title.innerText = "Настройки миссии";
    modal.appendChild(title);

    // Интервал обновления
    const intervalLabel = document.createElement('label');
    intervalLabel.innerText = "Интервал обновления (сек):";
    intervalLabel.style.width = "180px";
    intervalLabel.style.display = "inline-block";
    intervalLabel.style.marginBottom = "5px";
    intervalLabel.style.verticalAlign = "middle";
    const intervalInput = document.createElement('input');
    intervalInput.type = "number";
    intervalInput.id = "updateInterval";
    intervalInput.min = "1";
    intervalInput.max = "60";
    intervalInput.value = window.missionSettings.updateInterval;
    intervalInput.style.width = "80px";
    intervalInput.style.marginBottom = "8px";
    intervalInput.style.verticalAlign = "middle";
    modal.appendChild(intervalLabel);
    modal.appendChild(intervalInput);
    modal.appendChild(document.createElement('br'));

    // --- НОВЫЙ БЛОК: ИНТЕРВАЛ ПЕРЕКЛИЧКИ ---
    const rollCallLabel = document.createElement('label');
    rollCallLabel.innerText = "Перекличка LLM (мин):";
    rollCallLabel.style.width = "180px";
    rollCallLabel.style.display = "inline-block";
    rollCallLabel.style.marginBottom = "5px";
    rollCallLabel.style.verticalAlign = "middle";
    const rollCallInput = document.createElement('input');
    rollCallInput.type = "number";
    rollCallInput.id = "rollCallInterval";
    rollCallInput.min = "1";
    rollCallInput.max = "60";
    rollCallInput.value = window.missionSettings.rollCallInterval;
    rollCallInput.style.width = "80px";
    rollCallInput.style.marginBottom = "8px";
    rollCallInput.style.verticalAlign = "middle";
    modal.appendChild(rollCallLabel);
    modal.appendChild(rollCallInput);
    modal.appendChild(document.createElement('br'));
	
    const batchLabel = document.createElement('label');
    batchLabel.innerText = "Сбор докладов LLM (сек):";
    batchLabel.style.width = "180px";
    batchLabel.style.display = "inline-block";
    batchLabel.style.marginBottom = "5px";
    batchLabel.style.verticalAlign = "middle";
    const batchInput = document.createElement('input');
    batchInput.type = "number";
    batchInput.id = "llmBatchInterval";
    batchInput.min = "1";
    batchInput.max = "60";
    batchInput.value = window.missionSettings.llmBatchInterval;
    batchInput.style.width = "80px";
    batchInput.style.marginBottom = "8px";
    batchInput.style.verticalAlign = "middle";
    modal.appendChild(batchLabel);
    modal.appendChild(batchInput);
    modal.appendChild(document.createElement('br'));

    // Сторона LLM
    const sideLabel = document.createElement('label');
    sideLabel.innerText = "Сторона LLM:";
    sideLabel.style.width = "180px";
    sideLabel.style.display = "inline-block";
    sideLabel.style.marginBottom = "5px";
    sideLabel.style.verticalAlign = "middle";
    const sideSelect = document.createElement('select');
    sideSelect.id = "llmSide";
    sideSelect.style.width = "150px";
    sideSelect.style.marginBottom = "8px";
    sideSelect.style.verticalAlign = "middle";
    const defaultSideOption = document.createElement('option');
    defaultSideOption.value = "";
    defaultSideOption.text = "Выберите сторону";
    sideSelect.appendChild(defaultSideOption);
    for (const side in sidesData) {
      const option = document.createElement('option');
      option.value = side;
      option.text = side;
      if (window.missionSettings.llmSide === side) option.selected = true;
      sideSelect.appendChild(option);
    }
    modal.appendChild(sideLabel);
    modal.appendChild(sideSelect);
    modal.appendChild(document.createElement('br'));
	
	// Спрашиваем у сервера, какая сторона сейчас активна
    fetch('/set_llm_side', { method: 'GET' })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'success' || data.status === 'ignored') {
          if (data.side) {
            console.log("Синхронизация с сервером: активная сторона LLM ->", data.side);
            
            // 1. Попытка прямой установки
            let targetSide = data.side;
            
            // 2. Если такой опции нет в списке, пробуем найти эквивалент
            // Сервер возвращает: EAST, WEST, GUER
            // В меню может быть: OPFOR, BLUFOR, Independent
            const sideMap = {
              "EAST": "OPFOR",
              "WEST": "BLUFOR",
              "GUER": "Independent",
              "RESISTANCE": "Independent",
              "CIV": "CIVILIAN"
            };

            // Проверяем, есть ли такая опция в селекте прямо сейчас
            let optionExists = false;
            for (let i = 0; i < sideSelect.options.length; i++) {
                if (sideSelect.options[i].value === targetSide) {
                    optionExists = true;
                    break;
                }
            }

            // Если опции "EAST" нет, пробуем конвертировать в "OPFOR"
            if (!optionExists && sideMap[targetSide]) {
                targetSide = sideMap[targetSide];
                console.log(`Конвертация стороны: ${data.side} -> ${targetSide}`);
            }

            // Устанавливаем значение
            window.missionSettings.llmSide = targetSide;
            sideSelect.value = targetSide;
          }
        }
      })
      .catch(err => console.error("Ошибка синхронизации стороны LLM:", err));

    // Отображаемая сторона
    const displaySideLabel = document.createElement('label');
    displaySideLabel.innerText = "Отображаемая сторона:";
    displaySideLabel.style.width = "180px";
    displaySideLabel.style.display = "inline-block";
    displaySideLabel.style.marginBottom = "5px";
    displaySideLabel.style.verticalAlign = "middle";
    const displaySideSelect = document.createElement('select');
    displaySideSelect.id = "displaySide";
    displaySideSelect.style.width = "150px";
    displaySideSelect.style.marginBottom = "8px";
    displaySideSelect.style.verticalAlign = "middle";
    const defaultDisplaySideOption = document.createElement('option');
    defaultDisplaySideOption.value = "";
    defaultDisplaySideOption.text = "Все стороны";
    displaySideSelect.appendChild(defaultDisplaySideOption);
    for (const side in sidesData) {
      const option = document.createElement('option');
      option.value = side;
      option.text = side;
      if (window.missionSettings.displaySide === side) option.selected = true;
      displaySideSelect.appendChild(option);
    }
    modal.appendChild(displaySideLabel);
    modal.appendChild(displaySideSelect);
    modal.appendChild(document.createElement('br'));

    // Предустановки (сторона или группа)
    const presetLabel = document.createElement('label');
    presetLabel.innerText = "Предустановка:";
    presetLabel.style.width = "180px";
    presetLabel.style.display = "inline-block";
    presetLabel.style.marginBottom = "5px";
    presetLabel.style.verticalAlign = "middle";
    const presetSelect = document.createElement('select');
    presetSelect.id = "preset";
    presetSelect.style.width = "150px";
    presetSelect.style.marginBottom = "8px";
    presetSelect.style.verticalAlign = "middle";
    const presetDefault = document.createElement('option');
    presetDefault.value = "";
    presetDefault.text = "Выберите цель";
    presetSelect.appendChild(presetDefault);
    for (const side in sidesData) {
      const sideOption = document.createElement('option');
      sideOption.value = side;
      sideOption.text = side;
      if (window.missionSettings.preset === side) sideOption.selected = true;
      presetSelect.appendChild(sideOption);
      sidesData[side].forEach(group => {
        const groupOption = document.createElement('option');
        groupOption.value = `${side}:${group.n}`;
        groupOption.text = `${side}: ${group.n}`;
        if (window.missionSettings.preset === `${side}:${group.n}`) groupOption.selected = true;
        presetSelect.appendChild(groupOption);
      });
    }
    modal.appendChild(presetLabel);
    modal.appendChild(presetSelect);
    modal.appendChild(document.createElement('br'));

    // Выбор модели LLM
    const modelLabel = document.createElement('label');
    modelLabel.innerText = "Модель LLM:";
    modelLabel.style.width = "180px";
    modelLabel.style.display = "inline-block";
    modelLabel.style.marginBottom = "5px";
    modelLabel.style.verticalAlign = "middle";
    const modelSelect = document.createElement('select');
    modelSelect.id = "llmModel";
    modelSelect.style.width = "150px";
    modelSelect.style.marginBottom = "8px";
    modelSelect.style.verticalAlign = "middle";
    const defaultModelOption = document.createElement('option');
    defaultModelOption.value = "";
    defaultModelOption.text = "Выберите модель";
    modelSelect.appendChild(defaultModelOption);
    availableModels.forEach(model => {
      const option = document.createElement('option');
      option.value = model;
      option.text = model;
      if (window.missionSettings.llmModel === model) option.selected = true;
      modelSelect.appendChild(option);
    });
    modal.appendChild(modelLabel);
    modal.appendChild(modelSelect);
    modal.appendChild(document.createElement('br'));
    modal.appendChild(document.createElement('br'));
	
    // --- НОВОЕ: Источник вэйпойнтов ---
    const wpSourceLabel = document.createElement('label');
    wpSourceLabel.innerText = "Источник вэйпойнтов:";
    wpSourceLabel.style.width = "180px";
    wpSourceLabel.style.display = "inline-block";
    wpSourceLabel.style.marginBottom = "5px";
    wpSourceLabel.style.verticalAlign = "middle";

    const wpSourceSelect = document.createElement('select');
    wpSourceSelect.id = "waypointSource";
    wpSourceSelect.style.width = "150px";
    wpSourceSelect.style.marginBottom = "8px";
    wpSourceSelect.style.verticalAlign = "middle";

    const optGame = document.createElement('option');
    optGame.value = "game";
    optGame.text = "Данные из игры (Точно)";
    if (window.missionSettings.waypointSource === "game") optGame.selected = true;

    const optLlm = document.createElement('option');
    optLlm.value = "llm";
    optLlm.text = "Приказы LLM (Быстро)";
    if (window.missionSettings.waypointSource === "llm") optLlm.selected = true;

    wpSourceSelect.appendChild(optGame);
    wpSourceSelect.appendChild(optLlm);

    modal.appendChild(wpSourceLabel);
    modal.appendChild(wpSourceSelect);
    modal.appendChild(document.createElement('br'));
    
    // Обработчик изменения
    wpSourceSelect.addEventListener('change', () => {
        window.missionSettings.waypointSource = wpSourceSelect.value;
        saveSettings();
        // Перерисовываем слой юнитов сразу, чтобы применить изменения
        if (window.unitLayer && window.unitLayer._lastData) {
            window.unitLayer.updateData(window.unitLayer._lastData, []);
        }
        console.log("Источник вэйпойнтов изменен на:", window.missionSettings.waypointSource);
    });
    // ----------------------------------

    // Команды поведения AI
    const commands = [
      { id: "set_behaviour", label: "Поведение", options: ["CARELESS", "SAFE", "AWARE", "COMBAT", "STEALTH"], arg: "mode" },
      { id: "set_combat_mode", label: "Боевой режим", options: ["BLUE", "GREEN", "YELLOW", "RED"], arg: "mode" },
      { id: "set_formation", label: "Строй", options: ["COLUMN", "STAG COLUMN", "WEDGE", "ECH LEFT", "ECH RIGHT", "VEE", "LINE", "FILE", "DIAMOND"], arg: "formation" },
      { id: "set_speed_mode", label: "Скорость", options: ["LIMITED", "NORMAL", "FULL"], arg: "speed" },
      { id: "enable_attack", label: "Открытие огня", options: ["true", "false"], arg: "enable" },
      { id: "set_form_dir", label: "Направление (град)", type: "number", min: 0, max: 359, arg: "direction" }
    ];

    commands.forEach(cmd => {
      const label = document.createElement('label');
      label.innerText = `${cmd.label}:`;
      label.style.width = "180px";
      label.style.display = "inline-block";
      label.style.marginBottom = "5px";
      label.style.verticalAlign = "middle";
      
      let inputElement;
      if (cmd.type === "number") {
        inputElement = document.createElement('input');
        inputElement.type = "number";
        inputElement.id = `${cmd.id}Input`;
        inputElement.min = cmd.min;
        inputElement.max = cmd.max;
        inputElement.value = "0";
        inputElement.style.width = "100px";
        inputElement.style.marginBottom = "8px";
        inputElement.style.verticalAlign = "middle";
      } else {
        inputElement = document.createElement('select');
        inputElement.id = `${cmd.id}Select`;
        inputElement.style.width = "100px";
        inputElement.style.marginBottom = "8px";
        inputElement.style.verticalAlign = "middle";
        cmd.options.forEach(opt => {
          const option = document.createElement('option');
          option.value = opt;
          option.text = opt;
          inputElement.appendChild(option);
        });
      }

      const applyBtn = document.createElement('button');
      applyBtn.innerText = "Применить";
      applyBtn.style.marginLeft = "10px";
      applyBtn.onclick = () => sendCommand(cmd.id, cmd.arg, inputElement.value);

      modal.appendChild(label);
      modal.appendChild(inputElement);
      modal.appendChild(applyBtn);
      modal.appendChild(document.createElement('br'));
    });

    // Кнопка закрытия
    const btnContainer = document.createElement('div');
    btnContainer.classList.add('buttons-container');
    const btnClose = document.createElement('button');
    btnClose.innerText = "Закрыть";
    btnClose.onclick = function() {
      saveAndClose();
      document.body.removeChild(overlay);
    };
    btnContainer.appendChild(btnClose);
    modal.appendChild(btnContainer);

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Обработчики событий
    intervalInput.addEventListener('change', () => {
      window.missionSettings.updateInterval = Math.min(Math.max(parseInt(intervalInput.value) || 60, 1), 60);
      intervalInput.value = window.missionSettings.updateInterval;
    });
    rollCallInput.addEventListener('change', () => {
      window.missionSettings.rollCallInterval = Math.max(parseInt(rollCallInput.value) || 5, 1);
      rollCallInput.value = window.missionSettings.rollCallInterval;
    });
    batchInput.addEventListener('change', () => {
      window.missionSettings.llmBatchInterval = Math.max(parseInt(batchInput.value) || 20, 1);
      batchInput.value = window.missionSettings.llmBatchInterval;
    });
    sideSelect.addEventListener('change', () => {
            const newSide = sideSelect.value;
      window.missionSettings.llmSide = newSide;
      
      // Отправляем выбранную сторону на сервер
      fetch('/set_llm_side', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ side: newSide })
      })
      .then(response => response.json())
      .then(result => {
        if (result.status === "success") {
          console.log(`Сервер подтвердил выбор стороны LLM: ${result.side || 'не выбрана'}`);
          if (newSide) {
            fetch('/initiate_llm_start', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ side: newSide })
            })
            .then(initResp => initResp.json())
            .then(initResult => {
              if (initResult.status === "success") {
                console.log("Сервер начал процесс инициализации LLM (промпт, маркеры, силы).");
              } else {
                console.error("Ошибка инициализации LLM на сервере:", initResult.message);
              }
            });
          }
        } else {
          console.error("Ошибка установки стороны LLM на сервере:", result);
        }
      })
      .catch(err => {
        console.error("Сетевая ошибка при установке стороны LLM:", err);
      });
    });
    displaySideSelect.addEventListener('change', () => {
      window.missionSettings.displaySide = displaySideSelect.value;
    });
    presetSelect.addEventListener('change', () => {
      window.missionSettings.preset = presetSelect.value;
    });
    modelSelect.addEventListener('change', () => {
      const newModel = modelSelect.value;
      if (newModel) {
        fetch('/set_llm_model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: newModel })
        })
        .then(response => response.json())
        .then(result => {
          if (result.status === "success") {
            window.missionSettings.llmModel = newModel;
            saveSettings();
            console.log(`Модель LLM изменена на ${newModel}`);
          } else {
            console.error("Ошибка смены модели:", result);
            modelSelect.value = window.missionSettings.llmModel || "";
          }
        })
        .catch(err => {
          console.error("Ошибка отправки запроса на смену модели:", err);
          modelSelect.value = window.missionSettings.llmModel || "";
        });
      }
    });
  }

  // Отправка команды в игру
  function sendCommand(commandId, argName, argValue) {
    const preset = window.missionSettings.preset;
    if (!preset) {
      alert("Выберите предустановку (сторона или группа)!");
      return;
    }
    const [side, group] = preset.split(':');
    const message = {
      command: commandId,
      side: side
    };
    if (group) {
      message.group = group;
    }
    message[argName] = (argName === "direction") ? parseInt(argValue) : argValue;
    fetch('/send_callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message)
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Команда ${commandId} успешно отправлена:`, message);
      } else {
        console.error("Ошибка отправки команды:", result);
      }
    })
    .catch(err => console.error("Ошибка отправки команды:", err));
  }

  // Сохранение настроек и обновление интервала
  function saveAndClose() {
    const interval = Math.min(Math.max(parseInt(document.getElementById('updateInterval').value) || 60, 1), 60);
    fetch('/set_update_interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: interval })
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Интервал обновления установлен: ${result.interval} сек`);
        window.missionSettings.updateInterval = result.interval;
        saveSettings();
      } else {
        console.error("Ошибка установки интервала:", result);
      }
    })
    .catch(err => console.error("Ошибка установки интервала:", err));
	
    const rollCallIntervalMins = Math.max(parseInt(document.getElementById('rollCallInterval').value) || 5, 1);
    fetch('/set_roll_call_interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: rollCallIntervalMins })
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Интервал переклички установлен: ${result.interval} мин`);
        window.missionSettings.rollCallInterval = result.interval;
        saveSettings(); // Сохраняем обе настройки
      } else {
        console.error("Ошибка установки интервала переклички:", result);
      }
    })
    .catch(err => console.error("Ошибка установки интервала переклички:", err));
	
    const llmBatchIntervalSecs = Math.max(parseInt(document.getElementById('llmBatchInterval').value) || 10, 1);
    fetch('/set_llm_batch_interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: llmBatchIntervalSecs })
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Интервал сбора докладов установлен: ${result.interval} сек`);
        window.missionSettings.llmBatchInterval = result.interval;
        saveSettings(); 
      } else {
        console.error("Ошибка установки интервала сбора докладов:", result);
      }
    })
    .catch(err => console.error("Ошибка установки интервала сбора докладов:", err));
  }

	
  // Инициализация
  loadSettings();
  createMissionSettingsToolbar();
})();