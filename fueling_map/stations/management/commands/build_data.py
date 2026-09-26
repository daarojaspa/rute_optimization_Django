"""`manage.py build_data`: read the fuel and cities CSVs, write the station and city tables.

Offline only. All cleaning rules live in stations.pipeline; this command does the I/O.
"""

import csv
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stations.models import City, Station
from stations.pipeline import BuildResult, DataBuildError, MatchRateTooLow, build

UNMATCHED_CSV = "unmatched.csv"


def _fail_under(text: str) -> float:
    value = float(text)
    if not 0.0 <= value <= 1.0:
        raise ValueError
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError as err:
        raise DataBuildError(f"file not found: {path}") from err
    except (OSError, UnicodeDecodeError, csv.Error) as err:
        raise DataBuildError(f"cannot read {path}: {err}") from err


def _write_unmatched(result: BuildResult) -> None:
    with open(UNMATCHED_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "city", "state"])
        writer.writerows((u.name, u.city, u.state) for u in result.unmatched)


def _store(result: BuildResult) -> None:
    """Replace both tables (cities first). Rows go in ascending key order for stable output."""
    with transaction.atomic(using="cities"):
        City.objects.all().delete()
        City.objects.bulk_create([City(**vars_of(c)) for c in result.cities], batch_size=500)
    with transaction.atomic(using="default"):
        Station.objects.all().delete()
        Station.objects.bulk_create(
            [Station(**vars_of(s)) for s in result.stations], batch_size=500
        )


def vars_of(record: object) -> dict[str, Any]:
    return dict(vars(record))


class Command(BaseCommand):
    help = "Clean the fuel-price and US-cities CSVs and store stations with coordinates."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--fuel-csv", type=Path, default=settings.FUEL_CSV_PATH)
        parser.add_argument("--cities-csv", type=Path, default=settings.CITIES_CSV_PATH)
        parser.add_argument(
            "--fail-under",
            type=_fail_under,
            default=0.95,
            help="minimum match rate in [0, 1] (default 0.95)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        fail_under: float = options["fail_under"]
        try:
            fuel_rows = _read_csv(options["fuel_csv"])
            city_rows = _read_csv(options["cities_csv"])
            result = build(fuel_rows, city_rows, fail_under)
        except MatchRateTooLow as err:
            _write_unmatched(err.result)
            self._summary(err.result)
            raise CommandError(f"{err}; nothing was written to the databases") from err
        except DataBuildError as err:
            raise CommandError(str(err)) from err

        _write_unmatched(result)
        _store(result)
        self._summary(result)

    def _summary(self, result: BuildResult) -> None:
        s = result.stats
        drops = ", ".join(f"{code}={n}" for code, n in s.dropped_state.items()) or "none"
        lines = [
            f"Fuel rows read:            {s.rows_read}",
            f"Dropped, bad price:        {s.dropped_bad_price}",
            f"Dropped, state (by code):  {drops}",
            f"Duplicate groups collapsed: {s.groups_collapsed} ({s.rows_collapsed} rows)",
            f"Stations after cleaning:   {s.stations}",
            f"City rows read/collapsed:  {s.city_rows_read} / {s.city_rows_collapsed}",
            f"Match rate:                {s.match_rate:.4f}",
            f"Left out as unmatched:     {s.unmatched} (see {UNMATCHED_CSV})",
            f"Stations written:          {s.matched}",
        ]
        self.stdout.write("\n".join(lines))
