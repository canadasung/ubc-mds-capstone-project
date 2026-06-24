import os

import pytest

from scripts.config import TROPICOS_API_KEY_PLACEHOLDER


@pytest.fixture
def require_entrez_email():
    email = os.environ.get("ENTREZ_EMAIL", "")
    if not email or email == "your_email@example.com":
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail(
                "ENTREZ_EMAIL secret is not configured. "
                "Add it at: repository Settings → Secrets and variables → Actions → New repository secret"
            )
        else:
            pytest.skip("ENTREZ_EMAIL not set or is still the placeholder — tests require a real email address")


@pytest.fixture
def require_tropicos_api_key():
    key = os.environ.get("TROPICOS_API_KEY", "")
    if not key or key == TROPICOS_API_KEY_PLACEHOLDER:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail(
                "TROPICOS_API_KEY secret is not configured. "
                "Add it at: repository Settings → Secrets and variables → Actions → New repository secret"
            )
        else:
            pytest.skip("TROPICOS_API_KEY not set or is still the placeholder — tests require a real API key")
