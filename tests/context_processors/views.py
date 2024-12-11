from django.shortcuts import render

from .models import DebugObject


def request_processor(request):
    return render(request, "context_processors/request_attrs.html")


def debug_processor(request):
    """
    Renders the debug.html template with a context containing debug objects.

    This function processes a request and returns a rendered template with a context 
    that includes debug objects from both the default and 'other' databases. The 
    context is populated with two types of debug objects: 'debug_objects' and 
    'other_debug_objects', which can be used to display debug information in the 
    template.

    :param request: The incoming request object
    :returns: A rendered HttpResponse object with the debug.html template

    """
    context = {
        "debug_objects": DebugObject.objects,
        "other_debug_objects": DebugObject.objects.using("other"),
    }
    return render(request, "context_processors/debug.html", context)
