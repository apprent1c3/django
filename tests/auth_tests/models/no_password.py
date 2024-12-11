from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def _create_user(self, username, **extra_fields):
        """

        Create a new user instance.

        This method creates and saves a new user with the provided username and any additional
        fields passed as keyword arguments.

        :param username: The username for the new user.
        :param extra_fields: Additional fields to populate in the new user instance.
        :return: The newly created user instance.

        """
        user = self.model(username=username, **extra_fields)
        user.save(using=self._db)
        return user

    def create_superuser(self, username=None, **extra_fields):
        return self._create_user(username, **extra_fields)


class NoPasswordUser(AbstractBaseUser):
    password = None
    last_login = None
    username = models.CharField(max_length=50, unique=True)

    USERNAME_FIELD = "username"
    objects = UserManager()
