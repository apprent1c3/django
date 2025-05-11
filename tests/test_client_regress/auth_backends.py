from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class CustomUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None):
        """

        Authenticate a user based on the provided username and password.

        :param request: The current request
        :param username: The username to authenticate, defaults to None
        :param password: The password to authenticate, defaults to None
        :return: The authenticated user object if authentication is successful, otherwise None

        """
        try:
            user = CustomUser.custom_objects.get_by_natural_key(username)
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return CustomUser.custom_objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
