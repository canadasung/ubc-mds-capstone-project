from scripts.utils.normalize_query_string import normalize_query_string


class TestNormalizeQueryString:

    # 1. All-lowercase input gets first letter capitalized
    def test_all_lower(self):
        assert normalize_query_string("amanita muscaria") == "Amanita muscaria"

    # 2. All-uppercase input is fully lowercased then capitalized
    def test_all_upper(self):
        assert normalize_query_string("AMANITA MUSCARIA") == "Amanita muscaria"

    # 3. Mixed-case input is normalized the same way
    def test_mixed_case(self):
        assert normalize_query_string("AMANITA Muscaria") == "Amanita muscaria"

    # 4. Leading whitespace is stripped
    def test_leading_whitespace(self):
        assert normalize_query_string("  amanita muscaria") == "Amanita muscaria"

    # 5. Trailing whitespace is stripped
    def test_trailing_whitespace(self):
        assert normalize_query_string("amanita muscaria  ") == "Amanita muscaria"

    # 6. Multiple internal spaces are collapsed to one
    def test_internal_extra_whitespace(self):
        assert normalize_query_string("amanita   muscaria") == "Amanita muscaria"

    # 7. Tabs and mixed whitespace are treated the same as spaces
    def test_tabs_and_mixed_whitespace(self):
        assert normalize_query_string("amanita  \t muscaria") == "Amanita muscaria"

    # 8. Already-normalized input is returned unchanged
    def test_already_normalized(self):
        assert normalize_query_string("Amanita muscaria") == "Amanita muscaria"

    # Below are unusual tests as we normally just expect 2 words
    # But in theory, it should still capitalize 1st letter and
    # remove any extra white spaces

    # 9. Single-word genus input is capitalized correctly
    def test_single_word_genus(self):
        assert normalize_query_string("AMANITA") == "Amanita"

    # 10. Three-part name (e.g. with variety) is handled correctly
    def test_three_part_name(self):
        assert normalize_query_string("amanita muscaria var. alba") == "Amanita muscaria var. alba"

    # 11. Three-part name with mixed case and extra whitespace is fully normalized
    def test_three_part_name_uppercase_mixed(self):
        assert normalize_query_string("  AMANITA   MUSCARIA VAR. \tALBA ") == "Amanita muscaria var. alba"
