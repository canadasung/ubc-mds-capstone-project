# API router
"""
Routes taxonomic queries to a set of database sources based on kingdom name.

This class acts as the traffic controller for the search query pipeline. Instead
of querying all available databases (which takes time and bandwidth), it first
asks GBIF to classify the organism's kingdom. It then returns a list of sources
relevant to that specific kingdom.

Example:
    from scripts.APIs_pipe.gbif import GBIFAPI
    from scripts.utils.router import TaxonRouter

    router = TaxonRouter(gbif_client=GBIFAPI())
    kingdom = router._get_kingdom('Amanita muscaria')
    # Fungi
    apis = router.route("Amanita muscaria")
    # ['gbif', 'col', 'genbank', 'index_fungorum', 'mushroomobs', ...]
"""

from scripts.APIs_pipe.base import SpeciesAPI


class TaxonRouter:
    """
    Attributes:
        gbif (SpeciesAPI): An initialized GBIF API client used for high-level
            taxonomic resolution (determining the kingdom).
    """

    def __init__(self, gbif_client: SpeciesAPI):
        """
        Initializes the TaxonRouter with a primary backbone client.

        Args:
            gbif_client (SpeciesAPI): The GBIF client instance.
        """
        self.gbif = gbif_client

    def _get_kingdom(self, name: str) -> str:
        """
        Resolves the biological kingdom of a given scientific name.

        Performs a quick lookup against the GBIF backbone taxonomy to determine
        the kingdom name.

        Args:
            name (str): The scientific name to look up.

        Returns:
            str: The resolved kingdom (e.g., 'Fungi', 'Plantae', 'Animalia').
                 Based on GBIF's backbone there are 8 accepted kingdom names. 
                 Returns 'Unknown' if the name cannot be resolved.
        """
        try:
            res = self.gbif.search(name)
            return res.get("kingdom", "Unknown") if res else "Unknown"
        except Exception as e:
            print(f"Router Kingdom Lookup Error: {e}")
            return "Unknown"

    def route(self, name: str, strict: bool = False) -> list[str]:
        """
        Determines the list of database sources for a given species.

        Base APIs (like GBIF, COL, and GenBank) are always selected. Kingdom-specific
        APIs (like Tropicos for plants, or Mushroom Observer for fungi) are
        dynamically appended based on the taxon's classification.

        Args:
            name (str): The scientific name to route.
            strict (bool, optional): If True, only returns the base universal APIs.
                If False, expands the search to specialized regional and kingdom-specific
                databases. Defaults to False.

        Returns:
            list[str]: A list of string keys corresponding to the initialized API
                clients (e.g., ['gbif', 'col', 'genbank', 'mushroomobs']).
        """
        kingdom = self._get_kingdom(name)

        # Base universal APIs applicable to all domains of life
        apis = ["gbif", "col", "genbank"]

        if strict or kingdom == "Unknown":
            return apis

        # Kingdom-specific routing
        if kingdom == "Fungi":
            apis.extend(
                [
                    "index_fungorum",
                    "mushroomobs",
                    "symbiota_mycoportal",
                    "symbiota_lichen",
                ]
            )
        elif kingdom == "Plantae":
            apis.extend(
                [
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
            )
        elif kingdom == "Animalia":
            pass  # Expand here in the future (e.g., eBird, FishBase)

        return apis
