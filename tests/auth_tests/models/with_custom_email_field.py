from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.db import models


class CustomEmailFieldUserManager(BaseUserManager):
    def create_user(self, username, password, email):
        """
        Creates a new user with the provided credentials.

        :param username: The desired username for the new user
        :param password: The password for the new user
        :param email: The email address associated with the new user
        :return: The newly created user object

        This method initializes a new user instance with the given username, sets the password,
        and assigns the provided email address. The new user is then saved to the database.

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
