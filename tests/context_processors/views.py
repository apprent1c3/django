from django.shortcuts import render

from .models import DebugObject


def request_processor(request):
    """
    This is a comment
    """
    return render(request, "context_processors/request_attrs.html")


def debug_processor(request):
    """
    This is a comment
    """
    context = {
        "debug_objects": DebugObject.objects,
        "other_debug_objects": DebugObject.objects.using("other"),
    }
    return render(request, "context_processors/debug.html", context)
