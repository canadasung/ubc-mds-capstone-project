"""
Mushroom Observer API client.

Mushroom Observer is a community-driven database of fungal observations where
contributors photograph and identify fungi in the field.  The JSON API exposes
name records with synonym lists embedded directly in each result, so synonyms
require no second network request.  Note that Mushroom Observer does not
distinguish "accepted" from "synonym" using those labels; instead it uses a
``deprecated`` flag, and ``status`` is inferred from that.

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
    NAME_URL = "https://mushroomobserver.org/names"

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

    def _extract_status(self, string: str) -> str:
        """
        Map a Mushroom Observer status string to ``"Accepted"`` or ``"Synonym"``.

        Mushroom Observer uses a ``deprecated`` boolean rather than a status
        string; callers should pass ``"deprecated"`` when the flag is ``True``
        and ``"accepted"`` (or ``""``) otherwise.  Falls back to the base-class
        implementation for standard ``"accepted"`` / ``"synonym"`` substrings.

        Parameters
        ----------
        string : str
            ``"deprecated"`` for a deprecated (synonym) name, or any other
            value for the base-class substring check.

        Returns
        -------
        str
            ``"Synonym"`` when *string* is ``"deprecated"``; otherwise
            ``"Accepted"``, ``"Synonym"``, or ``""`` via the base class.
        """
        if string.lower() == "deprecated":
            return "Synonym"
        return super()._extract_status(string)

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
            timeout=15,
        )

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Flatten synonym records from all result entries into a single list.

        No network request is needed — synonyms are embedded directly in each
        result record by the Mushroom Observer API.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.

        Returns
        -------
        list
            Flat list of raw synonym dicts from all result records.
        """
        synonyms = []
        for result in raw_data.get("results", []):
            synonyms.extend(result.get("synonyms", []))
        return synonyms

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list) -> dict:
        """
        Return the ``results`` list from *raw_data* as the search term data.

        The queried name is a top-level result record in the same response as
        the synonyms, so no additional fetch is needed.

        Parameters
        ----------
        raw_data : dict
            The full JSON response returned by ``_fetch_query_data``.
        synonym_data : list
            Flat synonym dicts (unused here).

        Returns
        -------
        list
            The ``"results"`` list from the JSON response.
        """
        return raw_data.get("results", [])  # TODO: add error handling

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from the Mushroom Observer results.

        Returns the first non-misspelling, non-infraspecific result.

        Parameters
        ----------
        accepted_data : list
            The ``"results"`` list returned by ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if no
            suitable result is found.
        """
        # TODO: bug here, this is duplicating the entry when the search term is a synonym itself. when the search term is an accepted name this is working as expected. Likely an issue with the formatting of how mushroom observer returns that the code is not matching. Seems like the returned data is not symmetrical whether you search an "accepted" name or a "synonym", even though mushroom observer itself does not classify anything to accepted or synonym
        for result in accepted_data:
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
            status = self._extract_status(
                "deprecated" if result.get("deprecated", False) else "accepted"
            )
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
                    api_link=f"{self.NAME_URL}/{internal_id}" if internal_id else "",
                    **taxonomy,
                )
            ]
        return []

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw Mushroom Observer synonym records into pipeline-standard dicts.

        Skips misspellings, ``"sp."`` placeholders, infraspecific names,
        ``sensu auct.`` entries, and duplicates.

        Parameters
        ----------
        synonym_data : list
            Flat list of raw synonym dicts as returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records, deduplicated by name.
        """
        candidates = []
        seen = set()
        for synonym in synonym_data:
            full_name = synonym.get("name", "")
            full_name = normalize_query_string(full_name)
            if not full_name or full_name in seen:
                continue
            author = synonym.get("author", "")
            # removing rank incomplete names (rank marker above species level, e.g. "Amanita sp.", which indicates a collection-level annotation), misspelled, infraspecific (rank markers below species level, e.g. "var.", "subsp.", etc), and sensu auct. names
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
            status = self._extract_status(
                "deprecated" if synonym.get("deprecated", False) else "accepted"
            )
            candidates.append(
                self._format_row(
                    api_name=MUSHROOM_OBSERVER_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=internal_id,
                    author=author,
                    status=status,
                    api_link=f"{self.NAME_URL}/{internal_id}" if internal_id else "",
                )
            )
        return candidates
