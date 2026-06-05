def normalize_scientific_name(name: str) -> str:
    """Normalize a scientific name string.

    Steps: strip leading/trailing whitespace, collapse internal whitespace
    (including tabs), lowercase everything, then capitalize the first letter.

    Args:
        name: Two word string representing a species name, with the first word representing the Genus and the second word representing the Species.

    Returns:
        Normalized species name string in the format "Genus species".

    Examples:
        >>> normalize_scientific_name("amanita muscaria")
        'Amanita muscaria'
        >>> normalize_scientific_name(" AMANITA  MUSCARIA")
        'Amanita muscaria'
    """
    # TODO: add remove punctuation??
    normalized = " ".join(name.split())
    return normalized.lower().capitalize()
