from django.db import migrations, models


def add_legacy_name(apps, schema_editor):
    """

    Updates the name of ContentTypes in the database to use their corresponding model's object name.

    This function iterates over all ContentTypes in the database, associated with a given database alias,
    and attempts to update their 'name' field with the object name of their corresponding model.
    If the model cannot be found, the 'name' field is updated with the model name instead.
    The updated ContentTypes are then saved to the database.

    """
    alias = schema_editor.connection.alias
    ContentType = apps.get_model("contenttypes", "ContentType")
    for ct in ContentType.objects.using(alias):
        try:
            ct.name = apps.get_model(ct.app_label, ct.model)._meta.object_name
        except LookupError:
            ct.name = ct.model
        ct.save()


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="contenttype",
            options={
                "verbose_name": "content type",
                "verbose_name_plural": "content types",
            },
        ),
        migrations.AlterField(
            model_name="contenttype",
            name="name",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.RunPython(
            migrations.RunPython.noop,
            add_legacy_name,
            hints={"model_name": "contenttype"},
        ),
        migrations.RemoveField(
            model_name="contenttype",
            name="name",
        ),
    ]
