"""End-to-end behavior of `manage.py build_data` on small temp CSVs and test databases."""

import csv
import hashlib
import socket
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from stations.models import City, Station

pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "cities"])

FUEL_HEADER = [
    "OPIS Truckstop ID",
    "Truckstop Name",
    "Address",
    "City",
    "State",
    "Rack ID",
    "Retail Price",
]
CITY_HEADER = ["ID", "STATE_CODE", "STATE_NAME", "CITY", "COUNTY", "LATITUDE", "LONGITUDE"]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.chdir(tmp_path)
    fuel = write_csv(
        tmp_path / "fuel.csv",
        FUEL_HEADER,
        [
            ["1", "A", "I-94", "Tomah", "WI", "1", "3.10"],
            ["1", "A2", "I-94", "Tomah", "WI", "1", "2.90"],
            ["2", "B", "I-94", "Tomah", "wi", "1", "3.30"],
            ["3", "C", "SR-1", "St. Louis", "MO", "1", "3.00"],
            ["4", "D", "SR-2", "Nowhere", "MO", "1", "3.20"],
            ["5", "E", "SR-3", "Toronto", "ON", "1", "3.40"],
            ["6", "F", "SR-4", "Tomah", "WI", "1", "0"],
        ],
    )
    cities = write_csv(
        tmp_path / "cities.csv",
        CITY_HEADER,
        [
            ["1", "WI", "Wisconsin", "Tomah", "Monroe", "43.9", "-90.5"],
            ["2", "MO", "Missouri", "Saint Louis", "St Louis", "38.6", "-90.2"],
        ],
    )
    return fuel, cities


def run(fuel: Path, cities: Path, *extra: str) -> str:
    out = StringIO()
    call_command(
        "build_data", "--fuel-csv", str(fuel), "--cities-csv", str(cities), *extra, stdout=out
    )
    return out.getvalue()


def export() -> str:
    rows = Station.objects.order_by("opis_id").values_list(
        "opis_id", "name", "address", "city", "state", "latitude", "longitude", "retail_price"
    )
    return "\n".join(map(repr, rows))


def test_command_writes_stations_and_cities_and_prints_summary(files: tuple[Path, Path]) -> None:
    out = run(*files, "--fail-under", "0.5")

    assert Station.objects.count() == 3
    assert City.objects.using("cities").count() == 2
    assert Station.objects.get(opis_id=1).retail_price == 2.90
    assert Station.objects.get(opis_id=1).name == "A2"
    for label in ("Fuel rows read", "Dropped, bad price", "ON=1", "Match rate", "Stations written"):
        assert label in out


def test_no_station_has_duplicate_id_bad_price_or_bad_state(files: tuple[Path, Path]) -> None:
    run(*files, "--fail-under", "0.5")

    stored = list(Station.objects.all())
    assert len({s.opis_id for s in stored}) == len(stored)
    assert all(0 < s.retail_price <= 10.0 for s in stored)
    assert all(s.state != "ON" for s in stored)


def test_gate_failure_exits_nonzero_and_leaves_databases_unchanged(
    files: tuple[Path, Path],
) -> None:
    run(*files, "--fail-under", "0.5")
    before = export()

    with pytest.raises(CommandError, match="below --fail-under"):
        run(*files, "--fail-under", "1.0")

    assert export() == before
    assert City.objects.using("cities").count() == 2


def test_gate_failure_still_writes_unmatched_csv(files: tuple[Path, Path]) -> None:
    with pytest.raises(CommandError):
        run(*files)  # default 0.95, actual 0.75

    assert Path("unmatched.csv").exists()


def test_unmatched_csv_lists_name_city_state(files: tuple[Path, Path]) -> None:
    run(*files, "--fail-under", "0.5")

    rows = list(csv.reader(Path("unmatched.csv").open()))
    assert rows == [["name", "city", "state"], ["D", "Nowhere", "MO"]]


def test_unmatched_stations_are_absent_from_station_table(files: tuple[Path, Path]) -> None:
    run(*files, "--fail-under", "0.5")

    assert not Station.objects.filter(opis_id=4).exists()


def test_second_run_gives_identical_station_table_export_and_match_rate(
    files: tuple[Path, Path],
) -> None:
    first_out = run(*files, "--fail-under", "0.5")
    first = hashlib.sha256(export().encode()).hexdigest()

    second_out = run(*files, "--fail-under", "0.5")

    assert hashlib.sha256(export().encode()).hexdigest() == first
    assert second_out == first_out


def test_rows_missing_from_new_input_are_removed(files: tuple[Path, Path], tmp_path: Path) -> None:
    fuel, cities = files
    run(fuel, cities, "--fail-under", "0.5")
    smaller = write_csv(
        tmp_path / "small.csv", FUEL_HEADER, [["2", "B", "I-94", "Tomah", "WI", "1", "3.30"]]
    )

    run(smaller, cities)

    assert list(Station.objects.values_list("opis_id", flat=True)) == [2]


def test_custom_paths_and_threshold_are_used(files: tuple[Path, Path]) -> None:
    run(*files, "--fail-under", "0.75")  # exactly the achievable rate (3 of 4)

    assert Station.objects.count() == 3


def test_missing_csv_exits_nonzero_naming_file_and_writes_nothing(files: tuple[Path, Path]) -> None:
    with pytest.raises(CommandError, match="nope.csv"):
        run(Path("nope.csv"), files[1])

    assert Station.objects.count() == 0 and not Path("unmatched.csv").exists()


@pytest.mark.parametrize("value", ["1.5", "-0.1", "abc"])
def test_fail_under_outside_0_to_1_is_rejected(files: tuple[Path, Path], value: str) -> None:
    with pytest.raises(CommandError):
        run(*files, "--fail-under", value)


def test_command_makes_no_network_calls(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)

    run(*files, "--fail-under", "0.5")
