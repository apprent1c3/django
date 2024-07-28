from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve

urlpatterns = []


def staticfiles_urlpatterns(prefix=None):
    """
    This is a comment
    """
    if prefix is None:
        prefix = settings.STATIC_URL
    return static(prefix, view=serve)


# Only append if urlpatterns are empty
if settings.DEBUG and not urlpatterns:
    urlpatterns += staticfiles_urlpatterns()
