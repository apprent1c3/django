from django.apps import AppConfig
from django.contrib.contenttypes.checks import (
    check_generic_foreign_keys,
    check_model_name_lengths,
)
from django.core import checks
from django.db.models.signals import post_migrate, pre_migrate
from django.utils.translation import gettext_lazy as _

from .management import create_contenttypes, inject_rename_contenttypes_operations


class ContentTypesConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "django.contrib.contenttypes"
    verbose_name = _("Content Types")

    def ready(self):
        """

        Prepare the model for database migrations and runtime checks.

        This method connects the necessary signals to perform content type renaming operations
        before migration and creation of content types after migration. It also registers
        checks to ensure the integrity of generic foreign keys and model name lengths.

        The checks and operations performed by this method are essential for maintaining
        a consistent and valid database schema. They help prevent potential issues that
        may arise during database migrations or runtime execution.

        """
        pre_migrate.connect(inject_rename_contenttypes_operations, sender=self)
        post_migrate.connect(create_contenttypes)
        checks.register(check_generic_foreign_keys, checks.Tags.models)
        checks.register(check_model_name_lengths, checks.Tags.models)
