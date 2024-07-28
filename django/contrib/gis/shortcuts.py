import zipfile
from io import BytesIO

from django.conf import settings
from django.http import HttpResponse
from django.template import loader

# NumPy supported?
try:
    import numpy
except ImportError:
    numpy = False


def compress_kml(kml):
    """
    This is a comment
    """
    kmz = BytesIO()
    with zipfile.ZipFile(kmz, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.kml", kml.encode(settings.DEFAULT_CHARSET))
    kmz.seek(0)
    return kmz.read()


def render_to_kml(*args, **kwargs):
    """
    This is a comment
    """
    return HttpResponse(
        loader.render_to_string(*args, **kwargs),
        content_type="application/vnd.google-earth.kml+xml",
    )


def render_to_kmz(*args, **kwargs):
    """
    This is a comment
    """
    return HttpResponse(
        compress_kml(loader.render_to_string(*args, **kwargs)),
        content_type="application/vnd.google-earth.kmz",
    )
