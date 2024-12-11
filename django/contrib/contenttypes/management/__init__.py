from django.apps import apps as global_apps
from django.db import DEFAULT_DB_ALIAS, IntegrityError, migrations, router, transaction


class RenameContentType(migrations.RunPython):
    def __init__(self, app_label, old_model, new_model):
        """
        .. init:: __init__(app_label, old_model, new_model)
           :noindex:

           Initializes a model rename operation.

           :param app_label: The label of the application where the model resides.
           :param old_model: The original name of the model to be renamed.
           :param new_model: The new name for the model.

           This initializer sets up the necessary state for renaming a model, 
           including the application label and the old and new model names, 
           and calls the superclass initializer with the forward and backward 
           rename operations.
        """
        self.app_label = app_label
        self.old_model = old_model
        self.new_model = new_model
        super().__init__(self.rename_forward, self.rename_backward)

    def _rename(self, apps, schema_editor, old_model, new_model):
        """

        Rename a content type in the database.

        This function updates the model associated with a given content type to reflect
        a name change. It retrieves the content type from the database using the old model
        name, updates its model name to the new one, and saves the changes. If the update
        fails due to an integrity error, the model name is reverted to its original value.

        The function only proceeds with the rename operation if the router allows migration
        of the ContentType model on the current database connection.

        Parameters
        ----------
        apps : ~django.apps.registry.Apps
            The Django apps registry.
        schema_editor : ~django.db.backends.base.schema.BaseDatabaseSchemaEditor
            The database schema editor.
        old_model : str
            The old name of the model.
        new_model : str
            The new name of the model.

        Returns
        -------
        None

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
    Insert a `RenameContentType` operation after every planned `RenameModel`
    operation.
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
    Create content types for models in the given app.
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
