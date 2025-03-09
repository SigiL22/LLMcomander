// js/capture.js

function openMapWindow(xxx, yyy, m, showCellLabels = true) {
  // Константы
  const conf = Config.get();
  const CELL_SIZE = 100; // Размер ячейки в метрах
  const MAX_ZOOM = conf.maxZoom || 9; // По умолчанию 9, если не указано
  const MAP_SIZE_METERS = conf.islandWidth || 15360; // Размер карты в метрах
  const MAP_SIZE_PIXELS_ZOOM_7 = conf.mapImageWidth || 32768; // Размер карты в пикселей на зуме 7
  const PIXELS_PER_METER_ZOOM_7 = MAP_SIZE_PIXELS_ZOOM_7 / MAP_SIZE_METERS; // Динамически вычисляем
  const MAX_WINDOW_SIZE = 1500; // Максимальный размер окна (ширина и высота) остаётся фиксированным
  const WINDOW_MARGIN = 0.1; // Дополнительный запас 10% слева и сверху

  console.log(`[openMapWindow] Запуск функции: xxx=${xxx}, yyy=${yyy}, m=${m}, showCellLabels=${showCellLabels}`);

  // Преобразуем координаты ячейки в игровые метры (центр ячейки)
  const centerX = xxx * CELL_SIZE + CELL_SIZE / 2; // Центр ячейки (например, 27 * 100 + 50 = 2750)
  const centerY = yyy * CELL_SIZE + CELL_SIZE / 2; // Центр ячейки (например, 53 * 100 + 50 = 5350)
  console.log(`[openMapWindow] Центр в метрах: centerX=${centerX}, centerY=${centerY}`);

  // Рассчитываем размеры области
  const areaCells = 2 * m + 1; // Количество ячеек по оси (например, m=5 → 11x11 ячеек)
  const areaMeters = (areaCells * CELL_SIZE) / 2; // Половина ширины/высоты области в метрах
  const minX = centerX - areaMeters;
  const maxX = centerX + areaMeters;
  const minY = centerY - areaMeters;
  const maxY = centerY + areaMeters;
  console.log(`[openMapWindow] Границы области: minX=${minX}, maxX=${maxX}, minY=${minY}, maxY=${maxY}`);

  // Преобразуем в LatLng
  const sw = gameToLatLng(minX, minY);
  const ne = gameToLatLng(maxX, maxY);
  const bounds = L.latLngBounds(sw, ne);
  console.log(`[openMapWindow] Границы в LatLng: SW=${JSON.stringify(sw)}, NE=${JSON.stringify(ne)}`);

  // Инициализируем временную карту для расчёта зума
  const tempMap = L.map(document.createElement('div'), {
    crs: L.CRS.Simple,
    minZoom: 2,
    maxZoom: MAX_ZOOM
  });
  console.log(`[openMapWindow] Временная карта создана для расчёта зума`);

  // Рассчитываем зум и размер окна
  let zoom = MAX_ZOOM;
  let pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
  const areaWidthMeters = maxX - minX; // Например, 1100 метров для m=5
  const areaHeightMeters = maxY - minY;
  let pixelWidth = areaWidthMeters * pixelsPerMeter;
  let pixelHeight = areaHeightMeters * pixelsPerMeter;

  // Уменьшаем зум, пока область не уместится в окно
  let windowWidth = pixelWidth + (pixelWidth * WINDOW_MARGIN); // Запас только слева
  let windowHeight = pixelHeight + (pixelHeight * WINDOW_MARGIN); // Запас только сверху
  while ((windowWidth > MAX_WINDOW_SIZE || windowHeight > MAX_WINDOW_SIZE) && zoom > 2) {
    zoom--;
    pixelsPerMeter = PIXELS_PER_METER_ZOOM_7 * Math.pow(2, zoom - 7);
    pixelWidth = areaWidthMeters * pixelsPerMeter;
    pixelHeight = areaHeightMeters * pixelsPerMeter;
    windowWidth = pixelWidth + (pixelWidth * WINDOW_MARGIN);
    windowHeight = pixelHeight + (pixelHeight * WINDOW_MARGIN);
  }

  // Ограничиваем максимальный размер
  windowWidth = Math.min(windowWidth, MAX_WINDOW_SIZE);
  windowHeight = Math.min(windowHeight, MAX_WINDOW_SIZE);
  console.log(`[openMapWindow] Окончательный размер окна: ${windowWidth}x${windowHeight} пикселей`);

  // Открываем новое окно с динамическими размерами
  const mapWindow = window.open('', 'MapWindow', `width=${windowWidth},height=${windowHeight}`);
  console.log(`[openMapWindow] Новое окно открыто`);

  // Загружаем HTML с картой в новое окно
  mapWindow.document.write(`
    <html>
      <head>
        <title>Map Preview</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <script src="https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <script src="js/config.js"></script> <!-- Настройки -->
        <script src="js/gameToLatLng.js"></script> <!-- Функция преобразования координат -->
        <script src="js/gridLayer.js"></script> <!-- Слой сетки -->
        <script src="js/namesLayer.js"></script> <!-- Слой надписей -->
        <style>
          #map { width: 100%; height: 100%; }
          body { margin: 0; }
        </style>
      </head>
      <body>
        <div id="map"></div>
        <script>
          // Функция для перенаправления логов в консоль родительского окна
          function logToParent(...args) {
            if (window.opener && window.opener.console) {
              window.opener.console.log('[MapWindow]', ...args);
            } else {
              console.log('[MapWindow]', ...args); // Лог в консоль текущего окна
            }
          }

          // Загружаем настройки
          Config.load();
          var conf = Config.get();

          // Устанавливаем отображение подписей ячеек
          conf.cellCoordStyle.show = ${showCellLabels};
          Config.set(conf);

          // Инициализируем карту
          var map = L.map('map', {
            crs: L.CRS.Simple,
            minZoom: 2,
            maxZoom: conf.maxZoom || 9,
            updateWhenIdle: true,
            updateWhenZooming: false,
            zoomControl: false,
            doubleClickZoom: false
          });

          // Добавляем слой тайлов
          var tileLayer = L.tileLayer('http://localhost:5000/tiles/{z}/{x}/{y}.png', {
            noWrap: true,
            attribution: "Карта Chernarus",
            updateWhenIdle: true,
            tileBuffer: 2,
            maxNativeZoom: 7,
            maxZoom: conf.maxZoom || 9,
            bounds: [[-32768, -32768], [32768, 32768]], // Ограничиваем запросы
            getTileUrl: function(coords) {
              if (coords.x < 0 || coords.y < 0) {
                return '/transparent.png';
              }
              return L.Util.template(this._url, L.extend({
                z: coords.z,
                x: coords.x,
                y: coords.y
              }, this.options));
            }
          }).addTo(map);

          tileLayer.on('tileerror', function(error) {
            logToParent('Ошибка загрузки тайла:', error.tile.src, 'Ошибка:', error.error);
          });

          // Добавляем слой сетки
          var gridLayer = new GridLayer();
          gridLayer.addTo(map);

          // Добавляем слой надписей
          var namesLayer = new NamesLayer();
          namesLayer.addTo(map);

          // Устанавливаем центр и зум
          const centerLatLng = gameToLatLng(${centerX}, ${centerY});

          // Устанавливаем зум и границы
          map.setView(centerLatLng, ${zoom});
          map.fitBounds([
            gameToLatLng(${minX}, ${minY}),
            gameToLatLng(${maxX}, ${maxY})
          ], { animate: false, padding: [0, 0] });

          // Корректируем размер окна на основе реального зума
          const finalZoom = map.getZoom();
          const finalPixelsPerMeter = ${PIXELS_PER_METER_ZOOM_7} * Math.pow(2, finalZoom - 7);
          const finalPixelWidth = ${areaWidthMeters} * finalPixelsPerMeter;
          const finalPixelHeight = ${areaHeightMeters} * finalPixelsPerMeter;
          let adjustedWindowWidth = finalPixelWidth + (finalPixelWidth * ${WINDOW_MARGIN});
          let adjustedWindowHeight = finalPixelHeight + (finalPixelHeight * ${WINDOW_MARGIN});
          adjustedWindowWidth = Math.min(adjustedWindowWidth, ${MAX_WINDOW_SIZE});
          adjustedWindowHeight = Math.min(adjustedWindowHeight, ${MAX_WINDOW_SIZE});
          if (adjustedWindowWidth !== ${windowWidth} || adjustedWindowHeight !== ${windowHeight}) {
            window.resizeTo(adjustedWindowWidth, adjustedWindowHeight);
            map.fitBounds([
              gameToLatLng(${minX}, ${minY}),
              gameToLatLng(${maxX}, ${maxY})
            ], { animate: false, padding: [0, 0] });
          }

          // Применяем настройки и обновляем сетку с небольшой задержкой
          Config.apply();
          setTimeout(() => {
            if (gridLayer && typeof gridLayer._redraw === "function") {
              gridLayer._redraw();
            }
          }, 100);

          // Добавляем обработчики событий для обновления сетки
          map.on('zoomend moveend resize', function() {
            if (gridLayer && typeof gridLayer._redraw === "function") {
              gridLayer._redraw();
            }
          });

          // Захват карты и сохранение в файл
          const waitForTiles = new Promise((resolve) => {
            let tileLayer;
            map.eachLayer(layer => {
              if (layer instanceof L.TileLayer) {
                tileLayer = layer;
              }
            });

            if (!tileLayer) {
              logToParent('Слой тайлов не найден, продолжаем');
              resolve();
              return;
            }

            // Отслеживаем количество загруженных и ошибочных тайлов
            let tilesLoaded = 0;
            let tilesErrored = 0;
            const totalTilesExpected = Object.keys(tileLayer._tiles).length || 0;

            tileLayer.on('tileload', () => {
              tilesLoaded++;
              if (tilesLoaded + tilesErrored === totalTilesExpected) {
                logToParent('Все запросы на тайлы завершены');
                setTimeout(resolve, 1000); // Задержка для рендеринга
              }
            });

            tileLayer.on('tileerror', () => {
              tilesErrored++;
              if (tilesLoaded + tilesErrored === totalTilesExpected) {
                logToParent('Все запросы на тайлы завершены');
                setTimeout(resolve, 1000); // Задержка для рендеринга
              }
            });

            tileLayer.redraw(); // Принудительно обновляем тайлы
          });

          // Захват после загрузки
          waitForTiles.then(() => {
            const mapElement = document.getElementById('map');
            const mapSize = map.getSize();

            html2canvas(mapElement, {
              useCORS: true,
              width: mapSize.x,
              height: mapSize.y,
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
                const gridLayers = clonedMap.querySelectorAll('.leaflet-grid-layer');
                gridLayers.forEach(layer => {
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
                  filename: \`snapshot_${xxx}_${yyy}_m${m}_z\${finalZoom}.png\`
                })
              })
              .then(response => response.json())
              .then(result => {
                logToParent('Снимок сохранен');
                window.close();
              })
              .catch(err => {
                logToParent('Ошибка сохранения снимка:', err);
                window.close();
              });
            }).catch(err => {
              logToParent('Ошибка создания снимка:', err);
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