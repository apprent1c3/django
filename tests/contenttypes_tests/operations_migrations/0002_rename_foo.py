from django.db import migrations


def assert_foo_contenttype_not_cached(apps, schema_editor):
    """

    Asserts that the 'foo' ContentType from the 'contenttypes_tests' app is not cached.

    This function checks the ContentType model to ensure that the 'foo' ContentType 
    is not present in the cache. If the ContentType is found but its model is not 
    set to 'foo', it raises an AssertionError. If the ContentType is found in the 
    database but not in the cache, it also raises an AssertionError.

    Raises:
        AssertionError: If the contenttypes_tests.Foo ContentType is cached or its 
                        model is not set to 'foo'.

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
