from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.schemas.schemas import (
    MarkerCollection,
    JourneyDetails,
    JourneyPath
)
from app.services.train_tracker import (
    get_vehicle_markers,
    get_journey_details,
    get_journey_path
)

router = APIRouter()


@router.get(
    "/vehicle-journeys/markers",
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


@router.get(
    "/vehicle-journeys/{journey_id:path}/paths",
    response_model=JourneyPath,
    tags=["Journeys"],
    summary="Tracé géographique (polyline GPS 3D [lat, lon, distance]) d'un train"
)
def get_journey_path_route(journey_id: str):
    path_data = get_journey_path(journey_id)
    if not path_data:
        raise HTTPException(status_code=404, detail="Tracé non trouvé pour ce trajet")
    return path_data


@router.get(
    "/vehicle-journeys/{journey_id:path}",
    response_model=JourneyDetails,
    tags=["Journeys"],
    summary="Fiche détaillée d'un trajet de train (arrêts avec codes UIC, horaires, retards, quai)"
)
def get_journey(journey_id: str):
    journey = get_journey_details(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Trajet de train non trouvé")
    return journey


@router.get(
    "/paths/{path_id:path}",
    response_model=JourneyPath,
    tags=["Paths"],
    summary="Alias de récupération du tracé GPS d'un trajet"
)
def get_path_alias(path_id: str):
    path_data = get_journey_path(path_id)
    if not path_data:
        raise HTTPException(status_code=404, detail="Tracé non trouvé")
    return path_data
