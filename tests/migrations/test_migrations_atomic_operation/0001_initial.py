from django.db import migrations, models


def raise_error(apps, schema_editor):
    # Test atomic operation in non-atomic migration is wrapped in transaction
    """

    Raises a RuntimeError during migration, aborting the process.

    This function intentionally interrupts the migration flow by creating a new Editor instance
    and then raising an exception. It's used to forcefully stop the migration when executed.

    """
    Editor = apps.get_model("migrations", "Editor")
    Editor.objects.create(name="Test Editor")
    raise RuntimeError("Abort migration")


class Migration(migrations.Migration):
    atomic = False

    operations = [
        migrations.CreateModel(
            "Editor",
            [
                ("name", models.CharField(primary_key=True, max_length=255)),
            ],
        ),
        migrations.RunPython(raise_error, reverse_code=raise_error, atomic=True),
    ]
