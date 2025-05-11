from django.apps import apps
from django.core import checks
from django.core.checks.registry import registry
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Checks the entire Django project for potential problems."

    requires_system_checks = []

    def add_arguments(self, parser):
        """

        Add command-line arguments to the parser for customizing the execution of checks.

        The supported arguments include:
            - Application label(s) to check
            - Tags to filter checks
            - Options to list available tags, check deployment settings, and specify failure levels
            - Databases to run checks against

        These arguments allow users to tailor the checks to their specific needs and environments.

        """
        parser.add_argument("args", metavar="app_label", nargs="*")
        parser.add_argument(
            "--tag",
            "-t",
            action="append",
            dest="tags",
            help="Run only checks labeled with given tag.",
        )
        parser.add_argument(
            "--list-tags",
            action="store_true",
            help=(
                "List available tags. Specify --deploy to include available deployment "
                "tags."
            ),
        )
        parser.add_argument(
            "--deploy",
            action="store_true",
            help="Check deployment settings.",
        )
        parser.add_argument(
            "--fail-level",
            default="ERROR",
            choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            help=(
                "Message level that will cause the command to exit with a "
                "non-zero status. Default is ERROR."
            ),
        )
        parser.add_argument(
            "--database",
            action="append",
            choices=tuple(connections),
            dest="databases",
            help="Run database related checks against these aliases.",
        )

    def handle(self, *app_labels, **options):
        """
        Handle system checks for specified applications or tags.

        Performs system checks and reports on any errors found. Can be used to list available tags with the --list-tags option or to run checks on specific applications or tags. The --deploy option determines whether to include deployment checks.

        The function takes application labels and options as input and returns check results, either directly or by raising an error if an invalid tag is specified.

        Options:
            - deploy: Whether to include deployment checks.
            - list_tags: Whether to list available tags.
            - tags: List of tags to run checks for.
            - fail_level: The level at which to fail the check.
            - databases: List of databases to run checks on.

        """
        include_deployment_checks = options["deploy"]
        if options["list_tags"]:
            self.stdout.write(
                "\n".join(sorted(registry.tags_available(include_deployment_checks)))
            )
            return

        if app_labels:
            app_configs = [apps.get_app_config(app_label) for app_label in app_labels]
        else:
            app_configs = None

        tags = options["tags"]
        if tags:
            try:
                invalid_tag = next(
                    tag
                    for tag in tags
                    if not checks.tag_exists(tag, include_deployment_checks)
                )
            except StopIteration:
                # no invalid tags
                pass
            else:
                raise CommandError(
                    'There is no system check with the "%s" tag.' % invalid_tag
                )

        self.check(
            app_configs=app_configs,
            tags=tags,
            display_num_errors=True,
            include_deployment_checks=include_deployment_checks,
            fail_level=getattr(checks, options["fail_level"]),
            databases=options["databases"],
        )
