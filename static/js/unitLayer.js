// js/unitLayer.js

function gameToLatLng(x, y, conf) {
    const px = x * (conf.mapImageWidth / conf.islandWidth);
    const py = conf.mapImageHeight - (y * (conf.mapImageHeight / conf.islandHeight));
    return map.unproject([px, py], 7);
}

const unitIcons = {
    "OPFOR": {
        infantry: L.icon({ iconUrl: '/static/ico/r_inf_r.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        vehicle: L.icon({ iconUrl: '/static/ico/r_arm_r.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        waypointCurrent: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-current' }),
        waypointReached: L.icon({ iconUrl: '/static/ico/w_reach.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-reached' }),
        waypointUnreached: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-unreached' })
    },
    "BLUFOR": {
        infantry: L.icon({ iconUrl: '/static/ico/b_inf_s.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        vehicle: L.icon({ iconUrl: '/static/ico/b_arm_s.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        waypointCurrent: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-blufor-current' }),
        waypointReached: L.icon({ iconUrl: '/static/ico/w_reach.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-blufor-reached' }),
        waypointUnreached: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-blufor-unreached' })
    }
};

var UnitLayer = L.Layer.extend({
    initialize: function() {
        this._groupLayer = L.layerGroup();
        this._vehicleLayer = L.layerGroup();
        this._labelLayer = L.layerGroup();
        this._waypointLayer = L.layerGroup();
        this._reportGroupLayer = L.layerGroup();
        this._reportVehicleLayer = L.layerGroup();
        this._lastData = null;
        this.waypointMode = false;
        this.reports = { infantry: {}, vehicles: {} }; // Хранилище докладов
        this.savedReports = {}; // Хранилище сохраненных меток
    },

    onAdd: function(map) {
        this._map = map;
        console.log("Добавляем слои на карту");
        this._groupLayer.addTo(map);
        this._vehicleLayer.addTo(map);
        this._labelLayer.addTo(map);
        this._waypointLayer.addTo(map);
        this._reportGroupLayer.addTo(map);
        this._reportVehicleLayer.addTo(map);
    },

    onRemove: function(map) {
        console.log("Удаляем слои с карты");
        this._groupLayer.removeFrom(map);
        this._vehicleLayer.removeFrom(map);
        this._labelLayer.removeFrom(map);
        this._waypointLayer.removeFrom(map);
        this._reportGroupLayer.removeFrom(map);
        this._reportVehicleLayer.removeFrom(map);
    },

    processReports: function(reports) {
        console.log("Обрабатываем репорты:", reports);
        if (!reports || reports.length === 0) {
            console.log("Репорты пустые или отсутствуют");
            return;
        }
        reports.forEach(report => {
            console.log("Текущий репорт:", report);
            if (report.t === "enemy_detected") {
                const groupId = report.ge || "unknown";
                const side = report.se;
                console.log(`Обнаружен враг: groupId=${groupId}, side=${side}, pos=${report.p}, count=${report.ce}, acc=${report.acc}`);
                if (!this.reports.infantry[side]) this.reports.infantry[side] = {};
                this.reports.infantry[side][groupId] = {
                    pos: report.p,
                    count: report.ce,
                    acc: report.acc
                };
                console.log(`Добавлен/обновлен репорт пехоты: ${side}/${groupId}`);
            } else if (report.t === "vehicle_detected") {
                const vehicleId = report.id;
                const side = report.se;
                console.log(`Обнаружена техника: vehicleId=${vehicleId}, side=${side}, type=${report.vehicle_type}, pos=${report.p}, acc=${report.acc}`);
                if (!this.reports.vehicles[side]) this.reports.vehicles[side] = {};
                this.reports.vehicles[side][vehicleId] = {
                    type: report.vehicle_type,
                    pos: report.p,
                    acc: report.acc
                };
                console.log(`Добавлен/обновлен репорт техники: ${side}/${vehicleId}`);
            }
        });
    },

    updateData: function(jsonData, reports = []) {
        console.log("Вызван updateData с данными:", jsonData);
        if (JSON.stringify(jsonData) === JSON.stringify(this._lastData) && reports.length === 0) {
            console.log("Данные не изменились, пропускаем обновление");
            return;
        }
        this._lastData = jsonData;

        console.log("Очищаем слои точных данных");
        this._groupLayer.clearLayers();
        this._vehicleLayer.clearLayers();
        this._labelLayer.clearLayers();
        this._waypointLayer.clearLayers();
        const conf = Config.get();
        console.log("Конфигурация карты:", conf);

        if (!jsonData || !jsonData.sides) {
            console.error("Некорректные данные от arma_data:", jsonData);
            return;
        }

        const displaySide = window.missionSettings.displaySide || "";
        console.log("Текущая отображаемая сторона (displaySide):", displaySide);

        Object.keys(jsonData.sides).forEach(side => {
            const sideData = jsonData.sides[side];
            console.log(`Обрабатываем сторону: ${side}, групп: ${sideData.length}`);
            sideData.forEach(group => {
                const groupPos = group.p;
                const groupLatLng = gameToLatLng(groupPos[0], groupPos[1], conf);
                const groupIcon = unitIcons[side] ? unitIcons[side].infantry : unitIcons["OPFOR"].infantry;
                const groupTooltip = `
                    <b>${group.n}</b><br>
                    Командир: ${group.c}<br>
                    Юнитов: ${group.co || 'N/A'}<br>
                    Поведение: ${group.b || 'N/A'}<br>
                    Боевой режим: ${group.cm || 'N/A'}<br>
                    Строй: ${group.f || 'N/A'}<br>
                    Скорость: ${group.s || 'N/A'}<br>
                    Открытие огня: ${group.ae ? 'Да' : 'Нет'}${group.cw >= 0 ? `<br>Текущий вэйпойнт: ${group.cw}` : ''}
                `;

                let leaderInVehicle = false;
                let leaderVehicleId = null;
                if (group.u && group.u.length > 0) {
                    const leaderUnit = group.u.find(u => u.n === group.c);
                    if (leaderUnit && leaderUnit.v) {
                        leaderInVehicle = true;
                        leaderVehicleId = leaderUnit.v.id;
                    }
                }

                if (!displaySide || displaySide === side) {
                    console.log(`Отрисовываем группу: ${group.n}, сторона: ${side}`);
                    if (!leaderInVehicle) {
                        const groupMarker = L.marker(groupLatLng, { 
                            icon: groupIcon,
                            data: { side: side, group: group.n }
                        }).addTo(this._groupLayer);
                        groupMarker.bindTooltip(groupTooltip, { 
                            direction: 'top', 
                            offset: [0, -15], 
                            className: 'group-tooltip'
                        });
                        if (this.waypointMode && window.waypointEditor && window.waypointEditor.onGroupClick) {
                            groupMarker.on('click', window.waypointEditor.onGroupClick);
                        }

                        L.marker(groupLatLng, {
                            icon: L.divIcon({
                                html: `<div class="group-label">${group.n}</div>`,
                                className: 'label-marker',
                                iconSize: [100, 20],
                                iconAnchor: [50, -15]
                            })
                        }).addTo(this._labelLayer);
                    }

                    if (group.v && group.v.length > 0) {
                        group.v.forEach(vehicle => {
                            const vehPos = vehicle.p;
                            const vehLatLng = gameToLatLng(vehPos[0], vehPos[1], conf);
                            const vehIcon = unitIcons[side] ? unitIcons[side].vehicle : unitIcons["OPFOR"].vehicle;
                            let vehTooltip = `
                                <b>${vehicle.vn}</b><br>
                                ID: ${vehicle.id}<br>
                                Юнитов: ${vehicle.c}<br>
                                Топливо: ${vehicle.f}<br>
                                Здоровье: ${vehicle.h}
                            `;
                            if (leaderInVehicle && vehicle.id === leaderVehicleId) {
                                vehTooltip += `<br><br><b>Группа: ${group.n}</b><br>
                                    Командир: ${group.c}<br>
                                    Юнитов: ${group.co || 'N/A'}<br>
                                    Поведение: ${group.b || 'N/A'}<br>
                                    Боевой режим: ${group.cm || 'N/A'}<br>
                                    Строй: ${group.f || 'N/A'}<br>
                                    Скорость: ${group.s || 'N/A'}<br>
                                    Открытие огня: ${group.ae ? 'Да' : 'Нет'}${group.cw >= 0 ? `<br>Текущий вэйпойнт: ${group.cw}` : ''}`;
                            }
                            const vehMarker = L.marker(vehLatLng, { 
                                icon: vehIcon,
                                data: { side: side, group: group.n, vehicleId: vehicle.id }
                            }).addTo(this._vehicleLayer);
                            vehMarker.bindTooltip(vehTooltip, { 
                                direction: 'top', 
                                offset: [0, -15], 
                                className: 'vehicle-tooltip'
                            });

                            if (this.waypointMode && window.waypointEditor && window.waypointEditor.onGroupClick) {
                                vehMarker.on('click', window.waypointEditor.onGroupClick);
                            }

                            const labelHtml = `<div class="vehicle-label">${group.n}<br>${vehicle.vn}</div>`;
                            L.marker(vehLatLng, {
                                icon: L.divIcon({
                                    html: labelHtml,
                                    className: 'label-marker',
                                    iconSize: [100, 40],
                                    iconAnchor: [50, -15]
                                })
                            }).addTo(this._labelLayer);
                        });
                    }
                }

                if ((!displaySide || displaySide === side) && group.w && group.w.length > 0) {
                    group.w.forEach(wp => {
                        if (wp.i === 0) return;
                        const wpPos = wp.p;
                        const wpLatLng = gameToLatLng(wpPos[0], wpPos[1], conf);
                        const wpMessage = {
                            side: side,
                            group: group.n,
                            type: wp.t,
                            position: JSON.stringify([wpPos[0], wpPos[1], wpPos[2]]),
                            behaviour: wp.b === "UNCHANGED" ? "" : wp.b,
                            combatMode: wp.cm === "NO CHANGE" ? "" : wp.cm,
                            speed: wp.s === "UNCHANGED" ? "" : wp.s,
                            formation: wp.f === "NO CHANGE" ? "" : wp.f,
                            waypointIndex: wp.i
                        };
                        let wpIcon;
                        if (group.cw === wp.i) {
                            wpIcon = unitIcons[side] ? unitIcons[side].waypointCurrent : unitIcons["OPFOR"].waypointCurrent;
                        } else if (group.cw - 1 === wp.i) {
                            wpIcon = unitIcons[side] ? unitIcons[side].waypointReached : unitIcons["OPFOR"].waypointReached;
                        } else {
                            wpIcon = unitIcons[side] ? unitIcons[side].waypointUnreached : unitIcons["OPFOR"].waypointUnreached;
                        }
                        const marker = L.marker(wpLatLng, { icon: wpIcon });
                        marker.options.data = { 
                            group: group.n, 
                            waypointIndex: wp.i, 
                            params: wpMessage 
                        };
                        const tooltipContent = `
                            Тип: ${wp.t || "N/A"}<br>
                            Поведение: ${wp.b || "N/A"}<br>
                            Боевой режим: ${wp.cm || "N/A"}<br>
                            Скорость: ${wp.s || "N/A"}<br>
                            Строй: ${wp.f || "N/A"}<br>
                            Индекс: ${wp.i}${group.cw - 1 === wp.i ? '<br><b>Достигнут</b>' : group.cw === wp.i ? '<br><b>Текущий</b>' : ''}
                        `;
                        marker.bindTooltip(tooltipContent, { direction: 'top', offset: [0, -15] });
                        if (this.waypointMode && window.waypointEditor && typeof window.waypointEditor.onWaypointDoubleClick === 'function') {
                            marker.on('dblclick', window.waypointEditor.onWaypointDoubleClick);
                        }
                        marker.addTo(this._waypointLayer);

                        const labelIcon = L.divIcon({
                            html: `<div class="group-label">${group.n} #${wp.i}</div>`,
                            className: 'label-marker',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        });
                        const labelMarker = L.marker(wpLatLng, { icon: labelIcon });
                        labelMarker.options.data = { group: group.n, waypointIndex: wp.i };
                        labelMarker.addTo(this._waypointLayer);
                    });
                }
            });
        });

        // Восстанавливаем сохраненные метки после обновления данных
        this.updateReports(reports);
    },

    updateReports: function(reports) {
        console.log("Вызван updateReports с репортами:", reports);
        const displaySide = window.missionSettings.displaySide || "";
        console.log("Отображаемая сторона в updateReports:", displaySide);

        const armaDisplaySide = displaySide === "OPFOR" ? "EAST" : displaySide === "BLUFOR" ? "WEST" : displaySide;
        console.log("Скорректированная сторона для Arma:", armaDisplaySide);

        const filteredReports = armaDisplaySide ? reports.filter(report => report.s === armaDisplaySide) : reports;
        console.log("Отфильтрованные репорты:", filteredReports);
        this.processReports(filteredReports);

        // Обновляем сохраненные репорты последними данными
        filteredReports.forEach(report => {
            if (report.t === "enemy_detected") {
                const groupId = report.ge || "unknown";
                this.savedReports[groupId] = report;
                console.log(`Сохранен последний репорт для группы ${groupId}`);
            } else if (report.t === "vehicle_detected") {
                const vehicleId = report.id;
                this.savedReports[vehicleId] = report;
                console.log(`Сохранен последний репорт для техники ${vehicleId}`);
            }
        });

        console.log("Очищаем слои репортов");
        this._reportGroupLayer.clearLayers();
        this._reportVehicleLayer.clearLayers();
        const conf = Config.get();
        console.log("Конфигурация для updateReports:", conf);

        // Отрисовываем сохраненные репорты
        Object.values(this.savedReports).forEach(report => {
            const enemySide = report.se;
            const armaEnemySide = enemySide === "EAST" ? "OPFOR" : enemySide === "WEST" ? "BLUFOR" : enemySide;
            console.log(`Проверяем репорт: своя сторона=${armaDisplaySide}, сторона противника=${enemySide}`);
            if (armaDisplaySide && armaDisplaySide !== enemySide) {
                console.log(`Условие выполнено: отображаем маркер противника для ${enemySide}`);
                
                const markerSide = armaDisplaySide === "EAST" ? "BLUFOR" : "OPFOR";
                if (report.t === "enemy_detected") {
                    const groupId = report.ge || "unknown";
                    const enemyLatLng = gameToLatLng(report.p[0], report.p[1], conf);
                    console.log(`Координаты маркера противника (пехота): ${enemyLatLng.lat}, ${enemyLatLng.lng}`);
                    const enemyIcon = unitIcons[markerSide].infantry;
                    const enemyTooltip = `
                        <b>${groupId}</b><br>
                        Сторона: ${enemySide}<br>
                        Юнитов: ${report.ce}<br>
                        Точность: ${report.acc} м
                    `;
                    const enemyMarker = L.marker(enemyLatLng, { 
                        icon: enemyIcon,
                        data: { side: enemySide, group: groupId }
                    });
                    console.log(`Добавляем маркер пехоты противника для ${groupId} на слой _reportGroupLayer с иконкой ${markerSide}`);
                    enemyMarker.addTo(this._reportGroupLayer);
                    enemyMarker.bindTooltip(enemyTooltip, { 
                        direction: 'top', 
                        offset: [0, -15], 
                        className: 'group-tooltip'
                    });

                    const labelMarker = L.marker(enemyLatLng, {
                        icon: L.divIcon({
                            html: `<div class="group-label">${groupId} (${report.ce})</div>`,
                            className: 'label-marker',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        })
                    });
                    console.log("Добавляем метку пехоты противника на слой _reportGroupLayer");
                    labelMarker.addTo(this._reportGroupLayer);
                } else if (report.t === "vehicle_detected") {
                    const vehicleId = report.id;
                    const enemyLatLng = gameToLatLng(report.p[0], report.p[1], conf);
                    console.log(`Координаты маркера противника (техника): ${enemyLatLng.lat}, ${enemyLatLng.lng}`);
                    const vehIcon = unitIcons[markerSide].vehicle;
                    const vehTooltip = `
                        <b>${report.vehicle_type}</b><br>
                        ID: ${vehicleId}<br>
                        Сторона: ${enemySide}<br>
                        Точность: ${report.acc} м
                    `;
                    const vehMarker = L.marker(enemyLatLng, { 
                        icon: vehIcon,
                        data: { side: enemySide, vehicleId: vehicleId }
                    });
                    console.log(`Добавляем маркер техники противника для ${vehicleId} на слой _reportVehicleLayer с иконкой ${markerSide}`);
                    vehMarker.addTo(this._reportVehicleLayer);
                    vehMarker.bindTooltip(vehTooltip, { 
                        direction: 'top', 
                        offset: [0, -15], 
                        className: 'vehicle-tooltip'
                    });

                    const labelMarker = L.marker(enemyLatLng, {
                        icon: L.divIcon({
                            html: `<div class="vehicle-label">${report.vehicle_type}</div>`,
                            className: 'label-marker',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        })
                    });
                    console.log("Добавляем метку техники противника на слой _reportVehicleLayer");
                    labelMarker.addTo(this._reportVehicleLayer);
                } else {
                    console.log(`Репорт с типом ${report.t} не поддерживается для отрисовки`);
                }
            } else {
                console.log(`Репорт не отрисовывается: armaDisplaySide=${armaDisplaySide}, enemySide=${enemySide}`);
            }
        });
    }
});

window.unitLayer = new UnitLayer();

const style = document.createElement('style');
style.innerHTML = `
    .label-marker {
        background: none;
    }
    .group-label, .vehicle-label {
        width: 100px;
        text-align: center;
        font-size: 12px;
        color: #000;
        background: none;
        border: none;
        padding: 0;
    }
    .vehicle-label {
        line-height: 1.2;
    }
    .group-tooltip, .vehicle-tooltip {
        font-size: 12px;
        background-color: rgba(255, 255, 255, 0.9);
        border: 1px solid #ccc;
    }
    .waypoint-opfor-current {
        filter: hue-rotate(0deg) saturate(3) brightness(1.2);
    }
    .waypoint-opfor-reached, .waypoint-opfor-unreached {
        filter: hue-rotate(0deg) saturate(3) brightness(1.2);
        opacity: 0.33;
    }
    .waypoint-blufor-current {
        filter: hue-rotate(220deg) saturate(3) brightness(1.2);
    }
    .waypoint-blufor-reached, .waypoint-blufor-unreached {
        filter: hue-rotate(220deg) saturate(3) brightness(1.2);
        opacity: 0.33;
    }
`;
document.head.appendChild(style);