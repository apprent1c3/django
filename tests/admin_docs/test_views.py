import sys
import unittest

from django.conf import settings
from django.contrib import admin
from django.contrib.admindocs import utils, views
from django.contrib.admindocs.views import get_return_data_type, simplify_regex
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import fields
from django.test import SimpleTestCase, modify_settings, override_settings
from django.test.utils import captured_stderr
from django.urls import include, path, reverse
from django.utils.functional import SimpleLazyObject

from .models import Company, Person
from .tests import AdminDocsTestCase, TestDataMixin


@unittest.skipUnless(utils.docutils_is_available, "no docutils installed.")
class AdminDocViewTests(TestDataMixin, AdminDocsTestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_index(self):
        response = self.client.get(reverse("django-admindocs-docroot"))
        self.assertContains(response, "<h1>Documentation</h1>", html=True)
        self.assertContains(
            response,
            '<div id="site-name"><a href="/admin/">Django administration</a></div>',
        )
        self.client.logout()
        response = self.client.get(reverse("django-admindocs-docroot"), follow=True)
        # Should display the login screen
        self.assertContains(
            response, '<input type="hidden" name="next" value="/admindocs/">', html=True
        )

    def test_bookmarklets(self):
        """
        Tests the availability of bookmarklets in the admin documentation view.

        Checks if the admin documentation bookmarklets page contains the expected content,
        specifically the URL path related to admin documentation views. 

        This test ensures that the bookmarklets are properly configured and accessible 
        through the admin documentation interface. 

        Returns:
            None

        Raises:
            AssertionError: If the expected content is not found in the response.

        """
        response = self.client.get(reverse("django-admindocs-bookmarklets"))
        self.assertContains(response, "/admindocs/views/")

    def test_templatetag_index(self):
        """

        Tests that the templatetag index page contains the expected template tags.

        Verifies that the 'extends' built-in template tag is listed on the index page,
        which contains a comprehensive list of available template tags in the Django project.

        """
        response = self.client.get(reverse("django-admindocs-tags"))
        self.assertContains(
            response, '<h3 id="built_in-extends">extends</h3>', html=True
        )

    def test_templatefilter_index(self):
        response = self.client.get(reverse("django-admindocs-filters"))
        self.assertContains(response, '<h3 id="built_in-first">first</h3>', html=True)

    def test_view_index(self):
        """

        Tests the index view of the Django admin documentation.

        This test case checks the response of the index view to ensure it contains the expected content.
        It verifies the presence of links to specific views, such as the BaseAdminDocsView and XViewCallableObject,
        as well as other relevant information like the namespace and function name.
        The test validates the HTML content of the response to guarantee the correct rendering of the index page.

        """
        response = self.client.get(reverse("django-admindocs-views-index"))
        self.assertContains(
            response,
            '<h3><a href="/admindocs/views/django.contrib.admindocs.views.'
            'BaseAdminDocsView/">/admindocs/</a></h3>',
            html=True,
        )
        self.assertContains(response, "Views by namespace test")
        self.assertContains(response, "Name: <code>test:func</code>.")
        self.assertContains(
            response,
            '<h3><a href="/admindocs/views/admin_docs.views.XViewCallableObject/">'
            "/xview/callable_object_without_xview/</a></h3>",
            html=True,
        )

    def test_view_index_with_method(self):
        """
        Views that are methods are listed correctly.
        """
        response = self.client.get(reverse("django-admindocs-views-index"))
        self.assertContains(
            response,
            "<h3>"
            '<a href="/admindocs/views/django.contrib.admin.sites.AdminSite.index/">'
            "/admin/</a></h3>",
            html=True,
        )

    def test_view_detail(self):
        """

        Tests the detail view for a specific admin docs view.

        This test case verifies that the detail view for the given admin docs view
        returns a successful response and contains the expected view description.

        The test simulates a GET request to the detail view URL and checks that the
        response contains the view's description text.

        """
        url = reverse(
            "django-admindocs-views-detail",
            args=["django.contrib.admindocs.views.BaseAdminDocsView"],
        )
        response = self.client.get(url)
        # View docstring
        self.assertContains(response, "Base view for admindocs views.")

    @override_settings(ROOT_URLCONF="admin_docs.namespace_urls")
    def test_namespaced_view_detail(self):
        """

        Tests the detail view of a namespaced view in the admin documentation system.

        Verifies that the view detail page correctly displays the view's fully qualified name.

        This test case ensures that the admin documentation system properly handles namespaced views
        and provides accurate information about their location and implementation.

        """
        url = reverse(
            "django-admindocs-views-detail", args=["admin_docs.views.XViewClass"]
        )
        response = self.client.get(url)
        self.assertContains(response, "<h1>admin_docs.views.XViewClass</h1>")

    def test_view_detail_illegal_import(self):
        """

        Tests the detail view of a Django admin doc for a module that was not imported.

        This test case checks that when a user attempts to access the detail view of a non-imported module,
        the server returns a 404 status code and the module is not loaded into memory.

        """
        url = reverse(
            "django-admindocs-views-detail",
            args=["urlpatterns_reverse.nonimported_module.view"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("urlpatterns_reverse.nonimported_module", sys.modules)

    def test_view_detail_as_method(self):
        """
        Views that are methods can be displayed.
        """
        url = reverse(
            "django-admindocs-views-detail",
            args=["django.contrib.admin.sites.AdminSite.index"],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_model_index(self):
        response = self.client.get(reverse("django-admindocs-models-index"))
        self.assertContains(
            response,
            '<h2 id="app-auth">Authentication and Authorization (django.contrib.auth)'
            "</h2>",
            html=True,
        )

    def test_template_detail(self):
        """

        Tests the template detail view by making a GET request to the django-admindocs-templates URL
        with a specific template name and checking that the response contains the expected HTML content.

        The test verifies that the template detail page displays the correct title, including the name of the template
        being viewed, which in this case is 'admin_doc/template_detail.html'. This ensures that the template
        detail view is functioning correctly and displaying the expected information.

        """
        response = self.client.get(
            reverse(
                "django-admindocs-templates", args=["admin_doc/template_detail.html"]
            )
        )
        self.assertContains(
            response,
            "<h1>Template: <q>admin_doc/template_detail.html</q></h1>",
            html=True,
        )

    def test_template_detail_loader(self):
        """

        Tests the detail loader template for the view_for_loader_test.html template.

        This test checks if the template detail page for the specified template contains the
        expected template name, ensuring that the detail loader is functioning correctly.

        The test sends a GET request to the django-admindocs-templates view, passing the
        template name as an argument, and verifies that the response contains the template
        name, confirming that the detail loader is working as expected.

        """
        response = self.client.get(
            reverse("django-admindocs-templates", args=["view_for_loader_test.html"])
        )
        self.assertContains(response, "view_for_loader_test.html</code></li>")

    def test_missing_docutils(self):
        """
        :func:`test_missing_docutils`: 
            Tests the admin documentation system's handling of missing docutils library.

            Verifies that when the docutils library is not available, the admin documentation 
            root page displays an error message with instructions to install the library, 
            while still showing the standard Django administration site name.
        """
        utils.docutils_is_available = False
        try:
            response = self.client.get(reverse("django-admindocs-docroot"))
            self.assertContains(
                response,
                "<h3>The admin documentation system requires Python’s "
                '<a href="https://docutils.sourceforge.io/">docutils</a> '
                "library.</h3>"
                "<p>Please ask your administrators to install "
                '<a href="https://pypi.org/project/docutils/">docutils</a>.</p>',
                html=True,
            )
            self.assertContains(
                response,
                '<div id="site-name"><a href="/admin/">Django administration</a></div>',
            )
        finally:
            utils.docutils_is_available = True

    @modify_settings(INSTALLED_APPS={"remove": "django.contrib.sites"})
    @override_settings(SITE_ID=None)  # will restore SITE_ID after the test
    def test_no_sites_framework(self):
        """
        Without the sites framework, should not access SITE_ID or Site
        objects. Deleting settings is fine here as UserSettingsHolder is used.
        """
        Site.objects.all().delete()
        del settings.SITE_ID
        response = self.client.get(reverse("django-admindocs-views-index"))
        self.assertContains(response, "View documentation")

    def test_callable_urlconf(self):
        """
        Index view should correctly resolve view patterns when ROOT_URLCONF is
        not a string.
        """

        def urlpatterns():
            return (
                path("admin/doc/", include("django.contrib.admindocs.urls")),
                path("admin/", admin.site.urls),
            )

        with self.settings(ROOT_URLCONF=SimpleLazyObject(urlpatterns)):
            response = self.client.get(reverse("django-admindocs-views-index"))
            self.assertEqual(response.status_code, 200)


@unittest.skipUnless(utils.docutils_is_available, "no docutils installed.")
class AdminDocViewDefaultEngineOnly(TestDataMixin, AdminDocsTestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_template_detail_path_traversal(self):
        """

        Tests that attempting to access template details using a path traversal attack is correctly prevented.

        This test ensures that the view for template details does not allow an attacker to access arbitrary file system paths by providing a specially crafted path.
        It checks that the view returns a 400 Bad Request status code for such attempts, indicating that the request was invalid.

        The test covers various types of path traversal attempts, including absolute paths and paths with parent directory references.

        """
        cases = ["/etc/passwd", "../passwd"]
        for fpath in cases:
            with self.subTest(path=fpath):
                response = self.client.get(
                    reverse("django-admindocs-templates", args=[fpath]),
                )
                self.assertEqual(response.status_code, 400)


@override_settings(
    TEMPLATES=[
        {
            "NAME": "ONE",
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,
        },
        {
            "NAME": "TWO",
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,
        },
    ]
)
@unittest.skipUnless(utils.docutils_is_available, "no docutils installed.")
class AdminDocViewWithMultipleEngines(AdminDocViewTests):
    def test_templatefilter_index(self):
        # Overridden because non-trivial TEMPLATES settings aren't supported
        # but the page shouldn't crash (#24125).
        """

        Tests that the template filter index page returns a successful response with the correct title.

        The page is expected to contain the title 'Template filters' in its HTML output, 
        indicating that the template filter index page is functioning as expected.

        """
        response = self.client.get(reverse("django-admindocs-filters"))
        self.assertContains(response, "<title>Template filters</title>", html=True)

    def test_templatetag_index(self):
        # Overridden because non-trivial TEMPLATES settings aren't supported
        # but the page shouldn't crash (#24125).
        response = self.client.get(reverse("django-admindocs-tags"))
        self.assertContains(response, "<title>Template tags</title>", html=True)


@unittest.skipUnless(utils.docutils_is_available, "no docutils installed.")
class TestModelDetailView(TestDataMixin, AdminDocsTestCase):
    def setUp(self):
        """
        Sets up the test environment by logging in as a superuser and capturing any standard error output.
        The function prepares the client for testing by simulating a login with elevated privileges and directs the error stream to a controlled buffer, then uses the client to retrieve a specific admin documentation page, specifically the detail page for the 'Person' model in the 'admin_docs' app, storing the response in the 'response' attribute for later use in testing.
        """
        self.client.force_login(self.superuser)
        with captured_stderr() as self.docutils_stderr:
            self.response = self.client.get(
                reverse("django-admindocs-models-detail", args=["admin_docs", "Person"])
            )

    def test_table_headers(self):
        """
        Verifies that the HTML response contains the expected table headers.

        The function checks for the presence of specific table headers, including Method, Arguments, Description, Field, and Type. 
        It ensures that each header appears the correct number of times in the response, as specified in the test cases.

         ARGS: None

         RETURNS: None

         RAISES: AssertionError if any of the expected table headers are missing or appear an incorrect number of times.
        """
        tests = [
            ("Method", 1),
            ("Arguments", 1),
            ("Description", 2),
            ("Field", 1),
            ("Type", 1),
            ("Method", 1),
        ]
        for table_header, count in tests:
            self.assertContains(
                self.response, f'<th scope="col">{table_header}</th>', count=count
            )

    def test_method_excludes(self):
        """
        Methods that begin with strings defined in
        ``django.contrib.admindocs.views.MODEL_METHODS_EXCLUDE``
        shouldn't be displayed in the admin docs.
        """
        self.assertContains(self.response, "<td>get_full_name</td>")
        self.assertNotContains(self.response, "<td>_get_full_name</td>")
        self.assertNotContains(self.response, "<td>add_image</td>")
        self.assertNotContains(self.response, "<td>delete_image</td>")
        self.assertNotContains(self.response, "<td>set_status</td>")
        self.assertNotContains(self.response, "<td>save_changes</td>")

    def test_methods_with_arguments(self):
        """
        Methods that take arguments should also displayed.
        """
        self.assertContains(self.response, "<h3>Methods with arguments</h3>")
        self.assertContains(self.response, "<td>rename_company</td>")
        self.assertContains(self.response, "<td>dummy_function</td>")
        self.assertContains(self.response, "<td>dummy_function_keyword_only_arg</td>")
        self.assertContains(self.response, "<td>all_kinds_arg_function</td>")
        self.assertContains(self.response, "<td>suffix_company_name</td>")

    def test_methods_with_arguments_display_arguments(self):
        """
        Methods with arguments should have their arguments displayed.
        """
        self.assertContains(self.response, "<td>new_name</td>")
        self.assertContains(self.response, "<td>keyword_only_arg</td>")

    def test_methods_with_arguments_display_arguments_default_value(self):
        """
        Methods with keyword arguments should have their arguments displayed.
        """
        self.assertContains(self.response, "<td>suffix=&#x27;ltd&#x27;</td>")

    def test_methods_with_multiple_arguments_display_arguments(self):
        """
        Methods with multiple arguments should have all their arguments
        displayed, but omitting 'self'.
        """
        self.assertContains(
            self.response, "<td>baz, rox, *some_args, **some_kwargs</td>"
        )
        self.assertContains(self.response, "<td>position_only_arg, arg, kwarg</td>")

    def test_instance_of_property_methods_are_displayed(self):
        """Model properties are displayed as fields."""
        self.assertContains(self.response, "<td>a_property</td>")

    def test_instance_of_cached_property_methods_are_displayed(self):
        """Model cached properties are displayed as fields."""
        self.assertContains(self.response, "<td>a_cached_property</td>")

    def test_method_data_types(self):
        """
        Tests the data types returned by specific methods of a Person object to ensure they match the expected types. 
        The tested methods include get_status_count, which is expected to return an integer, and get_groups_list, which is expected to return a list. 
        This test creates a Person object associated with a Company object to provide a valid context for the method calls.
        """
        company = Company.objects.create(name="Django")
        person = Person.objects.create(
            first_name="Human", last_name="User", company=company
        )
        self.assertEqual(
            get_return_data_type(person.get_status_count.__name__), "Integer"
        )
        self.assertEqual(get_return_data_type(person.get_groups_list.__name__), "List")

    def test_descriptions_render_correctly(self):
        """
        The ``description`` field should render correctly for each field type.
        """
        # help text in fields
        self.assertContains(
            self.response, "<td>first name - The person's first name</td>"
        )
        self.assertContains(
            self.response, "<td>last name - The person's last name</td>"
        )

        # method docstrings
        self.assertContains(self.response, "<p>Get the full name of the person</p>")

        link = '<a class="reference external" href="/admindocs/models/%s/">%s</a>'
        markup = "<p>the related %s object</p>"
        company_markup = markup % (link % ("admin_docs.company", "admin_docs.Company"))

        # foreign keys
        self.assertContains(self.response, company_markup)

        # foreign keys with help text
        self.assertContains(self.response, "%s\n - place of work" % company_markup)

        # many to many fields
        self.assertContains(
            self.response,
            "number of related %s objects"
            % (link % ("admin_docs.group", "admin_docs.Group")),
        )
        self.assertContains(
            self.response,
            "all related %s objects"
            % (link % ("admin_docs.group", "admin_docs.Group")),
        )

        # "raw" and "include" directives are disabled
        self.assertContains(
            self.response,
            "<p>&quot;raw&quot; directive disabled.</p>",
        )
        self.assertContains(
            self.response, ".. raw:: html\n    :file: admin_docs/evilfile.txt"
        )
        self.assertContains(
            self.response,
            "<p>&quot;include&quot; directive disabled.</p>",
        )
        self.assertContains(self.response, ".. include:: admin_docs/evilfile.txt")
        out = self.docutils_stderr.getvalue()
        self.assertIn('"raw" directive disabled', out)
        self.assertIn('"include" directive disabled', out)

    def test_model_with_many_to_one(self):
        link = '<a class="reference external" href="/admindocs/models/%s/">%s</a>'
        response = self.client.get(
            reverse("django-admindocs-models-detail", args=["admin_docs", "company"])
        )
        self.assertContains(
            response,
            "number of related %s objects"
            % (link % ("admin_docs.person", "admin_docs.Person")),
        )
        self.assertContains(
            response,
            "all related %s objects"
            % (link % ("admin_docs.person", "admin_docs.Person")),
        )

    def test_model_with_no_backward_relations_render_only_relevant_fields(self):
        """
        A model with ``related_name`` of `+` shouldn't show backward
        relationship links.
        """
        response = self.client.get(
            reverse("django-admindocs-models-detail", args=["admin_docs", "family"])
        )
        fields = response.context_data.get("fields")
        self.assertEqual(len(fields), 2)

    def test_model_docstring_renders_correctly(self):
        """
        Tests the rendering of a model's documentation string.

        This test case verifies that the documentation for a model is correctly
        displayed, including a summary, subheading, body, and model fields. The
        test checks for the presence of specific HTML elements and content in the
        response, ensuring that the documentation is properly formatted and
        contains the expected information.

        The test covers the following aspects:
            - Summary: A brief overview of the model, including related models.
            - Subheading: A section title for additional notes or information.
            - Body: The main content of the documentation, including instructions
              or important details.
            - Model fields: A list of fields in the model, including their data types
              and descriptions.

        If the test passes, it confirms that the model's documentation string is
        correctly rendered and contains the expected content and structure.
        """
        summary = (
            '<h2 class="subhead"><p>Stores information about a person, related to '
            '<a class="reference external" href="/admindocs/models/myapp.company/">'
            "myapp.Company</a>.</p></h2>"
        )
        subheading = "<p><strong>Notes</strong></p>"
        body = (
            '<p>Use <tt class="docutils literal">save_changes()</tt> when saving this '
            "object.</p>"
        )
        model_body = (
            '<dl class="docutils"><dt><tt class="'
            'docutils literal">company</tt></dt><dd>Field storing <a class="'
            'reference external" href="/admindocs/models/myapp.company/">'
            "myapp.Company</a> where the person works.</dd></dl>"
        )
        self.assertContains(self.response, "DESCRIPTION")
        self.assertContains(self.response, summary, html=True)
        self.assertContains(self.response, subheading, html=True)
        self.assertContains(self.response, body, html=True)
        self.assertContains(self.response, model_body, html=True)

    def test_model_detail_title(self):
        self.assertContains(self.response, "<h1>admin_docs.Person</h1>", html=True)

    def test_app_not_found(self):
        """
        Tests that a 404 error is raised when attempting to view details of a non-existent Django app.

        This test case simulates a GET request to the admin docs model detail page for an app that does not exist, 
        and verifies that the response contains the expected exception message and a 404 status code.
        """
        response = self.client.get(
            reverse("django-admindocs-models-detail", args=["doesnotexist", "Person"])
        )
        self.assertEqual(response.context["exception"], "App 'doesnotexist' not found")
        self.assertEqual(response.status_code, 404)

    def test_model_not_found(self):
        """
        Tests the handling of a non-existent model in the admin documentation views.

        This test simulates a GET request to the model detail view with an argument of a model that does not exist in the 'admin_docs' app. It checks that the response has a 404 status code, which is the standard HTTP status code for \"Not Found\" requests, and that the 'exception' variable in the response context contains the expected error message indicating that the model was not found.
        """
        response = self.client.get(
            reverse(
                "django-admindocs-models-detail", args=["admin_docs", "doesnotexist"]
            )
        )
        self.assertEqual(
            response.context["exception"],
            "Model 'doesnotexist' not found in app 'admin_docs'",
        )
        self.assertEqual(response.status_code, 404)


class CustomField(models.Field):
    description = "A custom field type"


class DescriptionLackingField(models.Field):
    pass


class TestFieldType(unittest.TestCase):
    def test_field_name(self):
        """
        Tests that retrieving a field's readable data type raises an AttributeError when the field does not exist.

        This test case ensures that the function :func:`views.get_readable_field_data_type` handles non-existent fields correctly by throwing an AttributeError exception, providing a clear indication of the error for further handling or debugging purposes.
        """
        with self.assertRaises(AttributeError):
            views.get_readable_field_data_type("NotAField")

    def test_builtin_fields(self):
        self.assertEqual(
            views.get_readable_field_data_type(fields.BooleanField()),
            "Boolean (Either True or False)",
        )

    def test_char_fields(self):
        """
        Tests the conversion of CharacterField data types to human-readable formats.

        This test case checks that the get_readable_field_data_type function correctly
        handles CharacterField instances with and without a specified max_length, returning
        'String (up to <max_length>)' and 'String (unlimited)' respectively.
        """
        self.assertEqual(
            views.get_readable_field_data_type(fields.CharField(max_length=255)),
            "String (up to 255)",
        )
        self.assertEqual(
            views.get_readable_field_data_type(fields.CharField()),
            "String (unlimited)",
        )

    def test_custom_fields(self):
        """

        Tests the functionality of getting human-readable data types for custom fields.

        This test case checks that the :func:`~views.get_readable_field_data_type` function returns the correct data type 
        for custom fields. It verifies that fields with a description return a custom type string and fields without a 
        description return a string indicating the field type. 

        :raises AssertionError: If the returned data type does not match the expected value.

        """
        self.assertEqual(
            views.get_readable_field_data_type(CustomField()), "A custom field type"
        )
        self.assertEqual(
            views.get_readable_field_data_type(DescriptionLackingField()),
            "Field of type: DescriptionLackingField",
        )


class AdminDocViewFunctionsTests(SimpleTestCase):
    def test_simplify_regex(self):
        """
        Tests the :func:`simplify_regex` function with a variety of regular expression patterns.

        This test function verifies that the :func:`simplify_regex` function correctly simplifies
        regular expressions by replacing named groups with angle brackets around their names and
        non-named groups with angle brackets around a variable name. The test cases cover a range
        of regular expression features, including named and non-named groups, character classes,
        anchors, and quantifiers.

        The test function uses a series of test cases to verify the correct behavior of the
        :func:`simplify_regex` function, including cases with trailing slashes, capturing and
        non-capturing groups, and special characters.

        Each test case checks that the simplified regular expression matches the expected output.

        """
        tests = (
            # Named and unnamed groups.
            (r"^(?P<a>\w+)/b/(?P<c>\w+)/$", "/<a>/b/<c>/"),
            (r"^(?P<a>\w+)/b/(?P<c>\w+)$", "/<a>/b/<c>"),
            (r"^(?P<a>\w+)/b/(?P<c>\w+)", "/<a>/b/<c>"),
            (r"^(?P<a>\w+)/b/(\w+)$", "/<a>/b/<var>"),
            (r"^(?P<a>\w+)/b/(\w+)", "/<a>/b/<var>"),
            (r"^(?P<a>\w+)/b/((x|y)\w+)$", "/<a>/b/<var>"),
            (r"^(?P<a>\w+)/b/((x|y)\w+)", "/<a>/b/<var>"),
            (r"^(?P<a>(x|y))/b/(?P<c>\w+)$", "/<a>/b/<c>"),
            (r"^(?P<a>(x|y))/b/(?P<c>\w+)", "/<a>/b/<c>"),
            (r"^(?P<a>(x|y))/b/(?P<c>\w+)ab", "/<a>/b/<c>ab"),
            (r"^(?P<a>(x|y)(\(|\)))/b/(?P<c>\w+)ab", "/<a>/b/<c>ab"),
            # Non-capturing groups.
            (r"^a(?:\w+)b", "/ab"),
            (r"^a(?:(x|y))", "/a"),
            (r"^(?:\w+(?:\w+))a", "/a"),
            (r"^a(?:\w+)/b(?:\w+)", "/a/b"),
            (r"(?P<a>\w+)/b/(?:\w+)c(?:\w+)", "/<a>/b/c"),
            (r"(?P<a>\w+)/b/(\w+)/(?:\w+)c(?:\w+)", "/<a>/b/<var>/c"),
            # Single and repeated metacharacters.
            (r"^a", "/a"),
            (r"^^a", "/a"),
            (r"^^^a", "/a"),
            (r"a$", "/a"),
            (r"a$$", "/a"),
            (r"a$$$", "/a"),
            (r"a?", "/a"),
            (r"a??", "/a"),
            (r"a???", "/a"),
            (r"a*", "/a"),
            (r"a**", "/a"),
            (r"a***", "/a"),
            (r"a+", "/a"),
            (r"a++", "/a"),
            (r"a+++", "/a"),
            (r"\Aa", "/a"),
            (r"\A\Aa", "/a"),
            (r"\A\A\Aa", "/a"),
            (r"a\Z", "/a"),
            (r"a\Z\Z", "/a"),
            (r"a\Z\Z\Z", "/a"),
            (r"\ba", "/a"),
            (r"\b\ba", "/a"),
            (r"\b\b\ba", "/a"),
            (r"a\B", "/a"),
            (r"a\B\B", "/a"),
            (r"a\B\B\B", "/a"),
            # Multiple mixed metacharacters.
            (r"^a/?$", "/a/"),
            (r"\Aa\Z", "/a"),
            (r"\ba\B", "/a"),
            # Escaped single metacharacters.
            (r"\^a", r"/^a"),
            (r"\\^a", r"/\\a"),
            (r"\\\^a", r"/\\^a"),
            (r"\\\\^a", r"/\\\\a"),
            (r"\\\\\^a", r"/\\\\^a"),
            (r"a\$", r"/a$"),
            (r"a\\$", r"/a\\"),
            (r"a\\\$", r"/a\\$"),
            (r"a\\\\$", r"/a\\\\"),
            (r"a\\\\\$", r"/a\\\\$"),
            (r"a\?", r"/a?"),
            (r"a\\?", r"/a\\"),
            (r"a\\\?", r"/a\\?"),
            (r"a\\\\?", r"/a\\\\"),
            (r"a\\\\\?", r"/a\\\\?"),
            (r"a\*", r"/a*"),
            (r"a\\*", r"/a\\"),
            (r"a\\\*", r"/a\\*"),
            (r"a\\\\*", r"/a\\\\"),
            (r"a\\\\\*", r"/a\\\\*"),
            (r"a\+", r"/a+"),
            (r"a\\+", r"/a\\"),
            (r"a\\\+", r"/a\\+"),
            (r"a\\\\+", r"/a\\\\"),
            (r"a\\\\\+", r"/a\\\\+"),
            (r"\\Aa", r"/\Aa"),
            (r"\\\Aa", r"/\\a"),
            (r"\\\\Aa", r"/\\\Aa"),
            (r"\\\\\Aa", r"/\\\\a"),
            (r"\\\\\\Aa", r"/\\\\\Aa"),
            (r"a\\Z", r"/a\Z"),
            (r"a\\\Z", r"/a\\"),
            (r"a\\\\Z", r"/a\\\Z"),
            (r"a\\\\\Z", r"/a\\\\"),
            (r"a\\\\\\Z", r"/a\\\\\Z"),
            # Escaped mixed metacharacters.
            (r"^a\?$", r"/a?"),
            (r"^a\\?$", r"/a\\"),
            (r"^a\\\?$", r"/a\\?"),
            (r"^a\\\\?$", r"/a\\\\"),
            (r"^a\\\\\?$", r"/a\\\\?"),
            # Adjacent escaped metacharacters.
            (r"^a\?\$", r"/a?$"),
            (r"^a\\?\\$", r"/a\\\\"),
            (r"^a\\\?\\\$", r"/a\\?\\$"),
            (r"^a\\\\?\\\\$", r"/a\\\\\\\\"),
            (r"^a\\\\\?\\\\\$", r"/a\\\\?\\\\$"),
            # Complex examples with metacharacters and (un)named groups.
            (r"^\b(?P<slug>\w+)\B/(\w+)?", "/<slug>/<var>"),
            (r"^\A(?P<slug>\w+)\Z", "/<slug>"),
        )
        for pattern, output in tests:
            with self.subTest(pattern=pattern):
                self.assertEqual(simplify_regex(pattern), output)
