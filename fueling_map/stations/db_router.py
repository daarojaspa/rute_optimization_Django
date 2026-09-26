"""Routes the City model to the separate `cities` database."""

from django.db import models


class CitiesRouter:
    """City lives in the `cities` database; every other model in `default`."""

    def db_for_read(self, model: type[models.Model], **hints: object) -> str:
        return "cities" if model._meta.model_name == "city" else "default"

    def db_for_write(self, model: type[models.Model], **hints: object) -> str:
        return self.db_for_read(model)

    def allow_relation(self, obj1: models.Model, obj2: models.Model, **hints: object) -> bool:
        return True

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: object
    ) -> bool:
        if model_name is None:
            return True
        return (db == "cities") == (model_name == "city")
