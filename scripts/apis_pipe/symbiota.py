"""
Symbiota API client.

Symbiota is open-source biodiversity data management software that powers
numerous natural history collection portals worldwide.  Each portal runs its
own instance with independent data, but the same API structure.  This module
provides a single ``SymbiotaAPI`` class that accepts a portal name at
construction time and resolves the correct base URL from ``config.py``.

The Symbiota API returns JSON from ``api/v2/taxonomy`` and HTML from
``/taxa/index.php``.  The JSON endpoints are used to resolve taxon IDs and
taxonomy; the HTML page is scraped for synonym entries.

Unlike most API clients in this pipeline, ``SymbiotaAPI`` overrides
``get_synonyms`` with a custom orchestrator.  ``_fetch_query_data`` performs
two calls — a name search to find the initial ``tid``, followed by a full
``api/v2/taxonomy/{tid}`` fetch — and returns the combined taxon record as
``raw_data``.  ``get_synonyms`` then extracts the accepted ``tid`` and passes
it explicitly to ``_fetch_synonym_data`` and ``_fetch_accepted_data``, rather
than relying on instance state.  Symbiota portals do not assign separate IDs
to synonym records; a single accepted ``tid`` is used for both
``api_internal_id`` and ``api_link`` across every row in the result.

Documentation
-------------
All implemented Symbiota portals have documentation available through Swagger.

- MyCoPortal: https://mycoportal.org/portal/api/v2/documentation
- Lichen Portal: https://lichenportal.org/portal/api/v2/documentation
- Bryophyte Portal: https://bryophyteportal.org/portal/api/v2/documentation
- CCH2: https://cch2.org/portal/api/v2/documentation
- SERNEC: https://sernecportal.org/portal/api/v2/documentation
- NANSH: https://nansh.org/portal/api/v2/documentation
- Algae Herbarium Portal: https://macroalgae.org/portal/api/v2/documentation
- Pterido Portal: https://pteridoportal.org/portal/api/v2/documentation
- CNH: https://neherbaria.org/portal/api/v2/documentation
- Mid-Atlantic Herbaria Consortium: https://midatlanticherbaria.org/portal/api/v2/documentation
- swbiodiversity: https://swbiodiversity.org/seinet/api/v2/documentation

Fields implemented
------------------
- Taxonomy (kingdom → subfamily): accepted name row only
- author: both rows
- original_source: accepted name row only
- status: both rows
- api_link: both rows
"""

import re

import pandas as pd

from scripts.config import SYMBIOTA_PORTAL_BY_NAME
from scripts.utils.normalize_query_string import normalize_query_string
from scripts.utils.schema import empty_synonym_table

from .base import SpeciesAPI

# Maps each portal's display_name to the endpoint used for name search queries.
_SEARCH_ENDPOINT: dict[str, str] = {
    "MyCoPortal": "api/v2/taxonomy/search",
}
_DEFAULT_SEARCH_ENDPOINT = "api/v2/taxonomy"

# Exact rankid values used by Symbiota for each taxonomic rank.
# Kingdom (10) is read from the top-level kingdomName field instead.
_RANK_IDS: dict[str, int] = {
    "phylum": 30,
    "class_": 60,
    "order": 100,
    "family": 140,
}


class SymbiotaAPI(SpeciesAPI):
    """
    SpeciesAPI implementation for a single Symbiota portal instance.

    Attributes
    ----------
    BASE_URL : str
        Empty string placeholder; the real URL is set at construction time
        from ``config.SYMBIOTA_PORTAL_BY_NAME`` and stored without a trailing
        slash.
    portal_name : str
        Human-readable portal identifier used in log messages and the
        ``api_name`` field.
    """

    BASE_URL = ""

    def __init__(self, portal_name: str):
        """
        Initialise the client for the named Symbiota portal.

        Parameters
        ----------
        portal_name : str
            Display name of the target portal (e.g. ``"MyCoPortal"``).  Must
            be a key in ``config.SYMBIOTA_PORTAL_BY_NAME``.

        Raises
        ------
        ValueError
            If *portal_name* is not a recognised Symbiota portal key.
        """
        portal = SYMBIOTA_PORTAL_BY_NAME.get(portal_name)
        if portal is None:
            raise ValueError(
                f"Unknown Symbiota portal key {portal_name!r}. "
                f"Must be one of: {sorted(SYMBIOTA_PORTAL_BY_NAME)}"
            )
        self.BASE_URL = portal.base_url.rstrip("/")
        self.portal_name = portal.display_name

    # ---------------------------------------------------------
    # Schema helpers
    # ---------------------------------------------------------

    def _extract_taxonomy(self, data: dict) -> dict[str, str]:
        """
        Extract taxonomy fields from a Symbiota ``api/v2/taxonomy/{id}`` response.

        Builds a rankid-to-names index from the ``"classification"`` list.
        When a rankid has multiple entries the first value is used.

        Parameters
        ----------
        data : dict
            Parsed JSON from ``api/v2/taxonomy/{id}``.

        Returns
        -------
        dict[str, str]
            Keys: ``"kingdom"``, ``"phylum"``, ``"class_"``, ``"order"``,
            and ``"family"``.
        """
        rank_index: dict[int, list[str]] = {}
        for entry in data.get("classification", []):
            rid = entry.get("rankid")
            name = entry.get("scientificName", "")
            if rid is not None and name and str(name).strip():
                rank_index.setdefault(int(rid), []).append(str(name).strip())

        kingdom = str(data.get("kingdomName") or (rank_index.get(10, [""])[0]) or "")
        result: dict[str, str] = {"kingdom": kingdom}
        for col, rid in _RANK_IDS.items():
            result[col] = rank_index.get(rid, [""])[0]
        return result

    # ---------------------------------------------------------
    # Taxon ID resolution (internal helpers)
    # ---------------------------------------------------------

    def _extract_internal_id(self, raw_data: dict) -> str:
        """
        Extract the portal's internal taxon ID (``tid``) from a taxon record.

        Parameters
        ----------
        raw_data : dict
            Full ``api/v2/taxonomy/{tid}`` record returned by ``_fetch_query_data``.

        Returns
        -------
        str
            Internal taxon ID (``tid``).
        """
        return raw_data["tid"]

    def _extract_internal_accepted_id(self, raw_data: dict) -> str:
        """
        Extract the accepted taxon ``tid`` from a ``api/v2/taxonomy/{id}`` response.

        Returns the taxon's own ``tid`` when its status is ``"accepted"``, or
        follows the ``accepted.tid`` pointer when it is ``"synonym"``.

        Parameters
        ----------
        raw_data : dict
            Parsed JSON from ``api/v2/taxonomy/{id}``.

        Returns
        -------
        str
            Internal ``tid`` of the accepted taxon.

        Raises
        ------
        ValueError
            If the taxon status is neither ``"accepted"`` nor ``"synonym"``.
        """
        status = raw_data["status"]
        if status not in ("accepted", "synonym"):
            raise ValueError(f"{self.portal_name}: Unrecognised status '{status}'.")
        if status == "accepted":
            return raw_data["tid"]
        else:
            accepted = raw_data["accepted"]
            return accepted["tid"]

    # ---------------------------------------------------------
    # Synonym extraction helpers
    # ---------------------------------------------------------

    def _extract_synonym_pairs(self, html: str) -> list[tuple[str, str]]:
        """
        Extract ``(name, author)`` pairs from the ``synonymDiv`` in taxa page HTML.

        Finds the ``synonymDiv`` element, then parses ``<i>name</i> author``
        entries within it.  Infraspecific names are excluded.

        Parameters
        ----------
        html : str
            Raw HTML of the taxa page (full page, not just the div).

        Returns
        -------
        list[tuple[str, str]]
            ``(name, author)`` pairs for species-level synonyms, or ``[]`` if
            the ``synonymDiv`` is not found.
        """
        syn_match = re.search(r'id="synonymDiv"[^>]*>(.*?)</div>', html, re.DOTALL)
        if not syn_match:
            return []
        syn_html = syn_match.group(1)
        pairs = []
        for match in re.finditer(r"<i>(.*?)</i>([^<]*)", syn_html):
            name = match.group(1).strip()
            author = match.group(2).strip()
            if name and not self._is_infraspecific(name):
                pairs.append((name, author))
        return pairs

    # ---------------------------------------------------------
    # Required template methods
    # ---------------------------------------------------------

    def _fetch_query_data(self, name: str) -> dict:
        """
        Query the portal for *name* and return the full ``api/v2/taxonomy/{tid}`` record.

        Searches for *name* using ``api/v2/taxonomy/search`` (some portals) or
        ``api/v2/taxonomy``, falling back to autocomplete if both return nothing.
        Once a matching ``tid`` is found, fetches and returns the full taxon record
        from ``api/v2/taxonomy/{tid}``, which includes ``status``, ``accepted.tid``,
        author, and classification — the fields needed by downstream extract and
        compile methods.

        Parameters
        ----------
        name : str
            Normalised scientific name.

        Returns
        -------
        dict
            Full ``api/v2/taxonomy/{tid}`` record, or ``{}`` if the name is not
            found or the taxon fetch fails.
        """
        endpoint = _SEARCH_ENDPOINT.get(self.portal_name, _DEFAULT_SEARCH_ENDPOINT)
        data = self._fetch_JSON(
            f"{self.BASE_URL}/{endpoint}",
            {"taxon": name, "type": "EXACT", "limit": 100, "offset": 0},
        )

        result = {}
        if data != {}:
            # Some portals return a list directly, while others wrap it in a 'results' dict.
            if isinstance(data, list):
                result = data[0] if len(data) > 0 else {}
            else:
                results = data.get("results") or []
                result = results[0] if len(results) > 0 else {}

        if result:
            print(f"[{self.portal_name}] '{endpoint}' returned results for '{name}'.")
        else:
            print(
                f"[{self.portal_name}] Search endpoint returned no results for '{name}'. Attempting autocomplete search."
            )
            # If the search endpoint returned nothing, attempt to resolve via autocomplete.
            items = self._fetch_JSON(
                f"{self.BASE_URL}/taxa/taxonomy/rpc/gettaxasuggest.php",
                {"term": name},
            )
            for item in items if isinstance(items, list) else []:
                label = item["label"]
                if re.match(rf"^{re.escape(name)}(\s|$)", label):
                    print(
                        f"[{self.portal_name}] Found match for '{name}' via autocomplete."
                    )
                    result = item
                    break

        if not result:
            print(
                f"[{self.portal_name}] All searches failed or returned no results for '{name}'."
            )
            return {}

        tid = result.get("tid", "")
        if not tid:
            return {}
        taxon = self._fetch_JSON(f"{self.BASE_URL}/api/v2/taxonomy/{tid}")
        return taxon if taxon else {}

    def _fetch_synonym_data(self, accepted_id: str) -> str:
        """
        Fetch the accepted taxon's taxa page HTML from ``/taxa/index.php``.

        Parameters
        ----------
        accepted_id : str
            Internal ``tid`` of the accepted taxon, as resolved by
            ``get_synonyms`` via ``_extract_internal_accepted_id``.

        Returns
        -------
        str
            Raw HTML of the accepted taxon's taxa page, or ``""`` on error.
        """
        return self._fetch_HTML(
            url=f"{self.BASE_URL}/taxa/index.php",
            params={"tid": accepted_id},
            timeout=30,
        )

    def _fetch_accepted_data(self, accepted_id: str) -> dict:
        """
        Fetch the accepted taxon's full taxonomy record from ``api/v2/taxonomy/{id}``.

        Parameters
        ----------
        accepted_id : str
            Internal ``tid`` of the accepted taxon, as resolved by
            ``get_synonyms`` via ``_extract_internal_accepted_id``.

        Returns
        -------
        dict
            Parsed JSON from ``api/v2/taxonomy/{accepted_id}``, or ``{}`` on error.
        """
        return self._fetch_JSON(
            f"{self.BASE_URL}/api/v2/taxonomy/{accepted_id}"
        )  # TODO: add error handling for failed request

    def _compile_accepted(self, accepted_data: dict, accepted_id: str) -> list[dict]:
        """
        Build a pipeline-standard record for the accepted name from a Symbiota taxonomy record.

        Parameters
        ----------
        accepted_data : dict
            Full ``api/v2/taxonomy/{tid}`` record returned by ``_fetch_accepted_data``.
        accepted_id : str
            Internal ``tid`` of the accepted taxon, used for ``api_internal_id``
            and ``api_link``.

        Returns
        -------
        list of dict
            One-item list with the accepted name record, or ``[]`` if the name
            cannot be determined or is infraspecific.
        """
        name = normalize_query_string(
            accepted_data.get("sciname", "") or accepted_data.get("scientificName", "")
        )
        if not name or self._is_infraspecific(name):
            return []
        genus, species = self._extract_genus_species(name)
        taxonomy = self._extract_taxonomy(accepted_data)
        return [
            self._format_row(
                **{
                    "api_name": self.portal_name,
                    **taxonomy,
                    "genus": genus,
                    "species": species,
                    "api_internal_id": str(accepted_id),
                    "author": accepted_data.get("author", ""),
                    "original_source": accepted_data.get("source") or "",
                    "status": "Accepted",
                    "api_link": f"{self.BASE_URL}/taxa/index.php?tid={accepted_id}"
                    if accepted_id
                    else "",
                }
            )
        ]

    def _compile_synonyms(self, synonym_data: str, accepted_id: str) -> list[dict]:
        """
        Convert taxa page HTML into pipeline-standard synonym records.

        Delegates parsing to ``_extract_synonym_pairs``, deduplicates by
        canonical name, and strips leading ``", "`` from raw author strings.

        Parameters
        ----------
        synonym_data : str
            Raw HTML of the accepted taxon's taxa page as returned by
            ``_fetch_synonym_data``.
        accepted_id : str
            Internal ``tid`` of the accepted taxon.  Symbiota portals do not
            assign individual IDs to synonym records, so this value is used for
            both ``api_internal_id`` and ``api_link`` on every synonym row.

        Returns
        -------
        list of dict
            Pipeline-standard synonym records produced by ``_format_row``.
        """
        seen = set()
        results = []
        for raw_name, raw_author in self._extract_synonym_pairs(synonym_data):
            name = normalize_query_string(raw_name)
            if not name or self._is_infraspecific(name):
                continue
            if name not in seen:
                seen.add(name)
                genus, species = self._extract_genus_species(name)
                author = raw_author.lstrip(", ")
                results.append(
                    self._format_row(
                        **{
                            "api_name": self.portal_name,
                            "genus": genus,
                            "species": species,
                            "api_internal_id": str(
                                accepted_id
                            ),  # symbiota portals only have accepted ID
                            "author": author,
                            "status": "Synonym",
                            "api_link": f"{self.BASE_URL}/taxa/index.php?taxon={accepted_id}"
                            if accepted_id
                            else "",
                        }
                    )
                )
        return results

    def get_synonyms(self, name: str) -> pd.DataFrame:
        """
        Retrieve synonyms and accepted name for *name* from this Symbiota portal.

        Overrides the base-class orchestration to resolve the accepted taxon ID
        explicitly before calling the fetch methods, rather than storing it as
        side-effect state inside ``_fetch_synonym_data``.  The fetch sequence is:

        1. ``_fetch_query_data`` — search by scientific name, then fetch full
           ``api/v2/taxonomy/{tid}`` record in one step
        2. ``_extract_internal_accepted_id`` — read accepted ``tid`` (no API call)
        3. ``_fetch_synonym_data`` — taxa page HTML for the accepted taxon
        4. ``_fetch_accepted_data`` — full taxonomy record for the accepted taxon

        Parameters
        ----------
        name : str
            The scientific name to search (e.g. ``"Amanita muscaria"``).

        Returns
        -------
        pd.DataFrame
            Schema-validated synonym table, or an empty table if the name is
            not found or no rows can be compiled.
        """
        name = normalize_query_string(name)

        raw_data = self._fetch_query_data(name)
        if self._is_empty(raw_data):
            return empty_synonym_table()

        accepted_id = self._extract_internal_accepted_id(raw_data)
        if not accepted_id:
            return empty_synonym_table()

        synonym_data = self._fetch_synonym_data(accepted_id)
        if accepted_id == self._extract_internal_id(raw_data):
            accepted_data = raw_data
        else:
            accepted_data = self._fetch_accepted_data(accepted_id)

        accepted_rows = self._compile_accepted(accepted_data, accepted_id)
        synonym_rows = self._compile_synonyms(synonym_data, accepted_id)

        rows = accepted_rows + synonym_rows
        if not rows:
            return empty_synonym_table()
        return pd.DataFrame(rows)
