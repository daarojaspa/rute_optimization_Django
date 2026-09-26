from django.db import models


class Station(models.Model):
    """A truckstop with its price and location; one row per OPIS Truckstop ID.

    Coordinates are city-level approximations (see README). Latitude and longitude are
    decimal degrees; retail_price is USD per gallon.
    """

    opis_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    latitude = models.FloatField()
    longitude = models.FloatField()
    retail_price = models.FloatField()

    class Meta:
        db_table = "stations"


class City(models.Model):
    """One US city per (city_key, state); coordinates of its first source row."""

    city = models.CharField(max_length=100)
    city_key = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        db_table = "us_cities"
        constraints = [
            models.UniqueConstraint(fields=["city_key", "state"], name="unique_city_key_state")
        ]
