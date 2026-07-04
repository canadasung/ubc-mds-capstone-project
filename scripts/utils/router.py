"""
Looks up a species name in GBIF to find its kingdom, then returns the list
of databases to search for that kingdom.

    from scripts.utils.router import TaxonRouter

    router = TaxonRouter()
    router.route("Amanita muscaria")
    # ['GBIF', 'COL', 'GenBank', 'Index Fungorum', 'Mushroom Observer', ...]
"""

from scripts.apis_pipe.gbif import GBIFAPI

ANIMALIA_APIS: list[str] = [
    "GBIF",
    "COL",
    "GenBank",
    "ITIS",
    "FishBase",
    "Paleobiology Database",
]

PLANTAE_APIS: list[str] = [
    "GBIF",
    "COL",
    "GenBank",
    "ITIS",
    "Tropicos",
    "Bryophyte Portal",
    "CCH2",
    "SERNEC",
    "NANSH",
    "Algae Herbarium Portal",
    "Pterido Portal",
    "CNH",
    "Mid-Atlantic Herbaria Consortium",
    "swbiodiversity",
    "Paleobiology Database",
]

FUNGI_APIS: list[str] = [
    "GBIF",
    "COL",
    "GenBank",
    "Index Fungorum",
    "Mushroom Observer",
    "MyCoPortal",
    "Lichen Portal",
    "Paleobiology Database",
    "MycoBank",
]

_KINGDOM_MAP: dict[str, list[str]] = {
    "Animalia": ANIMALIA_APIS,
    "Plantae": PLANTAE_APIS,
    "Fungi": FUNGI_APIS,
}


class TaxonRouter:
    def __init__(self):
        self.gbif = GBIFAPI()

    def _get_kingdom(self, name: str) -> str:
        """Ask GBIF which kingdom a species belongs to. Returns 'Unknown' on failure."""
        try:
            df = self.gbif.get_synonyms(name)
            if df.empty:
                return "Unknown"
            kingdom = df["kingdom"].iloc[0]
            return kingdom if kingdom else "Unknown"
        except Exception as e:
            print(f"Router kingdom lookup failed: {e}")
            return "Unknown"

    def route(self, name: str) -> list[str]:
        """Return the list of databases to search for a given species name.

        Returns an empty list if the kingdom cannot be determined.

            router.route("Quercus robur")
            # ['gbif', 'col', 'genbank', 'tropicos', 'symbiota_bryophyte', ...]
        """
        kingdom = self._get_kingdom(name)
        return _KINGDOM_MAP.get(kingdom, [])
