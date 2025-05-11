import sys

from django.apps import apps
from django.db import models


def sql_flush(style, connection, reset_sequences=True, allow_cascade=False):
    """
    Return a list of the SQL statements used to flush the database.
    """
    tables = connection.introspection.django_table_names(
        only_existing=True, include_views=False
    )
    return connection.ops.sql_flush(
        style,
        tables,
        reset_sequences=reset_sequences,
        allow_cascade=allow_cascade,
    )


def emit_pre_migrate_signal(verbosity, interactive, db, **kwargs):
    # Emit the pre_migrate signal for every application.
    """
    Sends a pre-migrate signal to all application configurations, allowing custom handlers to execute before database migration occurs.

    :param verbosity: Verbosity level for output
    :param interactive: Whether the migration is interactive
    :param db: Database alias to use for the migration
    """
    for app_config in apps.get_app_configs():
        if app_config.models_module is None:
            continue
        if verbosity >= 2:
            stdout = kwargs.get("stdout", sys.stdout)
            stdout.write(
                "Running pre-migrate handlers for application %s" % app_config.label
            )
        models.signals.pre_migrate.send(
            sender=app_config,
            app_config=app_config,
            verbosity=verbosity,
            interactive=interactive,
            using=db,
            **kwargs,
        )


def emit_post_migrate_signal(verbosity, interactive, db, **kwargs):
    # Emit the post_migrate signal for every application.
    """
    Emit a post-migrate signal to all installed applications after database migration.

    This signal allows applications to perform any necessary actions after their models have been installed or updated in the database.

    :param verbosity: The level of output verbosity.
    :param interactive: Whether the migration is being run in interactive mode.
    :param db: The database alias being used.
    :keyword arguments: Additional keyword arguments are passed to the signal handlers.
    """
    for app_config in apps.get_app_configs():
        if app_config.models_module is None:
            continue
        if verbosity >= 2:
            stdout = kwargs.get("stdout", sys.stdout)
            stdout.write(
                "Running post-migrate handlers for application %s" % app_config.label
            )
        models.signals.post_migrate.send(
            sender=app_config,
            app_config=app_config,
            verbosity=verbosity,
            interactive=interactive,
            using=db,
            **kwargs,
        )
