from django.urls import path, re_path

from . import views


class URLObject:
    urlpatterns = [
        path("inner/", views.empty_view, name="urlobject-view"),
        re_path(
            r"^inner/(?P<arg1>[0-9]+)/(?P<arg2>[0-9]+)/$",
            views.empty_view,
            name="urlobject-view",
        ),
        re_path(r"^inner/\+\\\$\*/$", views.empty_view, name="urlobject-special-view"),
    ]

    def __init__(self, app_name, namespace=None):
        """
        Initializes an instance of the class with application metadata.

        :param app_name: The name of the application.
        :param namespace: Optional namespace for the application. Defaults to None.
        :returns: None
        :description: This method sets the fundamental properties of the class, including the application name and an optional namespace.
        """
        self.app_name = app_name
        self.namespace = namespace

    @property
    def urls(self):
        return (self.urlpatterns, self.app_name), self.namespace

    @property
    def app_urls(self):
        return self.urlpatterns, self.app_name
