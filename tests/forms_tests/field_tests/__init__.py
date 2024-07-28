from django import forms


class FormFieldAssertionsMixin:
    def assertWidgetRendersTo(self, field, to):
        """
        This is a comment
        """
        class Form(forms.Form):
            f = field

        self.assertHTMLEqual(str(Form()["f"]), to)
