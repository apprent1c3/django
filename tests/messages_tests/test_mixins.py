from django.core.signing import b64_decode
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SomeObject
from .urls import ContactFormViewWithMsg, DeleteFormViewWithMsg


@override_settings(ROOT_URLCONF="messages_tests.urls")
class SuccessMessageMixinTests(TestCase):
    def test_set_messages_success(self):
        """

        Tests the successful setting of success messages.

        Verifies that when a success message is added, it is correctly stored and
        retrieved, and that the message contains the expected content, specifically
        the name of the author who triggered the message.

        This test case simulates a POST request to the success message endpoint,
        and then checks the response cookies to ensure the message is set as expected.

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

        Tests whether the delete view displays a success message after an object has been deleted.

        The test creates an instance of SomeObject, sends a POST request to the delete view, 
        and verifies that the response contains the expected success message.

        This test case ensures that the delete functionality works correctly and provides 
        user feedback after a successful deletion.

        """
        object_to_delete = SomeObject.objects.create(name="MyObject")
        delete_url = reverse("success_msg_on_delete", args=[object_to_delete.pk])
        response = self.client.post(delete_url, follow=True)
        self.assertContains(response, DeleteFormViewWithMsg.success_message)
