// =========================================================================
// Radar Ferroviaire Européen — Client Web multi-réseaux (NeTEx & Zenbus RT)
// =========================================================================

// État de l'application
let networksData = [];
let currentNetwork = 'all';
let currentFilter = 'all';
let searchQuery = '';
let markersMap = {};
let stationMarkers = [];
let activeSelectedId = null;
let activeRouteLayers = [];
let cachedMarkers = [];

// Caches en mémoire côté client pour les détails et tracés NeTEx
const journeyDetailsCache = new Map();
const journeyPathsCache = new Map();

// Initialisation de la carte Leaflet
const map = L.map('map', {
    zoomControl: false
}).setView([50.5, 6.5], 6);

L.control.zoom({ position: 'bottomright' }).addTo(map);

// Fond de carte sombre Esri Canvas Dark
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: '&copy; Esri &mdash; Radar Ferroviaire NeTEx RT',
    maxZoom: 16
}).addTo(map);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
    attribution: '',
    maxZoom: 16
}).addTo(map);

// =========================================================================
// 1. Déduction & Traitement Client (Sans altérer les modèles backend)
// =========================================================================

function getMarkerNetwork(m) {
    if (!m) return 'eurostar';
    const id = m.id || '';
    const num = m.lineNumber || m.vehicleNumber || '';
    const fillColor = (m.fillColor || '').toUpperCase();

    if (id.includes(':Sleeper:') || id.includes('ES_') || num.startsWith('ES') || fillColor === '#FF3602') {
        return 'european_sleeper';
    }
    return 'eurostar';
}

function getNetworkMeta(networkKey) {
    if (networkKey === 'european_sleeper') {
        return {
            key: 'european_sleeper',
            name: 'European Sleeper',
            badge: '🌙',
            color: '#FF3602',
            textColor: '#FFFFFF',
            tag: '🌙 Sleeper',
            tagClass: 'sleeper',
            netexId: 'BE:Network:EuropeanSleeper'
        };
    }
    return {
        key: 'eurostar',
        name: 'Eurostar',
        badge: '🚆',
        color: '#116BFE',
        textColor: '#FFFFFF',
        tag: '🚆 Eurostar',
        tagClass: 'eurostar',
        netexId: 'FR:Network:Eurostar'
    };
}

function computeDelayFromCalls(calls) {
    if (!calls || calls.length === 0) return { delaySec: 0, delayStr: "À l'heure", isDelayed: false };
    
    // Recherche le premier arrêt non passé ou le dernier avec retard
    for (const c of calls) {
        if (c.callStatus === 'SCHEDULED' || c.callStatus === 'EXPECTED') {
            const aimed = c.aimedArrivalTime || c.aimedTime;
            const exp = c.expectedArrivalTime || c.expectedTime;
            if (aimed && exp) {
                const diffMs = new Date(exp).getTime() - new Date(aimed).getTime();
                const diffSec = Math.round(diffMs / 1000);
                if (diffSec > 60) {
                    const mins = Math.floor(diffSec / 60);
                    return { delaySec: diffSec, delayStr: `+${mins} min`, isDelayed: true };
                }
            }
        }
    }
    return { delaySec: 0, delayStr: "À l'heure", isDelayed: false };
}

// Centrage de la carte
function fitNetworkView(networkId) {
    if (networkId === 'eurostar' || networkId === 'FR:Network:Eurostar') {
        map.flyTo([50.8, 3.5], 7, { duration: 0.9 });
    } else if (networkId === 'european_sleeper' || networkId === 'BE:Network:EuropeanSleeper') {
        map.flyTo([50.5, 9.5], 6, { duration: 0.9 });
    } else {
        map.flyTo([50.5, 6.5], 6, { duration: 0.9 });
    }
}

// Mise à jour visuelle du branding de l'en-tête
function updateBranding(networkId) {
    const badgeEl = document.getElementById('brand-badge');
    const titleEl = document.getElementById('brand-title');
    const subtitleEl = document.getElementById('brand-subtitle');

    if (!badgeEl || !titleEl || !subtitleEl) return;

    badgeEl.className = 'brand-badge';
    if (networkId === 'european_sleeper' || networkId === 'BE:Network:EuropeanSleeper') {
        badgeEl.textContent = '🌙';
        badgeEl.style.background = 'linear-gradient(135deg, #FF3602, #b91c1c)';
        badgeEl.style.boxShadow = '0 0 16px rgba(255, 54, 2, 0.5)';
        titleEl.textContent = 'European Sleeper';
        subtitleEl.textContent = 'Trains de nuit trans-européens';
        subtitleEl.style.color = '#FF3602';
    } else if (networkId === 'eurostar' || networkId === 'FR:Network:Eurostar') {
        badgeEl.textContent = '🚆';
        badgeEl.style.background = 'linear-gradient(135deg, #116BFE, #004ecc)';
        badgeEl.style.boxShadow = '0 0 16px rgba(17, 107, 254, 0.5)';
        titleEl.textContent = 'Eurostar Radar';
        subtitleEl.textContent = 'Grande Vitesse & Transmanche';
        subtitleEl.style.color = '#116BFE';
    } else {
        badgeEl.textContent = '🌐';
        badgeEl.style.background = 'linear-gradient(135deg, #116BFE, #FF3602)';
        badgeEl.style.boxShadow = '0 0 16px rgba(17, 107, 254, 0.35)';
        titleEl.textContent = 'Radar Ferroviaire';
        subtitleEl.textContent = 'Eurostar & European Sleeper';
        subtitleEl.style.color = '#00d2ff';
    }
}

// =========================================================================
// 2. Récupération Asynchrone des Endpoints NeTEx
// =========================================================================

async function fetchNetworks() {
    try {
        const res = await fetch('/api/networks');
        if (res.ok) {
            networksData = await res.json();
            // Met à jour les couleurs des variables CSS si nécessaire
            networksData.forEach(net => {
                if (net.color && net.id.includes('Eurostar')) {
                    document.documentElement.style.setProperty('--eurostar-brand', `#${net.color}`);
                }
                if (net.color && net.id.includes('Sleeper')) {
                    document.documentElement.style.setProperty('--sleeper-brand', `#${net.color}`);
                }
            });
        }
    } catch (e) {
        console.warn('Impossible de charger /api/networks:', e);
    }
}

async function fetchVehicleMarkers() {
    try {
        const res = await fetch('/api/vehicle-journeys/markers');
        if (!res.ok) return [];
        const data = await res.json();
        return data.items || [];
    } catch (e) {
        console.error('Erreur chargement /api/vehicle-journeys/markers:', e);
        return [];
    }
}

async function getOrFetchJourney(journeyId) {
    if (journeyDetailsCache.has(journeyId)) {
        return journeyDetailsCache.get(journeyId);
    }
    try {
        // Encodage propre du chemin NeTEx
        const cleanId = encodeURIComponent(journeyId);
        const res = await fetch(`/api/vehicle-journeys/${cleanId}`);
        if (!res.ok) return null;
        const details = await res.json();
        journeyDetailsCache.set(journeyId, details);
        return details;
    } catch (e) {
        console.warn(`Erreur détails voyage ${journeyId}:`, e);
        return null;
    }
}

async function getOrFetchPath(journeyId) {
    if (journeyPathsCache.has(journeyId)) {
        return journeyPathsCache.get(journeyId);
    }
    try {
        const cleanId = encodeURIComponent(journeyId);
        const res = await fetch(`/api/vehicle-journeys/${cleanId}/paths`);
        if (!res.ok) return null;
        const data = await res.json();
        journeyPathsCache.set(journeyId, data);
        return data;
    } catch (e) {
        console.warn(`Erreur tracé ${journeyId}:`, e);
        return null;
    }
}

// Préchargement paresseux en tâche de fond pour enrichir progressivement les cartes
async function enrichVisibleCardsInBackground(markers) {
    for (const m of markers) {
        if (!journeyDetailsCache.has(m.id)) {
            // Requête légère non bloquante
            getOrFetchJourney(m.id).then(details => {
                if (details) {
                    updateCardContent(m.id, details);
                }
            });
            // Petit intervalle pour ne pas surcharger le réseau
            await new Promise(r => setTimeout(r, 60));
        } else {
            const details = journeyDetailsCache.get(m.id);
            if (details) updateCardContent(m.id, details);
        }
    }
}

function updateCardContent(journeyId, details) {
    const card = document.querySelector(`.train-card[data-id="${journeyId}"]`);
    if (!card) return;

    // Destination & origine
    const routeEl = card.querySelector('.card-route');
    if (routeEl && details.calls && details.calls.length > 0) {
        const origin = details.calls[0].stopName || 'Départ';
        const dest = details.destination || details.calls[details.calls.length - 1].stopName || 'Arrivée';
        routeEl.innerHTML = `<span>${origin}</span> ➔ <span>${dest}</span>`;
    }

    // Retard
    const topEl = card.querySelector('.card-top');
    if (topEl) {
        const delayInfo = computeDelayFromCalls(details.calls);
        const pillEl = topEl.querySelector('.delay-pill');
        if (pillEl) {
            pillEl.className = `delay-pill ${delayInfo.isDelayed ? 'delay-warning' : 'delay-ontime'}`;
            pillEl.textContent = delayInfo.delayStr;
        }
    }

    // Arrêts supprimés éventuels
    const skippedCount = (details.calls || []).filter(c => c.callStatus === 'SKIPPED').length;
    if (skippedCount > 0) {
        const badgeTag = card.querySelector('.skipped-notice-tag');
        if (!badgeTag) {
            const statusEl = card.querySelector('.card-status-text');
            if (statusEl) {
                const tag = document.createElement('div');
                tag.className = 'skipped-notice-tag';
                tag.style.marginTop = '4px';
                tag.innerHTML = `⚠️ ${skippedCount} arrêt(s) supprimé(s)`;
                statusEl.appendChild(tag);
            }
        }
    }
}

// =========================================================================
// 3. Rendu Principal de l'Interface
// =========================================================================

function renderUI(markers) {
    cachedMarkers = markers || [];

    // 1. Filtrage par réseau
    const networkMarkers = cachedMarkers.filter(m => {
        if (currentNetwork === 'all') return true;
        const net = getMarkerNetwork(m);
        return net === currentNetwork || (currentNetwork.includes('Eurostar') && net === 'eurostar') || (currentNetwork.includes('Sleeper') && net === 'european_sleeper');
    });

    // 2. Calcul des KPIs en temps réel
    let runningCount = networkMarkers.length;
    let delayedCount = 0;
    let totalCount = networkMarkers.length;

    networkMarkers.forEach(m => {
        if (journeyDetailsCache.has(m.id)) {
            const d = journeyDetailsCache.get(m.id);
            if (d && computeDelayFromCalls(d.calls).isDelayed) {
                delayedCount++;
            }
        }
    });

    const elRunning = document.getElementById('kpi-running');
    if (elRunning) elRunning.textContent = runningCount;

    const elDeparting = document.getElementById('kpi-departing');
    if (elDeparting) elDeparting.textContent = Math.round(runningCount * 0.2); // Rames proches du départ

    const elDelayed = document.getElementById('kpi-delayed');
    if (elDelayed) elDelayed.textContent = delayedCount;

    const elTotal = document.getElementById('kpi-total');
    if (elTotal) elTotal.textContent = totalCount;

    // 3. Filtrage par chip & recherche
    const filteredMarkers = networkMarkers.filter(m => {
        const isSleeper = getMarkerNetwork(m) === 'european_sleeper';
        const num = (m.lineNumber || m.vehicleNumber || '').toLowerCase();
        const details = journeyDetailsCache.get(m.id);

        if (currentFilter === 'delayed') {
            if (!details || !computeDelayFromCalls(details.calls).isDelayed) return false;
        } else if (currentFilter === 'ontime') {
            if (details && computeDelayFromCalls(details.calls).isDelayed) return false;
        } else if (currentFilter === 'skipped') {
            if (!details || !(details.calls || []).some(c => c.callStatus === 'SKIPPED')) return false;
        }

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            const matchNum = num.includes(q);
            let matchDest = false;
            let matchOrig = false;
            if (details) {
                matchDest = (details.destination || '').toLowerCase().includes(q);
                matchOrig = details.calls && details.calls[0] && details.calls[0].stopName.toLowerCase().includes(q);
            }
            if (!matchNum && !matchDest && !matchOrig) return false;
        }

        return true;
    });

    // 4. Rendu de la barre latérale
    const listEl = document.getElementById('train-list');
    listEl.innerHTML = '';

    if (filteredMarkers.length === 0) {
        listEl.innerHTML = `
            <div style="padding: 24px 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                Aucun train ne correspond aux filtres actuels.
            </div>
        `;
    }

    filteredMarkers.forEach(m => {
        const netKey = getMarkerNetwork(m);
        const meta = getNetworkMeta(netKey);
        const trainNum = m.lineNumber || m.vehicleNumber || 'Train';
        const isSelected = activeSelectedId === m.id;

        const card = document.createElement('div');
        card.className = `train-card ${netKey === 'european_sleeper' ? 'network-sleeper' : ''} ${isSelected ? 'selected' : ''}`;
        card.setAttribute('data-id', m.id);

        // Récupère les infos si déjà en cache
        let destText = 'Destination en cours...';
        let originText = meta.name;
        let delayBadge = `<div class="delay-pill delay-ontime">À l'heure</div>`;

        if (journeyDetailsCache.has(m.id)) {
            const d = journeyDetailsCache.get(m.id);
            if (d) {
                if (d.calls && d.calls.length > 0) {
                    originText = d.calls[0].stopName;
                    destText = d.destination || d.calls[d.calls.length - 1].stopName;
                }
                const del = computeDelayFromCalls(d.calls);
                delayBadge = `<div class="delay-pill ${del.isDelayed ? 'delay-warning' : 'delay-ontime'}">${del.delayStr}</div>`;
            }
        }

        card.innerHTML = `
            <div class="card-top">
                <div class="train-id-badge">
                    <span class="operator-tag ${meta.tagClass}">${meta.tag}</span>
                    <span>${trainNum}</span>
                </div>
                ${delayBadge}
            </div>
            <div class="card-route">
                <span>${originText}</span> ➔ <span>${destText}</span>
            </div>
            <div class="card-status-text">
                <span>📍</span> En circulation • Cap ${Math.round(m.position.bearing || 0)}°
            </div>
        `;

        card.onclick = () => selectTrain(m.id);
        listEl.appendChild(card);
    });

    // 5. Mise à jour des marqueurs Leaflet
    updateMapMarkers(filteredMarkers);

    // 6. Enrichissement progressif en arrière-plan
    enrichVisibleCardsInBackground(filteredMarkers);
}

// Mise à jour des marqueurs Leaflet sur la carte
function updateMapMarkers(markersToDisplay) {
    // Nettoyage ancien
    Object.values(markersMap).forEach(m => map.removeLayer(m));
    markersMap = {};

    // Détection des positions identiques pour dispersion en rosace
    const posCounts = {};
    markersToDisplay.forEach(m => {
        const key = `${m.position.latitude.toFixed(4)}_${m.position.longitude.toFixed(4)}`;
        posCounts[key] = (posCounts[key] || 0) + 1;
    });

    const posIndex = {};

    markersToDisplay.forEach(m => {
        const key = `${m.position.latitude.toFixed(4)}_${m.position.longitude.toFixed(4)}`;
        let mLat = m.position.latitude;
        let mLon = m.position.longitude;

        if (posCounts[key] > 1) {
            const idx = posIndex[key] || 0;
            posIndex[key] = idx + 1;
            const angle = (idx * 2 * Math.PI) / posCounts[key];
            const radius = 0.009 + (Math.floor(idx / 8) * 0.005);
            mLat += radius * Math.cos(angle);
            mLon += radius * Math.sin(angle) * 1.5;
        }

        const netKey = getMarkerNetwork(m);
        const isSleeper = netKey === 'european_sleeper';
        const trainNum = m.lineNumber || m.vehicleNumber || '';
        const markerColor = m.fillColor || (isSleeper ? '#FF3602' : '#116BFE');
        const isSelected = activeSelectedId === m.id;

        const html = `
            <div class="train-marker ${isSleeper ? 'network-sleeper' : ''} ${isSelected ? 'selected-train' : ''}" style="color:${markerColor}">
                <div class="train-marker-label" style="background:${markerColor}">${trainNum}</div>
                <div class="train-marker-body" style="transform: rotate(${m.position.bearing || 0}deg);">
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
            selectTrain(m.id, false);
        });

        markersMap[m.id] = marker;
    });
}

// =========================================================================
// 4. Sélection d'un Train & Affichage des Arrêts NeTEx
// =========================================================================

async function selectTrain(journeyId, shouldFly = true) {
    activeSelectedId = journeyId;

    // Mise à jour de l'état sélectionné sur les cartes
    document.querySelectorAll('.train-card').forEach(c => c.classList.remove('selected'));
    const cardEl = document.querySelector(`.train-card[data-id="${journeyId}"]`);
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
                if (id === journeyId) b.classList.add('selected-train');
                else b.classList.remove('selected-train');
            }
        }
    });

    // Nettoyage de l'ancien tracé GPS
    activeRouteLayers.forEach(l => map.removeLayer(l));
    activeRouteLayers = [];

    // Récupération asynchrone des détails et du tracé
    const [details, pathData] = await Promise.all([
        getOrFetchJourney(journeyId),
        getOrFetchPath(journeyId)
    ]);

    if (!details) return;

    // Affichage du tracé GPS sur la carte
    if (pathData && pathData.path && pathData.path.length > 1) {
        const routePts = pathData.path.map(pt => [pt[0], pt[1]]);
        const isSleeper = getMarkerNetwork({ id: journeyId }) === 'european_sleeper';
        const glowColor = isSleeper ? '#FF3602' : '#116BFE';
        const coreColor = isSleeper ? '#ffedd5' : '#dbeafe';

        const glow = L.polyline(routePts, {
            color: glowColor,
            weight: 8,
            opacity: 0.5,
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

    // Ouverture du volet latéral avec les arrêts NeTEx
    openDetailPanel(details);

    const marker = markersMap[journeyId];
    if (marker && shouldFly) {
        map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 7), { duration: 0.8 });
    }
}

function openDetailPanel(details) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    if (!panel || !content) return;

    const netKey = details.networkId && details.networkId.includes('Sleeper') ? 'european_sleeper' : 'eurostar';
    const meta = getNetworkMeta(netKey);
    const delayInfo = computeDelayFromCalls(details.calls);
    const origin = details.calls && details.calls[0] ? details.calls[0].stopName : 'Départ';
    const destination = details.destination || (details.calls && details.calls[details.calls.length - 1].stopName) || 'Arrivée';

    // Rendu des arrêts NeTEx
    const stopsHtml = (details.calls || []).map(c => {
        const isSkipped = c.callStatus === 'SKIPPED';
        const isPassed = c.callStatus === 'PASSED';
        const track = c.platformName ? `<span style="color:#94a3b8;font-size:0.7rem;"> (Voie ${c.platformName})</span>` : '';
        const stopCode = c.stopRef ? `<span style="font-family:'JetBrains Mono';font-size:0.65rem;color:#64748b;">${c.stopRef}</span>` : '';

        // Formatage des heures ISO
        const formatTime = (tStr) => {
            if (!tStr) return '--:--';
            try {
                const d = new Date(tStr);
                return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            } catch {
                return tStr;
            }
        };

        const schedTime = formatTime(c.aimedArrivalTime || c.aimedTime);
        const estTime = formatTime(c.expectedArrivalTime || c.expectedTime);

        if (isSkipped) {
            return `
                <div class="stop-item skipped">
                    <div class="stop-item-title" style="text-decoration: line-through; color: #f87171;">
                        ${c.stopName} <span class="badge-skipped">ARRÊT SUPPRIMÉ</span>
                    </div>
                    <div class="stop-item-time" style="color: #64748b;">
                        Arrêt non desservi • Prévu : ${schedTime}
                    </div>
                </div>
            `;
        }

        let timeLabel = `Prévu : ${schedTime}`;
        if (estTime && estTime !== schedTime) {
            timeLabel += ` ➔ Estimé : <b style="color:var(--status-warning);">${estTime}</b>`;
        }

        return `
            <div class="stop-item ${isPassed ? 'passed' : ''}">
                <div class="stop-item-title">
                    ${c.stopName} ${track}
                </div>
                <div class="stop-item-time">
                    ${timeLabel}
                </div>
                <div>${stopCode}</div>
            </div>
        `;
    }).join('');

    content.innerHTML = `
        <div class="detail-header">
            <div>
                <div style="margin-bottom: 4px;">
                    <span class="operator-tag ${meta.tagClass}">${meta.tag}</span>
                </div>
                <div class="detail-title">${meta.name} N°${details.vehicle?.number || details.id.split(':').pop()}</div>
                <div class="detail-subtitle">${origin} ➔ ${destination}</div>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div class="delay-pill ${delayInfo.isDelayed ? 'delay-warning' : 'delay-ontime'}">${delayInfo.delayStr}</div>
                <button class="detail-close-btn" onclick="clearActiveRoute()" title="Fermer le panneau">✕</button>
            </div>
        </div>
        <div class="detail-body">
            <div class="detail-status-pill">
                <span>📍</span> ${details.position.atStop ? "À quai en gare" : "En circulation sur voie"}
            </div>
            <div class="detail-section-title">
                Arrêts NeTEx & Horaires officiels
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

// =========================================================================
// 5. Gestionnaires d'Événements & Boucle de Rafraîchissement
// =========================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Menu déroulant Réseau
    const networkSelectEl = document.getElementById('network-select');
    if (networkSelectEl) {
        networkSelectEl.addEventListener('change', (e) => {
            currentNetwork = e.target.value;
            updateBranding(currentNetwork);
            fitNetworkView(currentNetwork);
            clearActiveRoute();
            renderUI(cachedMarkers);
        });
    }

    // Filtres Chips
    document.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            renderUI(cachedMarkers);
        });
    });

    // Recherche
    const searchEl = document.getElementById('search-input');
    if (searchEl) {
        searchEl.addEventListener('input', (e) => {
            searchQuery = e.target.value.trim();
            renderUI(cachedMarkers);
        });
    }

    // Recentrage
    const recenterBtn = document.getElementById('btn-recenter');
    if (recenterBtn) {
        recenterBtn.addEventListener('click', () => {
            fitNetworkView(currentNetwork);
        });
    }

    // Clic sur fond de carte
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
            refreshData();
        });
    }
});

// Timer de rafraîchissement
let secondsLeft = 30;
function updateRefreshTimer() {
    secondsLeft--;
    if (secondsLeft <= 0) {
        refreshData();
        secondsLeft = 30;
    }
    const timerEl = document.getElementById('refresh-timer');
    if (timerEl) timerEl.textContent = `${secondsLeft}s`;
}
setInterval(updateRefreshTimer, 1000);

// Rafraîchissement principal des données
async function refreshData() {
    const markers = await fetchVehicleMarkers();
    renderUI(markers);
}

// Initialisation globale
async function initApp() {
    await fetchNetworks();
    await refreshData();
}

initApp();