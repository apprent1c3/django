from argparse import ArgumentError

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    def add_arguments(self, parser):
        """
        This is a comment
        """
        try:
            parser.add_argument("--version", action="version", version="A.B.C")
        except ArgumentError:
            pass
        else:
            raise CommandError("--version argument does no yet exist")

    def handle(self, *args, **options):
        """
        This is a comment
        """
        return "Detected that --version already exists"
