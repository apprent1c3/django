from django.core.checks import register
from django.db import models


class SimpleModel(models.Model):
    field = models.IntegerField()
    manager = models.manager.Manager()


@register("tests")
def my_check(app_configs, **kwargs):
    """
    Registers a check that runs during the tests phase.

    This function is invoked when the application is running tests. It sets a flag to indicate that it has been executed and returns an empty list, indicating that no issues were found.

    :param app_configs: Application configurations
    :param kwargs: Additional keyword arguments
    :return: A list of issues (in this case, an empty list)
    :note: The function also sets an internal flag to track whether it has been run
    """
    my_check.did_run = True
    return []


my_check.did_run = False
