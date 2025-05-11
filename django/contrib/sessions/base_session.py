"""
This module allows importing AbstractBaseSession even
when django.contrib.sessions is not in INSTALLED_APPS.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseSessionManager(models.Manager):
    def encode(self, session_dict):
        """
        Return the given session dictionary serialized and encoded as a string.
        """
        session_store_class = self.model.get_session_store_class()
        return session_store_class().encode(session_dict)

    def save(self, session_key, session_dict, expire_date):
        """

        Saves a session to the database.

        This method creates a new session object with the provided key, dictionary data, and expiration date.
        If the session dictionary is not empty, it saves the session; otherwise, it deletes the existing session if any.

        :param session_key: Unique key for the session
        :param session_dict: Dictionary containing session data
        :param expire_date: Date when the session expires
        :return: The saved or deleted session object

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
        return self.session_key

    @classmethod
    def get_session_store_class(cls):
        raise NotImplementedError

    def get_decoded(self):
        session_store_class = self.get_session_store_class()
        return session_store_class().decode(self.session_data)
