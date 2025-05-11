from django.http import Http404
from django.utils.translation import gettext as _


def feed(request, url, feed_dict=None):
    """
    Returns a syndication feed instance for the given URL, using the provided feed dictionary for configuration. 
    The feed dictionary maps URLs to feed classes, and this function instantiates the corresponding feed class 
    based on the provided URL and returns its instance. The function is provided for backwards compatibility.
    """
    if not feed_dict:
        raise Http404(_("No feeds are registered."))

    slug = url.partition("/")[0]
    try:
        f = feed_dict[slug]
    except KeyError:
        raise Http404(_("Slug %r isn’t registered.") % slug)

    instance = f()
    instance.feed_url = getattr(f, "feed_url", None) or request.path
    instance.title_template = f.title_template or ("feeds/%s_title.html" % slug)
    instance.description_template = f.description_template or (
        "feeds/%s_description.html" % slug
    )
    return instance(request)
