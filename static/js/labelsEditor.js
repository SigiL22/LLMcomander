// js/labelsEditor.js

(function(){
  var editMode = false;
  var editableMarkers = [];

  function gameToLatLng(X, Y) {
    var conf = Config.get();
    var px = X * (conf.mapImageWidth / conf.islandWidth);
    var py = conf.mapImageHeight - (Y * (conf.mapImageHeight / conf.islandHeight));
    return map.unproject([px, py], 7);
  }

  function containerPointToGame(pt) {
    var conf = Config.get();
    var latlng = map.containerPointToLatLng(pt);
    var point7 = map.project(latlng, 7);
    var X = point7.x / (conf.mapImageWidth / conf.islandWidth);
    var Y = (conf.mapImageHeight - point7.y) / (conf.mapImageHeight / conf.islandHeight);
    return { x: X, y: Y };
  }

  function sendUpdateLabel(data) {
    fetch('/update_label', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: data.id, x: data.newCoords.x, y: data.newCoords.y })
    })
    .then(response => response.json())
    .then(result => {
      console.log("Обновление на сервере успешно:", result);
      namesLayer.update();
    })
    .catch(err => console.error("Ошибка обновления на сервере:", err));
  }

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
        if (callback) callback(result.id); // Передаем id в callback
      }
      namesLayer.update();
    })
    .catch(err => console.error("Ошибка добавления на сервере:", err));
  }

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

  function toggleEditMode() {
    editMode = !editMode;
    var btn = document.getElementById("editLabelsBtn");
    if (editMode) {
      btn.style.backgroundColor = "#aaf";
      enableEditing();
    } else {
      btn.style.backgroundColor = "";
      disableEditing();
    }
  }

  function enableEditing() {
    namesLayer._namesGroup.eachLayer(function(marker) {
      marker.setOpacity(1);
      marker.dragging.enable();
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
      // Проверяем, нет ли уже этого маркера в editableMarkers
      if (!editableMarkers.some(m => m.id === marker.options.data.id && m.marker === marker)) {
        editableMarkers.push({ id: marker.options.data.id, marker: marker });
      }
    });
    map.on('dblclick', onMapDoubleClick);
  }

  function disableEditing() {
    map.off('dblclick', onMapDoubleClick);
    editableMarkers.forEach(function(item) {
      var data = item.marker.options.data;
      var gameCoords;

      if (data.newCoords) {
        gameCoords = data.newCoords;
      } else if (data.id === null) {
        var latlng = item.marker.getLatLng();
        var containerPt = map.latLngToContainerPoint(latlng);
        gameCoords = containerPointToGame(containerPt);
      } else {
        return;
      }

      if (data.id !== null) {
        sendUpdateLabel({ id: data.id, newCoords: gameCoords });
      } else {
        sendAddLabel({ name: data.name, type: data.type, newCoords: gameCoords }, function(newId) {
          item.id = newId; // Обновляем id после добавления
          data.id = newId;
        });
      }

      // Проверяем, существует ли dragging, перед вызовом disable
      if (item.marker.dragging) {
        item.marker.dragging.disable();
      }
    });
    editableMarkers = []; // Очищаем массив после обработки
  }

  function onMapDoubleClick(e) {
    L.DomEvent.stop(e);
    showLabelPopup(e.latlng, null);
  }

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

    setTimeout(() => {
      if (labelData) {
        inputText.select();
      } else {
        inputText.focus();
      }
    }, 0);

    inputText.addEventListener('keypress', function(e) {
      if (e.key === 'Enter' || e.keyCode === 13) {
        btnOk.click();
      }
    });
    inputText.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' || e.keyCode === 27) {
        btnCancel.click();
      }
    });

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
      var style = Config.get().nameSettings[type];
      if (labelData && labelData.marker) {
        labelData.marker.setIcon(L.divIcon({
          className: "name-label",
          html: `<div style="font:${style.fontSize}px ${style.fontFamily};color:${style.color};opacity:${style.opacity};display:flex;align-items:center;justify-content:center;">${text}</div>`,
          iconSize: [100, 30],
          iconAnchor: [50, 15]
        }));
        labelData.marker.options.data.name = text;
        labelData.marker.options.data.type = type;
        console.log("Отредактирована надпись id=" + labelData.id + " новым текстом: " + text);
      } else {
        var icon = L.divIcon({
          className: "name-label",
          html: `<div style="font:${style.fontSize}px ${style.fontFamily};color:${style.color};opacity:${style.opacity};display:flex;align-items:center;justify-content:center;">${text}</div>`,
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
        marker.addTo(namesLayer._namesGroup);
        // Проверяем, нет ли уже этого маркера в editableMarkers
        if (!editableMarkers.some(m => m.marker === marker)) {
          editableMarkers.push({ id: null, marker: marker });
        }
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

  createEditLabelsButton();

  window.labelsEditor = {
    toggleEditMode: toggleEditMode,
    editableMarkers: editableMarkers
  };
})();