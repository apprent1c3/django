from django.core.signing import b64_decode
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SomeObject
from .urls import ContactFormViewWithMsg, DeleteFormViewWithMsg


@override_settings(ROOT_URLCONF="messages_tests.urls")
class SuccessMessageMixinTests(TestCase):
    def test_set_messages_success(self):
        """

        Tests the successful setting of a success message in the messages cookie.

        This test simulates a POST request to the add_success_msg view with an author object,
        and then verifies that the response includes a cookie with a success message containing the author's name.
        The success message is expected to match the format defined in ContactFormViewWithMsg.

        """
        author = {"name": "John Doe", "slug": "success-msg"}
        add_url = reverse("add_success_msg")
        req = self.client.post(add_url, author)
        # Uncompressed message is stored in the cookie.
        value = b64_decode(
            req.cookies["messages"].value.split(":")[0].encode(),
        ).decode()
        self.assertIn(ContactFormViewWithMsg.success_message % author, value)

    def test_set_messages_success_on_delete(self):
        """

        Tests whether a success message is displayed when an object is deleted.

        This test case verifies that the DeleteFormViewWithMsg view behaves as expected
        when handling a deletion request. It checks if the view correctly sets a success
        message after deleting an object and if this message is displayed in the response.

        The test creates a sample object, sends a POST request to the delete view, and
        then asserts that the response contains the expected success message.

        """
        object_to_delete = SomeObject.objects.create(name="MyObject")
        delete_url = reverse("success_msg_on_delete", args=[object_to_delete.pk])
        response = self.client.post(delete_url, follow=True)
        self.assertContains(response, DeleteFormViewWithMsg.success_message)
