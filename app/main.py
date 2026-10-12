import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.core.config import HOST, PORT
from app.api.router import api_router
from app.services.train_tracker import get_cached_raw_data

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

# Montage des routes de l'API (/api/...)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "Eurostar & European Sleeper Radar API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


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
    print(f"🚄 Trains Eurostar : {len(eurostar_trains)}")
    print(f"🌙 Trains European Sleeper : {len(sleeper_trains)}")
    print(f"⚡ Trains actuellement en circulation : {len(running)}")
    print(f"🟢 Trains à l'heure : {len(ontime)}")
    print(f"🚨 Trains avec retard : {len(delayed)}")
    print(f"📋 Total trajets répertoriés : {len(trains)}")
    print("=" * 75)
    print(f"📖 Documentation Swagger interactive : http://localhost:{PORT}/docs")
    print(f"🚀 Serveur API actif sur : http://{HOST}:{PORT}/api")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
