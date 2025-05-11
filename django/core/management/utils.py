import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
from subprocess import run

from django.apps import apps as installed_apps
from django.utils.crypto import get_random_string
from django.utils.encoding import DEFAULT_LOCALE_ENCODING

from .base import CommandError, CommandParser


def popen_wrapper(args, stdout_encoding="utf-8"):
    """
    Executes a command with the provided arguments and returns its output, capturing both stdout and stderr, along with the command's return code, providing a convenient and error-handling interface around the system's Popen functionality.
    """
    try:
        p = run(args, capture_output=True, close_fds=os.name != "nt")
    except OSError as err:
        raise CommandError("Error executing %s" % args[0]) from err
    return (
        p.stdout.decode(stdout_encoding),
        p.stderr.decode(DEFAULT_LOCALE_ENCODING, errors="replace"),
        p.returncode,
    )


def handle_extensions(extensions):
    """
    Organize multiple extensions into a standardized set of file extensions.

    The function takes a list of extensions as input, which may be comma-separated or 
    provided as multiple items, and returns a set of extensions with leading dots added 
    if necessary. It removes any duplicates and ignores whitespace to produce a 
    consistent list of file extensions.
    """
    ext_list = []
    for ext in extensions:
        ext_list.extend(ext.replace(" ", "").split(","))
    for i, ext in enumerate(ext_list):
        if not ext.startswith("."):
            ext_list[i] = ".%s" % ext_list[i]
    return set(ext_list)


def find_command(cmd, path=None, pathext=None):
    """
    Find the executable path for a given command.

    Searches for the command in the system's PATH environment variable or a provided path,
    and returns the full path to the command if found, including any file extension.

    :param cmd: The command to search for.
    :param path: Optional path to search in, defaults to the system's PATH environment variable.
    :param pathext: Optional list of file extensions to check, defaults to the system's PATHEXT environment variable.
    :return: The full path to the command if found, otherwise None.
    """
    if path is None:
        path = os.environ.get("PATH", "").split(os.pathsep)
    if isinstance(path, str):
        path = [path]
    # check if there are funny path extensions for executables, e.g. Windows
    if pathext is None:
        pathext = os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep)
    # don't use extensions if the command ends with one of them
    for ext in pathext:
        if cmd.endswith(ext):
            pathext = [""]
            break
    # check if we find the command on PATH
    for p in path:
        f = os.path.join(p, cmd)
        if os.path.isfile(f):
            return f
        for ext in pathext:
            fext = f + ext
            if os.path.isfile(fext):
                return fext
    return None


def get_random_secret_key():
    """
    Return a 50 character random string usable as a SECRET_KEY setting value.
    """
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    return get_random_string(50, chars)


def parse_apps_and_model_labels(labels):
    """
    Parse a list of \"app_label.ModelName\" or \"app_label\" strings into actual Django application configurations and model classes.

    Returns a tuple containing two sets: model classes and application configurations.

    Raises a CommandError if any of the specified models or applications do not exist.
    """
    apps = set()
    models = set()

    for label in labels:
        if "." in label:
            try:
                model = installed_apps.get_model(label)
            except LookupError:
                raise CommandError("Unknown model: %s" % label)
            models.add(model)
        else:
            try:
                app_config = installed_apps.get_app_config(label)
            except LookupError as e:
                raise CommandError(str(e))
            apps.add(app_config)

    return models, apps


def get_command_line_option(argv, option):
    """
    Retrieves the value of a specific command line option from an argument list.

    The option must be provided with its leading dashes (e.g., '--testrunner').

    If the option is found, its value is returned; otherwise, None is returned.
    """
    parser = CommandParser(add_help=False, allow_abbrev=False)
    parser.add_argument(option, dest="value")
    try:
        options, _ = parser.parse_known_args(argv[2:])
    except CommandError:
        return None
    else:
        return options.value


def normalize_path_patterns(patterns):
    """
    Normalizes a collection of glob-style path patterns to ensure consistency across different operating systems.
    The function removes any directory suffixes from the patterns to create a standardized format.
    Returns a list of normalized path patterns.
    """
    patterns = [os.path.normcase(p) for p in patterns]
    dir_suffixes = {"%s*" % path_sep for path_sep in {"/", os.sep}}
    norm_patterns = []
    for pattern in patterns:
        for dir_suffix in dir_suffixes:
            if pattern.endswith(dir_suffix):
                norm_patterns.append(pattern.removesuffix(dir_suffix))
                break
        else:
            norm_patterns.append(pattern)
    return norm_patterns


def is_ignored_path(path, ignore_patterns):
    """
    Check if a given path matches any of the provided glob-style ignore patterns, 
    determining whether it should be ignored or not based on these matches.
    """
    path = Path(path)

    def ignore(pattern):
        return fnmatch.fnmatchcase(path.name, pattern) or fnmatch.fnmatchcase(
            str(path), pattern
        )

    return any(ignore(pattern) for pattern in normalize_path_patterns(ignore_patterns))


def find_formatters():
    return {"black_path": shutil.which("black")}


def run_formatters(written_files, black_path=(sentinel := object())):
    """
    Run the Black code formatter on the specified files, ensuring consistent code style and formatting. If the Black executable path is not provided, it will be automatically detected.
    """
    # Use a sentinel rather than None, as which() returns None when not found.
    if black_path is sentinel:
        black_path = shutil.which("black")
    if black_path:
        subprocess.run(
            [black_path, "--fast", "--", *written_files],
            capture_output=True,
        )
