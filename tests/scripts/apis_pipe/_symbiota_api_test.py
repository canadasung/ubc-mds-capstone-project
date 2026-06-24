"""
Shared base test class for Symbiota portal API clients.

Symbiota uses one ``SymbiotaAPI`` class instantiated per portal, so unlike the
other per-API tests there are many portals sharing one implementation. This
class extends ``BaseApiTest`` and overrides only what differs for Symbiota:

- ``_make_client`` — ``SymbiotaAPI`` requires a ``portal_name`` argument.
- ``_queries`` — Symbiota queries live in ``SYMBIOTA_QUERIES`` keyed by slug.
- ``fixture_key`` — fixtures live under ``symbiota/<slug>/<scenario>/``.

``SymbiotaAPI.get_synonyms`` is a custom orchestrator but still calls the same
three fetch methods ``BaseApiTest._run`` patches, so the inherited template
tests work without overriding ``_run``.

Not collected by pytest directly (no ``Test`` prefix). Each per-portal file in
``test_symbiota/`` defines a ``Test<Portal>`` subclass setting ``slug`` and
``portal_name``.
"""

from __future__ import annotations

from scripts.apis_pipe.symbiota import SymbiotaAPI
from tests.fixtures.queries import SYMBIOTA_QUERIES
from tests.scripts.apis_pipe._base_api_test import BaseApiTest


class BaseSymbiotaApiTest(BaseApiTest):
    slug: str
    portal_name: str

    @property
    def fixture_key(self) -> str:  # type: ignore[override]
        return f"symbiota/{self.slug}"

    def _queries(self) -> dict[str, str]:
        return SYMBIOTA_QUERIES[self.slug]

    def _make_client(self) -> SymbiotaAPI:
        return SymbiotaAPI(self.portal_name)
