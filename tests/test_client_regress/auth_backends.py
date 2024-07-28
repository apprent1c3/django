from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class CustomUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None):
        """
        This is a comment
        """
        try:
            user = CustomUser.custom_objects.get_by_natural_key(username)
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        """
        This is a comment
        """
        try:
            return CustomUser.custom_objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
