import os
import json
import math
import time
import urllib.request

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rail_shapes_cache.json")

def perpendicular_dist(p, l1, l2):
    if l1 == l2:
        return math.hypot(p[0] - l1[0], p[1] - l1[1])
    dy = l2[0] - l1[0]
    dx = l2[1] - l1[1]
    return abs(dy * p[1] - dx * p[0] + l2[1] * l1[0] - l2[0] * l1[1]) / math.hypot(dx, dy)

def rdp_simplify(points, epsilon=0.0001):
    """Simplifie la polyline avec l'algorithme Ramer-Douglas-Peucker (précision ~10m)."""
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

class RailRouter:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.cache = {}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            except Exception as e:
                print(f"⚠️ Erreur lors du chargement de {self.cache_file} ({e})")
                self.cache = {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"⚠️ Erreur lors de la sauvegarde de {self.cache_file} ({e})")

    def make_key(self, lat1, lon1, lat2, lon2):
        return f"{round(lat1, 4)}_{round(lon1, 4)}__{round(lat2, 4)}_{round(lon2, 4)}"

    def get_rail_segment(self, lat1, lon1, lat2, lon2):
        """Récupère le tracé ferroviaire réel via cache ou BRouter rail."""
        key = self.make_key(lat1, lon1, lat2, lon2)
        rev_key = self.make_key(lat2, lon2, lat1, lon1)

        if key in self.cache:
            return self.cache[key]
        if rev_key in self.cache:
            return list(reversed(self.cache[rev_key]))

        # Interrogation de l'API BRouter avec profil 'rail'
        url = f"https://brouter.de/brouter?lonlats={lon1},{lat1}|{lon2},{lat2}&profile=rail&format=geojson"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EurostarRadar-GTFS/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                features = data.get('features', [])
                if features and 'geometry' in features[0]:
                    coords = features[0]['geometry']['coordinates']
                    pts = [[round(c[1], 6), round(c[0], 6)] for c in coords]
                    simplified = rdp_simplify(pts, epsilon=0.0001)
                    self.cache[key] = simplified
                    self.save_cache()
                    return simplified
        except Exception as e:
            print(f"⚠️ BRouter rail indisponible pour {key} ({e})")

        # Repli gracieux : segment direct
        fallback = [[round(lat1, 6), round(lon1, 6)], [round(lat2, 6), round(lon2, 6)]]
        self.cache[key] = fallback
        return fallback

    def get_full_route(self, stops_coords):
        """Assemble les segments ferroviaires successifs pour une liste d'arrêts [ [lat, lon], ... ]."""
        if not stops_coords or len(stops_coords) < 2:
            return stops_coords or []

        full_pts = []
        for i in range(len(stops_coords) - 1):
            s1 = stops_coords[i]
            s2 = stops_coords[i + 1]
            seg = self.get_rail_segment(s1[0], s1[1], s2[0], s2[1])
            if not full_pts:
                full_pts.extend(seg)
            else:
                # Évite de dupliquer le point de jonction
                if full_pts[-1] == seg[0]:
                    full_pts.extend(seg[1:])
                else:
                    full_pts.extend(seg)
        return full_pts

rail_router = RailRouter()
