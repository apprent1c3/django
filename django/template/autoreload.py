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

    Returns a set of template directory paths.

    This function iterates over all available template engines, focusing on Django template engines, 
    and collects the directories where templates are located. It considers both the engine's own 
    directories and those provided by enabled template loaders. The directories are resolved 
    relative to the current working directory.

    The function returns a set of Path objects representing the unique template directories.

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

    Resets the template loaders for all Django template backends and the default renderer.

    This function iterates over all template engines, identifies those that use DjangoTemplates,
    and resets their corresponding template loaders. Additionally, it checks the default renderer
    and resets its template loaders if it is based on DjangoTemplates.

    The purpose of this function is to restart the template loading process, which can be useful
    in certain scenarios such as testing or development, where template caching or previous
    loading attempts may interfere with the desired outcome.

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
