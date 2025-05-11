from django.core import mail
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


@override_settings(
    ADMINS=(
        ("Admin", "admin@example.com"),
        ("Admin and Manager", "admin_and_manager@example.com"),
    ),
    MANAGERS=(
        ("Manager", "manager@example.com"),
        ("Admin and Manager", "admin_and_manager@example.com"),
    ),
)
class SendTestEmailManagementCommand(SimpleTestCase):
    """
    Test the sending of a test email using the `sendtestemail` command.
    """

    def test_single_receiver(self):
        """
        Tests that an email is sent to a single recipient with the correct subject.\"\"\"
        ```
        """
        recipient = "joe@example.com"
        call_command("sendtestemail", recipient)
        self.assertEqual(len(mail.outbox), 1)
        mail_message = mail.outbox[0]
        self.assertEqual(mail_message.subject[0:15], "Test email from")
        self.assertEqual(mail_message.recipients(), [recipient])

    def test_multiple_receivers(self):
        """
        Tests if an email can be successfully sent to multiple recipients. Verifies that only one email is sent and that both recipients receive the email with the correct subject.
        """
        recipients = ["joe@example.com", "jane@example.com"]
        call_command("sendtestemail", recipients[0], recipients[1])
        self.assertEqual(len(mail.outbox), 1)
        mail_message = mail.outbox[0]
        self.assertEqual(mail_message.subject[0:15], "Test email from")
        self.assertEqual(
            sorted(mail_message.recipients()),
            [
                "jane@example.com",
                "joe@example.com",
            ],
        )

    def test_missing_receivers(self):
        """
        The command should complain if no receivers are given (and --admins or
        --managers are not set).
        """
        msg = (
            "You must specify some email recipients, or pass the --managers or "
            "--admin options."
        )
        with self.assertRaisesMessage(CommandError, msg):
            call_command("sendtestemail")

    def test_manager_receivers(self):
        """

        Verifies email sending to managers, ensuring that test emails are delivered to the email addresses specified in settings.MANAGERS.

        """
        call_command("sendtestemail", "--managers")
        self.assertEqual(len(mail.outbox), 1)
        mail_message = mail.outbox[0]
        self.assertEqual(
            sorted(mail_message.recipients()),
            [
                "admin_and_manager@example.com",
                "manager@example.com",
            ],
        )

    def test_admin_receivers(self):
        """
        Tests that the admin receivers correctly receive an email when the sendtestemail command is run with the --admins option.
        """
        call_command("sendtestemail", "--admins")
        self.assertEqual(len(mail.outbox), 1)
        mail_message = mail.outbox[0]
        self.assertEqual(
            sorted(mail_message.recipients()),
            [
                "admin@example.com",
                "admin_and_manager@example.com",
            ],
        )

    def test_manager_and_admin_receivers(self):
        """

        Tests that the sendtestemail command sends mail to both managers and admins.

        Verifies that email addresses specified in settings.MANAGERS and settings.ADMINS
        receive the test email, with email content and recipients validated accordingly.

        """
        call_command("sendtestemail", "--managers", "--admins")
        self.assertEqual(len(mail.outbox), 2)
        manager_mail = mail.outbox[0]
        self.assertEqual(
            sorted(manager_mail.recipients()),
            [
                "admin_and_manager@example.com",
                "manager@example.com",
            ],
        )
        admin_mail = mail.outbox[1]
        self.assertEqual(
            sorted(admin_mail.recipients()),
            [
                "admin@example.com",
                "admin_and_manager@example.com",
            ],
        )
