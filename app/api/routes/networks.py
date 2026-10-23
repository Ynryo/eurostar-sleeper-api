from typing import List
from fastapi import APIRouter, HTTPException

from app.schemas.schemas import NetworkItem, NetworkDetails, NetworkLineItem
from app.services.train_tracker import get_networks_list, get_network_lines

router = APIRouter(prefix="/networks", tags=["Networks"])


@router.get(
    "",
    response_model=List[NetworkItem],
    summary="Liste tous les réseaux de transports disponibles"
)
def get_networks():
    return get_networks_list()


@router.get(
    "/{network_id:path}/lines",
    response_model=List[NetworkLineItem],
    summary="Liste les lignes associées à un réseau (contrat Spotted API)"
)
def get_network_lines_endpoint(network_id: str):
    lines = get_network_lines(network_id)
    if lines is None:
        raise HTTPException(status_code=404, detail="Réseau ou lignes non trouvées")
    return lines


@router.get(
    "/{network_id:path}",
    response_model=NetworkDetails,
    summary="Détails d'un réseau avec ses lignes associées (contrat BusTrackerClient ?withDetails=true)"
)
def get_network_details_endpoint(network_id: str, withDetails: bool = False):
    s_id = str(network_id).strip()
    net = next((
        n for n in get_networks_list()
        if str(n["id"]) == s_id
        or n["ref"] == s_id
        or n.get("networkRef") == s_id
        or s_id.upper() in n["ref"].upper()
        or s_id.upper() in n["name"].upper()
    ), None)
    if not net:
        raise HTTPException(status_code=404, detail="Réseau non trouvé")
    lines = get_network_lines(network_id) or []
    return {**net, "lines": lines, "operators": []}
