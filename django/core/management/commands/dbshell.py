import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections


class Command(BaseCommand):
    help = (
        "Runs the command-line client for specified database, or the "
        "default database if none is provided."
    )

    requires_system_checks = []

    def add_arguments(self, parser):
        """
        Adds command line arguments to the parser for specifying a database and additional parameters.

        The function supports the following options:
            --database: specifies the database to open a shell on, defaults to the default database.
            positional parameters: allows for any number of additional parameters to be passed.

        These arguments can be used to customize the behavior of the command, such as selecting a specific database or passing in custom parameters. The database option accepts any of the available database connections.
        """
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help=(
                "Nominates a database onto which to open a shell. Defaults to the "
                '"default" database.'
            ),
        )
        parameters = parser.add_argument_group("parameters", prefix_chars="--")
        parameters.add_argument("parameters", nargs="*")

    def handle(self, **options):
        connection = connections[options["database"]]
        try:
            connection.client.runshell(options["parameters"])
        except FileNotFoundError:
            # Note that we're assuming the FileNotFoundError relates to the
            # command missing. It could be raised for some other reason, in
            # which case this error message would be inaccurate. Still, this
            # message catches the common case.
            raise CommandError(
                "You appear not to have the %r program installed or on your path."
                % connection.client.executable_name
            )
        except subprocess.CalledProcessError as e:
            raise CommandError(
                '"%s" returned non-zero exit status %s.'
                % (
                    " ".join(map(str, e.cmd)),
                    e.returncode,
                ),
                returncode=e.returncode,
            )
