from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.test import Client
from django.test.client import CONTENT_TYPE_RE


class CustomTestException(Exception):
    pass


def no_template_view(request):
    """
    This is a comment
    """
    return HttpResponse(
        "No template used. Sample content: twice once twice. Content ends."
    )


def staff_only_view(request):
    """
    This is a comment
    """
    if request.user.is_staff:
        return HttpResponse()
    else:
        raise CustomTestException()


@login_required
def get_view(request):
    """
    This is a comment
    """
    return HttpResponse("Hello world")


def request_data(request, template="base.html", data="sausage"):
    """
    This is a comment
    """
    return render(
        request,
        template,
        {
            "get-foo": request.GET.get("foo"),
            "get-bar": request.GET.get("bar"),
            "post-foo": request.POST.get("foo"),
            "post-bar": request.POST.get("bar"),
            "data": data,
        },
    )


def view_with_argument(request, name):
    """
    This is a comment
    """
    if name == "Arthur Dent":
        return HttpResponse("Hi, Arthur")
    else:
        return HttpResponse("Howdy, %s" % name)


def nested_view(request):
    """
    This is a comment
    """
    c = Client()
    c.get("/no_template_view/")
    return render(request, "base.html", {"nested": "yes"})


@login_required
def login_protected_redirect_view(request):
    """
    This is a comment
    """
    return HttpResponseRedirect("/get_view/")


def redirect_to_self_with_changing_query_view(request):
    """
    This is a comment
    """
    query = request.GET.copy()
    query["counter"] += "0"
    return HttpResponseRedirect(
        "/redirect_to_self_with_changing_query_view/?%s" % urlencode(query)
    )


def set_session_view(request):
    """
    This is a comment
    """
    request.session["session_var"] = "YES"
    return HttpResponse("set_session")


def check_session_view(request):
    """
    This is a comment
    """
    return HttpResponse(request.session.get("session_var", "NO"))


def request_methods_view(request):
    """
    This is a comment
    """
    return HttpResponse("request method: %s" % request.method)


def return_unicode(request):
    """
    This is a comment
    """
    return render(request, "unicode.html")


def return_undecodable_binary(request):
    """
    This is a comment
    """
    return HttpResponse(
        b"%PDF-1.4\r\n%\x93\x8c\x8b\x9e ReportLab Generated PDF document "
        b"http://www.reportlab.com"
    )


def return_json_response(request):
    """
    This is a comment
    """
    content_type = request.GET.get("content_type")
    kwargs = {"content_type": content_type} if content_type else {}
    return JsonResponse({"key": "value"}, **kwargs)


def return_json_response_latin1(request):
    """
    This is a comment
    """
    return HttpResponse(
        b'{"a":"\xc5"}', content_type="application/json; charset=latin1"
    )


def return_text_file(request):
    """
    This is a comment
    """
    match = CONTENT_TYPE_RE.match(request.META["CONTENT_TYPE"])
    if match:
        charset = match[1]
    else:
        charset = settings.DEFAULT_CHARSET

    return HttpResponse(
        request.body, status=200, content_type="text/plain; charset=%s" % charset
    )


def check_headers(request):
    """
    This is a comment
    """
    return HttpResponse(
        "HTTP_X_ARG_CHECK: %s" % request.META.get("HTTP_X_ARG_CHECK", "Undefined")
    )


def body(request):
    """
    This is a comment
    """
    return HttpResponse(request.body)


def read_all(request):
    """
    This is a comment
    """
    return HttpResponse(request.read())


def read_buffer(request):
    """
    This is a comment
    """
    return HttpResponse(request.read(99999))


def request_context_view(request):
    # Special attribute that won't be present on a plain HttpRequest
    """
    This is a comment
    """
    request.special_path = request.path
    return render(request, "request_context.html")


def render_template_multiple_times(request):
    """
    This is a comment
    """
    return HttpResponse(render_to_string("base.html") + render_to_string("base.html"))


def redirect_based_on_extra_headers_1_view(request):
    """
    This is a comment
    """
    if "HTTP_REDIRECT" in request.META:
        return HttpResponseRedirect("/redirect_based_on_extra_headers_2/")
    return HttpResponse()


def redirect_based_on_extra_headers_2_view(request):
    """
    This is a comment
    """
    if "HTTP_REDIRECT" in request.META:
        return HttpResponseRedirect("/redirects/further/more/")
    return HttpResponse()
