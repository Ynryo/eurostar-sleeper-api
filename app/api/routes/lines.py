from typing import List
from fastapi import APIRouter, HTTPException

from app.schemas.schemas import NetworkLineItem
from app.services.train_tracker import get_network_lines, get_line_by_id

router = APIRouter(prefix="/lines", tags=["Lines"])


@router.get(
    "",
    response_model=List[NetworkLineItem],
    summary="Liste toutes les lignes de trains Eurostar et European Sleeper"
)
def get_all_lines():
    euro_lines = get_network_lines(10001) or []
    sleeper_lines = get_network_lines(10002) or []
    return euro_lines + sleeper_lines


@router.get(
    "/{line_id:path}",
    response_model=NetworkLineItem,
    summary="Détails d'une ligne de transport (contrat LineService Spotted API)"
)
def get_line_endpoint(line_id: str):
    line = get_line_by_id(line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Ligne non trouvée")
    return line
