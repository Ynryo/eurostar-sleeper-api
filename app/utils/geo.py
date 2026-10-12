import math
from typing import List, Tuple, Optional


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance géodésique en mètres entre deux coordonnées (lat, lon)."""
    R = 6371000.0  # Rayon terrestre moyen en mètres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Distance géodésique entre deux points (lat, lon)."""
    return haversine(p1[0], p1[1], p2[0], p2[1])


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule l'azimut (bearing en degrés 0..360) entre deux coordonnées."""
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def interpolate_along_track(pts: List[List[float]], ratio: float) -> Tuple[List[float], float]:
    """Calcule la position [lat, lon] et le bearing exact le long d'une polyline ferroviaire selon un ratio [0..1]."""
    if not pts:
        return [0.0, 0.0], 0.0
    if len(pts) == 1:
        return pts[0], 0.0

    ratio = min(1.0, max(0.0, ratio))
    dists = [haversine_dist(pts[i], pts[i+1]) for i in range(len(pts)-1)]
    total_dist = sum(dists)
    if total_dist == 0:
        return pts[0], 0.0

    target = ratio * total_dist
    accum = 0.0
    for i, d in enumerate(dists):
        if accum + d >= target:
            seg_r = (target - accum) / d if d > 0 else 0
            lat = pts[i][0] + (pts[i+1][0] - pts[i][0]) * seg_r
            lon = pts[i][1] + (pts[i+1][1] - pts[i][1]) * seg_r
            b = calculate_bearing(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            return [round(lat, 6), round(lon, 6)], round(b, 1)
        accum += d

    p_last = pts[-1]
    p_prev = pts[-2]
    return p_last, round(calculate_bearing(p_prev[0], p_prev[1], p_last[0], p_last[1]), 1)


def extract_sub_shape(
    full_shape: Optional[List[List[float]]],
    cur_lat: float,
    cur_lon: float,
    nxt_lat: float,
    nxt_lon: float
) -> Optional[List[List[float]]]:
    """Extrait le tronçon ferroviaire entre deux gares consécutives le long de la shape complète."""
    if not full_shape or len(full_shape) < 2:
        return None
    i_start = min(range(len(full_shape)), key=lambda i: haversine_dist(full_shape[i], (cur_lat, cur_lon)))
    i_end = min(range(len(full_shape)), key=lambda i: haversine_dist(full_shape[i], (nxt_lat, nxt_lon)))
    if i_start == i_end:
        return None
    if i_start < i_end:
        return full_shape[i_start : i_end + 1]
    else:
        return list(reversed(full_shape[i_end : i_start + 1]))


def perpendicular_dist(p: List[float], l1: List[float], l2: List[float]) -> float:
    """Distance perpendiculaire d'un point à un segment linéaire."""
    if l1 == l2:
        return math.hypot(p[0] - l1[0], p[1] - l1[1])
    dy = l2[0] - l1[0]
    dx = l2[1] - l1[1]
    return abs(dy * p[1] - dx * p[0] + l2[1] * l1[0] - l2[0] * l1[1]) / math.hypot(dx, dy)


def rdp_simplify(points: List[List[float]], epsilon: float = 0.0001) -> List[List[float]]:
    """Simplifie une polyline avec l'algorithme Ramer-Douglas-Peucker (tolérance epsilon ~10m)."""
    if len(points) < 3:
        return points
    dmax = 0.0
    index = 0
    for i in range(1, len(points) - 1):
        d = perpendicular_dist(points[i], points[0], points[-1])
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        left = rdp_simplify(points[:index + 1], epsilon)
        right = rdp_simplify(points[index:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]
