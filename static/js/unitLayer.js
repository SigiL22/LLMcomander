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
        vehicle: L.icon({ iconUrl: '/static/ico/r_arm_r.png', iconSize: [30, 30], iconAnchor: [15, 15] })
    },
    "BLUFOR": {
        infantry: L.icon({ iconUrl: '/static/ico/b_inf_s.png', iconSize: [30, 30], iconAnchor: [15, 15] }),
        vehicle: L.icon({ iconUrl: '/static/ico/b_arm_s.png', iconSize: [30, 30], iconAnchor: [15, 15] })
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
                    Поведение: ${group.b || 'N/A'}
                `;

                // Проверяем, находится ли командир в технике
                let leaderInVehicle = false;
                let leaderVehicleId = null;
                if (group.u && group.u.length > 0) {
                    const leaderUnit = group.u.find(u => u.n === group.c); // Находим командира в списке юнитов
                    if (leaderUnit && leaderUnit.v) {
                        leaderInVehicle = true;
                        leaderVehicleId = leaderUnit.v.id; // ID техники командира
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
                }

                // Подпись группы
                L.marker(groupLatLng, {
                    icon: L.divIcon({
                        html: `<div class="group-label">${group.n}</div>`,
                        className: 'label-marker',
                        iconSize: [100, 20],
                        iconAnchor: [50, -15]
                    })
                }).addTo(this._labelLayer);

                // Маркеры техники
                if (group.v && group.v.length > 0) {
                    group.v.forEach(vehicle => {
                        const vehPos = vehicle.p;
                        const vehLatLng = gameToLatLng(vehPos[0], vehPos[1], conf);
                        const vehIcon = unitIcons[side] ? unitIcons[side].vehicle : unitIcons["OPFOR"].vehicle;
                        const vehTooltip = `
                            <b>${vehicle.vn}</b><br>
                            ID: ${vehicle.id}<br>
                            Юнитов: ${vehicle.c}<br>
                            Топливо: ${vehicle.f}<br>
                            Здоровье: ${vehicle.h}
                        `;
                        const vehMarker = L.marker(vehLatLng, { 
                            icon: vehIcon,
                            data: { side: side, group: group.n, vehicleId: vehicle.id } // Добавляем данные о группе
                        }).addTo(this._vehicleLayer);
                        vehMarker.bindTooltip(vehTooltip, { 
                            direction: 'top', 
                            offset: [0, -15], 
                            className: 'vehicle-tooltip'
                        });

                        // Привязываем обработчик клика для техники
                        if (this.waypointMode && window.waypointEditor && window.waypointEditor.onGroupClick) {
                            vehMarker.on('click', window.waypointEditor.onGroupClick);
                        }

                        L.marker(vehLatLng, {
                            icon: L.divIcon({
                                html: `<div class="vehicle-label">${group.n}<br>${vehicle.vn}<br>${vehicle.id}</div>`,
                                className: 'label-marker',
                                iconSize: [100, 40],
                                iconAnchor: [50, -35]
                            })
                        }).addTo(this._labelLayer);
                    });
                }
            });
        });
    }
});

// Создаём глобальный экземпляр слоя
window.unitLayer = new UnitLayer();

// Стили для подписей
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
`;
document.head.appendChild(style);