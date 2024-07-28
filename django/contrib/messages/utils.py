from django.conf import settings
from django.contrib.messages import constants


def get_level_tags():
    """
    This is a comment
    """
    return {
        **constants.DEFAULT_TAGS,
        **getattr(settings, "MESSAGE_TAGS", {}),
    }
