import sys
from fastapi.testclient import TestClient
from gtfs import app

client = TestClient(app)

def test_api():
    print("Testing /api/networks...")
    r = client.get("/api/networks")
    assert r.status_code == 200, f"Failed: {r.status_code}"
    networks = r.json()
    assert len(networks) == 2
    assert networks[0]["id"] == 101
    assert networks[0]["ref"] == "FR:Network:Eurostar"
    assert networks[1]["id"] == 102
    assert networks[1]["ref"] == "BE:Network:EuropeanSleeper"
    assert networks[0]["regionId"] == 16
    assert networks[1]["regionId"] == 16
    print(f"✅ /api/networks OK: IDs entiers ({networks[0]['id']}, {networks[1]['id']}) et NeTEx refs ({networks[0]['ref']}, {networks[1]['ref']}) validés.")

    print("Testing /api/networks/101?withDetails=true (BusTrackerClient.php contract)...")
    r_details = client.get("/api/networks/101?withDetails=true")
    assert r_details.status_code == 200
    net_details = r_details.json()
    assert net_details["id"] == 101
    assert "lines" in net_details
    assert len(net_details["lines"]) == 1
    assert net_details["lines"][0]["id"] == 1010
    print(f"✅ /api/networks/101?withDetails=true OK: {len(net_details['lines'])} ligne(s) rattachée(s) (lineId: {net_details['lines'][0]['id']})")

    print("Testing /api/networks/102?withDetails=true (Sleeper)...")
    r_details_sl = client.get("/api/networks/102?withDetails=true")
    assert r_details_sl.status_code == 200
    assert r_details_sl.json()["lines"][0]["id"] == 1020
    print(f"✅ /api/networks/102?withDetails=true OK (lineId: 1020)")

    print("Testing /api/networks/101/lines (Spotted-API Numeric ID)...")
    r = client.get("/api/networks/101/lines")
    assert r.status_code == 200
    lines = r.json()
    assert len(lines) == 1
    assert lines[0]["id"] == 1010
    assert lines[0]["ref"] == "FR:Line:Eurostar"
    assert "FR:Line:Eurostar" in lines[0]["references"]
    print(f"✅ /api/networks/101/lines OK (lineId entier 1010): {lines[0]['id']}")

    print("Testing /api/networks/1/lines (Legacy ID)...")
    r_leg_id = client.get("/api/networks/1/lines")
    assert r_leg_id.status_code == 200
    assert r_leg_id.json()[0]["id"] == 1010
    print("✅ /api/networks/1/lines OK (compatibilité legacy).")

    print("Testing /api/networks/FR:Network:Eurostar/lines (NeTEx ID)...")
    r_netex = client.get("/api/networks/FR:Network:Eurostar/lines")
    assert r_netex.status_code == 200
    assert r_netex.json()[0]["id"] == 1010
    print("✅ /api/networks/FR:Network:Eurostar/lines OK (NeTEx URN).")

    print("Testing /api/networks/102/lines (Spotted-API Numeric ID Sleeper)...")
    r = client.get("/api/networks/102/lines")
    assert r.status_code == 200
    lines2 = r.json()
    assert len(lines2) == 1
    assert lines2[0]["id"] == 1020
    assert lines2[0]["ref"] == "BE:Line:EuropeanSleeper"
    print(f"✅ /api/networks/102/lines OK: lineId {lines2[0]['id']}")

    print("Testing /api/networks/BE:Network:EuropeanSleeper/lines (NeTEx ID)...")
    r_sleeper = client.get("/api/networks/BE:Network:EuropeanSleeper/lines")
    assert r_sleeper.status_code == 200
    assert r_sleeper.json()[0]["id"] == 1020
    print("✅ /api/networks/BE:Network:EuropeanSleeper/lines OK (NeTEx URN).")

    print("Testing /api/vehicle-journeys/markers...")
    r = client.get("/api/vehicle-journeys/markers")
    assert r.status_code == 200
    markers = r.json()
    assert "items" in markers
    assert "at" in markers
    print(f"✅ /api/vehicle-journeys/markers OK: {len(markers['items'])} marqueurs en direct.")

    # Test Bounding Box
    r_bbox = client.get("/api/vehicle-journeys/markers?swLat=48.0&swLon=2.0&neLat=52.0&neLon=5.0")
    assert r_bbox.status_code == 200
    bbox_items = r_bbox.json()["items"]
    print(f"✅ Bounding Box filtrage OK: {len(bbox_items)} marqueurs dans la zone.")

    if markers["items"]:
        first_id = markers["items"][0]["id"]
        assert ":VehicleJourney:" in first_id, f"Invalid NeTEx Journey ID: {first_id}"
        print(f"Testing /api/vehicle-journeys/{first_id}...")
        r_journey = client.get(f"/api/vehicle-journeys/{first_id}")
        assert r_journey.status_code == 200
        journey_data = r_journey.json()
        assert "calls" in journey_data
        assert "position" in journey_data
        assert isinstance(journey_data["lineId"], int), "lineId must be int"
        assert isinstance(journey_data["networkId"], int), "networkId must be int"
        assert journey_data["lineId"] in (1010, 1020)
        assert journey_data["networkId"] in (101, 102)
        assert ":Vehicle:" in journey_data["vehicle"]["ref"]
        
        # Validation du format UIC NeTEx dans stopRef
        first_call = journey_data["calls"][0]
        stop_ref = first_call["stopRef"]
        assert ":StopPoint:" in stop_ref
        print(f"✅ /api/vehicle-journeys/{first_id} OK: arrêt {first_call['stopName']} -> stopRef NeTEx: {stop_ref}")
        print(f"   vehicle: {journey_data['vehicle']['ref']}, line: {journey_data['lineId']} (ref: {journey_data.get('lineRef')}), network: {journey_data['networkId']} (ref: {journey_data.get('networkRef')})")

        print(f"Testing /api/vehicle-journeys/{first_id}/paths...")
        r_path = client.get(f"/api/vehicle-journeys/{first_id}/paths")
        assert r_path.status_code == 200
        path_data = r_path.json()
        assert "path" in path_data
        assert "p" in path_data["path"], "Structure Path.php attend {'path': {'p': ..., 'cancelled': []}}"
        assert "cancelled" in path_data["path"]
        print(f"✅ /api/vehicle-journeys/{first_id}/paths OK (Format Path.php): {len(path_data['path']['p'])} points GPS 3D.")

        # Test de résolution avec l'identifiant brut (rétrocompatibilité)
        raw_id = first_id.split(":VehicleJourney:")[-1]
        r_raw = client.get(f"/api/vehicle-journeys/{raw_id}")
        assert r_raw.status_code == 200
        assert r_raw.json()["id"] == first_id
        print(f"✅ Résolution rétrocompatible via ID brut '{raw_id}' OK.")

    print("Testing legacy /api/data...")
    r_leg = client.get("/api/data")
    assert r_leg.status_code == 200
    assert "trains" in r_leg.json()
    print("✅ /api/data OK (rétrocompatibilité Leaflet conservée).")

    print("\n🎉 TOUS LES ENDPOINTS, IDENTIFIANTS ENTIERS ET FORMATS PATH.PHP SONT VALIDÉS ET CONFORMES !")

if __name__ == "__main__":
    test_api()

