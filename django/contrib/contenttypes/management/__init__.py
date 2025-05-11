from django.apps import apps as global_apps
from django.db import DEFAULT_DB_ALIAS, IntegrityError, migrations, router, transaction


class RenameContentType(migrations.RunPython):
    def __init__(self, app_label, old_model, new_model):
        self.app_label = app_label
        self.old_model = old_model
        self.new_model = new_model
        super().__init__(self.rename_forward, self.rename_backward)

    def _rename(self, apps, schema_editor, old_model, new_model):
        """
        Renames a model in the content type database table, updating the existing content type entry 
        to reference the new model name, if the content type exists and migration is allowed.
        """
        ContentType = apps.get_model("contenttypes", "ContentType")
        db = schema_editor.connection.alias
        if not router.allow_migrate_model(db, ContentType):
            return

        try:
            content_type = ContentType.objects.db_manager(db).get_by_natural_key(
                self.app_label, old_model
            )
        except ContentType.DoesNotExist:
            pass
        else:
            content_type.model = new_model
            try:
                with transaction.atomic(using=db):
                    content_type.save(using=db, update_fields={"model"})
            except IntegrityError:
                # Gracefully fallback if a stale content type causes a
                # conflict as remove_stale_contenttypes will take care of
                # asking the user what should be done next.
                content_type.model = old_model
            else:
                # Clear the cache as the `get_by_natural_key()` call will cache
                # the renamed ContentType instance by its old model name.
                ContentType.objects.clear_cache()

    def rename_forward(self, apps, schema_editor):
        self._rename(apps, schema_editor, self.old_model, self.new_model)

    def rename_backward(self, apps, schema_editor):
        self._rename(apps, schema_editor, self.new_model, self.old_model)


def inject_rename_contenttypes_operations(
    plan=None, apps=global_apps, using=DEFAULT_DB_ALIAS, **kwargs
):
    """
    Insert a `RenameContentType` operation after every planned `RenameModel` operation to ensure content types are updated accordingly when models are renamed, maintaining consistency between model and content type names.
    """
    if plan is None:
        return

    # Determine whether or not the ContentType model is available.
    try:
        ContentType = apps.get_model("contenttypes", "ContentType")
    except LookupError:
        available = False
    else:
        if not router.allow_migrate_model(using, ContentType):
            return
        available = True

    for migration, backward in plan:
        if (migration.app_label, migration.name) == ("contenttypes", "0001_initial"):
            # There's no point in going forward if the initial contenttypes
            # migration is unapplied as the ContentType model will be
            # unavailable from this point.
            if backward:
                break
            else:
                available = True
                continue
        # The ContentType model is not available yet.
        if not available:
            continue
        inserts = []
        for index, operation in enumerate(migration.operations):
            if isinstance(operation, migrations.RenameModel):
                operation = RenameContentType(
                    migration.app_label,
                    operation.old_name_lower,
                    operation.new_name_lower,
                )
                inserts.append((index + 1, operation))
        for inserted, (index, operation) in enumerate(inserts):
            migration.operations.insert(inserted + index, operation)


def get_contenttypes_and_models(app_config, using, ContentType):
    """

    Retrieve a mapping of content types and models for a given application configuration.

    Returns a tuple containing two dictionaries: one mapping model names to their corresponding content types,
    and another mapping model names to their corresponding model classes. Returns (None, None) if migration is not allowed.

    :param app_config: Application configuration object.
    :param using: Database alias to use for the query.
    :param ContentType: ContentType model class.
    :rtype: tuple

    """
    if not router.allow_migrate_model(using, ContentType):
        return None, None

    ContentType.objects.clear_cache()

    content_types = {
        ct.model: ct
        for ct in ContentType.objects.using(using).filter(app_label=app_config.label)
    }
    app_models = {model._meta.model_name: model for model in app_config.get_models()}
    return content_types, app_models


def create_contenttypes(
    app_config,
    verbosity=2,
    interactive=True,
    using=DEFAULT_DB_ALIAS,
    apps=global_apps,
    **kwargs,
):
    """

    Create content types for models in a given application.

    This function is responsible for initializing the content types in the database
    for the models defined in the provided application configuration. It creates the
    necessary ContentType objects for each model and stores them in the database.

    :param app_config: Application configuration to create content types for.
    :param verbosity: Verbosity level for output messages (default: 2).
    :param interactive: Whether to run in interactive mode (default: True).
    :param using: Database alias to use for the operation (default: DEFAULT_DB_ALIAS).
    :param apps: Registry of applications (default: global_apps).

    """
    if not app_config.models_module:
        return

    app_label = app_config.label
    try:
        app_config = apps.get_app_config(app_label)
        ContentType = apps.get_model("contenttypes", "ContentType")
    except LookupError:
        return

    content_types, app_models = get_contenttypes_and_models(
        app_config, using, ContentType
    )

    if not app_models:
        return

    cts = [
        ContentType(
            app_label=app_label,
            model=model_name,
        )
        for (model_name, model) in app_models.items()
        if model_name not in content_types
    ]
    ContentType.objects.using(using).bulk_create(cts)
    if verbosity >= 2:
        for ct in cts:
            print("Adding content type '%s | %s'" % (ct.app_label, ct.model))
