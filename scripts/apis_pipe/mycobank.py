"""
MycoBank API client.

MycoBank is the official nomenclatural registry for fungal names, maintained
by the Westerdijk Fungal Biodiversity Institute via BioAware web services.
This client queries the MycoBank REST API to retrieve accepted names and
synonyms for fungal taxa.

Authentication
--------------
Requires a registered MycoBank account (https://www.mycobank.org/profile/register).
Set MYCOBANK_EMAIL and MYCOBANK_PASSWORD in the .env file. An OAuth2 access
token is obtained from the /connect/token endpoint using the password grant
and cached for its lifetime.

Documentation
-------------
https://webservices.bio-aware.com/westerdijk/mycobank

Fields implemented
------------------
- Taxonomy (kingdom -> subfamily): accepted name row only
- author: both rows
- publication_name: both rows
- publication_year: both rows
- status: both rows
- api_link: both rows

Request cost
------------
The search response only returns synonym ids with a placeholder name (a
MycoBank API quirk), so each synonym must be fetched individually to resolve
its real name, authorship, and publication year. A heavily-synonymized query
can therefore issue many sequential requests.
"""

import os
import time

import requests

from scripts.config import MYCOBANK_PORTAL
from scripts.utils.normalize_query_string import normalize_query_string

from .base import SpeciesAPI


class MycoBankAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for the MycoBank/BioAware REST API.
    """

    BASE_URL = MYCOBANK_PORTAL.base_url
    _TOKEN_URL = "https://webservices.bio-aware.com/westerdijk/connect/token"
    _CLIENT_ID = "CBS"

    # Maps MycoBank's abbreviated rank strings (from the resolved
    # `classification` list) to schema taxonomy field names.
    _RANK_TO_FIELD = {
        "regn.": "kingdom",
        "div.": "phylum",
        "cl.": "class_",
        "ordo": "order",
        "fam.": "family",
        "subfam.": "subfamily",
    }

    # `include=` fields for the accepted-name row (needs classification and
    # bibliography resolved).
    _ACCEPTED_INCLUDE = [
        "authors",
        "yearOfEffectivePublication",
        "mycobankNr",
        "rank",
        "synonymy",
        "classification",
        "bibliographyinfo",
    ]
    # Lighter `include=` list for resolving a single synonym record (no
    # classification/synonymy needed for a synonym row).
    _SYNONYM_INCLUDE = [
        "authors",
        "yearOfEffectivePublication",
        "mycobankNr",
        "rank",
        "bibliographyinfo",
    ]

    def __init__(self):
        """
        Load MycoBank credentials from the environment.

        Raises
        ------
        ValueError
            If MYCOBANK_EMAIL or MYCOBANK_PASSWORD is not set.
        """
        self._email = os.getenv("MYCOBANK_EMAIL", "")
        self._password = os.getenv("MYCOBANK_PASSWORD", "")
        if not self._email or not self._password:
            raise ValueError(
                "MycoBank credentials not provided. Set MYCOBANK_EMAIL and "
                "MYCOBANK_PASSWORD in the `.env` file."
            )
        self._access_token: str = ""
        self._token_expiry: float = 0.0

    def _get_token(self) -> str:
        """
        Return a cached OAuth2 access token, requesting a new one if expired.

        Returns
        -------
        str
            A bearer access token valid for the ``mycobank`` scope.

        Raises
        ------
        requests.RequestException
            If the token request fails.
        """
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        resp = requests.post(
            self._TOKEN_URL,
            data={
                "grant_type": "password",
                "username": self._email,
                "password": self._password,
                "client_id": self._CLIENT_ID,
                "client_secret": "",
                "scope": "mycobank",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._TIMEOUT,
        )
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            print(f"{type(self).__name__} error parsing token response JSON.")
            raise
        self._access_token = data["access_token"]
        # Refresh 60 seconds early so a token never expires mid-request.
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token

    def _authed_get(
        self, path: str, params: dict, accept: str = "application/json"
    ) -> dict:
        """
        Make an authenticated GET request against the MycoBank API.

        Reuses ``SpeciesAPI._fetch`` for the network call and error
        reporting (via its ``headers`` override), so a failed request is
        printed and re-raised the same way every other client's requests
        are, rather than reimplementing that logic here.

        Parameters
        ----------
        path : str
            Path appended to ``BASE_URL`` (e.g. ``"/taxonnames"``).
        params : dict
            Query parameters.
        accept : str, optional
            Value of the ``Accept`` header, controlling how relational
            fields (``classification``, ``synonymy``) are shaped in the
            response. Defaults to ``"application/json"`` (ids only, not
            resolved).

        Returns
        -------
        dict
            Parsed JSON response, or ``{}`` if the response body is not
            valid JSON.

        Raises
        ------
        requests.RequestException
            If the request fails (network error or non-2xx status).
        """
        token = self._get_token()
        response = self._fetch(
            f"{self.BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": accept},
        )
        try:
            return response.json()
        except ValueError:
            print(f"{type(self).__name__} error parsing JSON.")
            return {}

    def _fetch_query_data(self, name: str) -> dict:
        """
        Search MycoBank for *name* and return the first matching taxon record.

        Uses ``/taxonnames`` with an exact ``anyText eq`` filter and
        ``Accept: application/links+json`` so ``classification`` resolves to
        named, ranked objects in this single call. Returns ``{}`` when no
        record matches (a clean 200 response with an empty ``items`` list).

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        dict
            The first matching taxon record, with ``classification``
            resolved. ``{}`` if no match is found.
        """
        # OData string literals escape an embedded single quote by doubling
        # it; without this, a name like "O'Brienii" would break the filter
        # expression's quoting.
        escaped_name = name.replace("'", "''")
        data = self._authed_get(
            "/taxonnames",
            params={
                "filter": f"anyText eq '{escaped_name}'",
                "pageSize": 1,
                "include": self._ACCEPTED_INCLUDE,
            },
            accept="application/links+json",
        )
        items = data.get("items", [])
        return items[0] if items else {}

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the MycoBank internal taxon id from a record.

        Parameters
        ----------
        raw_data : dict
            A MycoBank taxon record containing an ``id`` field.

        Returns
        -------
        str
            The record's ``id`` as a string, or ``""`` if absent.
        """
        return str(raw_data["id"]) if "id" in raw_data else ""

    def _fetch_synonym_data(self, raw_data: dict) -> list:
        """
        Resolve all synonym records referenced by *raw_data*'s ``synonymy``.

        The nested ``taxonSynonyms``, ``obligateSynonyms``, and ``basionym``
        entries only carry a placeholder name (a MycoBank API quirk), so each
        referenced id is fetched individually to obtain its real name,
        authorship, and publication year. A synonym id that fails to
        resolve (e.g. a transient error) is skipped rather than aborting the
        whole search.

        When *raw_data* itself is a synonym (not the accepted name), the
        synonym group returned by the API includes *raw_data*'s own id, since
        the API returns the whole group's synonymy regardless of which
        member was queried. That entry is resolved from *raw_data* directly
        (it already carries a clean ``name``, avoiding a redundant fetch)
        rather than skipped, so the exact name that was searched for is not
        silently dropped from the result. Only the accepted name's own id is
        excluded, since it is compiled separately by ``_fetch_accepted_data``.

        Parameters
        ----------
        raw_data : dict
            The record returned by ``_fetch_query_data``.

        Returns
        -------
        list of dict
            Fully resolved synonym records (one per unique referenced id).
        """
        synonymy = raw_data.get("synonymy", {})
        ids: list[int] = []
        for entry in synonymy.get("taxonSynonyms") or []:
            entry_id = entry.get("id")
            if entry_id is not None:
                ids.append(entry_id)
        for entry in synonymy.get("obligateSynonyms") or []:
            entry_id = entry.get("id")
            if entry_id is not None:
                ids.append(entry_id)
        basionym = synonymy.get("basionym")
        if basionym:
            basionym_id = basionym.get("id")
            if basionym_id is not None:
                ids.append(basionym_id)

        current_name = synonymy.get("currentName") or {}
        current_id = current_name.get("id")
        own_id = raw_data.get("id")

        seen: set[int] = set()
        resolved = []
        for syn_id in ids:
            if syn_id == current_id or syn_id in seen:
                continue
            seen.add(syn_id)
            if syn_id == own_id:
                resolved.append(raw_data)
                continue
            try:
                record = self._authed_get(
                    f"/taxonnames/{syn_id}",
                    params={"include": self._SYNONYM_INCLUDE},
                    accept="application/links+json",
                )
            except requests.RequestException:
                continue
            if record:
                resolved.append(record)
        return resolved

    def _fetch_accepted_data(self, raw_data: dict, synonym_data: list) -> dict:
        """
        Return the fully resolved accepted-name record.

        Fast path: *raw_data* already is the accepted name (its own ``id``
        matches ``synonymy.currentName.id``), so it is returned unchanged.
        Slow path: fetches the accepted record by id, since the initial hit
        was itself a synonym.

        Parameters
        ----------
        raw_data : dict
            The record returned by ``_fetch_query_data``.
        synonym_data : list
            Resolved synonym records (unused here).

        Returns
        -------
        dict
            The accepted taxon record with ``classification`` resolved, or
            ``{}`` if it cannot be resolved.
        """
        synonymy = raw_data.get("synonymy", {})
        current_name = synonymy.get("currentName") or {}
        current_id = current_name.get("id")
        if current_id is None or current_id == raw_data.get("id"):
            return raw_data
        try:
            return self._authed_get(
                f"/taxonnames/{current_id}",
                params={"include": self._ACCEPTED_INCLUDE},
                accept="application/links+json",
            )
        except requests.RequestException:
            return {}

    def _extract_publication_year(self, record: dict) -> str:
        """
        Return the publication year already provided by MycoBank.

        Unlike sources that embed the year in a citation string, MycoBank
        exposes it as its own field, so no extraction is needed.

        Parameters
        ----------
        record : dict
            A MycoBank taxon record.

        Returns
        -------
        str
            The ``yearOfEffectivePublication`` value, or ``""`` if absent.
        """
        return record.get("yearOfEffectivePublication") or ""

    def _extract_publication_name(self, record: dict) -> str:
        """
        Extract the resolved bibliography citation string from a record.

        Parameters
        ----------
        record : dict
            A MycoBank taxon record with ``bibliographyinfo`` resolved via
            ``Accept: application/links+json``.

        Returns
        -------
        str
            The first bibliography entry's citation string, or ``""`` if
            ``bibliographyinfo`` is empty or unresolved.
        """
        entries = record.get("bibliographyinfo") or []
        if entries and isinstance(entries[0], dict):
            return entries[0].get("name") or ""
        return ""

    def _build_api_link(self, record: dict) -> str:
        """
        Build the public MycoBank URL for a record, if it has a mycobankNr.

        Parameters
        ----------
        record : dict
            A MycoBank taxon record, possibly containing a ``mycobankNr``
            field.

        Returns
        -------
        str
            ``"https://www.mycobank.org/MB/{mycobankNr}"``, or ``""`` if
            ``mycobankNr`` is absent. Uses an explicit ``None`` check rather
            than truthiness, since ``0`` would be a valid (if unlikely) id.
        """
        mycobank_nr = record.get("mycobankNr")
        if mycobank_nr is None:
            return ""
        return f"https://www.mycobank.org/MB/{mycobank_nr}"

    def _extract_taxonomy(self, data: dict) -> dict[str, str]:
        """
        Extract taxonomy fields from a resolved ``classification`` list.

        Maps MycoBank's abbreviated rank strings (e.g. ``"regn."``,
        ``"div."``) to schema taxonomy field names via ``_RANK_TO_FIELD``.

        Parameters
        ----------
        data : dict
            A MycoBank taxon record with ``classification`` resolved to a
            list of ``{id, name, rank, ...}`` objects.

        Returns
        -------
        dict[str, str]
            Taxonomy field dict with string values for each rank present.
            Ranks not found in ``classification`` are omitted.
        """
        rank_map = {
            item.get("rank"): item.get("name", "")
            for item in data.get("classification") or []
            if isinstance(item, dict) and item.get("rank") in self._RANK_TO_FIELD
        }
        return {
            field: rank_map[rank]
            for rank, field in self._RANK_TO_FIELD.items()
            if rank in rank_map
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
        name = normalize_query_string(accepted_data.get("name", ""))
        if not name:
            return []
        try:
            genus, species = self._extract_genus_species(name)
        except ValueError:
            return []
        taxonomy = self._extract_taxonomy(accepted_data)
        return [
            self._format_row(
                api_name=MYCOBANK_PORTAL.display_name,
                **taxonomy,
                genus=genus,
                species=species,
                api_internal_id=self._extract_internal_id(accepted_data),
                author=accepted_data.get("authors", ""),
                publication_year=self._extract_publication_year(accepted_data),
                publication_name=self._extract_publication_name(accepted_data),
                status="Accepted",
                api_link=self._build_api_link(accepted_data),
            )
        ]

    def _compile_synonyms(self, synonym_data: list) -> list[dict]:
        """
        Convert resolved MycoBank synonym records into pipeline-standard dicts.

        Skips infraspecific names and duplicates.

        Parameters
        ----------
        synonym_data : list of dict
            Fully resolved synonym records returned by ``_fetch_synonym_data``.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        candidates = []
        seen = set()
        for record in synonym_data:
            name = normalize_query_string(record.get("name", ""))
            if not name or name in seen or self._is_infraspecific(name):
                continue
            try:
                genus, species = self._extract_genus_species(name)
            except ValueError:
                continue
            seen.add(name)
            candidates.append(
                self._format_row(
                    api_name=MYCOBANK_PORTAL.display_name,
                    genus=genus,
                    species=species,
                    api_internal_id=self._extract_internal_id(record),
                    author=record.get("authors", ""),
                    publication_year=self._extract_publication_year(record),
                    publication_name=self._extract_publication_name(record),
                    status="Synonym",
                    api_link=self._build_api_link(record),
                )
            )
        return candidates
