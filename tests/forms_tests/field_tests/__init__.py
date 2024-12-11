from django import forms


class FormFieldAssertionsMixin:
    def assertWidgetRendersTo(self, field, to):
        """
        Asserts that a given form field renders to the specified HTML.

        Parameters
        ----------
        field : Field
            The form field to be rendered.
        to : str
            The expected HTML string.

        This function creates a temporary form with the given field and compares its
        rendered HTML with the provided string, ensuring they are equal. It is useful for
        testing the HTML output of custom form fields.
        """
        class Form(forms.Form):
            f = field

        self.assertHTMLEqual(str(Form()["f"]), to)
