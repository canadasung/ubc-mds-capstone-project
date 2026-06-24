"""
Tests for scripts/utils/call_apis_pipe.py

The _PORTAL_REGISTRY is patched so individual API clients are never instantiated
and no network calls are made.

Run from the project root:
    pytest tests/scripts/utils/test_call_apis_pipe.py -v
"""

from unittest.mock import MagicMock, patch

import pandas as pd

from scripts.utils.call_apis_pipe import call_apis
from scripts.utils.schema import SYNONYM_COLUMNS


def _make_api_df(*rows: dict) -> pd.DataFrame:
    """Build a minimal schema-format DataFrame from one or more row dicts."""
    return pd.DataFrame(rows, columns=SYNONYM_COLUMNS)


def _make_factory(df: pd.DataFrame) -> MagicMock:
    """Return a zero-arg callable whose instance's get_synonyms returns df."""
    instance = MagicMock()
    instance.get_synonyms.return_value = df
    factory = MagicMock(return_value=instance)
    return factory


_ROW_A = {col: ("GBIF" if col == "api_name" else "val") for col in SYNONYM_COLUMNS}
_ROW_B = {col: ("COL" if col == "api_name" else "val2") for col in SYNONYM_COLUMNS}


class TestCallApisBasic:
    def test_known_source_is_called(self):
        factory = _make_factory(_make_api_df(_ROW_A))
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", {"GBIF": factory}):
            result = call_apis("Amanita muscaria", ["GBIF"])
        factory.assert_called_once()
        factory.return_value.get_synonyms.assert_called_once_with("Amanita muscaria")
        assert len(result) == 1

    def test_unknown_source_is_skipped(self):
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", {}):
            result = call_apis("Amanita muscaria", ["NotAPortal"])
        assert result.empty
        assert list(result.columns) == SYNONYM_COLUMNS

    def test_empty_sources_returns_empty_table(self):
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", {}):
            result = call_apis("Amanita muscaria", [])
        assert result.empty
        assert list(result.columns) == SYNONYM_COLUMNS

    def test_all_apis_return_empty_returns_empty_table(self):
        factory = _make_factory(pd.DataFrame(columns=SYNONYM_COLUMNS))
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", {"GBIF": factory}):
            result = call_apis("Amanita muscaria", ["GBIF"])
        assert result.empty
        assert list(result.columns) == SYNONYM_COLUMNS


class TestCallApisMultipleSources:
    def test_results_from_multiple_sources_are_concatenated(self):
        factory_a = _make_factory(_make_api_df(_ROW_A))
        factory_b = _make_factory(_make_api_df(_ROW_B))
        registry = {"GBIF": factory_a, "COL": factory_b}
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", registry):
            result = call_apis("Amanita muscaria", ["GBIF", "COL"])
        assert len(result) == 2

    def test_known_and_unknown_sources_mixed(self):
        factory = _make_factory(_make_api_df(_ROW_A))
        registry = {"GBIF": factory}
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", registry):
            result = call_apis("Amanita muscaria", ["GBIF", "NotAPortal"])
        assert len(result) == 1

    def test_one_empty_one_nonempty_returns_nonempty(self):
        factory_empty = _make_factory(pd.DataFrame(columns=SYNONYM_COLUMNS))
        factory_data = _make_factory(_make_api_df(_ROW_A))
        registry = {"COL": factory_empty, "GBIF": factory_data}
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", registry):
            result = call_apis("Amanita muscaria", ["COL", "GBIF"])
        assert len(result) == 1

    def test_result_has_correct_columns(self):
        factory = _make_factory(_make_api_df(_ROW_A))
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", {"GBIF": factory}):
            result = call_apis("Amanita muscaria", ["GBIF"])
        assert list(result.columns) == SYNONYM_COLUMNS

    def test_index_is_reset_after_concat(self):
        factory_a = _make_factory(_make_api_df(_ROW_A))
        factory_b = _make_factory(_make_api_df(_ROW_B))
        registry = {"GBIF": factory_a, "COL": factory_b}
        with patch("scripts.utils.call_apis_pipe._PORTAL_REGISTRY", registry):
            result = call_apis("Amanita muscaria", ["GBIF", "COL"])
        assert list(result.index) == [0, 1]
