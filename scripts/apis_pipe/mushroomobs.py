"""
Mushroom Observer API client.

Mushroom Observer is a community-driven database of fungal observations where
contributors photograph and identify fungi in the field.  The JSON API exposes
name records with synonym lists embedded directly in each result, so synonyms
require no second network request.  Mushroom Observer does not distinguish
"accepted" from "synonym" using those labels; instead it uses a ``deprecated``
boolean flag, and ``status`` is inferred from that.

Synonym searches are not always symmetrical: searching an accepted name will
find its synonyms, but searching a synonym may fail to return an accepted name
row if the only non-deprecated candidate in the API response is an infraspecific
name (e.g. a variety or subspecies).  In that case ``_compile_accepted`` returns
``[]`` rather than emitting a record with a potentially incorrect author.

Documentation
-------------
https://github.com/MushroomObserver/mushroom-observer/blob/main/README_API.md

Fields implemented
------------------
- Taxonomy (kingdom → family): accepted name row only
- author: both rows
- publication_name: accepted name row only
- publication_year: accepted name row only
- status: both rows
- api_link: both rows
"""

import re

from scripts.config import MUSHROOM_OBSERVER_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class MushroomObserverAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for Mushroom Observer.
    """

    BASE_URL = MUSHROOM_OBSERVER_PORTAL.base_url

    _SENSU_AUCT_RE = re.compile(r"sensu\s+auct\.", re.IGNORECASE)

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the Mushroom Observer name ID from a result or synonym record.

        Parameters
        ----------
        raw_data : dict
            A single name record from the ``"results"`` or ``"synonyms"`` list.

        Returns
        -------
        str
            The ``"id"`` field as a string, or ``""`` if absent.
        """
        return str(raw_data.get("id", ""))

    def _extract_publication_name(self, citation: str) -> str:
        """
        Extract the publication name from a Mushroom Observer citation string.

        Parameters
        ----------
        citation : str
            A citation string containing an HTML ``<cite>`` tag, e.g.
            ``"in <cite>Mycologia</cite> (1994)"``.

        Returns
        -------
        str
            The text content of the ``<cite>`` element, or ``""`` if absent.
        """
        match = re.search(r"<cite>(.*?)</cite>", citation)
        return match.group(1) if match else ""

    def _extract_publication_year(self, citation: str) -> str:
        """
        Extract the four-digit publication year from a Mushroom Observer citation string.

        Parameters
        ----------
        citation : str
            A citation string ending with a parenthesised year, e.g.
            ``"in <cite>Mycologia</cite> (1994)"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found.
        """
        match = re.search(r"\((\d{4})\)\s*$", citation)
        return match.group(1) if match else ""

    def _extract_taxonomy(self, parents: list) -> dict[str, str]:
        """
        Extract taxonomy fields from a Mushroom Observer ``parents`` list.

        Parameters
        ----------
        parents : list
            The ``"parents"`` list from a Mushroom Observer name record, each
            item being a dict with ``"rank"`` and ``"name"`` keys.

        Returns
        -------
        dict[str, str]
            Keys present for any of: ``"kingdom"``, ``"phylum"``,
            ``"class_"``, ``"order"``, ``"family"``.
        """
        rank_to_field = {
            "kingdom": "kingdom",
            "phylum": "phylum",
            "class": "class_",
            "order": "order",
            "family": "family",
        }
        return {
            rank_to_field[p["rank"]]: p["name"]
            for p in parents
            if p.get("rank") in rank_to_field
        }

    def _extract_status(self, deprecated: bool | None) -> str:
        """
        Map a Mushroom Observer ``deprecated`` flag to ``"Accepted"`` or ``"Synonym"``.

        Parameters
        ----------
        deprecated : bool or None
            The ``"deprecated"`` field value from a Mushroom Observer name record,
            or ``None`` if the field is absent.

        Returns
        -------
        str
            ``"Synonym"`` when *deprecated* is ``True``; ``"Accepted"`` when
            ``False``; ``""`` when ``None``.
        """
        if deprecated is None:
            return ""
        return "Synonym" if deprecated else "Accepted"

    def _fetch_query_data(self, name: str) -> dict:
        """
        Fetch name records for *name* from the Mushroom Observer ``/names`` endpoint.

        Parameters
        ----------
        name : str
            The scientific name to query (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            Full JSON response from ``/names``, or ``{}`` on any error.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/names",
            params={
                "name": name,
                "include_synonyms": "true",
                "detail": "high",
                "format": "json",
            },
        )

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Flatten synonym records from all result entries into a single list.

        No network request is needed — synonyms are embedded directly in each
        result record by the Mushroom Observer API.  The returned list contains
        both deprecated and non-deprecated entries; ``_compile_synonyms`` filters
        to deprecated-only, while ``_fetch_accepted_data`` uses the full list to
        locate the non-deprecated accepted name when the queried name is a synonym.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Flat list of all embedded synonym dicts from every result record.
        """
        synonyms = []
        for result in raw_data.get("results", []):
            synonyms.extend(result.get("synonyms", []))
        return synonyms

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list) -> list:
        """
        Return all name candidates from *raw_data* for accepted-name resolution.

        When the queried name is already accepted it appears as a top-level
        result.  When it is a synonym, the accepted name is embedded in the
        ``"synonyms"`` list of that result.  Concatenating the top-level results
        with *synonym_data* (already collected by ``_fetch_synonym_data``) gives
        ``_compile_accepted`` a single list to scan for the non-deprecated entry
        regardless of which case applies.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.
        synonym_data : list
            Flat synonym dicts returned by ``_fetch_synonym_data``.

        Returns
        -------
        list
            Top-level result records concatenated with *synonym_data*.
        """
        return raw_data.get("results", []) + synonym_data

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from the Mushroom Observer results.

        Scans candidates from ``_fetch_accepted_data`` — which includes both
        top-level results and embedded synonyms — and returns the first
        non-deprecated, non-infraspecific, non-misspelling entry.  If no such
        entry exists (e.g. MO only resolves to a variety-level name), returns
        ``[]``.

        Parameters
        ----------
        accepted_data : list
            Combined candidate list returned by ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if no
            suitable result is found.
        """
        for result in accepted_data:
            status = self._extract_status(result.get("deprecated"))
            if status == "Synonym":
                continue

            name = normalize_query_string(result["name"])
            if not name:
                continue
            author = result.get("author", "")
            if (
                " sp." in name
                or self._is_infraspecific(name)
                or result.get("misspelled", False)
                or self._SENSU_AUCT_RE.search(author)
            ):
                continue
            genus, species = self._extract_genus_species(name)
            citation = result.get("citation", "")
            taxonomy = self._extract_taxonomy(result.get("parents", []))
            internal_id = self._extract_internal_id(result)
            return [
                self._format_row(
                    api_name=MUSHROOM_OBSERVER_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=internal_id,
                    author=author,
                    publication_name=self._extract_publication_name(citation),
                    publication_year=self._extract_publication_year(citation),
                    status=status,
                    api_link=f"https://mushroomobserver.org/names/{internal_id}"
                    if internal_id
                    else "",
                    **taxonomy,
                )
            ]
        return []

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw Mushroom Observer synonym records into pipeline-standard dicts.

        Skips non-deprecated entries (which belong to the accepted-name row),
        ``"sp."`` placeholders, infraspecific names (rank markers below species
        level, e.g. ``"var."``, ``"subsp."``), ``sensu auct.`` entries,
        misspellings, and duplicates.

        Parameters
        ----------
        synonym_data : list
            Flat list of all embedded synonym dicts as returned by
            ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for synonym in synonym_data:
            status = self._extract_status(synonym.get("deprecated"))
            if status == "Accepted":
                continue
            full_name = synonym.get("name", "")
            full_name = normalize_query_string(full_name)
            if not full_name or full_name in seen:
                continue
            author = synonym.get("author", "")
            if (
                " sp." in full_name
                or synonym.get("misspelled", False)
                or self._is_infraspecific(full_name)
                or self._SENSU_AUCT_RE.search(author)
            ):
                continue
            seen.add(full_name)
            genus, species = self._extract_genus_species(full_name)
            internal_id = self._extract_internal_id(synonym)
            candidates.append(
                self._format_row(
                    api_name=MUSHROOM_OBSERVER_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=internal_id,
                    author=author,
                    status=status,
                    api_link=f"https://mushroomobserver.org/names/{internal_id}"
                    if internal_id
                    else "",
                )
            )
        return candidates
