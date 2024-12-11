from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import FileField, FileInput, Form
from django.utils.datastructures import MultiValueDict

from .base import WidgetTest


class FileInputTest(WidgetTest):
    widget = FileInput()

    def test_render(self):
        """
        FileInput widgets never render the value attribute. The old value
        isn't useful if a form is updated or an error occurred.
        """
        self.check_html(
            self.widget,
            "email",
            "test@example.com",
            html='<input type="file" name="email">',
        )
        self.check_html(
            self.widget, "email", "", html='<input type="file" name="email">'
        )
        self.check_html(
            self.widget, "email", None, html='<input type="file" name="email">'
        )

    def test_value_omitted_from_data(self):
        """

        Checks if a value is omitted from the data.

        This method determines whether a specific field has a value in the provided data.
        It returns True if the field's value is not present, and False otherwise.

        :param dict data_dict: The dictionary containing the data.
        :param dict initial_data: The initial data dictionary.
        :param str field: The name of the field to check.
        :returns: A boolean indicating whether the value is omitted.

        """
        self.assertIs(self.widget.value_omitted_from_data({}, {}, "field"), True)
        self.assertIs(
            self.widget.value_omitted_from_data({}, {"field": "value"}, "field"), False
        )

    def test_use_required_attribute(self):
        # False when initial data exists. The file input is left blank by the
        # user to keep the existing, initial value.
        """
        Tests the use_required_attribute method of the widget.

        This method checks whether the widget should utilize the required attribute based on the provided filename.
        It returns True if no filename is provided (i.e., None), indicating that the required attribute should be used.
        Conversely, it returns False when a filename is given, such as 'resume.txt', signifying that the required attribute should not be used.

        The purpose of this test is to validate the widget's behavior in handling the required attribute under varying conditions.

        """
        self.assertIs(self.widget.use_required_attribute(None), True)
        self.assertIs(self.widget.use_required_attribute("resume.txt"), False)

    def test_fieldset(self):
        """

        Tests the rendering of a form field without using a fieldset.

        This test case checks that the field is correctly rendered as a standard form input,
        without being wrapped in a fieldset element, when the use_fieldset attribute of the
        widget is set to False.

        The test creates a test form with a single file field and verifies that the rendered
        HTML matches the expected output.

        """
        class TestForm(Form):
            template_name = "forms_tests/use_fieldset.html"
            field = FileField(widget=self.widget)

        form = TestForm()
        self.assertIs(self.widget.use_fieldset, False)
        self.assertHTMLEqual(
            '<div><label for="id_field">Field:</label><input id="id_field" '
            'name="field" required type="file"></div>',
            form.render(),
        )

    def test_multiple_error(self):
        msg = "FileInput doesn't support uploading multiple files."
        with self.assertRaisesMessage(ValueError, msg):
            FileInput(attrs={"multiple": True})

    def test_value_from_datadict_multiple(self):
        """
        Tests the value_from_datadict method of the FileInput widget in cases where multiple files are selected.

        This test covers two scenarios: the first where the FileInput widget is configured to allow multiple file selection,
        and the second where it is not. It verifies that the method returns the expected list of files or a single file
        depending on the widget's configuration.

        The test uses SimpleUploadedFile objects to simulate uploaded files and checks the return value of the
        value_from_datadict method against the expected result in both cases.
        """
        class MultipleFileInput(FileInput):
            allow_multiple_selected = True

        file_1 = SimpleUploadedFile("something1.txt", b"content 1")
        file_2 = SimpleUploadedFile("something2.txt", b"content 2")
        # Uploading multiple files is allowed.
        widget = MultipleFileInput(attrs={"multiple": True})
        value = widget.value_from_datadict(
            data={"name": "Test name"},
            files=MultiValueDict({"myfile": [file_1, file_2]}),
            name="myfile",
        )
        self.assertEqual(value, [file_1, file_2])
        # Uploading multiple files is not allowed.
        widget = FileInput()
        value = widget.value_from_datadict(
            data={"name": "Test name"},
            files=MultiValueDict({"myfile": [file_1, file_2]}),
            name="myfile",
        )
        self.assertEqual(value, file_2)

    def test_multiple_default(self):
        class MultipleFileInput(FileInput):
            allow_multiple_selected = True

        tests = [
            (None, True),
            ({"class": "myclass"}, True),
            ({"multiple": False}, False),
        ]
        for attrs, expected in tests:
            with self.subTest(attrs=attrs):
                widget = MultipleFileInput(attrs=attrs)
                self.assertIs(widget.attrs["multiple"], expected)
