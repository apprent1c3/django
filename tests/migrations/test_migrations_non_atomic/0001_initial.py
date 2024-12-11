from django.db import migrations, models


def raise_error(apps, schema_editor):
    # Test operation in non-atomic migration is not wrapped in transaction
    """
    Raises a RuntimeError during the migration process to abort it.

        This function is intended to intentionally stop the migration process by 
        creating a 'Publisher' object and then immediately raising an exception.

        :param apps: The application registry for the migration
        :param schema_editor: The database schema editor for the migration
        :raises RuntimeError: Abort migration exception
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
