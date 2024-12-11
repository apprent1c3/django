from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class CustomUserWithUniqueConstraintManager(BaseUserManager):
    def create_superuser(self, username, password):
        """

        Create a new superuser with the given username and password.

        This method instantiates a new user with the provided username, sets their
        password, and saves the user to the database. The resulting superuser object
        is then returned.

        :param username: The desired username for the superuser.
        :param password: The desired password for the superuser.
        :return: The newly created superuser instance.

        """
        user = self.model(username=username)
        user.set_password(password)
        user.save(using=self._db)
        return user


class CustomUserWithUniqueConstraint(AbstractBaseUser):
    username = models.CharField(max_length=150)

    objects = CustomUserWithUniqueConstraintManager()
    USERNAME_FIELD = "username"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["username"], name="unique_custom_username"),
        ]
