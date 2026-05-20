"""
This module defines the foundational architecture and abstract blueprint for the 
project's biodiversity data aggregation pipeline. 

It establishes a strict contract (the `SpeciesAPI` base class) that all external 
database connectors must adhere to. By enforcing standardized methods and consistent 
output formats, it ensures the broader application can seamlessly query multiple, 
vastly different biological databases without needing to handle their individual 
structural quirks.

This file is not meant to be executed directly or instantiated on its own. Instead, 
it serves as the structural foundation that concrete API clients (such as the GBIF 
or Symbiota connectors) must inherit from and implement.
"""

from abc import ABC, abstractmethod


class SpeciesAPI(ABC):
    """
    Abstract base class establishing a unified contract for biodiversity database clients.

    This blueprint mandates that any integrated database client (e.g., GBIF, Symbiota) 
    must implement three core methods and return data in strictly standardized formats.
    """

    @abstractmethod
    def search(self, name: str):
        """
        Queries the primary taxonomic backbone for a precise match.

        Args:
            name (str): The scientific name to search (e.g., "Amanita muscaria").

        Returns:
            dict | xml.etree.ElementTree.Element: The parsed database response 
                containing the internal ID or taxonomy resolution for the name.
        """
        pass

    @abstractmethod
    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieves taxonomic synonyms and their associated publication metadata.

        Args:
            name (str): The primary accepted scientific name or target query.

        Returns:
            list[dict]: A list of dictionaries containing the synonyms. Clients
                MUST strive to return the following strict metadata keys (using
                empty strings if the specific database lacks the data):
                [
                    {
                        "canonicalName": "Amanita muscaria",
                        "author": "(L.) Lam.",
                        "date": "1783",
                        "publishedIn": "Encycl. Méth. Bot. 1(1): 111",
                        "url": "https://www.database.org/taxon/123"
                    },
                    ...
                ]
        """
        pass

    @abstractmethod
    def occurrences(self, name: str, limit: int = 20) -> list[dict]:
        """
        Retrieves physical occurrence records formatted to Darwin Core standards.

        Args:
            name (str): The scientific name to query.
            limit (int, optional): Maximum number of records to return. Defaults to 20.

        Returns:
            list[dict]: A list of occurrence records. Clients must format keys using 
                standard Darwin Core terms (e.g., 'decimalLatitude') and append a 
                custom 'top_3_images' array containing up to 3 image URL strings.
        """
        pass