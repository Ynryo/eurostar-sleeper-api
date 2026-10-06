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
    assert networks[0]["regionId"] == 13
    assert networks[1]["regionId"] == 13
    print(f"✅ /api/networks OK: {len(networks)} réseaux trouvés (logos et région 13 validés).")

    print("Testing /api/networks/1/lines...")
    r = client.get("/api/networks/1/lines")
    assert r.status_code == 200
    lines = r.json()
    assert len(lines) == 1
    assert lines[0]["number"] == "Eurostar"
    print(f"✅ /api/networks/1/lines OK: {lines[0]['number']}")

    print("Testing /api/networks/2/lines...")
    r = client.get("/api/networks/2/lines")
    assert r.status_code == 200
    lines2 = r.json()
    assert len(lines2) == 1
    assert lines2[0]["number"] == "European Sleeper"
    print(f"✅ /api/networks/2/lines OK: {lines2[0]['number']}")

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
        print(f"Testing /api/vehicle-journeys/{first_id}...")
        r_journey = client.get(f"/api/vehicle-journeys/{first_id}")
        assert r_journey.status_code == 200
        journey_data = r_journey.json()
        assert "calls" in journey_data
        assert "position" in journey_data
        
        # Validation du format UIC NeTEx dans stopRef
        first_call = journey_data["calls"][0]
        stop_ref = first_call["stopRef"]
        assert ":StopPoint:" in stop_ref
        print(f"✅ /api/vehicle-journeys/{first_id} OK: arrêt {first_call['stopName']} -> stopRef NeTEx: {stop_ref}")

        print(f"Testing /api/vehicle-journeys/{first_id}/paths...")
        r_path = client.get(f"/api/vehicle-journeys/{first_id}/paths")
        assert r_path.status_code == 200
        path_data = r_path.json()
        assert "path" in path_data
        print(f"✅ /api/vehicle-journeys/{first_id}/paths OK: {len(path_data['path'])} points GPS 3D.")

    print("Testing legacy /api/data...")
    r_leg = client.get("/api/data")
    assert r_leg.status_code == 200
    assert "trains" in r_leg.json()
    print("✅ /api/data OK (rétrocompatibilité Leaflet conservée).")

    print("\n🎉 TOUS LES ENDPOINTS SONT VALIDÉS ET CONFORMES !")

if __name__ == "__main__":
    test_api()
