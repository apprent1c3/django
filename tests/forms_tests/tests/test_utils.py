import copy
import json

from django.core.exceptions import ValidationError
from django.forms.utils import (
    ErrorDict,
    ErrorList,
    RenderableFieldMixin,
    RenderableMixin,
    flatatt,
    pretty_name,
)
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy


class FormsUtilsTestCase(SimpleTestCase):
    # Tests for forms/utils.py module.

    def test_flatatt(self):
        ###########
        # flatatt #
        ###########

        self.assertEqual(flatatt({"id": "header"}), ' id="header"')
        self.assertEqual(
            flatatt({"class": "news", "title": "Read this"}),
            ' class="news" title="Read this"',
        )
        self.assertEqual(
            flatatt({"class": "news", "title": "Read this", "required": "required"}),
            ' class="news" required="required" title="Read this"',
        )
        self.assertEqual(
            flatatt({"class": "news", "title": "Read this", "required": True}),
            ' class="news" title="Read this" required',
        )
        self.assertEqual(
            flatatt({"class": "news", "title": "Read this", "required": False}),
            ' class="news" title="Read this"',
        )
        self.assertEqual(flatatt({"class": None}), "")
        self.assertEqual(flatatt({}), "")

    def test_flatatt_no_side_effects(self):
        """
        flatatt() does not modify the dict passed in.
        """
        attrs = {"foo": "bar", "true": True, "false": False}
        attrs_copy = copy.copy(attrs)
        self.assertEqual(attrs, attrs_copy)

        first_run = flatatt(attrs)
        self.assertEqual(attrs, attrs_copy)
        self.assertEqual(first_run, ' foo="bar" true')

        second_run = flatatt(attrs)
        self.assertEqual(attrs, attrs_copy)

        self.assertEqual(first_run, second_run)

    def test_validation_error(self):
        ###################
        # ValidationError #
        ###################

        # Can take a string.
        self.assertHTMLEqual(
            str(ErrorList(ValidationError("There was an error.").messages)),
            '<ul class="errorlist"><li>There was an error.</li></ul>',
        )
        # Can take a Unicode string.
        self.assertHTMLEqual(
            str(ErrorList(ValidationError("Not \u03C0.").messages)),
            '<ul class="errorlist"><li>Not π.</li></ul>',
        )
        # Can take a lazy string.
        self.assertHTMLEqual(
            str(ErrorList(ValidationError(gettext_lazy("Error.")).messages)),
            '<ul class="errorlist"><li>Error.</li></ul>',
        )
        # Can take a list.
        self.assertHTMLEqual(
            str(ErrorList(ValidationError(["Error one.", "Error two."]).messages)),
            '<ul class="errorlist"><li>Error one.</li><li>Error two.</li></ul>',
        )
        # Can take a dict.
        self.assertHTMLEqual(
            str(
                ErrorList(
                    sorted(
                        ValidationError(
                            {"error_1": "1. Error one.", "error_2": "2. Error two."}
                        ).messages
                    )
                )
            ),
            '<ul class="errorlist"><li>1. Error one.</li><li>2. Error two.</li></ul>',
        )
        # Can take a mixture in a list.
        self.assertHTMLEqual(
            str(
                ErrorList(
                    sorted(
                        ValidationError(
                            [
                                "1. First error.",
                                "2. Not \u03C0.",
                                gettext_lazy("3. Error."),
                                {
                                    "error_1": "4. First dict error.",
                                    "error_2": "5. Second dict error.",
                                },
                            ]
                        ).messages
                    )
                )
            ),
            '<ul class="errorlist">'
            "<li>1. First error.</li>"
            "<li>2. Not π.</li>"
            "<li>3. Error.</li>"
            "<li>4. First dict error.</li>"
            "<li>5. Second dict error.</li>"
            "</ul>",
        )

        class VeryBadError:
            def __str__(self):
                return "A very bad error."

        # Can take a non-string.
        self.assertHTMLEqual(
            str(ErrorList(ValidationError(VeryBadError()).messages)),
            '<ul class="errorlist"><li>A very bad error.</li></ul>',
        )

        # Escapes non-safe input but not input marked safe.
        example = 'Example of link: <a href="http://www.example.com/">example</a>'
        self.assertHTMLEqual(
            str(ErrorList([example])),
            '<ul class="errorlist"><li>Example of link: '
            "&lt;a href=&quot;http://www.example.com/&quot;&gt;example&lt;/a&gt;"
            "</li></ul>",
        )
        self.assertHTMLEqual(
            str(ErrorList([mark_safe(example)])),
            '<ul class="errorlist"><li>Example of link: '
            '<a href="http://www.example.com/">example</a></li></ul>',
        )
        self.assertHTMLEqual(
            str(ErrorDict({"name": example})),
            '<ul class="errorlist"><li>nameExample of link: '
            "&lt;a href=&quot;http://www.example.com/&quot;&gt;example&lt;/a&gt;"
            "</li></ul>",
        )
        self.assertHTMLEqual(
            str(ErrorDict({"name": mark_safe(example)})),
            '<ul class="errorlist"><li>nameExample of link: '
            '<a href="http://www.example.com/">example</a></li></ul>',
        )

    def test_error_dict_copy(self):
        """

        Tests the correctness of copying ErrorDict instances.

        Verifies that both shallow and deep copies of an ErrorDict object produce
        equivalent instances, comparing their contents and data representations.
        Ensures that the copying process preserves the original object's structure
        and attributes, including ErrorList instances and associated validation errors.

        """
        e = ErrorDict()
        e["__all__"] = ErrorList(
            [
                ValidationError(
                    message="message %(i)s",
                    params={"i": 1},
                ),
                ValidationError(
                    message="message %(i)s",
                    params={"i": 2},
                ),
            ]
        )

        e_copy = copy.copy(e)
        self.assertEqual(e, e_copy)
        self.assertEqual(e.as_data(), e_copy.as_data())

        e_deepcopy = copy.deepcopy(e)
        self.assertEqual(e, e_deepcopy)

    def test_error_dict_html_safe(self):
        """

        Tests that an ErrorDict instance generates HTML-safe output when converted to a string.

        This test case verifies that the ErrorDict class has an __html__ method and that its
        string representation matches the HTML output. The test creates an instance of ErrorDict,
        adds an error message, and checks the following conditions:
        - The ErrorDict class has an __html__ attribute.
        - The string representation of the ErrorDict instance is equivalent to its HTML representation.

        The purpose of this test is to ensure that the ErrorDict class correctly handles HTML
        output, preventing potential security vulnerabilities such as cross-site scripting (XSS).

        """
        e = ErrorDict()
        e["username"] = "Invalid username."
        self.assertTrue(hasattr(ErrorDict, "__html__"))
        self.assertEqual(str(e), e.__html__())

    def test_error_list_html_safe(self):
        """

        Verifies that ErrorList instances are HTML-safe.

        This test checks that the ErrorList class has a __html__ method, 
        indicating it can be safely used in HTML templates without risking XSS attacks.
        It also ensures that the string representation of an ErrorList instance 
        matches its HTML representation, as returned by the __html__ method.

        """
        e = ErrorList(["Invalid username."])
        self.assertTrue(hasattr(ErrorList, "__html__"))
        self.assertEqual(str(e), e.__html__())

    def test_error_dict_is_dict(self):
        self.assertIsInstance(ErrorDict(), dict)

    def test_error_dict_is_json_serializable(self):
        """
        Tests whether an ErrorDict object can be successfully serialized into JSON.

        The ErrorDict object is a container for validation errors, which may be nested within each other to represent complex error structures. This test case verifies that the ErrorDict object can be converted into a JSON-compatible format, regardless of the complexity or depth of its error tree.
        """
        init_errors = ErrorDict(
            [
                (
                    "__all__",
                    ErrorList(
                        [ValidationError("Sorry this form only works on leap days.")]
                    ),
                ),
                ("name", ErrorList([ValidationError("This field is required.")])),
            ]
        )
        min_value_error_list = ErrorList(
            [ValidationError("Ensure this value is greater than or equal to 0.")]
        )
        e = ErrorDict(
            init_errors,
            date=ErrorList(
                [
                    ErrorDict(
                        {
                            "day": min_value_error_list,
                            "month": min_value_error_list,
                            "year": min_value_error_list,
                        }
                    ),
                ]
            ),
        )
        e["renderer"] = ErrorList(
            [
                ValidationError(
                    "Select a valid choice. That choice is not one of the "
                    "available choices."
                ),
            ]
        )
        self.assertJSONEqual(
            json.dumps(e),
            {
                "__all__": ["Sorry this form only works on leap days."],
                "name": ["This field is required."],
                "date": [
                    {
                        "day": ["Ensure this value is greater than or equal to 0."],
                        "month": ["Ensure this value is greater than or equal to 0."],
                        "year": ["Ensure this value is greater than or equal to 0."],
                    },
                ],
                "renderer": [
                    "Select a valid choice. That choice is not one of the "
                    "available choices."
                ],
            },
        )

    def test_get_context_must_be_implemented(self):
        """
        Tests that subclasses of RenderableMixin must implement the get_context method.

        Verifies that calling get_context on a base RenderableMixin instance raises a
        NotImplementedError with a message indicating that subclasses are responsible
        for providing their own implementation of this method.
        """
        mixin = RenderableMixin()
        msg = "Subclasses of RenderableMixin must provide a get_context() method."
        with self.assertRaisesMessage(NotImplementedError, msg):
            mixin.get_context()

    def test_field_mixin_as_hidden_must_be_implemented(self):
        """
        ..: Tests that the RenderableFieldMixin correctly raises a NotImplementedError when its as_hidden method is not implemented by a subclass.

            This test case checks that the mixin enforces the implementation of as_hidden in any subclass, 
            ensuring that all renderable fields provide a way to be represented as a hidden field.

            Raises:
                NotImplementedError: if as_hidden is not implemented by a subclass of RenderableFieldMixin.
        """
        mixin = RenderableFieldMixin()
        msg = "Subclasses of RenderableFieldMixin must provide an as_hidden() method."
        with self.assertRaisesMessage(NotImplementedError, msg):
            mixin.as_hidden()

    def test_field_mixin_as_widget_must_be_implemented(self):
        """
        Tests that RenderableFieldMixin subclasses must implement the as_widget method.

        This test case ensures that any subclass of RenderableFieldMixin provides a valid 
        implementation for the as_widget method, which is necessary for rendering the 
        field as a widget. If the method is not implemented, it raises a NotImplementedError 
        with a corresponding error message.
        """
        mixin = RenderableFieldMixin()
        msg = "Subclasses of RenderableFieldMixin must provide an as_widget() method."
        with self.assertRaisesMessage(NotImplementedError, msg):
            mixin.as_widget()

    def test_pretty_name(self):
        self.assertEqual(pretty_name("john_doe"), "John doe")
        self.assertEqual(pretty_name(None), "")
        self.assertEqual(pretty_name(""), "")
