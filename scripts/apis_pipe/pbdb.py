"""
Paleobiology Database (PBDB) API client.

PBDB is a public database of fossil occurrence and taxonomic records maintained
by a global consortium of paleontologists. This client queries the PBDB data
service to retrieve accepted names and synonyms for paleontological taxa.

Documentation
-------------
https://paleobiodb.org/data1.2/

Fields implemented
------------------
- Taxonomy (phylum, class, order, family): accepted name row only
- author: both rows (full attribution string from the att field)
- publication_year: both rows
- status: both rows
- api_link: both rows
"""

import re

import requests

from scripts.config import PBDB_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class PaleobiologyDatabaseAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the Paleobiology Database data service.
    """

    BASE_URL = PBDB_PORTAL.base_url
    HEADERS = {
        "User-Agent": "SpeciesSynonymSearch/1.0 (github.com/canadasung/ubc-mds-capstone-project)"
    }

    _ATT_YEAR_RE: re.Pattern = re.compile(r"\b(\d{4})\b")

    def _is_not_found(self, exc: requests.RequestException) -> bool:
        """
        Return True if *exc* represents a PBDB "no match" response.

        PBDB's ``/taxa/single.json`` and ``/taxa/list.json`` endpoints return
        HTTP 404 when a name has no match, unlike GBIF or COL which return a
        200 response with a semantic no-match flag. Other failure modes
        (timeouts, connection errors, 5xx) are not considered "not found" and
        should propagate so callers can distinguish a missing taxon from a
        flaky or unreachable source.

        Parameters
        ----------
        exc : requests.RequestException
            The exception raised by a failed request.

        Returns
        -------
        bool
            True if *exc* is an ``HTTPError`` with a 404 status code.
        """
        return (
            isinstance(exc, requests.HTTPError)
            and exc.response is not None
            and exc.response.status_code == 404
        )

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the PBDB for *name* and return the first matching taxon record.

        Uses ``/taxa/single.json`` with ``show=attr,class`` to include
        attribution and classification in the response. Returns ``{}`` when
        the name is not found (HTTP 404) or the response contains no records.

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Tyrannosaurus rex"``).

        Returns
        -------
        dict
            Parsed taxon record with fields including ``oid``, ``nam``,
            ``att``, ``phl``, ``cll``, ``odl``, and ``fml``. When the
            queried name is a known synonym, the record also includes
            ``tdf``, ``acc``, and ``acn`` fields. Returns ``{}`` if no
            match is found.

        Raises
        ------
        requests.RequestException
            If the request fails for a reason other than a 404 not-found
            response (timeout, connection error, 5xx, etc.).
        """
        try:
            data = self._fetch_JSON(
                f"{self.BASE_URL}/taxa/single.json",
                params={"name": name, "show": "attr,class"},
            )
        except requests.RequestException as e:
            if self._is_not_found(e):
                return {}
            raise
        records = data.get("records", [])
        return records[0] if records else {}

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the PBDB taxon identifier from a taxon record.

        Parameters
        ----------
        raw_data : dict
            A PBDB taxon record containing an ``oid`` field.

        Returns
        -------
        str
            The ``oid`` value (e.g. ``"txn:54833"``), or ``""`` if absent.
        """
        return raw_data.get("oid", "")

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Fetch all synonym records for the accepted taxon resolved from *raw_data*.

        Uses ``/taxa/list.json`` with ``rel=synonyms``. When *raw_data* is
        itself a synonym (``acn`` field present), the accepted name is taken
        from ``acn``; otherwise it is taken from ``nam``. The returned list
        includes the accepted name entry (identifiable by the absence of a
        ``tdf`` field) as well as all synonym entries.

        Parameters
        ----------
        raw_data : dict
            The record returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            All taxon records from the synonyms endpoint, or ``[]`` when
            *raw_data* has no name or PBDB returns a 404 not-found response.

        Raises
        ------
        requests.RequestException
            If the request fails for a reason other than a 404 not-found
            response (timeout, connection error, 5xx, etc.).
        """
        accepted_name = raw_data.get("acn") or raw_data.get("nam", "")
        if not accepted_name:
            return []
        try:
            data = self._fetch_JSON(
                f"{self.BASE_URL}/taxa/list.json",
                params={
                    "name": accepted_name,
                    "rel": "synonyms",
                    "show": "attr",
                    "limit": 500,
                },
            )
        except requests.RequestException as e:
            if self._is_not_found(e):
                return []
            raise
        return data.get("records", [])

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list) -> dict:
        """
        Return the accepted taxon record with classification fields.

        When *raw_data* is already the accepted name (no ``tdf`` field),
        returns it directly without an additional network call. When
        *raw_data* is a synonym, fetches the accepted taxon record by its
        ``acc`` identifier using ``/taxa/single.json`` with ``show=attr,class``.

        Parameters
        ----------
        raw_data : dict
            The record returned by ``_fetch_query_data``.
        synonym_data : list
            Raw synonym records (unused here).

        Returns
        -------
        dict
            The accepted taxon record with classification fields, or ``{}``
            when the identifier is missing or PBDB returns a 404 not-found
            response.

        Raises
        ------
        requests.RequestException
            If the request fails for a reason other than a 404 not-found
            response (timeout, connection error, 5xx, etc.).
        """
        if not raw_data.get("tdf"):
            return raw_data
        accepted_id = raw_data.get("acc", "")
        if not accepted_id:
            return {}
        try:
            data = self._fetch_JSON(
                f"{self.BASE_URL}/taxa/single.json",
                params={"id": accepted_id, "show": "attr,class"},
            )
        except requests.RequestException as e:
            if self._is_not_found(e):
                return {}
            raise
        records = data.get("records", [])
        return records[0] if records else {}

    def _extract_publication_year(self, att: str) -> str:
        """
        Extract a four-digit publication year from a PBDB attribution string.

        Parameters
        ----------
        att : str
            A PBDB ``att`` value, e.g. ``"Osborn 1905"`` or ``"(Paul 1988)"``.

        Returns
        -------
        str
            Four-digit year string, or ``""`` if not found.
        """
        m = self._ATT_YEAR_RE.search(att)
        return m.group(1) if m else ""

    def _extract_taxonomy(self, data: dict) -> dict[str, str]:
        """
        Extract taxonomy fields from a PBDB taxon record.

        Maps the abbreviated PBDB field names to schema keys. Treats any
        value beginning with ``"NO_"`` (e.g. ``"NO_ORDER_SPECIFIED"``) as
        absent and returns ``""`` for that rank.

        Parameters
        ----------
        data : dict
            A PBDB taxon record obtained from ``/taxa/single.json`` with
            ``show=class``.

        Returns
        -------
        dict[str, str]
            Keys: ``"phylum"``, ``"class_"``, ``"order"``, ``"family"``.
        """
        def _clean(v: str) -> str:
            return "" if not v or v.startswith("NO_") else v

        return {
            "phylum": _clean(data.get("phl", "")),
            "class_": _clean(data.get("cll", "")),
            "order": _clean(data.get("odl", "")),
            "family": _clean(data.get("fml", "")),
        }

    def _compile_accepted(self, accepted_data: dict) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name.

        Parameters
        ----------
        accepted_data : dict
            The accepted taxon record returned by ``_fetch_accepted_data``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the
            scientific name is absent or cannot be parsed into genus and
            species components.
        """
        name = normalize_query_string(accepted_data.get("nam", ""))
        if not name:
            return []
        try:
            genus, species = self._extract_genus_species(name)
        except ValueError:
            return []
        oid = self._extract_internal_id(accepted_data)
        att = accepted_data.get("att", "")
        taxonomy = self._extract_taxonomy(accepted_data)
        numeric_id = oid.split(":")[-1] if ":" in oid else oid
        return [
            self._format_row(
                api_name=PBDB_PORTAL.display_name,
                **taxonomy,
                genus=genus,
                species=species,
                api_internal_id=oid,
                author=att,
                publication_year=self._extract_publication_year(att),
                status="Accepted",
                api_link=f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_no={numeric_id}",
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert raw PBDB synonym records into pipeline-standard synonym dicts.

        Skips records without a ``tdf`` field (the accepted name entry),
        infraspecific names, and duplicate names.

        Parameters
        ----------
        synonym_data : list of dict
            Raw records returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        candidates = []
        seen = set()
        for item in synonym_data:
            if not item.get("tdf"):
                continue
            name = normalize_query_string(item.get("nam", ""))
            if not name or name in seen or self._is_infraspecific(name):
                continue
            try:
                genus, species = self._extract_genus_species(name)
            except ValueError:
                continue
            seen.add(name)
            oid = self._extract_internal_id(item)
            att = item.get("att", "")
            numeric_id = oid.split(":")[-1] if ":" in oid else oid
            candidates.append(
                self._format_row(
                    api_name=PBDB_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=oid,
                    author=att,
                    publication_year=self._extract_publication_year(att),
                    status=self._extract_status(item.get("tdf", "")),
                    api_link=f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_no={numeric_id}",
                )
            )
        return candidates
