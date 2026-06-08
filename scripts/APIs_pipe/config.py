"""
Canonical API name constants for the biodiversity pipeline.

All string values here must match the allowed set in ``scripts.utils.schema._API_NAMES``.
Import from this module rather than spelling names inline so that capitalization
and spacing are consistent across the codebase.
"""

GBIF = "GBIF"
COL = "COL"
TROPICOS = "Tropicos"
INDEX_FUNGORUM = "Index Fungorum"
GENBANK = "GenBank"
MUSHROOM_OBSERVER = "Mushroom Observer"

# Symbiota portal names — pass one of these as ``portal_name`` to ``SymbiotaAPI``.
MYCOPORTAL = "MyCoPortal"
LICHEN_PORTAL = "Lichen Portal"
BRYOPHYTE_PORTAL = "Bryophyte Portal"
CCH2 = "CCH2"
SERNEC = "SERNEC"
NANSH = "NANSH"
SWBIODIVERSITY = "swbiodiversity"
ALGAE_HERBARIUM_PORTAL = "Algae Herbarium Portal"
PTERIDO_PORTAL = "Pterido Portal"
CNH = "CNH"
MID_ATLANTIC_HERBARIA_CONSORTIUM = "Mid-Atlantic Herbaria Consortium"

SYMBIOTA_PORTALS: frozenset[str] = frozenset({
    MYCOPORTAL,
    LICHEN_PORTAL,
    BRYOPHYTE_PORTAL,
    CCH2,
    SERNEC,
    NANSH,
    SWBIODIVERSITY,
    ALGAE_HERBARIUM_PORTAL,
    PTERIDO_PORTAL,
    CNH,
    MID_ATLANTIC_HERBARIA_CONSORTIUM,
})
