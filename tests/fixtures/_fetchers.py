"""
_fetchers.py — Shared fetch logic for regenerate_fixtures.py and check_fixtures.py.

Each public function is a generator that yields (fixture_path, raw_data) tuples
for one API. The caller decides whether to save (regenerate) or compare (check).

Raw data types match exactly what the corresponding _fetch_* method returns:
    dict / list  →  serialized as JSON  (.json)
    ET.Element   →  serialized as XML   (.xml)
    str          →  serialized as HTML  (.html)

Callers use serialize() / deserialize() for consistent round-tripping.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Generator, Iterator

from scripts.utils.normalize_query_string import normalize_query_string

FIXTURES_DIR = Path(__file__).resolve().parent

Fixture = tuple[Path, Any]  # (path, raw_data)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def extension(data: Any) -> str:
    """Return the file extension for data based on its type."""
    if isinstance(data, ET.Element):
        return "xml"
    if isinstance(data, str):
        return "html"
    return "json"


def serialize(data: Any) -> str:
    """Serialize raw data to a string for saving or comparison."""
    if isinstance(data, ET.Element):
        return ET.tostring(data, encoding="unicode")
    if isinstance(data, str):
        return data
    return json.dumps(data, indent=2, ensure_ascii=False)


def deserialize(content: str, ext: str) -> Any:
    """Deserialize saved fixture content back to a Python object."""
    if ext == "xml":
        return ET.fromstring(content)
    if ext == "html":
        return content
    return json.loads(content)


def _norm(name: str) -> str:
    return normalize_query_string(name)


# ---------------------------------------------------------------------------
# GBIF
# Fetch types: query_data=dict, synonym_data=list[dict], accepted_data=dict
# ---------------------------------------------------------------------------

_GBIF_SCENARIOS = [
    ("accepted", "Amanita muscaria"),
    ("synonym", "Agaricus muscarius"),
    ("not_found", "Not species"),
]


def gbif_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all GBIF fixture files."""
    from scripts.apis_pipe.gbif import GBIFAPI

    client = GBIFAPI()
    base = FIXTURES_DIR / "gbif"

    for scenario, name in _GBIF_SCENARIOS:
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue
        synonym_data = client._fetch_synonym_data(query_data)
        yield base / scenario / "synonym_data.json", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.json", accepted_data


# ---------------------------------------------------------------------------
# COL
# Fetch types: query_data=dict, synonym_data=list, accepted_data=dict
# ---------------------------------------------------------------------------

_COL_SCENARIOS = [
    ("accepted", "Quercus robur"),
    ("synonym", "Quercus atrosanguinea"),
    ("not_found", "Not species"),
]


def col_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all COL fixture files."""
    from scripts.apis_pipe.col import COLAPI

    client = COLAPI()
    base = FIXTURES_DIR / "col"

    for scenario, name in _COL_SCENARIOS:
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue
        synonym_data = client._fetch_synonym_data(query_data)
        yield base / scenario / "synonym_data.json", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.json", accepted_data


# ---------------------------------------------------------------------------
# Tropicos
# Fetch types: all list (JSON). accepted_data reuses query_data in accepted path.
# Extra method: _fetch_accepted_list (always called).
# ---------------------------------------------------------------------------

_TROPICOS_SCENARIOS = [
    ("accepted", "Quercus robur"),
    ("synonym", "Quercus pedunculata"),
    ("not_found", "Not species"),
]


def tropicos_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all Tropicos fixture files."""
    import os

    from scripts.config import TROPICOS_API_KEY_PLACEHOLDER

    key = os.environ.get("TROPICOS_API_KEY", "")
    if not key or key == TROPICOS_API_KEY_PLACEHOLDER:
        print("  [Tropicos] SKIPPED — TROPICOS_API_KEY not configured")
        return

    from scripts.apis_pipe.tropicos import TropicosAPI

    client = TropicosAPI()
    base = FIXTURES_DIR / "tropicos"

    for scenario, name in _TROPICOS_SCENARIOS:
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue

        name_id = client._extract_internal_id(query_data)
        accepted_list = client._fetch_accepted_list(name_id)
        yield base / scenario / "accepted_list_data.json", accepted_list

        accepted_id = client._extract_internal_accepted_id(accepted_list, name_id)
        synonym_data = client._fetch_synonym_data(accepted_id)
        yield base / scenario / "synonym_data.json", synonym_data

        if accepted_id == name_id:
            # Accepted path: no extra fetch; reuse query_data as accepted_data.
            yield base / scenario / "accepted_data.json", query_data
        else:
            accepted_data = client._fetch_accepted_data(accepted_id)
            yield base / scenario / "accepted_data.json", accepted_data


# ---------------------------------------------------------------------------
# FishBase
# Fetch types: query_data=str (HTML), synonym_data=str (HTML), accepted_data=dict {}
# ---------------------------------------------------------------------------

_FISHBASE_SCENARIOS = [
    ("accepted", "Gadus morhua"),
    ("synonym", "Gadus callarias"),
    ("not_found", "Not species"),
]

_FISHBASE_PROC_TIME_RE = re.compile(
    r"<span class='slabel7' >Total processing time for the page : [\d.]+ seconds</span>"
)
# FishBase load-balances across geographic mirrors (fishbase.se, fishbase.us, etc.).
# Mirror hostnames appear throughout the HTML, so normalize to a canonical domain.
_FISHBASE_MIRROR_RE = re.compile(r"(https?:)?//(?:www\.)?fishbase\.\w+")
# pagefrom includes a city name that varies by server (e.g. "- Stockholm, Sweden").
_FISHBASE_PAGEFROM_RE = re.compile(
    r"(<input[^>]*name='pagefrom'[^>]*value=')[^']*(')",
    re.IGNORECASE,
)


def _strip_fishbase_volatile(html: str) -> str:
    """Normalize per-request and mirror-dependent content in FishBase HTML."""
    html = _FISHBASE_PROC_TIME_RE.sub("", html)
    html = _FISHBASE_MIRROR_RE.sub("//www.fishbase.se", html)
    html = _FISHBASE_PAGEFROM_RE.sub(r"\1\2", html)
    return html


def fishbase_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all FishBase fixture files."""
    from scripts.apis_pipe.fishbase import FishBaseAPI

    client = FishBaseAPI()
    base = FIXTURES_DIR / "fishbase"

    for scenario, name in _FISHBASE_SCENARIOS:
        query_data = _strip_fishbase_volatile(client._fetch_query_data(_norm(name)))
        yield base / scenario / "query_data.html", query_data
        if client._is_empty(query_data):
            continue
        synonym_data = _strip_fishbase_volatile(client._fetch_synonym_data(query_data))
        yield base / scenario / "synonym_data.html", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.json", accepted_data


# ---------------------------------------------------------------------------
# GenBank
# Fetch types: query_data=dict, synonym_data=ET.Element, accepted_data=ET.Element
# Note: _fetch_accepted_data returns synonym_data unchanged (no extra call).
# ---------------------------------------------------------------------------

_GENBANK_SCENARIOS = [
    ("accepted", "Amanita muscaria"),
    ("synonym", "Agaricus muscarius"),
    ("not_found", "Not species"),
]


def genbank_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all GenBank fixture files."""
    from scripts.apis_pipe.genbank import GenBankAPI

    client = GenBankAPI()
    base = FIXTURES_DIR / "genbank"

    # NCBI allows 3 req/s without an API key. _fetch_query_data makes up to 2
    # esearch calls and _fetch_synonym_data makes 1 efetch call, so sleep
    # between each outer call to stay safely under the limit.
    for scenario, name in _GENBANK_SCENARIOS:
        time.sleep(0.4)
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue
        time.sleep(0.4)
        synonym_data = client._fetch_synonym_data(query_data)
        yield base / scenario / "synonym_data.xml", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.xml", accepted_data


# ---------------------------------------------------------------------------
# Index Fungorum
# Fetch types: all ET.Element. _fetch_accepted_data returns synonym_data unchanged.
# ---------------------------------------------------------------------------

_INDEX_FUNGORUM_SCENARIOS = [
    ("accepted", "Amanita muscaria"),
    ("synonym", "Agaricus muscarius"),
    ("not_found", "Not species"),
]


def index_fungorum_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all Index Fungorum fixture files."""
    from scripts.apis_pipe.index_fungorum import IndexFungorumAPI

    client = IndexFungorumAPI()
    base = FIXTURES_DIR / "index_fungorum"

    for scenario, name in _INDEX_FUNGORUM_SCENARIOS:
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.xml", query_data
        if client._is_empty(query_data):
            continue
        synonym_data = client._fetch_synonym_data(query_data)
        yield base / scenario / "synonym_data.xml", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.xml", accepted_data


# ---------------------------------------------------------------------------
# Mushroom Observer
# Fetch types: query_data=dict, synonym_data=list, accepted_data=list
# Note: synonym and accepted data are derived from query_data in-memory (no extra calls).
# ---------------------------------------------------------------------------

_MUSHROOM_OBSERVER_SCENARIOS = [
    ("accepted", "Amanita muscaria"),
    ("synonym", "Amanita amerimuscaria"),
    ("not_found", "Not species"),
]

_MO_VOLATILE_KEYS = {"run_date", "run_time", "last_viewed", "number_of_views"}


def _strip_mo_volatile(data: dict) -> dict:
    """Remove per-request volatile fields from a Mushroom Observer API response."""
    result = {k: v for k, v in data.items() if k not in _MO_VOLATILE_KEYS}
    if "results" in result:
        cleaned_results = []
        for r in result["results"]:
            r = {k: v for k, v in r.items() if k not in _MO_VOLATILE_KEYS}
            if "synonyms" in r:
                r["synonyms"] = [
                    {k: v for k, v in s.items() if k not in _MO_VOLATILE_KEYS}
                    for s in r["synonyms"]
                ]
            cleaned_results.append(r)
        result["results"] = cleaned_results
    return result


def mushroom_observer_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all Mushroom Observer fixture files."""
    from scripts.apis_pipe.mushroomobs import MushroomObserverAPI

    client = MushroomObserverAPI()
    base = FIXTURES_DIR / "mushroom_observer"

    for scenario, name in _MUSHROOM_OBSERVER_SCENARIOS:
        query_data = _strip_mo_volatile(client._fetch_query_data(_norm(name)))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue
        synonym_data = client._fetch_synonym_data(query_data)
        yield base / scenario / "synonym_data.json", synonym_data
        accepted_data = client._fetch_accepted_data(query_data, synonym_data)
        yield base / scenario / "accepted_data.json", accepted_data


# ---------------------------------------------------------------------------
# ITIS
# Fetch types: all JSON (dict or list).
# Custom orchestrator: _fetch_synonym_data takes accepted_id (str), not raw_data.
# Extra method: _fetch_hierarchy_data(accepted_id) → list.
# Synonym path: _extract_internal_accepted_id internally calls
#   _fetch_internal_accepted_id_data; we capture that return value.
# ---------------------------------------------------------------------------

_ITIS_SCENARIOS = [
    ("accepted", "Oncorhynchus mykiss"),
    ("synonym", "Salmo mykiss"),
    ("not_found", "Not species"),
]


def itis_fixtures() -> Iterator[Fixture]:
    """Yield (path, data) pairs for all ITIS fixture files."""
    from scripts.apis_pipe.itis import ITISAPI

    client = ITISAPI()
    base = FIXTURES_DIR / "itis"

    for scenario, name in _ITIS_SCENARIOS:
        query_data = client._fetch_query_data(_norm(name))
        yield base / scenario / "query_data.json", query_data
        if client._is_empty(query_data):
            continue

        if scenario == "synonym":
            # Capture _fetch_internal_accepted_id_data return value without a
            # second network call by temporarily wrapping the method.
            captured: dict[str, Any] = {}
            _original = client._fetch_internal_accepted_id_data

            def _capturing_wrapper(tsn: str, _orig=_original, _cap=captured) -> list:
                result = _orig(tsn)
                _cap["data"] = result
                return result

            client._fetch_internal_accepted_id_data = _capturing_wrapper  # type: ignore[method-assign]

        accepted_id = client._extract_internal_accepted_id(query_data)

        if scenario == "synonym":
            client._fetch_internal_accepted_id_data = _original  # type: ignore[method-assign]
            yield (
                base / scenario / "internal_accepted_id_data.json",
                captured.get("data", []),
            )

        if not accepted_id:
            continue

        synonym_data = client._fetch_synonym_data(accepted_id)
        yield base / scenario / "synonym_data.json", synonym_data
        accepted_data = client._fetch_accepted_data(accepted_id)
        yield base / scenario / "accepted_data.json", accepted_data
        hierarchy_data = client._fetch_hierarchy_data(accepted_id)
        yield base / scenario / "hierarchy_data.json", hierarchy_data


# ---------------------------------------------------------------------------
# All API fetchers in run order
# ---------------------------------------------------------------------------

ALL_FETCHERS: list[tuple[str, Generator[Fixture, None, None]]] = [
    ("GBIF", gbif_fixtures),
    ("COL", col_fixtures),
    ("Tropicos", tropicos_fixtures),
    ("FishBase", fishbase_fixtures),
    ("GenBank", genbank_fixtures),
    ("Index Fungorum", index_fungorum_fixtures),
    ("Mushroom Observer", mushroom_observer_fixtures),
    ("ITIS", itis_fixtures),
]
