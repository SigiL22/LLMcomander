// js/mapUtils.js

/**
 * Находит центр масс (среднюю точку) всех известных групп указанной стороны.
 * Использует данные из unitLayer, так как там самые свежие координаты.
 * 
 * @param {string} side - Сторона (например, "OPFOR", "BLUFOR")
 * @returns {Object|null} - Объект {x, y} в игровых метрах или null, если групп нет.
 */
function getFriendlyCenterOfMass(side) {
    // Проверка: есть ли данные о юнитах вообще
    if (!window.unitLayer || !window.unitLayer._lastData || !window.unitLayer._lastData.sides) {
        console.warn("[mapUtils] Нет данных о юнитах для расчета центра масс.");
        return null;
    }

    // Нормализация стороны (на случай если в настройках 'EAST', а в данных 'OPFOR')
    // Но обычно unitLayer._lastData.sides использует ключи как прислала Арма (OPFOR/BLUFOR)
    
    // Ищем подходящий ключ в объекте sides
    let targetKey = side;
    const sidesObj = window.unitLayer._lastData.sides;
    
    // Простая эвристика для поиска ключа, если прямого совпадения нет
    if (!sidesObj[targetKey]) {
        if (side === "EAST" && sidesObj["OPFOR"]) targetKey = "OPFOR";
        else if (side === "OPFOR" && sidesObj["EAST"]) targetKey = "EAST";
        else if (side === "WEST" && sidesObj["BLUFOR"]) targetKey = "BLUFOR";
        else if (side === "BLUFOR" && sidesObj["WEST"]) targetKey = "WEST";
        else if ((side === "GUER" || side === "INDEPENDENT") && sidesObj["Independent"]) targetKey = "Independent";
    }

    const groups = sidesObj[targetKey];
    if (!groups || groups.length === 0) return null;

    let sumX = 0;
    let sumY = 0;
    let count = 0;

    groups.forEach(group => {
        // group.p - это [x, y, z, dir]
        if (group.p && group.p.length >= 2) {
            sumX += group.p[0];
            sumY += group.p[1];
            count++;
        }
    });

    if (count === 0) return null;

    const centerX = sumX / count;
    const centerY = sumY / count;

    console.log(`[mapUtils] Центр масс для ${side} (групп: ${count}): X=${centerX}, Y=${centerY}`);
    return { x: centerX, y: centerY };
}

/**
 * Рассчитывает параметры для captureMapArea (центр и радиусы), 
 * чтобы в кадр попали две точки (startPoint и endPoint).
 * 
 * @param {Object} p1 - {x, y} (Наши войска)
 * @param {Object} p2 - {x, y} (Цель)
 * @returns {Object} - { cellX, cellY, regionSizeX, regionSizeY } для функции captureMapArea
 */
function calculateStrategicParams(p1, p2) {
    // 1. Находим геометрический центр между двумя точками
    const midX = (p1.x + p2.x) / 2;
    const midY = (p1.y + p2.y) / 2;

    // 2. Вычисляем расстояние по осям (абсолютная разница)
    const diffX = Math.abs(p1.x - p2.x);
    const diffY = Math.abs(p1.y - p2.y);

    // 3. Добавляем отступы (padding), чтобы точки не были на самом краю экрана
    // 1.3 = +30% запаса места
    const padding = 1.3; 
    const totalWidthMeters = diffX * padding;
    const totalHeightMeters = diffY * padding;

    // 4. Конвертируем в "радиусы ячеек" для captureMapArea
    // regionSize - это расстояние от центра до края. То есть половина ширины.
    // 1 ячейка = 100 метров.
    
    // Минимум 5 ячеек (500м радиус), чтобы совсем в упор не снимать
    let rX = Math.ceil((totalWidthMeters / 2) / 100);
    if (rX < 5) rX = 5;

    let rY = Math.ceil((totalHeightMeters / 2) / 100);
    if (rY < 5) rY = 5;

    // 5. Конвертируем центр в координаты ячеек
    const cX = Math.floor(midX / 100);
    const cY = Math.floor(midY / 100);

    return {
        cellX: cX,
        cellY: cY,
        regionSizeX: rX,
        regionSizeY: rY
    };
}