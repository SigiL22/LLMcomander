// js/unitLayer.js

// Функция преобразования игровых координат в Leaflet-координаты
function gameToLatLng(x, y, conf) {
    const px = x * (conf.mapImageWidth / conf.islandWidth);
    const py = conf.mapImageHeight - (y * (conf.mapImageHeight / conf.islandHeight));
    return map.unproject([px, py], 7);
}

// Определение иконок для сторон и типов
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

// Класс слоя для юнитов и техники
var UnitLayer = L.Layer.extend({
    initialize: function() {
        this._groupLayer = L.layerGroup();
        this._vehicleLayer = L.layerGroup();
        this._labelLayer = L.layerGroup();
        this._waypointLayer = L.layerGroup();
        this._lastData = null;
        this.waypointMode = false;
    },

    onAdd: function(map) {
        this._map = map;
        this._groupLayer.addTo(map);
        this._vehicleLayer.addTo(map);
        this._labelLayer.addTo(map);
        this._waypointLayer.addTo(map);
    },

    onRemove: function(map) {
        this._groupLayer.removeFrom(map);
        this._vehicleLayer.removeFrom(map);
        this._labelLayer.removeFrom(map);
        this._waypointLayer.removeFrom(map);
    },

    updateData: function(jsonData) {
        if (JSON.stringify(jsonData) === JSON.stringify(this._lastData)) {
            console.log("Данные не изменились, пропускаем обновление");
            return;
        }
        this._lastData = jsonData;

        this._groupLayer.clearLayers();
        this._vehicleLayer.clearLayers();
        this._labelLayer.clearLayers();
        this._waypointLayer.clearLayers();
        const conf = Config.get();

        if (!jsonData || !jsonData.sides) return;

        Object.keys(jsonData.sides).forEach(side => {
            const sideData = jsonData.sides[side];
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

                // Проверяем, находится ли командир в технике
                let leaderInVehicle = false;
                let leaderVehicleId = null;
                if (group.u && group.u.length > 0) {
                    const leaderUnit = group.u.find(u => u.n === group.c);
                    if (leaderUnit && leaderUnit.v) {
                        leaderInVehicle = true;
                        leaderVehicleId = leaderUnit.v.id;
                    }
                }

                // Создаем маркер группы только если командир не в технике
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

                // Маркеры техники
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

                // Синхронизация вэйпойнтов из "w", исключая стартовый вэйпойнт ("i": 0)
                if (group.w && group.w.length > 0) {
                    group.w.forEach(wp => {
                        if (wp.i === 0) return; // Пропускаем стартовый вэйпойнт
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
                            waypointIndex: wp.i // Используем "i" как индекс
                        };
                        // Определяем иконку в зависимости от состояния
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
    }
});

// Создаём глобальный экземпляр слоя
window.unitLayer = new UnitLayer();

// Стили для подписей и иконок вэйпойнтов
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
        filter: hue-rotate(0deg) saturate(3) brightness(1.2); /* Красный для OPFOR, текущий */
    }
    .waypoint-opfor-reached, .waypoint-opfor-unreached {
        filter: hue-rotate(0deg) saturate(3) brightness(1.2); /* Красный для OPFOR */
        opacity: 0.33; /* Полупрозрачный для достигнутых и недостигнутых */
    }
    .waypoint-blufor-current {
        filter: hue-rotate(220deg) saturate(3) brightness(1.2); /* Синий для BLUFOR, текущий */
    }
    .waypoint-blufor-reached, .waypoint-blufor-unreached {
        filter: hue-rotate(220deg) saturate(3) brightness(1.2); /* Синий для BLUFOR */
        opacity: 0.33; /* Полупрозрачный для достигнутых и недостигнутых */
    }
`;
document.head.appendChild(style);