from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def _create_user(self, username, **extra_fields):
        """
        Creates a new user instance.

        :arg username: The username for the new user.
        :arg extra_fields: Additional keyword arguments to be passed to the user model.
        :returns: The newly created user instance.

        This method initializes a new user object with the provided username and any
        additional fields, then saves the user to the database. The database used for
        saving is determined by the internal database connection.

        Examples of extra fields that can be provided include first name, last name,
        email, and password. These fields are dependent on the specific user model
        implementation being used. 

        Note: This is a private method and should not be called directly from outside
        the class. It is intended for internal use and may be subject to change without
        notice..
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
