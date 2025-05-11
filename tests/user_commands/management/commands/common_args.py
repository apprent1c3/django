from argparse import ArgumentError

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def add_arguments(self, parser):
        """

        Add the --version argument to the parser, if available.

        Attempts to add a version argument to the parser, silently ignoring ArgumentError
        if the argument already exists, and instead raises an exception to indicate that the
        argument was successfully added, but the parser's handling is incomplete.

        """
        try:
            parser.add_argument("--version", action="version", version="A.B.C")
        except ArgumentError:
            pass
        else:
            raise CommandError("--version argument does no yet exist")

    def handle(self, *args, **options):
        return "Detected that --version already exists"
