"""
Looks up a species name in GBIF to find its kingdom, then returns the list
of databases to search for that kingdom.

    from scripts.APIs_pipe.gbif import GBIFAPI
    from scripts.utils.router import TaxonRouter

    router = TaxonRouter(gbif_client=GBIFAPI())
    router.route("Amanita muscaria")
    # ['gbif', 'col', 'genbank', 'index_fungorum', 'mushroomobs', ...]
"""

from scripts.apis_pipe.base import SpeciesAPI

ANIMALIA_APIS: list[str] = [
    "gbif",
    "col",
    "genbank",
]

PLANTAE_APIS: list[str] = [
    "gbif",
    "col",
    "genbank",
    "tropicos",
    "symbiota_bryophyte",
    "symbiota_cch2",
    "symbiota_sernec",
    "symbiota_nansh",
    "symbiota_swbiodiversity",
    "symbiota_macroalgae",
    "symbiota_pterido",
    "symbiota_neherbaria",
    "symbiota_midatlantic",
]

FUNGI_APIS: list[str] = [
    "gbif",
    "col",
    "genbank",
    "index_fungorum",
    "mushroomobs",
    "symbiota_mycoportal",
    "symbiota_lichen",
]

_KINGDOM_MAP: dict[str, list[str]] = {
    "Animalia": ANIMALIA_APIS,
    "Plantae": PLANTAE_APIS,
    "Fungi": FUNGI_APIS,
}


class TaxonRouter:

    def __init__(self, gbif_client: SpeciesAPI):
        self.gbif = gbif_client

    def _get_kingdom(self, name: str) -> str:
        """Ask GBIF which kingdom a species belongs to. Returns 'Unknown' on failure."""
        try:
            res = self.gbif.search(name)
            return res.get("kingdom", "Unknown") if res else "Unknown"
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
