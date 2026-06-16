# Unified Synonym Engine

from datetime import datetime

from scripts.utils.router import TaxonRouter


class SynonymEngine:
    """
    Engine for aggregating and deduplicating taxonomic synonyms across multiple APIs.

    Normalizes the output into a unified format containing provenance data, metadata
    (authors, dates), and confidence scores.

    All API clients are expected to return synonyms as ``list[dict]`` in the
    pipeline-standard ``_format_synonym()`` format with keys:
    ``"name"``, ``"author"``, ``"publication_date"``, ``"publication_name"``,
    ``"api_link"``.
    """

    def __init__(self, gbif, tropicos, index_fungorum, col):
        """
        Initialize the SynonymEngine with concrete API client instances.

        Args:
            gbif (GBIFAPI): Initialized GBIF API client (used as the base authoritative router).
            tropicos (TropicosAPI): Initialized Tropicos API client (for plants).
            index_fungorum (IndexFungorumAPI): Initialized Index Fungorum API client (for fungi).
            col (COLAPI): Initialized Catalogue of Life API client (general fallback).
        """
        self.gbif = gbif
        self.tropicos = tropicos
        self.index_fungorum = index_fungorum
        self.col = col

        # Dynamic API router based on GBIF backbone
        self.router = TaxonRouter(gbif)

    def _wrap(
        self,
        name: str,
        source: str,
        raw,
        confidence: float,
        author: str = "",
        date: str = "",
        published_in: str = "",
        url: str = "",
    ):
        """
        Internal helper to wrap raw API synonym data into a standardized dictionary.

        Attaches metadata such as the source API, a confidence score, publication
        data, direct URLs, and a timestamped provenance record.

        Args:
            name (str): The extracted canonical synonym name.
            source (str): The name of the API source (e.g., "GBIF", "Tropicos").
            raw (dict | str): The raw data record returned by the source API.
            confidence (float): A score from 0.0 to 1.0 indicating reliability.
            author (str, optional): The author citation for the name.
            date (str, optional): The year or date of publication.
            published_in (str, optional): The journal or publication name.
            url (str, optional): A direct hyperlink to the taxon's source page.

        Returns:
            dict: A standardized dictionary containing the synonym and its metadata.
        """
        return {
            "name": name,
            "author": author.strip() if author else "",
            "date": date.strip() if date else "",
            "publishedIn": published_in.strip() if published_in else "",
            "url": url.strip() if url else "",
            "source": source,
            "confidence": confidence,
            "provenance": {
                "api": source,
                "raw": raw,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def _wrap_standard(self, s: dict, source: str, confidence: float) -> dict:
        """
        Wrap a pipeline-standard ``_format_synonym()`` record into the engine's output format.

        All backbone API clients return synonyms with the standardized keys
        ``"name"``, ``"author"``, ``"publication_date"``, ``"publication_name"``,
        ``"api_link"``. This helper reads those keys uniformly.

        Args:
            s (dict): A synonym record from a ``_format_synonym()``-compliant client.
            source (str): The source label (e.g. ``"GBIF"``).
            confidence (float): Confidence score to attach.

        Returns:
            dict: Engine-format synonym dict.
        """
        return self._wrap(
            name=s.get("name", ""),
            source=source,
            raw=s,
            confidence=confidence,
            author=s.get("author", ""),
            date=s.get("publication_date", ""),
            published_in=s.get("publication_name", ""),
            url=s.get("api_link", ""),
        )

    def get_synonyms(self, name: str):
        """
        Retrieve, aggregate, and deduplicate synonyms for a given scientific name.

        Uses the TaxonRouter to determine the appropriate domain-specific APIs to query,
        fetches the data, wraps each result in a standardized format with metadata,
        and deduplicates the final list based on the canonical name.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            list[dict]: A list of unified synonym dictionaries.
        """
        synonyms = []

        # Determine which APIs to query based on taxonomy
        apis = self.router.route(name)

        # ---------------------------------------------------------
        # 1. GBIF (always authoritative, always included)
        # ---------------------------------------------------------
        try:
            gbif_syns = self.gbif.synonyms(name)
            for s in gbif_syns:
                confidence = 1.0 if s.get("name", "").lower() == name.lower() else 0.9
                synonyms.append(self._wrap_standard(s, source="GBIF", confidence=confidence))
        except Exception as e:
            print(f"GBIF Synonym Error: {e}")

        # ---------------------------------------------------------
        # 2. Tropicos (plants only)
        # ---------------------------------------------------------
        if "tropicos" in apis:
            try:
                for s in self.tropicos.synonyms(name):
                    if s.get("name"):
                        synonyms.append(self._wrap_standard(s, source="Tropicos", confidence=0.9))
            except Exception as e:
                print(f"Tropicos Synonym Error: {e}")

        # ---------------------------------------------------------
        # 3. Index Fungorum (fungi only)
        # ---------------------------------------------------------
        if "index_fungorum" in apis:
            try:
                for s in self.index_fungorum.synonyms(name):
                    if s.get("name"):
                        synonyms.append(self._wrap_standard(s, source="Index Fungorum", confidence=0.8))
            except Exception as e:
                print(f"Index Fungorum Synonym Error: {e}")

        # ---------------------------------------------------------
        # 4. COL (fallback for most groups)
        # ---------------------------------------------------------
        if "col" in apis:
            try:
                for s in self.col.synonyms(name):
                    if s.get("name"):
                        synonyms.append(self._wrap_standard(s, source="COL", confidence=0.7))
            except Exception as e:
                print(f"COL Synonym Error: {e}")

        # ---------------------------------------------------------
        # Deduplicate by canonical name
        # ---------------------------------------------------------
        seen = set()
        unique = []
        for s in synonyms:
            if s["name"] and s["name"] not in seen:
                seen.add(s["name"])
                unique.append(s)

        return unique
