"""Google Search-grounded medicine listings. Results are leads, not verified pharmacy quotes."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx


def _safe_http_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _json_from_text(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I)
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except ValueError:
            return {}
    return data if isinstance(data, dict) else {}


def search_web_medicine_prices(query: str, timeout_seconds: float = 25.0) -> dict:
    """Search the public web using Gemini Google Search grounding and preserve citations.

    This intentionally does not claim stock or verify a price against the retailer checkout.
    """
    api_key = (os.getenv("GEMINI_SEARCH_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GEMMA_API_KEY") or "").strip()
    model = (os.getenv("GEMINI_SEARCH_MODEL") or "gemini-2.5-flash").strip()
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    if not api_key:
        return {
            "query": query, "configured": False, "count": 0, "results": [], "sources": [],
            "checked_at": checked_at, "search_provider": "Google Search grounding via Gemini API",
            "notice": "Web price search is not configured. Set GEMINI_SEARCH_API_KEY (or GEMINI_API_KEY) on the backend. Catalogue search remains available."
        }

    prompt = f"""Search the web for Indian pharmacy listings for the exact medicine query: {query[:120]!r}.
Prioritize recognized Indian online pharmacies and official medicine/brand pages. Extract only product listings actually supported by the search results. Return a JSON object only with keys: summary (string), products (array). Each product must have brand_name, ingredient, strength, dosage_form, pack_size, price_inr (number or null), price_type (MRP, listed selling price, or unknown), retailer, source_url (exact URL from the grounded web sources), availability_text (short quote/description only if explicitly supported, otherwise empty). Include at most 8 products. Do not infer or invent a price, ingredient, strength, pack, retailer, URL or stock. If a value is absent, use an empty string or null. Do not recommend substitutions or provide medical advice. Keep different strengths and pack sizes separate. Query: {query[:120]}"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        # Avoid returning provider response bodies, which may contain sensitive details.
        if status in (401, 403):
            message = "Gemini rejected the API key or this API is not enabled. Check the key and Google AI Studio project."
        elif status == 429:
            message = "Gemini API quota/rate limit reached. Try later or check billing and quota."
        else:
            message = f"Gemini web search failed (HTTP {status})."
        return {"query": query, "configured": True, "count": 0, "results": [], "sources": [], "checked_at": checked_at, "search_provider": "Google Search grounding via Gemini API", "error": message, "notice": "No live price results were returned; use catalogue data as a separate, unverified source."}
    except Exception:
        return {"query": query, "configured": True, "count": 0, "results": [], "sources": [], "checked_at": checked_at, "search_provider": "Google Search grounding via Gemini API", "error": "Gemini web search could not be reached. Check backend internet access and model availability.", "notice": "No live price results were returned; use catalogue data as a separate, unverified source."}

    text_parts = []
    candidates = body.get("candidates") or []
    for part in ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text_parts.append(part["text"])
    parsed = _json_from_text("\n".join(text_parts))

    metadata = (candidates[0].get("groundingMetadata") or {}) if candidates else {}
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for chunk in metadata.get("groundingChunks") or []:
        web = chunk.get("web") or {}
        source_url = _safe_http_url(web.get("uri"))
        if source_url and source_url not in seen_urls:
            seen_urls.add(source_url)
            sources.append({"title": str(web.get("title") or urlparse(source_url).netloc)[:200], "url": source_url})
    # A product URL must be present in the API's grounding sources; otherwise reject it.
    rows = []
    for item in parsed.get("products", []) if isinstance(parsed.get("products"), list) else []:
        if not isinstance(item, dict):
            continue
        source_url = _safe_http_url(item.get("source_url"))
        if not source_url or source_url not in seen_urls:
            continue
        price = item.get("price_inr")
        try:
            price = float(str(price).replace(",", "")) if price not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        if price is not None and (price <= 0 or price > 10_000_000):
            price = None
        rows.append({
            "brand_name": str(item.get("brand_name") or "").strip()[:160],
            "ingredient": str(item.get("ingredient") or "").strip()[:200],
            "strength": str(item.get("strength") or "").strip()[:80],
            "dosage_form": str(item.get("dosage_form") or "").strip()[:80],
            "pack_size": str(item.get("pack_size") or "").strip()[:100],
            "price_inr": round(price, 2) if price is not None else None,
            "price_type": str(item.get("price_type") or "unknown").strip()[:60],
            "retailer": str(item.get("retailer") or "").strip()[:120],
            "source_url": source_url,
            "source_title": next((s["title"] for s in sources if s["url"] == source_url), urlparse(source_url).netloc),
            "availability_text": str(item.get("availability_text") or "").strip()[:180],
            "stock_status": "not_confirmed",
            "price_status": "web_listed_unverified" if price is not None else "price_not_found",
            "checked_at": checked_at,
            "savings_allowed": False,
        })
        if len(rows) >= 8:
            break
    return {
        "query": query, "configured": True, "count": len(rows), "results": rows, "sources": sources,
        "search_queries": [str(q)[:200] for q in metadata.get("webSearchQueries", []) if str(q).strip()][:10],
        "checked_at": checked_at, "search_provider": "Google Search grounding via Gemini API",
        "summary": str(parsed.get("summary") or "")[:500],
        "notice": "Web-search results are leads, not a verified pharmacy quote. Prices may be stale or location-specific. Stock is not confirmed unless the retailer confirms it directly. Savings are disabled until exact ingredient, strength, dosage form, pack quantity and current prices are independently verified."
    }
