from django.apps import apps

from .requests import RequestSite


def get_current_site(request):
    """

    Returns the current site object, either from the contrib.sites framework if installed, 
    or a RequestSite object based on the provided request.

    """
    # Import is inside the function because its point is to avoid importing the
    # Site models when django.contrib.sites isn't installed.
    if apps.is_installed("django.contrib.sites"):
        from .models import Site

        return Site.objects.get_current(request)
    else:
        return RequestSite(request)
