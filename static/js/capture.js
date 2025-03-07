// js/capture.js

function captureMapArea(xxx, yyy, m, num) {
  // Константы
  const CELL_SIZE = 100; // Размер ячейки в метрах
  const MAX_ZOOM = 9;    // Максимальный зум
  const MAX_RESOLUTION = 1572; // Максимальное разрешение в пикселях
  const BORDER_OFFSET = 50; // Дополнительное пространство для окантовки (в пикселях)

  console.log(`Запуск captureMapArea: xxx=${xxx}, yyy=${yyy}, m=${m}, num=${num}`);

  // Преобразуем координаты ячейки в игровые метры (левый нижний угол)
  const centerX = xxx * CELL_SIZE;
  const centerY = yyy * CELL_SIZE;

  // Рассчитываем размеры области
  const areaCells = 2 * m + 1;
  const areaMeters = m * CELL_SIZE; // Половина ширины/высоты области

  // Определяем симметричные границы
  const minX = centerX - areaMeters;
  const maxX = centerX + areaMeters;
  const minY = centerY - areaMeters;
  const maxY = centerY + areaMeters;

  // Преобразуем в LatLng
  const sw = gameToLatLng(minX, minY);
  const ne = gameToLatLng(maxX, maxY);
  const bounds = L.latLngBounds(sw, ne);

  // Временное включение подписей ячеек
  const conf = Config.get();
  const originalShowCellCoords = conf.cellCoordStyle.show;
  if (num) {
    conf.cellCoordStyle.show = true;
    Config.set(conf);
    if (window.gridLayer && typeof gridLayer._redraw === "function") {
      gridLayer._redraw();
    }
  }

  // Устанавливаем зум
  let zoom = MAX_ZOOM;
  map.setView(bounds.getCenter(), zoom);
  let pixelWidth = Math.abs(map.project(ne, zoom).x - map.project(sw, zoom).x);
  let pixelHeight = Math.abs(map.project(ne, zoom).y - map.project(sw, zoom).y);

  while ((pixelWidth > MAX_RESOLUTION || pixelHeight > MAX_RESOLUTION) && zoom > 2) {
    zoom--;
    map.setZoom(zoom);
    pixelWidth = Math.abs(map.project(ne, zoom).x - map.project(sw, zoom).x);
    pixelHeight = Math.abs(map.project(ne, zoom).y - map.project(sw, zoom).y);
  }

  // Увеличиваем область захвата, чтобы включить окантовку
  pixelWidth = 960 + BORDER_OFFSET * 2; // Добавляем место для окантовки слева и справа
  pixelHeight = 960 + BORDER_OFFSET * 2; // Добавляем место для окантовки сверху и снизу

  console.log(`Выбранный зум: ${zoom}, размер области: ${pixelWidth}x${pixelHeight} пикселей`);
  map.fitBounds(bounds);

  // Ожидаем загрузки тайлов
  const waitForTiles = new Promise((resolve) => {
    let tileLayer;
    map.eachLayer(layer => {
      if (layer instanceof L.TileLayer) {
        tileLayer = layer;
      }
    });

    if (!tileLayer) {
      console.log("Слой тайлов не найден, продолжаем");
      resolve();
      return;
    }

    let loaded = false;
    tileLayer.on('tileload', () => {
      console.log("Тайлы загружены (tileload)");
      loaded = true;
      setTimeout(resolve, 2000); // Задержка для рендеринга
    });

    tileLayer.on('tileerror', () => {
      console.warn("Ошибка загрузки тайлов, продолжаем");
      resolve();
    });

    tileLayer.redraw(); // Принудительно обновляем тайлы

    setTimeout(() => {
      if (!loaded) {
        console.log("Тайлы не загрузились за 20 секунд, продолжаем");
        resolve();
      }
    }, 20000);
  });

  // Захват после загрузки
  waitForTiles.then(() => {
    const mapElement = document.getElementById('map');
    const mapSize = map.getSize();
    const centerLatLng = bounds.getCenter();
    const centerPixel = map.project(centerLatLng, zoom);
    const pixelBounds = map.getPixelBounds();

    // Корректируем центр с учётом смещения на пол-ячейки (50 метров)
    const halfCellPixelX = map.project(gameToLatLng(centerX + 50, centerY)).x - centerPixel.x;
    const halfCellPixelY = map.project(gameToLatLng(centerX, centerY + 50)).y - centerPixel.y;
    const correctedCenterPixelX = centerPixel.x + halfCellPixelX * 0.5; // Компенсация на 0.5 ячейки
    const correctedCenterPixelY = centerPixel.y + halfCellPixelY * 0.5;

    // Рассчитываем координаты захвата относительно корректированного центра
    const offsetX = correctedCenterPixelX - (pixelWidth / 2) - pixelBounds.min.x;
    const offsetY = correctedCenterPixelY - (pixelHeight / 2) - pixelBounds.min.y;

    // Корректируем, чтобы оставаться в пределах контейнера, с учётом окантовки
    const correctedOffsetX = Math.max(-BORDER_OFFSET, Math.min(offsetX, mapSize.x - pixelWidth + BORDER_OFFSET));
    const correctedOffsetY = Math.max(-BORDER_OFFSET, Math.min(offsetY, mapSize.y - pixelHeight + BORDER_OFFSET));

    console.log(`Захват области: x=${correctedOffsetX}, y=${correctedOffsetY}, width=${pixelWidth}, height=${pixelHeight}`);
    console.log(`Размер карты: ${mapSize.x}x${mapSize.y}, pixelBounds: min=${pixelBounds.min.x},${pixelBounds.min.y}, max=${pixelBounds.max.x},${pixelBounds.max.y}`);

    // Проверяем загруженные тайлы
    const tileImages = mapElement.querySelectorAll('.leaflet-tile-pane img');
    tileImages.forEach(img => console.log(`Тайл: ${img.src}, загружен: ${img.complete}, размер: ${img.naturalWidth}x${img.naturalHeight}`));

    html2canvas(mapElement, {
      useCORS: true,
      width: pixelWidth,
      height: pixelHeight,
      x: correctedOffsetX,
      y: correctedOffsetY,
      logging: true,
      onclone: (doc) => {
        const clonedMap = doc.getElementById('map');
        clonedMap.style.backgroundColor = '#fff';
        const tilePane = clonedMap.querySelector('.leaflet-tile-pane');
        const overlayPane = clonedMap.querySelector('.leaflet-overlay-pane');
        if (tilePane && overlayPane) {
          tilePane.style.opacity = '1'; // Устанавливаем непрозрачность тайлов
          overlayPane.appendChild(tilePane); // Переносим тайлы в overlayPane
        }
        clonedMap.querySelectorAll('.leaflet-layer, .leaflet-overlay-pane').forEach(layer => {
          layer.style.transform = 'none';
        });
        // Явно включаем слои сетки
        const gridLayers = clonedMap.querySelectorAll('.leaflet-grid-layer');
        gridLayers.forEach(layer => {
          layer.style.display = 'block';
          layer.style.opacity = '0.5'; // Прозрачность сетки
          layer.style.zIndex = '1000'; // Сетка поверх
          console.log('Слой сетки найден:', layer);
        });
        // Проверяем содержимое overlayPane
        console.log('Содержимое overlayPane:', overlayPane.innerHTML);
      }
    }).then(canvas => {
      const dataUrl = canvas.toDataURL('image/png');
      console.log("Снимок создан, размер:", canvas.width, "x", canvas.height);

      // Временно добавляем canvas на страницу для проверки
      document.body.appendChild(canvas);
      canvas.style.position = 'absolute';
      canvas.style.top = '10px';
      canvas.style.left = '10px';
      canvas.style.border = '1px solid red';

      fetch('/save_snapshot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: dataUrl,
          filename: `snapshot_${xxx}_${yyy}_m${m}_z${zoom}.png`
        })
      })
      .then(response => response.json())
      .then(result => {
        console.log("Снимок сохранен:", result);
      })
      .catch(err => console.error("Ошибка сохранения снимка:", err));

      // Восстанавливаем настройки
      if (num) {
        conf.cellCoordStyle.show = originalShowCellCoords;
        Config.set(conf);
        if (window.gridLayer && typeof gridLayer._redraw === "function") {
          gridLayer._redraw();
        }
      }
    }).catch(err => console.error("Ошибка создания снимка:", err));
  });
}

window.captureMapArea = captureMapArea;