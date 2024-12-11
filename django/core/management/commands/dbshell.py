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
        """
        Handle a database management task by running a shell command.

        This function establishes a connection to the specified database and executes
        a management command with the provided parameters. It verifies that the required
        executable is installed and available on the system path, and checks the command's
        exit status to ensure successful execution.

         Parameters:
            database (str): The name of the database connection to use.
            parameters (str): The parameters to pass to the management command.

         Raises:
            CommandError: If the required executable is not installed or not found on the path,
                          or if the command returns a non-zero exit status.

         Returns:
            None
        """
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
