// js/waypointEditor.js

function pixelToGame(latlng) {
  var conf = Config.get();
  var point7 = map.project(latlng, 7); // Проецируем на уровень 7
  var gameX = point7.x / conf.scaleFactor;  // scaleFactor = mapImageWidth / islandWidth
  var gameY = conf.islandHeight - (point7.y / conf.scaleFactor);
  return { x: gameX, y: gameY };
}

(function() {
  let selectedGroup = null;
  let blinkInterval = null;

  // Создание кнопки "Добавить вэйпойнт"
  function createWaypointButton() {
    const toolbar = document.getElementById("settingsToolbar");
    const btn = document.createElement('button');
    btn.id = "addWaypointBtn";
    btn.innerText = "Добавить вэйпойнт";
    btn.style.marginLeft = "10px";
    btn.onclick = toggleWaypointMode;
    toolbar.appendChild(btn);
  }

  // Переключение режима создания вэйпойнта
  function toggleWaypointMode() {
    unitLayer.waypointMode = !unitLayer.waypointMode;
    const btn = document.getElementById("addWaypointBtn");
    if (unitLayer.waypointMode) {
      btn.style.backgroundColor = "#aaf";
      enableWaypointMode();
    } else {
      btn.style.backgroundColor = "";
      disableWaypointMode();
    }
  }

  // Активация режима создания вэйпойнта
  function enableWaypointMode() {
    unitLayer.waypointMode = true;
    unitLayer._groupLayer.eachLayer(marker => {
      marker.on('click', onGroupClick);
    });
    map.on('dblclick', onMapDoubleClick);
    // Добавляем обработчик двойного клика для редактирования вэйпойнтов
    unitLayer._waypointLayer.eachLayer(marker => {
      marker.on('dblclick', onWaypointDoubleClick);
    });
  }

  // Деактивация режима создания вэйпойнта
  function disableWaypointMode() {
    unitLayer.waypointMode = false;
    unitLayer._groupLayer.eachLayer(marker => {
      marker.off('click', onGroupClick);
      marker.setOpacity(1);
      delete marker._currentOpacity;
    });
    map.off('dblclick', onMapDoubleClick);
    unitLayer._waypointLayer.eachLayer(marker => {
      marker.off('dblclick', onWaypointDoubleClick);
    });
    if (blinkInterval) {
      clearInterval(blinkInterval);
      blinkInterval = null;
      if (selectedGroup) selectedGroup.marker.setOpacity(1);
    }
    selectedGroup = null;
  }

  // Обработка клика по группе или технике
  function onGroupClick(e) {
    console.log("Клик по маркеру:", e.target.options.data);
    if (!unitLayer.waypointMode) return;
    if (selectedGroup) {
      clearInterval(blinkInterval);
      selectedGroup.marker.setOpacity(1);
      delete selectedGroup.marker._currentOpacity;
    }
    selectedGroup = {
      marker: e.target,
      side: e.target.options.data.side,
      group: e.target.options.data.group
    };
    e.target._currentOpacity = 1;
    blinkInterval = setInterval(() => {
      const currentOpacity = e.target._currentOpacity || 1;
      const newOpacity = currentOpacity === 1 ? 0.3 : 1;
      e.target.setOpacity(newOpacity);
      e.target._currentOpacity = newOpacity;
    }, 500);
    console.log("Выбрана группа:", selectedGroup);
  }

  // Обработка двойного клика по карте
  function onMapDoubleClick(e) {
    if (!unitLayer.waypointMode || !selectedGroup) return;
    L.DomEvent.stop(e);
    showWaypointPopup(e.latlng, null);
  }

  // Обработка двойного клика по вэйпойнту
  function onWaypointDoubleClick(e) {
    if (!unitLayer.waypointMode) return;
    L.DomEvent.stop(e);
    const waypointData = e.target.options.data;
    showWaypointPopup(e.target.getLatLng(), waypointData);
  }

  // Отображение модального окна для создания или редактирования вэйпойнта
  function showWaypointPopup(latlng, waypointData) {
    const overlay = document.createElement('div');
    overlay.id = "waypointOverlay";
    overlay.style.position = "fixed";
    overlay.style.top = "0";
    overlay.style.left = "0";
    overlay.style.width = "100%";
    overlay.style.height = "100%";
    overlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    overlay.style.zIndex = "1100";

    const modal = document.createElement('div');
    modal.id = "waypointModal";
    modal.style.position = "fixed";
    modal.style.top = "50%";
    modal.style.left = "50%";
    modal.style.transform = "translate(-50%, -50%)";
    modal.style.backgroundColor = "white";
    modal.style.padding = "20px";
    modal.style.boxShadow = "0 0 10px rgba(0,0,0,0.5)";
    modal.style.zIndex = "1200";
    modal.style.width = "400px";
    modal.style.maxHeight = "80vh";
    modal.style.overflowY = "auto";

    const title = document.createElement('h2');
    title.innerText = waypointData ? "Редактировать маршрутную точку" : "Создание маршрутной точки";
    modal.appendChild(title);

    const params = [
      { id: "type", label: "Тип", options: [
        "MOVE", "DESTROY", "GETIN", "SAD", "JOIN", "LEADER", "GETOUT", "CYCLE", "LOAD", 
        "UNLOAD", "TR UNLOAD", "HOLD", "SENTRY", "GUARD", "TALK", "SCRIPTED", "SUPPORT", 
        "GETIN NEAREST", "DISMISS", "LOITER"
      ]},
      { id: "behaviour", label: "Поведение", options: ["CARELESS", "SAFE", "AWARE", "COMBAT", "STEALTH"] },
      { id: "combatMode", label: "Боевой режим", options: ["BLUE", "GREEN", "YELLOW", "RED"] },
      { id: "speed", label: "Скорость", options: ["LIMITED", "NORMAL", "FULL"] },
      { id: "formation", label: "Строй", options: ["COLUMN", "WEDGE", "LINE", "DIAMOND"] }
    ];

    const lastValues = JSON.parse(localStorage.getItem('lastWaypointValues')) || {};

    params.forEach(param => {
      const label = document.createElement('label');
      label.innerText = `${param.label}:`;
      label.style.width = "120px";
      label.style.display = "inline-block";
      label.style.marginBottom = "5px";
      label.style.verticalAlign = "middle";
      
      const select = document.createElement('select');
      select.id = `wp_${param.id}`;
      select.style.width = "150px";
      select.style.marginBottom = "8px";
      select.style.verticalAlign = "middle";
      const defaultOption = document.createElement('option');
      defaultOption.value = "";
      defaultOption.text = "Не выбрано";
      select.appendChild(defaultOption);
      param.options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt;
        option.text = opt;
        select.appendChild(option);
      });
      
      // Устанавливаем сохраненное значение или значение из waypointData
      if (waypointData && waypointData.params[param.id]) {
        select.value = waypointData.params[param.id];
      } else if (lastValues[param.id]) {
        select.value = lastValues[param.id];
      }

      modal.appendChild(label);
      modal.appendChild(select);
      modal.appendChild(document.createElement('br'));
    });

    const btnContainer = document.createElement('div');
    btnContainer.classList.add('buttons-container');

    const btnOk = document.createElement('button');
    btnOk.innerText = waypointData ? "Сохранить" : "ОК";
    btnOk.style.marginRight = "10px";
    btnOk.onclick = () => waypointData ? editWaypoint(latlng, modal, waypointData) : createWaypoint(latlng, modal);
    btnContainer.appendChild(btnOk);

    if (waypointData) {
      const btnDelete = document.createElement('button');
      btnDelete.innerText = "Удалить";
      btnDelete.style.marginRight = "10px";
      btnDelete.onclick = () => deleteWaypoint(waypointData);
      btnContainer.appendChild(btnDelete);
    }

    const btnCancel = document.createElement('button');
    btnCancel.innerText = "Отмена";
    btnCancel.onclick = () => {
      document.body.removeChild(overlay);
    };
    btnContainer.appendChild(btnCancel);

    modal.appendChild(btnContainer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
  }

  // Создание вэйпойнта
  function createWaypoint(latlng, modal) {
    const conf = Config.get();
    const gameCoords = pixelToGame(latlng);
    const message = {
      command: "add_waypoint",
      side: selectedGroup.side,
      group: selectedGroup.group,
      type: document.getElementById("wp_type").value,
      position: JSON.stringify([Math.round(gameCoords.x), Math.round(gameCoords.y), 0])
    };

    const optionalParams = ["behaviour", "combatMode", "speed", "formation"];
    optionalParams.forEach(param => {
      const value = document.getElementById(`wp_${param}`).value;
      if (value) message[param] = value;
    });

    // Сохраняем выбранные значения
    const lastValues = {};
    lastValues.type = message.type;
    optionalParams.forEach(param => {
      if (message[param]) lastValues[param] = message[param];
    });
    localStorage.setItem('lastWaypointValues', JSON.stringify(lastValues));

    fetch('/send_callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message)
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log("Вэйпойнт создан:", message);
        addWaypointMarker(latlng, message);
      } else {
        console.error("Ошибка создания вэйпойнта:", result);
      }
    })
    .catch(err => console.error("Ошибка отправки команды:", err));

    document.body.removeChild(document.getElementById("waypointOverlay"));
  }

  // Редактирование вэйпойнта
  function editWaypoint(latlng, modal, waypointData) {
    const conf = Config.get();
    const gameCoords = pixelToGame(latlng);
    const message = {
      command: "edit_waypoint",
      side: waypointData.params.side,
      group: waypointData.params.group,
      waypointNumber: waypointData.number, // Номер вэйпойнта для идентификации
      type: document.getElementById("wp_type").value,
      position: JSON.stringify([Math.round(gameCoords.x), Math.round(gameCoords.y), 0])
    };

    const optionalParams = ["behaviour", "combatMode", "speed", "formation"];
    optionalParams.forEach(param => {
      const value = document.getElementById(`wp_${param}`).value;
      if (value) message[param] = value;
    });

    // Сохраняем выбранные значения
    const lastValues = {};
    lastValues.type = message.type;
    optionalParams.forEach(param => {
      if (message[param]) lastValues[param] = message[param];
    });
    localStorage.setItem('lastWaypointValues', JSON.stringify(lastValues));

    fetch('/send_callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message)
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log("Вэйпойнт отредактирован:", message);
        updateWaypointMarker(latlng, message, waypointData);
      } else {
        console.error("Ошибка редактирования вэйпойнта:", result);
      }
    })
    .catch(err => console.error("Ошибка отправки команды:", err));

    document.body.removeChild(document.getElementById("waypointOverlay"));
  }

  // Удаление вэйпойнта
  function deleteWaypoint(waypointData) {
    const message = {
      command: "delete_waypoint",
      side: waypointData.params.side,
      group: waypointData.params.group,
      waypointNumber: waypointData.number
    };

    fetch('/send_callback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message)
    })
    .then(response => response.json())
    .then(result => {
      if (result.status === "success") {
        console.log("Вэйпойнт удален:", message);
        removeWaypointMarker(waypointData);
      } else {
        console.error("Ошибка удаления вэйпойнта:", result);
      }
    })
    .catch(err => console.error("Ошибка отправки команды:", err));

    document.body.removeChild(document.getElementById("waypointOverlay"));
  }

  // Добавление маркера вэйпойнта на карту
  function addWaypointMarker(latlng, message) {
    const sideIcon = message.side === "OPFOR" ? '/static/ico/r_wp.png' : '/static/ico/b_wp.png';
    const groupName = message.group;
    const wpNumber = unitLayer._waypointLayer.getLayers().filter(l => l.options.data && l.options.data.group === groupName).length / 2 + 1;
    
    const icon = L.icon({
      iconUrl: sideIcon,
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    });
    const marker = L.marker(latlng, { icon: icon });
    marker.options.data = { group: groupName, number: wpNumber, params: message };
    
    const tooltipContent = `
      Тип: ${message.type || "N/A"}<br>
      Поведение: ${message.behaviour || "N/A"}<br>
      Боевой режим: ${message.combatMode || "N/A"}<br>
      Скорость: ${message.speed || "N/A"}<br>
      Строй: ${message.formation || "N/A"}
    `;
    marker.bindTooltip(tooltipContent, { direction: 'top', offset: [0, -15] });
    if (unitLayer.waypointMode) {
      marker.on('dblclick', onWaypointDoubleClick);
    }
    
    const labelIcon = L.divIcon({
      html: `<div class="group-label">${groupName} #${wpNumber}</div>`,
      className: 'label-marker',
      iconSize: [100, 20],
      iconAnchor: [50, -15]
    });
    const labelMarker = L.marker(latlng, { icon: labelIcon });
    labelMarker.options.data = { group: groupName, number: wpNumber };
    
    unitLayer._waypointLayer.addLayer(marker);
    unitLayer._waypointLayer.addLayer(labelMarker);
  }

  // Обновление маркера вэйпойнта
  function updateWaypointMarker(latlng, message, waypointData) {
    unitLayer._waypointLayer.eachLayer(layer => {
      if (layer.options.data.group === waypointData.group && layer.options.data.number === waypointData.number) {
        if (layer.options.icon) { // Это маркер
          layer.setLatLng(latlng);
          layer.options.data.params = message;
          const tooltipContent = `
            Тип: ${message.type || "N/A"}<br>
            Поведение: ${message.behaviour || "N/A"}<br>
            Боевой режим: ${message.combatMode || "N/A"}<br>
            Скорость: ${message.speed || "N/A"}<br>
            Строй: ${message.formation || "N/A"}
          `;
          layer.setTooltipContent(tooltipContent);
        }
      }
    });
  }

  // Удаление маркера вэйпойнта
  function removeWaypointMarker(waypointData) {
    const layersToRemove = [];
    unitLayer._waypointLayer.eachLayer(layer => {
      if (layer.options.data.group === waypointData.group && layer.options.data.number === waypointData.number) {
        layersToRemove.push(layer);
      }
    });
    layersToRemove.forEach(layer => unitLayer._waypointLayer.removeLayer(layer));
  }

  // Инициализация
  createWaypointButton();

  // Экспортируем публичный API
  window.waypointEditor = {
    onGroupClick: onGroupClick,
    toggleWaypointMode: toggleWaypointMode
  };
})();