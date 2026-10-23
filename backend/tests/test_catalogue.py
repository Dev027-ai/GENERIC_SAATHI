from app.services.catalogue import search_medicines, quality_report, load_catalogues, _load_indian_medicine_catalogue


def test_three_approved_catalogues_load():
    _, jan = load_catalogues()
    branded = _load_indian_medicine_catalogue()
    assert len(jan) > 2000
    assert len(branded) > 200_000
    assert {"drug_code", "generic_name", "price_inr", "unit_size_raw"}.issubset(jan.columns)
    assert {"name", "price(₹)", "manufacturer_name", "short_composition1"}.issubset(branded.columns)


def test_jan_aushadhi_price_is_displayable_as_source_listed_value():
    results = search_medicines("paracetamol 650", limit=10)
    exact = [r for r in results if r["generic_name"].casefold() == "paracetamol tablets ip 650 mg".casefold()]
    assert exact
    assert float(exact[0]["jan_price_inr"]) > 0
    assert "unverified" in exact[0]["jan_price_status"].casefold() or "review" in exact[0].get("jan_record_review_status", "").casefold() or "mrp" in exact[0]["jan_price_status"].casefold()
    assert exact[0]["comparison_allowed"] is False
    assert exact[0]["savings_inr"] is None


def test_fuzzy_search_finds_typo_and_returns_results():
    results = search_medicines("paracetmol", limit=10)
    assert results
    assert any("paracetamol" in r["generic_name"].casefold() for r in results)
    assert all(r["match_type"] in {"exact", "close", "fuzzy"} for r in results)


def test_numeric_strength_query_does_not_return_other_strengths_first():
    results = search_medicines("paracetamol 650", limit=10)
    assert results
    assert all("650" in (r["generic_name"] + " " + r["strength"]) for r in results)


def test_records_with_both_price_sources_rank_first():
    results = search_medicines("paracetamol", limit=10)
    assert results
    coverage = [r.get("price_source_count", 0) for r in results]
    assert coverage == sorted(coverage, reverse=True)
    assert any(r.get("price_coverage") == "jan_aushadhi_and_branded" for r in results)


def test_no_local_pharmacy_prices_are_fabricated():
    results = search_medicines("paracetamol", limit=10)
    assert results
    assert all(r["local_pharmacy_price_available"] is False for r in results)
    assert all("No local pharmacy price feed" in r["local_pharmacy_price_note"] for r in results)


def test_quality_report_only_mentions_three_approved_datasets():
    report = quality_report()
    names = set(report["files"])
    assert names == {"jan_aushadhi_extracted(3).csv", "indian_medicine_data.csv", "kendra_directory.csv"}
    assert report["local_pharmacy_prices"]["available"] is False


def test_brand_name_search_returns_source_listed_brand_price_and_generic_link():
    results = search_medicines("Dolo 650", limit=10)
    assert results
    hit = next((r for r in results if r.get("branded_candidate", "").casefold() == "dolo 650 tablet"), None)
    assert hit is not None
    assert float(hit["branded_price_inr"]) > 0
    assert hit["branded_price_status"] == "SOURCE_LISTED_UNVERIFIED"
    assert hit["indian_catalogue_brand_options"]
    assert hit["indian_catalogue_brand_options"][0]["verification_status"] == "unverified_source_dataset"
    assert hit["comparison_allowed"] is False
    assert hit["savings_inr"] is None


def test_typo_in_brand_name_can_find_brand_catalogue_record():
    results = search_medicines("dloo 650", limit=10)
    assert any("dolo 650" in r.get("branded_candidate", "").casefold() for r in results)


def test_brand_query_does_not_claim_savings_for_different_or_unverified_pack():
    results = search_medicines("Dolo 650", limit=10)
    hit = next(r for r in results if r.get("branded_candidate", "").casefold() == "dolo 650 tablet")
    assert hit["comparison_allowed"] is False
    assert hit["savings_inr"] is None
    assert hit["savings_percent"] is None


def test_paracetamol_500_promotes_dolo_500_same_pack_price():
    results = search_medicines("Paracetamol Tablets IP 500 mg", limit=10)
    hit = next(r for r in results if r["generic_name"].casefold() == "paracetamol tablets ip 500 mg")
    assert hit["branded_candidate"] == "Dolo 500 Tablet"
    assert float(hit["branded_price_inr"]) == 10.19
    assert hit["branded_pack_size"] == "strip of 10 tablets"
    assert hit["jan_pack_size"] == "10's"
    assert float(hit["jan_price_inr"]) == 6.57
    assert hit["branded_price_status"] == "SOURCE_LISTED_UNVERIFIED"
    assert any(option["brand_name"] == "Dolo 500 Tablet" and option["pack_comparable"] for option in hit["indian_catalogue_brand_options"])


def test_single_ingredient_brand_options_exclude_combination_products():
    results = search_medicines("Paracetamol Tablets IP 500 mg", limit=10)
    hit = next(r for r in results if r["generic_name"].casefold() == "paracetamol tablets ip 500 mg")
    options = hit["indian_catalogue_brand_options"]
    assert options
    assert all("+" not in option["strength"] for option in options)
    assert all(option["pack_comparable"] for option in options)


def test_autocomplete_skips_broad_brand_enrichment():
    results = search_medicines("Paracetamol Tablets IP 500 mg", limit=6, include_brand_options=False)
    assert results
    assert all(not row.get("indian_catalogue_brand_options") for row in results)
