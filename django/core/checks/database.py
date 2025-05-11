from django.db import connections

from . import Tags, register


@register(Tags.database)
def check_database_backends(databases=None, **kwargs):
    """
    Checks the database backends for potential issues.

    :param databases: List of database aliases to check; if None, an empty list is returned
    :returns: List of validation issues found in the specified databases
    """
    if databases is None:
        return []
    issues = []
    for alias in databases:
        conn = connections[alias]
        issues.extend(conn.validation.check(**kwargs))
    return issues
