import os

from django.contrib.staticfiles import finders
from django.core.management.base import LabelCommand


class Command(LabelCommand):
    help = "Finds the absolute paths for the given static file(s)."
    label = "staticfile"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--first",
            action="store_false",
            dest="all",
            help="Only return the first match for each static file.",
        )

    def handle_label(self, path, **options):
        """
        Locate a file or directory at the given path and return its location.

        The function searches for the specified path, and if found, returns the absolute path(s) where the file or directory is located.
        The level of verbosity can be controlled through the `verbosity` option, which determines the amount of detail included in the output.
        If the file or directory is not found, an error message is returned indicating that no matching file was found.
        Optional keyword arguments:
            verbosity: controls the level of detail in the output (integer)
            all: if True, find all occurrences of the path (boolean)
        """
        verbosity = options["verbosity"]
        result = finders.find(path, find_all=options["all"])
        if verbosity >= 2:
            searched_locations = (
                "\nLooking in the following locations:\n  %s"
                % "\n  ".join([str(loc) for loc in finders.searched_locations])
            )
        else:
            searched_locations = ""
        if result:
            if not isinstance(result, (list, tuple)):
                result = [result]
            result = (os.path.realpath(path) for path in result)
            if verbosity >= 1:
                file_list = "\n  ".join(result)
                return "Found '%s' here:\n  %s%s" % (
                    path,
                    file_list,
                    searched_locations,
                )
            else:
                return "\n".join(result)
        else:
            message = ["No matching file found for '%s'." % path]
            if verbosity >= 2:
                message.append(searched_locations)
            if verbosity >= 1:
                self.stderr.write("\n".join(message))
