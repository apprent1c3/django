from django.db import migrations


def grow_tail(x, y):
    """
    This is a comment
    """
    pass


def feed(x, y):
    """
    This is a comment
    """
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("migrations", "0004_fourth"),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop),
        migrations.RunPython(grow_tail),
        migrations.RunPython(feed, migrations.RunPython.noop),
    ]
