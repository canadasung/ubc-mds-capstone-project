#!/usr/bin/env python3
"""
check_fixtures.py — Compare live API responses to saved fixture files.

Run from the project root:
    python tests/fixtures/check_fixtures.py

Prints OK or CHANGED for each fixture file. Never modifies any files.
Run regenerate_fixtures.py to update stale fixtures.

Requires internet access and a configured .env file (same as regenerate_fixtures.py).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from tests.fixtures._fetchers import ALL_FETCHERS, FIXTURES_DIR, serialize  # noqa: E402

_ok = 0
_changed: list[str] = []
_missing: list[str] = []


def _check(path: Path, data: object) -> None:
    rel = str(path.relative_to(FIXTURES_DIR))
    if not path.exists():
        print(f"  {rel:<70}  MISSING")
        _missing.append(rel)
        return
    current = serialize(data)
    saved = path.read_text(encoding="utf-8")
    if current == saved:
        print(f"  {rel:<70}  OK")
        global _ok
        _ok += 1
    else:
        print(f"  {rel:<70}  CHANGED")
        _changed.append(rel)


def main() -> None:
    for api_name, fetcher_fn in ALL_FETCHERS:
        print(f"\n[{api_name}]")
        if api_name == "FishBase":
            print("  (HTML scrape — volatile server-side fields may cause spurious CHANGED results)")
        try:
            for path, data in fetcher_fn():
                _check(path, data)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print("\n" + "=" * 60)
    total = _ok + len(_changed) + len(_missing)
    print(
        f"Results: {_ok} OK, {len(_changed)} CHANGED, {len(_missing)} MISSING  (of {total} checked)"
    )
    print(
        "NOTE: FishBase fixtures are HTML scrapes. Volatile server-side fields "
        "(mirrors, processing time) are normalized, but residual changes are expected. "
        "Verify FishBase output manually rather than relying on fixture diffs."
    )

    if _changed:
        print("\nChanged fixtures (run regenerate_fixtures.py to update):")
        for f in _changed:
            print(f"  {f}")

    if _missing:
        print("\nMissing fixtures (run regenerate_fixtures.py to create):")
        for f in _missing:
            print(f"  {f}")


if __name__ == "__main__":
    main()
