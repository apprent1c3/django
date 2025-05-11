import itertools

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections, router
from django.db.models.deletion import Collector


class Command(BaseCommand):
    help = "Deletes stale content types in the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Tells Django to NOT prompt the user for input of any kind.",
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help='Nominates the database to use. Defaults to the "default" database.',
        )
        parser.add_argument(
            "--include-stale-apps",
            action="store_true",
            default=False,
            help=(
                "Deletes stale content types including ones from previously "
                "installed apps that have been removed from INSTALLED_APPS."
            ),
        )

    def handle(self, **options):
        """
        Handle stale content types in the database.

        Removes content types that are no longer associated with any models. The 
        deletion process can be controlled through the `include_stale_apps` and 
        `interactive` options. If `interactive` is True, the user is prompted to 
        confirm the deletion of each stale content type. 

        The function takes the following options:

        - `database`: the database to operate on
        - `include_stale_apps`: whether to include stale apps in the deletion process
        - `interactive`: whether to prompt the user for confirmation before deletion
        - `verbosity`: the level of output verbosity
        """
        db = options["database"]
        include_stale_apps = options["include_stale_apps"]
        interactive = options["interactive"]
        verbosity = options["verbosity"]

        if not router.allow_migrate_model(db, ContentType):
            return
        ContentType.objects.clear_cache()

        apps_content_types = itertools.groupby(
            ContentType.objects.using(db).order_by("app_label", "model"),
            lambda obj: obj.app_label,
        )
        for app_label, content_types in apps_content_types:
            if not include_stale_apps and app_label not in apps.app_configs:
                continue
            to_remove = [ct for ct in content_types if ct.model_class() is None]
            # Confirm that the content type is stale before deletion.
            using = router.db_for_write(ContentType)
            if to_remove:
                if interactive:
                    ct_info = []
                    for ct in to_remove:
                        ct_info.append(
                            "    - Content type for %s.%s" % (ct.app_label, ct.model)
                        )
                        collector = NoFastDeleteCollector(using=using, origin=ct)
                        collector.collect([ct])

                        for obj_type, objs in collector.data.items():
                            if objs != {ct}:
                                ct_info.append(
                                    "    - %s %s object(s)"
                                    % (
                                        len(objs),
                                        obj_type._meta.label,
                                    )
                                )
                    content_type_display = "\n".join(ct_info)
                    self.stdout.write(
                        "Some content types in your database are stale and can be "
                        "deleted.\n"
                        "Any objects that depend on these content types will also be "
                        "deleted.\n"
                        "The content types and dependent objects that would be deleted "
                        "are:\n\n"
                        f"{content_type_display}\n\n"
                        "This list doesn't include any cascade deletions to data "
                        "outside of Django\n"
                        "models (uncommon).\n\n"
                        "Are you sure you want to delete these content types?\n"
                        "If you're unsure, answer 'no'."
                    )
                    ok_to_delete = input("Type 'yes' to continue, or 'no' to cancel: ")
                else:
                    ok_to_delete = "yes"

                if ok_to_delete == "yes":
                    for ct in to_remove:
                        if verbosity >= 2:
                            self.stdout.write(
                                "Deleting stale content type '%s | %s'"
                                % (ct.app_label, ct.model)
                            )
                        ct.delete()
                else:
                    if verbosity >= 2:
                        self.stdout.write("Stale content types remain.")


class NoFastDeleteCollector(Collector):
    def can_fast_delete(self, *args, **kwargs):
        """
        Always load related objects to display them when showing confirmation.
        """
        return False
