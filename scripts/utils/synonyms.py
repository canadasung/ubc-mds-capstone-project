# Unified Synonym Engine

from datetime import datetime

from scripts.utils.router import TaxonRouter


class SynonymEngine:
    """
    Engine for aggregating and deduplicating taxonomic synonyms across multiple APIs.

    Normalizes the output into a unified format containing provenance data, metadata
    (authors, dates), and confidence scores.
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
                synonyms.append(
                    self._wrap(
                        name=s.get("canonicalName", ""),
                        source="GBIF",
                        raw=s,
                        confidence=1.0
                        if s.get("canonicalName", "").lower() == name.lower()
                        else 0.9,
                        author=s.get("author", ""),
                        date=s.get("date", ""),
                        published_in=s.get("publishedIn", ""),
                        url=s.get("url", ""),
                    )
                )
        except Exception as e:
            print(f"GBIF Synonym Error: {e}")

        # ---------------------------------------------------------
        # 2. Tropicos (plants only)
        # ---------------------------------------------------------
        if "tropicos" in apis:
            try:
                for s in self.tropicos.synonyms(name):
                    name_text = s.get("NameText", "")
                    if name_text:
                        synonyms.append(
                            self._wrap(
                                name=name_text,
                                source="Tropicos",
                                raw=s,
                                confidence=0.9,
                                author=s.get("ScientificNameWithAuthors", "")
                                .replace(name_text, "")
                                .strip()
                                or s.get("Author", ""),
                                date=s.get("DisplayDate", ""),
                                published_in=s.get("DisplayReference", ""),
                                url=f"https://www.tropicos.org/name/{s.get('NameId')}"
                                if s.get("NameId")
                                else "",
                            )
                        )
            except Exception as e:
                print(f"Tropicos Synonym Error: {e}")

        # ---------------------------------------------------------
        # 3. Index Fungorum (fungi only)
        # ---------------------------------------------------------
        if "index_fungorum" in apis:
            try:
                if_syns = self.index_fungorum.synonyms(name)
                # Safely check if it's a list of dicts (in case it still returns raw XML strings)
                if isinstance(if_syns, list):
                    for s in if_syns:
                        if_name = s.get("name") or s.get("canonicalName")
                        if isinstance(s, dict) and if_name:
                            synonyms.append(
                                self._wrap(
                                    name=if_name,
                                    source="Index Fungorum",
                                    raw=s,
                                    confidence=0.8,
                                    author=s.get("authorship", "")
                                    or s.get("author", ""),
                                    date=s.get("year", "") or s.get("date", ""),
                                    published_in=s.get("publishedIn", ""),
                                    url=f"http://www.indexfungorum.org/names/NamesRecord.asp?RecordID={s.get('id')}"
                                    if s.get("id")
                                    else "",
                                )
                            )
            except Exception as e:
                print(f"Index Fungorum Synonym Error: {e}")

        # ---------------------------------------------------------
        # 4. COL (fallback for most groups)
        # ---------------------------------------------------------
        if "col" in apis:
            try:
                for s in self.col.synonyms(name):
                    col_name = s.get("name")
                    if col_name:
                        synonyms.append(
                            self._wrap(
                                name=col_name,
                                source="COL",
                                raw=s,
                                confidence=0.7,
                                author=s.get("authorship", ""),
                                date="",  # COL does not strictly separate publication year in basic endpoints
                                published_in=s.get("publishedIn", ""),
                                url=f"https://www.catalogueoflife.org/data/taxon/{s.get('id')}"
                                if s.get("id")
                                else "",
                            )
                        )
            except Exception as e:
                print(f"COL Synonym Error: {e}")

        # ---------------------------------------------------------
        # Deduplicate by canonical name
        # ---------------------------------------------------------
        seen = set()
        unique = []
        for s in synonyms:
            # 1. s["name"] checks that the string is not empty or None
            # 2. s["name"] not in seen checks that we haven't processed this name yet
            if s["name"] and s["name"] not in seen:
                seen.add(s["name"])
                unique.append(s)

        return unique
