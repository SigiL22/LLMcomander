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
        vehicleDestroyed: L.icon({ iconUrl: '/static/ico/arm_dest.png', iconSize: [30, 30], iconAnchor: [15, 15], className: 'vehicle-destroyed' }),
        waypointCurrent: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-current' }),
        waypointReached: L.icon({ iconUrl: '/static/ico/w_reach.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-reached' }),
        waypointUnreached: L.icon({ iconUrl: '/static/ico/w_curr.png', iconSize: [20, 20], iconAnchor: [10, 10], className: 'waypoint-opfor-unreached' })
    },
    "BLUFOR": {
        infantry: L.icon({ iconUrl: '/static/ico/b_inf_s.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        vehicle: L.icon({ iconUrl: '/static/ico/b_arm_s.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        vehicleDestroyed: L.icon({ iconUrl: '/static/ico/arm_dest.png', iconSize: [30, 30], iconAnchor: [15, 15], className: 'vehicle-destroyed' }),
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
        this.savedReports = JSON.parse(localStorage.getItem('savedReports')) || {};
        this.startMissionProcessed = false; // Флаг обработки start_mission
    },

    onAdd: function(map) {
        this._map = map;
        this._groupLayer.addTo(map);
        this._vehicleLayer.addTo(map);
        this._labelLayer.addTo(map);
        this._waypointLayer.addTo(map);
        this._reportGroupLayer.addTo(map);
        this._reportVehicleLayer.addTo(map);
        if (window.missionSettings) {
            this.updateReports([]);
        }
    },

    onRemove: function(map) {
        this._groupLayer.removeFrom(map);
        this._vehicleLayer.removeFrom(map);
        this._labelLayer.removeFrom(map);
        this._waypointLayer.removeFrom(map);
        this._reportGroupLayer.removeFrom(map);
        this._reportVehicleLayer.removeFrom(map);
    },

    processReports: function(reports) {
        if (!reports || reports.length === 0) return;
        for (const report of reports) {
            if (report.command === "start_mission" && !this.startMissionProcessed) {
                this.savedReports = {};
                localStorage.setItem('savedReports', JSON.stringify(this.savedReports));
                this.startMissionProcessed = true;
                this._reportGroupLayer.clearLayers(); // Очищаем слой пехоты
                this._reportVehicleLayer.clearLayers(); // Очищаем слой техники
                console.log("Получена команда start_mission, сохраненные репорты и маркеры очищены");
                return; // Прерываем обработку
            } else if (report.t === "enemy_detected") {
                const groupId = report.ge || "unknown";
                this.savedReports[groupId] = report;
            } else if (report.t === "vehicle_detected" || report.t === "vehicle_destroyed") {
                const vehicleId = report.id;
                this.savedReports[vehicleId] = report;
            } else if (report.t === "enemies_cleared") {
                const groupName = report.g;
                const clearedPos = report.p;
                for (const key in this.savedReports) {
                    const savedReport = this.savedReports[key];
                    if (savedReport.t === "enemy_detected") {
                        if (savedReport.g === groupName) {
                            delete this.savedReports[key];
                            console.log(`Удален репорт enemy_detected от группы ${groupName} для ${key} (по группе)`);
                        } else if (clearedPos) {
                            const enemyPos = savedReport.p;
                            const distance = Math.sqrt(
                                Math.pow(clearedPos[0] - enemyPos[0], 2) +
                                Math.pow(clearedPos[1] - enemyPos[1], 2)
                            );
                            if (distance < 200) {
                                delete this.savedReports[key];
                                console.log(`Удален репорт enemy_detected для ${key} группой ${groupName} на расстоянии ${distance} м`);
                            }
                        }
                    }
                }
            }
        }
        localStorage.setItem('savedReports', JSON.stringify(this.savedReports));
    },

    updateData: function(jsonData, reports = []) {
        if (JSON.stringify(jsonData) === JSON.stringify(this._lastData) && reports.length === 0) {
            console.log("Данные не изменились, пропускаем обновление");
            return;
        }
        this._lastData = jsonData;

        this._groupLayer.clearLayers();
        this._vehicleLayer.clearLayers();
        this._labelLayer.clearLayers();
        this._waypointLayer.clearLayers();
        const conf = Config.get();

        if (!jsonData || !jsonData.sides) {
            console.error("Некорректные данные от arma_data:", jsonData);
            return;
        }

        const displaySide = window.missionSettings.displaySide || "";

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

                        L.marker(wpLatLng, {
                            icon: L.divIcon({
                                html: `<div class="group-label">${group.n} #${wp.i}</div>`,
                                className: 'label-marker',
                                iconSize: [100, 20],
                                iconAnchor: [50, -15]
                            })
                        }).addTo(this._waypointLayer);
                    });
                }
            });
        });

        this.updateReports(reports);
    },

    updateReports: function(reports) {
        console.log("Получены репорты:", reports);
        if (!window.missionSettings) {
            console.log("missionSettings еще не загружен, пропускаем отрисовку репортов");
            return;
        }
        const displaySide = window.missionSettings.displaySide || "";
        const armaDisplaySide = displaySide === "OPFOR" ? "EAST" : displaySide === "BLUFOR" ? "WEST" : displaySide;
        const filteredReports = armaDisplaySide ? reports.filter(report => report.s === armaDisplaySide || report.command === "start_mission") : reports;
        this.processReports(filteredReports);

        this._reportGroupLayer.clearLayers();
        this._reportVehicleLayer.clearLayers();
        const conf = Config.get();

        Object.values(this.savedReports).forEach(report => {
            const enemySide = report.se || "UNKNOWN";
            const armaEnemySide = enemySide === "EAST" ? "OPFOR" : enemySide === "WEST" ? "BLUFOR" : enemySide;
            if (armaDisplaySide && armaDisplaySide !== enemySide) {
                const markerSide = armaDisplaySide === "EAST" ? "BLUFOR" : "OPFOR";
                if (report.t === "enemy_detected") {
                    const groupId = report.ge || "unknown";
                    const enemyLatLng = gameToLatLng(report.p[0], report.p[1], conf);
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
                    }).addTo(this._reportGroupLayer);
                    enemyMarker.bindTooltip(enemyTooltip, { 
                        direction: 'top', 
                        offset: [0, -15], 
                        className: 'group-tooltip'
                    });

                    L.marker(enemyLatLng, {
                        icon: L.divIcon({
                            html: `<div class="group-label">${groupId} (${report.ce})</div>`,
                            className: 'label-marker',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        })
                    }).addTo(this._reportGroupLayer);
                } else if (report.t === "vehicle_detected") {
                    const vehicleId = report.id;
                    const enemyLatLng = gameToLatLng(report.p[0], report.p[1], conf);
                    const vehIcon = unitIcons[markerSide].vehicle;
                    const vehTooltip = `
                        <b>${report.vehicle_name || report.vehicle_type}</b><br>
                        ID: ${vehicleId}<br>
                        Сторона: ${enemySide}<br>
                        Точность: ${report.acc} м
                    `;
                    const vehMarker = L.marker(enemyLatLng, { 
                        icon: vehIcon,
                        data: { side: enemySide, vehicleId: vehicleId }
                    }).addTo(this._reportVehicleLayer);
                    vehMarker.bindTooltip(vehTooltip, { 
                        direction: 'top', 
                        offset: [0, -15], 
                        className: 'vehicle-tooltip'
                    });

                    L.marker(enemyLatLng, {
                        icon: L.divIcon({
                            html: `<div class="vehicle-label">${report.vehicle_name || report.vehicle_type}</div>`,
                            className: 'label-marker',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        })
                    }).addTo(this._reportVehicleLayer);
                } else if (report.t === "vehicle_destroyed") {
                    const vehicleId = report.id;
                    const enemyLatLng = gameToLatLng(report.p[0], report.p[1], conf);
                    const vehIcon = unitIcons[markerSide].vehicleDestroyed;
                    const vehTooltip = `
                        <b>${report.vehicle_name || report.vehicle_type}</b> (уничтожена)<br>
                        ID: ${vehicleId}<br>
                        Сторона: ${enemySide}
                    `;
                    const vehMarker = L.marker(enemyLatLng, { 
                        icon: vehIcon,
                        data: { side: enemySide, vehicleId: vehicleId }
                    }).addTo(this._reportVehicleLayer);
                    vehMarker.bindTooltip(vehTooltip, { 
                        direction: 'top', 
                        offset: [0, -15], 
                        className: 'vehicle-tooltip destroyed'
                    });

                    L.marker(enemyLatLng, {
                        icon: L.divIcon({
                            html: `<div class="vehicle-label">${report.vehicle_name || report.vehicle_type} (X)</div>`,
                            className: 'label-marker destroyed',
                            iconSize: [100, 20],
                            iconAnchor: [50, -15]
                        })
                    }).addTo(this._reportVehicleLayer);
                }
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
    .vehicle-tooltip.destroyed {
        background-color: rgba(255, 0, 0, 0.9);
        color: #fff;
    }
    .label-marker.destroyed {
        color: #ff0000;
    }
    .vehicle-destroyed {
        filter: grayscale(100%) opacity(0.7);
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