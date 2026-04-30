"""
AntWeb.py — AntWeb Taxonomy API client
 
Queries the AntWeb v3.1 Taxa API to retrieve species synonyms from the
AntWeb taxonomy database (ant-specific).
 
Main entry point: get_antweb_synonyms(query)
"""
 
import requests
 
ANTWEB_BASE = "https://antweb.org/v3.1"
HEADERS = {"User-Agent": "Mozilla/5.0 (species-synonym-research-tool)"}
 
 
def main():
    import json
 
    result = get_antweb_synonyms("Camponotus herculeanus")
    print(json.dumps(result, indent=2))
 
 
def _species_name_to_taxon_name(species_name: str) -> str:
    """
    Convert a normal species name to AntWeb's taxonName format.
 
    AntWeb taxonName concatenates subfamily + genus + species with no separators,
    all lowercase. Since we don't know the subfamily upfront, we first do a
    genus-level lookup to find it.
 
    Parameters:
        species_name (str): e.g. "Camponotus herculeanus"
 
    Returns:
        str: AntWeb taxonName e.g. "formicinaecamponotusherculeanus",
             or empty string if the genus can't be resolved.
    """
    parts = species_name.lower().split()
    if len(parts) < 2:
        return ""
 
    genus = parts[0]
 
    # Look up the genus to find its subfamily
    resp = requests.get(
        f"{ANTWEB_BASE}/taxa",
        params={"genus": genus, "rank": "genus"},
    )
    resp.raise_for_status()
    taxa = resp.json().get("taxon", [])
 
    if not taxa:
        return ""
 
    subfamily = taxa[0].get("subfamily", "").lower().replace(" ", "")
    if not subfamily:
        return ""
 
    return subfamily + "".join(parts)
 
 
def get_antweb_synonyms(species_name: str) -> dict:
    """
    Given a species name, returns a dict of species-level synonym names from AntWeb.
 
    Keys are the queried species name and all AntWeb synonyms.
    Values are empty lists (placeholders for rank categories to be added).
    Returns an empty dict if no match is found or species is not an ant.
 
    Example:
        {"Camponotus herculeanus": [], "Formica herculanea": []}
    """
    taxon_name = _species_name_to_taxon_name(species_name)
    if not taxon_name:
        return {}
 
    resp = requests.get(
        f"{ANTWEB_BASE}/taxa",
        params={"taxonName": taxon_name, "rank": "species"},
    )
    resp.raise_for_status()
    taxa = resp.json().get("taxon", [])
 
    if not taxa:
        return {}
 
    synonyms: list[str] = [species_name]
 
    for taxon in taxa:
        name = taxon.get("speciesName", "").strip()
        genus = taxon.get("genus", "").strip()
        if not name or not genus:
            continue
        full_name = f"{genus.capitalize()} {name}"
        if full_name.lower() != species_name.lower() and full_name not in synonyms:
            synonyms.append(full_name)
 
    return {name: [] for name in synonyms}
 
 
if __name__ == "__main__":
    main()