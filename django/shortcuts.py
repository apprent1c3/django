"""
This module collects helper functions and classes that "span" multiple levels
of MVC. In other words, these functions/classes introduce controlled coupling
for convenience's sake.
"""

from django.http import (
    Http404,
    HttpResponse,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.template import loader
from django.urls import NoReverseMatch, reverse
from django.utils.functional import Promise


def render(
    request, template_name, context=None, content_type=None, status=None, using=None
):
    """
    Return an HttpResponse whose content is filled with the result of calling
    django.template.loader.render_to_string() with the passed arguments.
    """
    content = loader.render_to_string(template_name, context, request, using=using)
    return HttpResponse(content, content_type, status)


def redirect(to, *args, permanent=False, **kwargs):
    """
    Return an HttpResponseRedirect to the appropriate URL for the arguments
    passed.

    The arguments could be:

        * A model: the model's `get_absolute_url()` function will be called.

        * A view name, possibly with arguments: `urls.reverse()` will be used
          to reverse-resolve the name.

        * A URL, which will be used as-is for the redirect location.

    Issues a temporary redirect by default; pass permanent=True to issue a
    permanent redirect.
    """
    redirect_class = (
        HttpResponsePermanentRedirect if permanent else HttpResponseRedirect
    )
    return redirect_class(resolve_url(to, *args, **kwargs))


def _get_queryset(klass):
    """
    Return a QuerySet or a Manager.
    Duck typing in action: any class with a `get()` method (for
    get_object_or_404) or a `filter()` method (for get_list_or_404) might do
    the job.
    """
    # If it is a model class or anything else with ._default_manager
    if hasattr(klass, "_default_manager"):
        return klass._default_manager.all()
    return klass


def get_object_or_404(klass, *args, **kwargs):
    """
    Retrieves an object of the specified class, raising an Http404 exception if the object does not exist, or MultipleObjectsReturned if more than one object is found.
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "get"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_404() must be a Model, Manager, "
            "or QuerySet, not '%s'." % klass__name
        )
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        raise Http404(
            "No %s matches the given query." % queryset.model._meta.object_name
        )


async def aget_object_or_404(klass, *args, **kwargs):
    """
    Retrieve an object asynchronously, raising a 404 error if it does not exist.

    This function is similar to get_object_or_404(), but uses asynchronous queries.
    It is designed to retrieve a single object from a model, manager, or queryset,
    and raises an Http404 exception if no object matches the given query parameters.
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "aget"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to aget_object_or_404() must be a Model, Manager, or "
            f"QuerySet, not '{klass__name}'."
        )
    try:
        return await queryset.aget(*args, **kwargs)
    except queryset.model.DoesNotExist:
        raise Http404(f"No {queryset.model._meta.object_name} matches the given query.")


def get_list_or_404(klass, *args, **kwargs):
    """
    Retrieves a list of objects from the database, raising an Http404 exception if no objects match the query. 
    Supports filtering using model, manager, or queryset objects with arbitrary keyword and positional arguments.
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "filter"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_list_or_404() must be a Model, Manager, or "
            "QuerySet, not '%s'." % klass__name
        )
    obj_list = list(queryset.filter(*args, **kwargs))
    if not obj_list:
        raise Http404(
            "No %s matches the given query." % queryset.model._meta.object_name
        )
    return obj_list


async def aget_list_or_404(klass, *args, **kwargs):
    """
    Fetches a list of objects from the database asynchronously, raising a 404 error if no objects match the given query.

        :param klass: The model, manager, or queryset to query from
        :param args: Positional arguments to pass to the filter method
        :param kwargs: Keyword arguments to pass to the filter method
        :return: A list of objects matching the query
        :raises ValueError: If the first argument is not a model, manager, or queryset
        :raises Http404: If no objects match the given query
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "filter"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to aget_list_or_404() must be a Model, Manager, or "
            f"QuerySet, not '{klass__name}'."
        )
    obj_list = [obj async for obj in queryset.filter(*args, **kwargs)]
    if not obj_list:
        raise Http404(f"No {queryset.model._meta.object_name} matches the given query.")
    return obj_list


def resolve_url(to, *args, **kwargs):
    """
    Return a URL appropriate for the provided arguments, handling models, view names, and plain URLs.
    """
    # If it's a model, use get_absolute_url()
    if hasattr(to, "get_absolute_url"):
        return to.get_absolute_url()

    if isinstance(to, Promise):
        # Expand the lazy instance, as it can cause issues when it is passed
        # further to some Python functions like urlparse.
        to = str(to)

    # Handle relative URLs
    if isinstance(to, str) and to.startswith(("./", "../")):
        return to

    # Next try a reverse URL resolution.
    try:
        return reverse(to, args=args, kwargs=kwargs)
    except NoReverseMatch:
        # If this is a callable, re-raise.
        if callable(to):
            raise
        # If this doesn't "feel" like a URL, re-raise.
        if "/" not in to and "." not in to:
            raise

    # Finally, fall back and assume it's a URL
    return to
