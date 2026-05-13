def normalize_query_string(query: str) -> str:
    """Normalize a species name query string.

    Steps: strip leading/trailing whitespace, collapse internal whitespace
    (including tabs), lowercase everything, then capitalize the first letter.

    Args:
        query: Raw species name string, e.g. from user input.

    Returns:
        Normalized species name string.

    Examples:
        >>> normalize_query_string("amanita muscaria")
        'Amanita muscaria'
        >>> normalize_query_string(" AMANITA  MUSCARIA")
        'Amanita muscaria'
    """
    normalized = " ".join(query.split())
    return normalized.lower().capitalize()
