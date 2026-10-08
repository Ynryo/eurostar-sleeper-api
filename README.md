# 🚆 Eurostar & European Sleeper Radar API

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](requirements.txt)
[![GTFS-RT](https://img.shields.io/badge/GTFS--RT-Live%20Feed-10B981)](#-sources-de-donn%C3%A9es)
[![BRouter](https://img.shields.io/badge/OSM-BRouter%20Rail-F59E0B)](#-routage-ferroviaire-physique-brouter)

> **API et Radar temps réel multi-réseaux** pour les trains à grande vitesse **Eurostar** (Grande-Bretagne, France, Belgique, Pays-Bas, Allemagne) et les trains de nuit trans-européens **European Sleeper** (Bruxelles, Amsterdam, Berlin, Prague).
> 
> Conçu pour alimenter l'écosystème de supervision de transport **[Spotted API](https://api.spotted.ynryo.fr)** et les applications de cartographie en temps réel.

---

## 🎯 Fonctionnalités Clés

- **🌐 Multi-réseaux unifié** : Fusion transparente des flux GTFS statiques et des mises à jour temps réel (GTFS-RT) d'Eurostar et d'European Sleeper.
- **🧭 Suivi ferroviaire physique à 100 % (zéro vol d'oiseau)** :
  - Intégration du moteur **BRouter Rail** sur le graphe OpenStreetMap.
  - Modélisation exacte du **High Speed 1 (HS1)** britannique, du **Tunnel sous la Manche** et de la **LGV Nord**.
  - Jonction continue à la gare de **Lille Europe** pour éliminer les ruptures de tracé.
- **⚡ Cache local & simplification Ramer-Douglas-Peucker (RDP)** :
  - Tolérance $\epsilon \approx 10\text{ m}$ pour des courbes nettes et un payload JSON allégé.
  - Cache persistant local (`rail_shapes_cache.json`) garantissant **0 ms de latence** et zéro dépendance réseau au rafraîchissement.
- **📡 Radar opérationnel dynamique** :
  - Affichage exclusif des **trains en cours de circulation** (`RUNNING`) et des **départs imminents sous 20 minutes** (`SCHEDULED`).
  - Suppression de la pollution visuelle des dizaines de trains inactifs ou terminés.
  - Calcul dynamique de l'orientation de l'icône (`bearing`) selon le cap de la voie ferrée.
- **🖥️ Interface cartographique moderne intégrée** :
  - Thème sombre épuré, typographie Google Fonts et micro-animations.
  - Sélecteur de réseau instantané (Eurostar / European Sleeper / Tous).
  - KPIs en direct (En circulation, Départ < 20 min, En retard, Actifs sur radar).

---

## 🏗️ Architecture du Projet

```text
eurostar-sleeper-api/
├── config.py                 # Configuration centrale (ports, fuseaux horaires, URLs de flux)
├── gtfs.py                   # Serveur FastAPI et distribution des endpoints temps réel NeTEx
├── gtfs_service.py           # Ingestion GTFS/GTFS-RT, statuts radar et interpolation
├── rail_routing_service.py   # Client BRouter ferroviaire, simplification RDP et cache
├── rail_shapes_cache.json    # Cache local des géométries de voies calculées
├── regenerate_shapes.py      # Outil CLI de maintenance et régénération des tracés BRouter
├── static/                   # Frontend Web temps réel (Leaflet, JS Vanilla, CSS moderne)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── Dockerfile                # Image conteneur optimisée (Python 3.12-slim)
├── docker-compose.yml        # Orchestration locale prête à l'emploi
├── requirements.txt          # Dépendances Python minimales
└── .gitignore
```

---

## 🔌 Points d'Accès API

La documentation interactive **OpenAPI / Swagger** est accessible directement sur `http://localhost:8080/docs`.

### 1. `GET /api/networks`
Retourne la liste des réseaux gérés (Eurostar : 101, European Sleeper : 102) selon le standard européen NeTEx et Bus-Tracker.

### 2. `GET /api/networks/{network_id}?withDetails=true`
Retourne la fiche détaillée d'un réseau enrichie de ses lignes actives (`lines`) pour compatibilité native avec `BusTrackerClient` et `spotted-api`.

### 3. `GET /api/vehicle-journeys/markers`
Flux temps réel allégé pour la cartographie, avec filtrage optionnel par bounding box.
- **Query params :** `swLat`, `swLon`, `neLat`, `neLon` (optionnels)
- **Réponse :**
  ```json
  {
    "items": [
      {
        "id": "FR:Eurostar:VehicleJourney:9028-1006",
        "lineNumber": "9028",
        "vehicleNumber": "9028",
        "color": "#FFFFFF",
        "fillColor": "#116BFE",
        "position": {
          "latitude": 50.1867,
          "longitude": 2.8708,
          "bearing": 182.4,
          "type": "COMPUTED"
        }
      }
    ],
    "at": "2026-10-06T15:58:00Z"
  }
  ```

### 4. `GET /api/vehicle-journeys/{journey_id}`
Fiche détaillée d'un trajet de train avec arrêts formatés selon la nomenclature NeTEx/UIC (`FR:StopPoint:{CodeUIC}`, `BE:StopPoint:{CodeUIC}`), horaires ISO 8601, retards, voies/quais et position temps réel.

### 5. `GET /api/vehicle-journeys/{journey_id}/paths` *(ou `/api/paths/{path_id}`)*
Tracé ferroviaire 3D précis du train avec distance cumulée en mètres compatible `Path.php` (`spotted-api`) :
- **Réponse :**
  ```json
  {
    "path": {
      "p": [[50.1867, 2.8708, 0.0], [50.1912, 2.8754, 150.2]],
      "cancelled": []
    }
  }
  ```

---

## 🚀 Démarrage Rapide

### Option 1 : Avec Docker Compose (Recommandé)

```bash
# Cloner le projet
git clone https://github.com/Ynryo/eurostar-sleeper-api.git
cd eurostar-sleeper-api

# Démarrer le conteneur en arrière-plan
docker compose up -d
```
L'application et l'API sont immédiatement accessibles sur **`http://localhost:8080`**.

### Option 2 : En local avec Python

```bash
# Installer les dépendances
pip install -r requirements.txt

# Démarrer le serveur
python gtfs.py
```

### Maintenance du cache des tracés (BRouter)

Pour rafraîchir ou recalculer les polylines ferroviaires OpenStreetMap sans impacter l'API :

```bash
# Vérifier et ne recalculer que les tracés manquants ou en ligne droite
python regenerate_shapes.py --fallback-only

# Rafraîchir l'ensemble du cache avec délai de courtoisie (recommandé : 1s)
python regenerate_shapes.py --delay 1.0
```

---

## 🛠️ Sources de Données

| Opérateur | Type de flux | Source |
| :--- | :--- | :--- |
| **Eurostar** | GTFS Statique | `https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_static_commercial_v2.zip` |
| **Eurostar** | GTFS-RT (Temps Réel) | `https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_rt_v2.bin` |
| **European Sleeper** | GTFS Statique | `https://raw.githubusercontent.com/deryclem/european-sleeper-gtfs/main/gtfs-european-sleeper.zip` |
| **OpenStreetMap** | Routage Ferroviaire | API BRouter (`profile=rail`) |

---

## 👤 Auteur & Maintenance

Développé par **Ynryo** ([@Ynryo](https://github.com/Ynryo)) dans le cadre de la plateforme de transport **[Spotted](https://api.spotted.ynryo.fr)**.
