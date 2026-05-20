"""
This module serves as the dedicated connector between the application's data 
aggregation pipeline and the Global Biodiversity Information Facility (GBIF) API. 
It is a concrete, fully realized implementation of the `SpeciesAPI` blueprint.

The script acts as a translator, handling the specific routing and logic required 
to communicate with GBIF's REST endpoints. It automates the retrieval of exact 
taxonomic matches, resolves historical synonyms through secondary API routing, 
and extracts image-rich physical occurrence records. 

Crucially, this module shields the rest of the application from GBIF's complex, 
deeply-nested JSON structure. It scrubs the raw data, applies Darwin Core standards 
where necessary, and packages the results into clean, predictable dictionaries ready 
for immediate frontend display.
"""

import re

import requests

from .base import SpeciesAPI


class GBIFAPI(SpeciesAPI):
    """
    Concrete implementation of the SpeciesAPI for the Global Biodiversity Information Facility (GBIF).

    This client interacts directly with the GBIF REST API to perform taxonomic matching, 
    retrieve historical synonyms, and fetch physical occurrence records mapped to Darwin Core standards.
    """

    BASE = "https://api.gbif.org/v1"

    def search(self, name: str):
        """
        Query the GBIF backbone taxonomy to find a precise match for a species.

        Uses the '/species/match' endpoint with strict matching enabled.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict: The JSON response from GBIF containing match details, including
                the match type, taxonomic rank, and usage keys.
        """
        resp = requests.get(
            f"{self.BASE}/species/match", params={"name": name, "strict": "true"}
        )
        resp.raise_for_status()
        return resp.json()

    def _resolve_usage_key(self, match_data: dict) -> int:
        """
        Helper method to extract the correct GBIF usage key from match data.

        If the matched taxon is classified as a synonym, GBIF provides an
        'acceptedUsageKey' pointing to the currently accepted name. This method
        prioritizes the accepted key to ensure downstream queries use the valid taxon.

        Args:
            match_data (dict): The dictionary returned by the `search` method.

        Returns:
            int: The official numeric ID of the accepted name.
        """
        if "acceptedUsageKey" in match_data:
            return match_data["acceptedUsageKey"]
        return match_data["usageKey"]

    def synonyms(self, name: str):
        """
        Retrieve species-level synonyms and metadata for a given scientific name.

        This method first resolves the name to its accepted usage key, then queries
        the '/species/{key}/synonyms' endpoint. It filters the results to only include
        taxa at the 'SPECIES' rank, and extracts authorship, publication dates, and URLs.

        Args:
            name (str): The scientific name to query.

        Returns:
            list[dict]: A list of dictionaries containing the canonical names and
                associated metadata. The first item is always the currently accepted
                taxon, followed by any discovered synonyms.
                Example:
                [
                    {
                        "canonicalName": "Amanita muscaria",
                        "author": "(L.) Lam.",
                        "date": "1783",
                        "publishedIn": "Encycl. Méth. Bot. 1(1): 111",
                        "url": "https://www.gbif.org/species/3328328"
                    },
                    ...
                ]
        """
        match = self.search(name)
        if match.get("matchType") == "NONE":
            return []

        usage_key = match.get("acceptedUsageKey") or match["usageKey"]
        resp = requests.get(
            f"{self.BASE}/species/{usage_key}/synonyms", params={"limit": 500}
        )
        resp.raise_for_status()

        results = []

        # Helper to extract Year from authorship string
        def extract_year(authorship):
            if not authorship:
                return ""
            year_match = re.search(r"\b(17|18|19|20)\d{2}\b", authorship)
            return year_match.group(0) if year_match else ""

        # Format accepted name
        results.append(
            {
                "canonicalName": match.get("canonicalName") or name,
                "author": match.get("authorship", ""),
                "date": extract_year(match.get("authorship", "")),
                "publishedIn": match.get("publishedIn", ""),
                "url": f"https://www.gbif.org/species/{usage_key}",
            }
        )

        for item in resp.json().get("results", []):
            if item.get("rank") == "SPECIES" and item.get("canonicalName"):
                results.append(
                    {
                        "canonicalName": item["canonicalName"],
                        "author": item.get("authorship", ""),
                        "date": extract_year(item.get("authorship", "")),
                        "publishedIn": item.get("publishedIn", ""),
                        "url": f"https://www.gbif.org/species/{item.get('key')}",
                    }
                )
        return results

    def occurrences(self, name: str, limit: int = 20):
        """
        Retrieves a strictly mixed batch of occurrence records with images for a specific taxon from GBIF:
        90% Institutional Specimens and 10% Citizen Science observations.

        It explicitly filters for records containing 'StillImage' media, parses
        the media arrays, and extracts up to 3 image URLs into a custom
        'top_3_images' key for easy access by the frontend UI.

        Args:
            name (str): The scientific name of the species to search for.
            limit (int, optional): The maximum number of records to return.
                Defaults to 20.

        Returns:
            list[dict]: A list of occurrence records. Each record contains standard
                Darwin Core fields AND a custom 'top_3_images' key containing a
                list of up to 3 image URL strings.
        """
        institutional_limit = int(limit * 0.90)
        citizen_limit = limit - institutional_limit

        combined_records = []

        # --- Helper Function to Extract Images ---
        def process_and_extract_images(results_list):
            processed = []
            for occ in results_list:
                images = []
                for media in occ.get("media", []):
                    if media.get("type") == "StillImage" and media.get("identifier"):
                        images.append(media["identifier"])
                        if len(images) == 3:
                            break

                occ["top_3_images"] = images
                processed.append(occ)
            return processed

        # -----------------------------------------

        # 1. Query for Institutional Data (Museums, Herbaria, Universities)
        try:
            inst_resp = requests.get(
                f"{self.BASE}/occurrence/search",
                params={
                    "scientificName": name,
                    "limit": institutional_limit,
                    "hasCoordinate": "true",
                    "hasGeospatialIssue": "false",
                    "basisOfRecord": "PRESERVED_SPECIMEN",
                    "mediaType": "StillImage",  # Guarantee they have photos!
                },
            )
            inst_resp.raise_for_status()
            inst_data = inst_resp.json()

            if "results" in inst_data:
                # Process the images before adding them to our final list
                processed_inst = process_and_extract_images(inst_data["results"])
                combined_records.extend(processed_inst)
        except Exception as e:
            print(f"GBIF Institutional query failed: {e}")

        # 2. Query for Citizen Science Data (iNaturalist, Observation Networks)
        try:
            cit_resp = requests.get(
                f"{self.BASE}/occurrence/search",
                params={
                    "scientificName": name,
                    "limit": citizen_limit,
                    "hasCoordinate": "true",
                    "hasGeospatialIssue": "false",
                    "basisOfRecord": "HUMAN_OBSERVATION",
                    "mediaType": "StillImage",  # Guarantee they have photos!
                },
            )
            cit_resp.raise_for_status()
            cit_data = cit_resp.json()

            if "results" in cit_data:
                # Process the images before adding them to our final list
                processed_cit = process_and_extract_images(cit_data["results"])
                combined_records.extend(processed_cit)
        except Exception as e:
            print(f"GBIF Citizen Science query failed: {e}")

        # 3. Return the fully stitched, image-rich list to the aggregator
        return combined_records
