// labelsEditor.js

(function(){
  var editMode = false;
  var editableMarkers = []; // Массив объектов: { id, marker }
  
  // Функция преобразования игровой координаты в latlng (с использованием зума 7)
  function gameToLatLng(X, Y) {
    var conf = Config.get();
    var px = X * (conf.mapImageWidth / conf.islandWidth);
    var py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
    return map.unproject([px, py], 7);
  }
  
  // Функция обратного преобразования container point в игровые координаты
  function containerPointToGame(pt) {
    var conf = Config.get();
    var latlng = map.containerPointToLatLng(pt);
    var point7 = map.project(latlng, 7);
    var X = point7.x / (conf.mapImageWidth / conf.islandWidth);
    var Y = (conf.mapImageHeight - point7.y) / (conf.mapImageHeight / conf.islandHeight);
    return { x: X, y: Y };
  }
  
  // Функция для отправки запроса на обновление существующей надписи
  function sendUpdateLabel(data) {
    fetch('/update_label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: data.id, x: data.newCoords.x, y: data.newCoords.y })
    })
    .then(response => response.json())
    .then(result => {
      console.log("Обновление на сервере успешно:", result);
    })
    .catch(err => console.error("Ошибка обновления на сервере:", err));
  }
  
  // Функция для отправки запроса на добавление новой надписи
  function sendAddLabel(data, callback) {
    fetch('/add_label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: data.name, type: data.type, x: data.newCoords.x, y: data.newCoords.y })
    })
    .then(response => response.json())
    .then(result => {
      console.log("Добавление на сервере успешно:", result);
      if (result.id) {
        data.id = result.id;
      }
      if (callback) callback();
    })
    .catch(err => console.error("Ошибка добавления на сервере:", err));
  }
  
  // Создаем кнопку редактирования и добавляем её в тулбар настроек
  function createEditLabelsButton() {
    var toolbar = document.getElementById("settingsToolbar");
    if (!toolbar) {
      toolbar = document.createElement('div');
      toolbar.id = "settingsToolbar";
      toolbar.style.position = "absolute";
      toolbar.style.top = "10px";
      toolbar.style.left = "10px";
      toolbar.style.zIndex = "1000";
      document.body.appendChild(toolbar);
    }
    var btn = document.createElement('button');
    btn.id = "editLabelsBtn";
    btn.innerText = "Ред. надписи";
    btn.style.marginLeft = "10px";
    btn.onclick = toggleEditMode;
    toolbar.appendChild(btn);
  }
  
  // Переключение режима редактирования
  function toggleEditMode() {
    editMode = !editMode;
    var btn = document.getElementById("editLabelsBtn");
    if (editMode) {
      btn.style.backgroundColor = "#aaf"; // выделяем активное состояние
      enableEditing();
    } else {
      btn.style.backgroundColor = "";
      disableEditing();
    }
  }
  
  // Включение режима редактирования: создаем draggable-маркеры для существующих надписей
  function enableEditing() {
    // Скрываем canvas с отрисовкой надписей
    var namesCanvas = document.querySelector('.leaflet-names-layer');
    if (namesCanvas) {
      namesCanvas.style.display = "none";
    }
    if (window.namesLayer && namesLayer._names) {
      namesLayer._names.forEach(function(item) {
        // Вычисляем latlng напрямую через gameToLatLng, чтобы соответствовать отрисовке
        var latlng = gameToLatLng(item.x, item.y);
        // Используем стили из настроек для данной надписи
        var styleCfg = Config.get().nameSettings[item.type] || { fontFamily: "sans-serif", fontSize: 14, color: "#000000", opacity: 1 };
        var html = '<div style="font:' + styleCfg.fontSize + 'px ' + styleCfg.fontFamily + ';' +
                   'color:' + styleCfg.color + ';opacity:' + styleCfg.opacity + ';">' + item.name + '</div>';
        var icon = L.divIcon({
          className: "label-marker",
          html: html,
          iconSize: [100, 30],
          iconAnchor: [50,15] // центр иконки
        });
        var marker = L.marker(latlng, {
          icon: icon,
          draggable: true
        });
        marker.options.data = {
          id: item.id,
          name: item.name,
          type: item.type,
          original: { x: item.x, y: item.y },
          newCoords: null
        };
        marker.on('dragend', function(e) {
          var newLatLng = e.target.getLatLng();
          var containerPt = map.latLngToContainerPoint(newLatLng);
          var gameCoords = containerPointToGame(containerPt);
          e.target.options.data.newCoords = gameCoords;
          console.log("Маркер id=" + e.target.options.data.id + " перемещён в", gameCoords);
        });
        marker.on('dblclick', function(e) {
          showLabelPopup(e.target.getLatLng(), {
            id: e.target.options.data.id,
            name: e.target.options.data.name,
            type: e.target.options.data.type,
            marker: e.target
          });
        });
        marker.addTo(map);
        editableMarkers.push({ id: item.id, marker: marker });
      });
    }
    // Включаем обработчик двойного клика на карте для добавления новых надписей
    map.on('dblclick', onMapDoubleClick);
  }
  
  // Выключение режима редактирования: отправляем изменения на сервер и обновляем отображение
  function disableEditing() {
    map.off('dblclick', onMapDoubleClick);
    if (window.namesLayer && namesLayer._names) {
      editableMarkers.forEach(function(item) {
        var data = item.marker.options.data;
        if (data.newCoords) {
          if (data.id !== null) {
            // Существующая надпись – отправляем запрос на обновление
            sendUpdateLabel(data);
            // Обновляем локальную копию
            namesLayer._names.forEach(function(n) {
              if (n.id === data.id) {
                n.x = data.newCoords.x;
                n.y = data.newCoords.y;
              }
            });
          } else {
            // Новая надпись – отправляем запрос на добавление
            sendAddLabel(data, function(){
              if (window.namesLayer && namesLayer._names) {
                namesLayer._names.push({
                  id: data.id, // обновленный в sendAddLabel
                  name: data.name,
                  type: data.type,
                  x: data.newCoords.x,
                  y: data.newCoords.y
                });
              }
            });
          }
        }
        map.removeLayer(item.marker);
      });
    }
    editableMarkers = [];
    var namesCanvas = document.querySelector('.leaflet-names-layer');
    if (namesCanvas) {
      namesCanvas.style.display = "";
    }
    if (window.namesLayer && typeof namesLayer._redraw === "function") {
      namesLayer._redraw();
    }
  }
  
  // Обработчик двойного клика на карте для добавления новой надписи
  function onMapDoubleClick(e) {
    showLabelPopup(e.latlng, null);
  }
  
  // Функция открытия всплывающего окна для добавления или редактирования надписи
  function showLabelPopup(latlng, labelData) {
    var popupOverlay = document.createElement('div');
    popupOverlay.id = "labelPopupOverlay";
    popupOverlay.style.position = "fixed";
    popupOverlay.style.top = "0";
    popupOverlay.style.left = "0";
    popupOverlay.style.width = "100%";
    popupOverlay.style.height = "100%";
    popupOverlay.style.backgroundColor = "rgba(0,0,0,0.5)";
    popupOverlay.style.zIndex = "1400";
    
    var popup = document.createElement('div');
    popup.id = "labelPopup";
    popup.style.position = "fixed";
    popup.style.top = "50%";
    popup.style.left = "50%";
    popup.style.transform = "translate(-50%, -50%)";
    popup.style.backgroundColor = "white";
    popup.style.padding = "20px";
    popup.style.boxShadow = "0 0 10px rgba(0,0,0,0.5)";
    popup.style.zIndex = "1500";
    popup.style.width = "300px";
    
    var title = document.createElement('h3');
    title.innerText = labelData ? "Редактировать надпись" : "Добавить надпись";
    popup.appendChild(title);
    
    var inputText = document.createElement('input');
    inputText.type = "text";
    inputText.id = "labelTextInput";
    inputText.style.width = "100%";
    inputText.value = labelData ? labelData.name : "";
    popup.appendChild(inputText);
    
    var selectType = document.createElement('select');
    selectType.id = "labelTypeSelect";
    selectType.style.width = "100%";
    var types = Config.get().nameSettings;
    for (var key in types) {
      if (types.hasOwnProperty(key)) {
        var option = document.createElement('option');
        option.value = key;
        option.text = types[key].displayName;
        if (labelData && labelData.type === key) {
          option.selected = true;
        }
        selectType.appendChild(option);
      }
    }
    if (!labelData) {
      var lastType = localStorage.getItem("lastLabelType");
      if (lastType) {
        selectType.value = lastType;
      }
    }
    popup.appendChild(selectType);
    
    var btnOk = document.createElement('button');
    btnOk.innerText = "OK";
    btnOk.style.marginRight = "10px";
    btnOk.onclick = function() {
      var text = inputText.value.trim();
      var type = selectType.value;
      if (!text) {
        alert("Введите текст надписи");
        return;
      }
      localStorage.setItem("lastLabelType", type);
      if (labelData && labelData.marker) {
        labelData.marker.setIcon(L.divIcon({
          className: "label-marker",
          html: '<div style="font:' + types[labelData.type].fontSize + 'px ' + types[labelData.type].fontFamily + '; color:' + types[labelData.type].color + '; opacity:' + types[labelData.type].opacity + ';">' + text + '</div>',
          iconSize: [100, 30],
          iconAnchor: [50, 15]
        }));
        labelData.marker.options.data.name = text;
        labelData.marker.options.data.type = type;
        console.log("Отредактирована надпись id=" + labelData.id + " новым текстом: " + text);
      } else {
        var icon = L.divIcon({
          className: "label-marker",
          html: '<div style="font:' + types[type].fontSize + 'px ' + types[type].fontFamily + '; color:' + types[type].color + '; opacity:' + types[type].opacity + ';">' + text + '</div>',
          iconSize: [100, 30],
          iconAnchor: [50, 15]
        });
        var marker = L.marker(latlng, { icon: icon, draggable: true });
        marker.options.data = {
          id: null,
          name: text,
          type: type,
          newCoords: null
        };
        marker.on('dragend', function(e) {
          var newLatLng = e.target.getLatLng();
          var containerPt = map.latLngToContainerPoint(newLatLng);
          var gameCoords = containerPointToGame(containerPt);
          e.target.options.data.newCoords = gameCoords;
          console.log("Новая надпись перемещена: ", e.target.options.data);
        });
        marker.on('dblclick', function(e) {
          showLabelPopup(e.target.getLatLng(), {
            id: e.target.options.data.id,
            name: e.target.options.data.name,
            type: e.target.options.data.type,
            marker: e.target
          });
        });
        marker.addTo(map);
        editableMarkers.push({ id: null, marker: marker });
        console.log("Добавлена новая надпись: " + text);
      }
      document.body.removeChild(popupOverlay);
    };
    popup.appendChild(btnOk);
    
    var btnCancel = document.createElement('button');
    btnCancel.innerText = "Отмена";
    btnCancel.onclick = function() {
      document.body.removeChild(popupOverlay);
    };
    popup.appendChild(btnCancel);
    
    popupOverlay.appendChild(popup);
    document.body.appendChild(popupOverlay);
  }
  
  // Инициализация кнопки редактирования
  createEditLabelsButton();
  
  // Обработчик двойного клика на карте для добавления новой надписи
  map.on('dblclick', onMapDoubleClick);
  
  function onMapDoubleClick(e) {
    showLabelPopup(e.latlng, null);
  }
  
  // Экспорт для отладки
  window.labelsEditor = {
    toggleEditMode: toggleEditMode,
    editableMarkers: editableMarkers
  };
})();
