class DefaultOtherRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db in {"default", "other"}


class TestRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Determines whether a model can be migrated to a specific database.

        The model 'tribble' is restricted to the 'other' database, while all other models are only allowed in the 'default' database.
        """
        if model_name == "tribble":
            return db == "other"
        elif db != "default":
            return False
