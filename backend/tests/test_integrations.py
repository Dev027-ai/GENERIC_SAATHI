from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_integration_status_reports_three_dataset_sources_and_no_live_stock():
    r=client.get("/api/v1/integrations/status")
    assert r.status_code == 200
    body=r.json()
    assert body["branded_price_comparison"]["enabled"] is True
    assert body["branded_price_comparison"]["source_listed_record_count"] > 100_000
    assert body["branded_price_comparison"]["verified_record_count"] == 0
    assert body["kendra_directory"]["coordinate_count"] == 0

def test_kendra_search_does_not_invent_directory():
    r=client.get("/api/v1/kendras/search", params={"q":"Delhi"})
    assert r.status_code in (200,503)
    if r.status_code == 503:
        assert "No Kendra directory" in r.json()["detail"]

def test_ai_review_is_explicitly_unconfigured_without_endpoint(monkeypatch):
    monkeypatch.delenv("GEMMA_API_BASE_URL", raising=False)
    monkeypatch.delenv("GEMMA_MODEL_ID", raising=False)
    r=client.post("/api/v1/ai/prescription-text-review", json={"text":"paracetamol 500 mg"})
    assert r.status_code == 503

def test_price_review_write_is_not_publicly_enabled():
    r=client.post("/api/v1/review/submissions", json={"generic_name":"example"})
    assert r.status_code == 501

def test_up_directory_csv_is_bundled_and_has_all_pdf_records():
    from pathlib import Path
    import csv
    root = Path(__file__).resolve().parents[2]
    directory = root / "data" / "input" / "kendra_directory.csv"
    assert directory.exists()
    with directory.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4484
    assert rows[0]["kendra_code"] == "PMBJK00478"
    assert rows[-1]["kendra_code"] == "PMBJK24675"
    assert all(row["state"] == "Uttar Pradesh" for row in rows)
    assert all(row["district"] and row["pincode"] and row["address"] for row in rows)

def test_kendra_search_finds_district_and_code():
    r = client.get("/api/v1/kendras/search", params={"q": "Varanasi"})
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert r.json()["results"][0]["district"] == "Varanasi"
    r2 = client.get("/api/v1/kendras/search", params={"q": "PMBJK24675"})
    assert r2.status_code == 200
    assert r2.json()["results"][0]["kendra_code"] == "PMBJK24675"

def test_nearby_endpoint_reports_missing_coordinates_honestly():
    r = client.get("/api/v1/kendras/nearby", params={"lat": 26.85, "lon": 80.95})
    assert r.status_code == 200
    body = r.json()
    assert body["directory_total"] == 4484
    assert body["coordinate_coverage"] == 0
    assert body["lookup_error"] is True
    assert "Google Maps" in body["notice"]
    assert body["discovery_source"] == "unavailable"

def test_branded_price_search_always_links_official_nppa_portal():
    r = client.get("/api/v1/prices/branded-search", params={"q": "paracetamol"})
    assert r.status_code == 200
    body = r.json()
    assert "nppaipdms.gov.in/NPPA/PharmaSahiDaam/searchMedicine" in body["official_live_lookup_url"]
    assert body["count"] > 0
    assert all(row["price_status"] == "source_listed_unverified" for row in body["results"])
    assert all(row["verification_status"] == "unverified_source_dataset" for row in body["results"])

def test_compare_does_not_calculate_savings_from_unverified_catalogue_prices():
    r = client.post("/api/v1/medicines/compare", json={"catalogue_id": "1", "branded_name": "Calpol Paediatric Suspension"})
    assert r.status_code == 200
    body = r.json()
    assert body["comparison_allowed"] is False
    assert body["savings_inr"] is None
    assert body["savings_percent"] is None

def test_gemma_gemini_api_search_terms_are_filtered_and_preserve_strength(monkeypatch):
    import httpx
    from app.services.catalogue import _gemma_search_terms

    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"search_terms":["paracetamol 500 mg","paracetamol 650 mg","paracetamol tablets"]}'}]}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, **kwargs):
            assert url.endswith("/models/gemma-4-31b-it:generateContent")
            assert kwargs["headers"]["x-goog-api-key"] == "test-key"
            assert "Query: paracetmol 500 mg" in kwargs["json"]["contents"][0]["parts"][0]["text"]
            return FakeResponse()

    monkeypatch.setenv("GEMMA_PROVIDER", "gemini-api")
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setenv("GEMMA_MODEL_ID", "gemma-4-31b-it")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    terms = _gemma_search_terms("paracetmol 500 mg")
    assert "paracetamol 500 mg" in terms
    assert "paracetamol 650 mg" not in terms


def test_gemma_gemini_api_without_key_falls_back_without_network(monkeypatch):
    from app.services.catalogue import _gemma_search_terms
    monkeypatch.setenv("GEMMA_PROVIDER", "gemini-api")
    monkeypatch.delenv("GEMMA_API_KEY", raising=False)
    monkeypatch.setenv("GEMMA_MODEL_ID", "gemma-4-31b-it")
    assert _gemma_search_terms("paracetmol") == []


def test_compare_never_claims_savings_without_fresh_verified_price_files():
    r = client.post("/api/v1/medicines/compare", json={"catalogue_id": "23", "branded_name": "Dolo 500 Tablet"})
    assert r.status_code == 200
    body = r.json()
    assert body["comparison_allowed"] is False
    assert body["savings_inr"] is None
    assert body["savings_percent"] is None
    assert "no savings are claimed" in body["notice"].lower()


def test_jan_price_evidence_requires_official_source_and_fresh_date():
    from datetime import date, timedelta
    from app.main import _valid_jan_price_record

    base = {
        "generic_name": "Paracetamol Tablets IP 500 mg",
        "strength": "500 mg",
        "pack_size": "10 tablets",
        "mrp_inr": "6.57",
        "source_url": "https://janaushadhi.gov.in/product-portfolio/product-view-list",
        "source_name": "Official PMBI product list",
        "checked_on": date.today().isoformat(),
        "verification_status": "verified",
    }
    assert _valid_jan_price_record(base)
    assert not _valid_jan_price_record({**base, "source_url": "https://example.com/price"})
    assert not _valid_jan_price_record({**base, "verification_status": "unverified"})
    assert not _valid_jan_price_record({**base, "checked_on": (date.today() - timedelta(days=91)).isoformat()})
    assert not _valid_jan_price_record({**base, "mrp_inr": "0"})
