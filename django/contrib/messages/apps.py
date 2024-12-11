from django.apps import AppConfig
from django.contrib.messages.storage import base
from django.contrib.messages.utils import get_level_tags
from django.core.signals import setting_changed
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext_lazy as _


def update_level_tags(setting, **kwargs):
    """
    Updates the level tags used for logging based on the provided setting.

    Setting 'MESSAGE_TAGS' updates the LEVEL_TAGS defined in the base module, 
    using a SimpleLazyObject to lazily evaluate the level tags. The level tags 
    are determined by the get_level_tags function, which is not directly modified 
    by this function. Additional keyword arguments are accepted but not used in 
    the current implementation.
    """
    if setting == "MESSAGE_TAGS":
        base.LEVEL_TAGS = SimpleLazyObject(get_level_tags)


class MessagesConfig(AppConfig):
    name = "django.contrib.messages"
    verbose_name = _("Messages")

    def ready(self):
        setting_changed.connect(update_level_tags)
