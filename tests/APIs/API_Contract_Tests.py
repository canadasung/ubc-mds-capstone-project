"""
test_API.py — Generic contract tests for species synonym API functions.

All API scripts must accept a species name string and return dict[str, list]
where keys are synonym names and values are empty lists. Subclass
ApiContractTests and implement the four fixtures to apply all tests to a
new API.
"""

import re

import pytest
import requests.exceptions

_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

_RANK_ABBREV_PATTERN = re.compile(
    r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|form\.|subg\.|subgen\.|sect\.|subsect\.|cv\.)\s",
    re.IGNORECASE,
)


class ApiContractTests:
    """
    Base class that enforces the output contract for every species synonym API.

    Subclasses must implement the four fixtures below; the tests are inherited
    automatically so no test code needs to be duplicated per-API.

    API responses are cached at class scope: each distinct input is fetched
    exactly once per test class, minimising network calls.
    """

    # --- Required fixtures (override in subclass with scope="class") ---

    @pytest.fixture(scope="class")
    def api_fn(self):
        """Return the callable under test, e.g. get_gbif_synonyms."""
        raise NotImplementedError("Subclass must provide the api_fn fixture.")

    @pytest.fixture(scope="class")
    def valid_species_with_synonyms(self):
        """Return a species name string known to have at least one synonym. The species name string should be capitalized in the standard binomial format, i.e. "Genus species"."""
        raise NotImplementedError

    @pytest.fixture(scope="class")
    def valid_species_no_synonyms(self):
        """Return a species name string known to exist but have no synonyms. The species name string should be capitalized in the standard binomial format, i.e. "Genus species"."""
        raise NotImplementedError

    # --- Optional fixture (override in subclass with scope="class" if applicable) ---

    @pytest.fixture(scope="class")
    def nonexistent_species(self):
        """Return a name string that does not exist in the API's database."""
        return "Aaaa bbbb"

    # --- Cached API results (one network call each per test class) ---

    @pytest.fixture(scope="class")
    def _result_with_synonyms(self, api_fn, valid_species_with_synonyms):
        """Call the API with valid_species_with_synonyms and cache the result."""
        try:
            return api_fn(valid_species_with_synonyms)
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")

    @pytest.fixture(scope="class")
    def _result_no_synonyms(self, api_fn, valid_species_no_synonyms):
        """Call the API with valid_species_no_synonyms and cache the result."""
        try:
            return api_fn(valid_species_no_synonyms)
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")

    @pytest.fixture(scope="class")
    def _result_nonexistent(self, api_fn, nonexistent_species):
        """Call the API with nonexistent_species and cache the result."""
        try:
            return api_fn(nonexistent_species)
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")

    # --- Network health ---

    def test_call_does_not_raise_for_valid_species(self, _result_with_synonyms):
        """A valid species query must complete without raising any exception."""
        assert isinstance(_result_with_synonyms, dict)

    def test_call_does_not_raise_for_nonexistent_species(self, _result_nonexistent):
        """A nonexistent species query must complete without raising any exception."""
        assert isinstance(_result_nonexistent, dict)

    # --- Return-type contract ---

    def test_returns_dict(self, _result_with_synonyms):
        """Return value must always be a dict."""
        assert isinstance(_result_with_synonyms, dict)

    def test_all_keys_are_strings(self, _result_with_synonyms):
        """Every key in the returned dict must be a non-empty string."""
        for key in _result_with_synonyms:
            assert isinstance(key, str) and key.strip(), (
                f"Key {key!r} is not a non-empty string"
            )

    def test_all_values_are_empty_lists(self, _result_with_synonyms):
        """Every value in the returned dict must be an empty list."""
        for key, value in _result_with_synonyms.items():
            assert value == [], f"Value for {key!r} is {value!r}, expected []"

    # --- Key format ---

    def test_keys_have_no_surrounding_whitespace(self, _result_with_synonyms):
        """Keys must not have leading or trailing whitespace."""
        for key in _result_with_synonyms:
            assert key == key.strip(), f"Key {key!r} has leading/trailing whitespace"

    def test_keys_are_binomial_names(self, _result_with_synonyms):
        """Every key must be a binomial name (at least two words)."""
        for key in _result_with_synonyms:
            assert len(key.split()) >= 2, f"Key {key!r} is not a binomial species name"

    def test_keys_contain_no_rank_abbreviations(self, _result_with_synonyms):
        """Keys must not contain infraspecific rank abbreviations (var., subsp., f., etc.)."""
        for key in _result_with_synonyms:
            assert not _RANK_ABBREV_PATTERN.search(key), (
                f"Key {key!r} contains an infraspecific rank abbreviation"
            )

    # --- Valid species with synonyms ---

    def test_with_synonyms_has_multiple_keys(
        self, _result_with_synonyms, valid_species_with_synonyms
    ):
        """A species known to have synonyms should return more than one key."""
        assert len(_result_with_synonyms) > 1, (
            f"Expected synonyms for {valid_species_with_synonyms!r} but got only: "
            f"{list(_result_with_synonyms.keys())}"
        )

    def test_with_synonyms_query_name_is_key(
        self, _result_with_synonyms, valid_species_with_synonyms
    ):
        """The queried species name must appear as a key when the species is found."""
        assert valid_species_with_synonyms in _result_with_synonyms, (
            f"Query name {valid_species_with_synonyms!r} not found in result keys: "
            f"{list(_result_with_synonyms.keys())}"
        )

    def test_with_synonyms_no_duplicate_keys(self, _result_with_synonyms):
        """Synonym keys must be unique (dict keys are inherently unique, but verify no
        synonym appears more than once under a different casing or spacing)."""
        normalised = [k.strip().lower() for k in _result_with_synonyms]
        assert len(normalised) == len(set(normalised)), (
            "Duplicate synonym names found (case/whitespace-insensitive)"
        )

    # --- Valid species with no synonyms ---

    def test_no_synonyms_only_query_key(
        self, _result_no_synonyms, valid_species_no_synonyms
    ):
        """A species with no synonyms should return exactly one key."""
        assert _result_no_synonyms == {valid_species_no_synonyms: []}, (
            f"Expected {{{valid_species_no_synonyms!r}: []}} but got {_result_no_synonyms!r}"
        )

    # --- Nonexistent species ---

    def test_nonexistent_returns_empty_dict(self, _result_nonexistent):
        """A name not found in the API database should return an empty dict."""
        assert _result_nonexistent == {}, (
            f"Expected {{}} for unknown species but got {_result_nonexistent!r}"
        )

    # --- Empty / blank input (no network calls — API returns early for these) ---

    def test_empty_string_returns_empty_dict_or_raises(self, api_fn):
        """An empty string input should return {} or raise ValueError. It should never crash with an unhandled exception."""
        try:
            result = api_fn("")
            assert result == {}, f"Expected {{}} for empty input but got {result!r}"
        except ValueError:
            pass  # explicit validation is also acceptable

    def test_whitespace_string_returns_empty_dict_or_raises(self, api_fn):
        """A whitespace-only input should return {} or raise ValueError. It should never crash with an unhandled exception."""
        try:
            result = api_fn("   ")
            assert result == {}, (
                f"Expected {{}} for whitespace input but got {result!r}"
            )
        except ValueError:
            pass

    # --- Consistency ---

    def test_repeated_calls_return_same_keys(
        self, api_fn, _result_with_synonyms, valid_species_with_synonyms
    ):
        """Two calls with the same input must return the same set of synonym keys."""
        try:
            second_result = api_fn(valid_species_with_synonyms)
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")
        assert set(_result_with_synonyms.keys()) == set(second_result.keys()), (
            "Two calls with the same input returned different synonym sets"
        )

    # --- Case insensitivity and whitespace ---

    def test_lowercase_query_returns_same_keys(
        self, api_fn, _result_with_synonyms, valid_species_with_synonyms
    ):
        """A lowercase query must return the same synonym keys as the canonical query."""
        try:
            result = api_fn(valid_species_with_synonyms.lower())
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")
        assert set(result.keys()) == set(_result_with_synonyms.keys()), (
            "Lowercase query returned different keys than canonical query"
        )

    def test_uppercase_query_returns_same_keys(
        self, api_fn, _result_with_synonyms, valid_species_with_synonyms
    ):
        """An uppercase query must return the same synonym keys as the canonical query."""
        try:
            result = api_fn(valid_species_with_synonyms.upper())
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")
        assert set(result.keys()) == set(_result_with_synonyms.keys()), (
            "Uppercase query returned different keys than canonical query"
        )

    def test_extra_whitespace_query_returns_same_keys(
        self, api_fn, _result_with_synonyms, valid_species_with_synonyms
    ):
        """A query with extra surrounding whitespace must return the same synonym keys."""
        try:
            result = api_fn(f"  {valid_species_with_synonyms}  ")
        except _NETWORK_ERRORS as e:
            pytest.skip(f"API unreachable: {e}")
        assert set(result.keys()) == set(_result_with_synonyms.keys()), (
            "Query with extra whitespace returned different keys than canonical query"
        )
