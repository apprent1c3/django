from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse
from django.test import SimpleTestCase
from django.views.decorators.common import no_append_slash


class NoAppendSlashTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = no_append_slash(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = no_append_slash(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_no_append_slash_decorator(self):
        @no_append_slash
        """
        .. function:: test_no_append_slash_decorator

           Tests the functionality of the :func:`no_append_slash` decorator.

           The test checks if the decorator correctly sets the ``should_append_slash`` attribute of a view function to ``False``.
           Additionally, it verifies that the decorated view function returns an instance of :class:`HttpResponse` when called with an :class:`HttpRequest` object.
        """
        def sync_view(request):
            return HttpResponse()

        self.assertIs(sync_view.should_append_slash, False)
        self.assertIsInstance(sync_view(HttpRequest()), HttpResponse)

    async def test_no_append_slash_decorator_async_view(self):
        @no_append_slash
        """
        Test the no_append_slash decorator with an asynchronous view.

        This test case checks that the no_append_slash decorator correctly sets the 
        should_append_slash attribute of the view to False, and that the view returns 
        an HttpResponse instance when called with an HttpRequest object.

        The no_append_slash decorator is expected to prevent the view from appending a 
        slash to the URL. This test verifies the decorator's functionality in the 
        context of an asynchronous view.

        :raises AssertionError: If the should_append_slash attribute is not False or 
            the view does not return an HttpResponse instance.

        """
        async def async_view(request):
            return HttpResponse()

        self.assertIs(async_view.should_append_slash, False)
        self.assertIsInstance(await async_view(HttpRequest()), HttpResponse)
