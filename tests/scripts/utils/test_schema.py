"""
Tests for scripts/utils/schema.py

Covers empty_synonym_table and make_synonym_row, including all validators,
required-field enforcement, and the None/UNAVAILABLE guards.

Run from the project root:
    pytest tests/scripts/utils/test_schema.py -v
"""

import pytest

from scripts.utils.schema import (
    SYNONYM_COLUMNS,
    UNAVAILABLE,
    empty_synonym_table,
    make_synonym_row,
)

# Minimal set of required kwargs for a valid row
_REQUIRED = {
    "api_name": "GBIF",
    "genus": "Amanita",
    "species": "muscaria",
    "api_internal_id": "12345",
}


class TestEmptySynonymTable:
    def test_returns_dataframe_with_correct_columns(self):
        import pandas as pd

        df = empty_synonym_table()
        assert list(df.columns) == SYNONYM_COLUMNS
        assert isinstance(df, pd.DataFrame)

    def test_returns_empty_dataframe(self):
        df = empty_synonym_table()
        assert len(df) == 0


class TestMakeSynonymRowSuccess:
    def test_minimal_required_fields(self):
        row = make_synonym_row(**_REQUIRED)
        assert row["api_name"] == "GBIF"
        assert row["genus"] == "Amanita"
        assert row["species"] == "muscaria"
        assert row["api_internal_id"] == "12345"

    def test_missing_optional_fields_default_to_unavailable(self):
        row = make_synonym_row(**_REQUIRED)
        optional_cols = [c for c in SYNONYM_COLUMNS if c not in _REQUIRED]
        for col in optional_cols:
            assert row[col] == UNAVAILABLE, f"Expected {col!r} to default to UNAVAILABLE"

    def test_all_columns_present_in_output(self):
        row = make_synonym_row(**_REQUIRED)
        assert set(row.keys()) == set(SYNONYM_COLUMNS)

    def test_optional_fields_accepted(self):
        row = make_synonym_row(
            **_REQUIRED,
            kingdom="Fungi",
            publication_year="1898",
            api_link="https://example.com",
            status="Accepted",
        )
        assert row["kingdom"] == "Fungi"
        assert row["publication_year"] == "1898"
        assert row["api_link"] == "https://example.com"
        assert row["status"] == "Accepted"

    def test_empty_string_accepted_for_optional_string_field(self):
        row = make_synonym_row(**_REQUIRED, author="")
        assert row["author"] == ""

    def test_empty_string_accepted_for_publication_year(self):
        row = make_synonym_row(**_REQUIRED, publication_year="")
        assert row["publication_year"] == ""

    def test_status_synonym_accepted(self):
        row = make_synonym_row(**_REQUIRED, status="Synonym")
        assert row["status"] == "Synonym"

    def test_status_empty_string_accepted(self):
        row = make_synonym_row(**_REQUIRED, status="")
        assert row["status"] == ""

    def test_api_link_empty_string_accepted(self):
        row = make_synonym_row(**_REQUIRED, api_link="")
        assert row["api_link"] == ""

    def test_api_link_http_accepted(self):
        row = make_synonym_row(**_REQUIRED, api_link="http://example.com")
        assert row["api_link"] == "http://example.com"


class TestMakeSynonymRowNoneGuard:
    def test_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Got None for"):
            make_synonym_row(**_REQUIRED, author=None)


class TestMakeSynonymRowUnavailableGuard:
    def test_explicit_unavailable_raises_value_error(self):
        with pytest.raises(ValueError, match="Do not pass"):
            make_synonym_row(**_REQUIRED, author=UNAVAILABLE)


class TestMakeSynonymRowRequiredFields:
    def test_missing_api_name_raises(self):
        kwargs = {k: v for k, v in _REQUIRED.items() if k != "api_name"}
        with pytest.raises(ValueError, match="Missing required columns"):
            make_synonym_row(**kwargs)

    def test_missing_genus_raises(self):
        kwargs = {k: v for k, v in _REQUIRED.items() if k != "genus"}
        with pytest.raises(ValueError, match="Missing required columns"):
            make_synonym_row(**kwargs)

    def test_missing_species_raises(self):
        kwargs = {k: v for k, v in _REQUIRED.items() if k != "species"}
        with pytest.raises(ValueError, match="Missing required columns"):
            make_synonym_row(**kwargs)

    def test_missing_api_internal_id_raises(self):
        kwargs = {k: v for k, v in _REQUIRED.items() if k != "api_internal_id"}
        with pytest.raises(ValueError, match="Missing required columns"):
            make_synonym_row(**kwargs)

    def test_empty_string_for_required_field_raises(self):
        with pytest.raises(ValueError, match="Missing required columns"):
            make_synonym_row(**{**_REQUIRED, "genus": ""})


class TestValidateApiName:
    def test_invalid_api_name_raises(self):
        with pytest.raises(ValueError, match="api_name"):
            make_synonym_row(**{**_REQUIRED, "api_name": "NotAnAPI"})

    def test_valid_api_names_accepted(self):
        for name in ("GBIF", "COL", "ITIS", "FishBase", "MyCoPortal"):
            row = make_synonym_row(**{**_REQUIRED, "api_name": name})
            assert row["api_name"] == name


class TestValidatePublicationYear:
    def test_four_digit_year_accepted(self):
        row = make_synonym_row(**_REQUIRED, publication_year="1901")
        assert row["publication_year"] == "1901"

    def test_non_numeric_year_raises(self):
        with pytest.raises(ValueError, match="publication_year"):
            make_synonym_row(**_REQUIRED, publication_year="19ab")

    def test_three_digit_year_raises(self):
        with pytest.raises(ValueError, match="publication_year"):
            make_synonym_row(**_REQUIRED, publication_year="199")

    def test_five_digit_year_raises(self):
        with pytest.raises(ValueError, match="publication_year"):
            make_synonym_row(**_REQUIRED, publication_year="19999")


class TestValidateApiLink:
    def test_https_link_accepted(self):
        row = make_synonym_row(**_REQUIRED, api_link="https://gbif.org/species/1")
        assert row["api_link"] == "https://gbif.org/species/1"

    def test_no_protocol_raises(self):
        with pytest.raises(ValueError, match="api_link"):
            make_synonym_row(**_REQUIRED, api_link="gbif.org/species/1")

    def test_ftp_raises(self):
        with pytest.raises(ValueError, match="api_link"):
            make_synonym_row(**_REQUIRED, api_link="ftp://example.com")


class TestValidateStatus:
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="status"):
            make_synonym_row(**_REQUIRED, status="Invalid")


class TestValidateTaxonColumns:
    def test_taxon_with_whitespace_raises(self):
        with pytest.raises(ValueError, match="kingdom"):
            make_synonym_row(**_REQUIRED, kingdom="two words")

    def test_valid_single_word_taxon_accepted(self):
        row = make_synonym_row(**_REQUIRED, kingdom="Fungi")
        assert row["kingdom"] == "Fungi"


class TestValidateStringColumns:
    def test_non_string_author_raises(self):
        with pytest.raises(ValueError, match="author"):
            make_synonym_row(**_REQUIRED, author=42)

    def test_non_string_api_internal_id_raises(self):
        with pytest.raises(ValueError, match="api_internal_id"):
            make_synonym_row(
                api_name="GBIF",
                genus="Amanita",
                species="muscaria",
                api_internal_id=99,
            )
