import os
import sys
import json
import time
import threading
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from config import HOST, PORT, STATIC_DIR
from gtfs_service import build_network_data

# Configuration UTF-8 sur Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

class LiveMapServer(BaseHTTPRequestHandler):
    network_cache = None
    cache_time = 0

    def do_GET(self):
        # Route API JSON
        if self.path == '/api/data':
            try:
                if not LiveMapServer.network_cache or (time.time() - LiveMapServer.cache_time > 15):
                    LiveMapServer.network_cache = build_network_data()
                    LiveMapServer.cache_time = time.time()
                data_bytes = json.dumps(LiveMapServer.network_cache).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(data_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(data_bytes)
            except Exception as e:
                self.send_error(500, str(e))
            return

        # Fichiers statiques
        clean_path = self.path.split('?')[0].lstrip('/')
        if clean_path in ('', 'index.html', 'map.html'):
            filename = 'index.html'
            content_type = 'text/html; charset=utf-8'
        elif clean_path == 'style.css':
            filename = 'style.css'
            content_type = 'text/css; charset=utf-8'
        elif clean_path == 'app.js':
            filename = 'app.js'
            content_type = 'application/javascript; charset=utf-8'
        else:
            filename = clean_path
            content_type = 'application/octet-stream'

        file_path = os.path.join(STATIC_DIR, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, f"Fichier non trouvé: {filename}")

    def log_message(self, format, *args):
        # Silence les logs HTTP pour garder le terminal propre
        return

def start_server_in_background():
    try:
        server = ThreadingHTTPServer((HOST, PORT), LiveMapServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return True
    except Exception as e:
        print(f"ℹ️ Le port {PORT} est occupé ou indisponible ({e}).")
        return False

def main():
    print("📡 Analyse complète des réseaux Eurostar et European Sleeper...")
    data = build_network_data()

    trains = data['trains']
    eurostar_trains = [t for t in trains if t.get('network') == 'eurostar']
    sleeper_trains = [t for t in trains if t.get('network') == 'european_sleeper']
    running = [t for t in trains if t['status'] == 'RUNNING']
    delayed = [t for t in trains if t['delay_sec'] > 0]
    ontime = [t for t in trains if t['delay_sec'] == 0]

    print("\n" + "=" * 75)
    print(f"        RADAR FERROVIAIRE EUROPÉEN — STATISTIQUES ({data['date']})")
    print("=" * 75)
    print(f"🚆 Trains Eurostar : {len(eurostar_trains)}")
    print(f"🌙 Trains European Sleeper : {len(sleeper_trains)}")
    print(f"⚡ Trains actuellement en circulation : {len(running)}")
    print(f"🟢 Trains à l'heure : {len(ontime)}")
    print(f"🚨 Trains avec retard : {len(delayed)}")
    print(f"📋 Total trajets répertoriés : {len(trains)}")
    print("=" * 75)

    # Lancement du serveur local
    server_ok = start_server_in_background()

    # Ouverture du navigateur uniquement hors Docker
    if not os.environ.get("DOCKER"):
        url_to_open = f"http://localhost:{PORT}/"
        print(f"\n🚀 Ouverture de la carte dans le navigateur : {url_to_open}")
        try:
            webbrowser.open(url_to_open)
        except Exception:
            pass
    else:
        print(f"\n🚀 Serveur actif dans Docker et accessible sur : http://localhost:{PORT}/")

    if server_ok:
        print("💡 Serveur de rafraîchissement temps réel actif (toutes les 30s).")
        print("Appuyez sur Ctrl+C pour quitter le serveur lorsque vous avez terminé.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArrêt du serveur.")

if __name__ == "__main__":
    main()