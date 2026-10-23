from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_web_search_returns_setup_notice_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMMA_API_KEY", raising=False)
    response = client.get("/api/v1/prices/web-search", params={"q": "Dolo 650"})
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert data["results"] == []
    assert "GEMINI_SEARCH_API_KEY" in data["notice"]


def test_web_search_accepts_only_grounded_source_urls_and_never_confirms_stock(monkeypatch):
    import httpx
    from app.services.web_medicine_prices import search_web_medicine_prices

    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": '{"summary":"Found a listing","products":[{"brand_name":"Dolo 650","ingredient":"paracetamol","strength":"650 mg","dosage_form":"tablet","pack_size":"15 tablets","price_inr":32.5,"price_type":"listed selling price","retailer":"Example Pharmacy","source_url":"https://pharmacy.example/dolo","availability_text":""},{"brand_name":"Invented","price_inr":1,"source_url":"https://not-grounded.example/item"}]}'}]},
                    "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://pharmacy.example/dolo", "title": "Example Pharmacy"}}], "webSearchQueries": ["Dolo 650 price India"]}
                }]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, **kwargs):
            assert "google_search" in kwargs["json"]["tools"][0]
            assert kwargs["headers"]["x-goog-api-key"] == "test-key"
            return FakeResponse()

    monkeypatch.setenv("GEMINI_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_SEARCH_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    data = search_web_medicine_prices("Dolo 650")
    assert data["count"] == 1
    item = data["results"][0]
    assert item["brand_name"] == "Dolo 650"
    assert item["price_inr"] == 32.5
    assert item["stock_status"] == "not_confirmed"
    assert item["savings_allowed"] is False
    assert item["price_status"] == "web_listed_unverified"
    assert data["sources"][0]["url"] == "https://pharmacy.example/dolo"
