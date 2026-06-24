"""
test_base_fetch.py — Error-handling and success-branch tests for the shared HTTP
fetch wrappers on ``SpeciesAPI`` (``scripts/apis_pipe/base.py``):
``_fetch``, ``_fetch_JSON``, ``_fetch_XML``, and ``_fetch_HTML``.

These wrappers are patched out by the per-API unit tests, so their real
behavior (network failure -> ``None``, parse failure -> empty fallback, success
-> parsed payload) is exercised nowhere else. This file fills that gap with a
hybrid approach:

- Real-HTTP cases (marked ``@pytest.mark.integration``, deselect with
  ``-m 'not integration'``) cover the network-failure and HTTP-status paths
  against live endpoints.
- Mocked cases (no marker, run offline) cover the parse-error and
  ``None``-propagation branches that real APIs will not reliably produce.

Run from the project root:
    pytest tests/integration/test_base_fetch.py -v          # all
    pytest tests/integration/test_base_fetch.py -v -m "not integration"  # offline subset
"""

import socket
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from scripts.apis_pipe.base import SpeciesAPI


class _Stub(SpeciesAPI):
    """Minimal concrete subclass so the abstract ``SpeciesAPI`` can be instantiated."""

    BASE_URL = "https://example.com"

    def _fetch_query_data(self, name):
        return {}

    def _fetch_synonym_data(self, raw_data):
        return {}

    def _fetch_accepted_data(self, raw_data, synonym_data):
        return {}

    def _compile_synonyms(self, synonym_data):
        return []

    def _compile_accepted(self, accepted_data):
        return []


class _FakeResponse:
    """Stand-in for ``requests.Response`` exposing only what the wrappers read."""

    def __init__(self, text="", json_value=None, json_exc=None):
        self.text = text
        self._json_value = json_value if json_value is not None else {}
        self._json_exc = json_exc

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_value


@pytest.fixture
def client():
    return _Stub()


@pytest.fixture
def require_internet():
    """Skip the requesting test if the machine has no network access."""
    try:
        socket.setdefaulttimeout(5)
        socket.create_connection(("8.8.8.8", 53))
    except OSError:
        pytest.skip("No internet connection — skipping live HTTP test.")


# A reserved-but-non-routable RFC 5737 (TEST-NET-3) address; connections hang
# then time out, exercising the network-error branch of _fetch.
_UNROUTABLE_URL = "http://203.0.113.1/"
# Stable endpoints used for the success/HTTP-error branches.
_HTML_URL = "https://example.com"
_JSON_URL = "https://api.gbif.org/v1/species/match"
_NOT_FOUND_URL = "https://api.gbif.org/v1/this-endpoint-does-not-exist"


# ---------------------------------------------------------------------------
# Real-HTTP cases (network-failure and HTTP-status paths)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_returns_none_on_connection_error(client, require_internet):
    """A request to an unroutable host times out and _fetch returns None."""
    assert client._fetch(_UNROUTABLE_URL, timeout=2) is None


@pytest.mark.integration
def test_fetch_returns_none_on_http_error(client, require_internet):
    """A 4xx response makes raise_for_status fire and _fetch returns None."""
    assert client._fetch(_NOT_FOUND_URL) is None


@pytest.mark.integration
def test_fetch_json_success_returns_dict(client, require_internet):
    """A live JSON endpoint is parsed into a non-empty dict."""
    result = client._fetch_JSON(_JSON_URL, params={"name": "Amanita muscaria"})
    assert isinstance(result, dict)
    assert result != {}


@pytest.mark.integration
def test_fetch_html_success_returns_text(client, require_internet):
    """A live HTML page is returned as a non-empty string."""
    result = client._fetch_HTML(_HTML_URL)
    assert isinstance(result, str)
    assert "Example" in result


# ---------------------------------------------------------------------------
# Mocked cases (parse-error and None-propagation branches; run offline)
# ---------------------------------------------------------------------------


def test_fetch_json_returns_empty_dict_when_fetch_fails(client):
    with patch.object(client, "_fetch", return_value=None):
        assert client._fetch_JSON("http://x") == {}


def test_fetch_json_success_parses_response(client):
    fake = _FakeResponse(json_value={"key": "value"})
    with patch.object(client, "_fetch", return_value=fake):
        assert client._fetch_JSON("http://x") == {"key": "value"}


def test_fetch_json_propagates_malformed_body_error(client):
    """Current behavior: _fetch_JSON does NOT guard response.json(), so a 2xx
    response with a malformed body raises rather than returning {}. Unlike
    _fetch_XML (which catches ParseError). Flagged for a possible source guard."""
    fake = _FakeResponse(json_exc=ValueError("No JSON object could be decoded"))
    with patch.object(client, "_fetch", return_value=fake):
        with pytest.raises(ValueError):
            client._fetch_JSON("http://x")


def test_fetch_xml_returns_empty_element_when_fetch_fails(client):
    with patch.object(client, "_fetch", return_value=None):
        result = client._fetch_XML("http://x")
    assert isinstance(result, ET.Element)
    assert client._is_empty(result)


def test_fetch_xml_returns_empty_element_on_parse_error(client):
    fake = _FakeResponse(text="<not valid xml")
    with patch.object(client, "_fetch", return_value=fake):
        result = client._fetch_XML("http://x")
    assert isinstance(result, ET.Element)
    assert client._is_empty(result)


def test_fetch_xml_success_parses_root(client):
    fake = _FakeResponse(text="<root><child/></root>")
    with patch.object(client, "_fetch", return_value=fake):
        result = client._fetch_XML("http://x")
    assert result.tag == "root"
    assert len(result) == 1


def test_fetch_html_returns_empty_string_when_fetch_fails(client):
    with patch.object(client, "_fetch", return_value=None):
        assert client._fetch_HTML("http://x") == ""


def test_fetch_html_success_returns_text(client):
    fake = _FakeResponse(text="<html><body>hi</body></html>")
    with patch.object(client, "_fetch", return_value=fake):
        assert client._fetch_HTML("http://x") == "<html><body>hi</body></html>"
