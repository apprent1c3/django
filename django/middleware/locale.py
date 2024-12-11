from django.conf import settings
from django.conf.urls.i18n import is_language_prefix_patterns_used
from django.http import HttpResponseRedirect
from django.urls import get_script_prefix, is_valid_path
from django.utils import translation
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin


class LocaleMiddleware(MiddlewareMixin):
    """
    Parse a request and decide what translation object to install in the
    current thread context. This allows pages to be dynamically translated to
    the language the user desires (if the language is available).
    """

    response_redirect_class = HttpResponseRedirect

    def process_request(self, request):
        urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
        (
            i18n_patterns_used,
            prefixed_default_language,
        ) = is_language_prefix_patterns_used(urlconf)
        language = translation.get_language_from_request(
            request, check_path=i18n_patterns_used
        )
        language_from_path = translation.get_language_from_path(request.path_info)
        if (
            not language_from_path
            and i18n_patterns_used
            and not prefixed_default_language
        ):
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()

    def process_response(self, request, response):
        """

        Handles the processing of HTTP responses, including handling of language and URL prefixing.

        When a 404 status code is encountered and the URL pattern indicates the use of internationalization (i18n) language prefixing,
        the function attempts to find a matching URL by prepending the current language to the URL path.

        If a valid path is found, or if a slash needs to be appended to the URL for it to be valid,
        the function returns a redirect response to the appropriate URL, taking into account the language and any necessary URL prefixing.

        In all cases, the function ensures that the 'Content-Language' header is set to the current language and
        the 'Vary' header is updated to include 'Accept-Language', to indicate that the response is dependent on the language and other request headers.

        Returns the processed HTTP response object.

        """
        language = translation.get_language()
        language_from_path = translation.get_language_from_path(request.path_info)
        urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
        (
            i18n_patterns_used,
            prefixed_default_language,
        ) = is_language_prefix_patterns_used(urlconf)

        if (
            response.status_code == 404
            and not language_from_path
            and i18n_patterns_used
            and prefixed_default_language
        ):
            # Maybe the language code is missing in the URL? Try adding the
            # language prefix and redirecting to that URL.
            language_path = "/%s%s" % (language, request.path_info)
            path_valid = is_valid_path(language_path, urlconf)
            path_needs_slash = not path_valid and (
                settings.APPEND_SLASH
                and not language_path.endswith("/")
                and is_valid_path("%s/" % language_path, urlconf)
            )

            if path_valid or path_needs_slash:
                script_prefix = get_script_prefix()
                # Insert language after the script prefix and before the
                # rest of the URL
                language_url = request.get_full_path(
                    force_append_slash=path_needs_slash
                ).replace(script_prefix, "%s%s/" % (script_prefix, language), 1)
                # Redirect to the language-specific URL as detected by
                # get_language_from_request(). HTTP caches may cache this
                # redirect, so add the Vary header.
                redirect = self.response_redirect_class(language_url)
                patch_vary_headers(redirect, ("Accept-Language", "Cookie"))
                return redirect

        if not (i18n_patterns_used and language_from_path):
            patch_vary_headers(response, ("Accept-Language",))
        response.headers.setdefault("Content-Language", language)
        return response
