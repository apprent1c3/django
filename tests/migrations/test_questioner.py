import datetime
from io import StringIO
from unittest import mock

from django.core.management.base import OutputWrapper
from django.db.migrations.questioner import (
    InteractiveMigrationQuestioner,
    MigrationQuestioner,
)
from django.db.models import NOT_PROVIDED
from django.test import SimpleTestCase
from django.test.utils import override_settings


class QuestionerTests(SimpleTestCase):
    @override_settings(
        INSTALLED_APPS=["migrations"],
        MIGRATION_MODULES={"migrations": None},
    )
    def test_ask_initial_with_disabled_migrations(self):
        questioner = MigrationQuestioner()
        self.assertIs(False, questioner.ask_initial("migrations"))

    def test_ask_not_null_alteration(self):
        """

        Tests the behavior of asking for not-null alteration using the MigrationQuestioner.

        This test checks that the MigrationQuestioner's ask_not_null_alteration method returns None when
        called with a given field name and model name, verifying that it handles this scenario correctly.

        """
        questioner = MigrationQuestioner()
        self.assertIsNone(
            questioner.ask_not_null_alteration("field_name", "model_name")
        )

    @mock.patch("builtins.input", return_value="2")
    def test_ask_not_null_alteration_not_provided(self, mock):
        """
        Tests the ask_not_null_alteration method of the InteractiveMigrationQuestioner class.

        This test verifies that when no alteration is provided for a not null field, 
        the method correctly returns NOT_PROVIDED. The test uses a mock input to 
        simulate user input and checks the output of the method against the expected value.

        :param self: The test instance
        :param mock: The mock object for the builtins.input function
        """
        questioner = InteractiveMigrationQuestioner(
            prompt_output=OutputWrapper(StringIO())
        )
        question = questioner.ask_not_null_alteration("field_name", "model_name")
        self.assertEqual(question, NOT_PROVIDED)


class QuestionerHelperMethodsTests(SimpleTestCase):
    def setUp(self):
        """
        Sets up the necessary components for interactive migration question handling.

        This method initializes the prompt output wrapper and creates an instance of the InteractiveMigrationQuestioner, which is used to pose questions during the migration process.

        The purpose of this setup is to facilitate user interaction and input validation, allowing for a more dynamic and controlled migration experience.

        Parameters are not applicable for this method as it is a part of the class setup.

        Returns
        -------
        None

        Note
        ----
        This method is typically used as part of a test case or scenario setup, where interactive migration question handling is required.
        """
        self.prompt = OutputWrapper(StringIO())
        self.questioner = InteractiveMigrationQuestioner(prompt_output=self.prompt)

    @mock.patch("builtins.input", return_value="datetime.timedelta(days=1)")
    def test_questioner_default_timedelta(self, mock_input):
        value = self.questioner._ask_default()
        self.assertEqual(value, datetime.timedelta(days=1))

    @mock.patch("builtins.input", return_value="")
    def test_questioner_default_no_user_entry(self, mock_input):
        value = self.questioner._ask_default(default="datetime.timedelta(days=1)")
        self.assertEqual(value, datetime.timedelta(days=1))

    @mock.patch("builtins.input", side_effect=["", "exit"])
    def test_questioner_no_default_no_user_entry(self, mock_input):
        """
        Tests that the _ask_default method of the Questioner class handles the case where no default value is provided and the user does not enter any input, and then enters 'exit'.

        The test verifies that the method raises a SystemExit exception in this scenario and that the expected prompt is displayed, instructing the user to enter some code or exit the program.
        """
        with self.assertRaises(SystemExit):
            self.questioner._ask_default()
        self.assertIn(
            "Please enter some code, or 'exit' (without quotes) to exit.",
            self.prompt.getvalue(),
        )

    @mock.patch("builtins.input", side_effect=["bad code", "exit"])
    def test_questioner_no_default_bad_user_entry_code(self, mock_input):
        """
        Tests the behavior of the questioner when a user provides an invalid code without a default value.

        This test case simulates a user entering an invalid code and then exiting. It verifies that the questioner raises a SystemExit exception and provides an appropriate error message to the user, indicating that their input was invalid.
        """
        with self.assertRaises(SystemExit):
            self.questioner._ask_default()
        self.assertIn("Invalid input: ", self.prompt.getvalue())

    @mock.patch("builtins.input", side_effect=["", "n"])
    def test_questioner_no_default_no_user_entry_boolean(self, mock_input):
        """
        Tests the questioner's _boolean_input method when no default value is provided and the user does not enter any input, then enters 'n' (no).

        Verifies that the method correctly returns False in this scenario, demonstrating the expected behavior when handling user input for boolean prompts with no default value and a negative user response.
        """
        value = self.questioner._boolean_input("Proceed?")
        self.assertIs(value, False)

    @mock.patch("builtins.input", return_value="")
    def test_questioner_default_no_user_entry_boolean(self, mock_input):
        """

        Tests the Questioner's boolean input functionality when no user input is provided, 
        with a default value set to True. Verifies that the function returns the default 
        value when no user input is entered.

        """
        value = self.questioner._boolean_input("Proceed?", default=True)
        self.assertIs(value, True)

    @mock.patch("builtins.input", side_effect=[10, "garbage", 1])
    def test_questioner_bad_user_choice(self, mock_input):
        """

        Makes a choice input request to the user, offering a list of choices.

        The function repeatedly prompts the user for input until a valid choice is made.
        It then returns the index of the chosen option (1-indexed).

        The list of available choices is specified by the 'choices' parameter, which should be a string
        where each character represents a distinct option.

        The function also prints a message to the user, which includes the question and the list of options.

        """
        question = "Make a choice:"
        value = self.questioner._choice_input(question, choices="abc")
        expected_msg = f"{question}\n" f" 1) a\n" f" 2) b\n" f" 3) c\n"
        self.assertIn(expected_msg, self.prompt.getvalue())
        self.assertEqual(value, 1)
