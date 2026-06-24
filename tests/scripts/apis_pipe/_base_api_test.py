"""
Abstract base test class for apis_pipe API clients.

Not collected by pytest directly (no 'Test' prefix). Each per-API test file
defines a 'Test<Name>' class that inherits BaseApiTest and overrides the
class variables below. pytest then collects the inherited test methods from
each subclass.

Fixture loading:
  Fixtures are loaded from tests/fixtures/<fixture_key>/<scenario>/<stem>.<ext>.
  Tests patch _fetch_query_data, _fetch_synonym_data, and _fetch_accepted_data
  directly on the client instance so that get_synonyms() exercises the real
  _compile_* methods against saved real-API response shapes, with no network
  calls.

API-specific overrides:
  Tropicos — override _run to also patch _fetch_accepted_list (custom orchestrator).
  ITIS     — override _run to also patch _fetch_hierarchy_data and, for the
             synonym scenario, _fetch_internal_accepted_id_data (custom orchestrator).
  Mushroom Observer — override test_accepted_and_synonym_produce_same_accepted_row
             with @pytest.mark.xfail (known symmetry bug).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.utils.schema import SYNONYM_COLUMNS, UNAVAILABLE
from tests.fixtures._fetchers import FIXTURES_DIR, deserialize
from tests.fixtures.queries import API_QUERIES


class BaseApiTest:
    api_class: type
    fixture_key: str

    expected_accepted_genus: str
    expected_accepted_species: str

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _queries(self) -> dict[str, str]:
        return API_QUERIES[self.fixture_key]

    def _load(self, scenario: str, stem: str) -> Any:
        base = FIXTURES_DIR / self.fixture_key / scenario
        for ext in ("json", "xml", "html"):
            p = base / f"{stem}.{ext}"
            if p.exists():
                return deserialize(p.read_text(encoding="utf-8"), ext)
        raise FileNotFoundError(
            f"No fixture file found for {self.fixture_key}/{scenario}/{stem}.*"
        )

    def _load_or_none(self, scenario: str, stem: str) -> Any:
        try:
            return self._load(scenario, stem)
        except FileNotFoundError:
            return None

    def _make_client(self):
        return self.api_class()

    def _run(self, scenario: str) -> pd.DataFrame:
        """Run get_synonyms with the three standard fetch methods patched."""
        client = self._make_client()
        query_data = self._load(scenario, "query_data")
        synonym_data = self._load_or_none(scenario, "synonym_data")
        accepted_data = self._load_or_none(scenario, "accepted_data")
        with (
            patch.object(client, "_fetch_query_data", return_value=query_data),
            patch.object(client, "_fetch_synonym_data", return_value=synonym_data),
            patch.object(client, "_fetch_accepted_data", return_value=accepted_data),
        ):
            return client.get_synonyms(self._queries()[scenario])

    # ------------------------------------------------------------------
    # Template tests
    # ------------------------------------------------------------------

    def test_not_found_returns_empty_dataframe(self):
        df = self._run("not_found")
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert list(df.columns) == SYNONYM_COLUMNS

    def test_accepted_dataframe_has_correct_columns(self):
        df = self._run("accepted")
        assert list(df.columns) == SYNONYM_COLUMNS

    def test_accepted_result_has_accepted_row(self):
        df = self._run("accepted")
        assert (df["status"] == "Accepted").any(), (
            "Expected at least one row with status='Accepted' in the accepted scenario"
        )

    def test_synonym_result_has_accepted_row(self):
        df = self._run("synonym")
        assert (df["status"] == "Accepted").any(), (
            "Expected at least one row with status='Accepted' in the synonym scenario"
        )

    def test_accepted_and_synonym_produce_same_accepted_row(self):
        accepted_df = self._run("accepted")
        synonym_df = self._run("synonym")
        acc_row = accepted_df[accepted_df["status"] == "Accepted"].iloc[0]
        syn_row = synonym_df[synonym_df["status"] == "Accepted"].iloc[0]
        assert acc_row["genus"] == syn_row["genus"], (
            f"Accepted genus mismatch: {acc_row['genus']!r} vs {syn_row['genus']!r}"
        )
        assert acc_row["species"] == syn_row["species"], (
            f"Accepted species mismatch: {acc_row['species']!r} vs {syn_row['species']!r}"
        )

    def test_no_duplicate_rows(self):
        # Rows are duplicate if all columns except api_internal_id and api_link are equal.
        _identity_cols = [c for c in SYNONYM_COLUMNS if c not in ("api_internal_id", "api_link")]
        for scenario in ("accepted", "synonym"):
            df = self._run(scenario)
            if df.empty:
                continue
            dupes = df.duplicated(subset=_identity_cols, keep=False)
            assert not dupes.any(), (
                f"Duplicate rows found in {scenario!r} scenario "
                f"(ignoring api_internal_id and api_link):\n{df[dupes]}"
            )

    def test_required_fields_are_populated(self):
        df = self._run("accepted")
        for col in ("api_name", "genus", "species", "api_internal_id"):
            assert (df[col] != UNAVAILABLE).all(), (
                f"Column '{col}' contains UNAVAILABLE in the accepted scenario"
            )
