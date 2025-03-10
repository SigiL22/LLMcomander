// js/capture.js

function openMapWindow(xxx, yyy, m, showCellLabels = false) {
  const conf = Config.get();
  const CELL_SIZE = 100;
  const MAX_ZOOM = conf.maxZoom || 9;
  const MAP_SIZE_METERS = conf.islandWidth || 15360;
  const MAP_SIZE_PIXELS_ZOOM_7 = conf.mapImageWidth || 32768;
  const PIXELS_PER_METER_ZOOM_7 = MAP_SIZE_PIXELS_ZOOM_7 / MAP_SIZE_METERS;
  const MAX_WINDOW_SIZE = 1400;
  const WINDOW_MARGIN = 0.1;
  const TILE_LOAD_TIMEOUT = 5000;

  console.log(`[openMapWindow] Запуск: xxx=${xxx}, yyy=${yyy}, m=${m}, showCellLabels=${showCellLabels}`);

  const centerX = xxx * CELL_SIZE + CELL_SIZE / 2;
  const centerY = yyy * CELL_SIZE + CELL_SIZE / 2;
  const areaCells = 2 * m + 1; // Например, для m=5 -> 11 ячеек
  const areaMeters = areaCells * CELL_SIZE; // Полная ширина/высота в метрах (1100 м для m=5)
  const minX = centerX - areaMeters / 2;
  const maxX = centerX + areaMeters / 2;
  const minY = centerY - areaMeters / 2;
  const maxY = centerY + areaMeters / 2;

  // Кэшируем LatLng
  const centerLatLng = gameToLatLng(centerX, centerY, conf);
  const sw = gameToLatLng(minX, minY, conf);
  const ne = gameToLatLng(maxX, maxY, conf);

  // Расчет оптимального зума и размера окна
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
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
        <script src="https://unpkg.com/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <script src="js/config.js"></script>
        <script src="js/gameToLatLng.js"></script>
        <script src="js/gridLayer.js"></script>
        <script src="js/namesLayer.js"></script>
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

          // Устанавливаем центр и зум без подгонки
          map.setView([${centerLatLng.lat}, ${centerLatLng.lng}], ${zoom});

          Config.apply();
          setTimeout(() => gridLayer._redraw && gridLayer._redraw(), 100);

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