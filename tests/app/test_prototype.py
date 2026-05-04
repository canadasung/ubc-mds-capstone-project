"""
test_prototype.py — Headless tests for the Streamlit prototype app.

Uses Streamlit's built-in AppTest runner (streamlit.testing.v1), which
executes the app without a browser. GenBank tests are skipped when
ENTREZ_EMAIL is not set.

Run from the repo root:
    pytest tests/app/test_prototype.py -v
"""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).parents[2] / "app" / "prototype.py")

requires_email = pytest.mark.skipif(
    not os.environ.get("ENTREZ_EMAIL"),
    reason="ENTREZ_EMAIL not set — GenBank tests require a configured .env file",
)


def _make_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60)


# --- Startup ---


def test_app_starts_without_exception():
    """App must load and render its initial state without any exception."""
    at = _make_app()
    at.run()
    assert not at.exception


def test_app_has_search_input():
    """App must render a text input for the species name query."""
    at = _make_app()
    at.run()
    assert len(at.text_input) >= 1


# --- No query ---


def test_no_query_shows_no_results():
    """With no query entered the app must not display a dataframe."""
    at = _make_app()
    at.run()
    assert len(at.dataframe) == 0


# --- No sources selected ---


def test_no_sources_selected_shows_warning():
    """Deselecting all sources and entering a query must show a warning."""
    at = _make_app()
    at.run()
    # Uncheck all three source checkboxes
    for cb in at.checkbox:
        cb.uncheck()
    at.text_input[0].set_value("Amanita muscaria").run()
    assert len(at.warning) >= 1


# --- GBIF only (no auth required) ---


def test_valid_species_gbif_no_exception():
    """A valid species query against GBIF only must complete without exception."""
    at = _make_app()
    at.run()
    # Uncheck GenBank and MushroomObserver, keep GBIF
    for cb in at.checkbox:
        if "GenBank" in str(cb.label) or "Mushroom" in str(cb.label):
            cb.uncheck()
    at.text_input[0].set_value("Amanita muscaria").run()
    assert not at.exception


def test_valid_species_gbif_returns_dataframe():
    """A valid species query against GBIF must render a results dataframe."""
    at = _make_app()
    at.run()
    for cb in at.checkbox:
        if "GenBank" in str(cb.label) or "Mushroom" in str(cb.label):
            cb.uncheck()
    at.text_input[0].set_value("Amanita muscaria").run()
    assert not at.exception
    assert len(at.dataframe) >= 1


def test_nonexistent_species_gbif_shows_no_results():
    """A nonexistent species query against GBIF must show the no-results message."""
    at = _make_app()
    at.run()
    for cb in at.checkbox:
        if "GenBank" in str(cb.label) or "Mushroom" in str(cb.label):
            cb.uncheck()
    at.text_input[0].set_value("Aaaa bbbb").run()
    assert not at.exception
    assert len(at.dataframe) == 0
    assert len(at.markdown) >= 1


# --- All sources (requires ENTREZ_EMAIL for GenBank) ---


@requires_email
def test_valid_species_all_sources_no_exception():
    """A valid species query against all sources must complete without exception."""
    at = _make_app()
    at.run()
    at.text_input[0].set_value("Amanita muscaria").run()
    assert not at.exception


@requires_email
def test_valid_species_all_sources_returns_dataframe():
    """A valid species query against all sources must render a results dataframe."""
    at = _make_app()
    at.run()
    at.text_input[0].set_value("Amanita muscaria").run()
    assert not at.exception
    assert len(at.dataframe) >= 1
