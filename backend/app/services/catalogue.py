from pathlib import Path
from difflib import SequenceMatcher, get_close_matches
from functools import lru_cache
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "input"
COMMON_FILE = DATA_DIR / "generic_saathi_common_medicines_130(1).csv"
JAN_FILE = DATA_DIR / "jan_aushadhi_extracted(3).csv"


INDIAN_MEDICINE_FILE = DATA_DIR / "indian_medicine_data.csv"

@lru_cache(maxsize=1)
def _load_indian_medicine_catalogue():
    """Load the broad brand catalogue once; source prices are not assumed current."""
    if not INDIAN_MEDICINE_FILE.exists():
        return pd.DataFrame()
    usecols = ["id", "name", "price(₹)", "Is_discontinued", "manufacturer_name",
               "type", "pack_size_label", "short_composition1", "short_composition2"]
    try:
        frame = pd.read_csv(INDIAN_MEDICINE_FILE, usecols=usecols).fillna("")
        frame["price(₹)"] = pd.to_numeric(frame["price(₹)"], errors="coerce")
        frame["_composition_norm"] = (
            frame["short_composition1"].astype(str) + " " +
            frame["short_composition2"].astype(str)
        ).map(_normalize)
        frame["_name_norm"] = frame["name"].astype(str).map(_normalize)
        frame["_discontinued_bool"] = frame["Is_discontinued"].astype(str).str.casefold().isin(["true", "1", "yes"])
        return frame
    except (OSError, ValueError, pd.errors.ParserError):
        return pd.DataFrame()


def _ingredient_strength_matches(source_composition, generic_name, strength):
    """Conservative active-ingredient and strength match against raw composition text."""
    raw = as_text(source_composition).casefold()
    comp = _normalize(raw)
    generic = _normalize(generic_name)
    requested = _normalize(strength)
    if not comp or not generic or not requested:
        return False
    # Require requested ingredient words in composition, not just a similar brand name.
    ignored = {"tablet", "tablets", "tab", "tabs", "capsule", "capsules", "syrup", "suspension", "injection", "infusion", "drops", "oral", "paediatric", "pediatric", "ip", "usp", "bp", "and", "per", "of", "for"}
    generic_tokens = [t for t in generic.split() if len(t) > 2 and t not in ignored and not re.fullmatch(r"\d+(?:\.\d+)?", t)]
    if not generic_tokens or not all(token in comp.split() for token in generic_tokens):
        return False
    # Preserve source punctuation for strength extraction; normalization removes parentheses.
    requested_numbers = re.findall(r"\d+(?:\.\d+)?", requested)
    comp_numbers = re.findall(r"(\d+(?:\.\d+)?)\s*(?:mg|mcg|µg|g|ml|iu)\b", raw)
    if not requested_numbers:
        return False
    return requested_numbers[0] in comp_numbers


@lru_cache(maxsize=256)
def _indian_catalogue_brand_options(generic_name, strength, dosage_form_and_pack, is_combination=False, limit=5):
    """Return composition/strength/form-matched source-listed brand options.

    Combination products are excluded for a single-ingredient search. Prices here
    are source-listed, not guaranteed current retail prices. Same-count packs are
    surfaced first so the UI can make a fair pack comparison.
    """
    if is_combination:
        return []
    frame = _load_indian_medicine_catalogue()
    if frame.empty:
        return []
    generic = _normalize(generic_name)
    if not generic or not strength:
        return []
    first_tokens = [t for t in generic.split() if len(t) > 2 and t not in {"tablets", "tablet", "capsules", "capsule", "syrup", "suspension", "injection", "oral", "ip", "usp", "bp"} and not t.isdigit()]
    if not first_tokens:
        return []
    mask = frame["_composition_norm"].str.contains(re.escape(first_tokens[0]), regex=True, na=False)
    candidates = frame[mask].copy()
    if candidates.empty:
        return []

    def composition_matches(row):
        c1 = as_text(row.get("short_composition1", ""))
        c2 = as_text(row.get("short_composition2", ""))
        # A one-ingredient query must not select a combination that merely includes
        # the requested salt. The supplied data stores the second active ingredient
        # separately in short_composition2 for the common combination rows.
        if c1 and c2:
            return False
        composition = c1 or c2
        if not _ingredient_strength_matches(composition, generic, strength):
            return False
        requested_numbers = re.findall(r"\d+(?:\.\d+)?", _normalize(strength))
        composition_numbers = re.findall(r"(\d+(?:\.\d+)?)\s*(?:mg|mcg|µg|g|ml|iu)\b", composition.casefold())
        # Guard against multi-strength combinations encoded inside a single field.
        return bool(requested_numbers) and len(composition_numbers) == len(requested_numbers) and composition_numbers == requested_numbers

    candidates = candidates[candidates.apply(composition_matches, axis=1)].copy()
    if candidates.empty:
        return []
    candidates = candidates[(~candidates["_discontinued_bool"]) & (candidates["price(₹)"] > 0)]
    if candidates.empty:
        return []

    form = _normalize(dosage_form_and_pack)
    if "tablet" in form or re.search(r"\btab\b", form):
        candidates = candidates[candidates["pack_size_label"].astype(str).str.contains(r"tablet|tab", case=False, regex=True)]
    elif "capsule" in form or re.search(r"\bcap\b", form):
        candidates = candidates[candidates["pack_size_label"].astype(str).str.contains("capsule", case=False, regex=False)]
    elif "syrup" in form or "suspension" in form:
        candidates = candidates[candidates["pack_size_label"].astype(str).str.contains(r"syrup|suspension|ml", case=False, regex=True)]
    elif "injection" in form or "infusion" in form:
        candidates = candidates[candidates["pack_size_label"].astype(str).str.contains(r"injection|infusion|ampoule|vial|ml", case=False, regex=True)]
    if candidates.empty:
        return []

    jan_pack = _pack_unit_count(dosage_form_and_pack)
    candidates["_pack_count"] = candidates["pack_size_label"].map(_pack_unit_count)
    candidates["_same_pack_count"] = candidates["_pack_count"].map(lambda count: bool(jan_pack and count == jan_pack))
    candidates["_preferred_dolo"] = candidates.apply(
        lambda row: bool("paracetamol" in generic.split() and _normalize(row.get("name", "")).startswith("dolo ")),
        axis=1,
    )
    # The user specifically needs Dolo surfaced for a plain paracetamol query when
    # the catalogue actually contains a matching Dolo pack. It is only promoted
    # after composition, strength, form, active status and pack-count filtering.
    candidates = candidates.sort_values(
        ["_same_pack_count", "_preferred_dolo", "price(₹)", "name"],
        ascending=[False, False, True, True],
    ).drop_duplicates(subset=["name", "pack_size_label"])
    output = []
    for _, r in candidates.head(limit).iterrows():
        pack_size = str(r["pack_size_label"])
        output.append({
            "brand_name": str(r["name"]),
            "price_inr": round(float(r["price(₹)"]), 2),
            "manufacturer": str(r["manufacturer_name"]),
            "pack_size": pack_size,
            "strength": str(r["short_composition1"] or r["short_composition2"]),
            "dosage_form": str(r["type"]),
            "source_name": "Indian medicine dataset supplied by user",
            "source_url": "",
            "checked_on": "",
            "price_type": "source-listed price; date/current retail validity unverified",
            "verification_status": "unverified_source_dataset",
            "pack_comparable": bool(jan_pack and _pack_unit_count(pack_size) == jan_pack),
            "comparison_note": "Matched by active ingredient, strength and dosage form. Verify the source-listed price and pack with a pharmacist; current retail validity is not confirmed.",
        })
    return output


@lru_cache(maxsize=1)
def load_catalogues():
    if not JAN_FILE.exists():
        raise FileNotFoundError("The Jan Aushadhi CSV must be present in data/input.")
    # The older 130-row hand-curated seed catalogue is retired in favour of the
    # supplied 253k-row Indian medicine dataset and the full Jan Aushadhi catalogue.
    common = pd.read_csv(COMMON_FILE).fillna("") if COMMON_FILE.exists() else pd.DataFrame()
    jan = pd.read_csv(JAN_FILE).fillna("")
    return common, jan


def as_text(value):
    return "" if pd.isna(value) else str(value).strip()


def _normalize(value):
    """Normalize medicine text without changing source data."""
    text = as_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _pack_unit_count(value):
    """Extract a pack count from strings such as 10's or strip of 10 tablets."""
    text = as_text(value).casefold().replace("’", "'")
    patterns = (
        r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:[' ]s|tablets?|tabs?|capsules?|caps?|softgel capsules?|sachets?|ampoules?|vials?|bottles?|ml|m[lL]|units?)\b",
        r"\b(?:strip|pack|box|bottle|packet|of)\s+(\d+(?:\.\d+)?)\b",
        r"(?<!\d)(\d+)['’]s\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                number = float(match.group(1))
                return int(number) if number.is_integer() else number
            except ValueError:
                pass
    return None


def _match_score(query, fields):
    """Rank exact phrases and name prefixes first, then multi-token/fuzzy matches.

    Fuzzy matching is for discovery only: it never establishes clinical equivalence.
    """
    q = _normalize(query)
    if not q:
        return 0
    q_tokens = q.split()
    best = 0.0
    for index, raw in enumerate(fields):
        field = _normalize(raw)
        if not field:
            continue
        tokens = field.split()
        if field == q:
            score = 100.0
        elif field.startswith(q + " "):
            # Full multi-word query at the beginning of a medicine name.
            score = 98.0
        elif q in field:
            score = 95.0 if field.startswith(q) else 86.0
        elif all(token in tokens for token in q_tokens):
            # All query words occur in the field, even if strength/form order differs.
            positions = [tokens.index(token) for token in q_tokens]
            ordered = positions == sorted(positions)
            contiguous = ordered and positions == list(range(positions[0], positions[0] + len(positions)))
            score = 94.0 if contiguous and positions[0] == 0 else (91.0 if contiguous else 87.0)
        else:
            # Fuzzy token matching handles misspellings and partial multi-word queries.
            token_scores = []
            for qt in q_tokens:
                if len(qt) <= 2:
                    token_scores.append(1.0 if qt in tokens else 0.0)
                else:
                    token_scores.append(max(
                        SequenceMatcher(None, qt, ft).ratio()
                        for ft in tokens
                    ))
            token_coverage = sum(1 for value in token_scores if value >= 0.72) / len(q_tokens)
            mean_similarity = sum(token_scores) / len(token_scores)
            whole_similarity = SequenceMatcher(None, q, field).ratio()
            score = max(token_coverage * 82 + mean_similarity * 8, mean_similarity * 88, whole_similarity * 72)
            # Prefixes should win for the first word even if later words contain typos.
            first_word_match = max(SequenceMatcher(None, q_tokens[0], ft).ratio() for ft in tokens)
            if first_word_match >= 0.8 and token_coverage >= 0.5:
                score += 4
        # Earlier fields are the medicine's canonical generic name; prefer it over metadata.
        score += max(0, 3 - index) * 1.25
        best = max(best, min(score, 100.0))
    return round(best, 1)


def _is_combination(name, strength="", ingredient_text=""):
    """Conservatively flag likely multi-ingredient records from catalogue text."""
    combined = " ".join(as_text(v) for v in (name, strength, ingredient_text)).casefold()
    if re.search(r"\b(and|plus)\b|\+", combined):
        return True
    # Catalogue names often separate actives with commas; avoid treating a comma in
    # dosage instructions as proof by requiring a comma before a drug-like phrase.
    if re.search(r",\s*[a-z][a-z-]+(?:\s+[a-z][a-z-]+)?\s+\d", as_text(name).casefold()):
        return True
    return False


def _strength_key(value):
    """Normalize common strength spellings while preserving numerator/denominator."""
    text = _normalize(value)
    text = re.sub(r"\bper\b", "/", text)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+", "", text)
    return text


def _pack_key(value, form=""):
    text = _normalize(value)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ml|millilitre|milliliter|tablets?|tabs?|capsules?|caps?|g|grams?)\b", text)
    if m:
        unit = m.group(2)
        if unit.startswith("millil"): unit = "ml"
        elif unit.startswith("tablet") or unit.startswith("tab"): unit = "tablets"
        elif unit.startswith("caps"): unit = "capsules"
        elif unit.startswith("gram"): unit = "g"
        return f"{m.group(1)} {unit}"
    # Only interpret the ambiguous 10's convention as tablets when form explicitly says tablet.
    m = re.search(r"\b(\d+)\s*(?:'s|’s)\b", as_text(value).casefold())
    if m and "tablet" in _normalize(form):
        return f"{m.group(1)} tablets"
    return text


def _form_matches(brand_form, catalogue_form):
    bf = _normalize(brand_form)
    cf = _normalize(catalogue_form)
    if not bf or bf == "unspecified":
        return False
    aliases = {"tablet": ("tablet", "tablets", "tab"), "drops": ("drop", "drops"), "suspension": ("suspension",), "syrup": ("syrup",), "injection": ("injection", "infusion", "iv"), "spray": ("spray",), "capsule": ("capsule", "capsules"), "lozenge": ("lozenge", "lozenges")}
    terms = aliases.get(bf, (bf,))
    return any(term in cf for term in terms)


def _matching_branded_evidence(generic_name, strength, dosage_form_and_pack, pack_size, is_combination=False, brand_query="", brand_query_mode=False):
    """Return only pack/form/strength-compatible branded records; never use fuzzy equivalence."""
    from pathlib import Path
    import csv
    evidence_path = DATA_DIR / "branded_price_evidence.csv"
    if not evidence_path.exists():
        return []
    try:
        with evidence_path.open(newline="", encoding="utf-8-sig") as f:
            evidence = list(csv.DictReader(f))
    except OSError:
        return []
    generic_key = _normalize(generic_name)
    if is_combination:
        return []
    strength_key = _strength_key(strength)
    catalogue_pack = _pack_key(pack_size or dosage_form_and_pack, dosage_form_and_pack)
    matched = []
    for r in evidence:
        if str(r.get("verification_status", "")).casefold() != "verified":
            continue
        if not str(r.get("source_url", "")).startswith(("https://", "http://")):
            continue
        if brand_query_mode:
            query_tokens = _normalize(brand_query).split()
            brand_tokens = _normalize(r.get("brand_name", "")).split()
            if not query_tokens or not all(token in brand_tokens for token in query_tokens):
                continue
        evidence_generic = _normalize(r.get("generic_name", ""))
        # Catalogue labels may append dosage-form wording after a single salt. Do not allow
        # this prefix rule for combination products (blocked above).
        if not evidence_generic or not (generic_key == evidence_generic or generic_key.startswith(evidence_generic + " ")):
            continue
        if not strength_key or _strength_key(r.get("strength", "")) != strength_key:
            continue
        if not _form_matches(r.get("dosage_form", ""), dosage_form_and_pack):
            continue
        if _pack_key(r.get("pack_size", ""), r.get("dosage_form", "")) != catalogue_pack:
            continue
        try:
            price = float(str(r.get("mrp_inr", "")).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        matched.append({"brand_name": r.get("brand_name", ""), "price_inr": round(price, 2), "pack_size": r.get("pack_size", ""), "strength": r.get("strength", ""), "dosage_form": r.get("dosage_form", ""), "source_name": r.get("source_name", ""), "source_url": r.get("source_url", ""), "checked_on": r.get("checked_on", ""), "price_type": "filed_mrp", "verification_status": "verified_source_record"})
    return sorted(matched, key=lambda r: (r["brand_name"].casefold(), r["price_inr"]))


def _lower_cost_brand_alternatives(generic_name, strength, dosage_form_and_pack, is_combination=False, limit=5):
    """Return source-backed brands with same ingredient/strength/form, ordered by listed MRP.

    Packs can differ, so these are discovery options only—not direct savings comparisons.
    """
    if is_combination:
        return []
    import csv
    evidence_path = DATA_DIR / "branded_price_evidence.csv"
    if not evidence_path.exists():
        return []
    try:
        with evidence_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return []
    generic_key = _normalize(generic_name)
    strength_key = _strength_key(strength)
    matches = []
    seen = set()
    for row in rows:
        if str(row.get("verification_status", "")).casefold() != "verified":
            continue
        if not str(row.get("source_url", "")).startswith(("https://", "http://")):
            continue
        evidence_generic = _normalize(row.get("generic_name", ""))
        if not evidence_generic or not (generic_key == evidence_generic or generic_key.startswith(evidence_generic + " ")):
            continue
        if not strength_key or _strength_key(row.get("strength", "")) != strength_key:
            continue
        if not _form_matches(row.get("dosage_form", ""), dosage_form_and_pack):
            continue
        try:
            price = float(str(row.get("mrp_inr", "")).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue
        key = (_normalize(row.get("brand_name", "")), _normalize(row.get("pack_size", "")), price)
        if key in seen:
            continue
        seen.add(key)
        matches.append({"brand_name": row.get("brand_name", ""), "price_inr": round(price, 2), "pack_size": row.get("pack_size", ""), "strength": row.get("strength", ""), "dosage_form": row.get("dosage_form", ""), "source_name": row.get("source_name", ""), "source_url": row.get("source_url", ""), "checked_on": row.get("checked_on", ""), "price_type": "filed_mrp", "verification_status": "verified_source_record", "comparison_note": "Different pack sizes may not be directly comparable; verify current price and pack."})
    return sorted(matches, key=lambda r: (r["price_inr"], r["brand_name"].casefold(), r["pack_size"]))[:limit]


def _composition_tokens(*values):
    """Extract conservative ingredient words from source composition fields."""
    ignored = {"ip", "usp", "bp", "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "syrup", "suspension", "injection", "oral", "mg", "mcg", "ug", "ml", "iu", "and", "per", "of", "for", "with", "in", "plus"}
    tokens = []
    for value in values:
        cleaned = _normalize(re.sub(r"\d+(?:\.\d+)?", " ", as_text(value)))
        for token in cleaned.split():
            if len(token) > 2 and token not in ignored and token not in tokens:
                tokens.append(token)
    return tokens


def _jan_rows_for_brand(row, jan, max_rows=3):
    """Find likely Jan catalogue records by composition tokens and exact strength numbers.

    This is a discovery link only. It does not establish interchangeability.
    """
    ingredients = _composition_tokens(row.get("short_composition1", ""), row.get("short_composition2", ""))
    if not ingredients:
        return []
    comp_numbers = []
    for field in (row.get("short_composition1", ""), row.get("short_composition2", "")):
        comp_numbers.extend(re.findall(r"\d+(?:\.\d+)?", as_text(field)))
    if not comp_numbers:
        return []
    found = []
    for _, jr in jan.iterrows():
        jan_name = _normalize(jr.get("generic_name", ""))
        jan_tokens = set(jan_name.split())
        if not all(token in jan_tokens for token in ingredients):
            continue
        jan_numbers = re.findall(r"\d+(?:\.\d+)?", _normalize(jr.get("strength", "")))
        if sorted(comp_numbers) != sorted(jan_numbers):
            continue
        found.append(jr)
        if len(found) >= max_rows:
            break
    return found


def _branded_catalogue_search(query, jan, limit=5):
    """Search the supplied branded catalogue by product name, including brand-only queries."""
    frame = _load_indian_medicine_catalogue()
    q = _normalize(query)
    if frame.empty or not q:
        return []
    query_numbers = re.findall(r"\d+(?:\.\d+)?", q)
    # First use fast vectorized substring matching. If it misses (a typo), narrow
    # to records whose first word is a close spelling of the typed first word.
    candidate_mask = frame["_name_norm"].str.contains(re.escape(q), regex=True, na=False)
    if not candidate_mask.any():
        first = q.split()[0]
        first_words = frame["_name_norm"].str.split().str[0].dropna().unique().tolist()
        close_words = get_close_matches(first, first_words, n=25, cutoff=0.68)
        if not close_words:
            return []
        candidate_mask = frame["_name_norm"].str.split().str[0].isin(close_words)
        # If the query includes a strength, require it to occur in the product name.
        if query_numbers:
            for number in query_numbers:
                candidate_mask &= frame["_name_norm"].str.contains(rf"(?<!\d){re.escape(number)}(?!\d)", regex=True, na=False)
    candidates = frame[candidate_mask & (~frame["_discontinued_bool"]) & (frame["price(₹)"] > 0)].copy()
    if candidates.empty:
        return []
    candidates["_query_score"] = candidates["name"].map(lambda name: _match_score(q, [name]))
    candidates = candidates[candidates["_query_score"] >= 70].sort_values(["_query_score", "name"], ascending=[False, True])
    results = []
    seen = set()
    for _, brand in candidates.head(max(limit * 4, limit)).iterrows():
        brand_name = as_text(brand.get("name"))
        pack_label = as_text(brand.get("pack_size_label"))
        key = (_normalize(brand_name), _normalize(pack_label))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        jan_matches = _jan_rows_for_brand(brand, jan, max_rows=1)
        jr = jan_matches[0] if jan_matches else None
        generic_name = as_text(jr.get("generic_name")) if jr is not None else " ".join(_composition_tokens(brand.get("short_composition1", ""), brand.get("short_composition2", "")))
        strength_parts = [as_text(brand.get("short_composition1")), as_text(brand.get("short_composition2"))]
        strength = " + ".join(part for part in strength_parts if part)
        brand_price = round(float(brand.get("price(₹)")), 2)
        brand_option = {
            "brand_name": brand_name, "price_inr": brand_price,
            "manufacturer": as_text(brand.get("manufacturer_name")),
            "pack_size": as_text(brand.get("pack_size_label")), "strength": strength,
            "dosage_form": as_text(brand.get("type")),
            "source_name": "indian_medicine_data.csv supplied by user", "source_url": "", "checked_on": "",
            "price_type": "source-listed price; current retail validity unverified",
            "verification_status": "unverified_source_dataset",
            "comparison_note": "Found by brand-name search. Verify active ingredients, strength, form, pack and current price with a pharmacist."
        }
        jan_price = as_text(jr.get("price_inr")) if jr is not None else ""
        jan_pack = as_text(jr.get("unit_size_raw")) if jr is not None else ""
        results.append({
            "catalogue_id": "", "drug_code": as_text(jr.get("drug_code")) if jr is not None else "",
            "generic_name": generic_name or brand_name, "active_ingredient_candidate": " ".join(_composition_tokens(*strength_parts)),
            "strength": as_text(jr.get("strength")) if jr is not None else strength,
            "is_combination": bool(as_text(brand.get("short_composition2"))),
            "match_scope": "brand_name_search", "dosage_form_and_pack": as_text(brand.get("pack_size_label")),
            "jan_pack_size": jan_pack, "jan_price_inr": jan_price,
            "jan_price_status": as_text(jr.get("price_type")) if jr is not None else "NO_MATCHING_JAN_RECORD",
            "branded_candidate": brand_name, "branded_price_inr": str(brand_price),
            "branded_price_status": "SOURCE_LISTED_UNVERIFIED", "branded_price_source_url": "",
            "branded_pack_size": as_text(brand.get("pack_size_label")), "comparison_status": "NOT_COMPARABLE_UNVERIFIED",
            "source_reference": "indian_medicine_data.csv", "jan_source_page": as_text(jr.get("source_page")) if jr is not None else "",
            "jan_record_review_status": as_text(jr.get("data_review_status")) if jr is not None else "",
            "match_score": float(brand.get("_query_score", 0)), "match_type": "exact" if q in key else "close",
            "savings_inr": None, "savings_percent": None, "comparison_allowed": False,
            "indian_catalogue_brand_options": [brand_option], "price_source_count": int(bool(jan_price)) + 1,
            "price_coverage": "jan_aushadhi_and_branded" if jan_price else "branded_catalogue_only",
            "local_pharmacy_price_available": False,
            "local_pharmacy_price_note": "No local pharmacy price feed is included in the three supplied datasets.",
            "notice": "Brand-name result from the supplied dataset. Listed price is not current-verified; a similar ingredient/name does not establish interchangeability. No savings calculated."
        })
        if len(results) >= limit:
            break
    results.sort(key=lambda item: (
        0 if _pack_unit_count(item.get("branded_pack_size", "")) and _pack_unit_count(item.get("branded_pack_size", "")) == _pack_unit_count(item.get("jan_pack_size", "")) else 1,
        -float(item.get("match_score", 0)),
        float(item.get("branded_price_inr", 0) or 0),
        str(item.get("branded_candidate", "")).casefold(),
    ))
    return results


def _filter_gemma_terms(query, terms):
    """Validate model-generated search variants before using them for catalogue lookup."""
    qn = _normalize(query)
    safe = []
    for term in terms if isinstance(terms, list) else []:
        tn = _normalize(as_text(term)[:120])
        if not tn or tn == qn or tn in safe or len(tn) < 3:
            continue
        original_numbers = re.findall(r"\d+(?:\.\d+)?", qn)
        term_numbers = re.findall(r"\d+(?:\.\d+)?", tn)
        if original_numbers and original_numbers != term_numbers:
            continue
        safe.append(tn)
        if len(safe) >= 3:
            break
    return safe


def _gemma_search_terms(query, timeout_seconds=4.0):
    """Optional OpenAI-compatible Gemma query spelling/brand-term assistance.

    Gemma output is used only for catalogue discovery, never for prices, dosing,
    clinical equivalence, or substitution recommendations. No request is sent unless
    the operator explicitly configures a compatible endpoint and model ID.
    """
    import os, json
    import httpx
    # The Hacktoberfest Gemma 4 track uses Google's hosted Gemini API.
    # Keep local Ollama as an optional fallback for development, but only the
    # explicit gemini-api provider makes the hosted API call.
    provider = as_text(os.getenv("GEMMA_PROVIDER")).casefold()
    model = as_text(os.getenv("GEMMA_MODEL_ID"))
    if provider == "gemini-api":
        api_key = as_text(os.getenv("GEMMA_API_KEY"))
        if not api_key or not model:
            return []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "You help search a medicine catalogue. Return only JSON: {\"search_terms\":[...]} with at most 3 short spelling corrections or exact brand-name variants for the same text. Do not recommend alternatives, infer active ingredients, suggest substitutions, provide prices, or give medical advice. Preserve strength numbers exactly. If uncertain, return an empty list. Query: " + str(query)[:120]}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}
        }
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, json=payload)
                response.raise_for_status()
                body = response.json()
            content = body["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(str(content).strip())
            terms = parsed.get("search_terms", []) if isinstance(parsed, dict) else []
            return _filter_gemma_terms(query, terms)
        except Exception:
            return []
    base = as_text(os.getenv("GEMMA_API_BASE_URL")) or "http://localhost:11434/v1"
    model = model or "gemma4:e2b"
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        url = base
    elif base.endswith("/v1"):
        url = base + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    api_key = as_text(os.getenv("GEMMA_API_KEY"))
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You help search a medicine catalogue. Return only JSON: {\"search_terms\":[...]} with at most 3 short spelling corrections or exact brand-name variants for the same text. Do not recommend alternatives, infer active ingredients, suggest substitutions, provide prices, or give medical advice. Preserve strength numbers exactly. If uncertain, return an empty list."},
            {"role": "user", "content": str(query)[:120]}
        ]
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
        parsed = json.loads(str(content).strip().removeprefix("```json").removesuffix("``` ").strip())
        terms = parsed.get("search_terms", []) if isinstance(parsed, dict) else []
        return _filter_gemma_terms(query, terms)
    except Exception:
        # Search must continue when the optional AI provider is unavailable.
        return []


@lru_cache(maxsize=128)
def search_medicines(query: str, limit: int = 30, include_brand_options: bool = True):
    common, jan = load_catalogues()
    q = query.strip()
    if not q:
        return []
    results = []
    # Search only the three user-approved datasets: Jan Aushadhi products,
    # Indian medicine records, and the Kendra directory (served by main.py).
    # The retired 130-row seed catalogue is deliberately excluded from search.
    for _, row in common.iloc[0:0].iterrows():
        fields = [row.get("jan_aushadhi_generic_name", ""), row.get("branded_medicine_name_candidate", ""), row.get("active_salt_or_combination_to_verify", ""), row.get("strength", ""), row.get("category", "")]
        score = _match_score(q, fields)
        if score < 55:
            continue
        query_numbers = re.findall(r"\d+(?:\.\d+)?", _normalize(q))
        if query_numbers:
            searchable_name_strength = _normalize(" ".join([as_text(row.get("jan_aushadhi_generic_name")), as_text(row.get("strength"))]))
            if not all(number in re.findall(r"\d+(?:\.\d+)?", searchable_name_strength) for number in query_numbers):
                continue
        generic_name = as_text(row.get("jan_aushadhi_generic_name"))
        strength = as_text(row.get("strength"))
        ingredient_candidate = as_text(row.get("active_salt_or_combination_to_verify"))
        combination = _is_combination(generic_name, strength, ingredient_candidate)
        # A single ingredient query must rank matching single-ingredient medicines
        # above combination products that merely contain that ingredient.
        q_norm = _normalize(q)
        ingredient_query = len(q_norm.split()) == 1
        ingredient_priority = 18 if ingredient_query and not combination and q_norm in _normalize(generic_name).split() else (0 if ingredient_query and combination else 6)
        ranked_score = round(min(100, score + ingredient_priority), 1)
        code = as_text(row.get("jan_aushadhi_drug_code", ""))
        jrows = jan[jan["drug_code"].astype(str).str.strip() == code]
        j = jrows.iloc[0].to_dict() if not jrows.empty else {}
        results.append({
            "catalogue_id": as_text(row.get("catalogue_id")),
            "drug_code": code,
            "generic_name": generic_name,
            "active_ingredient_candidate": ingredient_candidate,
            "strength": strength,
            "is_combination": combination,
            "match_scope": "combination_contains_ingredient" if combination and ingredient_query else ("single_ingredient" if not combination else "name_match"),
            "dosage_form_and_pack": as_text(row.get("dosage_form_and_pack")),
            "jan_pack_size": as_text(row.get("jan_aushadhi_pack_size")),
            "jan_price_inr": as_text(row.get("jan_aushadhi_price_inr_as_in_supplied_csv")),
            "jan_price_status": as_text(row.get("jan_aushadhi_price_status")),
            "branded_candidate": as_text(row.get("branded_medicine_name_candidate")),
            "branded_price_inr": as_text(row.get("branded_price_inr")),
            "branded_price_status": "MISSING_SOURCE_EVIDENCE" if not as_text(row.get("branded_price_inr")) else "REVIEW_REQUIRED",
            "branded_price_source_url": as_text(row.get("branded_price_source_url")),
            "branded_pack_size": as_text(row.get("branded_pack_size")),
            "comparison_status": as_text(row.get("price_comparison_status")),
            "source_reference": as_text(row.get("source_reference")),
            "jan_source_page": as_text(j.get("source_page", "")),
            "jan_record_review_status": as_text(j.get("data_review_status", "")),
            "match_score": ranked_score,
            "match_type": "exact" if score >= 99 and not combination else ("close" if score >= 78 else "fuzzy"),
            "savings_inr": None,
            "savings_percent": None,
            "comparison_allowed": False,
            "notice": "Search similarity is not proof of medicine equivalence. Prices and product identity require independent verification; no savings calculated."
        })

    # Search the full Jan Aushadhi catalogue too, including records outside the 130-row shortlist.
    common_codes = {r["drug_code"] for r in results}
    for _, row in jan.iterrows():
        code = as_text(row.get("drug_code"))
        if code in common_codes:
            continue
        generic_name = as_text(row.get("generic_name"))
        strength = as_text(row.get("strength"))
        fields = [generic_name, strength, row.get("unit_size_raw", "")]
        score = _match_score(q, fields)
        if score < 55:
            continue
        query_numbers = re.findall(r"\d+(?:\.\d+)?", _normalize(q))
        if query_numbers:
            searchable_name_strength = _normalize(" ".join([as_text(row.get("generic_name")), as_text(row.get("strength"))]))
            if not all(number in re.findall(r"\d+(?:\.\d+)?", searchable_name_strength) for number in query_numbers):
                continue
        combination = _is_combination(generic_name, strength)
        q_norm = _normalize(q)
        ingredient_query = len(q_norm.split()) == 1
        ingredient_priority = 18 if ingredient_query and not combination and q_norm in _normalize(generic_name).split() else (0 if ingredient_query and combination else 6)
        ranked_score = round(min(100, score + ingredient_priority), 1)
        results.append({
            "catalogue_id": "", "drug_code": code,
            "generic_name": as_text(row.get("generic_name")),
            "active_ingredient_candidate": "", "strength": strength,
            "is_combination": combination,
            "match_scope": "combination_contains_ingredient" if combination and ingredient_query else ("single_ingredient" if not combination else "name_match"),
            "dosage_form_and_pack": as_text(row.get("unit_size_raw")),
            "jan_pack_size": as_text(row.get("unit_size_raw")),
            "jan_price_inr": as_text(row.get("price_inr")),
            "jan_price_status": as_text(row.get("price_type")),
            "branded_candidate": "", "branded_price_inr": "",
            "branded_price_status": "NO_BRAND_MAPPING_OR_PRICE", "branded_price_source_url": "", "branded_pack_size": "", "comparison_status": "NO_BRANDED_MATCH",
            "source_reference": "", "jan_source_page": as_text(row.get("source_page")),
            "jan_record_review_status": as_text(row.get("data_review_status")),
            "match_score": ranked_score,
            "match_type": "exact" if score >= 99 and not combination else ("close" if score >= 78 else "fuzzy"),
            "savings_inr": None, "savings_percent": None, "comparison_allowed": False,
            "notice": "Jan Aushadhi catalogue record only; fuzzy search does not establish equivalence or verified branded savings."
        })
    # Also search the branded dataset directly. Previously, brand-name queries were
    # only checked against the Jan Aushadhi generic-name catalogue, so names such as
    # a marketed brand could return zero results even when present in the 254k-row file.
    search_terms = [q]
    # Autocomplete is deliberately local/lightweight: do not invoke Gemma or scan
    # the broad brand catalogue for every keystroke. Full search gets those options.
    if include_brand_options:
        for ai_term in _gemma_search_terms(q):
            if ai_term not in {_normalize(term) for term in search_terms}:
                search_terms.append(ai_term)
    branded_hits = []
    if include_brand_options:
        for search_term in search_terms:
            branded_hits.extend(_branded_catalogue_search(search_term, jan, limit=min(max(limit, 5), 10)))
    # Deduplicate brand hits returned by the original query and optional Gemma spelling hints.
    unique_hits = []
    seen_hit_keys = set()
    for hit in branded_hits:
        hit_key = (_normalize(hit.get("branded_candidate", "")), _normalize(hit.get("branded_pack_size", "")))
        if hit_key[0] and hit_key not in seen_hit_keys:
            seen_hit_keys.add(hit_key)
            unique_hits.append(hit)
    branded_hits = unique_hits
    existing_brand_names = {(_normalize(r.get("branded_candidate", "")), _normalize(r.get("branded_pack_size", ""))) for r in results if r.get("branded_candidate")}
    for hit in branded_hits:
        brand_key = (_normalize(hit.get("branded_candidate", "")), _normalize(hit.get("branded_pack_size", "")))
        # Brand-name direct hits are added only when the query actually matches the
        # product name, and are de-duplicated against any existing catalogue result.
        if brand_key[0] and brand_key not in existing_brand_names:
            results.append(hit)
            existing_brand_names.add(brand_key)

    # If the query is a known brand name, restrict price attachment and ranking to that brand.
    evidence_rows = []
    evidence_file = DATA_DIR / "branded_price_evidence.csv"
    if evidence_file.exists():
        try:
            import csv
            with evidence_file.open(newline="", encoding="utf-8-sig") as f:
                evidence_rows = list(csv.DictReader(f))
        except OSError:
            evidence_rows = []
    query_tokens = _normalize(q).split()
    brand_query_mode = bool(query_tokens) and any(
        all(token in _normalize(r.get("brand_name", "")).split() for token in query_tokens)
        for r in evidence_rows
    )
    # Attach source-backed brand prices only when salt, strength, dosage form and pack agree exactly.
    for item in results:
        evidence = _matching_branded_evidence(
            item.get("generic_name", ""), item.get("strength", ""),
            item.get("dosage_form_and_pack", ""), item.get("jan_pack_size", ""),
            item.get("is_combination", False), q, brand_query_mode
        )
        item["lower_cost_brand_alternatives"] = _lower_cost_brand_alternatives(
            item.get("generic_name", ""), item.get("strength", ""),
            item.get("dosage_form_and_pack", ""), item.get("is_combination", False), 5
        )
        # Attach the large user-supplied catalogue lazily after ranking. Scanning
        # 254k rows for every result makes a normal search unacceptably slow.
        if item.get("match_scope") != "brand_name_search":
            item["indian_catalogue_brand_options"] = []
        item["branded_price_options"] = evidence[:8]
        if evidence:
            best = evidence[0]
            item["branded_candidate"] = best["brand_name"]
            item["branded_price_inr"] = str(best["price_inr"])
            item["branded_price_status"] = "verified_source_record"
            item["branded_price_source_url"] = best["source_url"]
            item["branded_price_checked_date"] = best["checked_on"]
            item["branded_price_type"] = "NPPA-filed MRP; not necessarily discounted retail price"
            item["branded_pack_size"] = best["pack_size"]
        else:
            item["branded_price_options"] = []
            item["branded_price_type"] = "unverified"

    if brand_query_mode:
        represented = {
            (str(opt.get("brand_name", "")).casefold(), str(opt.get("pack_size", "")).casefold(), str(opt.get("strength", "")).casefold())
            for item in results for opt in item.get("branded_price_options", [])
        }
        for row in evidence_rows:
            brand_tokens = _normalize(row.get("brand_name", "")).split()
            if not query_tokens or not all(token in brand_tokens for token in query_tokens):
                continue
            key = (str(row.get("brand_name", "")).casefold(), str(row.get("pack_size", "")).casefold(), str(row.get("strength", "")).casefold())
            if key in represented:
                continue
            try:
                brand_price = float(str(row.get("mrp_inr", "")).replace(",", ""))
            except ValueError:
                continue
            if brand_price <= 0 or str(row.get("verification_status", "")).casefold() != "verified":
                continue
            brand_option = {"brand_name": row.get("brand_name", ""), "price_inr": round(brand_price, 2), "pack_size": row.get("pack_size", ""), "strength": row.get("strength", ""), "dosage_form": row.get("dosage_form", ""), "source_name": row.get("source_name", ""), "source_url": row.get("source_url", ""), "checked_on": row.get("checked_on", ""), "price_type": "filed_mrp", "verification_status": "verified_source_record"}
            results.append({"catalogue_id":"", "drug_code":"", "generic_name":row.get("generic_name", ""), "active_ingredient_candidate":row.get("generic_name", ""), "strength":row.get("strength", ""), "is_combination":"+" in str(row.get("generic_name", "")), "match_scope":"brand_evidence_only", "dosage_form_and_pack":f"{row.get('dosage_form','')} | pack {row.get('pack_size','')}", "jan_pack_size":"", "jan_price_inr":"", "jan_price_status":"not_current_verified", "branded_candidate":row.get("brand_name", ""), "branded_price_inr":str(round(brand_price, 2)), "branded_price_status":"verified_source_record", "branded_price_source_url":row.get("source_url", ""), "branded_price_checked_date":row.get("checked_on", ""), "branded_price_type":"NPPA-filed MRP; not necessarily discounted retail price", "branded_pack_size":row.get("pack_size", ""), "branded_price_options":[brand_option], "comparison_status":"not_comparable", "match_score":100.0 if q_norm in _normalize(row.get("brand_name", "")) else 90.0, "match_type":"exact" if q_norm in _normalize(row.get("brand_name", "")) else "close", "comparison_allowed":False, "savings_inr":None, "savings_percent":None, "notice":"Brand MRP evidence only. No exact current Jan Aushadhi pack match is verified, so no savings are calculated."})
            represented.add(key)

    q_norm = _normalize(q)
    ingredient_query = len(q_norm.split()) == 1
    if brand_query_mode:
        for item in results:
            brand_match = any(all(token in _normalize(b.get("brand_name", "")).split() for token in q_norm.split()) for b in item.get("branded_price_options", []))
            if brand_match:
                exact_brand_phrase = q_norm in _normalize(item.get("branded_candidate", ""))
                item["match_score"] = 100.0 if exact_brand_phrase else 90.0
                item["match_type"] = "exact" if exact_brand_phrase else "close"
                item["match_scope"] = "exact_branded_pack" if exact_brand_phrase else "related_branded_pack"
            else:
                item["match_score"] = min(float(item.get("match_score", 0)), 35.0)
    if ingredient_query:
        # A single-salt search must never put a combination medicine above a single-salt candidate.
        results.sort(key=lambda item: (bool(item.get("is_combination")), -item["match_score"], item["generic_name"].casefold()))
    else:
        # For multi-word queries, prefer names that start with the typed phrase;
        # then prefer canonical generic-name matches over secondary metadata matches.
        def _result_rank(item):
            name = _normalize(item.get("generic_name", ""))
            starts_with_query = bool(q_norm) and (name == q_norm or name.startswith(q_norm + " "))
            all_query_words_in_name = bool(q_norm) and all(token in name.split() for token in q_norm.split())
            return (not starts_with_query, not all_query_words_in_name, -item["match_score"], bool(item.get("is_combination")), name)
        results.sort(key=_result_rank)
    # "Exact" means the whole canonical catalogue name matches, not merely one ingredient inside it.
    for item in results:
        if item.get("match_scope") in {"exact_branded_pack", "brand_evidence_only"}:
            item["match_type"] = "exact"
        elif _normalize(item.get("generic_name", "")) == q_norm and not item.get("is_combination"):
            item["match_type"] = "exact"
        elif item.get("is_combination") and ingredient_query:
            item["match_type"] = "fuzzy"
        elif item.get("match_score", 0) >= 78:
            item["match_type"] = "close"
        else:
            item["match_type"] = "fuzzy"
    # Enrich candidates before final ordering so records with both Jan Aushadhi
    # and branded catalogue prices are surfaced before one-source-only records.
    # The large branded dataset is cached after its first load; cap enrichment to
    # the first 40 textual candidates to keep requests responsive.
    for item in results[:min(limit, 8)]:
        if include_brand_options and item.get("match_scope") != "brand_name_search":
            item["indian_catalogue_brand_options"] = _indian_catalogue_brand_options(
                item.get("generic_name", ""), item.get("strength", ""),
                item.get("dosage_form_and_pack", ""), item.get("is_combination", False), 5
            )
            brand_options = item.get("indian_catalogue_brand_options") or []
            jan_count = _pack_unit_count(item.get("jan_pack_size") or item.get("dosage_form_and_pack", ""))
            same_pack_options = [o for o in brand_options if jan_count and _pack_unit_count(o.get("pack_size", "")) == jan_count]
            selectable_options = same_pack_options or brand_options
            preferred = next((o for o in selectable_options if "paracetamol" in _normalize(item.get("generic_name", "")).split() and _normalize(o.get("brand_name", "")).startswith("dolo ")), None)
            if preferred is None and selectable_options:
                preferred = selectable_options[0]
            # Promote a real, composition/strength/form-matched catalogue candidate
            # to the primary comparison. Prices remain explicitly source-listed.
            if preferred and not item.get("branded_price_inr"):
                item["branded_candidate"] = preferred["brand_name"]
                item["branded_price_inr"] = str(preferred["price_inr"])
                item["branded_price_status"] = "SOURCE_LISTED_UNVERIFIED"
                item["branded_price_source_url"] = preferred.get("source_url", "")
                item["branded_pack_size"] = preferred.get("pack_size", "")
                item["branded_price_type"] = preferred.get("price_type", "source-listed price; current retail validity unverified")
                item["branded_price_checked_date"] = ""
                item["comparison_status"] = "SOURCE_LISTED_UNVERIFIED_SAME_PACK" if preferred.get("pack_comparable") else "SOURCE_LISTED_UNVERIFIED_PACK_SIZE_DIFFERS"
                item["comparison_allowed"] = False
                item["featured_brand_pack_comparable"] = bool(preferred.get("pack_comparable"))
        elif not include_brand_options:
            item["indian_catalogue_brand_options"] = []
        jan_price = as_text(item.get("jan_price_inr"))
        brand_options = item.get("indian_catalogue_brand_options") or []
        item["price_source_count"] = int(bool(jan_price)) + int(bool(brand_options) or bool(item.get("branded_price_inr")))
        item["price_coverage"] = ("jan_aushadhi_and_branded" if jan_price and (brand_options or item.get("branded_price_inr"))
                                   else "jan_aushadhi_only" if jan_price
                                   else "branded_catalogue_only" if brand_options or item.get("branded_price_inr") else "no_price")
        item["local_pharmacy_price_available"] = False
        item["local_pharmacy_price_note"] = "No local pharmacy price feed is included in the three supplied datasets."
    # Prefer the requested dosage form. For a plain ingredient search,
    # put tablets first while retaining other valid formulations below.
    form_aliases = {
        "tablet": {"tablet", "tablets", "tab", "tabs"},
        "capsule": {"capsule", "capsules", "cap", "caps"},
        "syrup": {"syrup"},
        "drops": {"drop", "drops"},
        "injection": {"injection", "injections"},
        "suspension": {"suspension"},
    }
    query_tokens = set(q_norm.split())
    requested_form = next(
        (form for form, aliases in form_aliases.items() if query_tokens & aliases),
        None,
    )

    def _dosage_form_rank(item):
        candidate_text = _normalize(" ".join([
            str(item.get("dosage_form_and_pack", "")),
            str(item.get("generic_name", "")),
            str(item.get("branded_candidate", "")),
        ]))
        candidate_tokens = set(candidate_text.split())

        if requested_form:
            aliases = form_aliases[requested_form]
            return 0 if candidate_tokens & aliases else 1

        if ingredient_query:
            if candidate_tokens & form_aliases["tablet"]:
                return 0
            if candidate_tokens & form_aliases["capsule"]:
                return 1
            if candidate_tokens & form_aliases["syrup"]:
                return 3
            if candidate_tokens & form_aliases["drops"]:
                return 4
            if candidate_tokens & form_aliases["injection"]:
                return 5
            return 2

        return 0

    if ingredient_query or requested_form:
        results.sort(key=lambda item: (
            _dosage_form_rank(item),
            -int(item.get("price_source_count", 0)),
            bool(item.get("is_combination")),
            -item["match_score"],
            item["generic_name"].casefold(),
        ))
    else:
        results.sort(key=lambda item: (
            -int(item.get("price_source_count", 0)),
            -item["match_score"],
            item["generic_name"].casefold(),
        ))
    return results[:limit]


def quality_report():
    """Quality summary limited to the three approved user-supplied datasets."""
    _, jan = load_catalogues()
    brand = _load_indian_medicine_catalogue()
    kendra_path = ROOT / "data" / "input" / "kendra_directory.csv"
    import csv
    kendra_rows = []
    if kendra_path.exists():
        with kendra_path.open(newline="", encoding="utf-8-sig") as f:
            kendra_rows = list(csv.DictReader(f))
    return {
        "files": {
            JAN_FILE.name: {
                "rows": int(len(jan)),
                "duplicate_drug_codes": int(jan["drug_code"].astype(str).duplicated().sum()),
                "missing_prices": int(pd.to_numeric(jan["price_inr"], errors="coerce").isna().sum()),
                "records_flagged_review": int(jan["data_review_status"].astype(str).str.contains("review", case=False, na=False).sum()),
                "price_policy": "Display source-listed price with its supplied verification status; do not treat as current verified retail price."
            },
            INDIAN_MEDICINE_FILE.name: {
                "rows": int(len(brand)),
                "missing_prices": int(brand["price(₹)"].isna().sum()) if not brand.empty else 0,
                "discontinued_records": int(brand["_discontinued_bool"].sum()) if not brand.empty else 0,
                "price_policy": "Display source-listed price as unverified; exclude discontinued records from alternatives."
            },
            kendra_path.name: {
                "rows": len(kendra_rows),
                "coordinate_rows": sum(bool(str(r.get("latitude", "")).strip() and str(r.get("longitude", "")).strip()) for r in kendra_rows),
                "source_status": "Imported directory; not independently reverified"
            }
        },
        "ranking_policy": "Results with both a Jan Aushadhi listed price and a matching branded catalogue option rank before records with only one price source.",
        "local_pharmacy_prices": {"available": False, "reason": "No local-pharmacy price feed is present in the three approved datasets."},
        "savings_policy": "Savings percentages are not calculated from unverified source-listed prices or unmatched packs."
    }
