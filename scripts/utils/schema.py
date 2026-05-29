import re

import pandas as pd

SYNONYM_COLUMNS = [
    "api_name",  # name of API source that provided the data, e.g. GBIF (required)
    "kingdom",  # taxonomic kingdom (optional)
    "phylum",  # taxonomic phylum (optional)
    "class",  # taxonomic class (optional)
    "family",  # taxonomic family (optional)
    "subfamily",  # taxonomic subfamily (optional)
    "genus",  # taxonomic genus (required)
    "species",  # taxonomic species (required)
    "author",  # author of the taxonomic name (optional)
    "publication_name",  # name of the publication where the taxonomic name was published (optional)
    "publication_year",  # year when the taxonomic name was published (optional)
    "status",  # status of the taxonomic name in the API source's database, either "Accepted" or "Synonym" (optional)
    "source_name",  # name of the source that provided the data to the API source, e.g. a cited journal article, museum collection, etc. (optional)
    "api_link",  # link to the search result on the API source's website (optional)
    "api_internal_id",  # unique identifier for the record of this taxonomic name in the API source's database (required)
]
# value to use when data is unavailable (i.e. never present) from a given API source. This is not the same as an empty string, which indicates that the data was not found for that particular query (e.g. no author for a given taxonomic name).
UNAVAILABLE = "U"

# valid values for the "status" column, including UNAVAILABLE to indicate that the API source does not provide this information
_STATUS_VALUES = {
    "Accepted",
    "Synonym",
    UNAVAILABLE,
}

# columns that represent taxonomic ranks and must be single words (no whitespace) or UNAVAILABLE
_TAXON_COLUMNS = {
    "kingdom",
    "phylum",
    "class",
    "family",
    "subfamily",
    "genus",
    "species",
}

# columns that must be strings (can be empty or UNAVAILABLE, but not other types)
_STRING_COLUMNS = {
    "api_internal_id",
    "source_name",
    "author",
    "publication_name",
}

# columns that must be explicitly provided (cannot be UNAVAILABLE)
_REQUIRED_COLUMNS = {
    "api_name",
    "genus",
    "species",
    "api_internal_id",
}

_API_NAMES = {
    "GBIF",
    "COL",  # Catalogue of Life
    "Tropicos",
    "Index Fungorum",
    "GenBank",
    "Mushroom Observer",  # (prev. "mushroomobs")
    # Symbiota Portals
    "MyCoPortal",  # Mycology Collections Portal
    "Lichen Portal",  # Consortium of Lichen Herbaria
    "Bryophyte Portal",  # Consortium of Bryophyte Herbaria
    "CCH2",  # Consortium of California Herbaria
    "SERNEC",  # Southeast Regional Network of Expertise and Collections
    "NANSH",  # North American Network of Small Herbaria
    "swbiodiversity",  # SEINet New Mexico-Arizona Chapter
    "Algae Herbarium Portal",  # (prev. macroalgae)
    "Pterido Portal",  # Pteridophyte Collections Consortium
    "CNH",  # Consortium of Northeastern Herbaria (prev. "neherbaria")
    "Mid-Atlantic Herbaria Consortium",  # (prev. "midatlantic")
}


def _make_string_validator(col: str):
    """
    Create a validator function that checks if a value is a string.

    Parameters
    ----------
    col : str
        Column name, used in the error message.

    Returns
    -------
    callable
        Validator that raises ``ValueError`` if the value is not a string.
    """

    def validate(v) -> None:
        if not isinstance(v, str):
            raise ValueError(f"'{col}' must be a string, got {v!r}")

    return validate


def _make_taxon_validator(col: str):
    """
    Create a validator function that checks if a value is a single word or ``UNAVAILABLE``. All taxon entries must be a single word (no whitespace) or ``UNAVAILABLE``.

    Parameters
    ----------
    col : str
        Column name, used in the error message.

    Returns
    -------
    callable
        Validator that raises ``ValueError`` if the value is not a string, contains
        whitespace, or is not equal to ``UNAVAILABLE``.
    """

    def validate(v: str) -> None:
        if not isinstance(v, str) or (v != UNAVAILABLE and re.search(r"\s", v)):
            raise ValueError(
                f"'{col}' must be a single word (no whitespace) or {UNAVAILABLE!r}, got {v!r}"
            )

    return validate


def _validate_api_name(v: str) -> None:
    """
    Validate that an api name is one of the allowed values in ``_API_NAMES``.

    Parameters
    ----------
    v : str
        Value to validate.

    Raises
    ------
    ValueError
        If ``v`` is not in ``_API_NAMES``.
    """
    if v not in _API_NAMES:
        raise ValueError(f"'api_name' must be one of {_API_NAMES!r}, got {v!r}")


def _validate_publication_year(v: str) -> None:
    """
    Validate that a publication year is a 4-digit string or ``UNAVAILABLE``.

    Parameters
    ----------
    v : str
        Value to validate.

    Raises
    ------
    ValueError
        If ``v`` is not a 4-digit string and is not equal to ``UNAVAILABLE``.
    """
    if v != UNAVAILABLE and not re.fullmatch(r"\d{4}", v):
        raise ValueError(
            f"'publication_year' must be a 4-digit year string or {UNAVAILABLE!r}, got {v!r}"
        )


def _validate_api_link(v: str) -> None:
    """
    Validate that an api link starts with ``http://`` or ``https://``, or is ``UNAVAILABLE``.

    Parameters
    ----------
    v : str
        Value to validate.

    Raises
    ------
    ValueError
        If ``v`` does not start with ``http://`` or ``https://`` and is not equal to ``UNAVAILABLE``.
    """
    if v != UNAVAILABLE and not re.match(r"https?://", v):
        raise ValueError(
            f"'api_link' must start with 'http://' or 'https://', or be {UNAVAILABLE!r}, got {v!r}"
        )


def _validate_status(v: str) -> None:
    """
    Validate that a status value is one of the allowed values in ``_STATUS_VALUES``.

    Parameters
    ----------
    v : str
        Value to validate.

    Raises
    ------
    ValueError
        If ``v`` is not in ``_STATUS_VALUES``.
    """
    if v not in _STATUS_VALUES:
        raise ValueError(f"'status' must be one of {_STATUS_VALUES}, got {v!r}")


# mapping of column name to validator function for validating synonym row values. All columns have validators, but some share the same validator (e.g. all taxon columns use the same taxon validator factory).
_VALIDATORS = {
    "api_name": _validate_api_name,
    "publication_year": _validate_publication_year,
    "api_link": _validate_api_link,
    "status": _validate_status,
    **{col: _make_taxon_validator(col) for col in _TAXON_COLUMNS},
    **{col: _make_string_validator(col) for col in _STRING_COLUMNS},
}


def empty_synonym_table() -> pd.DataFrame:
    """
    Create an empty DataFrame with the synonym table columns.

    Returns
    -------
    pd.DataFrame
        Empty DataFrame with columns defined by ``SYNONYM_COLUMNS``.
    """
    return pd.DataFrame(columns=SYNONYM_COLUMNS)


def make_synonym_row(**kwargs) -> dict:
    """
    Build a validated synonym row dict with all columns from ``SYNONYM_COLUMNS``.

    Any column not provided in ``kwargs`` defaults to ``UNAVAILABLE``. Required
    columns (``_REQUIRED_COLUMNS``) must be explicitly provided and cannot be
    ``UNAVAILABLE``. All values are validated against ``_VALIDATORS`` before the
    row is returned.

    Parameters
    ----------
    **kwargs
        Column values keyed by column name. Valid keys are those in ``SYNONYM_COLUMNS``.

    Returns
    -------
    dict
        Mapping of column name to value for all columns in ``SYNONYM_COLUMNS``.

    Raises
    ------
    ValueError
        If a required column is missing or set to ``UNAVAILABLE``, or if any
        column value fails its validator.
    """
    row = {col: kwargs.get(col, UNAVAILABLE) for col in SYNONYM_COLUMNS}
    missing = [col for col in _REQUIRED_COLUMNS if row[col] == UNAVAILABLE]
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    for col, validate in _VALIDATORS.items():
        validate(row[col])
    return row
