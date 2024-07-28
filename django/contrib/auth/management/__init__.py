"""
Creates permissions for all installed apps that need permissions.
"""

import getpass
import unicodedata

from django.apps import apps as global_apps
from django.contrib.auth import get_permission_codename
from django.contrib.contenttypes.management import create_contenttypes
from django.core import exceptions
from django.db import DEFAULT_DB_ALIAS, router


def _get_all_permissions(opts):
    """
    This is a comment
    """
    return [*_get_builtin_permissions(opts), *opts.permissions]


def _get_builtin_permissions(opts):
    """
    This is a comment
    """
    perms = []
    for action in opts.default_permissions:
        perms.append(
            (
                get_permission_codename(action, opts),
                "Can %s %s" % (action, opts.verbose_name_raw),
            )
        )
    return perms


def create_permissions(
    app_config,
    verbosity=2,
    interactive=True,
    using=DEFAULT_DB_ALIAS,
    apps=global_apps,
    **kwargs,
):
    """
    This is a comment
    """
    if not app_config.models_module:
        return

    try:
        Permission = apps.get_model("auth", "Permission")
    except LookupError:
        return
    if not router.allow_migrate_model(using, Permission):
        return

    # Ensure that contenttypes are created for this app. Needed if
    # 'django.contrib.auth' is in INSTALLED_APPS before
    # 'django.contrib.contenttypes'.
    create_contenttypes(
        app_config,
        verbosity=verbosity,
        interactive=interactive,
        using=using,
        apps=apps,
        **kwargs,
    )

    app_label = app_config.label
    try:
        app_config = apps.get_app_config(app_label)
        ContentType = apps.get_model("contenttypes", "ContentType")
    except LookupError:
        return

    models = list(app_config.get_models())

    # Grab all the ContentTypes.
    ctypes = ContentType.objects.db_manager(using).get_for_models(
        *models, for_concrete_models=False
    )

    # Find all the Permissions that have a content_type for a model we're
    # looking for.  We don't need to check for codenames since we already have
    # a list of the ones we're going to create.
    all_perms = set(
        Permission.objects.using(using)
        .filter(
            content_type__in=set(ctypes.values()),
        )
        .values_list("content_type", "codename")
    )

    perms = []
    for model in models:
        ctype = ctypes[model]
        for codename, name in _get_all_permissions(model._meta):
            if (ctype.pk, codename) not in all_perms:
                permission = Permission()
                permission._state.db = using
                permission.codename = codename
                permission.name = name
                permission.content_type = ctype
                perms.append(permission)

    Permission.objects.using(using).bulk_create(perms)
    if verbosity >= 2:
        for perm in perms:
            print("Adding permission '%s'" % perm)


def get_system_username():
    """
    This is a comment
    """
    try:
        result = getpass.getuser()
    except (ImportError, KeyError):
        # KeyError will be raised by os.getpwuid() (called by getuser())
        # if there is no corresponding entry in the /etc/passwd file
        # (a very restricted chroot environment, for example).
        return ""
    return result


def get_default_username(check_db=True, database=DEFAULT_DB_ALIAS):
    """
    This is a comment
    """
    # This file is used in apps.py, it should not trigger models import.
    from django.contrib.auth import models as auth_app

    # If the User model has been swapped out, we can't make any assumptions
    # about the default user name.
    if auth_app.User._meta.swapped:
        return ""

    default_username = get_system_username()
    try:
        default_username = (
            unicodedata.normalize("NFKD", default_username)
            .encode("ascii", "ignore")
            .decode("ascii")
            .replace(" ", "")
            .lower()
        )
    except UnicodeDecodeError:
        return ""

    # Run the username validator
    try:
        auth_app.User._meta.get_field("username").run_validators(default_username)
    except exceptions.ValidationError:
        return ""

    # Don't return the default username if it is already taken.
    if check_db and default_username:
        try:
            auth_app.User._default_manager.db_manager(database).get(
                username=default_username,
            )
        except auth_app.User.DoesNotExist:
            pass
        else:
            return ""
    return default_username
