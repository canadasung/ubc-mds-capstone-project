# These are unit tests; they do not hit the real GBIF API.
# The GBIF client passed to TaxonRouter is replaced with a Mock whose
# .search() method returns controlled fake responses.

from unittest.mock import Mock

from scripts.utils.router import TaxonRouter


def make_gbif_client(kingdom: str) -> Mock:
    """Return a mock GBIF client whose search() resolves to the given kingdom."""
    client = Mock()
    client.search.return_value = {"kingdom": kingdom}
    return client


class TestGetKingdom:

    # 1. Animalia (Homo sapiens)
    def test_animalia(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Animalia"))
        assert router._get_kingdom("Homo sapiens") == "Animalia"

    # 2. Plantae (Rosa canina)
    def test_plantae(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Plantae"))
        assert router._get_kingdom("Rosa canina") == "Plantae"

    # 3. Fungi (Amanita muscaria)
    def test_fungi(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Fungi"))
        assert router._get_kingdom("Amanita muscaria") == "Fungi"

    # 4. Bacteria (Escherichia coli)
    def test_bacteria(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Bacteria"))
        assert router._get_kingdom("Escherichia coli") == "Bacteria"

    # 5. Protozoa (Plasmodium falciparum)
    def test_protozoa(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Protozoa"))
        assert router._get_kingdom("Plasmodium falciparum") == "Protozoa"

    # 6. Archaea (Methanobacterium thermoautotrophicum)
    def test_archaea(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Archaea"))
        assert router._get_kingdom("Methanobacterium thermoautotrophicum") == "Archaea"

    # 7. Viruses (Influenza A virus)
    def test_viruses(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Viruses"))
        assert router._get_kingdom("Influenza A virus") == "Viruses"

    # 8. Chromista (Phytophthora infestans)
    def test_chromista(self):
        router = TaxonRouter(gbif_client=make_gbif_client("Chromista"))
        assert router._get_kingdom("Phytophthora infestans") == "Chromista"

    # Edge case: GBIF returns no kingdom field, expect Unknown
    def test_missing_kingdom_returns_unknown(self):
        client = Mock()
        client.search.return_value = {}
        router = TaxonRouter(gbif_client=client)
        assert router._get_kingdom("Unknown organism") == "Unknown"

    # Edge case: GBIF search raises an exception, expect Unknown
    def test_exception_returns_unknown(self):
        client = Mock()
        client.search.side_effect = Exception("network error")
        router = TaxonRouter(gbif_client=client)
        assert router._get_kingdom("Anything") == "Unknown"
