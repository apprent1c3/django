import copy
import datetime
import json
import uuid

from django.core.exceptions import NON_FIELD_ERRORS
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import MaxValueValidator, RegexValidator
from django.forms import (
    BooleanField,
    CharField,
    CheckboxSelectMultiple,
    ChoiceField,
    DateField,
    DateTimeField,
    EmailField,
    Field,
    FileField,
    FileInput,
    FloatField,
    Form,
    HiddenInput,
    ImageField,
    IntegerField,
    MultipleChoiceField,
    MultipleHiddenInput,
    MultiValueField,
    MultiWidget,
    NullBooleanField,
    PasswordInput,
    RadioSelect,
    Select,
    SplitDateTimeField,
    SplitHiddenDateTimeWidget,
    Textarea,
    TextInput,
    TimeField,
    ValidationError,
)
from django.forms.renderers import DjangoTemplates, get_default_renderer
from django.forms.utils import ErrorDict, ErrorList
from django.http import QueryDict
from django.template import Context, Template
from django.test import SimpleTestCase
from django.test.utils import override_settings
from django.utils.datastructures import MultiValueDict
from django.utils.safestring import mark_safe

from . import jinja2_tests


class FrameworkForm(Form):
    name = CharField()
    language = ChoiceField(choices=[("P", "Python"), ("J", "Java")], widget=RadioSelect)


class Person(Form):
    first_name = CharField()
    last_name = CharField()
    birthday = DateField()


class PersonNew(Form):
    first_name = CharField(widget=TextInput(attrs={"id": "first_name_id"}))
    last_name = CharField()
    birthday = DateField()


class SongForm(Form):
    name = CharField()
    composers = MultipleChoiceField(
        choices=[("J", "John Lennon"), ("P", "Paul McCartney")],
        widget=CheckboxSelectMultiple,
    )


class MultiValueDictLike(dict):
    def getlist(self, key):
        return [self[key]]


class FormsTestCase(SimpleTestCase):
    # A Form is a collection of Fields. It knows how to validate a set of data and it
    # knows how to render itself in a couple of default ways (e.g., an HTML table).
    # You can pass it data in __init__(), as a dictionary.

    def test_form(self):
        # Pass a dictionary to a Form's __init__().
        """
        Tests the Person form to ensure it is correctly bound and validated.

        Checks that the form is bound and valid with no errors, and that the cleaned data matches the input data.
        Verifies that the form fields are correctly rendered as HTML inputs and that their values are correctly displayed.
        Tests that accessing a non-existent field raises a KeyError with the expected error message.
        Checks that iterating over the form fields produces the expected HTML output and field data.
        Tests the as_div and __str__ methods to ensure they produce the expected HTML output.

        Ensures that the form's label and data are correctly extracted for each field.
        Verifies that the form's HTML representation matches the expected output, including labels and input fields.
        """
        p = Person(
            {"first_name": "John", "last_name": "Lennon", "birthday": "1940-10-9"}
        )

        self.assertTrue(p.is_bound)
        self.assertEqual(p.errors, {})
        self.assertIsInstance(p.errors, dict)
        self.assertTrue(p.is_valid())
        self.assertHTMLEqual(p.errors.as_ul(), "")
        self.assertEqual(p.errors.as_text(), "")
        self.assertEqual(p.cleaned_data["first_name"], "John")
        self.assertEqual(p.cleaned_data["last_name"], "Lennon")
        self.assertEqual(p.cleaned_data["birthday"], datetime.date(1940, 10, 9))
        self.assertHTMLEqual(
            str(p["first_name"]),
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            "required>",
        )
        self.assertHTMLEqual(
            str(p["last_name"]),
            '<input type="text" name="last_name" value="Lennon" id="id_last_name" '
            "required>",
        )
        self.assertHTMLEqual(
            str(p["birthday"]),
            '<input type="text" name="birthday" value="1940-10-9" id="id_birthday" '
            "required>",
        )

        msg = (
            "Key 'nonexistentfield' not found in 'Person'. Choices are: birthday, "
            "first_name, last_name."
        )
        with self.assertRaisesMessage(KeyError, msg):
            p["nonexistentfield"]

        form_output = []

        for boundfield in p:
            form_output.append(str(boundfield))

        self.assertHTMLEqual(
            "\n".join(form_output),
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            "required>"
            '<input type="text" name="last_name" value="Lennon" id="id_last_name" '
            "required>"
            '<input type="text" name="birthday" value="1940-10-9" id="id_birthday" '
            "required>",
        )

        form_output = []

        for boundfield in p:
            form_output.append([boundfield.label, boundfield.data])

        self.assertEqual(
            form_output,
            [
                ["First name", "John"],
                ["Last name", "Lennon"],
                ["Birthday", "1940-10-9"],
            ],
        )
        self.assertHTMLEqual(
            str(p),
            '<div><label for="id_first_name">First name:</label><input type="text" '
            'name="first_name" value="John" required id="id_first_name"></div><div>'
            '<label for="id_last_name">Last name:</label><input type="text" '
            'name="last_name" value="Lennon" required id="id_last_name"></div><div>'
            '<label for="id_birthday">Birthday:</label><input type="text" '
            'name="birthday" value="1940-10-9" required id="id_birthday"></div>',
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_first_name">First name:</label><input type="text" '
            'name="first_name" value="John" required id="id_first_name"></div><div>'
            '<label for="id_last_name">Last name:</label><input type="text" '
            'name="last_name" value="Lennon" required id="id_last_name"></div><div>'
            '<label for="id_birthday">Birthday:</label><input type="text" '
            'name="birthday" value="1940-10-9" required id="id_birthday"></div>',
        )

    def test_empty_dict(self):
        # Empty dictionaries are valid, too.
        p = Person({})
        self.assertTrue(p.is_bound)
        self.assertEqual(p.errors["first_name"], ["This field is required."])
        self.assertEqual(p.errors["last_name"], ["This field is required."])
        self.assertEqual(p.errors["birthday"], ["This field is required."])
        self.assertFalse(p.is_valid())
        self.assertEqual(p.cleaned_data, {})
        self.assertHTMLEqual(
            str(p),
            '<div><label for="id_first_name">First name:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="first_name" aria-invalid="true" required '
            'id="id_first_name"></div>'
            '<div><label for="id_last_name">Last name:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="last_name" aria-invalid="true" required '
            'id="id_last_name"></div><div>'
            '<label for="id_birthday">Birthday:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="birthday" aria-invalid="true" required '
            'id="id_birthday"></div>',
        )
        self.assertHTMLEqual(
            p.as_table(),
            """<tr><th><label for="id_first_name">First name:</label></th><td>
<ul class="errorlist"><li>This field is required.</li></ul>
<input type="text" name="first_name" id="id_first_name" aria-invalid="true" required>
</td></tr><tr><th><label for="id_last_name">Last name:</label></th>
<td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="text" name="last_name" id="id_last_name" aria-invalid="true" required>
</td></tr><tr><th><label for="id_birthday">Birthday:</label></th>
<td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="text" name="birthday" id="id_birthday" aria-invalid="true" required>
</td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
<label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" aria-invalid="true" required>
</li><li><ul class="errorlist"><li>This field is required.</li></ul>
<label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" aria-invalid="true" required>
</li><li><ul class="errorlist"><li>This field is required.</li></ul>
<label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" aria-invalid="true" required>
</li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<ul class="errorlist"><li>This field is required.</li></ul>
<p><label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" aria-invalid="true" required>
</p><ul class="errorlist"><li>This field is required.</li></ul>
<p><label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" aria-invalid="true" required>
</p><ul class="errorlist"><li>This field is required.</li></ul>
<p><label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" aria-invalid="true" required>
</p>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_first_name">First name:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="first_name" aria-invalid="true" required '
            'id="id_first_name"></div>'
            '<div><label for="id_last_name">Last name:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="last_name" aria-invalid="true" required '
            'id="id_last_name"></div><div>'
            '<label for="id_birthday">Birthday:</label>'
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="birthday" aria-invalid="true" required '
            'id="id_birthday"></div>',
        )

    def test_empty_querydict_args(self):
        """
        Tests that a Person instance correctly stores and retrieves empty QueryDict objects when no data or files are provided as arguments.
        """
        data = QueryDict()
        files = QueryDict()
        p = Person(data, files)
        self.assertIs(p.data, data)
        self.assertIs(p.files, files)

    def test_unbound_form(self):
        # If you don't pass any values to the Form's __init__(), or if you pass None,
        # the Form will be considered unbound and won't do any validation. Form.errors
        # will be an empty dictionary *but* Form.is_valid() will return False.
        """
        Tests an unbound form instance, ensuring it has the expected properties and methods. 

        Specifically, this test checks that the form is initially invalid, contains no errors, and does not have cleaned data. 
        It also verifies that the form can be correctly rendered as HTML in various formats, including string representation, table, unordered list, paragraph, and div, to ensure that the form fields are displayed as expected. 

        The test covers various scenarios to ensure that the form behaves correctly when no data has been bound to it, providing a solid foundation for further testing and validation.
        """
        p = Person()
        self.assertFalse(p.is_bound)
        self.assertEqual(p.errors, {})
        self.assertFalse(p.is_valid())
        with self.assertRaises(AttributeError):
            p.cleaned_data

        self.assertHTMLEqual(
            str(p),
            '<div><label for="id_first_name">First name:</label><input type="text" '
            'name="first_name" id="id_first_name" required></div><div><label '
            'for="id_last_name">Last name:</label><input type="text" name="last_name" '
            'id="id_last_name" required></div><div><label for="id_birthday">'
            'Birthday:</label><input type="text" name="birthday" id="id_birthday" '
            "required></div>",
        )
        self.assertHTMLEqual(
            p.as_table(),
            """<tr><th><label for="id_first_name">First name:</label></th><td>
<input type="text" name="first_name" id="id_first_name" required></td></tr>
<tr><th><label for="id_last_name">Last name:</label></th><td>
<input type="text" name="last_name" id="id_last_name" required></td></tr>
<tr><th><label for="id_birthday">Birthday:</label></th><td>
<input type="text" name="birthday" id="id_birthday" required></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" required></li>
<li><label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" required></li>
<li><label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" required></li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<p><label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" required></p>
<p><label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" required></p>
<p><label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" required></p>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_first_name">First name:</label><input type="text" '
            'name="first_name" id="id_first_name" required></div><div><label '
            'for="id_last_name">Last name:</label><input type="text" name="last_name" '
            'id="id_last_name" required></div><div><label for="id_birthday">'
            'Birthday:</label><input type="text" name="birthday" id="id_birthday" '
            "required></div>",
        )

    def test_unicode_values(self):
        # Unicode values are handled properly.
        """
        Tests the functionality of the Person class with unicode values.

        Ensures that the class can handle special characters in first and last names.
        Verifies that required fields are properly validated and error messages are
        handled correctly. Also tests the rendering of form fields with different
        types of HTML structures (table, unordered list, paragraph, div).

        Checks that cleaned data is properly extracted and that field-specific errors
        are correctly reported. Additionally, tests the string representation of
        fields and their corresponding error messages.
        """
        p = Person(
            {
                "first_name": "John",
                "last_name": "\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111",
                "birthday": "1940-10-9",
            }
        )
        self.assertHTMLEqual(
            p.as_table(),
            '<tr><th><label for="id_first_name">First name:</label></th><td>'
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            "required></td></tr>\n"
            '<tr><th><label for="id_last_name">Last name:</label>'
            '</th><td><input type="text" name="last_name" '
            'value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111"'
            'id="id_last_name" required></td></tr>\n'
            '<tr><th><label for="id_birthday">Birthday:</label></th><td>'
            '<input type="text" name="birthday" value="1940-10-9" id="id_birthday" '
            "required></td></tr>",
        )
        self.assertHTMLEqual(
            p.as_ul(),
            '<li><label for="id_first_name">First name:</label> '
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            "required></li>\n"
            '<li><label for="id_last_name">Last name:</label> '
            '<input type="text" name="last_name" '
            'value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111" '
            'id="id_last_name" required></li>\n'
            '<li><label for="id_birthday">Birthday:</label> '
            '<input type="text" name="birthday" value="1940-10-9" id="id_birthday" '
            "required></li>",
        )
        self.assertHTMLEqual(
            p.as_p(),
            '<p><label for="id_first_name">First name:</label> '
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            "required></p>\n"
            '<p><label for="id_last_name">Last name:</label> '
            '<input type="text" name="last_name" '
            'value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111" '
            'id="id_last_name" required></p>\n'
            '<p><label for="id_birthday">Birthday:</label> '
            '<input type="text" name="birthday" value="1940-10-9" id="id_birthday" '
            "required></p>",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_first_name">First name:</label>'
            '<input type="text" name="first_name" value="John" id="id_first_name" '
            'required></div><div><label for="id_last_name">Last name:</label>'
            '<input type="text" name="last_name"'
            'value="\u0160\u0110\u0106\u017d\u0107\u017e\u0161\u0111" '
            'id="id_last_name" required></div><div><label for="id_birthday">'
            'Birthday:</label><input type="text" name="birthday" value="1940-10-9" '
            'id="id_birthday" required></div>',
        )

        p = Person({"last_name": "Lennon"})
        self.assertEqual(p.errors["first_name"], ["This field is required."])
        self.assertEqual(p.errors["birthday"], ["This field is required."])
        self.assertFalse(p.is_valid())
        self.assertEqual(
            p.errors,
            {
                "birthday": ["This field is required."],
                "first_name": ["This field is required."],
            },
        )
        self.assertEqual(p.cleaned_data, {"last_name": "Lennon"})
        self.assertEqual(p["first_name"].errors, ["This field is required."])
        self.assertHTMLEqual(
            p["first_name"].errors.as_ul(),
            '<ul class="errorlist"><li>This field is required.</li></ul>',
        )
        self.assertEqual(p["first_name"].errors.as_text(), "* This field is required.")

        p = Person()
        self.assertHTMLEqual(
            str(p["first_name"]),
            '<input type="text" name="first_name" id="id_first_name" required>',
        )
        self.assertHTMLEqual(
            str(p["last_name"]),
            '<input type="text" name="last_name" id="id_last_name" required>',
        )
        self.assertHTMLEqual(
            str(p["birthday"]),
            '<input type="text" name="birthday" id="id_birthday" required>',
        )

    def test_cleaned_data_only_fields(self):
        # cleaned_data will always *only* contain a key for fields defined in the
        # Form, even if you pass extra data when you define the Form. In this
        # example, we pass a bunch of extra fields to the form constructor,
        # but cleaned_data contains only the form's fields.
        """

        Tests if the Person class correctly cleans and validates input data, only including the required fields.

        This test case ensures that the cleaned_data attribute of the Person instance contains the expected first name, last name, 
        and birthday, and that any extra fields are properly excluded. The test also verifies that the is_valid method returns 
        True to indicate successful validation.

        """
        data = {
            "first_name": "John",
            "last_name": "Lennon",
            "birthday": "1940-10-9",
            "extra1": "hello",
            "extra2": "hello",
        }
        p = Person(data)
        self.assertTrue(p.is_valid())
        self.assertEqual(p.cleaned_data["first_name"], "John")
        self.assertEqual(p.cleaned_data["last_name"], "Lennon")
        self.assertEqual(p.cleaned_data["birthday"], datetime.date(1940, 10, 9))

    def test_optional_data(self):
        # cleaned_data will include a key and value for *all* fields defined in
        # the Form, even if the Form's data didn't include a value for fields
        # that are not required. In this example, the data dictionary doesn't
        # include a value for the "nick_name" field, but cleaned_data includes
        # it. For CharFields, it's set to the empty string.
        """

        Tests the functionality of optional form fields in the Django Form class.

        The test covers two scenarios: 
        1. A form with a CharField that is not required (i.e., `nick_name`).
        2. A form with a DateField that is not required (i.e., `birth_date`).

        Verifies that the form is valid even when the optional fields are not provided.
        Checks that the cleaned data for the optional fields behaves as expected, 
        i.e., it is an empty string for CharField and None for DateField when not provided.

        """
        class OptionalPersonForm(Form):
            first_name = CharField()
            last_name = CharField()
            nick_name = CharField(required=False)

        data = {"first_name": "John", "last_name": "Lennon"}
        f = OptionalPersonForm(data)
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data["nick_name"], "")
        self.assertEqual(f.cleaned_data["first_name"], "John")
        self.assertEqual(f.cleaned_data["last_name"], "Lennon")

        # For DateFields, it's set to None.
        class OptionalPersonForm(Form):
            first_name = CharField()
            last_name = CharField()
            birth_date = DateField(required=False)

        data = {"first_name": "John", "last_name": "Lennon"}
        f = OptionalPersonForm(data)
        self.assertTrue(f.is_valid())
        self.assertIsNone(f.cleaned_data["birth_date"])
        self.assertEqual(f.cleaned_data["first_name"], "John")
        self.assertEqual(f.cleaned_data["last_name"], "Lennon")

    def test_auto_id(self):
        # "auto_id" tells the Form to add an "id" attribute to each form
        # element. If it's a string that contains '%s', Django will use that as
        # a format string into which the field's name will be inserted. It will
        # also put a <label> around the human-readable labels for a field.
        p = Person(auto_id="%s_id")
        self.assertHTMLEqual(
            p.as_table(),
            """<tr><th><label for="first_name_id">First name:</label></th><td>
<input type="text" name="first_name" id="first_name_id" required></td></tr>
<tr><th><label for="last_name_id">Last name:</label></th><td>
<input type="text" name="last_name" id="last_name_id" required></td></tr>
<tr><th><label for="birthday_id">Birthday:</label></th><td>
<input type="text" name="birthday" id="birthday_id" required></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="first_name_id">First name:</label>
<input type="text" name="first_name" id="first_name_id" required></li>
<li><label for="last_name_id">Last name:</label>
<input type="text" name="last_name" id="last_name_id" required></li>
<li><label for="birthday_id">Birthday:</label>
<input type="text" name="birthday" id="birthday_id" required></li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<p><label for="first_name_id">First name:</label>
<input type="text" name="first_name" id="first_name_id" required></p>
<p><label for="last_name_id">Last name:</label>
<input type="text" name="last_name" id="last_name_id" required></p>
<p><label for="birthday_id">Birthday:</label>
<input type="text" name="birthday" id="birthday_id" required></p>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="first_name_id">First name:</label><input type="text" '
            'name="first_name" id="first_name_id" required></div><div><label '
            'for="last_name_id">Last name:</label><input type="text" '
            'name="last_name" id="last_name_id" required></div><div><label '
            'for="birthday_id">Birthday:</label><input type="text" name="birthday" '
            'id="birthday_id" required></div>',
        )

    def test_auto_id_true(self):
        # If auto_id is any True value whose str() does not contain '%s', the "id"
        # attribute will be the name of the field.
        """
        Checks that the Person object generates correct HTML list representation 
        when 'auto_id' is enabled. This includes the creation of HTML labels 
        and input fields for 'first_name', 'last_name', and 'birthday' fields, 
        each with an 'id' and 'name' attribute, and that each input field is 
        marked as 'required'.
        """
        p = Person(auto_id=True)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="first_name">First name:</label>
<input type="text" name="first_name" id="first_name" required></li>
<li><label for="last_name">Last name:</label>
<input type="text" name="last_name" id="last_name" required></li>
<li><label for="birthday">Birthday:</label>
<input type="text" name="birthday" id="birthday" required></li>""",
        )

    def test_auto_id_false(self):
        # If auto_id is any False value, an "id" attribute won't be output unless it
        # was manually entered.
        """
        Tests the rendering of a Person object as an unordered list when auto-id is disabled.

        The function verifies that the Person object is correctly displayed as a list of input fields for first name, last name, and birthday, without any HTML id attributes being automatically generated.
        """
        p = Person(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li>First name: <input type="text" name="first_name" required></li>
<li>Last name: <input type="text" name="last_name" required></li>
<li>Birthday: <input type="text" name="birthday" required></li>""",
        )

    def test_id_on_field(self):
        # In this example, auto_id is False, but the "id" attribute for the "first_name"
        # field is given. Also note that field gets a <label>, while the others don't.
        """
        Tests that the id attribute is not automatically added to form fields when auto_id is set to False.

        Verifies that the generated HTML output for a PersonNew form does not include an id attribute on fields when auto_id is disabled, with the exception of the first field which retains its id for accessibility purposes.

        The test checks for the correct HTML structure, including label and input tags, and ensures that the required attributes are present on the input fields. The resulting HTML output is verified to match the expected format, with id attributes only present where expected.
        """
        p = PersonNew(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="first_name_id">First name:</label>
<input type="text" id="first_name_id" name="first_name" required></li>
<li>Last name: <input type="text" name="last_name" required></li>
<li>Birthday: <input type="text" name="birthday" required></li>""",
        )

    def test_auto_id_on_form_and_field(self):
        # If the "id" attribute is specified in the Form and auto_id is True, the "id"
        # attribute in the Form gets precedence.
        """

        Tests automatic id generation for form and field elements.

        This test case verifies that when auto_id is enabled, the function correctly
        generates and assigns unique ids to form fields. It checks the resulting HTML
        output to ensure that each field has a properly formatted id attribute, and
        that these ids are correctly referenced in their corresponding label tags.

        The test covers the scenario where auto_id is set to True, and checks the
        generated HTML against an expected output to confirm correct functionality.

        """
        p = PersonNew(auto_id=True)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="first_name_id">First name:</label>
<input type="text" id="first_name_id" name="first_name" required></li>
<li><label for="last_name">Last name:</label>
<input type="text" name="last_name" id="last_name" required></li>
<li><label for="birthday">Birthday:</label>
<input type="text" name="birthday" id="birthday" required></li>""",
        )

    def test_various_boolean_values(self):
        class SignupForm(Form):
            email = EmailField()
            get_spam = BooleanField()

        f = SignupForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["email"]),
            '<input type="email" name="email" maxlength="320" required>',
        )
        self.assertHTMLEqual(
            str(f["get_spam"]), '<input type="checkbox" name="get_spam" required>'
        )

        f = SignupForm({"email": "test@example.com", "get_spam": True}, auto_id=False)
        self.assertHTMLEqual(
            str(f["email"]),
            '<input type="email" name="email" maxlength="320" value="test@example.com" '
            "required>",
        )
        self.assertHTMLEqual(
            str(f["get_spam"]),
            '<input checked type="checkbox" name="get_spam" required>',
        )

        # 'True' or 'true' should be rendered without a value attribute
        f = SignupForm({"email": "test@example.com", "get_spam": "True"}, auto_id=False)
        self.assertHTMLEqual(
            str(f["get_spam"]),
            '<input checked type="checkbox" name="get_spam" required>',
        )

        f = SignupForm({"email": "test@example.com", "get_spam": "true"}, auto_id=False)
        self.assertHTMLEqual(
            str(f["get_spam"]),
            '<input checked type="checkbox" name="get_spam" required>',
        )

        # A value of 'False' or 'false' should be rendered unchecked
        f = SignupForm(
            {"email": "test@example.com", "get_spam": "False"}, auto_id=False
        )
        self.assertHTMLEqual(
            str(f["get_spam"]),
            '<input type="checkbox" name="get_spam" aria-invalid="true" required>',
        )

        f = SignupForm(
            {"email": "test@example.com", "get_spam": "false"}, auto_id=False
        )
        self.assertHTMLEqual(
            str(f["get_spam"]),
            '<input type="checkbox" name="get_spam" aria-invalid="true" required>',
        )

        # A value of '0' should be interpreted as a True value (#16820)
        f = SignupForm({"email": "test@example.com", "get_spam": "0"})
        self.assertTrue(f.is_valid())
        self.assertTrue(f.cleaned_data.get("get_spam"))

    def test_widget_output(self):
        # Any Field can have a Widget class passed to its constructor:
        """
        Tests the output of a form widget, specifically a CharField with and without a Textarea widget, 
        ensuring that the HTML representation is correct and matches expected results.
        This includes testing the default widget, as well as a customized Textarea widget with specific rows and columns.
        It also covers rendering of the widget with and without bound data, 
        including rendering as different types of fields (e.g., textarea, text, hidden) and verifying the output against expected HTML strings.
        """
        class ContactForm(Form):
            subject = CharField()
            message = CharField(widget=Textarea)

        f = ContactForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["subject"]), '<input type="text" name="subject" required>'
        )
        self.assertHTMLEqual(
            str(f["message"]),
            '<textarea name="message" rows="10" cols="40" required></textarea>',
        )

        # as_textarea(), as_text() and as_hidden() are shortcuts for changing the output
        # widget type:
        self.assertHTMLEqual(
            f["subject"].as_textarea(),
            '<textarea name="subject" rows="10" cols="40" required></textarea>',
        )
        self.assertHTMLEqual(
            f["message"].as_text(), '<input type="text" name="message" required>'
        )
        self.assertHTMLEqual(
            f["message"].as_hidden(), '<input type="hidden" name="message">'
        )

        # The 'widget' parameter to a Field can also be an instance:
        class ContactForm(Form):
            subject = CharField()
            message = CharField(widget=Textarea(attrs={"rows": 80, "cols": 20}))

        f = ContactForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["message"]),
            '<textarea name="message" rows="80" cols="20" required></textarea>',
        )

        # Instance-level attrs are *not* carried over to as_textarea(), as_text() and
        # as_hidden():
        self.assertHTMLEqual(
            f["message"].as_text(), '<input type="text" name="message" required>'
        )
        f = ContactForm({"subject": "Hello", "message": "I love you."}, auto_id=False)
        self.assertHTMLEqual(
            f["subject"].as_textarea(),
            '<textarea rows="10" cols="40" name="subject" required>Hello</textarea>',
        )
        self.assertHTMLEqual(
            f["message"].as_text(),
            '<input type="text" name="message" value="I love you." required>',
        )
        self.assertHTMLEqual(
            f["message"].as_hidden(),
            '<input type="hidden" name="message" value="I love you.">',
        )

    def test_forms_with_choices(self):
        # For a form with a <select>, use ChoiceField:
        """
        Tests the rendering of Django form fields, specifically ChoiceField, with various configurations.

        This test case covers the following scenarios:

        - ChoiceField with a list of choices
        - ChoiceField with a list of choices and a selected value
        - ChoiceField with an empty choice (e.g., a blank option)
        - ChoiceField with custom HTML attributes (e.g., CSS class)
        - ChoiceField with custom widget and choices
        - ChoiceField without any choices specified, demonstrating dynamic assignment of choices.

        It verifies that the resulting HTML select elements are correctly rendered according to the provided choices and configurations.
        """
        class FrameworkForm(Form):
            name = CharField()
            language = ChoiceField(choices=[("P", "Python"), ("J", "Java")])

        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select name="language">
<option value="P">Python</option>
<option value="J">Java</option>
</select>""",
        )
        f = FrameworkForm({"name": "Django", "language": "P"}, auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select name="language">
<option value="P" selected>Python</option>
<option value="J">Java</option>
</select>""",
        )

        # A subtlety: If one of the choices' value is the empty string and the form is
        # unbound, then the <option> for the empty-string choice will get selected.
        class FrameworkForm(Form):
            name = CharField()
            language = ChoiceField(
                choices=[("", "------"), ("P", "Python"), ("J", "Java")]
            )

        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select name="language" required>
<option value="" selected>------</option>
<option value="P">Python</option>
<option value="J">Java</option>
</select>""",
        )

        # You can specify widget attributes in the Widget constructor.
        class FrameworkForm(Form):
            name = CharField()
            language = ChoiceField(
                choices=[("P", "Python"), ("J", "Java")],
                widget=Select(attrs={"class": "foo"}),
            )

        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select class="foo" name="language">
<option value="P">Python</option>
<option value="J">Java</option>
</select>""",
        )
        f = FrameworkForm({"name": "Django", "language": "P"}, auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select class="foo" name="language">
<option value="P" selected>Python</option>
<option value="J">Java</option>
</select>""",
        )

        # When passing a custom widget instance to ChoiceField, note that setting
        # 'choices' on the widget is meaningless. The widget will use the choices
        # defined on the Field, not the ones defined on the Widget.
        class FrameworkForm(Form):
            name = CharField()
            language = ChoiceField(
                choices=[("P", "Python"), ("J", "Java")],
                widget=Select(
                    choices=[("R", "Ruby"), ("P", "Perl")], attrs={"class": "foo"}
                ),
            )

        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select class="foo" name="language">
<option value="P">Python</option>
<option value="J">Java</option>
</select>""",
        )
        f = FrameworkForm({"name": "Django", "language": "P"}, auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select class="foo" name="language">
<option value="P" selected>Python</option>
<option value="J">Java</option>
</select>""",
        )

        # You can set a ChoiceField's choices after the fact.
        class FrameworkForm(Form):
            name = CharField()
            language = ChoiceField()

        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<select name="language">
</select>""",
        )
        f.fields["language"].choices = [("P", "Python"), ("J", "Java")]
        self.assertHTMLEqual(
            str(f["language"]),
            """<select name="language">
<option value="P">Python</option>
<option value="J">Java</option>
</select>""",
        )

    def test_forms_with_radio(self):
        # Add widget=RadioSelect to use that widget with a ChoiceField.
        """
        Tests the rendering of forms with radio buttons using the FrameworkForm class.

         The function creates a FrameworkForm instance with and without auto_id, and checks the rendered HTML of the form's fields in various formats, including as a table, unordered list, paragraphs, and using a custom template.

         It verifies that the form's fields, including text input and radio buttons, are correctly rendered with and without auto-generated ids.

         The test checks for the correct structure and attributes of the HTML elements, including input names, values, labels, and ids. 

         Please note that it is highly implementation-specific and should be maintained or modified with care as any changes to the FrameworkForm class or its rendering functionality may break this test.
        """
        f = FrameworkForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["language"]),
            """<div>
<div><label><input type="radio" name="language" value="P" required> Python</label></div>
<div><label><input type="radio" name="language" value="J" required> Java</label></div>
</div>""",
        )
        self.assertHTMLEqual(
            f.as_table(),
            """<tr><th>Name:</th><td><input type="text" name="name" required></td></tr>
<tr><th>Language:</th><td><div>
<div><label><input type="radio" name="language" value="P" required> Python</label></div>
<div><label><input type="radio" name="language" value="J" required> Java</label></div>
</div></td></tr>""",
        )
        self.assertHTMLEqual(
            f.as_ul(),
            """<li>Name: <input type="text" name="name" required></li>
<li>Language: <div>
<div><label><input type="radio" name="language" value="P" required> Python</label></div>
<div><label><input type="radio" name="language" value="J" required> Java</label></div>
</div></li>""",
        )
        # Need an auto_id to generate legend.
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<div> Name: <input type="text" name="name" required></div><div><fieldset>'
            'Language:<div><div><label><input type="radio" name="language" value="P" '
            'required> Python</label></div><div><label><input type="radio" '
            'name="language" value="J" required> Java</label></div></div></fieldset>'
            "</div>",
        )

        # Regarding auto_id and <label>, RadioSelect is a special case. Each
        # radio button gets a distinct ID, formed by appending an underscore
        # plus the button's zero-based index.
        f = FrameworkForm(auto_id="id_%s")
        self.assertHTMLEqual(
            str(f["language"]),
            """
            <div id="id_language">
            <div><label for="id_language_0">
            <input type="radio" id="id_language_0" value="P" name="language" required>
            Python</label></div>
            <div><label for="id_language_1">
            <input type="radio" id="id_language_1" value="J" name="language" required>
            Java</label></div>
            </div>""",
        )

        # When RadioSelect is used with auto_id, and the whole form is printed
        # using either as_table() or as_ul(), the label for the RadioSelect
        # will **not** point to the ID of the *first* radio button to improve
        # accessibility for screen reader users.
        self.assertHTMLEqual(
            f.as_table(),
            """
            <tr><th><label for="id_name">Name:</label></th><td>
            <input type="text" name="name" id="id_name" required></td></tr>
            <tr><th><label>Language:</label></th><td><div id="id_language">
            <div><label for="id_language_0">
            <input type="radio" id="id_language_0" value="P" name="language" required>
            Python</label></div>
            <div><label for="id_language_1">
            <input type="radio" id="id_language_1" value="J" name="language" required>
            Java</label></div>
            </div></td></tr>""",
        )
        self.assertHTMLEqual(
            f.as_ul(),
            """
            <li><label for="id_name">Name:</label>
            <input type="text" name="name" id="id_name" required></li>
            <li><label>Language:</label> <div id="id_language">
            <div><label for="id_language_0">
            <input type="radio" id="id_language_0" value="P" name="language" required>
            Python</label></div>
            <div><label for="id_language_1">
            <input type="radio" id="id_language_1" value="J" name="language" required>
            Java</label></div>
            </div></li>
            """,
        )
        self.assertHTMLEqual(
            f.as_p(),
            """
            <p><label for="id_name">Name:</label>
            <input type="text" name="name" id="id_name" required></p>
            <p><label>Language:</label> <div id="id_language">
            <div><label for="id_language_0">
            <input type="radio" id="id_language_0" value="P" name="language" required>
            Python</label></div>
            <div><label for="id_language_1">
            <input type="radio" id="id_language_1" value="J" name="language" required>
            Java</label></div>
            </div></p>
            """,
        )
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<div><label for="id_name">Name:</label><input type="text" name="name" '
            'required id="id_name"></div><div><fieldset><legend>Language:</legend>'
            '<div id="id_language"><div><label for="id_language_0"><input '
            'type="radio" name="language" value="P" required id="id_language_0">'
            'Python</label></div><div><label for="id_language_1"><input type="radio" '
            'name="language" value="J" required id="id_language_1">Java</label></div>'
            "</div></fieldset></div>",
        )

    def test_form_with_iterable_boundfield(self):
        class BeatleForm(Form):
            name = ChoiceField(
                choices=[
                    ("john", "John"),
                    ("paul", "Paul"),
                    ("george", "George"),
                    ("ringo", "Ringo"),
                ],
                widget=RadioSelect,
            )

        f = BeatleForm(auto_id=False)
        self.assertHTMLEqual(
            "\n".join(str(bf) for bf in f["name"]),
            '<label><input type="radio" name="name" value="john" required> John</label>'
            '<label><input type="radio" name="name" value="paul" required> Paul</label>'
            '<label><input type="radio" name="name" value="george" required> George'
            "</label>"
            '<label><input type="radio" name="name" value="ringo" required> Ringo'
            "</label>",
        )
        self.assertHTMLEqual(
            "\n".join("<div>%s</div>" % bf for bf in f["name"]),
            """
            <div><label>
            <input type="radio" name="name" value="john" required> John</label></div>
            <div><label>
            <input type="radio" name="name" value="paul" required> Paul</label></div>
            <div><label>
            <input type="radio" name="name" value="george" required> George
            </label></div>
            <div><label>
            <input type="radio" name="name" value="ringo" required> Ringo</label></div>
            """,
        )

    def test_form_with_iterable_boundfield_id(self):
        """
        Tests a form with an iterable BoundField id.

        This test case verifies that a form using a ChoiceField with a RadioSelect widget 
        correctly generates an iterable BoundField with the expected id, choice label, and HTML output.

        It checks the length of the fields, the id for each label, the choice label, 
        and the HTML output of the radio input and its corresponding label for each option.

        The test ensures that the form's field ids are properly generated and that the HTML output 
        matches the expected structure and content.
        """
        class BeatleForm(Form):
            name = ChoiceField(
                choices=[
                    ("john", "John"),
                    ("paul", "Paul"),
                    ("george", "George"),
                    ("ringo", "Ringo"),
                ],
                widget=RadioSelect,
            )

        fields = list(BeatleForm()["name"])
        self.assertEqual(len(fields), 4)

        self.assertEqual(fields[0].id_for_label, "id_name_0")
        self.assertEqual(fields[0].choice_label, "John")
        self.assertHTMLEqual(
            fields[0].tag(),
            '<input type="radio" name="name" value="john" id="id_name_0" required>',
        )
        self.assertHTMLEqual(
            str(fields[0]),
            '<label for="id_name_0"><input type="radio" name="name" '
            'value="john" id="id_name_0" required> John</label>',
        )

        self.assertEqual(fields[1].id_for_label, "id_name_1")
        self.assertEqual(fields[1].choice_label, "Paul")
        self.assertHTMLEqual(
            fields[1].tag(),
            '<input type="radio" name="name" value="paul" id="id_name_1" required>',
        )
        self.assertHTMLEqual(
            str(fields[1]),
            '<label for="id_name_1"><input type="radio" name="name" '
            'value="paul" id="id_name_1" required> Paul</label>',
        )

    def test_iterable_boundfield_select(self):
        """
        Tests the rendering of a ChoiceField in a Django form as an iterable BoundField, 
        verifying the correct output of HTML option tags and their corresponding labels. 
        This test case checks the number of choices, the id for the label, the choice label, 
        and the HTML representation of each option tag in the ChoiceField. 
        It ensures that the ChoiceField is properly rendered as a select element with options.
        """
        class BeatleForm(Form):
            name = ChoiceField(
                choices=[
                    ("john", "John"),
                    ("paul", "Paul"),
                    ("george", "George"),
                    ("ringo", "Ringo"),
                ]
            )

        fields = list(BeatleForm(auto_id=False)["name"])
        self.assertEqual(len(fields), 4)

        self.assertIsNone(fields[0].id_for_label)
        self.assertEqual(fields[0].choice_label, "John")
        self.assertHTMLEqual(fields[0].tag(), '<option value="john">John</option>')
        self.assertHTMLEqual(str(fields[0]), '<option value="john">John</option>')

    def test_form_with_noniterable_boundfield(self):
        # You can iterate over any BoundField, not just those with widget=RadioSelect.
        class BeatleForm(Form):
            name = CharField()

        f = BeatleForm(auto_id=False)
        self.assertHTMLEqual(
            "\n".join(str(bf) for bf in f["name"]),
            '<input type="text" name="name" required>',
        )

    def test_boundfield_slice(self):
        class BeatleForm(Form):
            name = ChoiceField(
                choices=[
                    ("john", "John"),
                    ("paul", "Paul"),
                    ("george", "George"),
                    ("ringo", "Ringo"),
                ],
                widget=RadioSelect,
            )

        f = BeatleForm()
        bf = f["name"]
        self.assertEqual(
            [str(item) for item in bf[1:]],
            [str(bf[1]), str(bf[2]), str(bf[3])],
        )

    def test_boundfield_invalid_index(self):
        """
        ```\"\"\"Tests that attempting to access a BoundField with a non-integer or non-slice index raises a TypeError.

        The test creates a form with a ChoiceField and then attempts to access the field using a string index, which should result in a TypeError being raised with a specific error message.

        :raises: TypeError
        :raises: AssertionError if the TypeError is not raised with the expected error message\"\"\"```
        """
        class TestForm(Form):
            name = ChoiceField(choices=[])

        field = TestForm()["name"]
        msg = "BoundField indices must be integers or slices, not str."
        with self.assertRaisesMessage(TypeError, msg):
            field["foo"]

    def test_boundfield_bool(self):
        """BoundField without any choices (subwidgets) evaluates to True."""

        class TestForm(Form):
            name = ChoiceField(choices=[])

        self.assertIs(bool(TestForm()["name"]), True)

    def test_forms_with_multiple_choice(self):
        # MultipleChoiceField is a special case, as its data is required to be a list:
        """
        Tests the rendering of Django form fields, specifically MultipleChoiceField, within a Form.

        The test covers various scenarios, including rendering multiple choice fields with and without choices, 
        rendering fields within a form with bound and unbound data, and testing different form rendering methods 
        (such as as_table, as_ul, as_p, and render). The expected HTML output is verified in each case.
        """
        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField()

        f = SongForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["composers"]),
            """<select multiple name="composers" required>
</select>""",
        )

        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")]
            )

        f = SongForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["composers"]),
            """<select multiple name="composers" required>
<option value="J">John Lennon</option>
<option value="P">Paul McCartney</option>
</select>""",
        )
        f = SongForm({"name": "Yesterday", "composers": ["P"]}, auto_id=False)
        self.assertHTMLEqual(
            str(f["name"]), '<input type="text" name="name" value="Yesterday" required>'
        )
        self.assertHTMLEqual(
            str(f["composers"]),
            """<select multiple name="composers" required>
<option value="J">John Lennon</option>
<option value="P" selected>Paul McCartney</option>
</select>""",
        )
        f = SongForm()
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><th><label for="id_name">Name:</label></th>'
            '<td><input type="text" name="name" required id="id_name"></td>'
            '</tr><tr><th><label for="id_composers">Composers:</label></th>'
            '<td><select name="composers" required id="id_composers" multiple>'
            '<option value="J">John Lennon</option>'
            '<option value="P">Paul McCartney</option>'
            "</select></td></tr>",
        )
        self.assertHTMLEqual(
            f.as_ul(),
            '<li><label for="id_name">Name:</label>'
            '<input type="text" name="name" required id="id_name"></li>'
            '<li><label for="id_composers">Composers:</label>'
            '<select name="composers" required id="id_composers" multiple>'
            '<option value="J">John Lennon</option>'
            '<option value="P">Paul McCartney</option>'
            "</select></li>",
        )
        self.assertHTMLEqual(
            f.as_p(),
            '<p><label for="id_name">Name:</label>'
            '<input type="text" name="name" required id="id_name"></p>'
            '<p><label for="id_composers">Composers:</label>'
            '<select name="composers" required id="id_composers" multiple>'
            '<option value="J">John Lennon</option>'
            '<option value="P">Paul McCartney</option>'
            "</select></p>",
        )
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<div><label for="id_name">Name:</label><input type="text" name="name" '
            'required id="id_name"></div><div><label for="id_composers">Composers:'
            '</label><select name="composers" required id="id_composers" multiple>'
            '<option value="J">John Lennon</option><option value="P">Paul McCartney'
            "</option></select></div>",
        )

    def test_multiple_checkbox_render(self):
        """
        Tests the rendering of a form with multiple checkboxes.

        The test case covers different rendering formats, including table, unordered list, paragraph, and div layouts. It verifies that the form fields, including a text input for the song name and multiple checkboxes for composers, are correctly rendered in each format. The test ensures that the HTML output matches the expected structure and content, including field names, labels, and checkbox values.
        """
        f = SongForm()
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><th><label for="id_name">Name:</label></th><td>'
            '<input type="text" name="name" required id="id_name"></td></tr>'
            '<tr><th><label>Composers:</label></th><td><div id="id_composers">'
            '<div><label for="id_composers_0">'
            '<input type="checkbox" name="composers" value="J" '
            'id="id_composers_0">John Lennon</label></div>'
            '<div><label for="id_composers_1">'
            '<input type="checkbox" name="composers" value="P" '
            'id="id_composers_1">Paul McCartney</label></div>'
            "</div></td></tr>",
        )
        self.assertHTMLEqual(
            f.as_ul(),
            '<li><label for="id_name">Name:</label>'
            '<input type="text" name="name" required id="id_name"></li>'
            '<li><label>Composers:</label><div id="id_composers">'
            '<div><label for="id_composers_0">'
            '<input type="checkbox" name="composers" value="J" '
            'id="id_composers_0">John Lennon</label></div>'
            '<div><label for="id_composers_1">'
            '<input type="checkbox" name="composers" value="P" '
            'id="id_composers_1">Paul McCartney</label></div>'
            "</div></li>",
        )
        self.assertHTMLEqual(
            f.as_p(),
            '<p><label for="id_name">Name:</label>'
            '<input type="text" name="name" required id="id_name"></p>'
            '<p><label>Composers:</label><div id="id_composers">'
            '<div><label for="id_composers_0">'
            '<input type="checkbox" name="composers" value="J" '
            'id="id_composers_0">John Lennon</label></div>'
            '<div><label for="id_composers_1">'
            '<input type="checkbox" name="composers" value="P" '
            'id="id_composers_1">Paul McCartney</label></div>'
            "</div></p>",
        )
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<div><label for="id_name">Name:</label><input type="text" name="name" '
            'required id="id_name"></div><div><fieldset><legend>Composers:</legend>'
            '<div id="id_composers"><div><label for="id_composers_0"><input '
            'type="checkbox" name="composers" value="J" id="id_composers_0">'
            'John Lennon</label></div><div><label for="id_composers_1"><input '
            'type="checkbox" name="composers" value="P" id="id_composers_1">'
            "Paul McCartney</label></div></div></fieldset></div>",
        )

    def test_form_with_disabled_fields(self):
        """
        Tests the functionality of forms with disabled fields.

        Verifies that forms with disabled fields can still pass validation and 
        return the expected cleaned data, regardless of whether the field's 
        value is provided through the form's initial data or an initial parameter 
        in the field's definition. Also checks that the disabled field's value 
        remains unchanged when the form is submitted with data for that field.

        Ensures the correct behavior in various scenarios, including when 
        the form is submitted with valid data, when the form is submitted with 
        data that would normally change the disabled field's value, and when 
        the form is submitted without any data. The test cases cover forms 
        where the disabled field's initial value is set through the form's 
        initial data and where it is set through the field's initial parameter.
        """
        class PersonForm(Form):
            name = CharField()
            birthday = DateField(disabled=True)

        class PersonFormFieldInitial(Form):
            name = CharField()
            birthday = DateField(disabled=True, initial=datetime.date(1974, 8, 16))

        # Disabled fields are generally not transmitted by user agents.
        # The value from the form's initial data is used.
        f1 = PersonForm(
            {"name": "John Doe"}, initial={"birthday": datetime.date(1974, 8, 16)}
        )
        f2 = PersonFormFieldInitial({"name": "John Doe"})
        for form in (f1, f2):
            self.assertTrue(form.is_valid())
            self.assertEqual(
                form.cleaned_data,
                {"birthday": datetime.date(1974, 8, 16), "name": "John Doe"},
            )

        # Values provided in the form's data are ignored.
        data = {"name": "John Doe", "birthday": "1984-11-10"}
        f1 = PersonForm(data, initial={"birthday": datetime.date(1974, 8, 16)})
        f2 = PersonFormFieldInitial(data)
        for form in (f1, f2):
            self.assertTrue(form.is_valid())
            self.assertEqual(
                form.cleaned_data,
                {"birthday": datetime.date(1974, 8, 16), "name": "John Doe"},
            )

        # Initial data remains present on invalid forms.
        data = {}
        f1 = PersonForm(data, initial={"birthday": datetime.date(1974, 8, 16)})
        f2 = PersonFormFieldInitial(data)
        for form in (f1, f2):
            self.assertFalse(form.is_valid())
            self.assertEqual(form["birthday"].value(), datetime.date(1974, 8, 16))

    def test_hidden_data(self):
        """

        Tests how HTML form fields with hidden input type are rendered.

        This function examines how form fields, including MultipleChoiceField and SplitDateTimeField, 
        are rendered as hidden fields. It checks that the field values are correctly represented 
        in the resulting HTML and that fields with multiple values (such as MultipleChoiceField 
        with multiple selected options) are properly handled.

        The test covers cases where the form field is a single value (e.g., a CharField), 
        a multiple-choice field with a single selected option, and a multiple-choice field 
        with multiple selected options. Additionally, it verifies that fields with complex 
        structures, such as SplitDateTimeField, are correctly rendered as hidden fields.

        """
        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")]
            )

        # MultipleChoiceField rendered as_hidden() is a special case. Because it can
        # have multiple values, its as_hidden() renders multiple <input type="hidden">
        # tags.
        f = SongForm({"name": "Yesterday", "composers": ["P"]}, auto_id=False)
        self.assertHTMLEqual(
            f["composers"].as_hidden(),
            '<input type="hidden" name="composers" value="P">',
        )
        f = SongForm({"name": "From Me To You", "composers": ["P", "J"]}, auto_id=False)
        self.assertHTMLEqual(
            f["composers"].as_hidden(),
            """<input type="hidden" name="composers" value="P">
<input type="hidden" name="composers" value="J">""",
        )

        # DateTimeField rendered as_hidden() is special too
        class MessageForm(Form):
            when = SplitDateTimeField()

        f = MessageForm({"when_0": "1992-01-01", "when_1": "01:01"})
        self.assertTrue(f.is_valid())
        self.assertHTMLEqual(
            str(f["when"]),
            '<input type="text" name="when_0" value="1992-01-01" id="id_when_0" '
            "required>"
            '<input type="text" name="when_1" value="01:01" id="id_when_1" required>',
        )
        self.assertHTMLEqual(
            f["when"].as_hidden(),
            '<input type="hidden" name="when_0" value="1992-01-01" id="id_when_0">'
            '<input type="hidden" name="when_1" value="01:01" id="id_when_1">',
        )

    def test_multiple_choice_checkbox(self):
        # MultipleChoiceField can also be used with the CheckboxSelectMultiple widget.
        """

        Tests the rendering of a multiple choice checkbox field in the SongForm.

        This test case covers three scenarios:
        1. An empty form: Verifies that the checkboxes are rendered without any pre-selected options.
        2. A form with one pre-selected composer: Checks that the corresponding checkbox is rendered as selected.
        3. A form with multiple pre-selected composers: Ensures that all selected checkboxes are rendered as checked.

        The test asserts that the HTML output of the 'composers' field matches the expected structure and content in each scenario.

        """
        f = SongForm(auto_id=False)
        self.assertHTMLEqual(
            str(f["composers"]),
            """
            <div>
            <div><label><input type="checkbox" name="composers" value="J">
            John Lennon</label></div>
            <div><label><input type="checkbox" name="composers" value="P">
            Paul McCartney</label></div>
            </div>
            """,
        )
        f = SongForm({"composers": ["J"]}, auto_id=False)
        self.assertHTMLEqual(
            str(f["composers"]),
            """
            <div>
            <div><label><input checked type="checkbox" name="composers" value="J">
            John Lennon</label></div>
            <div><label><input type="checkbox" name="composers" value="P">
            Paul McCartney</label></div>
            </div>
            """,
        )
        f = SongForm({"composers": ["J", "P"]}, auto_id=False)
        self.assertHTMLEqual(
            str(f["composers"]),
            """
            <div>
            <div><label><input checked type="checkbox" name="composers" value="J">
            John Lennon</label></div>
            <div><label><input checked type="checkbox" name="composers" value="P">
            Paul McCartney</label></div>
            </div>
            """,
        )

    def test_checkbox_auto_id(self):
        # Regarding auto_id, CheckboxSelectMultiple is a special case. Each checkbox
        # gets a distinct ID, formed by appending an underscore plus the checkbox's
        # zero-based index.
        """
        Tests the automatic generation of HTML IDs for checkboxes in a Django form.

        Verifies that a MultipleChoiceField with a CheckboxSelectMultiple widget correctly
        generates unique IDs for each checkbox, following the format specified by the form's
        auto_id parameter. The generated HTML is compared to an expected output to ensure
        consistency and correctness.

        The test case uses a sample form containing a MultipleChoiceField with two checkbox
        options, and checks that the resulting HTML matches the expected structure and IDs.
        """
        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")],
                widget=CheckboxSelectMultiple,
            )

        f = SongForm(auto_id="%s_id")
        self.assertHTMLEqual(
            str(f["composers"]),
            """
            <div id="composers_id">
            <div><label for="composers_id_0">
            <input type="checkbox" name="composers" value="J" id="composers_id_0">
            John Lennon</label></div>
            <div><label for="composers_id_1">
            <input type="checkbox" name="composers" value="P" id="composers_id_1">
            Paul McCartney</label></div>
            </div>
            """,
        )

    def test_multiple_choice_list_data(self):
        # Data for a MultipleChoiceField should be a list. QueryDict and
        # MultiValueDict conveniently work with this.
        """

        Tests a MultipleChoiceField in a form with different types of data to ensure it correctly handles 
        the provided values and returns the expected choices without any errors.

        This function covers various data formats, including dictionaries, QueryDicts, and MultiValueDicts, 
        to verify that the form field can effectively process and validate the input data.

        """
        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")],
                widget=CheckboxSelectMultiple,
            )

        data = {"name": "Yesterday", "composers": ["J", "P"]}
        f = SongForm(data)
        self.assertEqual(f.errors, {})

        data = QueryDict("name=Yesterday&composers=J&composers=P")
        f = SongForm(data)
        self.assertEqual(f.errors, {})

        data = MultiValueDict({"name": ["Yesterday"], "composers": ["J", "P"]})
        f = SongForm(data)
        self.assertEqual(f.errors, {})

        # SelectMultiple uses ducktyping so that MultiValueDictLike.getlist()
        # is called.
        f = SongForm(MultiValueDictLike({"name": "Yesterday", "composers": "J"}))
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["composers"], ["J"])

    def test_multiple_hidden(self):
        class SongForm(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")],
                widget=CheckboxSelectMultiple,
            )

        # The MultipleHiddenInput widget renders multiple values as hidden fields.
        class SongFormHidden(Form):
            name = CharField()
            composers = MultipleChoiceField(
                choices=[("J", "John Lennon"), ("P", "Paul McCartney")],
                widget=MultipleHiddenInput,
            )

        f = SongFormHidden(
            MultiValueDict({"name": ["Yesterday"], "composers": ["J", "P"]}),
            auto_id=False,
        )
        self.assertHTMLEqual(
            f.as_ul(),
            """<li>Name: <input type="text" name="name" value="Yesterday" required>
<input type="hidden" name="composers" value="J">
<input type="hidden" name="composers" value="P"></li>""",
        )

        # When using CheckboxSelectMultiple, the framework expects a list of input and
        # returns a list of input.
        f = SongForm({"name": "Yesterday"}, auto_id=False)
        self.assertEqual(f.errors["composers"], ["This field is required."])
        f = SongForm({"name": "Yesterday", "composers": ["J"]}, auto_id=False)
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["composers"], ["J"])
        self.assertEqual(f.cleaned_data["name"], "Yesterday")
        f = SongForm({"name": "Yesterday", "composers": ["J", "P"]}, auto_id=False)
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["composers"], ["J", "P"])
        self.assertEqual(f.cleaned_data["name"], "Yesterday")

        # MultipleHiddenInput uses ducktyping so that
        # MultiValueDictLike.getlist() is called.
        f = SongForm(MultiValueDictLike({"name": "Yesterday", "composers": "J"}))
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["composers"], ["J"])

    def test_escaping(self):
        # Validation errors are HTML-escaped when output as HTML.
        class EscapingForm(Form):
            special_name = CharField(label="<em>Special</em> Field")
            special_safe_name = CharField(label=mark_safe("<em>Special</em> Field"))

            def clean_special_name(self):
                raise ValidationError(
                    "Something's wrong with '%s'" % self.cleaned_data["special_name"]
                )

            def clean_special_safe_name(self):
                raise ValidationError(
                    mark_safe(
                        "'<b>%s</b>' is a safe string"
                        % self.cleaned_data["special_safe_name"]
                    )
                )

        f = EscapingForm(
            {
                "special_name": "Nothing to escape",
                "special_safe_name": "Nothing to escape",
            },
            auto_id=False,
        )
        self.assertHTMLEqual(
            f.as_table(),
            """
            <tr><th>&lt;em&gt;Special&lt;/em&gt; Field:</th><td>
            <ul class="errorlist">
            <li>Something&#x27;s wrong with &#x27;Nothing to escape&#x27;</li></ul>
            <input type="text" name="special_name" value="Nothing to escape"
            aria-invalid="true" required></td></tr>
            <tr><th><em>Special</em> Field:</th><td>
            <ul class="errorlist">
            <li>'<b>Nothing to escape</b>' is a safe string</li></ul>
            <input type="text" name="special_safe_name" value="Nothing to escape"
            aria-invalid="true" required></td></tr>
            """,
        )
        f = EscapingForm(
            {
                "special_name": "Should escape < & > and <script>alert('xss')</script>",
                "special_safe_name": "<i>Do not escape</i>",
            },
            auto_id=False,
        )
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>&lt;em&gt;Special&lt;/em&gt; Field:</th><td>"
            '<ul class="errorlist"><li>'
            "Something&#x27;s wrong with &#x27;Should escape &lt; &amp; &gt; and "
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;&#x27;</li></ul>"
            '<input type="text" name="special_name" value="Should escape &lt; &amp; '
            '&gt; and &lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" '
            'aria-invalid="true" required></td></tr>'
            "<tr><th><em>Special</em> Field:</th><td>"
            '<ul class="errorlist">'
            "<li>'<b><i>Do not escape</i></b>' is a safe string</li></ul>"
            '<input type="text" name="special_safe_name" '
            'value="&lt;i&gt;Do not escape&lt;/i&gt;" aria-invalid="true" required>'
            "</td></tr>",
        )

    def test_validating_multiple_fields(self):
        # There are a couple of ways to do multiple-field validation. If you
        # want the validation message to be associated with a particular field,
        # implement the clean_XXX() method on the Form, where XXX is the field
        # name. As in Field.clean(), the clean_XXX() method should return the
        # cleaned value. In the clean_XXX() method, you have access to
        # self.cleaned_data, which is a dictionary of all the data that has
        # been cleaned *so far*, in order by the fields, including the current
        # field (e.g., the field XXX if you're in clean_XXX()).
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password1 = CharField(widget=PasswordInput)
            password2 = CharField(widget=PasswordInput)

            def clean_password2(self):
                if (
                    self.cleaned_data.get("password1")
                    and self.cleaned_data.get("password2")
                    and self.cleaned_data["password1"] != self.cleaned_data["password2"]
                ):
                    raise ValidationError("Please make sure your passwords match.")

                return self.cleaned_data["password2"]

        f = UserRegistration(auto_id=False)
        self.assertEqual(f.errors, {})
        f = UserRegistration({}, auto_id=False)
        self.assertEqual(f.errors["username"], ["This field is required."])
        self.assertEqual(f.errors["password1"], ["This field is required."])
        self.assertEqual(f.errors["password2"], ["This field is required."])
        f = UserRegistration(
            {"username": "adrian", "password1": "foo", "password2": "bar"},
            auto_id=False,
        )
        self.assertEqual(
            f.errors["password2"], ["Please make sure your passwords match."]
        )
        f = UserRegistration(
            {"username": "adrian", "password1": "foo", "password2": "foo"},
            auto_id=False,
        )
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["username"], "adrian")
        self.assertEqual(f.cleaned_data["password1"], "foo")
        self.assertEqual(f.cleaned_data["password2"], "foo")

        # Another way of doing multiple-field validation is by implementing the
        # Form's clean() method. Usually ValidationError raised by that method
        # will not be associated with a particular field and will have a
        # special-case association with the field named '__all__'. It's
        # possible to associate the errors to particular field with the
        # Form.add_error() method or by passing a dictionary that maps each
        # field to one or more errors.
        #
        # Note that in Form.clean(), you have access to self.cleaned_data, a
        # dictionary of all the fields/values that have *not* raised a
        # ValidationError. Also note Form.clean() is required to return a
        # dictionary of all clean data.
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password1 = CharField(widget=PasswordInput)
            password2 = CharField(widget=PasswordInput)

            def clean(self):
                # Test raising a ValidationError as NON_FIELD_ERRORS.
                """

                Validates and cleans the form data, ensuring password fields match and do not contain forbidden values.

                Raises a :class:`ValidationError` if the passwords do not match or if either password field contains a forbidden value.
                The validation checks for two types of forbidden values, with the first type raising a :class:`ValidationError` with field-specific errors,
                and the second type adding both field-specific and non-field errors to the form.

                Returns the cleaned form data if validation is successful.

                """
                if (
                    self.cleaned_data.get("password1")
                    and self.cleaned_data.get("password2")
                    and self.cleaned_data["password1"] != self.cleaned_data["password2"]
                ):
                    raise ValidationError("Please make sure your passwords match.")

                # Test raising ValidationError that targets multiple fields.
                errors = {}
                if self.cleaned_data.get("password1") == "FORBIDDEN_VALUE":
                    errors["password1"] = "Forbidden value."
                if self.cleaned_data.get("password2") == "FORBIDDEN_VALUE":
                    errors["password2"] = ["Forbidden value."]
                if errors:
                    raise ValidationError(errors)

                # Test Form.add_error()
                if self.cleaned_data.get("password1") == "FORBIDDEN_VALUE2":
                    self.add_error(None, "Non-field error 1.")
                    self.add_error("password1", "Forbidden value 2.")
                if self.cleaned_data.get("password2") == "FORBIDDEN_VALUE2":
                    self.add_error("password2", "Forbidden value 2.")
                    raise ValidationError("Non-field error 2.")

                return self.cleaned_data

        f = UserRegistration(auto_id=False)
        self.assertEqual(f.errors, {})

        f = UserRegistration({}, auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            """<tr><th>Username:</th><td>
<ul class="errorlist"><li>This field is required.</li></ul>
<input type="text" name="username" maxlength="10" aria-invalid="true" required>
</td></tr>
<tr><th>Password1:</th><td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="password" name="password1" aria-invalid="true" required></td></tr>
<tr><th>Password2:</th><td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="password" name="password2" aria-invalid="true" required></td></tr>""",
        )
        self.assertEqual(f.errors["username"], ["This field is required."])
        self.assertEqual(f.errors["password1"], ["This field is required."])
        self.assertEqual(f.errors["password2"], ["This field is required."])

        f = UserRegistration(
            {"username": "adrian", "password1": "foo", "password2": "bar"},
            auto_id=False,
        )
        self.assertEqual(
            f.errors["__all__"], ["Please make sure your passwords match."]
        )
        self.assertHTMLEqual(
            f.as_table(),
            """
            <tr><td colspan="2">
            <ul class="errorlist nonfield">
            <li>Please make sure your passwords match.</li></ul></td></tr>
            <tr><th>Username:</th><td>
            <input type="text" name="username" value="adrian" maxlength="10" required>
            </td></tr>
            <tr><th>Password1:</th><td>
            <input type="password" name="password1" required></td></tr>
            <tr><th>Password2:</th><td>
            <input type="password" name="password2" required></td></tr>
            """,
        )
        self.assertHTMLEqual(
            f.as_ul(),
            """
            <li><ul class="errorlist nonfield">
            <li>Please make sure your passwords match.</li></ul></li>
            <li>Username:
            <input type="text" name="username" value="adrian" maxlength="10" required>
            </li>
            <li>Password1: <input type="password" name="password1" required></li>
            <li>Password2: <input type="password" name="password2" required></li>
            """,
        )
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<ul class="errorlist nonfield"><li>Please make sure your passwords match.'
            '</li></ul><div>Username: <input type="text" name="username" '
            'value="adrian" maxlength="10" required></div><div>Password1: <input '
            'type="password" name="password1" required></div><div>Password2: <input '
            'type="password" name="password2" required></div>',
        )

        f = UserRegistration(
            {"username": "adrian", "password1": "foo", "password2": "foo"},
            auto_id=False,
        )
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["username"], "adrian")
        self.assertEqual(f.cleaned_data["password1"], "foo")
        self.assertEqual(f.cleaned_data["password2"], "foo")

        f = UserRegistration(
            {
                "username": "adrian",
                "password1": "FORBIDDEN_VALUE",
                "password2": "FORBIDDEN_VALUE",
            },
            auto_id=False,
        )
        self.assertEqual(f.errors["password1"], ["Forbidden value."])
        self.assertEqual(f.errors["password2"], ["Forbidden value."])

        f = UserRegistration(
            {
                "username": "adrian",
                "password1": "FORBIDDEN_VALUE2",
                "password2": "FORBIDDEN_VALUE2",
            },
            auto_id=False,
        )
        self.assertEqual(
            f.errors["__all__"], ["Non-field error 1.", "Non-field error 2."]
        )
        self.assertEqual(f.errors["password1"], ["Forbidden value 2."])
        self.assertEqual(f.errors["password2"], ["Forbidden value 2."])

        with self.assertRaisesMessage(ValueError, "has no field named"):
            f.add_error("missing_field", "Some error.")

    def test_update_error_dict(self):
        class CodeForm(Form):
            code = CharField(max_length=10)

            def clean(self):
                try:
                    raise ValidationError({"code": [ValidationError("Code error 1.")]})
                except ValidationError as e:
                    self._errors = e.update_error_dict(self._errors)

                try:
                    raise ValidationError({"code": [ValidationError("Code error 2.")]})
                except ValidationError as e:
                    self._errors = e.update_error_dict(self._errors)

                try:
                    raise ValidationError({"code": ErrorList(["Code error 3."])})
                except ValidationError as e:
                    self._errors = e.update_error_dict(self._errors)

                try:
                    raise ValidationError("Non-field error 1.")
                except ValidationError as e:
                    self._errors = e.update_error_dict(self._errors)

                try:
                    raise ValidationError([ValidationError("Non-field error 2.")])
                except ValidationError as e:
                    self._errors = e.update_error_dict(self._errors)

                # The newly added list of errors is an instance of ErrorList.
                for field, error_list in self._errors.items():
                    if not isinstance(error_list, self.error_class):
                        self._errors[field] = self.error_class(error_list)

        form = CodeForm({"code": "hello"})
        # Trigger validation.
        self.assertFalse(form.is_valid())

        # update_error_dict didn't lose track of the ErrorDict type.
        self.assertIsInstance(form._errors, ErrorDict)

        self.assertEqual(
            dict(form.errors),
            {
                "code": ["Code error 1.", "Code error 2.", "Code error 3."],
                NON_FIELD_ERRORS: ["Non-field error 1.", "Non-field error 2."],
            },
        )

    def test_has_error(self):
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password1 = CharField(widget=PasswordInput, min_length=5)
            password2 = CharField(widget=PasswordInput)

            def clean(self):
                if (
                    self.cleaned_data.get("password1")
                    and self.cleaned_data.get("password2")
                    and self.cleaned_data["password1"] != self.cleaned_data["password2"]
                ):
                    raise ValidationError(
                        "Please make sure your passwords match.",
                        code="password_mismatch",
                    )

        f = UserRegistration(data={})
        self.assertTrue(f.has_error("password1"))
        self.assertTrue(f.has_error("password1", "required"))
        self.assertFalse(f.has_error("password1", "anything"))

        f = UserRegistration(data={"password1": "Hi", "password2": "Hi"})
        self.assertTrue(f.has_error("password1"))
        self.assertTrue(f.has_error("password1", "min_length"))
        self.assertFalse(f.has_error("password1", "anything"))
        self.assertFalse(f.has_error("password2"))
        self.assertFalse(f.has_error("password2", "anything"))

        f = UserRegistration(data={"password1": "Bonjour", "password2": "Hello"})
        self.assertFalse(f.has_error("password1"))
        self.assertFalse(f.has_error("password1", "required"))
        self.assertTrue(f.has_error(NON_FIELD_ERRORS))
        self.assertTrue(f.has_error(NON_FIELD_ERRORS, "password_mismatch"))
        self.assertFalse(f.has_error(NON_FIELD_ERRORS, "anything"))

    def test_html_output_with_hidden_input_field_errors(self):
        """
        Tests the HTML output of a form with hidden input field errors.

        This test ensures that when a form contains a hidden input field with errors,
        the errors are displayed correctly when the form is rendered as HTML.
        The test checks that the errors are displayed in various formats, including
        a table, an unordered list, a paragraph, and a custom template.

        The test verifies that the errors are displayed with the correct messages,
        including a form-wide error and an error specific to the hidden input field.
        It also checks that the hidden input field itself is included in the rendered HTML.

        This test covers the following formats:
        - as_table()
        - as_ul()
        - as_p()
        - render() with a custom template
        """
        class TestForm(Form):
            hidden_input = CharField(widget=HiddenInput)

            def clean(self):
                self.add_error(None, "Form error")

        f = TestForm(data={})
        error_dict = {
            "hidden_input": ["This field is required."],
            "__all__": ["Form error"],
        }
        self.assertEqual(f.errors, error_dict)
        f.as_table()
        self.assertEqual(f.errors, error_dict)
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><td colspan="2"><ul class="errorlist nonfield"><li>Form error</li>'
            "<li>(Hidden field hidden_input) This field is required.</li></ul>"
            '<input type="hidden" name="hidden_input" id="id_hidden_input"></td></tr>',
        )
        self.assertHTMLEqual(
            f.as_ul(),
            '<li><ul class="errorlist nonfield"><li>Form error</li>'
            "<li>(Hidden field hidden_input) This field is required.</li></ul>"
            '<input type="hidden" name="hidden_input" id="id_hidden_input"></li>',
        )
        self.assertHTMLEqual(
            f.as_p(),
            '<ul class="errorlist nonfield"><li>Form error</li>'
            "<li>(Hidden field hidden_input) This field is required.</li></ul>"
            '<p><input type="hidden" name="hidden_input" id="id_hidden_input"></p>',
        )
        self.assertHTMLEqual(
            f.render(f.template_name_div),
            '<ul class="errorlist nonfield"><li>Form error</li>'
            "<li>(Hidden field hidden_input) This field is required.</li></ul>"
            '<div><input type="hidden" name="hidden_input" id="id_hidden_input"></div>',
        )

    def test_dynamic_construction(self):
        # It's possible to construct a Form dynamically by adding to the self.fields
        # dictionary in __init__(). Don't forget to call Form.__init__() within the
        # subclass' __init__().
        """
        Tests dynamic construction of Django forms.

        This method checks that forms can be dynamically constructed by adding fields,
        modifying existing fields, and changing field options such as required status,
        max length, and choices. It ensures that these changes are correctly reflected
        in the generated HTML form.

        The tests cover various scenarios, including:

        * Adding fields dynamically to a form
        * Modifying existing fields to make them required or change their max length
        * Adding new choices to a ChoiceField
        * Dynamic generation of forms with varying field configurations

        The goal of these tests is to verify that the form construction logic is working
        correctly and that the resulting HTML forms are as expected. This ensures that
        forms can be dynamically generated and customized based on different conditions
        or user input, while still producing valid and functional HTML forms.

        """
        class Person(Form):
            first_name = CharField()
            last_name = CharField()

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["birthday"] = DateField()

        p = Person(auto_id=False)
        self.assertHTMLEqual(
            p.as_table(),
            """
            <tr><th>First name:</th><td>
            <input type="text" name="first_name" required></td></tr>
            <tr><th>Last name:</th><td>
            <input type="text" name="last_name" required></td></tr>
            <tr><th>Birthday:</th><td>
            <input type="text" name="birthday" required></td></tr>
            """,
        )

        # Instances of a dynamic Form do not persist fields from one Form instance to
        # the next.
        class MyForm(Form):
            def __init__(self, data=None, auto_id=False, field_list=[]):
                """
                Initializes a form object.

                This constructor allows for customization of the form with initial data and a list of fields.
                The :param:`data` parameter can be used to populate the form with existing information.
                The :param:`auto_id` flag controls whether to automatically assign unique identifiers to the form's fields.
                The :param:`field_list` parameter is a list of tuples, where each tuple contains the name of a field and its corresponding value.
                These fields are then added to the form, making them available for further use.

                :param data: Optional data to initialize the form with
                :param auto_id: Flag to automatically assign unique identifiers to the form's fields
                :param field_list: List of tuples containing field names and their corresponding values
                """
                Form.__init__(self, data, auto_id=auto_id)

                for field in field_list:
                    self.fields[field[0]] = field[1]

        field_list = [("field1", CharField()), ("field2", CharField())]
        my_form = MyForm(field_list=field_list)
        self.assertHTMLEqual(
            my_form.as_table(),
            """
            <tr><th>Field1:</th><td><input type="text" name="field1" required></td></tr>
            <tr><th>Field2:</th><td><input type="text" name="field2" required></td></tr>
            """,
        )
        field_list = [("field3", CharField()), ("field4", CharField())]
        my_form = MyForm(field_list=field_list)
        self.assertHTMLEqual(
            my_form.as_table(),
            """
            <tr><th>Field3:</th><td><input type="text" name="field3" required></td></tr>
            <tr><th>Field4:</th><td><input type="text" name="field4" required></td></tr>
            """,
        )

        class MyForm(Form):
            default_field_1 = CharField()
            default_field_2 = CharField()

            def __init__(self, data=None, auto_id=False, field_list=[]):
                """

                Initializes a form object.

                :param data: Initial data for the form.
                :param auto_id: Flag to automatically generate IDs for the form.
                :param field_list: List of tuples containing field names and their corresponding values.

                """
                Form.__init__(self, data, auto_id=auto_id)

                for field in field_list:
                    self.fields[field[0]] = field[1]

        field_list = [("field1", CharField()), ("field2", CharField())]
        my_form = MyForm(field_list=field_list)
        self.assertHTMLEqual(
            my_form.as_table(),
            """
            <tr><th>Default field 1:</th><td>
            <input type="text" name="default_field_1" required></td></tr>
            <tr><th>Default field 2:</th><td>
            <input type="text" name="default_field_2" required></td></tr>
            <tr><th>Field1:</th><td><input type="text" name="field1" required></td></tr>
            <tr><th>Field2:</th><td><input type="text" name="field2" required></td></tr>
            """,
        )
        field_list = [("field3", CharField()), ("field4", CharField())]
        my_form = MyForm(field_list=field_list)
        self.assertHTMLEqual(
            my_form.as_table(),
            """
            <tr><th>Default field 1:</th><td>
            <input type="text" name="default_field_1" required></td></tr>
            <tr><th>Default field 2:</th><td>
            <input type="text" name="default_field_2" required></td></tr>
            <tr><th>Field3:</th><td><input type="text" name="field3" required></td></tr>
            <tr><th>Field4:</th><td><input type="text" name="field4" required></td></tr>
            """,
        )

        # Similarly, changes to field attributes do not persist from one Form instance
        # to the next.
        class Person(Form):
            first_name = CharField(required=False)
            last_name = CharField(required=False)

            def __init__(self, names_required=False, *args, **kwargs):
                super().__init__(*args, **kwargs)

                if names_required:
                    self.fields["first_name"].required = True
                    self.fields["first_name"].widget.attrs["class"] = "required"
                    self.fields["last_name"].required = True
                    self.fields["last_name"].widget.attrs["class"] = "required"

        f = Person(names_required=False)
        self.assertEqual(
            f["first_name"].field.required,
            f["last_name"].field.required,
            (False, False),
        )
        self.assertEqual(
            f["first_name"].field.widget.attrs,
            f["last_name"].field.widget.attrs,
            ({}, {}),
        )
        f = Person(names_required=True)
        self.assertEqual(
            f["first_name"].field.required, f["last_name"].field.required, (True, True)
        )
        self.assertEqual(
            f["first_name"].field.widget.attrs,
            f["last_name"].field.widget.attrs,
            ({"class": "reuired"}, {"class": "required"}),
        )
        f = Person(names_required=False)
        self.assertEqual(
            f["first_name"].field.required,
            f["last_name"].field.required,
            (False, False),
        )
        self.assertEqual(
            f["first_name"].field.widget.attrs,
            f["last_name"].field.widget.attrs,
            ({}, {}),
        )

        class Person(Form):
            first_name = CharField(max_length=30)
            last_name = CharField(max_length=30)

            def __init__(self, name_max_length=None, *args, **kwargs):
                super().__init__(*args, **kwargs)

                if name_max_length:
                    self.fields["first_name"].max_length = name_max_length
                    self.fields["last_name"].max_length = name_max_length

        f = Person(name_max_length=None)
        self.assertEqual(
            f["first_name"].field.max_length, f["last_name"].field.max_length, (30, 30)
        )
        f = Person(name_max_length=20)
        self.assertEqual(
            f["first_name"].field.max_length, f["last_name"].field.max_length, (20, 20)
        )
        f = Person(name_max_length=None)
        self.assertEqual(
            f["first_name"].field.max_length, f["last_name"].field.max_length, (30, 30)
        )

        # Similarly, choices do not persist from one Form instance to the next.
        # Refs #15127.
        class Person(Form):
            first_name = CharField(required=False)
            last_name = CharField(required=False)
            gender = ChoiceField(choices=(("f", "Female"), ("m", "Male")))

            def __init__(self, allow_unspec_gender=False, *args, **kwargs):
                """
                :param bool allow_unspec_gender: If set to True, allows the 'gender' field to have an 'Unspecified' option in addition to the existing choices.
                :note: This initializer extends the parent class's initializer with the additional functionality of customizing the 'gender' field.
                """
                super().__init__(*args, **kwargs)

                if allow_unspec_gender:
                    self.fields["gender"].choices += (("u", "Unspecified"),)

        f = Person()
        self.assertEqual(f["gender"].field.choices, [("f", "Female"), ("m", "Male")])
        f = Person(allow_unspec_gender=True)
        self.assertEqual(
            f["gender"].field.choices,
            [("f", "Female"), ("m", "Male"), ("u", "Unspecified")],
        )
        f = Person()
        self.assertEqual(f["gender"].field.choices, [("f", "Female"), ("m", "Male")])

    def test_validators_independence(self):
        """
        The list of form field validators can be modified without polluting
        other forms.
        """

        class MyForm(Form):
            myfield = CharField(max_length=25)

        f1 = MyForm()
        f2 = MyForm()

        f1.fields["myfield"].validators[0] = MaxValueValidator(12)
        self.assertNotEqual(
            f1.fields["myfield"].validators[0], f2.fields["myfield"].validators[0]
        )

    def test_hidden_widget(self):
        # HiddenInput widgets are displayed differently in the as_table(), as_ul())
        # and as_p() output of a Form -- their verbose names are not displayed, and a
        # separate row is not displayed. They're displayed in the last row of the
        # form, directly after that row's form element.
        class Person(Form):
            first_name = CharField()
            last_name = CharField()
            hidden_text = CharField(widget=HiddenInput)
            birthday = DateField()

        p = Person(auto_id=False)
        self.assertHTMLEqual(
            p.as_table(),
            """
            <tr><th>First name:</th><td><input type="text" name="first_name" required>
            </td></tr>
            <tr><th>Last name:</th><td><input type="text" name="last_name" required>
            </td></tr>
            <tr><th>Birthday:</th>
            <td><input type="text" name="birthday" required>
            <input type="hidden" name="hidden_text"></td></tr>
            """,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>First name: <input type="text" name="first_name" required></li>
            <li>Last name: <input type="text" name="last_name" required></li>
            <li>Birthday: <input type="text" name="birthday" required>
            <input type="hidden" name="hidden_text"></li>
            """,
        )
        self.assertHTMLEqual(
            p.as_p(),
            """
            <p>First name: <input type="text" name="first_name" required></p>
            <p>Last name: <input type="text" name="last_name" required></p>
            <p>Birthday: <input type="text" name="birthday" required>
            <input type="hidden" name="hidden_text"></p>
            """,
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div>First name: <input type="text" name="first_name" required></div>'
            '<div>Last name: <input type="text" name="last_name" required></div><div>'
            'Birthday: <input type="text" name="birthday" required><input '
            'type="hidden" name="hidden_text"></div>',
        )

        # With auto_id set, a HiddenInput still gets an ID, but it doesn't get a label.
        p = Person(auto_id="id_%s")
        self.assertHTMLEqual(
            p.as_table(),
            """<tr><th><label for="id_first_name">First name:</label></th><td>
<input type="text" name="first_name" id="id_first_name" required></td></tr>
<tr><th><label for="id_last_name">Last name:</label></th><td>
<input type="text" name="last_name" id="id_last_name" required></td></tr>
<tr><th><label for="id_birthday">Birthday:</label></th><td>
<input type="text" name="birthday" id="id_birthday" required>
<input type="hidden" name="hidden_text" id="id_hidden_text"></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" required></li>
<li><label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" required></li>
<li><label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" required>
<input type="hidden" name="hidden_text" id="id_hidden_text"></li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<p><label for="id_first_name">First name:</label>
<input type="text" name="first_name" id="id_first_name" required></p>
<p><label for="id_last_name">Last name:</label>
<input type="text" name="last_name" id="id_last_name" required></p>
<p><label for="id_birthday">Birthday:</label>
<input type="text" name="birthday" id="id_birthday" required>
<input type="hidden" name="hidden_text" id="id_hidden_text"></p>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_first_name">First name:</label><input type="text" '
            'name="first_name" id="id_first_name" required></div><div><label '
            'for="id_last_name">Last name:</label><input type="text" name="last_name" '
            'id="id_last_name" required></div><div><label for="id_birthday">Birthday:'
            '</label><input type="text" name="birthday" id="id_birthday" required>'
            '<input type="hidden" name="hidden_text" id="id_hidden_text"></div>',
        )

        # If a field with a HiddenInput has errors, the as_table() and as_ul() output
        # will include the error message(s) with the text "(Hidden field [fieldname]) "
        # prepended. This message is displayed at the top of the output, regardless of
        # its field's order in the form.
        p = Person(
            {"first_name": "John", "last_name": "Lennon", "birthday": "1940-10-9"},
            auto_id=False,
        )
        self.assertHTMLEqual(
            p.as_table(),
            """
            <tr><td colspan="2">
            <ul class="errorlist nonfield"><li>
            (Hidden field hidden_text) This field is required.</li></ul></td></tr>
            <tr><th>First name:</th><td>
            <input type="text" name="first_name" value="John" required></td></tr>
            <tr><th>Last name:</th><td>
            <input type="text" name="last_name" value="Lennon" required></td></tr>
            <tr><th>Birthday:</th><td>
            <input type="text" name="birthday" value="1940-10-9" required>
            <input type="hidden" name="hidden_text"></td></tr>
            """,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li><ul class="errorlist nonfield"><li>
            (Hidden field hidden_text) This field is required.</li></ul></li>
            <li>First name: <input type="text" name="first_name" value="John" required>
            </li>
            <li>Last name: <input type="text" name="last_name" value="Lennon" required>
            </li>
            <li>Birthday: <input type="text" name="birthday" value="1940-10-9" required>
            <input type="hidden" name="hidden_text"></li>
            """,
        )
        self.assertHTMLEqual(
            p.as_p(),
            """
            <ul class="errorlist nonfield"><li>
            (Hidden field hidden_text) This field is required.</li></ul>
            <p>First name: <input type="text" name="first_name" value="John" required>
            </p>
            <p>Last name: <input type="text" name="last_name" value="Lennon" required>
            </p>
            <p>Birthday: <input type="text" name="birthday" value="1940-10-9" required>
            <input type="hidden" name="hidden_text"></p>
            """,
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<ul class="errorlist nonfield"><li>(Hidden field hidden_text) This field '
            'is required.</li></ul><div>First name: <input type="text" '
            'name="first_name" value="John" required></div><div>Last name: <input '
            'type="text" name="last_name" value="Lennon" required></div><div>'
            'Birthday: <input type="text" name="birthday" value="1940-10-9" required>'
            '<input type="hidden" name="hidden_text"></div>',
        )

        # A corner case: It's possible for a form to have only HiddenInputs.
        class TestForm(Form):
            foo = CharField(widget=HiddenInput)
            bar = CharField(widget=HiddenInput)

        p = TestForm(auto_id=False)
        self.assertHTMLEqual(
            p.as_table(),
            '<input type="hidden" name="foo"><input type="hidden" name="bar">',
        )
        self.assertHTMLEqual(
            p.as_ul(),
            '<input type="hidden" name="foo"><input type="hidden" name="bar">',
        )
        self.assertHTMLEqual(
            p.as_p(), '<input type="hidden" name="foo"><input type="hidden" name="bar">'
        )

    def test_hidden_widget_does_not_have_aria_describedby(self):
        """

        Test that a hidden widget in a form does not have an aria-describedby attribute.

        This test ensures that the HTML generated for a hidden form field does not include
        an aria-describedby attribute, which is used to reference a description of the
        element for accessibility purposes. Since a hidden field is not visible to the user,
        it should not have a description.

        The test uses a sample form with a single hidden text field to verify the expected
        HTML output.

        """
        class TestForm(Form):
            hidden_text = CharField(widget=HiddenInput, help_text="Help Text")

        f = TestForm()
        self.assertEqual(
            str(f), '<input type="hidden" name="hidden_text" id="id_hidden_text">'
        )

    def test_field_order(self):
        # A Form's fields are displayed in the same order in which they were defined.
        """

        Test that the fields in a form are rendered in the correct order when 
        as_table() method is called.

        This test case creates a test form with 14 character fields, then checks 
        that the fields are rendered as table rows in the order they were 
        defined in the form. The test is case sensitive and verifies that each 
        field is followed by its corresponding input field in the generated HTML.

        """
        class TestForm(Form):
            field1 = CharField()
            field2 = CharField()
            field3 = CharField()
            field4 = CharField()
            field5 = CharField()
            field6 = CharField()
            field7 = CharField()
            field8 = CharField()
            field9 = CharField()
            field10 = CharField()
            field11 = CharField()
            field12 = CharField()
            field13 = CharField()
            field14 = CharField()

        p = TestForm(auto_id=False)
        self.assertHTMLEqual(
            p.as_table(),
            "".join(
                f"<tr><th>Field{i}:</th><td>"
                f'<input type="text" name="field{i}" required></td></tr>'
                for i in range(1, 15)
            ),
        )

    def test_explicit_field_order(self):
        """
        #: Tests the handling of explicit field order in form classes.
        #: 
        #: Verifies that fields are ordered according to the `field_order` attribute, 
        #: that fields without an explicit order are appended to the end, and that 
        #: fields removed from the `field_order` attribute or set to `None` are still 
        #: included in the form fields, albeit in a different order. 
        #: 
        #: Additionally, checks the behavior when the `field_order` attribute is set 
        #: to `None` or is missing, and when the order is specified at form initialization. 
        #: 
        #: Confirms that the form fields are correctly ordered in different scenarios, 
        #: including when the `field_order` attribute is modified or when new fields 
        #: are added or removed.
        """
        class TestFormParent(Form):
            field1 = CharField()
            field2 = CharField()
            field4 = CharField()
            field5 = CharField()
            field6 = CharField()
            field_order = ["field6", "field5", "field4", "field2", "field1"]

        class TestForm(TestFormParent):
            field3 = CharField()
            field_order = ["field2", "field4", "field3", "field5", "field6"]

        class TestFormRemove(TestForm):
            field1 = None

        class TestFormMissing(TestForm):
            field_order = ["field2", "field4", "field3", "field5", "field6", "field1"]
            field1 = None

        class TestFormInit(TestFormParent):
            field3 = CharField()
            field_order = None

            def __init__(self, **kwargs):
                """

                Initializes the instance, setting up the internal state and ordering the fields according to the specified field order.

                The initialization process involves calling the parent class's constructor with any provided keyword arguments, and then ordering the fields based on the predefined field order defined in :attr:`TestForm.field_order`.

                This ensures that the fields are consistently arranged in a specific order, which can be useful for presenting the form to users or for internal processing.

                """
                super().__init__(**kwargs)
                self.order_fields(field_order=TestForm.field_order)

        p = TestFormParent()
        self.assertEqual(list(p.fields), TestFormParent.field_order)
        p = TestFormRemove()
        self.assertEqual(list(p.fields), TestForm.field_order)
        p = TestFormMissing()
        self.assertEqual(list(p.fields), TestForm.field_order)
        p = TestForm()
        self.assertEqual(list(p.fields), TestFormMissing.field_order)
        p = TestFormInit()
        order = [*TestForm.field_order, "field1"]
        self.assertEqual(list(p.fields), order)
        TestForm.field_order = ["unknown"]
        p = TestForm()
        self.assertEqual(
            list(p.fields), ["field1", "field2", "field4", "field5", "field6", "field3"]
        )

    def test_form_html_attributes(self):
        # Some Field classes have an effect on the HTML attributes of their associated
        # Widget. If you set max_length in a CharField and its associated widget is
        # either a TextInput or PasswordInput, then the widget's rendered HTML will
        # include the "maxlength" attribute.
        """

        Tests the HTML attributes rendered by Django forms.

        This function verifies that Django forms correctly generate HTML attributes for 
        their fields, specifically checking the 'maxlength' attribute. It tests both the 
        case where the 'maxlength' attribute is set explicitly in the widget, and the 
        case where it is inferred from the field's 'max_length' parameter.

        The test checks that the resulting HTML is as expected, including the correct 
        rendering of 'maxlength' and 'type' attributes for different field types, such 
        as text and password inputs.

        """
        class UserRegistration(Form):
            username = CharField(max_length=10)  # uses TextInput by default
            password = CharField(max_length=10, widget=PasswordInput)
            realname = CharField(
                max_length=10, widget=TextInput
            )  # redundantly define widget, just to test
            address = CharField()  # no max_length defined here

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" maxlength="10" required>
            </li>
            <li>Password: <input type="password" name="password" maxlength="10"
                required></li>
            <li>Realname: <input type="text" name="realname" maxlength="10" required>
            </li>
            <li>Address: <input type="text" name="address" required></li>
            """,
        )

        # If you specify a custom "attrs" that includes the "maxlength"
        # attribute, the Field's max_length attribute will override whatever
        # "maxlength" you specify in "attrs".
        class UserRegistration(Form):
            username = CharField(
                max_length=10, widget=TextInput(attrs={"maxlength": 20})
            )
            password = CharField(max_length=10, widget=PasswordInput)

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            '<li>Username: <input type="text" name="username" maxlength="10" required>'
            "</li>"
            '<li>Password: <input type="password" name="password" maxlength="10" '
            "required></li>",
        )

    def test_specifying_labels(self):
        # You can specify the label for a field by using the 'label' argument to a Field
        # class. If you don't specify 'label', Django will use the field name with
        # underscores converted to spaces, and the initial letter capitalized.
        class UserRegistration(Form):
            username = CharField(max_length=10, label="Your username")
            password1 = CharField(widget=PasswordInput)
            password2 = CharField(widget=PasswordInput, label="Contraseña (de nuevo)")

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Your username:
            <input type="text" name="username" maxlength="10" required></li>
            <li>Password1: <input type="password" name="password1" required></li>
            <li>Contraseña (de nuevo):
            <input type="password" name="password2" required></li>
            """,
        )

        # Labels for as_* methods will only end in a colon if they don't end in other
        # punctuation already.
        class Questions(Form):
            q1 = CharField(label="The first question")
            q2 = CharField(label="What is your name?")
            q3 = CharField(label="The answer to life is:")
            q4 = CharField(label="Answer this question!")
            q5 = CharField(label="The last question. Period.")

        self.assertHTMLEqual(
            Questions(auto_id=False).as_p(),
            """<p>The first question: <input type="text" name="q1" required></p>
<p>What is your name? <input type="text" name="q2" required></p>
<p>The answer to life is: <input type="text" name="q3" required></p>
<p>Answer this question! <input type="text" name="q4" required></p>
<p>The last question. Period. <input type="text" name="q5" required></p>""",
        )
        self.assertHTMLEqual(
            Questions().as_p(),
            """
            <p><label for="id_q1">The first question:</label>
            <input type="text" name="q1" id="id_q1" required></p>
            <p><label for="id_q2">What is your name?</label>
            <input type="text" name="q2" id="id_q2" required></p>
            <p><label for="id_q3">The answer to life is:</label>
            <input type="text" name="q3" id="id_q3" required></p>
            <p><label for="id_q4">Answer this question!</label>
            <input type="text" name="q4" id="id_q4" required></p>
            <p><label for="id_q5">The last question. Period.</label>
            <input type="text" name="q5" id="id_q5" required></p>
            """,
        )

        # If a label is set to the empty string for a field, that field won't
        # get a label.
        class UserRegistration(Form):
            username = CharField(max_length=10, label="")
            password = CharField(widget=PasswordInput)

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li> <input type="text" name="username" maxlength="10" required></li>
<li>Password: <input type="password" name="password" required></li>""",
        )
        p = UserRegistration(auto_id="id_%s")
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>
            <input id="id_username" type="text" name="username" maxlength="10" required>
            </li>
            <li><label for="id_password">Password:</label>
            <input type="password" name="password" id="id_password" required></li>
            """,
        )

        # If label is None, Django will auto-create the label from the field name. This
        # is default behavior.
        class UserRegistration(Form):
            username = CharField(max_length=10, label=None)
            password = CharField(widget=PasswordInput)

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            '<li>Username: <input type="text" name="username" maxlength="10" required>'
            "</li>"
            '<li>Password: <input type="password" name="password" required></li>',
        )
        p = UserRegistration(auto_id="id_%s")
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><label for="id_username">Username:</label>
<input id="id_username" type="text" name="username" maxlength="10" required></li>
<li><label for="id_password">Password:</label>
<input type="password" name="password" id="id_password" required></li>""",
        )

    def test_label_suffix(self):
        # You can specify the 'label_suffix' argument to a Form class to modify
        # the punctuation symbol used at the end of a label. By default, the
        # colon (:) is used, and is only appended to the label if the label
        # doesn't already end with a punctuation symbol: ., !, ? or :. If you
        # specify a different suffix, it will be appended regardless of the
        # last character of the label.
        class FavoriteForm(Form):
            color = CharField(label="Favorite color?")
            animal = CharField(label="Favorite animal")
            answer = CharField(label="Secret answer", label_suffix=" =")

        f = FavoriteForm(auto_id=False)
        self.assertHTMLEqual(
            f.as_ul(),
            """<li>Favorite color? <input type="text" name="color" required></li>
<li>Favorite animal: <input type="text" name="animal" required></li>
<li>Secret answer = <input type="text" name="answer" required></li>""",
        )

        f = FavoriteForm(auto_id=False, label_suffix="?")
        self.assertHTMLEqual(
            f.as_ul(),
            """<li>Favorite color? <input type="text" name="color" required></li>
<li>Favorite animal? <input type="text" name="animal" required></li>
<li>Secret answer = <input type="text" name="answer" required></li>""",
        )

        f = FavoriteForm(auto_id=False, label_suffix="")
        self.assertHTMLEqual(
            f.as_ul(),
            """<li>Favorite color? <input type="text" name="color" required></li>
<li>Favorite animal <input type="text" name="animal" required></li>
<li>Secret answer = <input type="text" name="answer" required></li>""",
        )

        f = FavoriteForm(auto_id=False, label_suffix="\u2192")
        self.assertHTMLEqual(
            f.as_ul(),
            '<li>Favorite color? <input type="text" name="color" required></li>\n'
            "<li>Favorite animal\u2192 "
            '<input type="text" name="animal" required></li>\n'
            '<li>Secret answer = <input type="text" name="answer" required></li>',
        )

    def test_initial_data(self):
        # You can specify initial data for a field by using the 'initial' argument to a
        # Field class. This initial data is displayed when a Form is rendered with *no*
        # data. It is not displayed when a Form is rendered with any data (including an
        # empty dictionary). Also, the initial value is *not* used if data for a
        # particular required field isn't provided.
        """

        Tests the initial data of a UserRegistration form.

        This test case checks the rendering of the form with different initial values, 
        enforcing the correct rendering of fields, including their initial values and
        error messages when necessary. It verifies that required fields are properly 
        marked and that error messages are displayed when the form is invalid.

        """
        class UserRegistration(Form):
            username = CharField(max_length=10, initial="django")
            password = CharField(widget=PasswordInput)

        # Here, we're not submitting any data, so the initial value will be displayed.)
        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="django"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            """,
        )

        # Here, we're submitting data, so the initial value will *not* be displayed.
        p = UserRegistration({}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true" required></li>""",
        )
        p = UserRegistration({"username": ""}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true" required></li>""",
        )
        p = UserRegistration({"username": "foo"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="foo" maxlength="10"
                required></li>
            <li><ul class="errorlist"><li>This field is required.</li></ul>
            Password: <input type="password" name="password" aria-invalid="true"
            required></li>
            """,
        )

        # An 'initial' value is *not* used as a fallback if data is not
        # provided. In this example, we don't provide a value for 'username',
        # and the form raises a validation error rather than using the initial
        # value for 'username'.
        p = UserRegistration({"password": "secret"})
        self.assertEqual(p.errors["username"], ["This field is required."])
        self.assertFalse(p.is_valid())

    def test_dynamic_initial_data(self):
        # The previous technique dealt with "hard-coded" initial data, but it's also
        # possible to specify initial data after you've already created the Form class
        # (i.e., at runtime). Use the 'initial' parameter to the Form constructor. This
        # should be a dictionary containing initial values for one or more fields in the
        # form, keyed by field name.
        """
        Tests the dynamic initialization of form data in Django forms.

        Verifies that the form fields are correctly populated with initial data,
        and that the 'initial' parameter takes precedence over the 'data' parameter.
        Checks for correct HTML rendering of form fields with initial data,
        including required fields and password fields.

        Also tests that when 'data' is provided, it overrides the 'initial' data,
        and that form validation correctly reports missing required fields.
        """
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password = CharField(widget=PasswordInput)

        # Here, we're not submitting any data, so the initial value will be displayed.)
        p = UserRegistration(initial={"username": "django"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="django"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            """,
        )
        p = UserRegistration(initial={"username": "stephane"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="stephane"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            """,
        )

        # The 'initial' parameter is meaningless if you pass data.
        p = UserRegistration({}, initial={"username": "django"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true" required></li>""",
        )
        p = UserRegistration(
            {"username": ""}, initial={"username": "django"}, auto_id=False
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true" required></li>""",
        )
        p = UserRegistration(
            {"username": "foo"}, initial={"username": "django"}, auto_id=False
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="foo" maxlength="10"
                required></li>
            <li><ul class="errorlist"><li>This field is required.</li></ul>
            Password: <input type="password" name="password" aria-invalid="true"
            required></li>
            """,
        )

        # A dynamic 'initial' value is *not* used as a fallback if data is not provided.
        # In this example, we don't provide a value for 'username', and the
        # form raises a validation error rather than using the initial value
        # for 'username'.
        p = UserRegistration({"password": "secret"}, initial={"username": "django"})
        self.assertEqual(p.errors["username"], ["This field is required."])
        self.assertFalse(p.is_valid())

        # If a Form defines 'initial' *and* 'initial' is passed as a parameter
        # to Form(), then the latter will get precedence.
        class UserRegistration(Form):
            username = CharField(max_length=10, initial="django")
            password = CharField(widget=PasswordInput)

        p = UserRegistration(initial={"username": "babik"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="babik"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            """,
        )

    def test_callable_initial_data(self):
        # The previous technique dealt with raw values as initial data, but it's also
        # possible to specify callable data.
        """

        Test the initialization of form fields with callable initial data.

        Verifies that form fields are properly initialized with values returned 
        by callable objects passed as the 'initial' parameter to the Form class. 
        In cases where the field has an 'initial' attribute, this value takes 
        precedence over any values provided by the form's 'initial' parameter.

        Checks for both valid and invalid form submissions to ensure that 
        callable initial data is correctly applied in various scenarios.

        """
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password = CharField(widget=PasswordInput)
            options = MultipleChoiceField(
                choices=[("f", "foo"), ("b", "bar"), ("w", "whiz")]
            )

        # We need to define functions that get called later.)
        def initial_django():
            return "django"

        def initial_stephane():
            return "stephane"

        def initial_options():
            return ["f", "b"]

        def initial_other_options():
            return ["b", "w"]

        # Here, we're not submitting any data, so the initial value will be displayed.)
        p = UserRegistration(
            initial={"username": initial_django, "options": initial_options},
            auto_id=False,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="django"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            <li>Options: <select multiple name="options" required>
            <option value="f" selected>foo</option>
            <option value="b" selected>bar</option>
            <option value="w">whiz</option>
            </select></li>
            """,
        )

        # The 'initial' parameter is meaningless if you pass data.
        p = UserRegistration(
            {},
            initial={"username": initial_django, "options": initial_options},
            auto_id=False,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Options: <select multiple name="options" aria-invalid="true" required>
<option value="f">foo</option>
<option value="b">bar</option>
<option value="w">whiz</option>
</select></li>""",
        )
        p = UserRegistration(
            {"username": ""}, initial={"username": initial_django}, auto_id=False
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist"><li>This field is required.</li></ul>
Username: <input type="text" name="username" maxlength="10" aria-invalid="true"
required></li><li><ul class="errorlist"><li>This field is required.</li></ul>
Password: <input type="password" name="password" aria-invalid="true" required></li>
<li><ul class="errorlist"><li>This field is required.</li></ul>
Options: <select multiple name="options" aria-invalid="true" required>
<option value="f">foo</option>
<option value="b">bar</option>
<option value="w">whiz</option>
</select></li>""",
        )
        p = UserRegistration(
            {"username": "foo", "options": ["f", "b"]},
            initial={"username": initial_django},
            auto_id=False,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="foo" maxlength="10"
                required></li>
            <li><ul class="errorlist"><li>This field is required.</li></ul>
            Password: <input type="password" name="password" aria-invalid="true"
            required></li><li>Options: <select multiple name="options" required>
            <option value="f" selected>foo</option>
            <option value="b" selected>bar</option>
            <option value="w">whiz</option>
            </select></li>
            """,
        )

        # A callable 'initial' value is *not* used as a fallback if data is not
        # provided. In this example, we don't provide a value for 'username',
        # and the form raises a validation error rather than using the initial
        # value for 'username'.
        p = UserRegistration(
            {"password": "secret"},
            initial={"username": initial_django, "options": initial_options},
        )
        self.assertEqual(p.errors["username"], ["This field is required."])
        self.assertFalse(p.is_valid())

        # If a Form defines 'initial' *and* 'initial' is passed as a parameter
        # to Form(), then the latter will get precedence.
        class UserRegistration(Form):
            username = CharField(max_length=10, initial=initial_django)
            password = CharField(widget=PasswordInput)
            options = MultipleChoiceField(
                choices=[("f", "foo"), ("b", "bar"), ("w", "whiz")],
                initial=initial_other_options,
            )

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="django"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            <li>Options: <select multiple name="options" required>
            <option value="f">foo</option>
            <option value="b" selected>bar</option>
            <option value="w" selected>whiz</option>
            </select></li>
            """,
        )
        p = UserRegistration(
            initial={"username": initial_stephane, "options": initial_options},
            auto_id=False,
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li>Username: <input type="text" name="username" value="stephane"
                maxlength="10" required></li>
            <li>Password: <input type="password" name="password" required></li>
            <li>Options: <select multiple name="options" required>
            <option value="f" selected>foo</option>
            <option value="b" selected>bar</option>
            <option value="w">whiz</option>
            </select></li>
            """,
        )

    def test_get_initial_for_field(self):
        """

        Tests the functionality of getting initial values for form fields.

        This function verifies that the `get_initial_for_field` method correctly retrieves the initial values for fields 
        in a form, considering both explicit initial values and those generated by callable functions. It checks 
        various field types, including CharField, IntegerField, and DateTimeField, to ensure that initial values are 
        returned as expected.

        The test covers different scenarios, such as fields with explicitly set initial values, fields with callable 
        initial values, and fields without any initial value. The correctness of the `get_initial_for_field` method 
        is validated for each field type and scenario, ensuring that it behaves as expected in various situations.

        """
        now = datetime.datetime(2006, 10, 25, 14, 30, 45, 123456)

        class PersonForm(Form):
            first_name = CharField(initial="John")
            last_name = CharField(initial="Doe")
            age = IntegerField()
            occupation = CharField(initial=lambda: "Unknown")
            dt_fixed = DateTimeField(initial=now)
            dt_callable = DateTimeField(initial=lambda: now)

        form = PersonForm(initial={"first_name": "Jane"})
        cases = [
            ("age", None),
            ("last_name", "Doe"),
            # Form.initial overrides Field.initial.
            ("first_name", "Jane"),
            # Callables are evaluated.
            ("occupation", "Unknown"),
            # Microseconds are removed from datetimes.
            ("dt_fixed", datetime.datetime(2006, 10, 25, 14, 30, 45)),
            ("dt_callable", datetime.datetime(2006, 10, 25, 14, 30, 45)),
        ]
        for field_name, expected in cases:
            with self.subTest(field_name=field_name):
                field = form.fields[field_name]
                actual = form.get_initial_for_field(field, field_name)
                self.assertEqual(actual, expected)

    def test_changed_data(self):
        """

        Tests whether the changed_data dictionary on a Form instance correctly
        identifies fields that have been modified from their initial values.

        Checks the following scenarios:
        - When a field's value is modified, it is included in changed_data.
        - When a field's value is not modified, it is not included in changed_data.
        - When a field's validation fails, it is included in changed_data, even if its value was not actually changed.

        """
        class Person(Form):
            first_name = CharField(initial="Hans")
            last_name = CharField(initial="Greatel")
            birthday = DateField(initial=datetime.date(1974, 8, 16))

        p = Person(
            data={"first_name": "Hans", "last_name": "Scrmbl", "birthday": "1974-08-16"}
        )
        self.assertTrue(p.is_valid())
        self.assertNotIn("first_name", p.changed_data)
        self.assertIn("last_name", p.changed_data)
        self.assertNotIn("birthday", p.changed_data)

        # A field raising ValidationError is always in changed_data
        class PedanticField(Field):
            def to_python(self, value):
                raise ValidationError("Whatever")

        class Person2(Person):
            pedantic = PedanticField(initial="whatever", show_hidden_initial=True)

        p = Person2(
            data={
                "first_name": "Hans",
                "last_name": "Scrmbl",
                "birthday": "1974-08-16",
                "initial-pedantic": "whatever",
            }
        )
        self.assertFalse(p.is_valid())
        self.assertIn("pedantic", p.changed_data)

    def test_boundfield_values(self):
        # It's possible to get to the value which would be used for rendering
        # the widget for a field by using the BoundField's value method.

        class UserRegistration(Form):
            username = CharField(max_length=10, initial="djangonaut")
            password = CharField(widget=PasswordInput)

        unbound = UserRegistration()
        bound = UserRegistration({"password": "foo"})
        self.assertIsNone(bound["username"].value())
        self.assertEqual(unbound["username"].value(), "djangonaut")
        self.assertEqual(bound["password"].value(), "foo")
        self.assertIsNone(unbound["password"].value())

    def test_boundfield_initial_called_once(self):
        """
        Multiple calls to BoundField().value() in an unbound form should return
        the same result each time (#24391).
        """

        class MyForm(Form):
            name = CharField(max_length=10, initial=uuid.uuid4)

        form = MyForm()
        name = form["name"]
        self.assertEqual(name.value(), name.value())
        # BoundField is also cached
        self.assertIs(form["name"], name)

    def test_boundfield_value_disabled_callable_initial(self):
        class PersonForm(Form):
            name = CharField(initial=lambda: "John Doe", disabled=True)

        # Without form data.
        form = PersonForm()
        self.assertEqual(form["name"].value(), "John Doe")

        # With form data. As the field is disabled, the value should not be
        # affected by the form data.
        form = PersonForm({})
        self.assertEqual(form["name"].value(), "John Doe")

    def test_custom_boundfield(self):
        """

        Tests that a custom bound field can be successfully retrieved from a form.

        The test case creates a custom field class that overrides the get_bound_field method,
        which is responsible for returning the bound field for a given form and field name.
        The test then creates a form instance with the custom field and verifies that the
        bound field is correctly returned when accessing the field by name on the form.

        """
        class CustomField(CharField):
            def get_bound_field(self, form, name):
                return (form, name)

        class SampleForm(Form):
            name = CustomField()

        f = SampleForm()
        self.assertEqual(f["name"], (f, "name"))

    def test_initial_datetime_values(self):
        """

        Tests the initial datetime values for various form fields.

        This test case verifies that the initial datetime values are correctly set for 
        different types of form fields, including DateTimeField, TimeField, and fields 
        with custom widgets (HiddenInput and TextInput). It checks that the initial values 
        are correctly set for fields with and without microsecond support, and that the 
        values are correctly returned by the form's value() method and get_initial_for_field() method.

        """
        now = datetime.datetime.now()
        # Nix microseconds (since they should be ignored). #22502
        now_no_ms = now.replace(microsecond=0)
        if now == now_no_ms:
            now = now.replace(microsecond=1)

        def delayed_now():
            return now

        def delayed_now_time():
            return now.time()

        class HiddenInputWithoutMicrosec(HiddenInput):
            supports_microseconds = False

        class TextInputWithoutMicrosec(TextInput):
            supports_microseconds = False

        class DateTimeForm(Form):
            # Test a non-callable.
            fixed = DateTimeField(initial=now)
            auto_timestamp = DateTimeField(initial=delayed_now)
            auto_time_only = TimeField(initial=delayed_now_time)
            supports_microseconds = DateTimeField(initial=delayed_now, widget=TextInput)
            hi_default_microsec = DateTimeField(initial=delayed_now, widget=HiddenInput)
            hi_without_microsec = DateTimeField(
                initial=delayed_now, widget=HiddenInputWithoutMicrosec
            )
            ti_without_microsec = DateTimeField(
                initial=delayed_now, widget=TextInputWithoutMicrosec
            )

        unbound = DateTimeForm()
        cases = [
            ("fixed", now_no_ms),
            ("auto_timestamp", now_no_ms),
            ("auto_time_only", now_no_ms.time()),
            ("supports_microseconds", now),
            ("hi_default_microsec", now),
            ("hi_without_microsec", now_no_ms),
            ("ti_without_microsec", now_no_ms),
        ]
        for field_name, expected in cases:
            with self.subTest(field_name=field_name):
                actual = unbound[field_name].value()
                self.assertEqual(actual, expected)
                # Also check get_initial_for_field().
                field = unbound.fields[field_name]
                actual = unbound.get_initial_for_field(field, field_name)
                self.assertEqual(actual, expected)

    def get_datetime_form_with_callable_initial(self, disabled, microseconds=0):
        class FakeTime:
            def __init__(self):
                self.elapsed_seconds = 0

            def now(self):
                """
                >Returns the current time, incrementing the elapsed seconds counter by one.
                >
                >Each call to this method returns a new datetime object representing the incremented time.
                >
                >The time starts from a fixed base date of October 25, 2006, 14:30:45, and increments by one second with each call.
                """
                self.elapsed_seconds += 1
                return datetime.datetime(
                    2006,
                    10,
                    25,
                    14,
                    30,
                    45 + self.elapsed_seconds,
                    microseconds,
                )

        class DateTimeForm(Form):
            dt = DateTimeField(initial=FakeTime().now, disabled=disabled)

        return DateTimeForm({})

    def test_datetime_clean_disabled_callable_initial_microseconds(self):
        """
        Cleaning a form with a disabled DateTimeField and callable initial
        removes microseconds.
        """
        form = self.get_datetime_form_with_callable_initial(
            disabled=True,
            microseconds=123456,
        )
        self.assertEqual(form.errors, {})
        self.assertEqual(
            form.cleaned_data,
            {
                "dt": datetime.datetime(2006, 10, 25, 14, 30, 46),
            },
        )

    def test_datetime_clean_disabled_callable_initial_bound_field(self):
        """
        The cleaned value for a form with a disabled DateTimeField and callable
        initial matches the bound field's cached initial value.
        """
        form = self.get_datetime_form_with_callable_initial(disabled=True)
        self.assertEqual(form.errors, {})
        cleaned = form.cleaned_data["dt"]
        self.assertEqual(cleaned, datetime.datetime(2006, 10, 25, 14, 30, 46))
        bf = form["dt"]
        self.assertEqual(cleaned, bf.initial)

    def test_datetime_changed_data_callable_with_microseconds(self):
        class DateTimeForm(Form):
            dt = DateTimeField(
                initial=lambda: datetime.datetime(2006, 10, 25, 14, 30, 45, 123456),
                disabled=True,
            )

        form = DateTimeForm({"dt": "2006-10-25 14:30:45"})
        self.assertEqual(form.changed_data, [])

    def test_help_text(self):
        # You can specify descriptive text for a field by using the 'help_text'
        # argument.
        """
        Tests that the help text for form fields is correctly rendered in various formats.

        The function checks the following:

        * The help text is displayed for each field in the form, regardless of the format used to render the form (unordered list, paragraph, table, or div).
        * The help text is correctly associated with the corresponding form field.
        * The help text is not displayed for hidden fields.
        * The function also tests that the help text is rendered correctly when the form is populated with initial data, and when the form contains errors. 

        Specifically, it verifies that the help text is correctly rendered for CharField and PasswordInput fields, and that it is omitted for HiddenInput fields.
        """
        class UserRegistration(Form):
            username = CharField(max_length=10, help_text="e.g., user@example.com")
            password = CharField(
                widget=PasswordInput, help_text="Wählen Sie mit Bedacht."
            )

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li>Username: <input type="text" name="username" maxlength="10" required>
<span class="helptext">e.g., user@example.com</span></li>
<li>Password: <input type="password" name="password" required>
<span class="helptext">Wählen Sie mit Bedacht.</span></li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<p>Username: <input type="text" name="username" maxlength="10" required>
<span class="helptext">e.g., user@example.com</span></p>
<p>Password: <input type="password" name="password" required>
<span class="helptext">Wählen Sie mit Bedacht.</span></p>""",
        )
        self.assertHTMLEqual(
            p.as_table(),
            """
            <tr><th>Username:</th><td>
            <input type="text" name="username" maxlength="10" required><br>
            <span class="helptext">e.g., user@example.com</span></td></tr>
            <tr><th>Password:</th><td><input type="password" name="password" required>
            <br>
            <span class="helptext">Wählen Sie mit Bedacht.</span></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div>Username: <div class="helptext">e.g., user@example.com</div>'
            '<input type="text" name="username" maxlength="10" required></div>'
            '<div>Password: <div class="helptext">Wählen Sie mit Bedacht.</div>'
            '<input type="password" name="password" required></div>',
        )

        # The help text is displayed whether or not data is provided for the form.
        p = UserRegistration({"username": "foo"}, auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            '<li>Username: <input type="text" name="username" value="foo" '
            'maxlength="10" required>'
            '<span class="helptext">e.g., user@example.com</span></li>'
            '<li><ul class="errorlist"><li>This field is required.</li></ul>'
            'Password: <input type="password" name="password" aria-invalid="true" '
            'required><span class="helptext">Wählen Sie mit Bedacht.</span></li>',
        )

        # help_text is not displayed for hidden fields. It can be used for documentation
        # purposes, though.
        class UserRegistration(Form):
            username = CharField(max_length=10, help_text="e.g., user@example.com")
            password = CharField(widget=PasswordInput)
            next = CharField(
                widget=HiddenInput, initial="/", help_text="Redirect destination"
            )

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li>Username: <input type="text" name="username" maxlength="10" required>
<span class="helptext">e.g., user@example.com</span></li>
<li>Password: <input type="password" name="password" required>
<input type="hidden" name="next" value="/"></li>""",
        )

    def test_help_text_html_safe(self):
        """help_text should not be escaped."""

        class UserRegistration(Form):
            username = CharField(max_length=10, help_text="e.g., user@example.com")
            password = CharField(
                widget=PasswordInput,
                help_text="Help text is <strong>escaped</strong>.",
            )

        p = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            '<li>Username: <input type="text" name="username" maxlength="10" required>'
            '<span class="helptext">e.g., user@example.com</span></li>'
            '<li>Password: <input type="password" name="password" required>'
            '<span class="helptext">Help text is <strong>escaped</strong>.</span></li>',
        )
        self.assertHTMLEqual(
            p.as_p(),
            '<p>Username: <input type="text" name="username" maxlength="10" required>'
            '<span class="helptext">e.g., user@example.com</span></p>'
            '<p>Password: <input type="password" name="password" required>'
            '<span class="helptext">Help text is <strong>escaped</strong>.</span></p>',
        )
        self.assertHTMLEqual(
            p.as_table(),
            "<tr><th>Username:</th><td>"
            '<input type="text" name="username" maxlength="10" required><br>'
            '<span class="helptext">e.g., user@example.com</span></td></tr>'
            "<tr><th>Password:</th><td>"
            '<input type="password" name="password" required><br>'
            '<span class="helptext">Help text is <strong>escaped</strong>.</span>'
            "</td></tr>",
        )

    def test_widget_attrs_custom_aria_describedby(self):
        # aria-describedby provided to the widget overrides the default.

        class UserRegistration(Form):
            username = CharField(
                max_length=255,
                help_text="e.g., user@example.com",
                widget=TextInput(attrs={"aria-describedby": "custom-description"}),
            )
            password = CharField(
                widget=PasswordInput, help_text="Wählen Sie mit Bedacht."
            )

        p = UserRegistration()
        self.assertHTMLEqual(
            p.as_div(),
            '<div><label for="id_username">Username:</label>'
            '<div class="helptext" id="id_username_helptext">e.g., user@example.com'
            '</div><input type="text" name="username" maxlength="255" required '
            'aria-describedby="custom-description" id="id_username">'
            "</div><div>"
            '<label for="id_password">Password:</label>'
            '<div class="helptext" id="id_password_helptext">Wählen Sie mit Bedacht.'
            '</div><input type="password" name="password" required '
            'aria-describedby="id_password_helptext" id="id_password"></div>',
        )
        self.assertHTMLEqual(
            p.as_ul(),
            '<li><label for="id_username">Username:</label><input type="text" '
            'name="username" maxlength="255" required '
            'aria-describedby="custom-description" id="id_username">'
            '<span class="helptext" id="id_username_helptext">e.g., user@example.com'
            "</span></li><li>"
            '<label for="id_password">Password:</label>'
            '<input type="password" name="password" required '
            'aria-describedby="id_password_helptext" id="id_password">'
            '<span class="helptext" id="id_password_helptext">Wählen Sie mit Bedacht.'
            "</span></li>",
        )
        self.assertHTMLEqual(
            p.as_p(),
            '<p><label for="id_username">Username:</label><input type="text" '
            'name="username" maxlength="255" required '
            'aria-describedby="custom-description" id="id_username">'
            '<span class="helptext" id="id_username_helptext">e.g., user@example.com'
            "</span></p><p>"
            '<label for="id_password">Password:</label>'
            '<input type="password" name="password" required '
            'aria-describedby="id_password_helptext" id="id_password">'
            '<span class="helptext" id="id_password_helptext">Wählen Sie mit Bedacht.'
            "</span></p>",
        )
        self.assertHTMLEqual(
            p.as_table(),
            '<tr><th><label for="id_username">Username:</label></th><td>'
            '<input type="text" name="username" maxlength="255" required '
            'aria-describedby="custom-description" id="id_username"><br>'
            '<span class="helptext" id="id_username_helptext">e.g., user@example.com'
            "</span></td></tr><tr><th>"
            '<label for="id_password">Password:</label></th><td>'
            '<input type="password" name="password" required '
            'aria-describedby="id_password_helptext" id="id_password"><br>'
            '<span class="helptext" id="id_password_helptext">Wählen Sie mit Bedacht.'
            "</span></td></tr>",
        )

    def test_aria_describedby_custom_widget_id(self):
        """
        Tests that the aria-describedby attribute is correctly set on a custom widget.

        When a form field is rendered, it should include an aria-describedby attribute that references
        the id of the help text element. This test case verifies that this attribute is correctly
        generated even when a custom id is specified for the widget.

        The test creates a simple form with a single field, a CharField with a custom widget id.
        It then asserts that the rendered HTML includes the expected aria-describedby attribute,
        referencing the id of the help text element, when the custom id is used for the widget.
        """
        class UserRegistration(Form):
            username = CharField(
                max_length=255,
                help_text="e.g., user@example.com",
                widget=TextInput(attrs={"id": "custom-id"}),
            )

        f = UserRegistration()
        self.assertHTMLEqual(
            str(f),
            '<div><label for="custom-id">Username:</label>'
            '<div class="helptext" id="id_username_helptext">e.g., user@example.com'
            '</div><input type="text" name="username" id="custom-id" maxlength="255" '
            'required aria-describedby="id_username_helptext"></div>',
        )

    def test_fieldset_aria_describedby(self):
        """
        **:param self: Test instance.
            :return: None

            Tests the generation of fieldsets and their associated ARIA attributes for accessibility.

            Verifies that fieldsets are correctly wrapped around form fields and that the `aria-describedby` attribute is
            properly set to reference the help text for each field. Also checks that the help text is correctly rendered
            with a `div` element of class `helptext`.

            The test covers different scenarios, including the use of auto-generated IDs and custom ID prefixes.

            :note: The test case assumes that the form fields are correctly defined and that the help text is provided for each field.
            :see: :class:`FieldsetForm` for the form definition used in this test case.```
        """
        class FieldsetForm(Form):
            checkbox = MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=CheckboxSelectMultiple,
                help_text="Checkbox help text",
            )
            radio = MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=RadioSelect,
                help_text="Radio help text",
            )
            datetime = SplitDateTimeField(help_text="Enter Date and Time")

        f = FieldsetForm()
        self.assertHTMLEqual(
            str(f),
            '<div><fieldset aria-describedby="id_checkbox_helptext">'
            "<legend>Checkbox:</legend>"
            '<div class="helptext" id="id_checkbox_helptext">Checkbox help text</div>'
            '<div id="id_checkbox"><div>'
            '<label for="id_checkbox_0"><input type="checkbox" name="checkbox" '
            'value="a" id="id_checkbox_0" /> A</label>'
            "</div><div>"
            '<label for="id_checkbox_1"><input type="checkbox" name="checkbox" '
            'value="b" id="id_checkbox_1" /> B</label>'
            "</div></div></fieldset></div>"
            '<div><fieldset aria-describedby="id_radio_helptext">'
            "<legend>Radio:</legend>"
            '<div class="helptext" id="id_radio_helptext">Radio help text</div>'
            '<div id="id_radio"><div>'
            '<label for="id_radio_0"><input type="radio" name="radio" value="a" '
            'required id="id_radio_0" />A</label>'
            "</div><div>"
            '<label for="id_radio_1"><input type="radio" name="radio" value="b" '
            'required id="id_radio_1" /> B</label>'
            "</div></div></fieldset></div>"
            '<div><fieldset aria-describedby="id_datetime_helptext">'
            "<legend>Datetime:</legend>"
            '<div class="helptext" id="id_datetime_helptext">Enter Date and Time</div>'
            '<input type="text" name="datetime_0" required id="id_datetime_0" />'
            '<input type="text" name="datetime_1" required id="id_datetime_1" />'
            "</fieldset></div>",
        )
        f = FieldsetForm(auto_id=False)
        # aria-describedby is not included.
        self.assertIn("<fieldset>", str(f))
        self.assertIn('<div class="helptext">', str(f))
        f = FieldsetForm(auto_id="custom_%s")
        # aria-describedby uses custom auto_id.
        self.assertIn('fieldset aria-describedby="custom_checkbox_helptext"', str(f))
        self.assertIn('<div class="helptext" id="custom_checkbox_helptext">', str(f))

    def test_fieldset_custom_aria_describedby(self):
        # aria-describedby set on widget results in aria-describedby being
        # added to widget and not the <fieldset>.
        """
        #: Tests the rendering of a fieldset with a custom aria-describedby attribute.
        #: 
        #: This test case verifies that a fieldset containing a checkbox form field with
        #: a custom aria-describedby attribute is rendered correctly. The fieldset should
        #: include a legend, a help text section, and the checkbox inputs with the
        #: specified aria-describedby attribute. The test ensures that the rendered HTML
        #: matches the expected output, including the correct ids, classes, and attribute
        #: values.
        """
        class FieldsetForm(Form):
            checkbox = MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=CheckboxSelectMultiple(attrs={"aria-describedby": "custom-id"}),
                help_text="Checkbox help text",
            )

        f = FieldsetForm()
        self.assertHTMLEqual(
            str(f),
            "<div><fieldset><legend>Checkbox:</legend>"
            '<div class="helptext" id="id_checkbox_helptext">Checkbox help text</div>'
            '<div id="id_checkbox"><div>'
            '<label for="id_checkbox_0"><input type="checkbox" name="checkbox" '
            'value="a" aria-describedby="custom-id" id="id_checkbox_0" />A</label>'
            "</div><div>"
            '<label for="id_checkbox_1"><input type="checkbox" name="checkbox" '
            'value="b" aria-describedby="custom-id" id="id_checkbox_1" />B</label>'
            "</div></div></fieldset></div>",
        )

    def test_as_widget_custom_aria_describedby(self):
        class FoodForm(Form):
            intl_name = CharField(help_text="The food's international name.")

        form = FoodForm({"intl_name": "Rendang"})
        self.assertHTMLEqual(
            form["intl_name"].as_widget(attrs={"aria-describedby": "some_custom_id"}),
            '<input type="text" name="intl_name" value="Rendang"'
            'aria-describedby="some_custom_id" required id="id_intl_name">',
        )

    def test_subclassing_forms(self):
        # You can subclass a Form to add fields. The resulting form subclass will have
        # all of the fields of the parent Form, plus whichever fields you define in the
        # subclass.
        """
        Tests the functionality of subclassing forms, ensuring that fields from parent classes are correctly inherited and rendered in the resulting HTML.

         The test covers both single and multiple inheritance scenarios, verifying that the order and presence of fields in the subclass match the expected output.

         It checks the HTML output of the form when rendered as an unordered list using the `as_ul()` method, comparing it to the expected HTML string.
        """
        class Person(Form):
            first_name = CharField()
            last_name = CharField()
            birthday = DateField()

        class Musician(Person):
            instrument = CharField()

        p = Person(auto_id=False)
        self.assertHTMLEqual(
            p.as_ul(),
            """<li>First name: <input type="text" name="first_name" required></li>
<li>Last name: <input type="text" name="last_name" required></li>
<li>Birthday: <input type="text" name="birthday" required></li>""",
        )
        m = Musician(auto_id=False)
        self.assertHTMLEqual(
            m.as_ul(),
            """<li>First name: <input type="text" name="first_name" required></li>
<li>Last name: <input type="text" name="last_name" required></li>
<li>Birthday: <input type="text" name="birthday" required></li>
<li>Instrument: <input type="text" name="instrument" required></li>""",
        )

        # Yes, you can subclass multiple forms. The fields are added in the order in
        # which the parent classes are listed.
        class Person(Form):
            first_name = CharField()
            last_name = CharField()
            birthday = DateField()

        class Instrument(Form):
            instrument = CharField()

        class Beatle(Person, Instrument):
            haircut_type = CharField()

        b = Beatle(auto_id=False)
        self.assertHTMLEqual(
            b.as_ul(),
            """<li>Instrument: <input type="text" name="instrument" required></li>
<li>First name: <input type="text" name="first_name" required></li>
<li>Last name: <input type="text" name="last_name" required></li>
<li>Birthday: <input type="text" name="birthday" required></li>
<li>Haircut type: <input type="text" name="haircut_type" required></li>""",
        )

    def test_forms_with_prefixes(self):
        # Sometimes it's necessary to have multiple forms display on the same
        # HTML page, or multiple copies of the same form. We can accomplish
        # this with form prefixes. Pass the keyword argument 'prefix' to the
        # Form constructor to use this feature. This value will be prepended to
        # each HTML form field name. One way to think about this is "namespaces
        # for HTML forms". Notice that in the data argument, each field's key
        # has the prefix, in this case 'person1', prepended to the actual field
        # name.
        """
        Tests the behavior of Django forms with prefixes, including rendering, validation, and field access.

            The test suite covers various scenarios, such as:

            * Creating a form with a prefix and verifying its HTML representation
            * Validating a form with a prefix and checking its cleaned data
            * Testing form validation with empty fields and custom prefixing logic
            * Creating multiple forms with different prefixes from the same data dictionary
            * Overriding the default prefixing behavior with a custom `add_prefix` method

            The test methods verify the expected output, errors, and cleaned data for each scenario.
        """
        class Person(Form):
            first_name = CharField()
            last_name = CharField()
            birthday = DateField()

        data = {
            "person1-first_name": "John",
            "person1-last_name": "Lennon",
            "person1-birthday": "1940-10-9",
        }
        p = Person(data, prefix="person1")
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li><label for="id_person1-first_name">First name:</label>
            <input type="text" name="person1-first_name" value="John"
                id="id_person1-first_name" required></li>
            <li><label for="id_person1-last_name">Last name:</label>
            <input type="text" name="person1-last_name" value="Lennon"
                id="id_person1-last_name" required></li>
            <li><label for="id_person1-birthday">Birthday:</label>
            <input type="text" name="person1-birthday" value="1940-10-9"
                id="id_person1-birthday" required></li>
            """,
        )
        self.assertHTMLEqual(
            str(p["first_name"]),
            '<input type="text" name="person1-first_name" value="John" '
            'id="id_person1-first_name" required>',
        )
        self.assertHTMLEqual(
            str(p["last_name"]),
            '<input type="text" name="person1-last_name" value="Lennon" '
            'id="id_person1-last_name" required>',
        )
        self.assertHTMLEqual(
            str(p["birthday"]),
            '<input type="text" name="person1-birthday" value="1940-10-9" '
            'id="id_person1-birthday" required>',
        )
        self.assertEqual(p.errors, {})
        self.assertTrue(p.is_valid())
        self.assertEqual(p.cleaned_data["first_name"], "John")
        self.assertEqual(p.cleaned_data["last_name"], "Lennon")
        self.assertEqual(p.cleaned_data["birthday"], datetime.date(1940, 10, 9))

        # Let's try submitting some bad data to make sure form.errors and field.errors
        # work as expected.
        data = {
            "person1-first_name": "",
            "person1-last_name": "",
            "person1-birthday": "",
        }
        p = Person(data, prefix="person1")
        self.assertEqual(p.errors["first_name"], ["This field is required."])
        self.assertEqual(p.errors["last_name"], ["This field is required."])
        self.assertEqual(p.errors["birthday"], ["This field is required."])
        self.assertEqual(p["first_name"].errors, ["This field is required."])
        # Accessing a nonexistent field.
        with self.assertRaises(KeyError):
            p["person1-first_name"].errors

        # In this example, the data doesn't have a prefix, but the form requires it, so
        # the form doesn't "see" the fields.
        data = {"first_name": "John", "last_name": "Lennon", "birthday": "1940-10-9"}
        p = Person(data, prefix="person1")
        self.assertEqual(p.errors["first_name"], ["This field is required."])
        self.assertEqual(p.errors["last_name"], ["This field is required."])
        self.assertEqual(p.errors["birthday"], ["This field is required."])

        # With prefixes, a single data dictionary can hold data for multiple instances
        # of the same form.
        data = {
            "person1-first_name": "John",
            "person1-last_name": "Lennon",
            "person1-birthday": "1940-10-9",
            "person2-first_name": "Jim",
            "person2-last_name": "Morrison",
            "person2-birthday": "1943-12-8",
        }
        p1 = Person(data, prefix="person1")
        self.assertTrue(p1.is_valid())
        self.assertEqual(p1.cleaned_data["first_name"], "John")
        self.assertEqual(p1.cleaned_data["last_name"], "Lennon")
        self.assertEqual(p1.cleaned_data["birthday"], datetime.date(1940, 10, 9))
        p2 = Person(data, prefix="person2")
        self.assertTrue(p2.is_valid())
        self.assertEqual(p2.cleaned_data["first_name"], "Jim")
        self.assertEqual(p2.cleaned_data["last_name"], "Morrison")
        self.assertEqual(p2.cleaned_data["birthday"], datetime.date(1943, 12, 8))

        # By default, forms append a hyphen between the prefix and the field name, but a
        # form can alter that behavior by implementing the add_prefix() method. This
        # method takes a field name and returns the prefixed field, according to
        # self.prefix.
        class Person(Form):
            first_name = CharField()
            last_name = CharField()
            birthday = DateField()

            def add_prefix(self, field_name):
                return (
                    "%s-prefix-%s" % (self.prefix, field_name)
                    if self.prefix
                    else field_name
                )

        p = Person(prefix="foo")
        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li><label for="id_foo-prefix-first_name">First name:</label>
            <input type="text" name="foo-prefix-first_name"
                id="id_foo-prefix-first_name" required></li>
            <li><label for="id_foo-prefix-last_name">Last name:</label>
            <input type="text" name="foo-prefix-last_name" id="id_foo-prefix-last_name"
                required></li>
            <li><label for="id_foo-prefix-birthday">Birthday:</label>
            <input type="text" name="foo-prefix-birthday" id="id_foo-prefix-birthday"
                required></li>
            """,
        )
        data = {
            "foo-prefix-first_name": "John",
            "foo-prefix-last_name": "Lennon",
            "foo-prefix-birthday": "1940-10-9",
        }
        p = Person(data, prefix="foo")
        self.assertTrue(p.is_valid())
        self.assertEqual(p.cleaned_data["first_name"], "John")
        self.assertEqual(p.cleaned_data["last_name"], "Lennon")
        self.assertEqual(p.cleaned_data["birthday"], datetime.date(1940, 10, 9))

    def test_class_prefix(self):
        # Prefix can be also specified at the class level.
        class Person(Form):
            first_name = CharField()
            prefix = "foo"

        p = Person()
        self.assertEqual(p.prefix, "foo")

        p = Person(prefix="bar")
        self.assertEqual(p.prefix, "bar")

    def test_forms_with_null_boolean(self):
        # NullBooleanField is a bit of a special case because its presentation (widget)
        # is different than its data. This is handled transparently, though.
        class Person(Form):
            name = CharField()
            is_cool = NullBooleanField()

        p = Person({"name": "Joe"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown" selected>Unknown</option>
<option value="true">Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "1"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown" selected>Unknown</option>
<option value="true">Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "2"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true" selected>Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "3"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true">Yes</option>
<option value="false" selected>No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": True}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true" selected>Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": False}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true">Yes</option>
<option value="false" selected>No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "unknown"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown" selected>Unknown</option>
<option value="true">Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "true"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true" selected>Yes</option>
<option value="false">No</option>
</select>""",
        )
        p = Person({"name": "Joe", "is_cool": "false"}, auto_id=False)
        self.assertHTMLEqual(
            str(p["is_cool"]),
            """<select name="is_cool">
<option value="unknown">Unknown</option>
<option value="true">Yes</option>
<option value="false" selected>No</option>
</select>""",
        )

    def test_forms_with_file_fields(self):
        # FileFields are a special case because they take their data from the
        # request.FILES, not request.POST.
        class FileForm(Form):
            file1 = FileField()

        f = FileForm(auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<input type="file" name="file1" required></td></tr>',
        )

        f = FileForm(data={}, files={}, auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="file" name="file1" aria-invalid="true" required></td></tr>',
        )

        f = FileForm(
            data={}, files={"file1": SimpleUploadedFile("name", b"")}, auto_id=False
        )
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<ul class="errorlist"><li>The submitted file is empty.</li></ul>'
            '<input type="file" name="file1" aria-invalid="true" required></td></tr>',
        )

        f = FileForm(
            data={}, files={"file1": "something that is not a file"}, auto_id=False
        )
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<ul class="errorlist"><li>No file was submitted. Check the '
            "encoding type on the form.</li></ul>"
            '<input type="file" name="file1" aria-invalid="true" required></td></tr>',
        )

        f = FileForm(
            data={},
            files={"file1": SimpleUploadedFile("name", b"some content")},
            auto_id=False,
        )
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<input type="file" name="file1" required></td></tr>',
        )
        self.assertTrue(f.is_valid())

        file1 = SimpleUploadedFile(
            "我隻氣墊船裝滿晒鱔.txt", "मेरी मँडराने वाली नाव सर्पमीनों से भरी ह".encode()
        )
        f = FileForm(data={}, files={"file1": file1}, auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<input type="file" name="file1" required></td></tr>',
        )

        # A required file field with initial data should not contain the
        # required HTML attribute. The file input is left blank by the user to
        # keep the existing, initial value.
        f = FileForm(initial={"file1": "resume.txt"}, auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><th>File1:</th><td><input type="file" name="file1"></td></tr>',
        )

    def test_filefield_initial_callable(self):
        class FileForm(Form):
            file1 = FileField(initial=lambda: "resume.txt")

        f = FileForm({})
        self.assertEqual(f.errors, {})
        self.assertEqual(f.cleaned_data["file1"], "resume.txt")

    def test_filefield_with_fileinput_required(self):
        class FileForm(Form):
            file1 = FileField(widget=FileInput)

        f = FileForm(auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            "<tr><th>File1:</th><td>"
            '<input type="file" name="file1" required></td></tr>',
        )
        # A required file field with initial data doesn't contain the required
        # HTML attribute. The file input is left blank by the user to keep the
        # existing, initial value.
        f = FileForm(initial={"file1": "resume.txt"}, auto_id=False)
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><th>File1:</th><td><input type="file" name="file1"></td></tr>',
        )

    def test_empty_permitted(self):
        # Sometimes (pretty much in formsets) we want to allow a form to pass validation
        # if it is completely empty. We can accomplish this by using the empty_permitted
        # argument to a form constructor.
        """

        Tests the behavior of form validation with respect to empty permitted fields.

        This test case checks how forms with empty fields are validated under different 
        settings of the `empty_permitted` parameter. It covers scenarios where the form 
        has required fields with no data, as well as when the `use_required_attribute` 
        flag is set to False. It ensures that form validity and error messages are 
        correctly determined based on these settings.

        The test verifies that when `empty_permitted` is False, empty fields trigger 
        validation errors. Conversely, when `empty_permitted` is True, empty fields do 
        not trigger errors, allowing the form to be considered valid even with missing 
        data. The behavior is tested for both CharFields and numeric fields like FloatField 
        and IntegerField.

        The test also checks the `cleaned_data` attribute to ensure it is populated 
        correctly according to the form's validity and the `empty_permitted` setting.

        """
        class SongForm(Form):
            artist = CharField()
            name = CharField()

        # First let's show what happens id empty_permitted=False (the default):
        data = {"artist": "", "song": ""}
        form = SongForm(data, empty_permitted=False)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "name": ["This field is required."],
                "artist": ["This field is required."],
            },
        )
        self.assertEqual(form.cleaned_data, {})

        # Now let's show what happens when empty_permitted=True and the form is empty.
        form = SongForm(data, empty_permitted=True, use_required_attribute=False)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.errors, {})
        self.assertEqual(form.cleaned_data, {})

        # But if we fill in data for one of the fields, the form is no longer empty and
        # the whole thing must pass validation.
        data = {"artist": "The Doors", "song": ""}
        form = SongForm(data, empty_permitted=False)
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"name": ["This field is required."]})
        self.assertEqual(form.cleaned_data, {"artist": "The Doors"})

        # If a field is not given in the data then None is returned for its data. Lets
        # make sure that when checking for empty_permitted that None is treated
        # accordingly.
        data = {"artist": None, "song": ""}
        form = SongForm(data, empty_permitted=True, use_required_attribute=False)
        self.assertTrue(form.is_valid())

        # However, we *really* need to be sure we are checking for None as any data in
        # initial that returns False on a boolean call needs to be treated literally.
        class PriceForm(Form):
            amount = FloatField()
            qty = IntegerField()

        data = {"amount": "0.0", "qty": ""}
        form = PriceForm(
            data,
            initial={"amount": 0.0},
            empty_permitted=True,
            use_required_attribute=False,
        )
        self.assertTrue(form.is_valid())

    def test_empty_permitted_and_use_required_attribute(self):
        msg = (
            "The empty_permitted and use_required_attribute arguments may not "
            "both be True."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Person(empty_permitted=True, use_required_attribute=True)

    def test_extracting_hidden_and_visible(self):
        """
        Tests the ability to extract hidden and visible fields from a form.

        This test case verifies that the :meth:`hidden_fields` and :meth:`visible_fields`
        methods correctly identify and return the respective fields based on their widget type.
        In this context, hidden fields are those that use the :class:`HiddenInput` widget, while
        visible fields use other widget types.

        The test creates a sample form with a mix of hidden and visible fields, then checks that
        the correct fields are returned by each method. This ensures that the form's field
        visibility is properly determined and reported.

        """
        class SongForm(Form):
            token = CharField(widget=HiddenInput)
            artist = CharField()
            name = CharField()

        form = SongForm()
        self.assertEqual([f.name for f in form.hidden_fields()], ["token"])
        self.assertEqual([f.name for f in form.visible_fields()], ["artist", "name"])

    def test_hidden_initial_gets_id(self):
        """
        Tests that a form field with `show_hidden_initial=True` correctly renders both the visible form input and a hidden input containing the initial value, with the hidden input having an ID that matches the pattern 'initial-id_fieldname'. This ensures that the initial value of the field is preserved and can be accessed via JavaScript or other means, even after the user has modified the visible input.
        """
        class MyForm(Form):
            field1 = CharField(max_length=50, show_hidden_initial=True)

        self.assertHTMLEqual(
            MyForm().as_table(),
            '<tr><th><label for="id_field1">Field1:</label></th><td>'
            '<input id="id_field1" type="text" name="field1" maxlength="50" required>'
            '<input type="hidden" name="initial-field1" id="initial-id_field1">'
            "</td></tr>",
        )

    def test_error_html_required_html_classes(self):
        """
        Tests the HTML representation of a form when required fields are not filled in, 
        ensuring the correct HTML classes are applied to indicate errors and required fields. 

        Specifically, this test checks that the 'error' and 'required' CSS classes are 
        correctly added to form fields and their associated HTML elements when errors occur, 
        across different form rendering formats (unordered list, paragraph, table, and div).
        """
        class Person(Form):
            name = CharField()
            is_cool = NullBooleanField()
            email = EmailField(required=False)
            age = IntegerField()

        p = Person({})
        p.error_css_class = "error"
        p.required_css_class = "required"

        self.assertHTMLEqual(
            p.as_ul(),
            """
            <li class="required error"><ul class="errorlist">
            <li>This field is required.</li></ul>
            <label class="required" for="id_name">Name:</label>
            <input type="text" name="name" id="id_name" aria-invalid="true" required>
            </li><li class="required">
            <label class="required" for="id_is_cool">Is cool:</label>
            <select name="is_cool" id="id_is_cool">
            <option value="unknown" selected>Unknown</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
            </select></li>
            <li><label for="id_email">Email:</label>
            <input type="email" name="email" id="id_email" maxlength="320"></li>
            <li class="required error"><ul class="errorlist">
            <li>This field is required.</li></ul>
            <label class="required" for="id_age">Age:</label>
            <input type="number" name="age" id="id_age" aria-invalid="true" required>
            </li>""",
        )

        self.assertHTMLEqual(
            p.as_p(),
            """
            <ul class="errorlist"><li>This field is required.</li></ul>
            <p class="required error">
            <label class="required" for="id_name">Name:</label>
            <input type="text" name="name" id="id_name" aria-invalid="true" required>
            </p><p class="required">
            <label class="required" for="id_is_cool">Is cool:</label>
            <select name="is_cool" id="id_is_cool">
            <option value="unknown" selected>Unknown</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
            </select></p>
            <p><label for="id_email">Email:</label>
            <input type="email" name="email" id="id_email" maxlength="320"></p>
            <ul class="errorlist"><li>This field is required.</li></ul>
            <p class="required error"><label class="required" for="id_age">Age:</label>
            <input type="number" name="age" id="id_age" aria-invalid="true" required>
            </p>""",
        )

        self.assertHTMLEqual(
            p.as_table(),
            """<tr class="required error">
<th><label class="required" for="id_name">Name:</label></th>
<td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="text" name="name" id="id_name" aria-invalid="true" required></td></tr>
<tr class="required"><th><label class="required" for="id_is_cool">Is cool:</label></th>
<td><select name="is_cool" id="id_is_cool">
<option value="unknown" selected>Unknown</option>
<option value="true">Yes</option>
<option value="false">No</option>
</select></td></tr>
<tr><th><label for="id_email">Email:</label></th><td>
<input type="email" name="email" id="id_email" maxlength="320"></td></tr>
<tr class="required error"><th><label class="required" for="id_age">Age:</label></th>
<td><ul class="errorlist"><li>This field is required.</li></ul>
<input type="number" name="age" id="id_age" aria-invalid="true" required></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<div class="required error"><label for="id_name" class="required">Name:'
            '</label><ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="text" name="name" required id="id_name" '
            'aria-invalid="true" /></div>'
            '<div class="required"><label for="id_is_cool" class="required">Is cool:'
            '</label><select name="is_cool" id="id_is_cool">'
            '<option value="unknown" selected>Unknown</option>'
            '<option value="true">Yes</option><option value="false">No</option>'
            '</select></div><div><label for="id_email">Email:</label>'
            '<input type="email" name="email" id="id_email" maxlength="320"/></div>'
            '<div class="required error"><label for="id_age" class="required">Age:'
            '</label><ul class="errorlist"><li>This field is required.</li></ul>'
            '<input type="number" name="age" required id="id_age" '
            'aria-invalid="true" /></div>',
        )

    def test_label_has_required_css_class(self):
        """
        required_css_class is added to label_tag() and legend_tag() of required
        fields.
        """

        class SomeForm(Form):
            required_css_class = "required"
            field = CharField(max_length=10)
            field2 = IntegerField(required=False)

        f = SomeForm({"field": "test"})
        self.assertHTMLEqual(
            f["field"].label_tag(),
            '<label for="id_field" class="required">Field:</label>',
        )
        self.assertHTMLEqual(
            f["field"].legend_tag(),
            '<legend for="id_field" class="required">Field:</legend>',
        )
        self.assertHTMLEqual(
            f["field"].label_tag(attrs={"class": "foo"}),
            '<label for="id_field" class="foo required">Field:</label>',
        )
        self.assertHTMLEqual(
            f["field"].legend_tag(attrs={"class": "foo"}),
            '<legend for="id_field" class="foo required">Field:</legend>',
        )
        self.assertHTMLEqual(
            f["field2"].label_tag(), '<label for="id_field2">Field2:</label>'
        )
        self.assertHTMLEqual(
            f["field2"].legend_tag(),
            '<legend for="id_field2">Field2:</legend>',
        )

    def test_label_split_datetime_not_displayed(self):
        """
        Tests that the label for a SplitDateTimeField is not displayed when using the SplitHiddenDateTimeWidget. 

        This test ensures that when a form field uses a SplitDateTimeField with a SplitHiddenDateTimeWidget, only the hidden input fields are rendered, without displaying the label for the datetime field. The expected output is a set of hidden input fields for the date and time components of the datetime field.
        """
        class EventForm(Form):
            happened_at = SplitDateTimeField(widget=SplitHiddenDateTimeWidget)

        form = EventForm()
        self.assertHTMLEqual(
            form.as_ul(),
            '<input type="hidden" name="happened_at_0" id="id_happened_at_0">'
            '<input type="hidden" name="happened_at_1" id="id_happened_at_1">',
        )

    def test_multivalue_field_validation(self):
        """
        Tests the validation of a multivalue field, specifically a `NameField` that consists of two `CharField` instances for first and last names. 
        The test checks that the field raises a `ValidationError` when a specific disallowed value is provided, 
        and that it enforces the maximum length constraint on each sub-field.
        It also verifies that valid input results in the field's values being properly cleaned and compressed into a single string.
        """
        def bad_names(value):
            if value == "bad value":
                raise ValidationError("bad value not allowed")

        class NameField(MultiValueField):
            def __init__(self, fields=(), *args, **kwargs):
                fields = (
                    CharField(label="First name", max_length=10),
                    CharField(label="Last name", max_length=10),
                )
                super().__init__(fields=fields, *args, **kwargs)

            def compress(self, data_list):
                return " ".join(data_list)

        class NameForm(Form):
            name = NameField(validators=[bad_names])

        form = NameForm(data={"name": ["bad", "value"]})
        form.full_clean()
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors, {"name": ["bad value not allowed"]})
        form = NameForm(data={"name": ["should be overly", "long for the field names"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "name": [
                    "Ensure this value has at most 10 characters (it has 16).",
                    "Ensure this value has at most 10 characters (it has 24).",
                ],
            },
        )
        form = NameForm(data={"name": ["fname", "lname"]})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {"name": "fname lname"})

    def test_multivalue_deep_copy(self):
        """
        #19298 -- MultiValueField needs to override the default as it needs
        to deep-copy subfields:
        """

        class ChoicesField(MultiValueField):
            def __init__(self, fields=(), *args, **kwargs):
                """
                Initialize a new instance of the class.

                This constructor sets up the fields for a form, including a 'Rank' choice field with two options (1 and 2)
                and a 'Name' character field with a maximum length of 10 characters.

                The :param fields: argument is overridden to include these required fields.
                Any additional positional arguments (:param args:) and keyword arguments (:param kwargs:) are passed to the parent class constructor.

                This class is designed to be used as a base for creating forms that require a rank and name input.

                """
                fields = (
                    ChoiceField(label="Rank", choices=((1, 1), (2, 2))),
                    CharField(label="Name", max_length=10),
                )
                super().__init__(fields=fields, *args, **kwargs)

        field = ChoicesField()
        field2 = copy.deepcopy(field)
        self.assertIsInstance(field2, ChoicesField)
        self.assertIsNot(field2.fields, field.fields)
        self.assertIsNot(field2.fields[0].choices, field.fields[0].choices)

    def test_multivalue_initial_data(self):
        """
        #23674 -- invalid initial data should not break form.changed_data()
        """

        class DateAgeField(MultiValueField):
            def __init__(self, fields=(), *args, **kwargs):
                """
                Initializes a new instance of the class, setting up a predefined set of form fields.

                The fields are fixed to include a 'Date' field and an 'Age' field, which are used to capture date and integer values respectively. 

                Any additional arguments passed to the constructor are forwarded to the parent class for further processing.
                """
                fields = (DateField(label="Date"), IntegerField(label="Age"))
                super().__init__(fields=fields, *args, **kwargs)

        class DateAgeForm(Form):
            date_age = DateAgeField()

        data = {"date_age": ["1998-12-06", 16]}
        form = DateAgeForm(data, initial={"date_age": ["200-10-10", 14]})
        self.assertTrue(form.has_changed())

    def test_multivalue_optional_subfields(self):
        """
        Tests a MultiValueField subclass (PhoneField) for handling phone number information. 
        The field is composed of four subfields: Country Code, Phone Number, Extension, and Label. 
        Country Code must be a valid code with a plus sign followed by 1 to 2 digits. The extension and label fields are not required for the field to be considered valid. 
        The test checks that the field behaves correctly when required, and when not required, including error cases such as missing or invalid input for specific subfields. 
        Additionally, it verifies that the field correctly handles combinations of required and optional subfields, and that it raises the expected ValidationErrors for different types of invalid input.
        """
        class PhoneField(MultiValueField):
            def __init__(self, *args, **kwargs):
                fields = (
                    CharField(
                        label="Country Code",
                        validators=[
                            RegexValidator(
                                r"^\+[0-9]{1,2}$", message="Enter a valid country code."
                            )
                        ],
                    ),
                    CharField(label="Phone Number"),
                    CharField(
                        label="Extension",
                        error_messages={"incomplete": "Enter an extension."},
                    ),
                    CharField(
                        label="Label", required=False, help_text="E.g. home, work."
                    ),
                )
                super().__init__(fields, *args, **kwargs)

            def compress(self, data_list):
                if data_list:
                    return "%s.%s ext. %s (label: %s)" % tuple(data_list)
                return None

        # An empty value for any field will raise a `required` error on a
        # required `MultiValueField`.
        f = PhoneField()
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean([])
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(["+61"])
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(["+61", "287654321", "123"])
        self.assertEqual(
            "+61.287654321 ext. 123 (label: Home)",
            f.clean(["+61", "287654321", "123", "Home"]),
        )
        with self.assertRaisesMessage(ValidationError, "'Enter a valid country code.'"):
            f.clean(["61", "287654321", "123", "Home"])

        # Empty values for fields will NOT raise a `required` error on an
        # optional `MultiValueField`
        f = PhoneField(required=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
        self.assertIsNone(f.clean([]))
        self.assertEqual("+61. ext.  (label: )", f.clean(["+61"]))
        self.assertEqual(
            "+61.287654321 ext. 123 (label: )", f.clean(["+61", "287654321", "123"])
        )
        self.assertEqual(
            "+61.287654321 ext. 123 (label: Home)",
            f.clean(["+61", "287654321", "123", "Home"]),
        )
        with self.assertRaisesMessage(ValidationError, "'Enter a valid country code.'"):
            f.clean(["61", "287654321", "123", "Home"])

        # For a required `MultiValueField` with `require_all_fields=False`, a
        # `required` error will only be raised if all fields are empty. Fields
        # can individually be required or optional. An empty value for any
        # required field will raise an `incomplete` error.
        f = PhoneField(require_all_fields=False)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean("")
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean(None)
        with self.assertRaisesMessage(ValidationError, "'This field is required.'"):
            f.clean([])
        with self.assertRaisesMessage(ValidationError, "'Enter a complete value.'"):
            f.clean(["+61"])
        self.assertEqual(
            "+61.287654321 ext. 123 (label: )", f.clean(["+61", "287654321", "123"])
        )
        with self.assertRaisesMessage(
            ValidationError, "'Enter a complete value.', 'Enter an extension.'"
        ):
            f.clean(["", "", "", "Home"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid country code.'"):
            f.clean(["61", "287654321", "123", "Home"])

        # For an optional `MultiValueField` with `require_all_fields=False`, we
        # don't get any `required` error but we still get `incomplete` errors.
        f = PhoneField(required=False, require_all_fields=False)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
        self.assertIsNone(f.clean([]))
        with self.assertRaisesMessage(ValidationError, "'Enter a complete value.'"):
            f.clean(["+61"])
        self.assertEqual(
            "+61.287654321 ext. 123 (label: )", f.clean(["+61", "287654321", "123"])
        )
        with self.assertRaisesMessage(
            ValidationError, "'Enter a complete value.', 'Enter an extension.'"
        ):
            f.clean(["", "", "", "Home"])
        with self.assertRaisesMessage(ValidationError, "'Enter a valid country code.'"):
            f.clean(["61", "287654321", "123", "Home"])

    def test_multivalue_optional_subfields_rendering(self):
        """
        Tests the rendering of multi-value optional subfields using the PhoneWidget and PhoneField classes.

        The test case covers various scenarios, including required and non-required fields, with and without the requirement for all subfields to be filled.

        Verifies that the as_p() method of the PhoneForm instance produces the expected HTML output, including the correct rendering of input fields and their respective attributes.
        """
        class PhoneWidget(MultiWidget):
            def __init__(self, attrs=None):
                """
                Initializes a form instance with text input widgets.

                Args:
                    attrs (dict, optional): Attributes to apply to the form. Defaults to None.

                This constructor sets up a form with two text input fields, providing a basic 
                structure for user data collection. Custom attributes can be passed to further 
                configure the form's appearance and behavior.
                """
                widgets = [TextInput(), TextInput()]
                super().__init__(widgets, attrs)

            def decompress(self, value):
                return [None, None]

        class PhoneField(MultiValueField):
            def __init__(self, *args, **kwargs):
                fields = [CharField(), CharField(required=False)]
                super().__init__(fields, *args, **kwargs)

        class PhoneForm(Form):
            phone1 = PhoneField(widget=PhoneWidget)
            phone2 = PhoneField(widget=PhoneWidget, required=False)
            phone3 = PhoneField(widget=PhoneWidget, require_all_fields=False)
            phone4 = PhoneField(
                widget=PhoneWidget,
                required=False,
                require_all_fields=False,
            )

        form = PhoneForm(auto_id=False)
        self.assertHTMLEqual(
            form.as_p(),
            """
            <p>Phone1:<input type="text" name="phone1_0" required>
            <input type="text" name="phone1_1" required></p>
            <p>Phone2:<input type="text" name="phone2_0">
            <input type="text" name="phone2_1"></p>
            <p>Phone3:<input type="text" name="phone3_0" required>
            <input type="text" name="phone3_1"></p>
            <p>Phone4:<input type="text" name="phone4_0">
            <input type="text" name="phone4_1"></p>
            """,
        )

    def test_custom_empty_values(self):
        """
        Form fields can customize what is considered as an empty value
        for themselves (#19997).
        """

        class CustomJSONField(CharField):
            empty_values = [None, ""]

            def to_python(self, value):
                # Fake json.loads
                if value == "{}":
                    return {}
                return super().to_python(value)

        class JSONForm(Form):
            json = CustomJSONField()

        form = JSONForm(data={"json": "{}"})
        form.full_clean()
        self.assertEqual(form.cleaned_data, {"json": {}})

    def test_boundfield_label_tag(self):
        """

        Tests the functionality of the label_tag and legend_tag methods of a BoundField instance.

        This test case covers various scenarios, including rendering the label with default and custom text,
        handling HTML special characters in the label text, and applying additional HTML attributes to the label tag.

        The test verifies that the generated HTML output for both the label and legend tags matches the expected
        results, ensuring that the BoundField instance correctly handles different input parameters and settings.

        """
        class SomeForm(Form):
            field = CharField()

        boundfield = SomeForm()["field"]

        testcases = [  # (args, kwargs, expected)
            # without anything: just print the <label>
            ((), {}, '<%(tag)s for="id_field">Field:</%(tag)s>'),
            # passing just one argument: overrides the field's label
            (("custom",), {}, '<%(tag)s for="id_field">custom:</%(tag)s>'),
            # the overridden label is escaped
            (("custom&",), {}, '<%(tag)s for="id_field">custom&amp;:</%(tag)s>'),
            ((mark_safe("custom&"),), {}, '<%(tag)s for="id_field">custom&:</%(tag)s>'),
            # Passing attrs to add extra attributes on the <label>
            (
                (),
                {"attrs": {"class": "pretty"}},
                '<%(tag)s for="id_field" class="pretty">Field:</%(tag)s>',
            ),
        ]

        for args, kwargs, expected in testcases:
            with self.subTest(args=args, kwargs=kwargs):
                self.assertHTMLEqual(
                    boundfield.label_tag(*args, **kwargs),
                    expected % {"tag": "label"},
                )
                self.assertHTMLEqual(
                    boundfield.legend_tag(*args, **kwargs),
                    expected % {"tag": "legend"},
                )

    def test_boundfield_label_tag_no_id(self):
        """
        If a widget has no id, label_tag() and legend_tag() return the text
        with no surrounding <label>.
        """

        class SomeForm(Form):
            field = CharField()

        boundfield = SomeForm(auto_id="")["field"]

        self.assertHTMLEqual(boundfield.label_tag(), "Field:")
        self.assertHTMLEqual(boundfield.legend_tag(), "Field:")
        self.assertHTMLEqual(boundfield.label_tag("Custom&"), "Custom&amp;:")
        self.assertHTMLEqual(boundfield.legend_tag("Custom&"), "Custom&amp;:")

    def test_boundfield_label_tag_custom_widget_id_for_label(self):
        """
        Tests the rendering of BoundField label tags with custom widgets that override the id_for_label method.

        Checks that the label and legend tags are correctly generated when the widget's id_for_label method returns a custom id or None.

        The test covers two scenarios: 
        - a widget that prefixes the id with a custom string
        - a widget that returns None, resulting in no 'for' attribute in the label and legend tags.

        Verifies that the resulting HTML is as expected in both cases, ensuring proper rendering of form fields with custom widget configurations.
        """
        class CustomIdForLabelTextInput(TextInput):
            def id_for_label(self, id):
                return "custom_" + id

        class EmptyIdForLabelTextInput(TextInput):
            def id_for_label(self, id):
                return None

        class SomeForm(Form):
            custom = CharField(widget=CustomIdForLabelTextInput)
            empty = CharField(widget=EmptyIdForLabelTextInput)

        form = SomeForm()
        self.assertHTMLEqual(
            form["custom"].label_tag(), '<label for="custom_id_custom">Custom:</label>'
        )
        self.assertHTMLEqual(
            form["custom"].legend_tag(),
            '<legend for="custom_id_custom">Custom:</legend>',
        )
        self.assertHTMLEqual(form["empty"].label_tag(), "<label>Empty:</label>")
        self.assertHTMLEqual(form["empty"].legend_tag(), "<legend>Empty:</legend>")

    def test_boundfield_empty_label(self):
        """
        Tests that a BoundField creates correct HTML for a field with an empty label.

        This test case ensures that when a form field's label is set to an empty string,
        the corresponding label and legend tags are still rendered correctly in HTML.

        It verifies that the label and legend tags have the correct 'for' attribute,
        even if the label text itself is empty.
        """
        class SomeForm(Form):
            field = CharField(label="")

        boundfield = SomeForm()["field"]

        self.assertHTMLEqual(boundfield.label_tag(), '<label for="id_field"></label>')
        self.assertHTMLEqual(
            boundfield.legend_tag(),
            '<legend for="id_field"></legend>',
        )

    def test_boundfield_id_for_label(self):
        """

        Tests that the id_for_label attribute of a BoundField instance is correctly generated.

        The test case checks that an empty label does not affect the id_for_label attribute, which is expected to be 'id_field'.

        This ensures that the field's id_for_label is properly set, allowing for correct integration with HTML labels.

        """
        class SomeForm(Form):
            field = CharField(label="")

        self.assertEqual(SomeForm()["field"].id_for_label, "id_field")

    def test_boundfield_id_for_label_override_by_attrs(self):
        """
        If an id is provided in `Widget.attrs`, it overrides the generated ID,
        unless it is `None`.
        """

        class SomeForm(Form):
            field = CharField(widget=TextInput(attrs={"id": "myCustomID"}))
            field_none = CharField(widget=TextInput(attrs={"id": None}))

        form = SomeForm()
        self.assertEqual(form["field"].id_for_label, "myCustomID")
        self.assertEqual(form["field_none"].id_for_label, "id_field_none")

    def test_boundfield_subwidget_id_for_label(self):
        """
        If auto_id is provided when initializing the form, the generated ID in
        subwidgets must reflect that prefix.
        """

        class SomeForm(Form):
            field = MultipleChoiceField(
                choices=[("a", "A"), ("b", "B")],
                widget=CheckboxSelectMultiple,
            )

        form = SomeForm(auto_id="prefix_%s")
        subwidgets = form["field"].subwidgets
        self.assertEqual(subwidgets[0].id_for_label, "prefix_field_0")
        self.assertEqual(subwidgets[1].id_for_label, "prefix_field_1")

    def test_boundfield_widget_type(self):
        class SomeForm(Form):
            first_name = CharField()
            birthday = SplitDateTimeField(widget=SplitHiddenDateTimeWidget)

        f = SomeForm()
        self.assertEqual(f["first_name"].widget_type, "text")
        self.assertEqual(f["birthday"].widget_type, "splithiddendatetime")

    def test_boundfield_css_classes(self):
        """

        Tests the functionality of the css_classes method on a BoundField object.

        This method verifies that the css_classes method returns the correct CSS classes for a field, 
        both when no extra classes are provided and when extra classes are specified. 
        It also checks that duplicate classes are handled correctly, ensuring that each class is only 
        included once in the output string. 

        The purpose of this test is to ensure that the BoundField object behaves as expected when 
        generating CSS classes, which is important for styling and layout purposes in HTML forms. 

        """
        form = Person()
        field = form["first_name"]
        self.assertEqual(field.css_classes(), "")
        self.assertEqual(field.css_classes(extra_classes=""), "")
        self.assertEqual(field.css_classes(extra_classes="test"), "test")
        self.assertEqual(field.css_classes(extra_classes="test test"), "test")

    def test_label_suffix_override(self):
        """
        BoundField label_suffix (if provided) overrides Form label_suffix
        """

        class SomeForm(Form):
            field = CharField()

        boundfield = SomeForm(label_suffix="!")["field"]

        self.assertHTMLEqual(
            boundfield.label_tag(label_suffix="$"),
            '<label for="id_field">Field$</label>',
        )
        self.assertHTMLEqual(
            boundfield.legend_tag(label_suffix="$"),
            '<legend for="id_field">Field$</legend>',
        )

    def test_error_dict(self):
        """
        Tests the error dictionary generated by a Django form with validation errors.

        The function creates a sample form with two required fields and a custom validation error that is not associated with any field.
        It then checks that the form's error dictionary is correctly populated and can be rendered in different formats, including plain text, HTML, and JSON.
        The test case verifies that all error messages, including non-field errors, are properly included in the rendered error output and that the JSON representation of the error dictionary matches the expected format.
        """
        class MyForm(Form):
            foo = CharField()
            bar = CharField()

            def clean(self):
                raise ValidationError(
                    "Non-field error.", code="secret", params={"a": 1, "b": 2}
                )

        form = MyForm({})
        self.assertIs(form.is_valid(), False)

        errors = form.errors.as_text()
        control = [
            "* foo\n  * This field is required.",
            "* bar\n  * This field is required.",
            "* __all__\n  * Non-field error.",
        ]
        for error in control:
            self.assertIn(error, errors)

        errors = form.errors.as_ul()
        control = [
            '<li>foo<ul class="errorlist"><li>This field is required.</li></ul></li>',
            '<li>bar<ul class="errorlist"><li>This field is required.</li></ul></li>',
            '<li>__all__<ul class="errorlist nonfield"><li>Non-field error.</li></ul>'
            "</li>",
        ]
        for error in control:
            self.assertInHTML(error, errors)

        errors = form.errors.get_json_data()
        control = {
            "foo": [{"code": "required", "message": "This field is required."}],
            "bar": [{"code": "required", "message": "This field is required."}],
            "__all__": [{"code": "secret", "message": "Non-field error."}],
        }
        self.assertEqual(errors, control)
        self.assertEqual(json.dumps(errors), form.errors.as_json())

    def test_error_dict_as_json_escape_html(self):
        """#21962 - adding html escape flag to ErrorDict"""

        class MyForm(Form):
            foo = CharField()
            bar = CharField()

            def clean(self):
                raise ValidationError(
                    "<p>Non-field error.</p>",
                    code="secret",
                    params={"a": 1, "b": 2},
                )

        control = {
            "foo": [{"code": "required", "message": "This field is required."}],
            "bar": [{"code": "required", "message": "This field is required."}],
            "__all__": [{"code": "secret", "message": "<p>Non-field error.</p>"}],
        }

        form = MyForm({})
        self.assertFalse(form.is_valid())

        errors = json.loads(form.errors.as_json())
        self.assertEqual(errors, control)

        escaped_error = "&lt;p&gt;Non-field error.&lt;/p&gt;"
        self.assertEqual(
            form.errors.get_json_data(escape_html=True)["__all__"][0]["message"],
            escaped_error,
        )
        errors = json.loads(form.errors.as_json(escape_html=True))
        control["__all__"][0]["message"] = escaped_error
        self.assertEqual(errors, control)

    def test_error_list(self):
        """

        Tests the functionality of ErrorList.

        The ErrorList is tested for its ability to hold and manage error messages,
        including simple string messages and ValidationErrors with parameters.
        The tests cover various methods of the ErrorList, such as appending errors,
        checking for the presence of specific errors, and formatting the error list
        into different output formats, including text, HTML unordered list, and JSON.

        The test also verifies that the ErrorList behaves like a standard list and
        that it can properly handle the conversion of ValidationErrors into a suitable
        format for output.

        """
        e = ErrorList()
        e.append("Foo")
        e.append(ValidationError("Foo%(bar)s", code="foobar", params={"bar": "bar"}))

        self.assertIsInstance(e, list)
        self.assertIn("Foo", e)
        self.assertIn("Foo", ValidationError(e))

        self.assertEqual(e.as_text(), "* Foo\n* Foobar")

        self.assertEqual(
            e.as_ul(), '<ul class="errorlist"><li>Foo</li><li>Foobar</li></ul>'
        )

        errors = e.get_json_data()
        self.assertEqual(
            errors,
            [{"message": "Foo", "code": ""}, {"message": "Foobar", "code": "foobar"}],
        )
        self.assertEqual(json.dumps(errors), e.as_json())

    def test_error_list_class_not_specified(self):
        e = ErrorList()
        e.append("Foo")
        e.append(ValidationError("Foo%(bar)s", code="foobar", params={"bar": "bar"}))
        self.assertEqual(
            e.as_ul(), '<ul class="errorlist"><li>Foo</li><li>Foobar</li></ul>'
        )

    def test_error_list_class_has_one_class_specified(self):
        """
        Tests that an ErrorList instance with a specified error class generates the expected HTML unordered list.

        The function validates that the ErrorList class correctly applies a custom CSS class to the error list, while also handling different types of error messages, including plain strings and ValidationError objects.

        It verifies that the generated HTML output matches the expected format, including the application of the custom error class and the correct rendering of error messages.
        """
        e = ErrorList(error_class="foobar-error-class")
        e.append("Foo")
        e.append(ValidationError("Foo%(bar)s", code="foobar", params={"bar": "bar"}))
        self.assertEqual(
            e.as_ul(),
            '<ul class="errorlist foobar-error-class"><li>Foo</li><li>Foobar</li></ul>',
        )

    def test_error_list_with_hidden_field_errors_has_correct_class(self):
        """
        Tests that a form with hidden fields displaying error messages correctly assigns the 'errorlist nonfield' class to the error list when the form is rendered in different formats, including unordered list, paragraph, table, and div. This test case covers the scenario where a hidden field has an error and the resulting HTML output is verified to ensure proper error message display and class assignment.
        """
        class Person(Form):
            first_name = CharField()
            last_name = CharField(widget=HiddenInput)

        p = Person({"first_name": "John"})
        self.assertHTMLEqual(
            p.as_ul(),
            """<li><ul class="errorlist nonfield">
<li>(Hidden field last_name) This field is required.</li></ul></li><li>
<label for="id_first_name">First name:</label>
<input id="id_first_name" name="first_name" type="text" value="John" required>
<input id="id_last_name" name="last_name" type="hidden"></li>""",
        )
        self.assertHTMLEqual(
            p.as_p(),
            """
            <ul class="errorlist nonfield">
            <li>(Hidden field last_name) This field is required.</li></ul>
            <p><label for="id_first_name">First name:</label>
            <input id="id_first_name" name="first_name" type="text" value="John"
                required>
            <input id="id_last_name" name="last_name" type="hidden"></p>
            """,
        )
        self.assertHTMLEqual(
            p.as_table(),
            """<tr><td colspan="2"><ul class="errorlist nonfield">
<li>(Hidden field last_name) This field is required.</li></ul></td></tr>
<tr><th><label for="id_first_name">First name:</label></th><td>
<input id="id_first_name" name="first_name" type="text" value="John" required>
<input id="id_last_name" name="last_name" type="hidden"></td></tr>""",
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<ul class="errorlist nonfield"><li>(Hidden field last_name) This field '
            'is required.</li></ul><div><label for="id_first_name">First name:</label>'
            '<input id="id_first_name" name="first_name" type="text" value="John" '
            'required><input id="id_last_name" name="last_name" type="hidden"></div>',
        )

    def test_error_list_with_non_field_errors_has_correct_class(self):
        """
        Tests the HTML rendering of form errors when a non-field error occurs.

        The test case covers various rendering methods for the form, including :meth:`as_ul`, :meth:`as_p`, :meth:`as_table`, and :meth:`as_div`.
        It verifies that non-field errors are correctly rendered with the \"errorlist nonfield\" class and that the error message is correctly displayed.
        Additionally, it tests the :meth:`non_field_errors` method for rendering non-field errors and the :meth:`as_text` method for rendering error messages as plain text.
        """
        class Person(Form):
            first_name = CharField()
            last_name = CharField()

            def clean(self):
                raise ValidationError("Generic validation error")

        p = Person({"first_name": "John", "last_name": "Lennon"})
        self.assertHTMLEqual(
            str(p.non_field_errors()),
            '<ul class="errorlist nonfield"><li>Generic validation error</li></ul>',
        )
        self.assertHTMLEqual(
            p.as_ul(),
            """<li>
<ul class="errorlist nonfield"><li>Generic validation error</li></ul></li>
<li><label for="id_first_name">First name:</label>
<input id="id_first_name" name="first_name" type="text" value="John" required></li>
<li><label for="id_last_name">Last name:</label>
<input id="id_last_name" name="last_name" type="text" value="Lennon" required></li>""",
        )
        self.assertHTMLEqual(
            p.non_field_errors().as_text(), "* Generic validation error"
        )
        self.assertHTMLEqual(
            p.as_p(),
            """<ul class="errorlist nonfield"><li>Generic validation error</li></ul>
<p><label for="id_first_name">First name:</label>
<input id="id_first_name" name="first_name" type="text" value="John" required></p>
<p><label for="id_last_name">Last name:</label>
<input id="id_last_name" name="last_name" type="text" value="Lennon" required></p>""",
        )
        self.assertHTMLEqual(
            p.as_table(),
            """
            <tr><td colspan="2"><ul class="errorlist nonfield">
            <li>Generic validation error</li></ul></td></tr>
            <tr><th><label for="id_first_name">First name:</label></th><td>
            <input id="id_first_name" name="first_name" type="text" value="John"
                required>
            </td></tr>
            <tr><th><label for="id_last_name">Last name:</label></th><td>
            <input id="id_last_name" name="last_name" type="text" value="Lennon"
                required>
            </td></tr>
            """,
        )
        self.assertHTMLEqual(
            p.as_div(),
            '<ul class="errorlist nonfield"><li>Generic validation error</li></ul>'
            '<div><label for="id_first_name">First name:</label><input '
            'id="id_first_name" name="first_name" type="text" value="John" required>'
            '</div><div><label for="id_last_name">Last name:</label><input '
            'id="id_last_name" name="last_name" type="text" value="Lennon" required>'
            "</div>",
        )

    def test_error_escaping(self):
        class TestForm(Form):
            hidden = CharField(widget=HiddenInput(), required=False)
            visible = CharField()

            def clean_hidden(self):
                raise ValidationError('Foo & "bar"!')

            clean_visible = clean_hidden

        form = TestForm({"hidden": "a", "visible": "b"})
        form.is_valid()
        self.assertHTMLEqual(
            form.as_ul(),
            '<li><ul class="errorlist nonfield">'
            "<li>(Hidden field hidden) Foo &amp; &quot;bar&quot;!</li></ul></li>"
            '<li><ul class="errorlist"><li>Foo &amp; &quot;bar&quot;!</li></ul>'
            '<label for="id_visible">Visible:</label> '
            '<input type="text" name="visible" aria-invalid="true" value="b" '
            'id="id_visible" required>'
            '<input type="hidden" name="hidden" value="a" id="id_hidden"></li>',
        )

    def test_baseform_repr(self):
        """
        BaseForm.__repr__() should contain some basic information about the
        form.
        """
        p = Person()
        self.assertEqual(
            repr(p),
            "<Person bound=False, valid=Unknown, "
            "fields=(first_name;last_name;birthday)>",
        )
        p = Person(
            {"first_name": "John", "last_name": "Lennon", "birthday": "1940-10-9"}
        )
        self.assertEqual(
            repr(p),
            "<Person bound=True, valid=Unknown, "
            "fields=(first_name;last_name;birthday)>",
        )
        p.is_valid()
        self.assertEqual(
            repr(p),
            "<Person bound=True, valid=True, fields=(first_name;last_name;birthday)>",
        )
        p = Person(
            {"first_name": "John", "last_name": "Lennon", "birthday": "fakedate"}
        )
        p.is_valid()
        self.assertEqual(
            repr(p),
            "<Person bound=True, valid=False, fields=(first_name;last_name;birthday)>",
        )

    def test_baseform_repr_dont_trigger_validation(self):
        """
        BaseForm.__repr__() shouldn't trigger the form validation.
        """
        p = Person(
            {"first_name": "John", "last_name": "Lennon", "birthday": "fakedate"}
        )
        repr(p)
        with self.assertRaises(AttributeError):
            p.cleaned_data
        self.assertFalse(p.is_valid())
        self.assertEqual(p.cleaned_data, {"first_name": "John", "last_name": "Lennon"})

    def test_accessing_clean(self):
        """

        Tests that the clean method is correctly called when accessing the cleaned_data attribute of a form.
        This ensures that any data transformations or validations defined in the clean method are applied
        before the cleaned data is returned. In this case, the clean method converts the username to lowercase.

        """
        class UserForm(Form):
            username = CharField(max_length=10)
            password = CharField(widget=PasswordInput)

            def clean(self):
                """
                Normalizes and returns the cleaned data.

                This function processes the collected data to ensure consistency in the username field.
                If the data validation is successful, it converts the username to lowercase to maintain uniformity.
                The function then returns the cleaned and normalized data for further use.
                """
                data = self.cleaned_data

                if not self.errors:
                    data["username"] = data["username"].lower()

                return data

        f = UserForm({"username": "SirRobin", "password": "blue"})
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data["username"], "sirrobin")

    def test_changing_cleaned_data_nothing_returned(self):
        """



        Tests the behavior of a Form's clean method when altering cleaned data.

        This test case checks that when a Form's clean method modifies the cleaned data,
        the changes are properly reflected in the form's cleaned_data dictionary.
        It verifies that the form is valid and that the cleaned data matches the expected output.


        """
        class UserForm(Form):
            username = CharField(max_length=10)
            password = CharField(widget=PasswordInput)

            def clean(self):
                self.cleaned_data["username"] = self.cleaned_data["username"].lower()
                # don't return anything

        f = UserForm({"username": "SirRobin", "password": "blue"})
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data["username"], "sirrobin")

    def test_changing_cleaned_data_in_clean(self):
        """

        Tests that the cleaned data returned by the form's clean method can be modified.

        In this test, the clean method of the UserForm class alters the case of the 
        username and hardcodes a password. The test verifies that the form is valid and 
        that the cleaned data has been updated correctly.

        It checks that the username has been converted to lowercase as expected and 
        ensures that the password has been replaced with a hardcoded value, demonstrating 
        that the cleaned data dictionary can be modified by the form's clean method.

        """
        class UserForm(Form):
            username = CharField(max_length=10)
            password = CharField(widget=PasswordInput)

            def clean(self):
                data = self.cleaned_data

                # Return a different dict. We have not changed self.cleaned_data.
                return {
                    "username": data["username"].lower(),
                    "password": "this_is_not_a_secret",
                }

        f = UserForm({"username": "SirRobin", "password": "blue"})
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data["username"], "sirrobin")

    def test_multipart_encoded_form(self):
        """
        Checks if a form is multipart encoded based on the presence of file or image fields.

        This test case evaluates the `is_multipart` method of a form instance, verifying its behavior with different form configurations. 

        It considers three scenarios: 
        - A form without any file fields (FormWithoutFile), 
        - A form containing a file field (FormWithFile), and 
        - A form containing an image field (FormWithImage).

        The test passes if the `is_multipart` method correctly identifies multipart forms, returning `False` for forms without file fields and `True` for forms with file or image fields.
        """
        class FormWithoutFile(Form):
            username = CharField()

        class FormWithFile(Form):
            username = CharField()
            file = FileField()

        class FormWithImage(Form):
            image = ImageField()

        self.assertFalse(FormWithoutFile().is_multipart())
        self.assertTrue(FormWithFile().is_multipart())
        self.assertTrue(FormWithImage().is_multipart())

    def test_html_safe(self):
        """

        Tests that HTML is rendered safely by a form and its fields.

        Verifies that both a form and its fields have an __html__ method and that this method returns the same result as the str() function, 
        ensuring that HTML rendering is safe and consistent. This test checks the base functionality of HTML rendering in forms.

        """
        class SimpleForm(Form):
            username = CharField()

        form = SimpleForm()
        self.assertTrue(hasattr(SimpleForm, "__html__"))
        self.assertEqual(str(form), form.__html__())
        self.assertTrue(hasattr(form["username"], "__html__"))
        self.assertEqual(str(form["username"]), form["username"].__html__())

    def test_use_required_attribute_true(self):
        class MyForm(Form):
            use_required_attribute = True
            f1 = CharField(max_length=30)
            f2 = CharField(max_length=30, required=False)
            f3 = CharField(widget=Textarea)
            f4 = ChoiceField(choices=[("P", "Python"), ("J", "Java")])

        form = MyForm()
        self.assertHTMLEqual(
            form.as_p(),
            '<p><label for="id_f1">F1:</label>'
            '<input id="id_f1" maxlength="30" name="f1" type="text" required></p>'
            '<p><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></p>'
            '<p><label for="id_f3">F3:</label>'
            '<textarea cols="40" id="id_f3" name="f3" rows="10" required>'
            "</textarea></p>"
            '<p><label for="id_f4">F4:</label> <select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></p>",
        )
        self.assertHTMLEqual(
            form.as_ul(),
            '<li><label for="id_f1">F1:</label> '
            '<input id="id_f1" maxlength="30" name="f1" type="text" required></li>'
            '<li><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></li>'
            '<li><label for="id_f3">F3:</label>'
            '<textarea cols="40" id="id_f3" name="f3" rows="10" required>'
            "</textarea></li>"
            '<li><label for="id_f4">F4:</label> <select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></li>",
        )
        self.assertHTMLEqual(
            form.as_table(),
            '<tr><th><label for="id_f1">F1:</label></th>'
            '<td><input id="id_f1" maxlength="30" name="f1" type="text" required>'
            "</td></tr>"
            '<tr><th><label for="id_f2">F2:</label></th>'
            '<td><input id="id_f2" maxlength="30" name="f2" type="text"></td></tr>'
            '<tr><th><label for="id_f3">F3:</label></th>'
            '<td><textarea cols="40" id="id_f3" name="f3" rows="10" required>'
            "</textarea></td></tr>"
            '<tr><th><label for="id_f4">F4:</label></th><td>'
            '<select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></td></tr>",
        )
        self.assertHTMLEqual(
            form.render(form.template_name_div),
            '<div><label for="id_f1">F1:</label><input id="id_f1" maxlength="30" '
            'name="f1" type="text" required></div><div><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></div><div><label '
            'for="id_f3">F3:</label><textarea cols="40" id="id_f3" name="f3" '
            'rows="10" required></textarea></div><div><label for="id_f4">F4:</label>'
            '<select id="id_f4" name="f4"><option value="P">Python</option>'
            '<option value="J">Java</option></select></div>',
        )

    def test_use_required_attribute_false(self):
        """
        Tests the rendering of a form when the `use_required_attribute` is set to False.

        The test creates a sample form with various fields including text fields, a text area, and a choice field, and then checks the HTML rendering of the form in different formats, including paragraph, unordered list, table, and div.

        It verifies that the HTML output matches the expected structure and content, ensuring that the form fields are correctly rendered without the required attribute.
        """
        class MyForm(Form):
            use_required_attribute = False
            f1 = CharField(max_length=30)
            f2 = CharField(max_length=30, required=False)
            f3 = CharField(widget=Textarea)
            f4 = ChoiceField(choices=[("P", "Python"), ("J", "Java")])

        form = MyForm()
        self.assertHTMLEqual(
            form.as_p(),
            '<p><label for="id_f1">F1:</label>'
            '<input id="id_f1" maxlength="30" name="f1" type="text"></p>'
            '<p><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></p>'
            '<p><label for="id_f3">F3:</label>'
            '<textarea cols="40" id="id_f3" name="f3" rows="10"></textarea></p>'
            '<p><label for="id_f4">F4:</label> <select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></p>",
        )
        self.assertHTMLEqual(
            form.as_ul(),
            '<li><label for="id_f1">F1:</label>'
            '<input id="id_f1" maxlength="30" name="f1" type="text"></li>'
            '<li><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></li>'
            '<li><label for="id_f3">F3:</label>'
            '<textarea cols="40" id="id_f3" name="f3" rows="10"></textarea></li>'
            '<li><label for="id_f4">F4:</label> <select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></li>",
        )
        self.assertHTMLEqual(
            form.as_table(),
            '<tr><th><label for="id_f1">F1:</label></th>'
            '<td><input id="id_f1" maxlength="30" name="f1" type="text"></td></tr>'
            '<tr><th><label for="id_f2">F2:</label></th>'
            '<td><input id="id_f2" maxlength="30" name="f2" type="text"></td></tr>'
            '<tr><th><label for="id_f3">F3:</label></th><td>'
            '<textarea cols="40" id="id_f3" name="f3" rows="10">'
            "</textarea></td></tr>"
            '<tr><th><label for="id_f4">F4:</label></th><td>'
            '<select id="id_f4" name="f4">'
            '<option value="P">Python</option>'
            '<option value="J">Java</option>'
            "</select></td></tr>",
        )
        self.assertHTMLEqual(
            form.render(form.template_name_div),
            '<div><label for="id_f1">F1:</label> <input id="id_f1" maxlength="30" '
            'name="f1" type="text"></div><div><label for="id_f2">F2:</label>'
            '<input id="id_f2" maxlength="30" name="f2" type="text"></div><div>'
            '<label for="id_f3">F3:</label> <textarea cols="40" id="id_f3" name="f3" '
            'rows="10"></textarea></div><div><label for="id_f4">F4:</label>'
            '<select id="id_f4" name="f4"><option value="P">Python</option>'
            '<option value="J">Java</option></select></div>',
        )

    def test_only_hidden_fields(self):
        # A form with *only* hidden fields that has errors is going to be very unusual.
        """
        Tests the rendering of form fields that are hidden from the user interface.

        It verifies that hidden fields with required values missing are correctly 
        highlighted with error messages when rendered in paragraph and table formats.
        """
        class HiddenForm(Form):
            data = IntegerField(widget=HiddenInput)

        f = HiddenForm({})
        self.assertHTMLEqual(
            f.as_p(),
            '<ul class="errorlist nonfield">'
            "<li>(Hidden field data) This field is required.</li></ul>\n<p> "
            '<input type="hidden" name="data" id="id_data"></p>',
        )
        self.assertHTMLEqual(
            f.as_table(),
            '<tr><td colspan="2"><ul class="errorlist nonfield">'
            "<li>(Hidden field data) This field is required.</li></ul>"
            '<input type="hidden" name="data" id="id_data"></td></tr>',
        )

    def test_field_named_data(self):
        """
        Tests that a Django form with a single CharField correctly handles data validation and cleaning. The field is defined with a maximum length of 10 characters, and this test verifies that a valid input is accepted and the cleaned data is correctly returned as a dictionary.
        """
        class DataForm(Form):
            data = CharField(max_length=10)

        f = DataForm({"data": "xyzzy"})
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data, {"data": "xyzzy"})

    def test_empty_data_files_multi_value_dict(self):
        """
        Tests that a newly instantiated Person object has both data and files attributes, 
        each initialized as empty MultiValueDict instances. This ensures the basic 
        structure for handling multiple values and files is correctly set up for the 
        Person object.
        """
        p = Person()
        self.assertIsInstance(p.data, MultiValueDict)
        self.assertIsInstance(p.files, MultiValueDict)

    def test_field_deep_copy_error_messages(self):
        """
        Tests that deep copying a custom field preserves its type and creates a new copy of error messages.

        Checks that a custom CharField with custom error messages is correctly deep copied, 
        ensuring the copied field is an instance of the same class and has its own independent error messages dictionary, 
        thus avoiding unintended modifications to the original field's error messages when altering the copied field's error messages.
        """
        class CustomCharField(CharField):
            def __init__(self, **kwargs):
                """
                Initializes a new instance of the class, inheriting from a parent class and setting custom error messages for form validation. 

                It overrides the default error messages with a custom message for invalid form data, providing a more user-friendly experience. 

                The initialization process supports additional keyword arguments, which are passed to the parent class constructor.
                """
                kwargs["error_messages"] = {"invalid": "Form custom error message."}
                super().__init__(**kwargs)

        field = CustomCharField()
        field_copy = copy.deepcopy(field)
        self.assertIsInstance(field_copy, CustomCharField)
        self.assertIsNot(field_copy.error_messages, field.error_messages)

    def test_label_does_not_include_new_line(self):
        """
        Verifies that the label for a given form field does not include new lines.

        This test checks the generated HTML label and legend tags for a form field,
        ensuring they match the expected output and do not contain any newline characters.
        The test case specifically examines the 'first_name' field of a Person form,
        confirming that the rendered label and legend tags are correctly formatted and
        free of unexpected line breaks.
        """
        form = Person()
        field = form["first_name"]
        self.assertEqual(
            field.label_tag(), '<label for="id_first_name">First name:</label>'
        )
        self.assertEqual(
            field.legend_tag(),
            '<legend for="id_first_name">First name:</legend>',
        )

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_label_attrs_not_localized(self):
        """

        Tests that label attributes for form fields are correctly generated without localization.

        This function verifies that when the USE_THOUSAND_SEPARATOR setting is enabled, 
        the label_tag and legend_tag methods of a form field produce the correct HTML output 
        with the provided attributes, in this case, the 'number' attribute.

        The test case ensures that the 'number' attribute is properly included in the 
        generated label and legend HTML tags, and that the output matches the expected format.

        """
        form = Person()
        field = form["first_name"]
        self.assertHTMLEqual(
            field.label_tag(attrs={"number": 9999}),
            '<label number="9999" for="id_first_name">First name:</label>',
        )
        self.assertHTMLEqual(
            field.legend_tag(attrs={"number": 9999}),
            '<legend number="9999" for="id_first_name">First name:</legend>',
        )

    def test_remove_cached_field(self):
        """
        Tests that attempting to access a cached field that has been removed from a form raises a KeyError.

        Verifies that when a field is deleted from a form after it has been cached, 
        the expected exception is raised when trying to access the field. This ensures 
        that the cache is properly updated after field removal. The test validates the 
        correct behavior of form field removal and its impact on cached fields.
        """
        class TestForm(Form):
            name = CharField(max_length=10)

            def __init__(self, *args, **kwargs):
                """
                Initializes the class instance, inheriting from its parent class, and then processes its fields by iterating over each one.
                After initialization, the 'name' field is removed from the instance's fields dictionary.
                """
                super().__init__(*args, **kwargs)
                # Populate fields cache.
                [field for field in self]
                # Removed cached field.
                del self.fields["name"]

        f = TestForm({"name": "abcde"})

        with self.assertRaises(KeyError):
            f["name"]


@jinja2_tests
class Jinja2FormsTestCase(FormsTestCase):
    pass


class CustomRenderer(DjangoTemplates):
    form_template_name = "forms_tests/form_snippet.html"
    field_template_name = "forms_tests/custom_field.html"


class RendererTests(SimpleTestCase):
    def test_default(self):
        form = Form()
        self.assertEqual(form.renderer, get_default_renderer())

    def test_kwarg_instance(self):
        """

        Tests that a Form instance correctly stores and retrieves a custom renderer instance passed via keyword argument.

        This test verifies that the Form class can be instantiated with a custom renderer and that the renderer is properly assigned to the instance.

        """
        custom = CustomRenderer()
        form = Form(renderer=custom)
        self.assertEqual(form.renderer, custom)

    def test_kwarg_class(self):
        """

        Tests that a custom renderer class can be successfully passed as a keyword argument to the Form class.

        Checks if the provided custom renderer instance is correctly assigned to the form's renderer attribute.

        """
        custom = CustomRenderer()
        form = Form(renderer=custom)
        self.assertEqual(form.renderer, custom)

    def test_attribute_instance(self):
        """
        Tests that an instance of a Form class correctly inherits the default renderer 
        from its class when no renderer is explicitly specified.

        Verifies that the instance's renderer attribute matches the class's default renderer 
        when a form instance is created without a custom renderer. This ensures that 
        forms without explicitly set renderers will use the class-defined default renderer.
        """
        class CustomForm(Form):
            default_renderer = DjangoTemplates()

        form = CustomForm()
        self.assertEqual(form.renderer, CustomForm.default_renderer)

    def test_attribute_class(self):
        """
        Verifies that a form instance is correctly initialized with its class-defined default renderer.

        This test checks if the renderer attribute of a form instance is an instance of the renderer class specified as the default_renderer attribute in the form class.

        The test creates a custom form class with a custom renderer and asserts that the renderer attribute of a form instance is of the correct type, ensuring that the default renderer is properly applied during form initialization.
        """
        class CustomForm(Form):
            default_renderer = CustomRenderer

        form = CustomForm()
        self.assertIsInstance(form.renderer, CustomForm.default_renderer)

    def test_attribute_override(self):
        class CustomForm(Form):
            default_renderer = DjangoTemplates()

        custom = CustomRenderer()
        form = CustomForm(renderer=custom)
        self.assertEqual(form.renderer, custom)


class TemplateTests(SimpleTestCase):
    def test_iterate_radios(self):
        f = FrameworkForm(auto_id="id_%s")
        t = Template(
            "{% for radio in form.language %}"
            '<div class="myradio">{{ radio }}</div>'
            "{% endfor %}"
        )
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            '<div class="myradio"><label for="id_language_0">'
            '<input id="id_language_0" name="language" type="radio" value="P" '
            "required> Python</label></div>"
            '<div class="myradio"><label for="id_language_1">'
            '<input id="id_language_1" name="language" type="radio" value="J" '
            "required> Java</label></div>",
        )

    def test_iterate_checkboxes(self):
        f = SongForm({"composers": ["J", "P"]}, auto_id=False)
        t = Template(
            "{% for checkbox in form.composers %}"
            '<div class="mycheckbox">{{ checkbox }}</div>'
            "{% endfor %}"
        )
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            '<div class="mycheckbox"><label>'
            '<input checked name="composers" type="checkbox" value="J"> '
            "John Lennon</label></div>"
            '<div class="mycheckbox"><label>'
            '<input checked name="composers" type="checkbox" value="P"> '
            "Paul McCartney</label></div>",
        )

    def test_templates_with_forms(self):
        """
        Tests the rendering of Django forms within templates.

        This test suite ensures that form fields are correctly rendered in HTML, 
        including the display of field labels, error messages and help text. 
        It covers various scenarios such as rendering empty forms, 
        forms with initial data and forms with validation errors. 
        The test cases also verify the correct usage of different template tags 
        such as `label_tag`, `help_text` and `errors.as_ul`. 

        The test uses a sample `UserRegistration` form with fields for username and password. 
        The form's validation logic checks that the two password fields match. 
        The test templates used in the test suite demonstrate different ways 
        to render form fields, labels and errors in HTML.
        """
        class UserRegistration(Form):
            username = CharField(
                max_length=10,
                help_text=("Good luck picking a username that doesn't already exist."),
            )
            password1 = CharField(widget=PasswordInput)
            password2 = CharField(widget=PasswordInput)

            def clean(self):
                """
                Validate and clean form data to ensure password consistency.

                This method checks if the provided password and its confirmation match.
                If the passwords do not match, a ValidationError is raised with a corresponding error message.
                Otherwise, the cleaned form data is returned.

                :raises: ValidationError if the passwords do not match
                :returns: The cleaned form data if passwords match
                """
                if (
                    self.cleaned_data.get("password1")
                    and self.cleaned_data.get("password2")
                    and self.cleaned_data["password1"] != self.cleaned_data["password2"]
                ):
                    raise ValidationError("Please make sure your passwords match.")
                return self.cleaned_data

        # There is full flexibility in displaying form fields in a template.
        # Just pass a Form instance to the template, and use "dot" access to
        # refer to individual fields. However, this flexibility comes with the
        # responsibility of displaying all the errors, including any that might
        # not be associated with a particular field.
        t = Template(
            "<form>"
            "{{ form.username.errors.as_ul }}"
            "<p><label>Your username: {{ form.username }}</label></p>"
            "{{ form.password1.errors.as_ul }}"
            "<p><label>Password: {{ form.password1 }}</label></p>"
            "{{ form.password2.errors.as_ul }}"
            "<p><label>Password (again): {{ form.password2 }}</label></p>"
            '<input type="submit" required>'
            "</form>"
        )
        f = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p><label>Your username: "
            '<input type="text" name="username" maxlength="10" required></label></p>'
            "<p><label>Password: "
            '<input type="password" name="password1" required></label></p>'
            "<p><label>Password (again): "
            '<input type="password" name="password2" required></label></p>'
            '<input type="submit" required>'
            "</form>",
        )
        f = UserRegistration({"username": "django"}, auto_id=False)
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p><label>Your username: "
            '<input type="text" name="username" value="django" maxlength="10" required>'
            "</label></p>"
            '<ul class="errorlist"><li>This field is required.</li></ul><p>'
            "<label>Password: "
            '<input type="password" name="password1" aria-invalid="true" required>'
            "</label></p>"
            '<ul class="errorlist"><li>This field is required.</li></ul>'
            "<p><label>Password (again): "
            '<input type="password" name="password2" aria-invalid="true" required>'
            "</label></p>"
            '<input type="submit" required>'
            "</form>",
        )
        # Use form.[field].label to output a field's label. 'label' for a field
        # can by specified by using the 'label' argument to a Field class. If
        # 'label' is not specified, Django will use the field name with
        # underscores converted to spaces, and the initial letter capitalized.
        t = Template(
            "<form>"
            "<p><label>{{ form.username.label }}: {{ form.username }}</label></p>"
            "<p><label>{{ form.password1.label }}: {{ form.password1 }}</label></p>"
            "<p><label>{{ form.password2.label }}: {{ form.password2 }}</label></p>"
            '<input type="submit" required>'
            "</form>"
        )
        f = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p><label>Username: "
            '<input type="text" name="username" maxlength="10" required></label></p>'
            "<p><label>Password1: "
            '<input type="password" name="password1" required></label></p>'
            "<p><label>Password2: "
            '<input type="password" name="password2" required></label></p>'
            '<input type="submit" required>'
            "</form>",
        )
        # Use form.[field].label_tag to output a field's label with a <label>
        # tag wrapped around it, but *only* if the given field has an "id"
        # attribute. Recall from above that passing the "auto_id" argument to a
        # Form gives each field an "id" attribute.
        t = Template(
            "<form>"
            "<p>{{ form.username.label_tag }} {{ form.username }}"
            '<span {% if form.username.id_for_label %}id="'
            '{{ form.username.id_for_label }}_helptext"{% endif %}>'
            "{{ form.username.help_text}}</span></p>"
            "<p>{{ form.password1.label_tag }} {{ form.password1 }}</p>"
            "<p>{{ form.password2.label_tag }} {{ form.password2 }}</p>"
            '<input type="submit" required>'
            "</form>"
        )
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p>Username: "
            '<input type="text" name="username" maxlength="10" required>'
            "<span>Good luck picking a username that doesn't already exist.</span></p>"
            '<p>Password1: <input type="password" name="password1" required></p>'
            '<p>Password2: <input type="password" name="password2" required></p>'
            '<input type="submit" required>'
            "</form>",
        )
        f = UserRegistration(auto_id="id_%s")
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            '<p><label for="id_username">Username:</label>'
            '<input id="id_username" type="text" name="username" maxlength="10" '
            'aria-describedby="id_username_helptext" required>'
            '<span id="id_username_helptext">'
            "Good luck picking a username that doesn't already exist.</span></p>"
            '<p><label for="id_password1">Password1:</label>'
            '<input type="password" name="password1" id="id_password1" required></p>'
            '<p><label for="id_password2">Password2:</label>'
            '<input type="password" name="password2" id="id_password2" required></p>'
            '<input type="submit" required>'
            "</form>",
        )
        # Use form.[field].legend_tag to output a field's label with a <legend>
        # tag wrapped around it, but *only* if the given field has an "id"
        # attribute. Recall from above that passing the "auto_id" argument to a
        # Form gives each field an "id" attribute.
        t = Template(
            "<form>"
            "<p>{{ form.username.legend_tag }} {{ form.username }}</p>"
            "<p>{{ form.password1.legend_tag }} {{ form.password1 }}</p>"
            "<p>{{ form.password2.legend_tag }} {{ form.password2 }}</p>"
            '<input type="submit" required>'
            "</form>"
        )
        f = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p>Username: "
            '<input type="text" name="username" maxlength="10" required></p>'
            '<p>Password1: <input type="password" name="password1" required></p>'
            '<p>Password2: <input type="password" name="password2" required></p>'
            '<input type="submit" required>'
            "</form>",
        )
        f = UserRegistration(auto_id="id_%s")
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            '<p><legend for="id_username">Username:</legend>'
            '<input id="id_username" type="text" name="username" maxlength="10" '
            'aria-describedby="id_username_helptext" required></p>'
            '<p><legend for="id_password1">Password1:</legend>'
            '<input type="password" name="password1" id="id_password1" required></p>'
            '<p><legend for="id_password2">Password2:</legend>'
            '<input type="password" name="password2" id="id_password2" required></p>'
            '<input type="submit" required>'
            "</form>",
        )
        # Use form.[field].help_text to output a field's help text. If the
        # given field does not have help text, nothing will be output.
        t = Template(
            "<form>"
            "<p>{{ form.username.label_tag }} {{ form.username }}<br>"
            "{{ form.username.help_text }}</p>"
            "<p>{{ form.password1.label_tag }} {{ form.password1 }}</p>"
            "<p>{{ form.password2.label_tag }} {{ form.password2 }}</p>"
            '<input type="submit" required>'
            "</form>"
        )
        f = UserRegistration(auto_id=False)
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p>Username: "
            '<input type="text" name="username" maxlength="10" required><br>'
            "Good luck picking a username that doesn&#x27;t already exist.</p>"
            '<p>Password1: <input type="password" name="password1" required></p>'
            '<p>Password2: <input type="password" name="password2" required></p>'
            '<input type="submit" required>'
            "</form>",
        )
        self.assertEqual(
            Template("{{ form.password1.help_text }}").render(Context({"form": f})),
            "",
        )
        # To display the errors that aren't associated with a particular field
        # e.g. the errors caused by Form.clean() -- use
        # {{ form.non_field_errors }} in the template. If used on its own, it
        # is displayed as a <ul> (or an empty string, if the list of errors is
        # empty).
        t = Template(
            "<form>"
            "{{ form.username.errors.as_ul }}"
            "<p><label>Your username: {{ form.username }}</label></p>"
            "{{ form.password1.errors.as_ul }}"
            "<p><label>Password: {{ form.password1 }}</label></p>"
            "{{ form.password2.errors.as_ul }}"
            "<p><label>Password (again): {{ form.password2 }}</label></p>"
            '<input type="submit" required>'
            "</form>"
        )
        f = UserRegistration(
            {"username": "django", "password1": "foo", "password2": "bar"},
            auto_id=False,
        )
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            "<p><label>Your username: "
            '<input type="text" name="username" value="django" maxlength="10" required>'
            "</label></p>"
            "<p><label>Password: "
            '<input type="password" name="password1" required></label></p>'
            "<p><label>Password (again): "
            '<input type="password" name="password2" required></label></p>'
            '<input type="submit" required>'
            "</form>",
        )
        t = Template(
            "<form>"
            "{{ form.non_field_errors }}"
            "{{ form.username.errors.as_ul }}"
            "<p><label>Your username: {{ form.username }}</label></p>"
            "{{ form.password1.errors.as_ul }}"
            "<p><label>Password: {{ form.password1 }}</label></p>"
            "{{ form.password2.errors.as_ul }}"
            "<p><label>Password (again): {{ form.password2 }}</label></p>"
            '<input type="submit" required>'
            "</form>"
        )
        self.assertHTMLEqual(
            t.render(Context({"form": f})),
            "<form>"
            '<ul class="errorlist nonfield">'
            "<li>Please make sure your passwords match.</li></ul>"
            "<p><label>Your username: "
            '<input type="text" name="username" value="django" maxlength="10" required>'
            "</label></p>"
            "<p><label>Password: "
            '<input type="password" name="password1" required></label></p>'
            "<p><label>Password (again): "
            '<input type="password" name="password2" required></label></p>'
            '<input type="submit" required>'
            "</form>",
        )

    def test_basic_processing_in_view(self):
        class UserRegistration(Form):
            username = CharField(max_length=10)
            password1 = CharField(widget=PasswordInput)
            password2 = CharField(widget=PasswordInput)

            def clean(self):
                """
                Validates and returns cleaned form data, ensuring password fields match.

                    Checks if both password fields ('password1' and 'password2') are present and contain matching values.
                    If the passwords do not match, raises a ValidationError with a corresponding error message.
                    Otherwise, returns the cleaned form data.

                    :raises: ValidationError if password fields do not match
                    :return: The cleaned form data
                """
                if (
                    self.cleaned_data.get("password1")
                    and self.cleaned_data.get("password2")
                    and self.cleaned_data["password1"] != self.cleaned_data["password2"]
                ):
                    raise ValidationError("Please make sure your passwords match.")
                return self.cleaned_data

        def my_function(method, post_data):
            """

            Validates user registration data and returns a response based on the provided method.

            Args:
                method (str): The HTTP method to handle, currently only 'POST' is supported.
                post_data (dict): The user registration data to validate.

            Returns:
                str: If the form is valid, a string containing the cleaned data; otherwise, an HTML form to collect the registration data.

            Note:
                The function uses a UserRegistration form to validate the provided data. If the method is 'POST', the form is populated with the post_data; otherwise, an empty form is rendered.

            """
            if method == "POST":
                form = UserRegistration(post_data, auto_id=False)
            else:
                form = UserRegistration(auto_id=False)

            if form.is_valid():
                return "VALID: %r" % sorted(form.cleaned_data.items())

            t = Template(
                '<form method="post">'
                "{{ form }}"
                '<input type="submit" required>'
                "</form>"
            )
            return t.render(Context({"form": form}))

        # GET with an empty form and no errors.
        self.assertHTMLEqual(
            my_function("GET", {}),
            '<form method="post">'
            "<div>Username:"
            '<input type="text" name="username" maxlength="10" required></div>'
            "<div>Password1:"
            '<input type="password" name="password1" required></div>'
            "<div>Password2:"
            '<input type="password" name="password2" required></div>'
            '<input type="submit" required>'
            "</form>",
        )
        # POST with erroneous data, a redisplayed form, with errors.
        self.assertHTMLEqual(
            my_function(
                "POST",
                {
                    "username": "this-is-a-long-username",
                    "password1": "foo",
                    "password2": "bar",
                },
            ),
            '<form method="post">'
            '<ul class="errorlist nonfield">'
            "<li>Please make sure your passwords match.</li></ul>"
            '<div>Username:<ul class="errorlist">'
            "<li>Ensure this value has at most 10 characters (it has 23).</li></ul>"
            '<input type="text" name="username" aria-invalid="true" '
            'value="this-is-a-long-username" maxlength="10" required></div>'
            "<div>Password1:"
            '<input type="password" name="password1" required></div>'
            "<div>Password2:"
            '<input type="password" name="password2" required></div>'
            '<input type="submit" required>'
            "</form>",
        )
        # POST with valid data (the success message).
        self.assertEqual(
            my_function(
                "POST",
                {
                    "username": "adrian",
                    "password1": "secret",
                    "password2": "secret",
                },
            ),
            "VALID: [('password1', 'secret'), ('password2', 'secret'), "
            "('username', 'adrian')]",
        )

    def test_custom_field_template(self):
        """

        Tests the rendering of a Form with a custom field template.

        Verifies that a form field can be rendered using a custom HTML template,
        and that the rendered HTML matches the expected output. The custom template
        is specified using the 'template_name' parameter of the CharField.

        The test case checks for the correct rendering of the field's label, custom
        content, and input element.

        """
        class MyForm(Form):
            first_name = CharField(template_name="forms_tests/custom_field.html")

        f = MyForm()
        self.assertHTMLEqual(
            f.render(),
            '<div><label for="id_first_name">First name:</label><p>Custom Field<p>'
            '<input type="text" name="first_name" required id="id_first_name"></div>',
        )

    def test_custom_field_render_template(self):
        class MyForm(Form):
            first_name = CharField()

        f = MyForm()
        self.assertHTMLEqual(
            f["first_name"].render(template_name="forms_tests/custom_field.html"),
            '<label for="id_first_name">First name:</label><p>Custom Field<p>'
            '<input type="text" name="first_name" required id="id_first_name">',
        )


class OverrideTests(SimpleTestCase):
    @override_settings(FORM_RENDERER="forms_tests.tests.test_forms.CustomRenderer")
    def test_custom_renderer_template_name(self):
        """
        Tests the rendering of a form using a custom template renderer, verifying that the resulting HTML matches the expected output. 

        The test case creates a simple form with a single field and renders it using a custom renderer. It then compares the generated HTML to an expected result, ensuring that the custom renderer produces the correct output. 

        This test is useful for ensuring that custom form renderers are correctly implemented and that they produce the desired HTML structure. 

        :param self: The test instance.
        :raises AssertionError: If the rendered HTML does not match the expected output.
        """
        class Person(Form):
            first_name = CharField()

        t = Template("{{ form }}")
        html = t.render(Context({"form": Person()}))
        expected = """
        <div class="fieldWrapper"><label for="id_first_name">First name:</label>
        <input type="text" name="first_name" required id="id_first_name"></div>
        """
        self.assertHTMLEqual(html, expected)

    @override_settings(FORM_RENDERER="forms_tests.tests.test_forms.CustomRenderer")
    def test_custom_renderer_field_template_name(self):
        """

        Tests the usage of a custom Django form renderer.

        This test case verifies that a custom form renderer correctly renders form fields
        using a custom template. Specifically, it checks that the 'as_field_group' method
        of a form field returns the expected HTML when rendered using the custom template.

        The test creates a simple form with a single 'first_name' field, renders it using
        the custom renderer, and then asserts that the resulting HTML matches the expected
        output.

        """
        class Person(Form):
            first_name = CharField()

        t = Template("{{ form.first_name.as_field_group }}")
        html = t.render(Context({"form": Person()}))
        expected = """
        <label for="id_first_name">First name:</label>
        <p>Custom Field<p>
        <input type="text" name="first_name" required id="id_first_name">
        """
        self.assertHTMLEqual(html, expected)

    def test_per_form_template_name(self):
        class Person(Form):
            first_name = CharField()
            template_name = "forms_tests/form_snippet.html"

        t = Template("{{ form }}")
        html = t.render(Context({"form": Person()}))
        expected = """
        <div class="fieldWrapper"><label for="id_first_name">First name:</label>
        <input type="text" name="first_name" required id="id_first_name"></div>
        """
        self.assertHTMLEqual(html, expected)

    def test_errorlist_override(self):
        """

        Tests the override functionality of the error list in a form with invalid data.

        This test case creates a custom error list class and a form with fields that
        trigger validation errors when provided with invalid data. It then checks if the
        form's error messages are rendered as expected when using the custom error list
        class, ensuring that the error messages are displayed correctly in the form.

        The test verifies that the form's fields and error messages are rendered as HTML
        paragraph and div elements, with each error message wrapped in a div with the
        class 'error' and the error list wrapped in a div with the class 'errorlist'.

        """
        class CustomErrorList(ErrorList):
            template_name = "forms_tests/error.html"

        class CommentForm(Form):
            name = CharField(max_length=50, required=False)
            email = EmailField()
            comment = CharField()

        data = {"email": "invalid"}
        f = CommentForm(data, auto_id=False, error_class=CustomErrorList)
        self.assertHTMLEqual(
            f.as_p(),
            '<p>Name: <input type="text" name="name" maxlength="50"></p>'
            '<div class="errorlist">'
            '<div class="error">Enter a valid email address.</div></div>'
            "<p>Email: "
            '<input type="email" name="email" value="invalid" maxlength="320" '
            'aria-invalid="true" required></p><div class="errorlist">'
            '<div class="error">This field is required.</div></div>'
            '<p>Comment: <input type="text" name="comment" aria-invalid="true" '
            "required></p>",
        )

    def test_cyclic_context_boundfield_render(self):
        """

        Tests that a cyclic context in a BoundField's render method does not cause a RecursionError.

        This test case creates a form with a field that uses a custom template for rendering.
        The test verifies that the form can be rendered without encountering a recursion error,
        which would occur if there were a cyclic reference in the rendering process.

        The expected outcome is that the form renders successfully without raising an exception.
        If a RecursionError is raised, the test fails, indicating a problem with the BoundField's render method.

        """
        class FirstNameForm(Form):
            first_name = CharField()
            template_name_label = "forms_tests/cyclic_context_boundfield_render.html"

        f = FirstNameForm()
        try:
            f.render()
        except RecursionError:
            self.fail("Cyclic reference in BoundField.render().")

    def test_legend_tag(self):
        """

        Tests the rendering of a legend tag in a form.

        Verifies that the legend element is correctly generated with the required CSS class
        when using a custom form template and framework form class. 

        The test checks for a specific HTML output, ensuring that both the label and legend
        elements are properly rendered with the 'required' class.

        """
        class CustomFrameworkForm(FrameworkForm):
            template_name = "forms_tests/legend_test.html"
            required_css_class = "required"

        f = CustomFrameworkForm()
        self.assertHTMLEqual(
            str(f),
            '<label for="id_name" class="required">Name:</label>'
            '<legend class="required">Language:</legend>',
        )
