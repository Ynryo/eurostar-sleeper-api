# 🚄 Eurostar & European Sleeper Radar API

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](requirements.txt)
[![GTFS-RT](https://img.shields.io/badge/GTFS--RT-Live%20Feed-10B981)](#-sources-de-données)
[![BRouter](https://img.shields.io/badge/OSM-BRouter%20Rail-F59E0B)](#-routage-ferroviaire-physique-brouter)

> **API REST temps réel multi-réseaux** pour les trains à grande vitesse **Eurostar** (Grande-Bretagne, France, Belgique, Pays-Bas, Allemagne) et les trains de nuit trans-européens **European Sleeper** (Bruxelles, Amsterdam, Berlin, Prague).
> 
> Conçu pour alimenter l'écosystème de supervision de transport **[Spotted API](https://api.spotted.ynryo.fr)** et les applications tierces.

---

## 🎯 Fonctionnalités Clés

- **🌐 Multi-réseaux unifié** : Fusion transparente des flux GTFS statiques et des mises à jour temps réel (GTFS-RT) d'Eurostar et d'European Sleeper.
- **🧭 Suivi ferroviaire physique à 100 % (zéro vol d'oiseau)** :
  - Intégration du moteur **BRouter Rail** sur le graphe OpenStreetMap.
  - Modélisation exacte du **High Speed 1 (HS1)** britannique, du **Tunnel sous la Manche** et de la **LGV Nord**.
  - Jonction continue à la gare de **Lille Europe** pour éliminer les ruptures de tracé.
- **⚡ Cache local & simplification Ramer-Douglas-Peucker (RDP)** :
  - Tolérance $\epsilon \approx 10\text{ m}$ pour des courbes nettes et un payload JSON allégé.
  - Cache persistant local (`data/cache/rail_shapes_cache.json`) garantissant **0 ms de latence** et zéro dépendance réseau au rafraîchissement.
- **📡 Radar opérationnel dynamique** :
  - Exposition exclusive des **trains en cours de circulation** (`RUNNING`) et des **départs imminents sous 20 minutes** (`SCHEDULED`).
  - Suppression de la pollution des dizaines de trains inactifs ou terminés.
  - Calcul dynamique de l'orientation (`bearing`) selon le cap réel de la voie ferrée.

---

## 🏗️ Architecture du Projet

Le projet adopte une architecture modulaire standard FastAPI avec séparation claire des responsabilités :

```text
eurostar-sleeper-api/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Point d'entrée FastAPI, middlewares CORS, montage des routes
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py               # Configuration centrale (chemins data/cache, fuseaux horaires, URLs)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py               # Agrégation des sous-routeurs API
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── networks.py         # Endpoints /api/networks et /api/networks/{id}
│   │       └── journeys.py         # Endpoints /api/vehicle-journeys, markers et paths
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── schemas.py              # Modèles Pydantic standardisés NeTEx / Spotted
│   ├── services/
│   │   ├── __init__.py
│   │   ├── train_tracker.py        # Logique métier Spotted/NeTEx (markers, calls, formatage trains)
│   │   ├── gtfs_engine.py          # Ingestion GTFS statique & GTFS-RT, interpolation et radar
│   │   └── rail_router.py          # Client BRouter ferroviaire, cache géométrique et simplification RDP
│   └── utils/
│       ├── __init__.py
│       └── geo.py                  # Fonctions mathématiques & géodésiques (Haversine, bearing, RDP)
├── data/
│   ├── cache/
│   │   └── rail_shapes_cache.json  # Cache local persistant des géométries de voies ferroviaires
│   └── gtfs/                       # Archives ZIP GTFS téléchargées automatiquement
├── scripts/
│   └── regenerate_shapes.py        # Outil CLI de maintenance et régénération des tracés BRouter
├── tests/
│   ├── __init__.py
│   └── test_endpoints.py           # Suite de tests d'intégration et de validation des contrats d'API
├── Dockerfile                      # Image conteneur optimisée (Python 3.12-slim)
├── docker-compose.yaml             # Orchestration Docker
├── requirements.txt                # Dépendances Python minimales
└── .gitignore
```

---

## 🔌 Points d'Accès API

La documentation interactive **OpenAPI / Swagger** est accessible directement sur `http://localhost:8080/docs`.

### 1. `GET /api/networks`
Retourne la liste des réseaux gérés (Eurostar : 10001, European Sleeper : 10002) selon le standard européen NeTEx et Bus-Tracker.

### 2. `GET /api/networks/{network_id}?withDetails=true`
Retourne la fiche détaillée d'un réseau enrichie de ses lignes actives (`lines`) pour compatibilité native avec `BusTrackerClient` et `spotted-api`.

### 3. `GET /api/vehicle-journeys/markers`
Flux temps réel allégé pour la supervision et la cartographie, avec filtrage optionnel par bounding box.
- **Query params :** `swLat`, `swLon`, `neLat`, `neLon` (optionnels)
- **Réponse :**
  ```json
  {
    "items": [
      {
        "id": "FR:Network:Eurostar::VehicleJourney:9028-1006",
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
L'API et Swagger sont immédiatement accessibles sur **`http://localhost:8080/docs`**.

### Option 2 : En local avec Python

```bash
# Installer les dépendances
pip install -r requirements.txt

# Démarrer le serveur API
python -m app.main
```

### Exécution des Tests

```bash
python tests/test_endpoints.py
```

### Maintenance du cache des tracés (BRouter)

Pour rafraîchir ou recalculer les polylines ferroviaires OpenStreetMap sans impacter l'API :

```bash
# Vérifier et ne recalculer que les tracés manquants ou en ligne droite
python scripts/regenerate_shapes.py --fallback-only

# Rafraîchir l'ensemble du cache avec délai de courtoisie (recommandé : 1s)
python scripts/regenerate_shapes.py --delay 1.0
```

---

## 🛠️ Sources de Données

| Opérateur | Type de flux | Source |
| :--- | :--- | :--- |
| **Eurostar** | GTFS Statique | `https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_static_commercial_v2.zip` |
| **Eurostar** | GTFS-RT (Temps Réel) | `https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_rt_v2.bin` |
| **European Sleeper** | GTFS Statique | `https://jbb.ghsq.de/gtfs/eu-es.gtfs.zip` |
| **OpenStreetMap** | Routage Ferroviaire | API BRouter (`profile=rail`) |

---

## 👤 Auteur & Maintenance

Développé par **Ynryo** ([@Ynryo](https://github.com/Ynryo)) dans le cadre de la plateforme de transport **[Spotted](https://api.spotted.ynryo.fr)**.
