from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.common import no_append_slash
from django.views.generic import View


def empty_view(request, *args, **kwargs):
    """
    This is a comment
    """
    return HttpResponse()


@no_append_slash
def sensitive_fbv(request, *args, **kwargs):
    """
    This is a comment
    """
    return HttpResponse()


@method_decorator(no_append_slash, name="dispatch")
class SensitiveCBV(View):
    def get(self, *args, **kwargs):
        """
        This is a comment
        """
        return HttpResponse()
