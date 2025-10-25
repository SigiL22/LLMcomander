// js/capture.js
/**
 * Функция captureMapArea создаёт скрытый offscreen-контейнер для рендеринга карты,
 * устанавливает нужный центр и зум (на основе target-маркера и заданной области из настроек миссии),
 * затем выполняет захват изображения с помощью html2canvas, сохраняет снимок в папку snapshots,
 * запрашивает данные зданий и названий из базы (по ограничению области) и сохраняет их как JSON,
 * а также фильтрует маркеры: для выбранной стороны (первый элемент массива sides) – берутся полные данные,
 * для противоположных сторон – берутся маркеры, полученные по докладам.
 *
 * @param {number} targetCellX - координата X target-маркера в игровых единицах (например, номер ячейки)
 * @param {number} targetCellY - координата Y target-маркера в игровых единицах
 * @param {number} regionSize - размер области вокруг target (например, количество ячеек от центра)
 * @param {boolean} showCellLabels - флаг отображения подписей ячеек
 * @param {Array} sides - список сторон, где первый элемент — выбранная сторона, остальные – противоположные
 * @returns {Promise<Object>} - Promise, который разрешается объектом { mapImage, objects, labels }
 */
function captureMapArea(targetCellX, targetCellY, regionSize, showCellLabels, sides) {
  return new Promise((resolve, reject) => {
    console.log("[captureMapArea] Начало захвата карты с параметрами:", { targetCellX, targetCellY, regionSize, showCellLabels, sides });
    
    // Получаем конфигурацию
    const conf = Config.get();
    console.log("[captureMapArea] Загружена конфигурация:", conf);
    const CELL_SIZE = 100; // размер игровой ячейки (в метрах)
    const MAX_ZOOM = conf.maxZoom || 9;
    const MAP_SIZE_METERS = conf.islandWidth || 15360;
    const mapImageWidth = conf.mapImageWidth || 32768;
    const PIXELS_PER_METER_ZOOM_7 = mapImageWidth / MAP_SIZE_METERS;
    const WINDOW_MARGIN = 0.1; // дополнительный запас 10%

    // Вычисляем центр в игровых координатах
    const centerX = targetCellX * CELL_SIZE + CELL_SIZE / 2;
    const centerY = targetCellY * CELL_SIZE + CELL_SIZE / 2;
    console.log("[captureMapArea] Игровой центр:", { centerX, centerY });

    // Определяем область захвата: 2*regionSize+1 ячеек
    const areaCells = 2 * regionSize + 1;
    const areaMeters = areaCells * CELL_SIZE;
    const minX = centerX - areaMeters / 2;
    const maxX = centerX + areaMeters / 2;
    const minY = centerY - areaMeters / 2;
    const maxY = centerY + areaMeters / 2;
    console.log("[captureMapArea] Область захвата (в метрах):", { minX, maxX, minY, maxY });

    // Преобразуем в координаты Leaflet
    const centerLatLng = gameToLatLng(centerX, centerY, conf);
    console.log("[captureMapArea] Центр карты (Leaflet):", centerLatLng);

    // Определяем оптимальный зум и размеры offscreen-контейнера
    let zoom = MAX_ZOOM;
    let pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
    let windowWidth = areaMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
    let windowHeight = areaMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
    const MAX_WINDOW_SIZE = 2000;
    while ((windowWidth > MAX_WINDOW_SIZE || windowHeight > MAX_WINDOW_SIZE) && zoom > 2) {
      zoom--;
      pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
      windowWidth = areaMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
      windowHeight = areaMeters * pixelsPerMeter * (1 + WINDOW_MARGIN);
    }
    windowWidth = Math.round(Math.min(windowWidth, MAX_WINDOW_SIZE));
    windowHeight = Math.round(Math.min(windowHeight, MAX_WINDOW_SIZE));
    console.log("[captureMapArea] Определён зум и размеры:", { zoom, windowWidth, windowHeight });

    // Область для запросов зданий/названий
    const area = { minX, maxX, minY, maxY };

    // Создаём скрытый контейнер (не используя display:none)
    const hiddenContainer = document.createElement('div');
    hiddenContainer.style.position = 'absolute';
    hiddenContainer.style.top = '-9999px';
    hiddenContainer.style.left = '-9999px';
    hiddenContainer.style.width = `${windowWidth}px`;
    hiddenContainer.style.height = `${windowHeight}px`;
    document.body.appendChild(hiddenContainer);
    console.log("[captureMapArea] Скрытый контейнер создан.");

    // Инициализируем offscreen-карту
    const offscreenMap = L.map(hiddenContainer, {
      crs: L.CRS.Simple,
      zoomControl: false,
      attributionControl: false,
      doubleClickZoom: false,
      dragging: false,
      scrollWheelZoom: false,
      boxZoom: false,
      keyboard: false
    });
    console.log("[captureMapArea] Offscreen-карта инициализирована.");

    // Добавляем тайловый слой
    const tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
      noWrap: true,
      attribution: "Карта Chernarus",
      tileBuffer: 2,
      maxNativeZoom: 7,
      maxZoom: MAX_ZOOM,
      bounds: [[-32768, -32768], [32768, 32768]],
      getTileUrl: function(coords) {
        if (coords.x < 0 || coords.y < 0) {
          return '/transparent.png';
        }
        return L.Util.template(this._url, { z: coords.z, x: coords.x, y: coords.y });
      }
    }).addTo(offscreenMap);
    console.log("[captureMapArea] Тайловый слой добавлен.");

    // Устанавливаем вид карты (центр, зум)
    offscreenMap.setView([centerLatLng.lat, centerLatLng.lng], zoom);
    console.log("[captureMapArea] Вид карты установлен:", { centerLatLng, zoom });

    // Добавляем дополнительные слои: GridLayer, NamesLayer и UnitLayer
    var gridLayerInstance = new GridLayer();
    gridLayerInstance.addTo(offscreenMap);
    console.log("[captureMapArea] GridLayer добавлен.");

    var namesLayerInstance = new NamesLayer();
    namesLayerInstance.addTo(offscreenMap);
    console.log("[captureMapArea] NamesLayer добавлен.");

    var unitLayerInstance = new UnitLayer();
    unitLayerInstance.addTo(offscreenMap);
    console.log("[captureMapArea] UnitLayer добавлен.");
	
    if (window.unitLayer && window.unitLayer._lastData) {
      console.log("[captureMapArea] Копирование актуальных данных в offscreen UnitLayer...");
      unitLayerInstance.updateData(window.unitLayer._lastData, []); // Передаем последние данные, отчеты здесь не нужны
      console.log("[captureMapArea] Данные для UnitLayer скопированы.");
    } else {
      console.warn("[captureMapArea] Не найдены данные в основном unitLayer для копирования.");
    }

    // Принудительная перерисовка (если соответствующие методы определены)
    if (typeof gridLayerInstance._redraw === "function") {
      gridLayerInstance._redraw();
      console.log("[captureMapArea] Перерисовка GridLayer выполнена.");
    }
    if (typeof namesLayerInstance._createMarkers === "function") {
      namesLayerInstance._createMarkers();
      console.log("[captureMapArea] Маркеры NamesLayer созданы.");
    }

    // Отключаем интерактивность карты
    offscreenMap.dragging.disable();
    offscreenMap.touchZoom.disable();
    offscreenMap.doubleClickZoom.disable();
    offscreenMap.scrollWheelZoom.disable();

    // После загрузки тайлов ждём окончательного рендеринга
    tileLayer.on('load', function() {
      console.log("[captureMapArea] Тайлы загружены. Дополнительное ожидание для рендеринга...");
      setTimeout(() => {
        console.log("[captureMapArea] Запуск html2canvas для offscreen-контейнера.");
		html2canvas(hiddenContainer, {
		  useCORS: true, // Важно для загрузки тайлов с другого домена, если потребуется
		  onclone: (clonedDoc) => {
			// onclone вызывается на клонированной копии DOM перед рендерингом
			const hiddenMapElement = clonedDoc.querySelector('.leaflet-container');
			if (!hiddenMapElement) return;

			// Находим панель с тайлами и панель с оверлеями (маркеры, сетка)
			const tilePane = hiddenMapElement.querySelector('.leaflet-tile-pane');
			const overlayPane = hiddenMapElement.querySelector('.leaflet-overlay-pane');

			if (tilePane && overlayPane) {
			  console.log("[captureMapArea | onclone] Найдены панели тайлов и оверлеев. Попытка перемещения...");
			  // Это ключевой трюк: мы делаем панель с тайлами дочерним элементом
			  // панели с оверлеями. Это помогает html2canvas правильно их "увидеть".
			  overlayPane.appendChild(tilePane);
			  // Сбрасываем CSS-трансформации, которые могут мешать html2canvas
			  tilePane.style.transform = 'none';
			} else {
			  console.warn("[captureMapArea | onclone] Не удалось найти панели тайлов или оверлеев.");
			}
		  }
		}).then(canvas => {
          const mapImage = canvas.toDataURL("image/png");
          console.log("[captureMapArea] Снимок карты получен.");

          // Сохраняем снимок в папку snapshots через /save_snapshot
          const snapshotFileName = "snapshot_" + new Date().toISOString().replace(/[:.]/g, "-") + ".png";
          console.log("[captureMapArea] Сохранение снимка с именем:", snapshotFileName);
          fetch('/save_snapshot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: mapImage, filename: snapshotFileName })
          })
          .then(resp => resp.json())
          .then(saveResult => {
            console.log("[captureMapArea] Снимок успешно сохранён:", saveResult);
          })
          .catch(err => {
            console.error("[captureMapArea] Ошибка сохранения снимка:", err);
          });

          // Запрашиваем данные зданий из базы с ограничением области и сохраняем JSON
          fetch('/get_buildings', {
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
            const filenameBuildings = "buildings_snapshot_" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
            console.log("[captureMapArea] Сохранение JSON зданий с именем:", filenameBuildings);
            return fetch('/save_json', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filename: filenameBuildings, data: buildingsJson })
            });
          })
          .then(resp => resp.json())
          .then(result => {
            console.log("[captureMapArea] Buildings JSON успешно сохранён:", result);
          })
          .catch(err => {
            console.error("[captureMapArea] Ошибка получения/сохранения зданий:", err);
          });

          // Запрашиваем данные названий из базы с ограничением области и сохраняем JSON
          fetch('/get_names_in_area', {
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
            const filenameNames = "names_snapshot_" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
            console.log("[captureMapArea] Сохранение JSON названий с именем:", filenameNames);
            return fetch('/save_json', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filename: filenameNames, data: namesJson })
            });
          })
          .then(resp => resp.json())
          .then(result => {
            console.log("[captureMapArea] Names JSON успешно сохранён:", result);
          })
          .catch(err => {
            console.error("[captureMapArea] Ошибка получения/сохранения названий:", err);
          })
          .finally(() => {
            // Фильтрация маркеров по сторонам:
            // Если параметр sides задан и не пуст, то первый элемент – выбранная сторона (полные данные из unitLayer._groupLayer),
            // а для остальных сторон (противоположных) берём маркеры из unitLayer._reportGroupLayer.
            const bounds = offscreenMap.getBounds();
            console.log("[captureMapArea] Границы offscreen-карты:", bounds);
            const objects = [];
            let chosenSide = (sides && sides.length > 0) ? sides[0] : null;
            if (window.unitLayer) {
              // Отбираем маркеры для выбранной стороны из полного слоя
              if (window.unitLayer._groupLayer) {
                window.unitLayer._groupLayer.eachLayer(marker => {
                  if (bounds.contains(marker.getLatLng())) {
                    if (!chosenSide || marker.options.data.side === chosenSide) {
                      objects.push(marker.options.data);
                    }
                  }
                });
                console.log("[captureMapArea] Маркеры для выбранной стороны из полного слоя:", objects);
              }
              // Отбираем маркеры для противоположных сторон из слоя докладов
              if (window.unitLayer._reportGroupLayer) {
                window.unitLayer._reportGroupLayer.eachLayer(marker => {
                  if (bounds.contains(marker.getLatLng())) {
                    if (chosenSide && marker.options.data.side !== chosenSide) {
                      objects.push(marker.options.data);
                    }
                  }
                });
                console.log("[captureMapArea] Дополнительные маркеры для противоположных сторон из слоя докладов добавлены.");
              }
            } else {
              console.warn("[captureMapArea] Глобальный unitLayer недоступен.");
            }
            // Для labels оставляем без фильтрации (как в предыдущем варианте)
            const labels = [];
            if (window.namesLayer && window.namesLayer._namesGroup) {
              window.namesLayer._namesGroup.eachLayer(marker => {
                if (bounds.contains(marker.getLatLng())) {
                  labels.push(marker.options.data);
                }
              });
              console.log("[captureMapArea] Собраны надписи из namesLayer:", labels);
            } else {
              console.warn("[captureMapArea] namesLayer или его группа недоступны.");
            }

            // Очистка offscreen-карты и скрытого контейнера
            offscreenMap.remove();
            document.body.removeChild(hiddenContainer);
            console.log("[captureMapArea] Offscreen-карта и скрытый контейнер удалены.");
            // Возвращаем итоговые данные
            resolve({
              mapImage: mapImage,
              objects: objects,
              labels: labels
            });
          });
        }).catch(err => {
          console.error("[captureMapArea] Ошибка в html2canvas:", err);
          offscreenMap.remove();
          document.body.removeChild(hiddenContainer);
          reject(err);
        });
      }, 2000);
    });

    // Если тайлы не загрузятся за 10 секунд, возвращаем ошибку
    setTimeout(() => {
      if (!offscreenMap._loaded) {
        console.error("[captureMapArea] Тайловый слой не загрузился за отведённое время.");
        offscreenMap.remove();
        if (document.body.contains(hiddenContainer)) {
          document.body.removeChild(hiddenContainer);
        }
        reject(new Error("Тайловый слой не загрузился за отведённое время."));
      }
    }, 10000);
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