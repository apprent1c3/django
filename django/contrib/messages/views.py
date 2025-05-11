from django.contrib import messages


class SuccessMessageMixin:
    """
    Add a success message on successful form submission.
    """

    success_message = ""

    def form_valid(self, form):
        """
        ..: 
            Overrides the default form validation success behavior to display a success message.

            :return: The response from the parent class after successful form validation.
        """
        response = super().form_valid(form)
        success_message = self.get_success_message(form.cleaned_data)
        if success_message:
            messages.success(self.request, success_message)
        return response

    def get_success_message(self, cleaned_data):
        return self.success_message % cleaned_data
