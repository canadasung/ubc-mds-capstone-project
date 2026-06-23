# Test Instructions

All commands are run from the **project root** directory.

## Overview

```
tests/
├── scripts/
│   ├── integration/
│   │   ├── test_env_configured.py   — verifies .env file and credentials
│   │   └── test_API_online.py       — live HTTP connectivity checks for all APIs
│   └── utils/
│       ├── test_call_apis_pipe.py   — unit tests for scripts/utils/call_apis_pipe.py
│       ├── test_fuzzy_search.py     — unit tests for scripts/utils/fuzzy_search.py
│       ├── test_normalize_query_string.py — unit tests for scripts/utils/normalize_query_string.py
│       ├── test_router.py           — unit tests for scripts/utils/router.py
│       └── test_schema.py           — unit tests for scripts/utils/schema.py
```

The `utils/` tests are **unit tests** — they mock all network calls and run offline. The `apis_pipe/` tests are also **unit tests**, but instead of synthetic mock data they replay saved real API responses captured from live calls; this keeps them offline while still exercising the actual response shapes each API returns. The `integration/` tests make real HTTP requests and require internet access and a configured `.env` file.

Two helper scripts will accompany the `apis_pipe/` tests:

- **`regenerate_fixtures.py`** — fetches a fresh set of real responses from every API and overwrites the saved fixture files. Run this when an API changes its response format. The newly saved responses must be **manually reviewed** before committing, since the tests will pass against whatever is saved.
- **`check_fixtures.py`** — fetches current live responses and compares them to the saved fixtures without overwriting anything. Run this to find out whether the saved fixtures are still accurate, i.e. whether `regenerate_fixtures.py` needs to be run.

---

## Run all tests

```bash
pytest tests/ -v
```

To exclude integration tests (offline-safe):

```bash
pytest tests/ -v -m "not integration"
```

---

## Run a folder of tests

**All unit tests:**

```bash
pytest tests/scripts/utils/ -v
```

**All integration tests:**

```bash
pytest tests/scripts/integration/ -v
```

---

## Run a single test file

```bash
pytest tests/scripts/utils/test_call_apis_pipe.py -v
pytest tests/scripts/utils/test_fuzzy_search.py -v
pytest tests/scripts/utils/test_normalize_query_string.py -v
pytest tests/scripts/utils/test_router.py -v
pytest tests/scripts/utils/test_schema.py -v
pytest tests/scripts/integration/test_env_configured.py -v
pytest tests/scripts/integration/test_API_online.py -v
```

---

## Run a single test class or test

```bash
# All tests in a class
pytest tests/scripts/utils/test_schema.py::TestMakeSynonymRowSuccess -v

# One specific test
pytest tests/scripts/utils/test_schema.py::TestMakeSynonymRowSuccess::test_minimal_required_fields -v
```

---

## Test file reference

### `tests/scripts/utils/test_call_apis_pipe.py`

Unit tests for `call_apis` in `scripts/utils/call_apis_pipe.py`. The internal portal registry is patched so no API clients are instantiated.

| Class | What it covers |
|---|---|
| `TestCallApisBasic` | Known source is called with the query; unknown sources are skipped; empty source list; all APIs returning empty |
| `TestCallApisMultipleSources` | Results from multiple sources are concatenated; mixed known/unknown sources; one empty + one non-empty source; correct output columns; index is reset after concat |

---

### `tests/scripts/utils/test_fuzzy_search.py`

Unit tests for `fuzzy_search` in `scripts/utils/fuzzy_search.py`. `requests.get` is patched to return controlled fake responses.

| Class | What it covers |
|---|---|
| `TestFuzzySearch` | Exact species match returns a single-item list; exact match only calls the `/match` endpoint; fuzzy match returns a single-item list; exact match at non-species rank falls through to `/suggest`; fuzzy match only calls the `/match` endpoint; suggest entries with null `canonicalName` are filtered; no match returns empty list; duplicate names from suggest are deduplicated |

---

### `tests/scripts/utils/test_normalize_query_string.py`

Unit tests for `normalize_query_string` in `scripts/utils/normalize_query_string.py`.

| Class | What it covers |
|---|---|
| `TestNormalizeQueryString` | All-lowercase input; all-uppercase input; mixed-case input; leading whitespace; trailing whitespace; internal extra spaces; tabs and mixed whitespace; already-normalized input; single-word genus; three-part name; three-part name with mixed case and extra whitespace |

---

### `tests/scripts/utils/test_router.py`

Unit tests for `TaxonRouter` in `scripts/utils/router.py`. `GBIFAPI` is patched via a pytest fixture so no network calls are made.

| Class | What it covers |
|---|---|
| `TestTaxonRouterRouting` | Animalia → Animalia API list; Plantae → Plantae API list; Fungi → Fungi API list; unrecognized kingdom → empty list |
| `TestTaxonRouterFailureCases` | Empty GBIF response → empty list; GBIF exception → empty list; null kingdom in response → empty list |
| `TestTaxonRouterApiLists` | GBIF present in Animalia and Plantae lists; Index Fungorum present in Fungi list; all three lists are non-empty |

---

### `tests/scripts/utils/test_schema.py`

Unit tests for `empty_synonym_table` and `make_synonym_row` in `scripts/utils/schema.py`.

| Class | What it covers |
|---|---|
| `TestEmptySynonymTable` | Returns a DataFrame with the correct columns; DataFrame is empty |
| `TestMakeSynonymRowSuccess` | Minimal required fields; optional fields default to `UNAVAILABLE`; all columns present; optional fields accepted; empty string for optional string/year fields; `Synonym` and `""` accepted for status; `""` and `http://` accepted for api_link |
| `TestMakeSynonymRowNoneGuard` | Passing `None` raises `TypeError` |
| `TestMakeSynonymRowUnavailableGuard` | Passing `UNAVAILABLE` explicitly raises `ValueError` |
| `TestMakeSynonymRowRequiredFields` | Each of the four required fields raises `ValueError` when missing or empty |
| `TestValidateApiName` | Invalid name raises `ValueError`; all known valid names accepted |
| `TestValidatePublicationYear` | Valid 4-digit year accepted; non-numeric, 3-digit, and 5-digit values raise `ValueError` |
| `TestValidateApiLink` | `https://` accepted; no-protocol and `ftp://` raise `ValueError` |
| `TestValidateStatus` | Invalid status string raises `ValueError` |
| `TestValidateTaxonColumns` | Taxon value with whitespace raises `ValueError`; single-word value accepted |
| `TestValidateStringColumns` | Non-string values for `author` and `api_internal_id` raise `ValueError` |

---

### `tests/scripts/integration/test_env_configured.py`

Verifies that `.env` exists at the project root and that `ENTREZ_EMAIL` and `TROPICOS_API_KEY` are set to real (non-placeholder) values. Run this before `test_API_online.py` to confirm credentials are in place.

**Requires:** A `.env` file copied from `.env.example` with real values filled in.

**Relationship to `conftest.py` fixtures:** `conftest.py` defines `require_entrez_email` and `require_tropicos_api_key` fixtures that also check these credentials, but they serve a different purpose. Those fixtures are *guards* — they protect individual tests that need a credential, skipping or failing only that test when the credential is missing. `test_env_configured.py` is a *diagnostic* — it checks things the fixtures don't, including whether the `.env` file exists at all and whether `ENTREZ_EMAIL` is a validly formatted address. If you skip this file, a missing `.env` will produce a wall of unexplained skips or failures across the suite; running this file first surfaces the root cause immediately.

---

### `tests/scripts/integration/test_API_online.py`

Live connectivity checks that make real HTTP requests to each API. Each test sends a minimal query and asserts a 2xx response. Tests are parametrized over all 11 Symbiota portals.

**Requires:** Internet access. `test_tropicos_online` additionally requires `TROPICOS_API_KEY` to be set in `.env` (skipped otherwise).

| Test | API checked |
|---|---|
| `test_gbif_online` | GBIF species match endpoint |
| `test_col_online` | Catalogue of Life name search endpoint |
| `test_genbank_online` | NCBI GenBank Entrez esearch endpoint |
| `test_index_fungorum_online` | Index Fungorum `IsAlive` health check |
| `test_mushroom_observer_online` | Mushroom Observer names endpoint |
| `test_tropicos_online` | Tropicos name search endpoint |
| `test_symbiota_portal_online[*]` | All 11 Symbiota portals (parametrized) |
