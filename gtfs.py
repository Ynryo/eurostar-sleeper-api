import os
import sys
import webbrowser
import threading
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from config import HOST, PORT, STATIC_DIR
from api_models import (
    NetworkItem,
    NetworkLineItem,
    NetworkDetails,
    MarkerCollection,
    JourneyDetails,
    JourneyPath
)
from bus_tracker_service import (
    get_cached_raw_data,
    get_networks_list,
    get_network_lines,
    get_vehicle_markers,
    get_journey_details,
    get_journey_path
)

# Configuration UTF-8 sur Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

app = FastAPI(
    title="Eurostar & European Sleeper Radar API",
    description="API standardisée pour les flux ferroviaires Eurostar et European Sleeper.",
    version="1.0.0"
)

# Configuration CORS pour autoriser les requêtes de frontends ou services externes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================================
# Endpoints Réseaux & Lignes
# =========================================================================

@app.get(
    "/api/networks",
    response_model=List[NetworkItem],
    tags=["Networks"],
    summary="Liste tous les réseaux de transports disponibles"
)
def get_networks():
    return get_networks_list()

@app.get(
    "/api/networks/{network_id:path}/lines",
    response_model=List[NetworkLineItem],
    tags=["Networks"],
    summary="Liste des lignes d'un réseau de transport"
)
def get_lines(network_id: str):
    lines = get_network_lines(network_id)
    if lines is None:
        raise HTTPException(status_code=404, detail="Réseau non trouvé")
    return lines

@app.get(
    "/api/networks/{network_id:path}",
    response_model=NetworkDetails,
    tags=["Networks"],
    summary="Détails d'un réseau avec ses lignes associées (compatible BusTrackerClient ?withDetails=true)"
)
def get_network_details_endpoint(network_id: str, withDetails: bool = False):
    s_id = str(network_id).strip()
    net = next((
        n for n in get_networks_list() 
        if str(n["id"]) == s_id 
        or n["ref"] == s_id 
        or n.get("networkRef") == s_id
        or (s_id in ("1", "101") and "Eurostar" in n["name"]) 
        or (s_id in ("2", "102") and "Sleeper" in n["name"])
    ), None)
    if not net:
        raise HTTPException(status_code=404, detail="Réseau non trouvé")
    lines = get_network_lines(network_id) or []
    return {**net, "lines": lines, "operators": []}

# =========================================================================
# Endpoints Trajets & Positions Temps Réel
# =========================================================================

@app.get(
    "/api/vehicle-journeys/markers",
    response_model=MarkerCollection,
    tags=["Markers"],
    summary="Positions en direct des trains dans une zone géographique (bounding box)"
)
def get_markers(
    swLat: Optional[float] = Query(None, description="Latitude sud-ouest"),
    swLon: Optional[float] = Query(None, description="Longitude sud-ouest"),
    neLat: Optional[float] = Query(None, description="Latitude nord-est"),
    neLon: Optional[float] = Query(None, description="Longitude nord-est")
):
    return get_vehicle_markers(sw_lat=swLat, sw_lon=swLon, ne_lat=neLat, ne_lon=neLon)

@app.get(
    "/api/vehicle-journeys/{journey_id:path}/paths",
    response_model=JourneyPath,
    tags=["Journeys"],
    summary="Tracé géographique (polyline GPS 3D [lat, lon, distance]) d'un train"
)
def get_journey_path_route(journey_id: str):
    path_data = get_journey_path(journey_id)
    if not path_data:
        raise HTTPException(status_code=404, detail="Tracé non trouvé pour ce trajet")
    return path_data

@app.get(
    "/api/vehicle-journeys/{journey_id:path}",
    response_model=JourneyDetails,
    tags=["Journeys"],
    summary="Fiche détaillée d'un trajet de train (arrêts avec codes UIC, horaires, retards, quai)"
)
def get_journey(journey_id: str):
    journey = get_journey_details(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Trajet de train non trouvé")
    return journey

@app.get(
    "/api/paths/{path_id:path}",
    response_model=JourneyPath,
    tags=["Paths"],
    summary="Alias de récupération du tracé GPS d'un trajet"
)
def get_path_alias(path_id: str):
    path_data = get_journey_path(path_id)
    if not path_data:
        raise HTTPException(status_code=404, detail="Tracé non trouvé")
    return path_data

# =========================================================================
# Route de rétrocompatibilité pour le visualiseur Leaflet existant
# =========================================================================

@app.get(
    "/api/data",
    tags=["Legacy"],
    summary="Flux global hérité (trains, gares, shapes) pour le frontend Leaflet existant"
)
def get_legacy_data():
    return get_cached_raw_data()

# =========================================================================
# Fichiers statiques et interface web
# =========================================================================

@app.get("/", include_in_schema=False)
def serve_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Eurostar & Sleeper API active. Rendez-vous sur /docs pour Swagger."}

@app.get("/map.html", include_in_schema=False)
def serve_map():
    return serve_root()

@app.get("/style.css", include_in_schema=False)
def serve_css():
    css_path = os.path.join(STATIC_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path)
    raise HTTPException(status_code=404, detail="style.css non trouvé")

@app.get("/app.js", include_in_schema=False)
def serve_js():
    js_path = os.path.join(STATIC_DIR, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path)
    raise HTTPException(status_code=404, detail="app.js non trouvé")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def open_browser_later():
    time.sleep(1.2)
    if not os.environ.get("DOCKER"):
        url = f"http://localhost:{PORT}/"
        try:
            webbrowser.open(url)
        except Exception:
            pass

def main():
    print("📡 Analyse complète des réseaux Eurostar et European Sleeper...")
    data = get_cached_raw_data()

    trains = data.get('trains', [])
    eurostar_trains = [t for t in trains if t.get('network') == 'eurostar']
    sleeper_trains = [t for t in trains if t.get('network') == 'european_sleeper']
    running = [t for t in trains if t['status'] == 'RUNNING']
    delayed = [t for t in trains if t['delay_sec'] > 0]
    ontime = [t for t in trains if t['delay_sec'] == 0]

    print("\n" + "=" * 75)
    print(f"        RADAR FERROVIAIRE EUROPÉEN — STATISTIQUES ({data.get('date', '')})")
    print("=" * 75)
    print(f"🚆 Trains Eurostar : {len(eurostar_trains)}")
    print(f"🌙 Trains European Sleeper : {len(sleeper_trains)}")
    print(f"⚡ Trains actuellement en circulation : {len(running)}")
    print(f"🟢 Trains à l'heure : {len(ontime)}")
    print(f"🚨 Trains avec retard : {len(delayed)}")
    print(f"📋 Total trajets répertoriés : {len(trains)}")
    print("=" * 75)
    print(f"📖 Documentation Swagger interactive : http://localhost:{PORT}/docs")
    print(f"🚀 Serveur web actif sur : http://{HOST}:{PORT}/")

    threading.Thread(target=open_browser_later, daemon=True).start()

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")

if __name__ == "__main__":
    main()