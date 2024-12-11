from django.apps import AppConfig
from django.contrib.messages.storage import base
from django.contrib.messages.utils import get_level_tags
from django.core.signals import setting_changed
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext_lazy as _


def update_level_tags(setting, **kwargs):
    """

    Updates the level tags setting based on the provided configuration.

    The function takes a setting parameter and optional keyword arguments. 
    When the setting is 'MESSAGE_TAGS', it updates the base.LEVEL_TAGS with a lazily evaluated object 
    that returns the level tags when accessed.

    :param setting: The setting to be updated
    :param kwargs: Optional keyword arguments

    """
    if setting == "MESSAGE_TAGS":
        base.LEVEL_TAGS = SimpleLazyObject(get_level_tags)


class MessagesConfig(AppConfig):
    name = "django.contrib.messages"
    verbose_name = _("Messages")

    def ready(self):
        setting_changed.connect(update_level_tags)
