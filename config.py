import os
import sys
from zoneinfo import ZoneInfo

# Sécurisation encodage flux sortie sous Windows (évite UnicodeEncodeError / charmap sur emojis)
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Répertoire racine du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Fuseaux horaires de référence
EUROSTAR_TZ = ZoneInfo("Europe/Paris")
EUROPEAN_SLEEPER_TZ = ZoneInfo("Europe/Brussels")

# URLs et fichiers GTFS Eurostar
EUROSTAR_RT_URL = "https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_rt_v2.bin"
EUROSTAR_STATIC_URL = "https://integration-storage.dm.eurostar.com/gtfs-prod/gtfs_static_commercial_v2.zip"
STATIC_CACHE_FILE = os.path.join(BASE_DIR, "eurostar_gtfs_static.zip")

# URLs et fichiers GTFS European Sleeper
EUROPEAN_SLEEPER_STATIC_URL = "https://raw.githubusercontent.com/deryclem/european-sleeper-gtfs/main/gtfs-european-sleeper.zip"
EUROPEAN_SLEEPER_CACHE_FILE = os.path.join(BASE_DIR, "european_sleeper_gtfs.zip")

# Configuration réseau et serveur HTTP
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Noms normalisés des gares Eurostar
STATION_NAMES = {
    'st_pancras_international': 'Londres St Pancras Int.',
    'paris_nord': 'Paris Gare du Nord',
    'bruxelles_midi': 'Bruxelles-Midi',
    'amsterdam_centraal': 'Amsterdam Centraal',
    'rotterdam_centraal': 'Rotterdam Centraal',
    'antwerpen_centraal': 'Anvers-Central',
    'schiphol_airport': 'Schiphol Airport',
    'lille_europe': 'Lille Europe',
    'koln_hbf': 'Cologne Hbf',
    'dusseldorf_hbf': 'Düsseldorf Hbf',
    'duisburg_hbf': 'Duisburg Hbf',
    'dortmund_hbf': 'Dortmund Hbf',
    'essen_hbf': 'Essen Hbf',
    'aachen_hbf': 'Aix-la-Chapelle Hbf',
    'liege_guillemins': 'Liège-Guillemins',
    'marne_la_vallee_chessy': 'Marne-la-Vallée (Disneyland)',
    'calais_frethun': 'Calais-Fréthun',
    'ebbsfleet_international': 'Ebbsfleet International',
    'ashford_international': 'Ashford International'
}
