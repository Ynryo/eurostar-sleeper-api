// Application Multi-Réseaux : Eurostar & European Sleeper
let initialData = null;
let currentNetwork = 'all';
let currentFilter = 'all';
let searchQuery = '';
let markersMap = {};
let stationMarkers = [];
let activeSelectedId = null;
let activeRouteLayers = [];

// Initialisation de la carte Leaflet
const map = L.map('map', {
    zoomControl: false
}).setView([50.5, 6.5], 6);

L.control.zoom({ position: 'bottomright' }).addTo(map);

// Fond de carte sombre CartoDB / Esri
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri &mdash; Eurostar & European Sleeper Radar',
    maxZoom: 16
}).addTo(map);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
    attribution: '',
    maxZoom: 16
}).addTo(map);

// Centrage et zooms prédéfinis par réseau
function fitNetworkView(networkId) {
    if (networkId === 'eurostar') {
        map.flyTo([50.8, 3.5], 7, { duration: 0.9 });
    } else if (networkId === 'european_sleeper') {
        map.flyTo([50.5, 9.5], 6, { duration: 0.9 });
    } else {
        map.flyTo([50.5, 6.5], 6, { duration: 0.9 });
    }
}

// Mise à jour de l'en-tête et du badge en fonction du réseau
function updateBranding(networkId) {
    const badgeEl = document.getElementById('brand-badge');
    const titleEl = document.getElementById('brand-title');
    const subtitleEl = document.getElementById('brand-subtitle');

    if (!badgeEl || !titleEl || !subtitleEl) return;

    badgeEl.className = 'brand-badge';
    if (networkId === 'european_sleeper') {
        badgeEl.textContent = '🌙';
        badgeEl.classList.add('network-sleeper');
        titleEl.textContent = 'European Sleeper';
        subtitleEl.textContent = 'Night Train Trans-European';
    } else if (networkId === 'eurostar') {
        badgeEl.textContent = '🚆';
        titleEl.textContent = 'Eurostar Radar';
        subtitleEl.textContent = 'GTFS-RT Live Network';
    } else {
        badgeEl.textContent = '🌐';
        badgeEl.classList.add('network-all');
        titleEl.textContent = 'Radar Ferroviaire';
        subtitleEl.textContent = 'Eurostar & European Sleeper';
    }
}

// Rendu des gares dynamiquement selon le réseau sélectionné
function renderStations(stations, networkId) {
    stationMarkers.forEach(m => map.removeLayer(m));
    stationMarkers = [];

    if (!stations) return;

    stations.forEach(st => {
        // Filtrage de la gare selon le réseau sélectionné
        const isEurostar = st.network === 'eurostar' || st.network === 'both';
        const isSleeper = st.network === 'european_sleeper' || st.network === 'both';

        if (networkId === 'eurostar' && !isEurostar) return;
        if (networkId === 'european_sleeper' && !isSleeper) return;

        let modifierClass = '';
        let badgeText = '';

        if (st.network === 'both') {
            modifierClass = 'both-station';
            badgeText = ' <span style="color:#ffd000;font-size:10px;">(Eurostar & Sleeper)</span>';
        } else if (st.network === 'european_sleeper') {
            modifierClass = 'sleeper-station';
            badgeText = ' <span style="color:#c084fc;font-size:10px;">(European Sleeper)</span>';
        } else {
            badgeText = ' <span style="color:#00d2ff;font-size:10px;">(Eurostar)</span>';
        }

        const stIcon = L.divIcon({
            className: 'station-div-icon',
            html: `<div class="station-marker ${modifierClass}" title="${st.name}"></div>`,
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });

        const marker = L.marker([st.lat, st.lon], { icon: stIcon })
            .bindTooltip(`<b>${st.name}</b>${badgeText}`, { direction: 'top', className: 'station-tooltip' })
            .addTo(map);

        stationMarkers.push(marker);
    });
}

// Helper pour déterminer le réseau de manière résiliente
function getTrainNetwork(t) {
    if (t && t.network) return t.network;
    if (t && ((t.num && t.num.startsWith('ES')) || (t.id && t.id.startsWith('ES')))) {
        return 'european_sleeper';
    }
    return 'eurostar';
}

// Vérification d'éligibilité au radar (en circulation ou départ imminent < 20 min)
function isRadarEligible(t) {
    if (!t) return false;
    if (t.status === 'RUNNING') return true;
    if (t.status === 'SCHEDULED') {
        if (t.is_departing_soon) return true;
        if (t.time_to_dep_sec !== undefined && t.time_to_dep_sec !== null && t.time_to_dep_sec >= 0 && t.time_to_dep_sec <= 1200) {
            return true;
        }
    }
    return false;
}

// Rendu global de l'interface
function renderUI(data) {
    if (!data) return;

    renderStations(data.stations, currentNetwork);
    const rawTrains = data.trains || [];

    // Filtrage strict : seuls les trains en circulation et ceux qui partent dans moins de 20 min
    const radarTrains = rawTrains;

    // 1. Filtrage par réseau
    const networkTrains = radarTrains.filter(t => {
        if (currentNetwork === 'all') return true;
        return getTrainNetwork(t) === currentNetwork;
    });

    // 2. Calcul KPIs pour le radar actif
    const runningCount = networkTrains.filter(t => t.status === 'RUNNING').length;
    const departingCount = networkTrains.filter(t => t.status === 'SCHEDULED').length;
    const delayedCount = networkTrains.filter(t => t.delay_sec > 0).length;
    const totalCount = networkTrains.length;

    const elRunning = document.getElementById('kpi-running');
    if (elRunning) elRunning.textContent = runningCount;

    const elDeparting = document.getElementById('kpi-departing');
    if (elDeparting) elDeparting.textContent = departingCount;

    const elDelayed = document.getElementById('kpi-delayed');
    if (elDelayed) elDelayed.textContent = delayedCount;

    const elTotal = document.getElementById('kpi-total');
    if (elTotal) elTotal.textContent = totalCount;

    // 3. Filtrage par catégorie & recherche
    const filteredTrains = networkTrains.filter(t => {
        // Filtre catégorie
        if (currentFilter === 'running' && t.status !== 'RUNNING') return false;
        if (currentFilter === 'departing' && t.status !== 'SCHEDULED') return false;
        if (currentFilter === 'delayed' && t.delay_sec <= 0) return false;
        if (currentFilter === 'ontime' && (t.delay_sec > 0 || t.status === 'CANCELED')) return false;
        if (currentFilter === 'skipped' && !t.has_skipped) return false;

        // Recherche texte
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            const matchNum = (t.num || '').toLowerCase().includes(q);
            const matchHead = (t.headsign || '').toLowerCase().includes(q);
            const matchOrig = (t.origin || '').toLowerCase().includes(q);
            const matchDest = (t.destination || '').toLowerCase().includes(q);
            const matchOp = (t.operator_name || '').toLowerCase().includes(q);
            if (!matchNum && !matchHead && !matchOrig && !matchDest && !matchOp) return false;
        }

        return true;
    });

    // 4. Rendu de la sidebar
    const listEl = document.getElementById('train-list');
    listEl.innerHTML = '';

    if (filteredTrains.length === 0) {
        listEl.innerHTML = `
            <div style="padding: 24px 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                Aucun train ne correspond aux filtres actuels.
            </div>
        `;
    }

    filteredTrains.forEach(train => {
        const card = document.createElement('div');
        let delayClass = 'delay-ontime';
        let cardDelayModifier = '';

        if (train.status === 'CANCELED') {
            cardDelayModifier = 'status-canceled';
        } else if (train.delay_sec > 900) {
            delayClass = 'delay-alert';
            cardDelayModifier = 'delayed-alert';
        } else if (train.delay_sec > 0) {
            delayClass = 'delay-warning';
            cardDelayModifier = 'delayed-warning';
        } else if (train.status === 'SCHEDULED') {
            cardDelayModifier = 'status-scheduled';
        } else if (train.status === 'TERMINATED') {
            cardDelayModifier = 'status-terminated';
        }

        const isSleeper = getTrainNetwork(train) === 'european_sleeper';
        const operatorClass = isSleeper ? 'sleeper' : 'eurostar';
        const operatorLabel = isSleeper ? '🌙 Sleeper' : '🚆 Eurostar';
        const networkCardClass = isSleeper ? 'network-sleeper' : '';

        let badgeHtml = `<div class="delay-pill ${delayClass}">${train.delay_str}</div>`;
        if (train.status === 'CANCELED') {
            badgeHtml = `<div class="badge-canceled">ANNULÉ</div>`;
        } else if (train.status === 'SCHEDULED') {
            const mins = (train.time_to_dep_sec !== undefined && train.time_to_dep_sec !== null) ? Math.max(1, Math.floor(train.time_to_dep_sec / 60)) : null;
            const minText = mins ? `dans ${mins} min` : 'imminent';
            badgeHtml = `<div class="delay-pill" style="background: rgba(255, 208, 0, 0.15); color: #ffd000; border-color: rgba(255, 208, 0, 0.35);">⏳ Départ ${minText}</div>`;
        } else if (train.has_skipped) {
            badgeHtml = `
                <div style="display: flex; gap: 6px; align-items: center;">
                    <span class="skipped-notice-tag">⚠️ ${train.skipped_count} arrêt(s) supprimé(s)</span>
                    <div class="delay-pill ${delayClass}">${train.delay_str}</div>
                </div>
            `;
        }

        card.className = `train-card ${cardDelayModifier} ${networkCardClass} ${activeSelectedId === train.id ? 'selected' : ''}`;
        card.innerHTML = `
            <div class="card-top">
                <div class="train-id-badge">
                    <span class="operator-tag ${operatorClass}">${operatorLabel}</span>
                    <span>${train.num}</span>
                </div>
                ${badgeHtml}
            </div>
            <div class="card-route">
                <span>${train.origin}</span> ➔ <span>${train.destination}</span>
            </div>
            <div class="card-status-text">
                <span>📍</span> ${train.status_label}
            </div>
            ${train.alert ? `<div class="card-alert-banner">🚨 ${train.alert}</div>` : ''}
        `;

        card.setAttribute('data-id', train.id);
        card.onclick = () => selectTrain(train);
        listEl.appendChild(card);
    });

    // 5. Mise à jour des marqueurs sur la carte
    updateMapMarkers(filteredTrains);
}

// Mise à jour des marqueurs Leaflet
function updateMapMarkers(trainsToDisplay) {
    // Nettoyage ancien
    Object.values(markersMap).forEach(m => map.removeLayer(m));
    markersMap = {};

    // Détection des positions identiques pour décalage en rosace
    const posCounts = {};
    trainsToDisplay.forEach(t => {
        const key = `${t.lat.toFixed(4)}_${t.lon.toFixed(4)}`;
        posCounts[key] = (posCounts[key] || 0) + 1;
    });

    const posIndex = {};

    trainsToDisplay.forEach(train => {
        const key = `${train.lat.toFixed(4)}_${train.lon.toFixed(4)}`;
        let mLat = train.lat;
        let mLon = train.lon;

        if (posCounts[key] > 1) {
            const idx = posIndex[key] || 0;
            posIndex[key] = idx + 1;
            const angle = (idx * 2 * Math.PI) / posCounts[key];
            const radius = 0.009 + (Math.floor(idx / 8) * 0.005);
            mLat += radius * Math.cos(angle);
            mLon += radius * Math.sin(angle) * 1.5;
        }

        let markerModifier = '';
        if (train.status === 'CANCELED') {
            markerModifier = 'delayed-alert';
        } else if (train.delay_sec > 900) {
            markerModifier = 'delayed-alert';
        } else if (train.delay_sec > 0) {
            markerModifier = 'delayed-warning';
        } else if (train.status === 'SCHEDULED') {
            markerModifier = 'status-scheduled';
        } else if (train.status === 'TERMINATED') {
            markerModifier = 'status-terminated';
        }

        const isSleeper = getTrainNetwork(train) === 'european_sleeper';
        const networkMarkerClass = isSleeper ? 'network-sleeper' : '';

        const html = `
            <div class="train-marker ${markerModifier} ${networkMarkerClass} ${activeSelectedId === train.id ? 'selected-train' : ''}">
                <div class="train-marker-label">${train.num}</div>
                <div class="train-marker-body" style="transform: rotate(${train.bearing}deg);">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display:block;">
                        <path d="M12 3L4 19L12 15L20 19L12 3Z"/>
                    </svg>
                </div>
            </div>
        `;

        const icon = L.divIcon({
            className: 'custom-train-icon',
            html: html,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        const marker = L.marker([mLat, mLon], { icon: icon }).addTo(map);

        marker.on('click', (e) => {
            if (e && e.originalEvent) e.originalEvent.stopPropagation();
            selectTrain(train, false);
        });
        markersMap[train.id] = marker;
    });
}

// Panneau latéral droit
function openDetailPanel(train) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    if (!panel || !content) return;

    let delayClass = 'delay-ontime';
    if (train.status === 'CANCELED') {
        delayClass = 'delay-alert';
    } else if (train.delay_sec > 900) {
        delayClass = 'delay-alert';
    } else if (train.delay_sec > 0) {
        delayClass = 'delay-warning';
    }

    const isSleeper = getTrainNetwork(train) === 'european_sleeper';
    const operatorName = isSleeper ? 'European Sleeper (Train de nuit)' : 'Eurostar';
    const operatorTag = isSleeper ? '🌙 European Sleeper' : '🚆 Eurostar';
    const operatorClass = isSleeper ? 'sleeper' : 'eurostar';

    let badgeHtml = `<div class="delay-pill ${delayClass}">${train.delay_str}</div>`;
    if (train.status === 'CANCELED') {
        badgeHtml = `<div class="badge-canceled">ANNULÉ</div>`;
    } else if (train.has_skipped) {
        badgeHtml = `
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <span class="skipped-notice-tag">⚠️ ${train.skipped_count} arrêt(s) supprimé(s)</span>
                <div class="delay-pill ${delayClass}">${train.delay_str}</div>
            </div>
        `;
    }

    const stopsHtml = (train.stops || []).map(s => {
        if (s.is_skipped) {
            return `
                <div class="stop-item skipped">
                    <div class="stop-item-title" style="text-decoration: line-through; color: #f87171;">
                        ${s.name} <span class="badge-skipped">ARRÊT SUPPRIMÉ</span>
                    </div>
                    <div class="stop-item-time" style="color: #64748b;">
                        Arrêt non desservi (prévu: ${s.sched_arr})
                    </div>
                </div>
            `;
        }
        return `
            <div class="stop-item ${s.delay_arr > 0 || s.delay_dep > 0 ? 'delayed' : ''}">
                <div class="stop-item-title">${s.name}</div>
                <div class="stop-item-time">
                    Arr: ${s.est_arr} ${s.delay_arr > 0 ? `(+${Math.round(s.delay_arr/60)}m)` : ''} | 
                    Dép: ${s.est_dep} ${s.delay_dep > 0 ? `(+${Math.round(s.delay_dep/60)}m)` : ''}
                </div>
            </div>
        `;
    }).join('');

    content.innerHTML = `
        <div class="detail-header">
            <div>
                <div style="margin-bottom: 4px;">
                    <span class="operator-tag ${operatorClass}">${operatorTag}</span>
                </div>
                <div class="detail-title">${train.operator_name || operatorName} N°${train.num}</div>
                <div class="detail-subtitle">${train.origin} ➔ ${train.destination}</div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                ${badgeHtml}
                <button class="detail-close-btn" onclick="clearActiveRoute()" title="Fermer le panneau">✕</button>
            </div>
        </div>
        <div class="detail-body">
            <div class="detail-status-pill">
                <span>📍</span> ${train.status_label}
            </div>
            ${train.alert ? `<div class="card-alert-banner">🚨 <b>Cause :</b> ${train.alert}</div>` : ''}
            <div class="detail-section-title">
                ${isSleeper ? 'Horaires théoriques (GTFS Statique)' : 'Arrêts et horaires estimés'}
            </div>
            <div class="stops-timeline">
                ${stopsHtml}
            </div>
        </div>
    `;

    panel.classList.add('open');
}

function closeDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (panel) panel.classList.remove('open');
}

function clearActiveRoute() {
    activeRouteLayers.forEach(l => map.removeLayer(l));
    activeRouteLayers = [];
    activeSelectedId = null;

    document.querySelectorAll('.train-card').forEach(c => c.classList.remove('selected'));
    Object.values(markersMap).forEach(m => {
        const el = m.getElement();
        if (el) {
            const b = el.querySelector('.train-marker');
            if (b) b.classList.remove('selected-train');
        }
    });
    closeDetailPanel();
}

function selectTrain(train, shouldFly = true) {
    activeSelectedId = train.id;

    // Mise à jour de la classe CSS sur les cartes
    document.querySelectorAll('.train-card').forEach(c => c.classList.remove('selected'));
    const cardEl = document.querySelector(`.train-card[data-id="${train.id}"]`);
    if (cardEl) {
        cardEl.classList.add('selected');
        cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Mise à jour visuelle des marqueurs
    Object.entries(markersMap).forEach(([id, m]) => {
        const el = m.getElement();
        if (el) {
            const b = el.querySelector('.train-marker');
            if (b) {
                if (id === train.id) b.classList.add('selected-train');
                else b.classList.remove('selected-train');
            }
        }
    });

    // Nettoyage ancien tracé
    activeRouteLayers.forEach(l => map.removeLayer(l));
    activeRouteLayers = [];

    // Récupération de la géométrie du tracé
    let routePts = null;
    if (train.shape_id && initialData && initialData.shapes_dict && initialData.shapes_dict[train.shape_id]) {
        routePts = initialData.shapes_dict[train.shape_id];
    } else if (train.stops && train.stops.length > 1) {
        const validPts = train.stops.filter(s => !s.is_skipped).map(s => [s.lat, s.lon]);
        if (validPts.length > 1) routePts = validPts;
    }

    const isSleeper = getTrainNetwork(train) === 'european_sleeper';
    const glowColor = isSleeper ? '#a855f7' : '#ffd000';
    const coreColor = isSleeper ? '#e9d5ff' : '#ffd000';

    if (routePts && routePts.length > 1) {
        const glow = L.polyline(routePts, {
            color: glowColor,
            weight: 8,
            opacity: 0.45,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map);

        const core = L.polyline(routePts, {
            color: coreColor,
            weight: 3.5,
            opacity: 0.95,
            lineCap: 'round',
            lineJoin: 'round'
        }).addTo(map);

        activeRouteLayers.push(glow, core);
    }

    // Ouverture du volet latéral
    openDetailPanel(train);

    const marker = markersMap[train.id];
    if (marker && shouldFly) {
        map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 7), { duration: 0.8 });
    }
}

// Gestionnaires d'événements
document.addEventListener('DOMContentLoaded', () => {
    // Écouteur sur le menu déroulant de réseau
    const networkSelectEl = document.getElementById('network-select');
    if (networkSelectEl) {
        networkSelectEl.addEventListener('change', (e) => {
            currentNetwork = e.target.value;
            updateBranding(currentNetwork);
            fitNetworkView(currentNetwork);
            clearActiveRoute();
            renderUI(initialData);
        });
    }

    // Filtres chips
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            renderUI(initialData);
        });
    });

    // Recherche
    const searchEl = document.getElementById('search-input');
    if (searchEl) {
        searchEl.addEventListener('input', (e) => {
            searchQuery = e.target.value.trim();
            renderUI(initialData);
        });
    }

    // Bouton de recentrage
    const recenterBtn = document.getElementById('btn-recenter');
    if (recenterBtn) {
        recenterBtn.addEventListener('click', () => {
            fitNetworkView(currentNetwork);
        });
    }

    // Clic sur le fond de la carte
    map.on('click', (e) => {
        if (e.originalEvent && e.originalEvent.target && e.originalEvent.target.classList && e.originalEvent.target.classList.contains('leaflet-container')) {
            clearActiveRoute();
        }
    });

    // Actualisation manuelle
    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            secondsLeft = 30;
            fetchFreshData();
        });
    }
});

// Actualisation automatique
let secondsLeft = 30;
function updateRefreshTimer() {
    secondsLeft--;
    if (secondsLeft <= 0) {
        fetchFreshData();
        secondsLeft = 30;
    }
    const timerEl = document.getElementById('refresh-timer');
    if (timerEl) timerEl.textContent = `${secondsLeft}s`;
}
setInterval(updateRefreshTimer, 1000);

async function fetchFreshData() {
    try {
        const res = await fetch('/api/data');
        if (res.ok) {
            initialData = await res.json();
            renderUI(initialData);
        }
    } catch (e) {
        console.log('Mode autonome ou serveur hors ligne');
    }
}

// Chargement initial
fetchFreshData();