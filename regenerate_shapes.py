#!/usr/bin/env python3
"""
Script de régénération et de maintenance du cache des tracés ferroviaires (BRouter Rail).
Permet de recalculer les tracés GPS précis de manière contrôlée, sans impacter le runtime de l'API.

Usage :
    python regenerate_shapes.py                     # Rafraîchit les tracés avec un délai de courtoisie de 1s
    python regenerate_shapes.py --fallback-only     # Ne recalcule que les segments non résolus (<= 2 points)
    python regenerate_shapes.py --force --delay 1.5 # Force le recalcul de tout le cache avec 1.5s de délai
"""

import os
import sys
import json
import time
import argparse
import urllib.request
from typing import Dict, List, Tuple

# Configuration UTF-8 sur Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from rail_routing_service import CACHE_FILE, rdp_simplify


def parse_key_coordinates(key: str) -> Tuple[float, float, float, float]:
    """Extrait lat1, lon1, lat2, lon2 depuis la clé de segment 'lat1_lon1__lat2_lon2'."""
    parts = key.split('__')
    p1 = [float(x) for x in parts[0].split('_')]
    p2 = [float(x) for x in parts[1].split('_')]
    return p1[0], p1[1], p2[0], p2[1]


def fetch_brouter_segment(lat1: float, lon1: float, lat2: float, lon2: float, timeout: int = 25) -> List[List[float]]:
    """Interroge l'API BRouter rail et retourne la polyline simplifiée."""
    url = f"https://brouter.de/brouter?lonlats={lon1},{lat1}|{lon2},{lat2}&profile=rail&format=geojson"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EurostarRadar-GTFS/1.0 (Maintenance Script)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        features = data.get('features', [])
        if features and 'geometry' in features[0]:
            coords = features[0]['geometry']['coordinates']
            pts = [[round(c[1], 6), round(c[0], 6)] for c in coords]
            return rdp_simplify(pts, epsilon=0.0001)
    raise ValueError("Réponse BRouter invalide ou sans géométrie")


def regenerate_cache(
    cache_path: str = CACHE_FILE,
    delay: float = 1.0,
    force: bool = False,
    fallback_only: bool = False,
    timeout: int = 25
):
    print("=" * 75)
    print("🚆 RÉGÉNÉRATION DU CACHE FERROVIAIRE BROUTER")
    print(f"📁 Fichier cible : {cache_path}")
    print(f"⏱️  Délai entre requêtes : {delay}s | Timeout : {timeout}s")
    print(f"⚙️  Mode : {'Forcer tout' if force else 'Fallback / Lignes droites uniquement' if fallback_only else 'Mise à jour standard'}")
    print("=" * 75)

    if not os.path.exists(cache_path):
        print(f"⚠️ Le fichier de cache {cache_path} n'existe pas. Création d'un nouveau dictionnaire.")
        cache = {}
    else:
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    total_keys = len(cache)
    if total_keys == 0:
        print("ℹ️ Aucun segment à traiter.")
        return

    updated_count = 0
    preserved_count = 0
    skipped_count = 0

    updated_cache = dict(cache)

    for idx, (key, existing_pts) in enumerate(cache.items(), 1):
        is_fallback_segment = len(existing_pts) <= 2

        if fallback_only and not is_fallback_segment:
            skipped_count += 1
            continue

        try:
            lat1, lon1, lat2, lon2 = parse_key_coordinates(key)
        except Exception as e:
            print(f"[{idx}/{total_keys}] ⚠️ Clé invalide {key} ({e}), ignorée.")
            continue

        prefix = f"[{idx}/{total_keys}] {key}"

        try:
            new_pts = fetch_brouter_segment(lat1, lon1, lat2, lon2, timeout=timeout)
            updated_cache[key] = new_pts
            updated_count += 1
            print(f"{prefix} -> ✅ Mis à jour ({len(new_pts)} points)")
        except urllib.error.HTTPError as he:
            preserved_count += 1
            print(f"{prefix} -> ⚠️ Erreur HTTP {he.code} ({he.reason}). Ancien tracé conservé ({len(existing_pts)} pts)")
            if he.code in (403, 429):
                print("   ⏳ Rate-limit BRouter détecté. Pause de sécurité de 5 secondes...")
                time.sleep(5.0)
        except Exception as e:
            preserved_count += 1
            print(f"{prefix} -> ⚠️ Échec ({e}). Ancien tracé conservé ({len(existing_pts)} pts)")

        if delay > 0 and idx < total_keys:
            time.sleep(delay)

    # Sauvegarde atomique du cache mis à jour
    temp_file = f"{cache_path}.tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(updated_cache, f)
    
    if os.path.exists(cache_path):
        os.remove(cache_path)
    os.rename(temp_file, cache_path)

    print("\n" + "=" * 75)
    print("📊 BILAN DE L'OPÉRATION")
    print(f"• Total segments examinés  : {total_keys}")
    print(f"• Segments mis à jour      : {updated_count}")
    print(f"• Segments préservés/échec : {preserved_count}")
    if fallback_only:
        print(f"• Segments ignorés (déjà OK): {skipped_count}")
    print(f"💾 Cache sauvegardé avec succès dans : {cache_path}")
    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(
        description="Outil de régénération des tracés ferroviaires via BRouter OpenStreetMap."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Délai de courtoisie en secondes entre chaque requête BRouter (défaut : 1.0s)."
    )
    parser.add_argument(
        "--fallback-only",
        action="store_true",
        help="Ne tente de recalculer que les segments qui ont un tracé de secours (<= 2 points)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force le recalcul de tous les segments du cache."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=25,
        help="Timeout HTTP par requête en secondes (défaut : 25s)."
    )
    parser.add_argument(
        "--cache-file",
        type=str,
        default=CACHE_FILE,
        help=f"Chemin vers le fichier de cache JSON (défaut : {CACHE_FILE})."
    )

    args = parser.parse_args()
    regenerate_cache(
        cache_path=args.cache_file,
        delay=args.delay,
        force=args.force,
        fallback_only=args.fallback_only,
        timeout=args.timeout
    )


if __name__ == "__main__":
    main()
