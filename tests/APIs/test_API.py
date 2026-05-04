"""
test_API.py — Generic contract tests for species synonym API functions.

All API scripts must accept a species name string and return dict[str, list]
where keys are synonym names and values are empty lists. Subclass
ApiContractTests and implement the four fixtures to apply all tests to a
new API.
"""

import re

import pytest

_RANK_ABBREV_PATTERN = re.compile(
    r"\b(var\.|subsp\.|ssp\.|f\.|fo\.|form\.|subg\.|subgen\.|sect\.|subsect\.|cv\.)\s",
    re.IGNORECASE,
)


class ApiContractTests:
    """
    Base class that enforces the output contract for every species synonym API.

    Subclasses must implement the four fixtures below; the tests are inherited
    automatically so no test code needs to be duplicated per-API.
    """

    # --- Required fixtures (override in subclass) ---

    @pytest.fixture
    def api_fn(self):
        """Return the callable under test, e.g. get_gbif_synonyms."""
        raise NotImplementedError("Subclass must provide the api_fn fixture.")

    @pytest.fixture
    def valid_species_with_synonyms(self):
        """Return a species name string known to have at least one synonym."""
        raise NotImplementedError

    @pytest.fixture
    def valid_species_no_synonyms(self):
        """Return a species name string known to exist but have no synonyms."""
        raise NotImplementedError

    # --- Optional fixture (override in subclass if applicable) ---
    @pytest.fixture
    def nonexistent_species(self):
        """Return a name string that does not exist in the API's database."""
        return "Aaaa bbbb"

    # --- Network health ---

    def test_call_does_not_raise_for_valid_species(
        self, api_fn, valid_species_with_synonyms
    ):
        """A valid species query must complete without raising any exception."""
        try:
            api_fn(valid_species_with_synonyms)
        except Exception as e:
            pytest.fail(f"API call raised an unexpected exception: {e}")

    def test_call_does_not_raise_for_nonexistent_species(
        self, api_fn, nonexistent_species
    ):
        """A nonexistent species query must complete without raising any exception."""
        try:
            api_fn(nonexistent_species)
        except Exception as e:
            pytest.fail(f"API call raised an unexpected exception: {e}")

    # --- Return-type contract ---

    def test_returns_dict(self, api_fn, valid_species_with_synonyms):
        """Return value must always be a dict."""
        result = api_fn(valid_species_with_synonyms)
        assert isinstance(result, dict)

    def test_all_keys_are_strings(self, api_fn, valid_species_with_synonyms):
        """Every key in the returned dict must be a non-empty string."""
        result = api_fn(valid_species_with_synonyms)
        for key in result:
            assert isinstance(key, str) and key.strip(), (
                f"Key {key!r} is not a non-empty string"
            )

    def test_all_values_are_empty_lists(self, api_fn, valid_species_with_synonyms):
        """Every value in the returned dict must be an empty list."""
        result = api_fn(valid_species_with_synonyms)
        for key, value in result.items():
            assert value == [], f"Value for {key!r} is {value!r}, expected []"

    # --- Key format ---

    def test_keys_have_no_surrounding_whitespace(
        self, api_fn, valid_species_with_synonyms
    ):
        """Keys must not have leading or trailing whitespace."""
        result = api_fn(valid_species_with_synonyms)
        for key in result:
            assert key == key.strip(), f"Key {key!r} has leading/trailing whitespace"

    def test_keys_are_binomial_names(self, api_fn, valid_species_with_synonyms):
        """Every key must be a binomial name (at least two words)."""
        result = api_fn(valid_species_with_synonyms)
        for key in result:
            assert len(key.split()) >= 2, f"Key {key!r} is not a binomial species name"

    def test_keys_contain_no_rank_abbreviations(
        self, api_fn, valid_species_with_synonyms
    ):
        """Keys must not contain infraspecific rank abbreviations (var., subsp., f., etc.)."""
        result = api_fn(valid_species_with_synonyms)
        for key in result:
            assert not _RANK_ABBREV_PATTERN.search(key), (
                f"Key {key!r} contains an infraspecific rank abbreviation"
            )

    # --- Valid species with synonyms ---

    def test_with_synonyms_returns_nonempty_dict(
        self, api_fn, valid_species_with_synonyms
    ):
        """A species that has synonyms should return a dict with at least one entry."""
        result = api_fn(valid_species_with_synonyms)
        assert len(result) >= 1

    def test_with_synonyms_query_name_is_key(self, api_fn, valid_species_with_synonyms):
        """The queried species name must appear as a key when the species is found."""
        result = api_fn(valid_species_with_synonyms)
        assert valid_species_with_synonyms in result, (
            f"Query name {valid_species_with_synonyms!r} not found in result keys: "
            f"{list(result.keys())}"
        )

    def test_with_synonyms_has_multiple_keys(self, api_fn, valid_species_with_synonyms):
        """A species known to have synonyms should return more than one key."""
        result = api_fn(valid_species_with_synonyms)
        assert len(result) > 1, (
            f"Expected synonyms for {valid_species_with_synonyms!r} but got only: "
            f"{list(result.keys())}"
        )

    def test_with_synonyms_no_duplicate_keys(self, api_fn, valid_species_with_synonyms):
        """Synonym keys must be unique (dict keys are inherently unique, but verify no
        synonym appears more than once under a different casing or spacing)."""
        result = api_fn(valid_species_with_synonyms)
        normalised = [k.strip().lower() for k in result]
        assert len(normalised) == len(set(normalised)), (
            "Duplicate synonym names found (case/whitespace-insensitive)"
        )

    # --- Valid species with no synonyms ---

    def test_no_synonyms_returns_dict_with_query(
        self, api_fn, valid_species_no_synonyms
    ):
        """A valid species with no synonyms should return a dict containing the query."""
        result = api_fn(valid_species_no_synonyms)
        assert isinstance(result, dict)
        assert valid_species_no_synonyms in result, (
            f"Expected {valid_species_no_synonyms!r} in result but got: "
            f"{list(result.keys())}"
        )

    def test_no_synonyms_only_query_key(self, api_fn, valid_species_no_synonyms):
        """A species with no synonyms should return exactly one key."""
        result = api_fn(valid_species_no_synonyms)
        assert result == {valid_species_no_synonyms: []}, (
            f"Expected {{{valid_species_no_synonyms!r}: []}} but got {result!r}"
        )

    # --- Nonexistent species ---

    def test_nonexistent_returns_empty_dict(self, api_fn, nonexistent_species):
        """A name not found in the API database should return an empty dict."""
        result = api_fn(nonexistent_species)
        assert result == {}, f"Expected {{}} for unknown species but got {result!r}"

    # --- Empty / blank input ---

    def test_empty_string_returns_empty_dict_or_raises(self, api_fn):
        """An empty string input should return {} or raise ValueError — never crash."""
        try:
            result = api_fn("")
            assert result == {}, f"Expected {{}} for empty input but got {result!r}"
        except ValueError:
            pass  # explicit validation is also acceptable

    def test_whitespace_string_returns_empty_dict_or_raises(self, api_fn):
        """A whitespace-only input should return {} or raise ValueError — never crash."""
        try:
            result = api_fn("   ")
            assert result == {}, (
                f"Expected {{}} for whitespace input but got {result!r}"
            )
        except ValueError:
            pass

    # --- Consistency ---

    def test_repeated_calls_return_same_keys(self, api_fn, valid_species_with_synonyms):
        """Two calls with the same input must return the same set of synonym keys."""
        result1 = api_fn(valid_species_with_synonyms)
        result2 = api_fn(valid_species_with_synonyms)
        assert set(result1.keys()) == set(result2.keys()), (
            "Two calls with the same input returned different synonym sets"
        )

    def test_lowercase_query_does_not_crash(self, api_fn, valid_species_with_synonyms):
        """A lowercase query must return a dict or raise ValueError — never crash."""
        try:
            result = api_fn(valid_species_with_synonyms.lower())
            assert isinstance(result, dict)
        except ValueError:
            pass
