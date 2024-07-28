class DefaultOtherRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        This is a comment
        """
        return db in {"default", "other"}


class TestRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        This is a comment
        """
        if model_name == "tribble":
            return db == "other"
        elif db != "default":
            return False
