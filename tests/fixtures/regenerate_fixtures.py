#!/usr/bin/env python3
"""
regenerate_fixtures.py — Fetch real API responses and save them as fixture files.

Run from the project root:
    python tests/fixtures/regenerate_fixtures.py

Fixtures capture the return values of each API client's _fetch_query_data,
_fetch_synonym_data, and _fetch_accepted_data methods so that unit tests can
patch those methods directly and replay offline.

After running, MANUALLY REVIEW all changed fixture files before committing.
Verify that the get_synonyms() output for each test query is still correct.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from tests.fixtures._fetchers import ALL_FETCHERS, FIXTURES_DIR, serialize  # noqa: E402

_changed: list[str] = []


def _save(path: Path, data: object) -> None:
    content = serialize(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    _changed.append(str(path.relative_to(FIXTURES_DIR)))


def main() -> None:
    for api_name, fetcher_fn in ALL_FETCHERS:
        print(f"\n[{api_name}]")
        try:
            for path, data in fetcher_fn():
                _save(path, data)
                print(f"  {path.relative_to(FIXTURES_DIR)}")
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print("\n" + "=" * 60)
    if _changed:
        print(f"Changed ({len(_changed)} files):")
        for f in _changed:
            print(f"  {f}")
        print()
        print("WARNING: Review all changed fixtures before committing.")
        print("  Verify that get_synonyms() output for each test query is correct.")
    else:
        print("No changes — all fixtures are already up to date.")


if __name__ == "__main__":
    main()
