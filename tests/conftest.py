import os

import pytest


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
