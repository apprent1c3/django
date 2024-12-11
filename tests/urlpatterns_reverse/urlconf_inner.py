from django.http import HttpResponse
from django.template import Context, Template
from django.urls import path


def inner_view(request):
    """

    Generates a simple HTTP response containing URLs for the 'outer' and 'inner' views.

    The function renders a template that uses Django's built-in URL reversing to generate
    absolute URLs for the 'outer' and 'inner' views, and returns the rendered content
    as an HTTP response.

    The output will be a comma-separated string in the format 'outer:<outer_url>,inner:<inner_url>',
    where <outer_url> and <inner_url> are the absolute URLs for the respective views.

    """
    content = Template(
        '{% url "outer" as outer_url %}outer:{{ outer_url }},'
        '{% url "inner" as inner_url %}inner:{{ inner_url }}'
    ).render(Context())
    return HttpResponse(content)


urlpatterns = [
    path("second_test/", inner_view, name="inner"),
]
