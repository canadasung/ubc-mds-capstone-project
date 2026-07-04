"""
Canonical API name constants for the biodiversity pipeline.

All display_name values here must match the allowed set in ``scripts.utils.schema._API_NAMES``,
which is itself derived from ALL_PORTALS below — so this file is the single source of truth.
"""

from typing import NamedTuple

# Placeholder value for the Tropicos API key as set in .env.example.
# Used to detect when the key has not been replaced with a real value.
TROPICOS_API_KEY_PLACEHOLDER = "000-0000-0000-0000"


class APIPortal(NamedTuple):
    """Display name and base URL for a single API portal."""

    display_name: str  # name shown in output table; must match schema._API_NAMES
    base_url: str  # root URL of the API


# Non-Symbiota portals
GBIF_PORTAL = APIPortal("GBIF", "https://api.gbif.org/v1")
COL_PORTAL = APIPortal("COL", "https://api.checklistbank.org")
TROPICOS_PORTAL = APIPortal("Tropicos", "http://services.tropicos.org")
INDEX_FUNGORUM_PORTAL = APIPortal(
    "Index Fungorum", "https://www.indexfungorum.org/ixfwebservice/fungus.asmx"
)
GENBANK_PORTAL = APIPortal("GenBank", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils")
MUSHROOM_OBSERVER_PORTAL = APIPortal(
    "Mushroom Observer", "https://mushroomobserver.org/api2"
)
FISHBASE_PORTAL = APIPortal("FishBase", "https://www.fishbase.se")
ITIS_PORTAL = APIPortal("ITIS", "https://www.itis.gov/ITISWebService/jsonservice")
PBDB_PORTAL = APIPortal("Paleobiology Database", "https://paleobiodb.org/data1.2")
MYCOBANK_PORTAL = APIPortal(
    "MycoBank", "https://webservices.bio-aware.com/westerdijk/mycobank"
)


# Symbiota portal instances
SYMBIOTA_PORTALS: list[APIPortal] = [
    APIPortal("MyCoPortal", "https://mycoportal.org/portal"),
    APIPortal("Lichen Portal", "https://lichenportal.org/portal"),
    APIPortal("Bryophyte Portal", "https://bryophyteportal.org/portal"),
    APIPortal("CCH2", "https://cch2.org/portal"),
    APIPortal("SERNEC", "https://sernecportal.org/portal"),
    APIPortal("NANSH", "https://nansh.org/portal"),
    APIPortal("Algae Herbarium Portal", "https://macroalgae.org/portal"),
    APIPortal("Pterido Portal", "https://pteridoportal.org/portal"),
    APIPortal("CNH", "https://neherbaria.org/portal"),
    APIPortal(
        "Mid-Atlantic Herbaria Consortium", "https://midatlanticherbaria.org/portal"
    ),
    APIPortal("swbiodiversity", "https://swbiodiversity.org/seinet"),
]

# Lookup by display name — use this in SymbiotaAPI to resolve name → base URL.
SYMBIOTA_PORTAL_BY_NAME: dict[str, APIPortal] = {
    p.display_name: p for p in SYMBIOTA_PORTALS
}

# All portals — used by schema.py to build the valid api_name set.
ALL_PORTALS: list[APIPortal] = [
    GBIF_PORTAL,
    COL_PORTAL,
    TROPICOS_PORTAL,
    INDEX_FUNGORUM_PORTAL,
    GENBANK_PORTAL,
    MUSHROOM_OBSERVER_PORTAL,
    FISHBASE_PORTAL,
    ITIS_PORTAL,
    PBDB_PORTAL,
    MYCOBANK_PORTAL,
    *SYMBIOTA_PORTALS,
]
