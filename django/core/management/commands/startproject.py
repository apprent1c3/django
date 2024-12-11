from django.core.checks.security.base import SECRET_KEY_INSECURE_PREFIX
from django.core.management.templates import TemplateCommand

from ..utils import get_random_secret_key


class Command(TemplateCommand):
    help = (
        "Creates a Django project directory structure for the given project "
        "name in the current directory or optionally in the given directory."
    )
    missing_args_message = "You must provide a project name."

    def handle(self, **options):
        """

        Handles the creation of a new project.

        Called with keyword arguments, this function initializes a new project by providing a name and target directory.
        A random secret key is generated and combined with a predefined insecure prefix for the project's secret key.

        The provided options dictionary is updated with the generated secret key and then passed to the parent class for further handling.
        Required options include 'name' for the project name and 'directory' for the target directory.

        The function ultimately enables the creation of a new project with a unique secret key.

        """
        project_name = options.pop("name")
        target = options.pop("directory")

        # Create a random SECRET_KEY to put it in the main settings.
        options["secret_key"] = SECRET_KEY_INSECURE_PREFIX + get_random_secret_key()

        super().handle("project", project_name, target, **options)
