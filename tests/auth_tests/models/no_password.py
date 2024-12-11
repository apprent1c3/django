from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def _create_user(self, username, **extra_fields):
        """
        Create a new user instance with the given username and additional fields.

        This method instantiates a new user object using the provided username and any
        additional keyword arguments, then saves the user to the database. The newly
        created user is returned by the method.

        :param username: The username of the new user.
        :param extra_fields: Additional keyword arguments to be used when creating the user.
        :return: The new user instance.
        :rtype: self.model

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
