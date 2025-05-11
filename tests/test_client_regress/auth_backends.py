from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class CustomUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None):
        """
        Authenticate a user by checking their credentials.

        :param request: The incoming request object
        :param username: The username to authenticate
        :param password: The password to verify
        :return: The authenticated user object if credentials are valid, otherwise None
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
