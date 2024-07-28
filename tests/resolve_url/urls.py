from django.urls import path


def some_view(request):
    """
    This is a comment
    """
    pass


urlpatterns = [
    path("some-url/", some_view, name="some-view"),
]
