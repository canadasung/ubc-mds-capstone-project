"""
test_API_online.py — Live connectivity checks for APIs in scripts/APIs_pipe.

Each test makes a minimal real HTTP request to confirm the API is reachable,
accepting requests, and not returning credential or server errors. Response
format and content are not validated.

NOTE: These tests require internet access and will fail if the machine is offline.

Notice: These tests are intended only to check for basic connectivity to all APIs and do not guarantee that all API calls in the pipeline will succeed. Other code may call APIs incorrectly, or call endpoints that are not working or not supported.

Run from the project root:
    pytest tests/APIs_pipe/test_API_online.py -v
"""

import os
import socket

import pytest
import requests

_TIMEOUT = 15
_TEST_FUNGUS = "Amanita muscaria"
_TEST_PLANT = "Quercus robur"

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

_STATUS_DESCRIPTIONS = {
    301: "moved permanently — endpoint URL has changed",
    302: "redirect — endpoint may have moved",
    400: "bad request — query may be malformed",
    401: "unauthorized — credentials missing or invalid",
    403: "forbidden — access blocked, possibly by IP or credentials",
    404: "not found — endpoint may have moved",
    405: "method not allowed — GET may not be supported here",
    429: "rate limited — too many requests sent",
    500: "internal server error — service is down or crashing",
    502: "bad gateway — upstream server error",
    503: "service unavailable — server overloaded or temporarily down",
    504: "gateway timeout — upstream server timed out",
}


def _describe(code: int) -> str:
    return _STATUS_DESCRIPTIONS.get(code, "unexpected HTTP status")


@pytest.fixture(scope="session", autouse=True)
def require_internet():
    """Fail the entire session immediately if the machine has no internet."""
    try:
        socket.setdefaulttimeout(5)
        socket.create_connection(("8.8.8.8", 53))
    except OSError:
        pytest.fail(
            "No internet connection detected — all API tests require network access. "
            "Connect to the internet and re-run."
        )


def _get(url, params=None, headers=None):
    """Issue a GET request, failing the test if the host is unreachable or rate-limits us."""
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
    except _NETWORK_ERRORS as e:
        pytest.fail(f"Could not reach {url}: {e}")
    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        pytest.fail(
            f"Rate limited by {url} (HTTP 429) — "
            f"Retry-After: {retry_after}s. Wait before re-running the tests."
        )
    return resp


# ---------------------------------------------------------------------------
# Global backbone APIs
# ---------------------------------------------------------------------------


def test_gbif_online():
    resp = _get(
        "https://api.gbif.org/v1/species/match",
        params={"name": _TEST_FUNGUS, "strict": "true"},
    )
    assert 200 <= resp.status_code < 300, (
        f"GBIF returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )


def test_col_online():
    resp = _get(
        "https://api.catalogueoflife.org/nameusage/search",
        params={"q": _TEST_FUNGUS},
    )
    assert 200 <= resp.status_code < 300, (
        f"COL returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )


def test_genbank_online():
    resp = _get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={
            "db": "nucleotide",
            "term": f"{_TEST_FUNGUS}[Organism]",
            "retmode": "json",
            "retmax": 1,
        },
    )
    assert 200 <= resp.status_code < 300, (
        f"GenBank returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )
    assert "esearchresult" in resp.json(), (
        "GenBank response missing 'esearchresult' key"
    )


def test_index_fungorum_online():
    # The IsAlive endpoint is a built in health check for the Index Fungorum API that returns 200 if the service is up and running.
    resp = _get(
        "https://www.indexfungorum.org/ixfwebservice/fungus.asmx/IsAlive",
    )
    assert 200 <= resp.status_code < 300, (
        f"Index Fungorum returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )


def test_mushroom_observer_online():
    resp = _get(
        "https://mushroomobserver.org/api2/names",
        params={"name": _TEST_FUNGUS, "format": "json"},
        headers={"User-Agent": "Mozilla/5.0"},
    )
    assert 200 <= resp.status_code < 300, (
        f"Mushroom Observer returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )


def test_tropicos_online():
    api_key = os.getenv("TROPICOS_API_KEY")
    if not api_key:
        pytest.skip("TROPICOS_API_KEY not set — skipping Tropicos connectivity check")
    resp = _get(
        "http://services.tropicos.org/Name/Search",
        params={
            "name": _TEST_PLANT,
            "type": "exact",
            "apikey": api_key,
            "format": "json",
        },
    )
    assert 200 <= resp.status_code < 300, (
        f"Tropicos returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )


# ---------------------------------------------------------------------------
# Symbiota portals
# ---------------------------------------------------------------------------

_SYMBIOTA_PORTALS = [
    ("mycoportal", "https://mycoportal.org/portal"),
    ("lichen", "https://lichenportal.org/portal"),
    ("bryophyte", "https://bryophyteportal.org/portal"),
    ("cch2", "https://cch2.org/portal"),
    ("sernec", "https://sernecportal.org/portal"),
    ("nansh", "https://nansh.org/portal"),
    ("macroalgae", "https://macroalgae.org/portal"),
    ("pterido", "https://pteridoportal.org/portal"),
    ("neherbaria", "https://neherbaria.org/portal"),
    ("midatlantic", "https://midatlanticherbaria.org/portal"),
    ("swbiodiversity", "https://swbiodiversity.org/seinet"),
]


@pytest.mark.parametrize(
    "portal_id,base_url",
    _SYMBIOTA_PORTALS,
    ids=[p[0] for p in _SYMBIOTA_PORTALS],
)
def test_symbiota_portal_online(portal_id, base_url):
    resp = _get(
        f"{base_url}/api/v2/taxonomy/search",
        params={"taxon": _TEST_FUNGUS, "type": "EXACT", "limit": 1, "offset": 0},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    assert 200 <= resp.status_code < 300, (
        f"Symbiota {portal_id} returned HTTP {resp.status_code} ({_describe(resp.status_code)})"
    )
