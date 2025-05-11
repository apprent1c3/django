from django.contrib import messages


class SuccessMessageMixin:
    """
    Add a success message on successful form submission.
    """

    success_message = ""

    def form_valid(self, form):
        """

        Handles form submission when it is valid.

        Overrides the default behavior to display a success message after form validation.

        """
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        if success_message:
            messages.success(self.request, success_message)
        return response

    def get_success_message(self, cleaned_data):
        return self.success_message % cleaned_data
