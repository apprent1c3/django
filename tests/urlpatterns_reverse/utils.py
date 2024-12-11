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
        Initializes a new instance of the class.

        Parameters
        ----------
        app_name : str
            The name of the application.
        namespace : str, optional
            The namespace for the application (default is None).

        Notes
        -----
        This constructor sets the core attributes of the class, providing a 
        foundation for further configuration and usage. The application name 
        is a required parameter, while the namespace is optional and defaults 
        to None if not specified.
        """
        self.app_name = app_name
        self.namespace = namespace

    @property
    def urls(self):
        return (self.urlpatterns, self.app_name), self.namespace

    @property
    def app_urls(self):
        return self.urlpatterns, self.app_name
