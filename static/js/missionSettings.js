(function() {
  window.missionSettings = window.missionSettings || {
    updateInterval: 60,
    llmSide: null,
    preset: null,
    displaySide: null,
    llmModel: null,
    llmUpdateInterval: 30  // Новый параметр по умолчанию
  };
  let sidesData = {};
  let availableModels = [];

  function createMissionSettingsToolbar() {
    const toolbar = document.getElementById("settingsToolbar");
    const btn = document.createElement('button');
    btn.innerText = "Настройки миссии";
    btn.style.marginLeft = "10px";
    btn.onclick = showMissionSettingsModal;
    toolbar.appendChild(btn);
  }

  function loadSettings() {
    const stored = localStorage.getItem('missionSettings');
    if (stored) {
      try {
        window.missionSettings = JSON.parse(stored);
      } catch (e) {
        console.error("Ошибка парсинга настроек миссии, используются значения по умолчанию", e);
      }
    }
    fetch('/arma_data')
      .then(response => response.json())
      .then(data => {
        if (data.status === "success" && data.data.sides) {
          sidesData = data.data.sides;
          console.log("Данные о сторонах загружены:", sidesData);
        }
      })
      .catch(err => console.error("Ошибка загрузки данных о сторонах:", err));
    fetch('/llm_models')
      .then(response => response.json())
      .then(data => {
        if (data.status === "success") {
          availableModels = data.models;
          console.log("Доступные модели LLM:", availableModels);
        }
      })
      .catch(err => console.error("Ошибка запроса списка моделей LLM:", err));
  }

  function saveSettings() {
    localStorage.setItem('missionSettings', JSON.stringify(window.missionSettings));
  }

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

    // Интервал обновления игры
    const intervalLabel = document.createElement('label');
    intervalLabel.innerText = "Интервал обновления игры (сек):";
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
    modal.appendChild(intervalLabel);
    modal.appendChild(intervalInput);
    modal.appendChild(document.createElement('br'));

    // Интервал обновления LLM
    const llmIntervalLabel = document.createElement('label');
    llmIntervalLabel.innerText = "Интервал обновления LLM (сек):";
    llmIntervalLabel.style.width = "180px";
    llmIntervalLabel.style.display = "inline-block";
    llmIntervalLabel.style.marginBottom = "5px";
    llmIntervalLabel.style.verticalAlign = "middle";
    const llmIntervalInput = document.createElement('input');
    llmIntervalInput.type = "number";
    llmIntervalInput.id = "llmUpdateInterval";
    llmIntervalInput.min = "1";
    llmIntervalInput.max = "300";
    llmIntervalInput.value = window.missionSettings.llmUpdateInterval;
    llmIntervalInput.style.width = "80px";
    llmIntervalInput.style.marginBottom = "8px";
    modal.appendChild(llmIntervalLabel);
    modal.appendChild(llmIntervalInput);
    modal.appendChild(document.createElement('br'));

    // Сторона LLM
    const sideLabel = document.createElement('label');
    sideLabel.innerText = "Сторона LLM:";
    sideLabel.style.width = "180px";
    sideLabel.style.display = "inline-block";
    sideLabel.style.marginBottom = "5px";
    const sideSelect = document.createElement('select');
    sideSelect.id = "llmSide";
    sideSelect.style.width = "150px";
    sideSelect.style.marginBottom = "8px";
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

    // Отображаемая сторона
    const displaySideLabel = document.createElement('label');
    displaySideLabel.innerText = "Отображаемая сторона:";
    displaySideLabel.style.width = "180px";
    displaySideLabel.style.display = "inline-block";
    displaySideLabel.style.marginBottom = "5px";
    const displaySideSelect = document.createElement('select');
    displaySideSelect.id = "displaySide";
    displaySideSelect.style.width = "150px";
    displaySideSelect.style.marginBottom = "8px";
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

    // Предустановки
    const presetLabel = document.createElement('label');
    presetLabel.innerText = "Предустановка:";
    presetLabel.style.width = "180px";
    presetLabel.style.display = "inline-block";
    presetLabel.style.marginBottom = "5px";
    const presetSelect = document.createElement('select');
    presetSelect.id = "preset";
    presetSelect.style.width = "150px";
    presetSelect.style.marginBottom = "8px";
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

    // Модель LLM
    const modelLabel = document.createElement('label');
    modelLabel.innerText = "Модель LLM:";
    modelLabel.style.width = "180px";
    modelLabel.style.display = "inline-block";
    modelLabel.style.marginBottom = "5px";
    const modelSelect = document.createElement('select');
    modelSelect.id = "llmModel";
    modelSelect.style.width = "150px";
    modelSelect.style.marginBottom = "8px";
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
      } else {
        inputElement = document.createElement('select');
        inputElement.id = `${cmd.id}Select`;
        inputElement.style.width = "100px";
        inputElement.style.marginBottom = "8px";
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

    intervalInput.addEventListener('change', () => {
      window.missionSettings.updateInterval = Math.min(Math.max(parseInt(intervalInput.value) || 60, 1), 60);
      intervalInput.value = window.missionSettings.updateInterval;
    });
    llmIntervalInput.addEventListener('change', () => {
      window.missionSettings.llmUpdateInterval = Math.min(Math.max(parseInt(llmIntervalInput.value) || 30, 1), 300);
      llmIntervalInput.value = window.missionSettings.llmUpdateInterval;
    });
    sideSelect.addEventListener('change', () => {
      window.missionSettings.llmSide = sideSelect.value;
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
    if (group) message.group = group;
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

  function saveAndClose() {
    const updateInterval = Math.min(Math.max(parseInt(document.getElementById('updateInterval').value) || 60, 1), 60);
    const llmUpdateInterval = Math.min(Math.max(parseInt(document.getElementById('llmUpdateInterval').value) || 30, 1), 300);

    fetch('/set_update_interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: updateInterval })
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Интервал обновления игры установлен: ${result.interval} сек`);
        window.missionSettings.updateInterval = result.interval;
      } else {
        console.error("Ошибка установки интервала игры:", result);
      }
    })
    .catch(err => console.error("Ошибка установки интервала игры:", err));

    fetch('/set_llm_update_interval', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: llmUpdateInterval })
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log(`Интервал обновления LLM установлен: ${result.interval} сек`);
        window.missionSettings.llmUpdateInterval = result.interval;
      } else {
        console.error("Ошибка установки интервала LLM:", result);
      }
    })
    .catch(err => console.error("Ошибка установки интервала LLM:", err));

    saveSettings();
  }

  loadSettings();
  createMissionSettingsToolbar();
})();