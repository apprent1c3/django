import os

from . import Error, Tags, register

E001 = Error(
    "You should not set the DJANGO_ALLOW_ASYNC_UNSAFE environment variable in "
    "deployment. This disables async safety protection.",
    id="async.E001",
)


@register(Tags.async_support, deploy=True)
def check_async_unsafe(app_configs, **kwargs):
    """
    Checks if the environment variable DJANGO_ALLOW_ASYNC_UNSAFE is set, indicating potential issues with asynchronous support.

        :param app_configs: Application configurations
        :param kwargs: Additional keyword arguments
        :return: A list of error codes (in this case, [E001] if the environment variable is set) indicating async unsafe operations are allowed, otherwise an empty list.
    """
    if os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE"):
        return [E001]
    return []
