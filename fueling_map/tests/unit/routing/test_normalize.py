"""Behavior spec for the shared (city, state) matching key (spec FR-001, data-model.md CityKey).

This is the one normalizer both `stations/pipeline.py` (offline build) and `routing/pipeline.py`
(request path) must use, so a city present in the prepared data can never fail to resolve
because of divergent rules (FR-002).
"""

from routing.normalize import normalize_city_key


def test_state_is_trimmed_and_uppercased() -> None:
    _, state = normalize_city_key("Dallas", "  tx ")
    assert state == "TX"


def test_city_whitespace_collapsed_and_uppercased() -> None:
    city_key, _ = normalize_city_key("  saint   louis  ", "MO")
    assert city_key == "SAINT LOUIS"


def test_st_ft_mt_tokens_expand_as_whole_tokens_including_bare_mt() -> None:
    assert normalize_city_key("St. Louis", "MO")[0] == "SAINT LOUIS"
    assert normalize_city_key("St Louis", "MO")[0] == "SAINT LOUIS"
    assert normalize_city_key("Ft. Worth", "TX")[0] == "FORT WORTH"
    assert normalize_city_key("Ft Worth", "TX")[0] == "FORT WORTH"
    assert normalize_city_key("Mt. Vernon", "NY")[0] == "MOUNT VERNON"
    # Bare "MT" expands here (routing/normalize.py), unlike the data-build pipeline's
    # original local rule — this is the FR-001 closed list in full.
    assert normalize_city_key("Mt Vernon", "NY")[0] == "MOUNT VERNON"
    # A token that merely contains "ST" is not a whole-token match and must not expand.
    assert normalize_city_key("Stockton", "CA")[0] == "STOCKTON"


def test_normalizing_an_already_normalized_pair_is_idempotent() -> None:
    once = normalize_city_key("Saint Louis", "MO")
    twice = normalize_city_key(*once)
    assert once == twice
