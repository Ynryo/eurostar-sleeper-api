import time
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from config import EUROSTAR_TZ, EUROPEAN_SLEEPER_TZ
from gtfs_service import build_network_data

CACHE_TTL = 15  # secondes

_cache_data = None
_cache_time = 0

def get_cached_raw_data():
    global _cache_data, _cache_time
    now = time.time()
    if not _cache_data or (now - _cache_time > CACHE_TTL):
        _cache_data = build_network_data()
        _cache_time = now
    return _cache_data

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # mètres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def format_iso_time(time_str: Optional[str], tz_offset_hours: int = 2) -> Optional[str]:
    """Convertit 'HH:MM' ou 'HH:MM:SS' en ISO 8601 (YYYY-MM-DDTHH:MM:SS+02:00)."""
    if not time_str or time_str == '--:--':
        return None
    try:
        parts = time_str.split(':')
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0

        # Gestion des heures >= 24h dans GTFS
        day_add = h // 24
        h = h % 24

        today = datetime.now(EUROSTAR_TZ).date() + timedelta(days=day_add)
        sign = "+" if tz_offset_hours >= 0 else "-"
        return f"{today.isoformat()}T{h:02d}:{m:02d}:{s:02d}{sign}{abs(tz_offset_hours):02d}:00"
    except Exception:
        return None

def get_netex_stop_ref(stop: Dict[str, Any], is_sleeper: bool) -> str:
    """Génère un identifiant d'arrêt normalisé NeTEx (Code pays UIC + matricule)."""
    stop_uic = str(stop.get('stop_code') or stop.get('stop_id') or '')
    
    # Détection du code pays UIC selon la fiche UIC 920-14
    if stop_uic.startswith("87"):
        country = "FR"
    elif stop_uic.startswith("70"):
        country = "GB"
    elif stop_uic.startswith("88"):
        country = "BE"
    elif stop_uic.startswith("84"):
        country = "NL"
    elif stop_uic.startswith("80"):
        country = "DE"
    elif stop_uic.startswith("54"):
        country = "CZ"
    elif stop_uic.startswith("85"):
        country = "CH"
    elif stop_uic.startswith("81"):
        country = "AT"
    else:
        country = "BE" if is_sleeper else "FR"
        
    return f"{country}:StopPoint:{stop_uic}"

def format_journey_id(raw_id: Any, is_sleeper: bool) -> str:
    """Convertit un identifiant de course brut en identifiant NeTEx ServiceJourney."""
    str_id = str(raw_id)
    if str_id.startswith("FR:Eurostar:VehicleJourney:") or str_id.startswith("BE:Sleeper:VehicleJourney:"):
        return str_id
    if is_sleeper:
        return f"BE:Sleeper:VehicleJourney:{str_id}"
    else:
        return f"FR:Eurostar:VehicleJourney:{str_id}"

def extract_raw_journey_id(journey_id: str) -> str:
    """Extrait l'identifiant brut pour recherche interne si un ID NeTEx est fourni."""
    if ":VehicleJourney:" in journey_id:
        return journey_id.split(":VehicleJourney:")[-1]
    return journey_id

NETWORKS_METADATA = [
    {
        "id": 101,
        "ref": "FR:Network:Eurostar",
        "networkRef": "FR:Network:Eurostar",
        "name": "Eurostar",
        "authority": "Eurostar Group",
        "authorityRef": "FR:Authority:EurostarGroup",
        "countryCode": "FR",
        "timezone": "Europe/Paris",
        "logoHref": "https://upload.wikimedia.org/wikipedia/commons/3/33/Eurostar_logo_%282023%29.svg",
        "darkModeLogoHref": "https://upload.wikimedia.org/wikipedia/commons/3/33/Eurostar_logo_%282023%29.svg",
        "color": "116BFE",
        "textColor": "000000",
        "hasVehiclesFeature": True,
        "regionId": 16,
        "embedMapCenter": [2.355, 48.88, 7]
    },
    {
        "id": 102,
        "ref": "BE:Network:EuropeanSleeper",
        "networkRef": "BE:Network:EuropeanSleeper",
        "name": "European Sleeper",
        "authority": "European Sleeper BV",
        "authorityRef": "BE:Authority:EuropeanSleeperBV",
        "countryCode": "BE",
        "timezone": "Europe/Brussels",
        "logoHref": "https://upload.wikimedia.org/wikipedia/commons/3/3d/European_Sleeper_Logo.svg",
        "darkModeLogoHref": "https://upload.wikimedia.org/wikipedia/commons/3/3d/European_Sleeper_Logo.svg",
        "color": "FF3602",
        "textColor": "FFFFFF",
        "hasVehiclesFeature": True,
        "regionId": 16,
        "embedMapCenter": [4.35, 50.85, 6]
    }
]

def get_networks_list() -> List[Dict[str, Any]]:
    return NETWORKS_METADATA

def get_network_lines(network_id: Any) -> Optional[List[Dict[str, Any]]]:
    s_id = str(network_id).strip()
    net = next((
        n for n in NETWORKS_METADATA 
        if str(n["id"]) == s_id 
        or n["ref"] == s_id 
        or n.get("networkRef") == s_id
    ), None)

    if not net:
        return None

    data = get_cached_raw_data()
    euro_count = len([t for t in data['trains'] if t.get('network') == 'eurostar'])
    sleeper_count = len([t for t in data['trains'] if t.get('network') == 'european_sleeper'])

    if "Eurostar" in net["name"]:
        return [
            {
                "id": 1010,
                "ref": "FR:Line:Eurostar",
                "lineRef": "FR:Line:Eurostar",
                "references": ["FR:Line:Eurostar", "EUROSTAR:Line:1"],
                "number": "Eurostar",
                "girouetteNumber": None,
                "cartridgeHref": None,
                "color": "116BFE",
                "textColor": "FFFFFF",
                "sortOrder": 1,
                "archivedAt": None,
                "onlineMarkerCount": euro_count,
                "onlineVehicleCount": euro_count
            }
        ]
    elif "Sleeper" in net["name"]:
        return [
            {
                "id": 1020,
                "ref": "BE:Line:EuropeanSleeper",
                "lineRef": "BE:Line:EuropeanSleeper",
                "references": ["BE:Line:EuropeanSleeper", "EUROPEAN_SLEEPER:Line:1"],
                "number": "European Sleeper",
                "girouetteNumber": None,
                "cartridgeHref": None,
                "color": "FF3602",
                "textColor": "FFFFFF",
                "sortOrder": 1,
                "archivedAt": None,
                "onlineMarkerCount": sleeper_count,
                "onlineVehicleCount": sleeper_count
            }
        ]
    return []

def get_vehicle_markers(
    sw_lat: Optional[float] = None,
    sw_lon: Optional[float] = None,
    ne_lat: Optional[float] = None,
    ne_lon: Optional[float] = None
) -> Dict[str, Any]:
    data = get_cached_raw_data()
    now_iso = datetime.now(timezone.utc).isoformat()
    items = []

    for t in data.get('trains', []):
        lat = t.get('lat')
        lon = t.get('lon')
        if lat is None or lon is None:
            continue

        # Filtrage par Bounding Box si spécifiée
        if sw_lat is not None and lat < sw_lat:
            continue
        if ne_lat is not None and lat > ne_lat:
            continue
        if sw_lon is not None and lon < sw_lon:
            continue
        if ne_lon is not None and lon > ne_lon:
            continue

        is_sleeper = t.get('network') == 'european_sleeper'
        fill_color = "#FF3602" if is_sleeper else "#116BFE"
        journey_netex_id = format_journey_id(t.get('id'), is_sleeper)

        items.append({
            "id": journey_netex_id,
            "lineNumber": str(t.get('num', '')),
            "vehicleNumber": str(t.get('num', '')),
            "color": "#FFFFFF",
            "fillColor": fill_color,
            "position": {
                "latitude": lat,
                "longitude": lon,
                "bearing": float(t.get('bearing', 0.0)),
                "type": "COMPUTED"
            }
        })

    return {
        "items": items,
        "at": now_iso
    }

def get_journey_details(journey_id: str) -> Optional[Dict[str, Any]]:
    data = get_cached_raw_data()
    raw_id = extract_raw_journey_id(journey_id)
    train = next((t for t in data.get('trains', []) if str(t.get('id')) in (journey_id, raw_id)), None)
    if not train:
        return None

    is_sleeper = train.get('network') == 'european_sleeper'
    net_id = 102 if is_sleeper else 101
    net_ref = "BE:Network:EuropeanSleeper" if is_sleeper else "FR:Network:Eurostar"
    line_id = 1020 if is_sleeper else 1010
    line_ref = "BE:Line:EuropeanSleeper" if is_sleeper else "FR:Line:Eurostar"
    journey_netex_id = format_journey_id(train.get('id'), is_sleeper)
    tz_offset = 2

    # Construction des calls (arrêts)
    calls = []
    stops = train.get('stops', [])
    cum_distance = 0.0

    for idx, s in enumerate(stops):
        if idx > 0:
            cum_distance += haversine(stops[idx-1]['lat'], stops[idx-1]['lon'], s['lat'], s['lon'])

        aimed_dep = format_iso_time(s.get('sched_dep'), tz_offset)
        expected_dep = format_iso_time(s.get('est_dep'), tz_offset)
        aimed_arr = format_iso_time(s.get('sched_arr'), tz_offset)
        expected_arr = format_iso_time(s.get('est_arr'), tz_offset)

        # Statut de l'arrêt
        if s.get('is_skipped'):
            call_status = "SKIPPED"
        elif train.get('status') == 'TERMINATED':
            call_status = "PASSED"
        else:
            call_status = "SCHEDULED"

        calls.append({
            "aimedTime": aimed_dep or aimed_arr,
            "expectedTime": expected_dep or expected_arr,
            "aimedArrivalTime": aimed_arr,
            "expectedArrivalTime": expected_arr,
            "stopRef": get_netex_stop_ref(s, is_sleeper),
            "stopName": s.get('name', ''),
            "stopOrder": idx,
            "distanceTraveled": round(cum_distance, 1),
            "latitude": s.get('lat', 0.0),
            "longitude": s.get('lon', 0.0),
            "platformName": s.get('track') or None,
            "callStatus": call_status,
            "flags": ["NO_PICKUP"] if idx == len(stops) - 1 else ([] if idx > 0 else ["NO_DROP_OFF"])
        })

    now_iso = datetime.now(timezone.utc).isoformat()
    shape_id = train.get('shape_id')
    path_ref = f"{'BE:Sleeper' if is_sleeper else 'FR:Eurostar'}:Route:{shape_id}" if shape_id else None

    return {
        "id": journey_netex_id,
        "countryCode": "BE" if is_sleeper else "FR",
        "lineId": line_id,
        "lineRef": line_ref,
        "destination": train.get('destination', ''),
        "calls": calls,
        "position": {
            "latitude": train.get('lat', 0.0),
            "longitude": train.get('lon', 0.0),
            "bearing": float(train.get('bearing', 0.0)),
            "atStop": "quai" in train.get('status_label', '').lower(),
            "type": "COMPUTED",
            "distanceTraveled": round(cum_distance * train.get('progress', 0.0), 1),
            "recordedAt": now_iso
        },
        "pathRef": path_ref,
        "networkId": net_id,
        "networkRef": net_ref,
        "journeyRef": journey_netex_id,
        "vehicle": {
            "number": str(train.get('num', '')),
            "ref": f"{'BE:Sleeper' if is_sleeper else 'FR:Eurostar'}:Vehicle:{train.get('num', '')}"
        },
        "serviceDate": datetime.now(EUROSTAR_TZ).strftime("%Y-%m-%d"),
        "updatedAt": now_iso
    }

def get_journey_path(journey_id: str) -> Optional[Dict[str, Any]]:
    data = get_cached_raw_data()
    raw_id = extract_raw_journey_id(journey_id)
    train = next((t for t in data.get('trains', []) if str(t.get('id')) in (journey_id, raw_id)), None)
    if not train:
        return None

    shape_id = train.get('shape_id')
    raw_coords = []
    if shape_id and shape_id in data.get('shapes_dict', {}):
        raw_coords = data['shapes_dict'][shape_id]
    elif train.get('stops'):
        raw_coords = [[s['lat'], s['lon']] for s in train['stops'] if not s.get('is_skipped')]

    if not raw_coords:
        return {
            "path": {
                "p": [],
                "cancelled": []
            }
        }

    path_3d = []
    cum_dist = 0.0
    for idx, pt in enumerate(raw_coords):
        if idx > 0:
            cum_dist += haversine(raw_coords[idx-1][0], raw_coords[idx-1][1], pt[0], pt[1])
        path_3d.append([round(pt[0], 6), round(pt[1], 6), round(cum_dist, 1)])

    return {
        "path": {
            "p": path_3d,
            "cancelled": []
        }
    }
