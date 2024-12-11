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
        questioner = MigrationQuestioner()
        self.assertIsNone(
            questioner.ask_not_null_alteration("field_name", "model_name")
        )

    @mock.patch("builtins.input", return_value="2")
    def test_ask_not_null_alteration_not_provided(self, mock):
        questioner = InteractiveMigrationQuestioner(
            prompt_output=OutputWrapper(StringIO())
        )
        question = questioner.ask_not_null_alteration("field_name", "model_name")
        self.assertEqual(question, NOT_PROVIDED)


class QuestionerHelperMethodsTests(SimpleTestCase):
    def setUp(self):
        """
        Sets up the necessary components for interactive migration question handling, including an output wrapper and a questioner instance. 

        The setup involves creating an :class:`~StringIO` output wrapper to capture and manage prompt output, and an instance of :class:`~InteractiveMigrationQuestioner` to handle migration-related queries in an interactive manner. 

        This method is used to initialize the environment for testing or executing migration scripts that require user input, ensuring a controlled and consistent interaction process.
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
        with self.assertRaises(SystemExit):
            self.questioner._ask_default()
        self.assertIn(
            "Please enter some code, or 'exit' (without quotes) to exit.",
            self.prompt.getvalue(),
        )

    @mock.patch("builtins.input", side_effect=["bad code", "exit"])
    def test_questioner_no_default_bad_user_entry_code(self, mock_input):
        with self.assertRaises(SystemExit):
            self.questioner._ask_default()
        self.assertIn("Invalid input: ", self.prompt.getvalue())

    @mock.patch("builtins.input", side_effect=["", "n"])
    def test_questioner_no_default_no_user_entry_boolean(self, mock_input):
        """

        Tests the _boolean_input method of the Questioner class.

        This method tests the case when the user does not provide a default value and 
        does not enter any input, followed by a negative response ('n'). 

        It verifies that the method correctly interprets the user's input and returns 
        the corresponding boolean value (False in this case).

        """
        value = self.questioner._boolean_input("Proceed?")
        self.assertIs(value, False)

    @mock.patch("builtins.input", return_value="")
    def test_questioner_default_no_user_entry_boolean(self, mock_input):
        """
        \".. _boolean_input:

        _boolean_input
        -------------

        Prompt the user with a boolean question and return the user's response.

        The function asks the user for input, providing a prompt and a default answer.
        If the user enters a response, it is validated and converted to a boolean value.
        If the user does not enter a response, the default answer is returned.

        :arg str prompt: The question to ask the user.
        :arg bool default: The default answer to return if the user does not enter a response.
        :return: The user's response as a boolean value.
        \"
        """
        value = self.questioner._boolean_input("Proceed?", default=True)
        self.assertIs(value, True)

    @mock.patch("builtins.input", side_effect=[10, "garbage", 1])
    def test_questioner_bad_user_choice(self, mock_input):
        question = "Make a choice:"
        value = self.questioner._choice_input(question, choices="abc")
        expected_msg = f"{question}\n" f" 1) a\n" f" 2) b\n" f" 3) c\n"
        self.assertIn(expected_msg, self.prompt.getvalue())
        self.assertEqual(value, 1)
