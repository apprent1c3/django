from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class CustomUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None):
        """

        Authenticate a user based on their username and password.

        Authenticate a user by verifying their credentials. This function takes in a request and 
        optional username and password parameters. If the username and password are valid, it 
        returns the corresponding user object. If the credentials are invalid or the user does not 
        exist, it returns None.

        :param request: The incoming request object
        :param username: The username to authenticate, defaults to None
        :param password: The password to verify, defaults to None
        :rtype: CustomUser or None

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
