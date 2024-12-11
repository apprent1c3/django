from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import path

site = admin.AdminSite(name="custom_user_admin")


class CustomUserAdmin(UserAdmin):
    def log_change(self, request, obj, message):
        # LogEntry.user column doesn't get altered to expect a UUID, so set an
        # integer manually to avoid causing an error.
        """
        Records a change to the specified object with the given message, 
        temporarily switching to a system user to perform the logging action.

        :param request: The current request.
        :param obj: The object being changed.
        :param message: A message describing the change made to the object.

        This function ensures that all changes are logged under a specific user account, 
        regardless of the actual user making the change, providing consistency in logging.

        """
        original_pk = request.user.pk
        request.user.pk = 1
        super().log_change(request, obj, message)
        request.user.pk = original_pk


site.register(get_user_model(), CustomUserAdmin)

urlpatterns = [
    path("admin/", site.urls),
]
