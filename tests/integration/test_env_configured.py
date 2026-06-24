"""
test_env_configured.py — Verify the .env file exists and all required
environment variables are filled in with real (non-placeholder) values.

Run from the project root:
    pytest tests/integration/test_env_configured.py -v
"""

import os
import re
from pathlib import Path

import pytest
from dotenv import load_dotenv

from scripts.config import TROPICOS_API_KEY_PLACEHOLDER

# Load .env from the project root before any assertions
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

load_dotenv(_ENV_FILE)

# This is a local/live-environment diagnostic: it requires a real .env file on
# disk, which CI does not have (CI passes credentials as env vars). Mark the
# whole module integration so `-m "not integration"` (the PR job) skips it.
pytestmark = pytest.mark.integration

# Placeholder values copied from .env.example — these must be replaced
_PLACEHOLDER_EMAIL = "your_email@example.com"
_PLACEHOLDER_TROPICOS = TROPICOS_API_KEY_PLACEHOLDER

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# .env file presence
# ---------------------------------------------------------------------------


def test_env_file_exists():
    """
    Verify that a ``.env`` file exists at the project root.

    Raises
    ------
    AssertionError
        If ``_ENV_FILE`` does not exist, with a message directing the user to
        copy ``.env.example`` and fill in their credentials.
    """
    assert _ENV_FILE.exists(), (
        f".env file not found at {_ENV_FILE}. "
        "Copy .env.example to .env and fill in your credentials."
    )


# ---------------------------------------------------------------------------
# ENTREZ_EMAIL
# ---------------------------------------------------------------------------


def test_entrez_email_is_set():
    """
    Verify that ``ENTREZ_EMAIL`` is present and non-empty in the environment.

    Raises
    ------
    AssertionError
        If ``ENTREZ_EMAIL`` is not set or is an empty string.
    """
    email = os.getenv("ENTREZ_EMAIL", "")
    assert email, (
        "ENTREZ_EMAIL is not set in .env. "
        "NCBI requires an email address when using the Entrez (GenBank) API."
    )


def test_entrez_email_is_not_placeholder():
    """
    Verify that ``ENTREZ_EMAIL`` has been changed from its placeholder value.

    Raises
    ------
    AssertionError
        If ``ENTREZ_EMAIL`` equals ``_PLACEHOLDER_EMAIL``.
    """
    email = os.getenv("ENTREZ_EMAIL", "")
    assert email != _PLACEHOLDER_EMAIL, (
        f"ENTREZ_EMAIL is still the placeholder value ({_PLACEHOLDER_EMAIL!r}). "
        "Replace it with your real email address in .env."
    )


def test_entrez_email_looks_valid():
    """
    Verify that ``ENTREZ_EMAIL`` matches a basic email address format.

    Skipped if ``ENTREZ_EMAIL`` is unset or still the placeholder value, so
    that format errors are not reported before the more fundamental checks pass.

    Raises
    ------
    AssertionError
        If ``ENTREZ_EMAIL`` does not match ``_EMAIL_RE`` (``user@domain.tld``).
    """
    email = os.getenv("ENTREZ_EMAIL", "")
    if not email or email == _PLACEHOLDER_EMAIL:
        pytest.skip(
            "Skipping format check — ENTREZ_EMAIL not set or is still placeholder"
        )
    assert _EMAIL_RE.match(email), (
        f"ENTREZ_EMAIL {email!r} does not look like a valid email address (expected user@domain.tld)."
    )


# ---------------------------------------------------------------------------
# TROPICOS_API_KEY
# ---------------------------------------------------------------------------


def test_tropicos_api_key_is_set():
    """
    Verify that ``TROPICOS_API_KEY`` is present and non-empty in the environment.

    Raises
    ------
    AssertionError
        If ``TROPICOS_API_KEY`` is not set or is an empty string.
    """
    key = os.getenv("TROPICOS_API_KEY", "")
    assert key, (
        "TROPICOS_API_KEY is not set in .env. "
        "Register at https://services.tropicos.org/help?requestkey to get a free key."
    )


def test_tropicos_api_key_is_not_placeholder():
    """
    Verify that ``TROPICOS_API_KEY`` has been changed from its placeholder value.

    Raises
    ------
    AssertionError
        If ``TROPICOS_API_KEY`` equals ``_PLACEHOLDER_TROPICOS``.
    """
    key = os.getenv("TROPICOS_API_KEY", "")
    assert key != _PLACEHOLDER_TROPICOS, (
        f"TROPICOS_API_KEY is still the placeholder value ({_PLACEHOLDER_TROPICOS!r}). "
        "Register at https://services.tropicos.org/help?requestkey to get a free key."
    )
