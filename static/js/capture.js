// js/capture.js
/**
 * Функция captureMapArea (Обновленная для прямоугольных областей и skipDetails)
 *
 * @param {number} targetCellX - X центра (в ячейках)
 * @param {number} targetCellY - Y центра (в ячейках)
 * @param {number} regionSizeX - Радиус по X в ячейках (половина ширины)
 * @param {number} regionSizeY - Радиус по Y в ячейках (половина высоты). Если не задан, берется X.
 * @param {boolean} showCellLabels - Флаг отображения подписей ячеек (визуально)
 * @param {Array} sides - [ВыбраннаяСторона, Враги...]
 * @param {boolean} skipDetails - Если true, не генерирует и не сохраняет JSON зданий и названий (для обзорных снимков).
 */
function captureMapArea(targetCellX, targetCellY, regionSizeX, regionSizeY, showCellLabels, sides, skipDetails = false, customFilename = null) {
  if (regionSizeY === undefined || regionSizeY === null) {
    regionSizeY = regionSizeX;
  }

  return new Promise((resolve, reject) => {
    // --- ХАК ДЛЯ GRIDLAYER ---
    const conf = Config.get();
    const originalShowLabelsState = conf.cellCoordStyle.show;
    conf.cellCoordStyle.show = showCellLabels;
    Config.set(conf); 

    console.log("[captureMapArea] Захват:", { targetCellX, targetCellY, rx: regionSizeX, ry: regionSizeY, skipDetails, forceLabels: showCellLabels });
    
    const CELL_SIZE = 100; 
    const MAX_ZOOM = conf.maxZoom || 9;
    const MAP_SIZE_METERS = conf.islandWidth || 15360;
    const mapImageWidth = conf.mapImageWidth || 32768;
    const PIXELS_PER_METER_ZOOM_7 = mapImageWidth / MAP_SIZE_METERS;
    const WINDOW_MARGIN = 0.1; 
    const MAX_WINDOW_SIZE = 2000; 

    // 1. Геометрия
    const centerX = targetCellX * CELL_SIZE + CELL_SIZE / 2;
    const centerY = targetCellY * CELL_SIZE + CELL_SIZE / 2;
    const areaCellsX = 2 * regionSizeX + 1;
    const areaCellsY = 2 * regionSizeY + 1;
    const areaMetersX = areaCellsX * CELL_SIZE;
    const areaMetersY = areaCellsY * CELL_SIZE;
    const minX = centerX - areaMetersX / 2;
    const maxX = centerX + areaMetersX / 2;
    const minY = centerY - areaMetersY / 2;
    const maxY = centerY + areaMetersY / 2;
    const centerLatLng = gameToLatLng(centerX, centerY, conf);

    // 2. Расчет зума
    let zoom = MAX_ZOOM;
    let pixelsPerMeter, windowWidth, windowHeight;
    do {
      pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
      windowWidth = Math.ceil(areaMetersX * pixelsPerMeter * (1 + WINDOW_MARGIN));
      windowHeight = Math.ceil(areaMetersY * pixelsPerMeter * (1 + WINDOW_MARGIN));
      if (windowWidth > MAX_WINDOW_SIZE || windowHeight > MAX_WINDOW_SIZE) {
        zoom--;
      } else {
        break;
      }
    } while (zoom > 2);
    windowWidth = Math.min(windowWidth, MAX_WINDOW_SIZE);
    windowHeight = Math.min(windowHeight, MAX_WINDOW_SIZE);

    // 3. DOM контейнер
    const hiddenContainer = document.createElement('div');
    hiddenContainer.style.position = 'absolute';
    hiddenContainer.style.top = '-9999px';
    hiddenContainer.style.left = '-9999px';
    hiddenContainer.style.width = `${windowWidth}px`;
    hiddenContainer.style.height = `${windowHeight}px`;
    document.body.appendChild(hiddenContainer);

    // 4. Карта Leaflet
    const offscreenMap = L.map(hiddenContainer, {
      crs: L.CRS.Simple,
      zoomControl: false,
      attributionControl: false,
      doubleClickZoom: false,
      dragging: false,
      scrollWheelZoom: false,
      boxZoom: false,
      keyboard: false,
      zoomAnimation: false,
      fadeAnimation: false // Отключаем анимацию для надежности html2canvas
    });

    const tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
      noWrap: true,
      tileBuffer: 10, // <--- УВЕЛИЧЕНО С 2 ДО 10: Грузим больше тайлов вокруг, чтобы не было серых краев
      maxNativeZoom: 7,
      maxZoom: MAX_ZOOM,
      bounds: [[-32768, -32768], [32768, 32768]],
      getTileUrl: function(coords) {
        if (coords.x < 0 || coords.y < 0) return '/transparent.png';
        return L.Util.template(this._url, { z: coords.z, x: coords.x, y: coords.y });
      }
    }).addTo(offscreenMap);

    offscreenMap.setView([centerLatLng.lat, centerLatLng.lng], zoom);

    // Слои
    const gridLayerInstance = new GridLayer().addTo(offscreenMap);
    const namesLayerInstance = new NamesLayer().addTo(offscreenMap);
    const unitLayerInstance = new UnitLayer().addTo(offscreenMap);

    if (window.unitLayer && window.unitLayer._lastData) {
      unitLayerInstance.updateData(window.unitLayer._lastData, []);
    }

    if (gridLayerInstance._redraw) gridLayerInstance._redraw();
    if (namesLayerInstance._createMarkers) namesLayerInstance._createMarkers();

    const restoreConfig = () => {
        conf.cellCoordStyle.show = originalShowLabelsState;
        Config.set(conf);
        console.log("[captureMapArea] Глобальные настройки лейблов восстановлены");
    };

    // 5. Улучшенная логика ожидания
    const tryCapture = () => {
        // Проверяем, грузит ли еще Leaflet тайлы
        if (tileLayer.isLoading()) {
            console.log("[captureMapArea] Leaflet все еще грузит тайлы. Ждем...");
            setTimeout(tryCapture, 500);
            return;
        }

        console.log("[captureMapArea] Тайлы загружены. Старт html2canvas...");
        
        html2canvas(hiddenContainer, {
          useCORS: true,
          allowTaint: true, // Разрешаем "грязный" канвас (локально это ок)
          onclone: (clonedDoc) => {
            const hiddenMapElement = clonedDoc.querySelector('.leaflet-container');
            if (hiddenMapElement) {
              const tilePane = hiddenMapElement.querySelector('.leaflet-tile-pane');
              const overlayPane = hiddenMapElement.querySelector('.leaflet-overlay-pane');
              if (tilePane && overlayPane) {
                overlayPane.appendChild(tilePane);
                tilePane.style.transform = 'none';
              }
            }
          }
        }).then(canvas => {
          // -- Сохранение изображения --
          const mapImage = canvas.toDataURL("image/png");
          let snapshotFileName;
          let jsonBaseName;

          if (customFilename) {
              snapshotFileName = customFilename;
              jsonBaseName = customFilename.replace(/\.[^/.]+$/, "");
          } else {
              const typePrefix = skipDetails ? "strategic_" : "tactical_";
              const timePart = new Date().toISOString().replace(/[:.]/g, "-");
              jsonBaseName = "snapshot_" + typePrefix + timePart; 
              snapshotFileName = jsonBaseName + ".png";
          }
          
          fetch('/save_snapshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: mapImage, filename: snapshotFileName })
          }).then(() => console.log("Снимок сохранен:", snapshotFileName));

          // -- Формирование данных --
          const area = { minX, maxX, minY, maxY };
          
          let buildingsPromise;
          if (!skipDetails) {
              buildingsPromise = fetch('/get_buildings', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(area)
              })
              .then(res => res.json())
              .then(buildings => {
                  const bJson = buildings.map(b => ({ i: b.id, n: b.name, p: [b.x, b.y, b.z], in: b.interior }));
                  const fn = "buildings_" + jsonBaseName + ".json";
                  return fetch('/save_json', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ filename: fn, data: bJson })
                  }).then(() => bJson);
              });
          } else {
              buildingsPromise = Promise.resolve([]);
          }

          const namesPromise = fetch('/get_names_in_area', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(area)
          })
          .then(res => res.json())
          .then(names => {
              const nJson = names.map(n => ({ i: n.id, n: n.name, t: n.type, p: [n.x, n.y] }));
              const fn = "names_" + jsonBaseName + ".json";
              return fetch('/save_json', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ filename: fn, data: nJson })
              }).then(() => nJson);
          });

          const bounds = offscreenMap.getBounds();
          const unitMarkers = [];
          let chosenSide = (sides && sides.length > 0) ? sides[0] : null;

          if (window.unitLayer) {
             if (window.unitLayer._groupLayer) {
                window.unitLayer._groupLayer.eachLayer(marker => {
                  if (bounds.contains(marker.getLatLng())) {
                    if (!chosenSide || marker.options.data.side === chosenSide) {
                        unitMarkers.push(marker.options.data);
                    }
                  }
                });
             }
             if (window.unitLayer._reportGroupLayer) {
                window.unitLayer._reportGroupLayer.eachLayer(marker => {
                  if (bounds.contains(marker.getLatLng())) {
                    if (chosenSide && marker.options.data.side !== chosenSide) {
                        unitMarkers.push(marker.options.data);
                    }
                  }
                });
             }
          }

          Promise.all([buildingsPromise, namesPromise]).then(([buildingsData, namesData]) => {
              offscreenMap.remove();
              document.body.removeChild(hiddenContainer);
              restoreConfig();
              resolve({
                  mapImage: mapImage,
                  unitMarkers: unitMarkers,
                  buildings: buildingsData,
                  dbNames: namesData
              });
          }).catch(err => {
              console.error("[captureMapArea] Ошибка JSON:", err);
              offscreenMap.remove();
              document.body.removeChild(hiddenContainer);
              restoreConfig();
              reject(err);
          });

        }).catch(err => {
          console.error("[captureMapArea] Ошибка html2canvas:", err);
          offscreenMap.remove();
          document.body.removeChild(hiddenContainer);
          restoreConfig();
          reject(err);
        });
    };

    // Запускаем процесс ожидания загрузки
    tileLayer.on('load', function() {
        console.log("[captureMapArea] Событие load сработало. Старт безопасного ожидания...");
        // Ждем 4 секунды (надежный запас для больших карт) + проверка isLoading
        setTimeout(tryCapture, 4000); 
    });

    // Watchdog (увеличен до 30 сек для больших карт)
    setTimeout(() => {
        if (!offscreenMap._loaded && document.body.contains(hiddenContainer)) {
            console.error("[captureMapArea] Watchdog timeout.");
            offscreenMap.remove();
            document.body.removeChild(hiddenContainer);
            restoreConfig();
            reject(new Error("Timeout"));
        }
    }, 30000);
  });
}


function openMapWindow(xxx, yyy, m, showCellLabels = false, sides = []) {
  const conf = Config.get();
  const CELL_SIZE = 100;
  const MAX_ZOOM = conf.maxZoom || 9;
  const MAP_SIZE_METERS = conf.islandWidth || 15360;
  const MAP_SIZE_PIXELS_ZOOM_7 = conf.mapImageWidth || 32768;
  const PIXELS_PER_METER_ZOOM_7 = MAP_SIZE_PIXELS_ZOOM_7 / MAP_SIZE_METERS;
  const MAX_WINDOW_SIZE = 1500;
  const WINDOW_MARGIN = 0.1;
  const TILE_LOAD_TIMEOUT = 5000;

  console.log(`[openMapWindow] Запуск: xxx=${xxx}, yyy=${yyy}, m=${m}, showCellLabels=${showCellLabels}, sides=${sides}`);

  const centerX = xxx * CELL_SIZE + CELL_SIZE / 2;
  const centerY = yyy * CELL_SIZE + CELL_SIZE / 2;
  const areaCells = 2 * m + 1;
  const areaMeters = areaCells * CELL_SIZE;
  const minX = centerX - areaMeters / 2;
  const maxX = centerX + areaMeters / 2;
  const minY = centerY - areaMeters / 2;
  const maxY = centerY + areaMeters / 2;

  const centerLatLng = gameToLatLng(centerX, centerY, conf);
  const sw = gameToLatLng(minX, minY, conf);
  const ne = gameToLatLng(maxX, maxY, conf);

  let zoom = MAX_ZOOM;
  let pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
  const areaWidthMeters = maxX - minX;
  const areaHeightMeters = maxY - minY;
  let windowWidth = areaWidthMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
  let windowHeight = areaHeightMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);

  while ((windowWidth > MAX_WINDOW_SIZE || windowHeight > MAX_WINDOW_SIZE) && zoom > 2) {
    zoom--;
    pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
    windowWidth = areaWidthMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
    windowHeight = areaHeightMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
  }

  windowWidth = Math.round(Math.min(windowWidth, MAX_WINDOW_SIZE));
  windowHeight = Math.round(Math.min(windowHeight, MAX_WINDOW_SIZE));
  console.log(`[openMapWindow] Размер окна: ${windowWidth}x${windowHeight}, zoom=${zoom}`);

  const mapWindow = window.open('', 'MapWindow', `width=${windowWidth},height=${windowHeight}`);
  if (!mapWindow) {
    console.error('[openMapWindow] Не удалось открыть окно');
    return null;
  }

  mapWindow.document.write(`
    <html>
      <head>
        <title>Map Preview</title>
		<link rel="stylesheet" href="/static/leaflet/leaflet.css" />
        <script src="/static/leaflet/leaflet.js"></script>
        <script src="/static/html2canvas/html2canvas.min.js"></script> <!-- Локальный html2canvas -->
        <script src="js/config.js"></script>
        <script src="js/gameToLatLng.js"></script>
        <script src="js/gridLayer.js"></script>
        <script src="js/namesLayer.js"></script>
        <script src="js/unitLayer.js"></script>
        <style>
          #map { width: 100%; height: 100%; }
          body { margin: 0; }
        </style>
      </head>
      <body>
        <div id="map"></div>
        <script>
          function logToParent(...args) {
            window.opener?.console?.log('[MapWindow]', ...args) || console.log('[MapWindow]', ...args);
          }

          Config.load();
          var conf = Config.get();
          conf.cellCoordStyle.show = ${showCellLabels};
          Config.set(conf);

          var map = L.map('map', {
            crs: L.CRS.Simple,
            minZoom: 2,
            maxZoom: ${MAX_ZOOM},
            updateWhenIdle: true,
            updateWhenZooming: false,
            zoomControl: false,
            doubleClickZoom: false
          });

          var tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
            noWrap: true,
            attribution: "Карта Chernarus",
            updateWhenIdle: true,
            tileBuffer: 2,
            maxNativeZoom: 7,
            maxZoom: ${MAX_ZOOM},
            bounds: [[-32768, -32768], [32768, 32768]],
            getTileUrl: function(coords) {
              return coords.x < 0 || coords.y < 0 ? '/transparent.png' : 
                L.Util.template(this._url, { z: coords.z, x: coords.x, y: coords.y });
            }
          }).addTo(map);

          var gridLayer = new GridLayer().addTo(map);
          var namesLayer = new NamesLayer().addTo(map);
          var unitLayer = new UnitLayer().addTo(map);

          map.setView([${centerLatLng.lat}, ${centerLatLng.lng}], ${zoom});

          Config.apply();
          setTimeout(() => gridLayer._redraw && gridLayer._redraw(), 100);

          // Получаем данные юнитов через /arma_data
          fetch('http://localhost:5000/arma_data')
            .then(response => response.json())
            .then(data => {
              if (data.status === "success") {
                let filteredData = { sides: {} };
                const sidesToShow = ${JSON.stringify(sides)};
                if (sidesToShow.length > 0 && data.data.sides) {
                  sidesToShow.forEach(side => {
                    if (data.data.sides[side]) {
                      filteredData.sides[side] = data.data.sides[side];
                    }
                  });
                } else {
                  filteredData = data.data;
                }
                logToParent('Передаём данные в unitLayer:', filteredData);
                unitLayer.updateData(filteredData);
              } else {
                logToParent('Нет данных от /arma_data:', data);
              }
            })
            .catch(err => logToParent('Ошибка получения данных:', err));

          // Получаем данные зданий и названий из базы
          const area = { minX: ${minX}, maxX: ${maxX}, minY: ${minY}, maxY: ${maxY} };
          fetch('http://localhost:5000/get_buildings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(area)
          })
            .then(response => response.json())
            .then(buildings => {
              const buildingsJson = buildings.map(b => ({
                i: b.id,
                n: b.name,
                p: [b.x, b.y, b.z],
                in: b.interior
              }));
              fetch('/save_json', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: 'buildings.json', data: buildingsJson })
              }).then(() => logToParent('Buildings JSON сохранен'));
            })
            .catch(err => logToParent('Ошибка получения зданий:', err));

          fetch('http://localhost:5000/get_names_in_area', {
			  method: 'POST',
			  headers: { 'Content-Type': 'application/json' },
			  body: JSON.stringify(area)
			})
			  .then(response => response.json())
			  .then(names => {
				const namesJson = names.map(n => ({
				  i: n.id,
				  n: n.name,
				  t: n.type,
				  p: [n.x, n.y]
				}));
				fetch('/save_json', {
				  method: 'POST',
				  headers: { 'Content-Type': 'application/json' },
				  body: JSON.stringify({ filename: 'names.json', data: namesJson })
				}).then(() => logToParent('Names JSON сохранен'));
			  })
			  .catch(err => logToParent('Ошибка получения названий:', err));

          const waitForTiles = new Promise((resolve) => {
            tileLayer.once('load', () => {
              logToParent('Тайлы загружены');
              setTimeout(resolve, 500);
            });
            setTimeout(() => {
              logToParent('Тайм-аут загрузки тайлов');
              resolve();
            }, ${TILE_LOAD_TIMEOUT});
          });

          waitForTiles.then(() => {
            const mapElement = document.getElementById('map');
            html2canvas(mapElement, {
              useCORS: true,
              width: map.getSize().x,
              height: map.getSize().y,
              backgroundColor: null,
              onclone: (doc) => {
                const clonedMap = doc.getElementById('map');
                clonedMap.style.backgroundColor = '#fff';
                const tilePane = clonedMap.querySelector('.leaflet-tile-pane');
                const overlayPane = clonedMap.querySelector('.leaflet-overlay-pane');
                if (tilePane && overlayPane) {
                  tilePane.style.opacity = '1';
                  overlayPane.appendChild(tilePane);
                }
                clonedMap.querySelectorAll('.leaflet-layer, .leaflet-overlay-pane').forEach(layer => {
                  layer.style.transform = 'none';
                  layer.style.opacity = '1';
                });
                clonedMap.querySelectorAll('.leaflet-grid-layer').forEach(layer => {
                  layer.style.display = 'block';
                  layer.style.zIndex = '1000';
                });
              }
            }).then(canvas => {
              const dataUrl = canvas.toDataURL('image/png');
              fetch('/save_snapshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  image: dataUrl,
                  filename: \`snapshot_${xxx}_${yyy}_m${m}_z${map.getZoom()}.png\`
                })
              })
              .then(response => response.json())
              .then(result => {
                logToParent('Снимок сохранен:', result);
                window.close();
              })
              .catch(err => {
                logToParent('Ошибка сохранения снимка:', err);
                alert('Ошибка сохранения снимка');
                window.close();
              });
            }).catch(err => {
              logToParent('Ошибка рендеринга html2canvas:', err);
              alert('Ошибка создания снимка');
              window.close();
            });
          });
        </script>
      </body>
    </html>
  `);

  return mapWindow;
}

window.openMapWindow = openMapWindow;