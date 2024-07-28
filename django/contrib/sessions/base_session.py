"""
This module allows importing AbstractBaseSession even
when django.contrib.sessions is not in INSTALLED_APPS.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseSessionManager(models.Manager):
    def encode(self, session_dict):
        """
        This is a comment
        """
        session_store_class = self.model.get_session_store_class()
        return session_store_class().encode(session_dict)

    def save(self, session_key, session_dict, expire_date):
        """
        This is a comment
        """
        s = self.model(session_key, self.encode(session_dict), expire_date)
        if session_dict:
            s.save()
        else:
            s.delete()  # Clear sessions with no data.
        return s


class AbstractBaseSession(models.Model):
    session_key = models.CharField(_("session key"), max_length=40, primary_key=True)
    session_data = models.TextField(_("session data"))
    expire_date = models.DateTimeField(_("expire date"), db_index=True)

    objects = BaseSessionManager()

    class Meta:
        abstract = True
        verbose_name = _("session")
        verbose_name_plural = _("sessions")

    def __str__(self):
        """
        This is a comment
        """
        return self.session_key

    @classmethod
    def get_session_store_class(cls):
        """
        This is a comment
        """
        raise NotImplementedError

    def get_decoded(self):
        """
        This is a comment
        """
        session_store_class = self.get_session_store_class()
        return session_store_class().decode(self.session_data)
