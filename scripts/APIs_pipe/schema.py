import re

import pandas as pd

SYNONYM_COLUMNS = [
    "Source Name",
    "Kingdom",
    "Phylum",
    "Class",
    "Family",
    "Subfamily",
    "Genus",
    "Species",
    "Source Species ID",
    "Author",
    "Publication Name",
    "Publication Year",
    "Source Link",
    "GBIF Accepted Status",
]

UNAVAILABLE = "U"

_GBIF_STATUS_VALUES = {"Accepted", "Synonym", UNAVAILABLE}

_SINGLE_WORD_COLUMNS = {
    "Kingdom",
    "Phylum",
    "Class",
    "Family",
    "Subfamily",
    "Genus",
    "Species",
}
_STRING_COLUMNS = {"Source Species ID", "Author", "Publication Name"}


def _make_string_validator(col: str):
    def validate(v) -> None:
        if not isinstance(v, str):
            raise ValueError(f"'{col}' must be a string, got {v!r}")

    return validate


def _make_single_word_validator(col: str):
    def validate(v: str) -> None:
        if not isinstance(v, str) or (v != UNAVAILABLE and re.search(r"\s", v)):
            raise ValueError(
                f"'{col}' must be a single word (no whitespace) or {UNAVAILABLE!r}, got {v!r}"
            )

    return validate


def _validate_source_name(v: str) -> None:
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"'Source Name' must be a non-empty string, got {v!r}")


def _validate_publication_year(v: str) -> None:
    if v != UNAVAILABLE and not re.fullmatch(r"\d{4}", v):
        raise ValueError(
            f"'Publication Year' must be a 4-digit year string or {UNAVAILABLE!r}, got {v!r}"
        )


def _validate_source_link(v: str) -> None:
    if v != UNAVAILABLE and not re.match(r"https?://", v):
        raise ValueError(
            f"'Source Link' must start with 'http://' or 'https://', or be {UNAVAILABLE!r}, got {v!r}"
        )


def _validate_gbif_status(v: str) -> None:
    if v not in _GBIF_STATUS_VALUES:
        raise ValueError(
            f"'GBIF Accepted Status' must be one of {_GBIF_STATUS_VALUES}, got {v!r}"
        )


_VALIDATORS = {
    "Source Name": _validate_source_name,
    "Publication Year": _validate_publication_year,
    "Source Link": _validate_source_link,
    "GBIF Accepted Status": _validate_gbif_status,
    **{col: _make_single_word_validator(col) for col in _SINGLE_WORD_COLUMNS},
    **{col: _make_string_validator(col) for col in _STRING_COLUMNS},
}


def empty_synonym_table() -> pd.DataFrame:
    return pd.DataFrame(columns=SYNONYM_COLUMNS)


def make_synonym_row(**kwargs) -> dict:
    row = {col: kwargs.get(col, UNAVAILABLE) for col in SYNONYM_COLUMNS}
    for col, validate in _VALIDATORS.items():
        validate(row[col])
    return row
