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
    assert networks[0]["id"] == 10001
    assert networks[0]["ref"] == "FR:Network:Eurostar"
    assert networks[1]["id"] == 10002
    assert networks[1]["ref"] == "BE:Network:EuropeanSleeper"
    print(f"✅ /api/networks OK: IDs entiers ({networks[0]['id']}, {networks[1]['id']}) et NeTEx refs ({networks[0]['ref']}, {networks[1]['ref']}) validés.")

    print("Testing /api/networks/10001?withDetails=true (BusTrackerClient.php contract)...")
    r_details = client.get("/api/networks/10001?withDetails=true")
    assert r_details.status_code == 200
    net_details = r_details.json()
    assert net_details["id"] == 10001
    assert "lines" in net_details
    assert len(net_details["lines"]) == 1
    assert net_details["lines"][0]["id"] == 1010
    print(f"✅ /api/networks/10001?withDetails=true OK: {len(net_details['lines'])} ligne(s) rattachée(s) (lineId: {net_details['lines'][0]['id']})")

    print("Testing /api/networks/10002?withDetails=true (Sleeper)...")
    r_details_sl = client.get("/api/networks/10002?withDetails=true")
    assert r_details_sl.status_code == 200
    assert r_details_sl.json()["lines"][0]["id"] == 1020
    print(f"✅ /api/networks/10002?withDetails=true OK (lineId: 1020)")

    print("Testing /api/networks/FR:Network:Eurostar?withDetails=true (NeTEx URN)...")
    r_netex_d = client.get("/api/networks/FR:Network:Eurostar?withDetails=true")
    assert r_netex_d.status_code == 200
    assert r_netex_d.json()["id"] == 10001
    assert r_netex_d.json()["lines"][0]["id"] == 1010
    print("✅ /api/networks/FR:Network:Eurostar?withDetails=true OK.")

    print("Testing /api/networks/BE:Network:EuropeanSleeper?withDetails=true (NeTEx URN)...")
    r_sleeper_d = client.get("/api/networks/BE:Network:EuropeanSleeper?withDetails=true")
    assert r_sleeper_d.status_code == 200
    assert r_sleeper_d.json()["id"] == 10002
    assert r_sleeper_d.json()["lines"][0]["id"] == 1020
    print("✅ /api/networks/BE:Network:EuropeanSleeper?withDetails=true OK.")

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
    print(f"✅ /api/vehicle-journeys/markers (BBox) OK: {len(r_bbox.json()['items'])} marqueurs filtrés.")

    # Test détails du trajet
    if len(markers["items"]) > 0:
        first_marker = markers["items"][0]
        first_id = first_marker["id"]
        print(f"Testing /api/vehicle-journeys/{first_id}...")
        assert "::VehicleJourney:" in first_id, f"Invalid Spotted Journey ID: {first_id}"
        
        # Test split("::")[0] comme dans l'app Android SpottedMarkerData.java
        net_ref_extracted = first_id.split("::")[0]
        assert net_ref_extracted in ("FR:Network:Eurostar", "BE:Network:EuropeanSleeper"), f"Unexpected networkRef extracted: {net_ref_extracted}"

        r_journey = client.get(f"/api/vehicle-journeys/{first_id}")
        assert r_journey.status_code == 200
        journey_data = r_journey.json()
        assert journey_data["id"] == first_id
        assert journey_data["networkRef"] == net_ref_extracted
        assert "calls" in journey_data
        assert len(journey_data["calls"]) > 0

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
        raw_id = first_id.split("::VehicleJourney:")[-1]
        r_raw = client.get(f"/api/vehicle-journeys/{raw_id}")
        assert r_raw.status_code == 200
        assert r_raw.json()["id"] == first_id
        print(f"✅ Résolution rétrocompatible via ID brut '{raw_id}' OK.")

    print("\n🎉 TOUS LES ENDPOINTS, IDENTIFIANTS ENTIERS ET FORMATS PATH.PHP SONT VALIDÉS ET CONFORMES !")

if __name__ == "__main__":
    test_api()
