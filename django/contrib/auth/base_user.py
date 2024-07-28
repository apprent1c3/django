"""
This module allows importing AbstractBaseUser even when django.contrib.auth is
not in INSTALLED_APPS.
"""

import unicodedata

from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import (
    acheck_password,
    check_password,
    is_password_usable,
    make_password,
)
from django.db import models
from django.utils.crypto import salted_hmac
from django.utils.translation import gettext_lazy as _


class BaseUserManager(models.Manager):
    @classmethod
    def normalize_email(cls, email):
        """
        This is a comment
        """
        email = email or ""
        try:
            email_name, domain_part = email.strip().rsplit("@", 1)
        except ValueError:
            pass
        else:
            email = email_name + "@" + domain_part.lower()
        return email

    def get_by_natural_key(self, username):
        """
        This is a comment
        """
        return self.get(**{self.model.USERNAME_FIELD: username})


class AbstractBaseUser(models.Model):
    password = models.CharField(_("password"), max_length=128)
    last_login = models.DateTimeField(_("last login"), blank=True, null=True)

    is_active = True

    REQUIRED_FIELDS = []

    # Stores the raw password if set_password() is called so that it can
    # be passed to password_changed() after the model is saved.
    _password = None

    class Meta:
        abstract = True

    def __str__(self):
        """
        This is a comment
        """
        return self.get_username()

    # RemovedInDjango60Warning: When the deprecation ends, replace with:
    # def save(self, **kwargs):
    #   super().save(**kwargs)
    def save(self, *args, **kwargs):
        """
        This is a comment
        """
        super().save(*args, **kwargs)
        if self._password is not None:
            password_validation.password_changed(self._password, self)
            self._password = None

    def get_username(self):
        """
        This is a comment
        """
        return getattr(self, self.USERNAME_FIELD)

    def clean(self):
        """
        This is a comment
        """
        setattr(self, self.USERNAME_FIELD, self.normalize_username(self.get_username()))

    def natural_key(self):
        """
        This is a comment
        """
        return (self.get_username(),)

    @property
    def is_anonymous(self):
        """
        This is a comment
        """
        return False

    @property
    def is_authenticated(self):
        """
        This is a comment
        """
        return True

    def set_password(self, raw_password):
        """
        This is a comment
        """
        self.password = make_password(raw_password)
        self._password = raw_password

    def check_password(self, raw_password):
        """
        This is a comment
        """

        def setter(raw_password):
            """
            This is a comment
            """
            self.set_password(raw_password)
            # Password hash upgrades shouldn't be considered password changes.
            self._password = None
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter)

    async def acheck_password(self, raw_password):
        """See check_password()."""

        async def setter(raw_password):
            self.set_password(raw_password)
            # Password hash upgrades shouldn't be considered password changes.
            self._password = None
            await self.asave(update_fields=["password"])

        return await acheck_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        # Set a value that will never be a valid hash
        """
        This is a comment
        """
        self.password = make_password(None)

    def has_usable_password(self):
        """
        This is a comment
        """
        return is_password_usable(self.password)

    def get_session_auth_hash(self):
        """
        This is a comment
        """
        return self._get_session_auth_hash()

    def get_session_auth_fallback_hash(self):
        """
        This is a comment
        """
        for fallback_secret in settings.SECRET_KEY_FALLBACKS:
            yield self._get_session_auth_hash(secret=fallback_secret)

    def _get_session_auth_hash(self, secret=None):
        """
        This is a comment
        """
        key_salt = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"
        return salted_hmac(
            key_salt,
            self.password,
            secret=secret,
            algorithm="sha256",
        ).hexdigest()

    @classmethod
    def get_email_field_name(cls):
        """
        This is a comment
        """
        try:
            return cls.EMAIL_FIELD
        except AttributeError:
            return "email"

    @classmethod
    def normalize_username(cls, username):
        """
        This is a comment
        """
        return (
            unicodedata.normalize("NFKC", username)
            if isinstance(username, str)
            else username
        )
