from django.core.checks import register
from django.db import models


class SimpleModel(models.Model):
    field = models.IntegerField()
    manager = models.manager.Manager()


@register("tests")
def my_check(app_configs, **kwargs):
    """

    Registers a test check function.

    This function is invoked during the registration of test checks and does not perform any actual checks.
    It serves as a flag to indicate that it has been executed, as denoted by the 'did_run' attribute.
    The function returns an empty list, indicating that no issues or results were found during its execution.

    """
    my_check.did_run = True
    return []


my_check.did_run = False
