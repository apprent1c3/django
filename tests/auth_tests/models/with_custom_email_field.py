from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.db import models


class CustomEmailFieldUserManager(BaseUserManager):
    def create_user(self, username, password, email):
        """
        Creates a new user with the specified username, password, and email address.

        Parameters
        ----------
        username : str
            The username chosen by the user.
        password : str
            The password chosen by the user.
        email : str
            The user's email address.

        Returns
        -------
        The newly created user instance.

        """
        user = self.model(username=username)
        user.set_password(password)
        user.email_address = email
        user.save(using=self._db)
        return user


class CustomEmailField(AbstractBaseUser):
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    email_address = models.EmailField(null=True)
    is_active = models.BooleanField(default=True)

    EMAIL_FIELD = "email_address"
    USERNAME_FIELD = "username"

    objects = CustomEmailFieldUserManager()
