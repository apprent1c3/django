from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=255)


class CustomUserWithM2MManager(BaseUserManager):
    def create_superuser(self, username, orgs, password):
        """
        Create a new superuser account with the specified username, organizations, and password.

            :param username: The username for the superuser account.
            :param orgs: The organizations to associate with the superuser account.
            :param password: The password for the superuser account.
            :return: The newly created superuser object.
        """
        user = self.model(username=username)
        user.set_password(password)
        user.save(using=self._db)
        user.orgs.add(*orgs)
        return user


class CustomUserWithM2M(AbstractBaseUser):
    username = models.CharField(max_length=30, unique=True)
    orgs = models.ManyToManyField(Organization)

    custom_objects = CustomUserWithM2MManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["orgs"]


class CustomUserWithM2MThrough(AbstractBaseUser):
    username = models.CharField(max_length=30, unique=True)
    orgs = models.ManyToManyField(Organization, through="Membership")

    custom_objects = CustomUserWithM2MManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["orgs"]


class Membership(models.Model):
    user = models.ForeignKey(CustomUserWithM2MThrough, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
