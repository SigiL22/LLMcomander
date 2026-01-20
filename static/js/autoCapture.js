// js/autoCapture.js

/**
 * Главная функция: Анализирует миссию, делает снимки, грузит их и запускает LLM.
 */
async function performInitialCaptureAndSend() {
    console.log("=== [AutoCapture] ЗАПУСК ЦЕПОЧКИ ИНИЦИАЛИЗАЦИИ ===");
    
    const mySide = window.missionSettings.llmSide;
    // window.missionMarkers мы сохраним в armaDataFetcher.js (см. Шаг 5)
    const markers = window.missionMarkers || []; 
    
    if (!mySide) {
        console.error("[AutoCapture] Сторона LLM не выбрана! Прерывание.");
        return;
    }

    console.log(`[AutoCapture] Сторона: ${mySide}. Маркеров: ${markers.length}`);

    // 1. Поиск маркеров атаки (a-<side>) и обороны (d-<side>)
    // Превращаем "EAST" -> "opfor" для поиска в тексте маркера
    let searchSide = mySide.toLowerCase();
    if (searchSide === 'east') searchSide = 'opfor';
    if (searchSide === 'west') searchSide = 'blufor';
    if (searchSide === 'guer' || searchSide === 'independent') searchSide = 'independent'; // или guer, зависит от того как вы пишете в редакторе

    // Ищем маркер, в тексте которого есть 'a-opfor' (атака) или 'd-opfor' (оборона)
    const attackMarker = markers.find(m => m.text && m.text.toLowerCase().includes(`a-${searchSide}`));
    const defenseMarker = markers.find(m => m.text && m.text.toLowerCase().includes(`d-${searchSide}`));
    
    // Настройки радиуса для тактического (детального) снимка
    const tacticalRadiusMeters = 600; 
    const tacticalRadiusCells = tacticalRadiusMeters / 100;
    
    let snapshots = [];

    // --- СЦЕНАРИЙ 1: ОБОРОНА ---
    if (defenseMarker) {
        console.log("[AutoCapture] Обнаружен режим ОБОРОНА. Цель:", defenseMarker.text);
        
        const mX = Math.floor(defenseMarker.pos[0] / 100);
        const mY = Math.floor(defenseMarker.pos[1] / 100);
        
        // Делаем один детальный снимок вокруг точки обороны
        try {
            const result = await captureMapArea(
                mX, mY, 
                tacticalRadiusCells, tacticalRadiusCells, 
                true,       // showLabels (сетка)
                [mySide],   // сторона (для фильтра юнитов)
                false       // skipDetails=FALSE (нам нужен JSON зданий для обороны!)
            );
            
            snapshots.push({ 
                type: "tactical", 
                image: result.mapImage, 
                filename: `snap_defense_tac_${Date.now()}.png` 
            });
        } catch (e) {
            console.error("[AutoCapture] Ошибка съемки обороны:", e);
        }
    }

    // --- СЦЕНАРИЙ 2: АТАКА ---
    else if (attackMarker) {
        console.log("[AutoCapture] Обнаружен режим АТАКА. Цель:", attackMarker.text);
        
        const mX = Math.floor(attackMarker.pos[0] / 100);
        const mY = Math.floor(attackMarker.pos[1] / 100);
        
        // А. Тактический снимок (Финиш) - Вокруг цели
        try {
            console.log("[AutoCapture] Снимаем цель...");
            const tacResult = await captureMapArea(
                mX, mY, 
                tacticalRadiusCells, tacticalRadiusCells, 
                true, 
                [mySide], 
                false // JSON зданий нужен, чтобы штурмовать дома
            );
            snapshots.push({ 
                type: "tactical", 
                image: tacResult.mapImage, 
                filename: `snap_attack_tac_${Date.now()}.png` 
            });
        } catch (e) {
            console.error("[AutoCapture] Ошибка съемки цели:", e);
        }
        
        // Б. Стратегический снимок (Маршрут)
        // Нам нужно найти где наши войска
        const friendlyCenter = getFriendlyCenterOfMass(mySide);
        
        if (friendlyCenter) {
            // Считаем рамку, чтобы влезли и мы, и цель
            const stratParams = calculateStrategicParams(
                friendlyCenter, 
                { x: attackMarker.pos[0], y: attackMarker.pos[1] }
            );
            
            console.log("[AutoCapture] Параметры стратегического снимка:", stratParams);
            
            // Ограничитель: если карта получается больше 5x5 км (50 ячеек радиус),
            // лучше ограничить, иначе ничего не будет видно.
            // Прижимаем камеру к цели, но захватываем кусок маршрута.
            if (stratParams.regionSizeX > 25) stratParams.regionSizeX = 25;
            if (stratParams.regionSizeY > 25) stratParams.regionSizeY = 25;

            try {
                console.log("[AutoCapture] Снимаем общий план...");
                const stratResult = await captureMapArea(
                    stratParams.cellX,
                    stratParams.cellY,
                    stratParams.regionSizeX,
                    stratParams.regionSizeY,
                    false,      // Лейблы сетки можно выключить для чистоты
                    [mySide],
                    true        // skipDetails=TRUE (Не генерируем JSON зданий для огромной карты!)
                );
                
                snapshots.push({ 
                    type: "strategic", 
                    image: stratResult.mapImage, 
                    filename: `snap_attack_strat_${Date.now()}.png` 
                });
            } catch (e) {
                console.error("[AutoCapture] Ошибка съемки маршрута:", e);
            }
        } else {
            console.warn("[AutoCapture] Не удалось найти войска для расчета маршрута. Снят только тактический снимок.");
        }
    } else {
        console.warn("[AutoCapture] Не найдены маркеры a-side или d-side. Пропуск съемки.");
        // Даже если снимков нет, мы должны пнуть LLM, чтобы она инициализировалась (хотя бы текстом)
        // Но в вашей логике server.py ждет снимки, если они есть. Если их нет, отправит так.
    }

    // 2. Загрузка снимков на сервер
    if (snapshots.length > 0) {
        console.log(`[AutoCapture] Загрузка ${snapshots.length} снимков на сервер...`);
        try {
            const uploadResp = await fetch('/upload_mission_snapshots', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ snapshots: snapshots })
            });
            const uploadResult = await uploadResp.json();
            console.log("[AutoCapture] Результат загрузки:", uploadResult);
        } catch (e) {
            console.error("[AutoCapture] Ошибка сети при загрузке снимков:", e);
            return; // Не запускаем LLM, если загрузка упала (или запускаем? Решать вам. Лучше не запускать, чтобы не рассинхронить)
        }
    } else {
        console.log("[AutoCapture] Снимков нет. Запускаем LLM только на текстовых данных.");
    }

    // 3. Финальный пинок: Запуск инициализации LLM
    try {
        console.log("[AutoCapture] Отправка сигнала /initiate_llm_start...");
        const initResp = await fetch('/initiate_llm_start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ side: mySide })
        });
        const initResult = await initResp.json();
        console.log("[AutoCapture] Ответ сервера инициализации:", initResult);
    } catch (e) {
        console.error("[AutoCapture] Ошибка вызова /initiate_llm_start:", e);
    }
}