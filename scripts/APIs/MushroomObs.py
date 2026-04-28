import requests

BASE_URL = "https://mushroomobserver.org/api2"

def get_mushroom_observer_synonyms(species_name: str) -> list[str]:
    """
    Given a species name, returns a deduplicated list of non-misspelled synonyms
    from MushroomObserver.
    """
    resp = requests.get(
        f"{BASE_URL}/names",
        params={"name": species_name, "format": "json", "detail": "high"}
    )
    resp.raise_for_status()
    data = resp.json()

    if data.get("number_of_records", 0) == 0:
        raise ValueError(f"No MushroomObserver name found for '{species_name}'")

    synonyms = list(dict.fromkeys(
        s["name"]
        for result in data.get("results", [])
        for s in result.get("synonyms", [])
        if not s.get("misspelled", False)
    ))
    return synonyms


if __name__ == "__main__":
    result = get_mushroom_observer_synonyms("Amanita muscaria")
    print(f"Found {len(result)} synonyms:")
    for s in result:
        print(f"  {s}")
