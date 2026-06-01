"""tropicos.py — Tropicos API client.

Concrete SpeciesAPI implementation for Tropicos, the botanical database maintained
by the Missouri Botanical Garden. Tropicos requires a registered API key (loaded
from TROPICOS_API_KEY) and uses a relational model: names must first be resolved
to an internal NameId before taxonomic data can be queried.

Main entry point: TropicosAPI().synonyms(name)
"""

import os

from dotenv import load_dotenv

from scripts.utils.normalize_strings import normalize_scientific_name
from tests.APIs_pipe.test_env_configured import _PLACEHOLDER_TROPICOS

from .base import SpeciesAPI

load_dotenv()  # Load TROPICOS_API_KEY from .env


class TropicosAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Tropicos database.

    Tropicos is maintained by the Missouri Botanical Garden and focuses heavily
    on botanical (plant) data. Unlike open APIs, Tropicos requires a registered
    API key for all requests.
    """

    BASE = "http://services.tropicos.org"

    def __init__(self):
        """
        Load the registered Tropicos API key from the TROPICOS_API_KEY environment variable set in the
        `.env` file.

        Raises:
            ValueError: If the TROPICOS_API_KEY
                environment variable is missing.
        """
        self.key = os.getenv("TROPICOS_API_KEY")
        if not self.key or self.key == _PLACEHOLDER_TROPICOS:
            raise ValueError(
                "Tropicos API key not provided. Set TROPICOS_API_KEY in the `.env` file."
            )

    def _search(self, name: str) -> dict:
        """
        Search the Tropicos database for a given query.

        Args:
            name (str): The scientific name to search for.

        Returns:
            dict: A raw JSON response from the /Name/Search endpoint.
        """

        name = normalize_scientific_name(name)

        return self._fetch_JSON(
            f"{self.BASE}/Name/Search",
            params={
                "name": name,
                "type": "exact",
                "apikey": self.key,
                "format": "json",
            },
        )

        # TODO: what does first look like? The search function should be extracting any information itself, just returning raw search results, so let's see if we can return `first` instead of this extraction.
        # if isinstance(results, list) and len(results) > 0:
        #     first = results[0]
        #     if "NameId" in first:
        #         return {
        #             "name": first.get("ScientificName", name),
        #             "matchType": "EXACT",
        #             "key": first.get("NameId"),
        #         }
        # else:
        #     print("No results.")
        #     return {}

    def _

    def _extract_internal_accepted_id(self, name: str):
        # Note: double check that tropicos does not have an accepted ID link so only need to return the internal id
        return self._search(name)["key"]

    def get_synonyms(self, name: str) -> list[dict]:
        """
        Retrieve a pipeline-standard list of taxonomic synonyms for a plant species.

        Args:
            name (str): The scientific name of the plant.

        Returns:
            list[dict]: A list of synonym dictionaries formatted for the pipeline.
        """

        # Fetch synonym data
        synonym_data = self._fetch_JSON(
            f"{self.BASE}/Name/{self._extract_internal_accepted_id(name)}/Synonyms",
            params={
                "apikey": self.key,
                "format": "json",
            },
        )

        # For ea
        candidates = []
        seen = set()  # track seen synonyms to prevent duplicates
        for item in synonym_data:
            # Tropicos nests the actual synonym data under "SynonymName"
            syn_info = item.get("SynonymName", {})
            syn_name = syn_info.get("ScientificName")
            if not syn_name:
                continue
            if syn_name not in seen:
                seen.add(syn_name)
                syn_id = syn_info.get("NameId")
                candidates.append(
                    self._format_synonym(
                        name=syn_name,
                        author=syn_info.get("Author", ""),
                        api_link=f"https://www.tropicos.org/name/{syn_id}"
                        if syn_id
                        else "",
                    )
                )

        return candidates
