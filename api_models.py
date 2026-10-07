from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class NetworkItem(BaseModel):
    id: int
    ref: str
    name: str
    authority: Optional[str] = None
    countryCode: str
    timezone: str
    logoHref: Optional[str] = None
    darkModeLogoHref: Optional[str] = None
    color: Optional[str] = None
    textColor: Optional[str] = None
    hasVehiclesFeature: bool = True
    regionId: int = 16
    embedMapCenter: Optional[List[float]] = None

class NetworkLineItem(BaseModel):
    id: int
    references: List[str] = []
    number: str
    girouetteNumber: Optional[str] = None
    cartridgeHref: Optional[str] = None
    color: str
    textColor: str
    sortOrder: Optional[int] = None
    archivedAt: Optional[str] = None
    onlineMarkerCount: int = 0
    onlineVehicleCount: int = 0

class NetworkDetails(NetworkItem):
    operators: List[Dict[str, Any]] = []
    lines: List[NetworkLineItem] = []

class VehicleActivity(BaseModel):
    status: str = "online"
    since: Optional[str] = None
    lineId: Optional[int] = None

class VehicleItem(BaseModel):
    id: int
    networkId: int
    operatorId: Optional[int] = None
    ref: str
    type: str = "TRAIN"
    number: str
    designation: Optional[str] = None
    tcId: Optional[int] = None
    airConditioning: Optional[str] = "PRESENT"
    usbPorts: Optional[bool] = True
    archivedAt: Optional[str] = None
    archivedFor: Optional[str] = None
    activity: VehicleActivity

class MarkerPosition(BaseModel):
    latitude: float
    longitude: float
    bearing: Optional[float] = 0.0
    type: str = "COMPUTED"

class VehicleMarker(BaseModel):
    id: str
    lineNumber: str
    vehicleNumber: Optional[str] = None
    color: str = "#FFFFFF"
    fillColor: str = "#00D2FF"
    position: MarkerPosition

class MarkerCollection(BaseModel):
    items: List[VehicleMarker]
    at: str

class JourneyCall(BaseModel):
    aimedTime: Optional[str] = None
    expectedTime: Optional[str] = None
    aimedArrivalTime: Optional[str] = None
    expectedArrivalTime: Optional[str] = None
    stopRef: str
    stopName: str
    stopOrder: int
    distanceTraveled: float = 0.0
    latitude: float
    longitude: float
    platformName: Optional[str] = None
    callStatus: str = "SCHEDULED"
    flags: List[str] = []

class JourneyPosition(BaseModel):
    latitude: float
    longitude: float
    bearing: float = 0.0
    atStop: bool = False
    type: str = "COMPUTED"
    distanceTraveled: float = 0.0
    recordedAt: Optional[str] = None

class JourneyDetails(BaseModel):
    id: str
    countryCode: str = "FR"
    lineId: int
    direction: str = "OUTBOUND"
    destination: str
    calls: List[JourneyCall]
    position: JourneyPosition
    pathRef: Optional[str] = None
    networkId: int
    journeyRef: str
    vehicle: Dict[str, Any]
    serviceDate: str
    updatedAt: str

class JourneyPath(BaseModel):
    path: List[List[float]]
