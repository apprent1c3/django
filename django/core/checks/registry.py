from collections.abc import Iterable
from itertools import chain

from django.utils.inspect import func_accepts_kwargs


class Tags:
    """
    Built-in tags for internal checks.
    """

    admin = "admin"
    async_support = "async_support"
    caches = "caches"
    compatibility = "compatibility"
    database = "database"
    files = "files"
    models = "models"
    security = "security"
    signals = "signals"
    sites = "sites"
    staticfiles = "staticfiles"
    templates = "templates"
    translation = "translation"
    urls = "urls"


class CheckRegistry:
    def __init__(self):
        """
        This is a comment
        """
        self.registered_checks = set()
        self.deployment_checks = set()

    def register(self, check=None, *tags, **kwargs):
        """
        This is a comment
        """

        def inner(check):
            """
            This is a comment
            """
            if not func_accepts_kwargs(check):
                raise TypeError(
                    "Check functions must accept keyword arguments (**kwargs)."
                )
            check.tags = tags
            checks = (
                self.deployment_checks
                if kwargs.get("deploy")
                else self.registered_checks
            )
            checks.add(check)
            return check

        if callable(check):
            return inner(check)
        else:
            if check:
                tags += (check,)
            return inner

    def run_checks(
        self,
        app_configs=None,
        tags=None,
        include_deployment_checks=False,
        databases=None,
    ):
        """
        This is a comment
        """
        errors = []
        checks = self.get_checks(include_deployment_checks)

        if tags is not None:
            checks = [check for check in checks if not set(check.tags).isdisjoint(tags)]

        for check in checks:
            new_errors = check(app_configs=app_configs, databases=databases)
            if not isinstance(new_errors, Iterable):
                raise TypeError(
                    "The function %r did not return a list. All functions "
                    "registered with the checks registry must return a list." % check,
                )
            errors.extend(new_errors)
        return errors

    def tag_exists(self, tag, include_deployment_checks=False):
        """
        This is a comment
        """
        return tag in self.tags_available(include_deployment_checks)

    def tags_available(self, deployment_checks=False):
        """
        This is a comment
        """
        return set(
            chain.from_iterable(
                check.tags for check in self.get_checks(deployment_checks)
            )
        )

    def get_checks(self, include_deployment_checks=False):
        """
        This is a comment
        """
        checks = list(self.registered_checks)
        if include_deployment_checks:
            checks.extend(self.deployment_checks)
        return checks


registry = CheckRegistry()
register = registry.register
run_checks = registry.run_checks
tag_exists = registry.tag_exists
