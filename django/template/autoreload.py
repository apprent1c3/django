from pathlib import Path

from django.dispatch import receiver
from django.template import engines
from django.template.backends.django import DjangoTemplates
from django.utils._os import to_path
from django.utils.autoreload import autoreload_started, file_changed, is_django_path


def get_template_directories():
    # Iterate through each template backend and find
    # any template_loader that has a 'get_dirs' method.
    # Collect the directories, filtering out Django templates.
    """
    ..: 
        Returns a set of directory paths where template files can be found.

        This function iterates through all available template engines, focusing on Django template engines. For each Django engine, it collects 
        directories specified in the engine as well as directories obtained from template loaders. These directories are resolved relative to 
        the current working directory. Directories that are Django-specific paths (not relevant in this context) or empty are excluded.

        :return: A set of Path objects representing directories where templates are located.
        :rtype: Set[Path]
    """
    cwd = Path.cwd()
    items = set()
    for backend in engines.all():
        if not isinstance(backend, DjangoTemplates):
            continue

        items.update(cwd / to_path(dir) for dir in backend.engine.dirs if dir)

        for loader in backend.engine.template_loaders:
            if not hasattr(loader, "get_dirs"):
                continue
            items.update(
                cwd / to_path(directory)
                for directory in loader.get_dirs()
                if directory and not is_django_path(directory)
            )
    return items


def reset_loaders():
    """

    Resets all template loaders for Django template engines.

    This function iterates over all available Django template engines, and for each
    engine, it resets all of its template loaders. Additionally, it checks the default
    renderer and resets its template loaders if it is a Django template engine.

    Use this function to restart the template loading process and refresh the cache
    of loaded templates. It is particularly useful during development or in situations
    where template changes need to be reloaded without restarting the application.

    """
    from django.forms.renderers import get_default_renderer

    for backend in engines.all():
        if not isinstance(backend, DjangoTemplates):
            continue
        for loader in backend.engine.template_loaders:
            loader.reset()

    backend = getattr(get_default_renderer(), "engine", None)
    if isinstance(backend, DjangoTemplates):
        for loader in backend.engine.template_loaders:
            loader.reset()


@receiver(autoreload_started, dispatch_uid="template_loaders_watch_changes")
def watch_for_template_changes(sender, **kwargs):
    """

    Automatically watches for changes to template files when the autoreload event is triggered.

    This function iterates over all configured template directories and instructs the autoreload system to monitor them for any changes to files within those directories, including subdirectories. This allows for automatic reloading of the application when template changes are detected.

    :param sender: The autoreload system sender object
    :param kwargs: Additional keyword arguments passed by the autoreload event

    """
    for directory in get_template_directories():
        sender.watch_dir(directory, "**/*")


@receiver(file_changed, dispatch_uid="template_loaders_file_changed")
def template_changed(sender, file_path, **kwargs):
    if file_path.suffix == ".py":
        return
    for template_dir in get_template_directories():
        if template_dir in file_path.parents:
            reset_loaders()
            return True
