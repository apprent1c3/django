from django.contrib.auth.models import (
    AbstractBaseUser,
    AbstractUser,
    BaseUserManager,
    Group,
    Permission,
    PermissionsMixin,
    UserManager,
)
from django.db import models


# The custom user uses email as the unique identifier, and requires
# that every user provide a date of birth. This lets us test
# changes in username datatype, and non-text required fields.
class CustomUserManager(BaseUserManager):
    def create_user(self, email, date_of_birth, password=None, **fields):
        """

        Creates and saves a new User instance with the provided email, date of birth, and optional password.

        :param email: The email address of the user
        :param date_of_birth: The user's date of birth
        :param password: The user's password (optional)
        :param fields: Additional fields to set on the user (optional)
        :raises ValueError: If no email address is provided
        :return: The newly created User instance

        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            email=self.normalize_email(email), date_of_birth=date_of_birth, **fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, date_of_birth, **fields):
        u = self.create_user(
            email, password=password, date_of_birth=date_of_birth, **fields
        )
        u.is_admin = True
        u.save(using=self._db)
        return u


class CustomUser(AbstractBaseUser):
    email = models.EmailField(verbose_name="email address", max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    date_of_birth = models.DateField()
    first_name = models.CharField(max_length=50)

    custom_objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["date_of_birth", "first_name"]

    def __str__(self):
        return self.email

    # Maybe required?
    def get_group_permissions(self, obj=None):
        return set()

    def get_all_permissions(self, obj=None):
        return set()

    def has_perm(self, perm, obj=None):
        return True

    def has_perms(self, perm_list, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    # Admin required fields
    @property
    def is_staff(self):
        return self.is_admin


class RemoveGroupsAndPermissions:
    """
    A context manager to temporarily remove the groups and user_permissions M2M
    fields from the AbstractUser class, so they don't clash with the
    related_name sets.
    """

    def __enter__(self):
        """

        Enters the runtime context for modifying the many-to-many relationships of the PermissionsMixin and AbstractUser classes, specifically the 'groups' and 'user_permissions' relationships.

        """
        self._old_au_local_m2m = AbstractUser._meta.local_many_to_many
        self._old_pm_local_m2m = PermissionsMixin._meta.local_many_to_many
        groups = models.ManyToManyField(Group, blank=True)
        groups.contribute_to_class(PermissionsMixin, "groups")
        user_permissions = models.ManyToManyField(Permission, blank=True)
        user_permissions.contribute_to_class(PermissionsMixin, "user_permissions")
        PermissionsMixin._meta.local_many_to_many = [groups, user_permissions]
        AbstractUser._meta.local_many_to_many = [groups, user_permissions]

    def __exit__(self, exc_type, exc_value, traceback):
        AbstractUser._meta.local_many_to_many = self._old_au_local_m2m
        PermissionsMixin._meta.local_many_to_many = self._old_pm_local_m2m


class CustomUserWithoutIsActiveField(AbstractBaseUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)

    objects = UserManager()

    USERNAME_FIELD = "username"


# The extension user is a simple extension of the built-in user class,
# adding a required date_of_birth field. This allows us to check for
# any hard references to the name "User" in forms/handlers etc.
with RemoveGroupsAndPermissions():

    class ExtensionUser(AbstractUser):
        date_of_birth = models.DateField()

        custom_objects = UserManager()

        REQUIRED_FIELDS = AbstractUser.REQUIRED_FIELDS + ["date_of_birth"]
