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
    // 1. Находим границы миссии (минимумы и максимумы)
    const minMissionX = Math.min(p1.x, p2.x);
    const maxMissionX = Math.max(p1.x, p2.x);
    const minMissionY = Math.min(p1.y, p2.y);
    const maxMissionY = Math.max(p1.y, p2.y);

    // 2. ФИКСИРОВАННЫЙ БУФЕР (в метрах)
    // Добавляем по 2000 метров с каждой стороны.
    // Это гарантирует, что за точкой старта и целью всегда будет 2км карты.
    const bufferMeters = 2000; 

    // 3. Вычисляем размеры области обзора
    const viewWidth = (maxMissionX - minMissionX) + (bufferMeters * 2);
    const viewHeight = (maxMissionY - minMissionY) + (bufferMeters * 2);

    // 4. Вычисляем центр этой области
    // (min + max) / 2, но с учетом расширенных границ
    const viewMinX = minMissionX - bufferMeters;
    const viewMinY = minMissionY - bufferMeters;
    
    const centerX = viewMinX + viewWidth / 2;
    const centerY = viewMinY + viewHeight / 2;

    // 5. Переводим в "радиусы ячеек" (половина стороны / 100)
    let rX = Math.ceil((viewWidth / 2) / 100);
    let rY = Math.ceil((viewHeight / 2) / 100);

    // Минимальный размер (на всякий случай, хотя буфер уже дал 20 ячеек)
    if (rX < 15) rX = 40;
    if (rY < 15) rY = 40;

    console.log(`[mapUtils] Стратегический расчет: Буфер=${bufferMeters}m. Размер области: ${Math.round(viewWidth)}x${Math.round(viewHeight)}m`);

    return {
        cellX: Math.floor(centerX / 100),
        cellY: Math.floor(centerY / 100),
        regionSizeX: rX,
        regionSizeY: rY
    };
}