# Test Instructions

Run all commands from the **project root**.

## Layout

```
tests/
├── fixtures/            — saved API responses + scripts to refresh them
├── scripts/
│   ├── apis_pipe/       — per-API client unit tests (replay saved fixtures, offline)
│   │   └── test_symbiota/   — one test file per Symbiota portal (11 portals)
│   └── utils/           — utility unit tests (mocked network, offline)
└── integration/         — live tests that make real HTTP calls (need internet + .env)
```

- **Unit tests** (`tests/scripts/`) run offline. The `apis_pipe/` tests replay saved
  fixture responses; the `utils/` tests mock the network.
- **Integration tests** (`tests/integration/`) hit real APIs and require internet and a
  configured `.env`. They are marked `@pytest.mark.integration`.
- `tests/integration/test_base_fetch.py` is mixed: its mocked cases run offline, its
  live cases are `integration`-marked. Use the `-m` selector below to pick the level.

### Symbiota portals

Symbiota is one `SymbiotaAPI` class serving 11 portals. Each portal gets its own file
in `apis_pipe/test_symbiota/` (e.g. `test_mycoportal.py`), all subclassing the shared
`_symbiota_api_test.py` base, which sets the portal name, queries, and fixture path.
Per-portal queries live in `SYMBIOTA_QUERIES` in `tests/fixtures/queries.py`; fixtures
are under `tests/fixtures/symbiota/<slug>/<scenario>/`. The scraped `synonym_data.html`
fixture is reduced to just the stable `synonymDiv` slice (the only part the parser
reads) so the otherwise non-deterministic taxa page doesn't cause fixture churn.

## Run tests at different fidelity

```bash
pytest tests/                          # everything (needs internet)
pytest tests/ -m "not integration"     # offline only — fast, no network/credentials
pytest tests/ -m integration           # only the live network tests
pytest tests/ -v                        # add -v for per-test output
```

## Narrow the scope

```bash
pytest tests/scripts/                                   # a folder
pytest tests/scripts/apis_pipe/test_symbiota/           # all 11 Symbiota portals
pytest tests/scripts/apis_pipe/test_gbif.py             # a single file
pytest tests/scripts/utils/test_schema.py::TestValidateApiLink          # a class
pytest tests/scripts/utils/test_schema.py::TestValidateApiLink::test_https_link_accepted  # one test
pytest tests/ -k author                                 # by keyword match across files
```

## Fixtures

The `apis_pipe/` unit tests replay saved responses so they run offline. Both scripts
below need internet (and `.env`); Tropicos is skipped without `TROPICOS_API_KEY`.

```bash
python tests/fixtures/check_fixtures.py        # report drift (OK / CHANGED / MISSING), never writes
python tests/fixtures/regenerate_fixtures.py   # overwrite fixtures with fresh responses
```

After regenerating, **manually review** every changed file before committing — the tests
pass against whatever is saved.
