"""Behavior of stations.pipeline.build, tested on plain dict rows: no database, no files."""

import math

import pytest

import routing.normalize
import stations.pipeline
from stations.pipeline import DataBuildError, MatchRateTooLow, build


def fuel(
    opis: int, city: str = "Tomah", state: str = "WI", price: str = "3.00", **kw: str
) -> dict[str, str]:
    return {
        "OPIS Truckstop ID": str(opis),
        "Truckstop Name": kw.get("name", f"STOP {opis}"),
        "Address": kw.get("address", "I-94, EXIT 143"),
        "City": city,
        "State": state,
        "Rack ID": "1",
        "Retail Price": price,
    }


def city(
    name: str = "Tomah", state: str = "WI", lat: str = "43.9", lon: str = "-90.5", **kw: str
) -> dict[str, str]:
    row = {
        "CITY": name,
        "STATE_CODE": state,
        "LATITUDE": lat,
        "LONGITUDE": lon,
        "COUNTY": kw.get("county", "X"),
    }
    row.update({k.upper(): v for k, v in kw.items() if k == "population"})
    return row


def miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    p = math.pi / 180
    h = (
        math.sin((b[0] - a[0]) * p / 2) ** 2
        + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2
    )
    return 3959 * 2 * math.asin(math.sqrt(h))


def by_id(result, opis: int):  # type: ignore[no-untyped-def]
    return next(s for s in result.stations if s.opis_id == opis)


# --- normalization -------------------------------------------------------------------------


def test_state_is_trimmed_and_uppercased() -> None:
    result = build([fuel(1, state=" wi ")], [city()])
    assert result.stations[0].state == "WI"


def test_city_whitespace_collapsed_and_title_cased() -> None:
    result = build([fuel(1, city="  tOMAH   falls ")], [city("Tomah Falls")])
    assert result.stations[0].city == "Tomah Falls"


def test_name_and_address_are_trimmed_and_whitespace_collapsed() -> None:
    result = build([fuel(1, name="  PILOT   #1 ", address=" I-94,   EXIT 1 ")], [city()])
    assert (result.stations[0].name, result.stations[0].address) == ("PILOT #1", "I-94, EXIT 1")


@pytest.mark.parametrize(
    ("station_city", "cities_city"),
    [
        ("St. Louis", "Saint Louis"),
        ("Saint Louis", "St Louis"),
        ("Ft. Smith", "Fort Smith"),
        ("Fort Smith", "Ft Smith"),
        ("Mt. Vernon", "Mount Vernon"),
    ],
)
def test_st_ft_mt_tokens_expand_in_match_key_on_both_sides(
    station_city: str, cities_city: str
) -> None:
    result = build([fuel(1, city=station_city, state="MO")], [city(cities_city, "MO")])
    assert result.stats.matched == 1


def test_stations_pipeline_and_routing_share_the_identical_normalize_function() -> None:
    # FR-002: the data-build pipeline and the request path must use ONE normalizer, never two
    # that could drift apart. `is` (not `==`) proves it is the same function object, not a copy.
    assert stations.pipeline.normalize_city_key is routing.normalize.normalize_city_key


def test_bare_mt_without_period_is_expanded_by_the_shared_normalizer() -> None:
    # routing.normalize.normalize_city_key (FR-001/FR-002, research.md D2) expands bare "MT",
    # unlike this pipeline's original local rule. Matches, so nothing is left unmatched.
    result = build(
        [fuel(1, city="Mt Vernon", state="MO"), fuel(2)],
        [city("Mount Vernon", "MO"), city()],
        fail_under=0.0,
    )
    assert result.unmatched == []


def test_display_city_keeps_original_form_after_key_expansion() -> None:
    result = build([fuel(1, city="st. louis", state="MO")], [city("Saint Louis", "MO")])
    assert result.stations[0].city == "St. Louis"


def test_misspelled_city_is_not_fuzzy_matched() -> None:
    result = build([fuel(1, city="Tomha"), fuel(2)], [city()], fail_under=0.0)
    assert [u.city for u in result.unmatched] == ["Tomha"]


# --- filtering -----------------------------------------------------------------------------


@pytest.mark.parametrize("price", ["", "abc", "0", "-1.5", "10.01", "nan"])
def test_bad_price_is_dropped_and_counted(price: str) -> None:
    result = build([fuel(1, price=price), fuel(2)], [city()])
    assert [s.opis_id for s in result.stations] == [2]
    assert result.stats.dropped_bad_price == 1


def test_price_of_exactly_ten_is_kept() -> None:
    assert build([fuel(1, price="10.00")], [city()]).stats.stations == 1


def test_state_outside_50_plus_dc_is_dropped_and_counted_by_code() -> None:
    rows = [fuel(1, state="ON"), fuel(2, state="ON"), fuel(3, state="PR"), fuel(4)]
    result = build(rows, [city()])
    assert result.stats.dropped_state == {"ON": 2, "PR": 1}
    assert [s.opis_id for s in result.stations] == [4]


def test_dc_is_a_valid_state() -> None:
    assert (
        build([fuel(1, city="Washington", state="DC")], [city("Washington", "DC")]).stats.matched
        == 1
    )


def test_rows_read_equals_kept_plus_dropped_plus_collapsed() -> None:
    rows = [fuel(1), fuel(1, price="2.00"), fuel(2, price="0"), fuel(3, state="ON"), fuel(4)]
    s = build(rows, [city()]).stats
    assert s.rows_read == 5
    assert (
        s.rows_read
        == s.stations + s.dropped_bad_price + sum(s.dropped_state.values()) + s.rows_collapsed
    )


# --- deduplication -------------------------------------------------------------------------


def test_group_keeps_lowest_priced_row_with_all_its_fields() -> None:
    rows = [
        fuel(1, price="3.50", name="OLD", address="A1"),
        fuel(1, price="2.90", name="NEW", address="A2"),
    ]
    stop = build(rows, [city()]).stations[0]
    assert (stop.name, stop.address, stop.retail_price) == ("NEW", "A2", 2.90)


def test_equal_prices_keep_first_row() -> None:
    rows = [fuel(1, price="3.00", name="FIRST"), fuel(1, price="3.00", name="SECOND")]
    assert build(rows, [city()]).stations[0].name == "FIRST"


def test_bad_low_price_row_cannot_win_a_group() -> None:
    rows = [fuel(1, price="0", name="BAD"), fuel(1, price="3.10", name="GOOD")]
    assert build(rows, [city()]).stations[0].name == "GOOD"


def test_different_names_with_different_ids_are_not_merged() -> None:
    rows = [fuel(1243, name="PILOT TRAVEL CENTER #1243"), fuel(9999, name="PILOT #1243")]
    assert build(rows, [city()]).stats.stations == 2


def test_stats_report_rows_in_rows_out_groups_collapsed() -> None:
    rows = [fuel(1), fuel(1), fuel(1), fuel(2)]
    s = build(rows, [city()]).stats
    assert (s.rows_read, s.stations, s.groups_collapsed) == (4, 2, 1)


# --- cities --------------------------------------------------------------------------------


def test_identical_coordinate_city_rows_collapse() -> None:
    result = build([fuel(1)], [city(), city(county="Y")])
    assert len(result.cities) == 1 and result.stats.city_rows_collapsed == 1


def test_same_name_different_coordinates_uses_first_row() -> None:
    result = build(
        [fuel(1)], [city(lat="43.9", lon="-90.5"), city(lat="44.5", lon="-91.0", county="Y")]
    )
    assert (result.stations[0].latitude, result.stations[0].longitude) == (43.9, -90.5)
    assert result.stats.city_rows_collapsed == 1


def test_population_column_preferred_when_present() -> None:
    cities = [
        city(lat="43.9", lon="-90.5", population="10"),
        city(lat="44.5", lon="-91.0", population="500"),
    ]
    assert build([fuel(1)], cities).stations[0].latitude == 44.5


def test_same_name_in_different_states_stays_separate() -> None:
    result = build(
        [fuel(1, state="WI"), fuel(2, state="MN")], [city(state="WI"), city(state="MN", lat="45.0")]
    )
    assert len(result.cities) == 2


# --- join ----------------------------------------------------------------------------------


def test_station_joins_on_city_key_and_state() -> None:
    result = build(
        [fuel(1, city="tomah", state="WI")], [city("Tomah", "MN", lat="1"), city("Tomah", "WI")]
    )
    assert result.stations[0].latitude == 43.9


def test_unmatched_station_is_left_out_and_listed() -> None:
    result = build([fuel(1), fuel(2, city="Nowhere", name="LOST")], [city()], fail_under=0.0)
    assert [s.opis_id for s in result.stations] == [1]
    assert [(u.name, u.city, u.state) for u in result.unmatched] == [("LOST", "Nowhere", "WI")]
    assert result.stats.unmatched == 1


# --- shift ---------------------------------------------------------------------------------


def test_lowest_opis_id_in_city_keeps_city_coordinates() -> None:
    result = build([fuel(7), fuel(3), fuel(9)], [city()])
    assert (by_id(result, 3).latitude, by_id(result, 3).longitude) == (43.9, -90.5)


def test_other_stations_shift_at_most_5_miles_haversine() -> None:
    rows = [fuel(i) for i in range(1, 400)]
    result = build(rows, [city(lat="61.2", lon="-149.9")])
    shifted = [s for s in result.stations if s.opis_id != 1]
    assert all(miles((61.2, -149.9), (s.latitude, s.longitude)) <= 5.0 for s in shifted)
    assert any(miles((61.2, -149.9), (s.latitude, s.longitude)) > 1.0 for s in shifted)


def test_shift_is_a_pure_function_of_identity_and_city() -> None:
    a = build([fuel(1), fuel(5)], [city()])
    b = build([fuel(5), fuel(1), fuel(1)], [city()])
    assert (by_id(a, 5).latitude, by_id(a, 5).longitude) == (
        by_id(b, 5).latitude,
        by_id(b, 5).longitude,
    )


# --- gate ----------------------------------------------------------------------------------


def test_match_rate_is_matched_over_surviving_stations() -> None:
    rows = [fuel(1), fuel(2), fuel(3, city="X"), fuel(4, city="Y"), fuel(5, price="0")]
    assert build(rows, [city()], fail_under=0.0).stats.match_rate == 0.5


def test_match_rate_below_fail_under_raises_MatchRateTooLow() -> None:
    with pytest.raises(MatchRateTooLow) as err:
        build([fuel(1), fuel(2, city="X")], [city()], fail_under=0.9)
    assert err.value.result.stats.match_rate == 0.5 and len(err.value.result.unmatched) == 1


def test_match_rate_equal_to_fail_under_passes() -> None:
    assert build([fuel(1), fuel(2, city="X")], [city()], fail_under=0.5).stats.match_rate == 0.5


def test_zero_surviving_stations_raises_DataBuildError() -> None:
    with pytest.raises(DataBuildError, match="no stations"):
        build([fuel(1, price="0")], [city()])


def test_missing_required_column_raises_DataBuildError() -> None:
    with pytest.raises(DataBuildError, match="Retail Price"):
        build([{"OPIS Truckstop ID": "1"}], [city()])


def test_non_numeric_opis_id_raises_DataBuildError() -> None:
    with pytest.raises(DataBuildError, match="OPIS"):
        build([fuel(1) | {"OPIS Truckstop ID": "abc"}], [city()])


def test_build_is_deterministic_for_identical_input() -> None:
    rows = [fuel(i, price=f"{2 + i % 7}.5") for i in range(1, 60)] + [fuel(3, price="1.0")]
    assert build(rows, [city()]) == build(rows, [city()])
