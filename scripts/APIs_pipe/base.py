# All API clients follow the same structure

from abc import ABC, abstractmethod


class SpeciesAPI(ABC):
    """
    Abstract base class defining a unified interface for all biodiversity APIs.

    This blueprint enforces a strict contract: any database client added to the
    pipeline (e.g., GBIF, Symbiota, Tropicos) must implement these three core
    methods and return data in the standardized formats defined below.
    """

    @abstractmethod
    def search(self, name: str):
        """
        Query the primary backbone taxonomy to find a precise taxonomic match.

        Args:
            name (str): The scientific name to search for (e.g., "Amanita muscaria").

        Returns:
            dict | xml.etree.ElementTree.Element: The parsed response data containing
                the database's internal ID or taxonomy resolution for the name.
        """
        pass

    @abstractmethod
    def occurrences(self, name: str, limit: int = 20) -> list[dict]:
        """
        Retrieve physical occurrence records (specimens, observations) for a taxon.

        Args:
            name (str): The scientific name to query.
            limit (int, optional): Maximum number of records to return. Defaults to 20.

        Returns:
            list[dict]: A list of occurrence records. Whenever possible, clients
                should format keys using standard Darwin Core terms (e.g.,
                'decimalLatitude') AND include a custom 'top_3_images' key containing
                a list of up to 3 image URL strings.
        """
        pass

    @abstractmethod
    def synonyms(self, name: str) -> list[dict]:
        """
        Retrieve taxonomic synonyms and their associated publication metadata.

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
