from django.db import migrations


def assert_foo_contenttype_not_cached(apps, schema_editor):
    """
    Verifies that the 'contenttypes_tests.Foo' ContentType is not cached or has been correctly updated.

    This function checks the status of the 'contenttypes_tests.Foo' ContentType to ensure it is not lingering in an invalid state.
    It raises an AssertionError if the ContentType is cached or has an incorrect model attribute.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    try:
        content_type = ContentType.objects.get_by_natural_key(
            "contenttypes_tests", "foo"
        )
    except ContentType.DoesNotExist:
        pass
    else:
        if not ContentType.objects.filter(
            app_label="contenttypes_tests", model="foo"
        ).exists():
            raise AssertionError(
                "The contenttypes_tests.Foo ContentType should not be cached."
            )
        elif content_type.model != "foo":
            raise AssertionError(
                "The cached contenttypes_tests.Foo ContentType should have "
                "its model set to 'foo'."
            )


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes_tests", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel("Foo", "RenamedFoo"),
        migrations.RunPython(
            assert_foo_contenttype_not_cached, migrations.RunPython.noop
        ),
    ]
