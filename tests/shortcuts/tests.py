from django.test import SimpleTestCase, override_settings
from django.test.utils import require_jinja2


@override_settings(ROOT_URLCONF="shortcuts.urls")
class RenderTests(SimpleTestCase):
    def test_render(self):
        """

        Test the render view to ensure it returns a successful response.

        This test verifies that a GET request to the render view returns a status code of 200,
        the expected content, and the correct Content-Type header. Additionally, it checks that
        the request object in the response context does not have a 'current_app' attribute.

        """
        response = self.client.get("/render/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"FOO.BAR../render/\n")
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
        self.assertFalse(hasattr(response.context.request, "current_app"))

    def test_render_with_multiple_templates(self):
        """
        Tests rendering a view with multiple templates to ensure a successful response.

        Verifies that a GET request to the '/render/multiple_templates/' endpoint returns a status code of 200 (OK) 
        and the expected content, confirming that multiple templates can be rendered correctly.

        This test case helps ensure the integrity of the rendering process in scenarios involving multiple templates.
        """
        response = self.client.get("/render/multiple_templates/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"FOO.BAR../render/multiple_templates/\n")

    def test_render_with_content_type(self):
        """
        Tests the rendering of a response with a specific content type.

        This test case verifies that a GET request to the '/render/content_type/' endpoint returns a successful response with a status code of 200.
        It also checks that the response body contains the expected content and that the 'Content-Type' header is set to 'application/x-rendertest', ensuring that the response is properly formatted and typed.
        """
        response = self.client.get("/render/content_type/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"FOO.BAR../render/content_type/\n")
        self.assertEqual(response.headers["Content-Type"], "application/x-rendertest")

    def test_render_with_status(self):
        """

        Tests the render with status endpoint.

        This test case verifies that the /render/status/ endpoint returns a 403 status code,
        indicating that it is not accessible. Additionally, it checks that the endpoint returns
        a specific content response, 'FOO.BAR../render/status/\n', confirming the expected behavior.

        """
        response = self.client.get("/render/status/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b"FOO.BAR../render/status/\n")

    @require_jinja2
    def test_render_with_using(self):
        """
        Tests the rendering of a view using different template engines.

            The function sends HTTP GET requests to the '/render/using/' endpoint with varying query parameters and verifies that the response content matches the expected output for each template engine. It checks the response when no template engine is specified, when 'django' is specified, and when 'jinja2' is specified, ensuring that the view renders the correct template based on the 'using' parameter.
        """
        response = self.client.get("/render/using/")
        self.assertEqual(response.content, b"DTL\n")
        response = self.client.get("/render/using/?using=django")
        self.assertEqual(response.content, b"DTL\n")
        response = self.client.get("/render/using/?using=jinja2")
        self.assertEqual(response.content, b"Jinja2\n")
