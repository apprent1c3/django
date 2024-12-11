from django.db import migrations, models


def raise_error(apps, schema_editor):
    # Test operation in non-atomic migration is not wrapped in transaction
    """
    Abort the migration process by raising a RuntimeError exception.

    This function creates a new Publisher instance with the name 'Test Publisher'
    in the database and then intentionally raises an error to halt the migration.

    Parameters
    ----------
    apps : ~django.apps.registry.Apps
        The registry of installed applications.
    schema_editor : ~django.db.backends.base.schema.BaseDatabaseSchemaEditor
        The database schema editor.

    Raises
    ------
    RuntimeError
        Exception to abort the migration process.
    """
    Publisher = apps.get_model("migrations", "Publisher")
    Publisher.objects.create(name="Test Publisher")
    raise RuntimeError("Abort migration")


class Migration(migrations.Migration):
    atomic = False

    operations = [
        migrations.CreateModel(
            "Publisher",
            [
                ("name", models.CharField(primary_key=True, max_length=255)),
            ],
        ),
        migrations.RunPython(raise_error),
        migrations.CreateModel(
            "Book",
            [
                ("title", models.CharField(primary_key=True, max_length=255)),
                (
                    "publisher",
                    models.ForeignKey(
                        "migrations.Publisher", models.SET_NULL, null=True
                    ),
                ),
            ],
        ),
    ]
