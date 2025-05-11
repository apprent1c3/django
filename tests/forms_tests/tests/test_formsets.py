import datetime
from collections import Counter
from unittest import mock

from django.core.exceptions import ValidationError
from django.forms import (
    BaseForm,
    CharField,
    DateField,
    FileField,
    Form,
    IntegerField,
    SplitDateTimeField,
    formsets,
)
from django.forms.formsets import (
    INITIAL_FORM_COUNT,
    MAX_NUM_FORM_COUNT,
    MIN_NUM_FORM_COUNT,
    TOTAL_FORM_COUNT,
    BaseFormSet,
    ManagementForm,
    all_valid,
    formset_factory,
)
from django.forms.renderers import (
    DjangoTemplates,
    TemplatesSetting,
    get_default_renderer,
)
from django.forms.utils import ErrorList
from django.forms.widgets import HiddenInput
from django.test import SimpleTestCase

from . import jinja2_tests


class Choice(Form):
    choice = CharField()
    votes = IntegerField()


ChoiceFormSet = formset_factory(Choice)


class ChoiceFormsetWithNonFormError(ChoiceFormSet):
    def clean(self):
        super().clean()
        raise ValidationError("non-form error")


class FavoriteDrinkForm(Form):
    name = CharField()


class BaseFavoriteDrinksFormSet(BaseFormSet):
    def clean(self):
        """
        Checks for and prevents duplicate drink names in the cleaned data, raising an error if a duplicate is found to ensure data consistency.
        """
        seen_drinks = []

        for drink in self.cleaned_data:
            if drink["name"] in seen_drinks:
                raise ValidationError("You may only specify a drink once.")

            seen_drinks.append(drink["name"])


# A FormSet that takes a list of favorite drinks and raises an error if
# there are any duplicates.
FavoriteDrinksFormSet = formset_factory(
    FavoriteDrinkForm, formset=BaseFavoriteDrinksFormSet, extra=3
)


class CustomKwargForm(Form):
    def __init__(self, *args, custom_kwarg, **kwargs):
        self.custom_kwarg = custom_kwarg
        super().__init__(*args, **kwargs)


class FormsFormsetTestCase(SimpleTestCase):
    def make_choiceformset(
        self,
        formset_data=None,
        formset_class=ChoiceFormSet,
        total_forms=None,
        initial_forms=0,
        max_num_forms=0,
        min_num_forms=0,
        **kwargs,
    ):
        """
        Create a ChoiceFormSet instance from provided formset data.

        The formset data should be a list of tuples, where each tuple contains a choice and the number of votes.

        Returns a ChoiceFormSet instance, which can be used to validate and process the provided form data.

        :param formset_data: List of (choice, votes) tuples to populate the formset
        :param formset_class: The formset class to use (defaults to ChoiceFormSet)
        :param total_forms: The total number of forms to include in the formset
        :param initial_forms: The initial number of forms to display
        :param max_num_forms: The maximum number of forms allowed
        :param min_num_forms: The minimum number of forms required
        :param kwargs: Additional keyword arguments to pass to the formset class
        """
        kwargs.setdefault("prefix", "choices")
        kwargs.setdefault("auto_id", False)

        if formset_data is None:
            return formset_class(**kwargs)

        if total_forms is None:
            total_forms = len(formset_data)

        def prefixed(*args):
            args = (kwargs["prefix"],) + args
            return "-".join(args)

        data = {
            prefixed("TOTAL_FORMS"): str(total_forms),
            prefixed("INITIAL_FORMS"): str(initial_forms),
            prefixed("MAX_NUM_FORMS"): str(max_num_forms),
            prefixed("MIN_NUM_FORMS"): str(min_num_forms),
        }
        for i, (choice, votes) in enumerate(formset_data):
            data[prefixed(str(i), "choice")] = choice
            data[prefixed(str(i), "votes")] = votes

        return formset_class(data, **kwargs)

    def test_basic_formset(self):
        """
        Tests the creation and validation of a formset, including rendering it as HTML and verifying its behavior with and without initial data.
        """
        formset = self.make_choiceformset()
        self.assertHTMLEqual(
            str(formset),
            """<input type="hidden" name="choices-TOTAL_FORMS" value="1">
<input type="hidden" name="choices-INITIAL_FORMS" value="0">
<input type="hidden" name="choices-MIN_NUM_FORMS" value="0">
<input type="hidden" name="choices-MAX_NUM_FORMS" value="1000">
<div>Choice:<input type="text" name="choices-0-choice"></div>
<div>Votes:<input type="number" name="choices-0-votes"></div>""",
        )
        # FormSet are treated similarly to Forms. FormSet has an is_valid()
        # method, and a cleaned_data or errors attribute depending on whether
        # all the forms passed validation. However, unlike a Form, cleaned_data
        # and errors will be a list of dicts rather than a single dict.
        formset = self.make_choiceformset([("Calexico", "100")])
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.forms],
            [{"votes": 100, "choice": "Calexico"}],
        )

        # If a FormSet wasn't passed any data, is_valid() and has_changed()
        # return False.
        formset = self.make_choiceformset()
        self.assertFalse(formset.is_valid())
        self.assertFalse(formset.has_changed())

    def test_form_kwargs_formset(self):
        """
        Tests whether custom keyword arguments passed to a formset instance are correctly propagated to its underlying forms.
        """
        FormSet = formset_factory(CustomKwargForm, extra=2)
        formset = FormSet(form_kwargs={"custom_kwarg": 1})
        for form in formset:
            self.assertTrue(hasattr(form, "custom_kwarg"))
            self.assertEqual(form.custom_kwarg, 1)

    def test_form_kwargs_formset_dynamic(self):
        """
        Tests that form keyword arguments can be passed dynamically to forms within a formset, 
        overriding any static form keyword arguments specified when creating the formset.
        """

        class DynamicBaseFormSet(BaseFormSet):
            def get_form_kwargs(self, index):
                return {"custom_kwarg": index}

        DynamicFormSet = formset_factory(
            CustomKwargForm, formset=DynamicBaseFormSet, extra=2
        )
        formset = DynamicFormSet(form_kwargs={"custom_kwarg": "ignored"})
        for i, form in enumerate(formset):
            self.assertTrue(hasattr(form, "custom_kwarg"))
            self.assertEqual(form.custom_kwarg, i)

    def test_form_kwargs_empty_form(self):
        FormSet = formset_factory(CustomKwargForm)
        formset = FormSet(form_kwargs={"custom_kwarg": 1})
        self.assertTrue(hasattr(formset.empty_form, "custom_kwarg"))
        self.assertEqual(formset.empty_form.custom_kwarg, 1)

    def test_empty_permitted_ignored_empty_form(self):
        formset = ArticleFormSet(form_kwargs={"empty_permitted": False})
        self.assertIs(formset.empty_form.empty_permitted, True)

    def test_formset_validation(self):
        # FormSet instances can also have an error attribute if validation failed for
        # any of the forms.
        formset = self.make_choiceformset([("Calexico", "")])
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.errors, [{"votes": ["This field is required."]}])

    def test_formset_validation_count(self):
        """
        Verifies that a formset's ManagementForm is validated once and each form in the formset is cleaned once during formset validation.
        """

        def make_method_counter(func):
            """
            Return a wrapped version of the input function along with a counter object, 
            enabling tracking of the number of times the function is called.
            """
            counter = Counter()
            counter.call_count = 0

            def mocked_func(*args, **kwargs):
                counter.call_count += 1
                return func(*args, **kwargs)

            return mocked_func, counter

        mocked_is_valid, is_valid_counter = make_method_counter(
            formsets.ManagementForm.is_valid
        )
        mocked_full_clean, full_clean_counter = make_method_counter(BaseForm.full_clean)
        formset = self.make_choiceformset(
            [("Calexico", "100"), ("Any1", "42"), ("Any2", "101")]
        )

        with (
            mock.patch(
                "django.forms.formsets.ManagementForm.is_valid", mocked_is_valid
            ),
            mock.patch("django.forms.forms.BaseForm.full_clean", mocked_full_clean),
        ):
            self.assertTrue(formset.is_valid())
        self.assertEqual(is_valid_counter.call_count, 1)
        self.assertEqual(full_clean_counter.call_count, 4)

    def test_formset_has_changed(self):
        """
        Tests whether a formset's has_changed method behaves correctly, returning True when any data is passed to its forms, regardless of formset validation.
        """
        blank_formset = self.make_choiceformset([("", "")])
        self.assertFalse(blank_formset.has_changed())
        # invalid formset
        invalid_formset = self.make_choiceformset([("Calexico", "")])
        self.assertFalse(invalid_formset.is_valid())
        self.assertTrue(invalid_formset.has_changed())
        # valid formset
        valid_formset = self.make_choiceformset([("Calexico", "100")])
        self.assertTrue(valid_formset.is_valid())
        self.assertTrue(valid_formset.has_changed())

    def test_formset_initial_data(self):
        """
        A FormSet can be prefilled with existing data by providing a list of
        dicts to the `initial` argument. By default, an extra blank form is
        included.
        """
        formset = self.make_choiceformset(
            initial=[{"choice": "Calexico", "votes": 100}]
        )
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            '<li>Choice: <input type="text" name="choices-0-choice" value="Calexico">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-0-votes" value="100"></li>'
            '<li>Choice: <input type="text" name="choices-1-choice"></li>'
            '<li>Votes: <input type="number" name="choices-1-votes"></li>',
        )

    def test_blank_form_unfilled(self):
        """A form that's displayed as blank may be submitted as blank."""
        formset = self.make_choiceformset(
            [("Calexico", "100"), ("", "")], initial_forms=1
        )
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.forms],
            [{"votes": 100, "choice": "Calexico"}, {}],
        )

    def test_second_form_partially_filled(self):
        """
        If at least one field is filled out on a blank form, it will be
        validated.
        """
        formset = self.make_choiceformset(
            [("Calexico", "100"), ("The Decemberists", "")], initial_forms=1
        )
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.errors, [{}, {"votes": ["This field is required."]}])

    def test_delete_prefilled_data(self):
        """
        Deleting prefilled data is an error. Removing data from form fields
        isn't the proper way to delete it.
        """
        formset = self.make_choiceformset([("", ""), ("", "")], initial_forms=1)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.errors,
            [
                {
                    "votes": ["This field is required."],
                    "choice": ["This field is required."],
                },
                {},
            ],
        )

    def test_displaying_more_than_one_blank_form(self):
        """
        Tests the ability to display multiple blank forms using Django's formset_factory with the `extra` argument, ensuring that each form is rendered correctly and data is validated properly when submitted.
        """
        ChoiceFormSet = formset_factory(Choice, extra=3)
        formset = ChoiceFormSet(auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            """<li>Choice: <input type="text" name="choices-0-choice"></li>
<li>Votes: <input type="number" name="choices-0-votes"></li>
<li>Choice: <input type="text" name="choices-1-choice"></li>
<li>Votes: <input type="number" name="choices-1-votes"></li>
<li>Choice: <input type="text" name="choices-2-choice"></li>
<li>Votes: <input type="number" name="choices-2-votes"></li>""",
        )
        # Since every form was displayed as blank, they are also accepted as
        # blank. This may seem a little strange, but min_num is used to require
        # a minimum number of forms to be completed.
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "",
            "choices-0-votes": "",
            "choices-1-choice": "",
            "choices-1-votes": "",
            "choices-2-choice": "",
            "choices-2-votes": "",
        }
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual([form.cleaned_data for form in formset.forms], [{}, {}, {}])

    def test_min_num_displaying_more_than_one_blank_form(self):
        """
        Tests that formset_factory's min_num argument allows displaying more than one blank form.
        """
        ChoiceFormSet = formset_factory(Choice, extra=1, min_num=1)
        formset = ChoiceFormSet(auto_id=False, prefix="choices")
        # Min_num forms are required; extra forms can be empty.
        self.assertFalse(formset.forms[0].empty_permitted)
        self.assertTrue(formset.forms[1].empty_permitted)
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            """<li>Choice: <input type="text" name="choices-0-choice"></li>
<li>Votes: <input type="number" name="choices-0-votes"></li>
<li>Choice: <input type="text" name="choices-1-choice"></li>
<li>Votes: <input type="number" name="choices-1-votes"></li>""",
        )

    def test_min_num_displaying_more_than_one_blank_form_with_zero_extra(self):
        """More than 1 empty form can be displayed using min_num."""
        ChoiceFormSet = formset_factory(Choice, extra=0, min_num=3)
        formset = ChoiceFormSet(auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            """<li>Choice: <input type="text" name="choices-0-choice"></li>
<li>Votes: <input type="number" name="choices-0-votes"></li>
<li>Choice: <input type="text" name="choices-1-choice"></li>
<li>Votes: <input type="number" name="choices-1-votes"></li>
<li>Choice: <input type="text" name="choices-2-choice"></li>
<li>Votes: <input type="number" name="choices-2-votes"></li>""",
        )

    def test_single_form_completed(self):
        """
        Tests that a formset validates correctly when only one form is completed.
        """
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-1-choice": "",
            "choices-1-votes": "",
            "choices-2-choice": "",
            "choices-2-votes": "",
        }
        ChoiceFormSet = formset_factory(Choice, extra=3)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.forms],
            [{"votes": 100, "choice": "Calexico"}, {}, {}],
        )

    def test_formset_validate_max_flag(self):
        """
        Tests that formset validation correctly enforces the maximum number of forms when validate_max is True, raising a ValidationError if more forms are submitted than allowed.
        """
        data = {
            "choices-TOTAL_FORMS": "2",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "2",  # max number of forms - should be ignored
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice, extra=1, max_num=1, validate_max=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at most 1 form."])
        self.assertEqual(
            str(formset.non_form_errors()),
            '<ul class="errorlist nonform"><li>Please submit at most 1 form.</li></ul>',
        )

    def test_formset_validate_max_flag_custom_error(self):
        """
        Checks formset validation when the maximum number of allowed forms is exceeded, verifying that a custom error message is correctly displayed.
        """
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-MAX_NUM_FORMS": "2",
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice, extra=1, max_num=1, validate_max=True)
        formset = ChoiceFormSet(
            data,
            auto_id=False,
            prefix="choices",
            error_messages={
                "too_many_forms": "Number of submitted forms should be at most %(num)d."
            },
        )
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.non_form_errors(),
            ["Number of submitted forms should be at most 1."],
        )
        self.assertEqual(
            str(formset.non_form_errors()),
            '<ul class="errorlist nonform">'
            "<li>Number of submitted forms should be at most 1.</li></ul>",
        )

    def test_formset_validate_min_flag(self):
        """
        Tests that a formset validation error is raised when the minimum number of forms required is not met, as specified by the min_num and validate_min parameters.
        """
        data = {
            "choices-TOTAL_FORMS": "2",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms - should be ignored
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice, extra=1, min_num=3, validate_min=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at least 3 forms."])
        self.assertEqual(
            str(formset.non_form_errors()),
            '<ul class="errorlist nonform"><li>'
            "Please submit at least 3 forms.</li></ul>",
        )

    def test_formset_validate_min_flag_custom_formatted_error(self):
        """
        301
        \"\"\"
        Tests formset validation for the minimum number of forms with a custom error message.
        Verifies that the formset is invalid when the minimum number of forms is not met and 
        that the correct error message is displayed.

        """
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-MAX_NUM_FORMS": "0",
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice, extra=1, min_num=3, validate_min=True)
        formset = ChoiceFormSet(
            data,
            auto_id=False,
            prefix="choices",
            error_messages={
                "too_few_forms": "Number of submitted forms should be at least %(num)d."
            },
        )
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.non_form_errors(),
            ["Number of submitted forms should be at least 3."],
        )
        self.assertEqual(
            str(formset.non_form_errors()),
            '<ul class="errorlist nonform">'
            "<li>Number of submitted forms should be at least 3.</li></ul>",
        )

    def test_formset_validate_min_unchanged_forms(self):
        """
        Tests that the formset validation correctly handles the minimum number of forms required when some forms are unchanged and have initial data. Verifies that unchanged forms with initial data are not considered empty for the purposes of the minimum form count validation.
        """
        initial = [
            {"choice": "Zero", "votes": 0},
            {"choice": "One", "votes": 0},
        ]
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "2",
            "choices-MIN_NUM_FORMS": "0",
            "choices-MAX_NUM_FORMS": "2",
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",  # changed from initial
        }
        ChoiceFormSet = formset_factory(Choice, min_num=2, validate_min=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices", initial=initial)
        self.assertFalse(formset.forms[0].has_changed())
        self.assertTrue(formset.forms[1].has_changed())
        self.assertTrue(formset.is_valid())

    def test_formset_validate_min_excludes_empty_forms(self):
        """
        Tests that a formset with validate_min set to True correctly raises an error when no forms are filled in, excluding empty forms from consideration.
        """
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
        }
        ChoiceFormSet = formset_factory(
            Choice, extra=2, min_num=1, validate_min=True, can_delete=True
        )
        formset = ChoiceFormSet(data, prefix="choices")
        self.assertFalse(formset.has_changed())
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at least 1 form."])

    def test_second_form_partially_filled_2(self):
        """
        Tests if a partially filled form with required fields is considered invalid.
        """
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-1-choice": "The Decemberists",
            "choices-1-votes": "",  # missing value
            "choices-2-choice": "",
            "choices-2-votes": "",
        }
        ChoiceFormSet = formset_factory(Choice, extra=3)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.errors, [{}, {"votes": ["This field is required."]}, {}]
        )

    def test_more_initial_data(self):
        """
        Tests that a formset with initial data and extra forms works as expected, 
        verifying the rendering of the initial data and the extra empty forms.
        """
        initial = [{"choice": "Calexico", "votes": 100}]
        ChoiceFormSet = formset_factory(Choice, extra=3)
        formset = ChoiceFormSet(initial=initial, auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            '<li>Choice: <input type="text" name="choices-0-choice" value="Calexico">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-0-votes" value="100"></li>'
            '<li>Choice: <input type="text" name="choices-1-choice"></li>'
            '<li>Votes: <input type="number" name="choices-1-votes"></li>'
            '<li>Choice: <input type="text" name="choices-2-choice"></li>'
            '<li>Votes: <input type="number" name="choices-2-votes"></li>'
            '<li>Choice: <input type="text" name="choices-3-choice"></li>'
            '<li>Votes: <input type="number" name="choices-3-votes"></li>',
        )
        # Retrieving an empty form works. Tt shows up in the form list.
        self.assertTrue(formset.empty_form.empty_permitted)
        self.assertHTMLEqual(
            formset.empty_form.as_ul(),
            """<li>Choice: <input type="text" name="choices-__prefix__-choice"></li>
<li>Votes: <input type="number" name="choices-__prefix__-votes"></li>""",
        )

    def test_formset_with_deletion(self):
        """
        Test a formset with the can_delete argument enabled, verifying that the deletion of a form is correctly handled and the associated data is properly marked for deletion.
        """
        ChoiceFormSet = formset_factory(Choice, can_delete=True)
        initial = [
            {"choice": "Calexico", "votes": 100},
            {"choice": "Fergie", "votes": 900},
        ]
        formset = ChoiceFormSet(initial=initial, auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            '<li>Choice: <input type="text" name="choices-0-choice" value="Calexico">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-0-votes" value="100"></li>'
            '<li>Delete: <input type="checkbox" name="choices-0-DELETE"></li>'
            '<li>Choice: <input type="text" name="choices-1-choice" value="Fergie">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-1-votes" value="900"></li>'
            '<li>Delete: <input type="checkbox" name="choices-1-DELETE"></li>'
            '<li>Choice: <input type="text" name="choices-2-choice"></li>'
            '<li>Votes: <input type="number" name="choices-2-votes"></li>'
            '<li>Delete: <input type="checkbox" name="choices-2-DELETE"></li>',
        )
        # To delete something, set that form's special delete field to 'on'.
        # Let's go ahead and delete Fergie.
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "2",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-0-DELETE": "",
            "choices-1-choice": "Fergie",
            "choices-1-votes": "900",
            "choices-1-DELETE": "on",
            "choices-2-choice": "",
            "choices-2-votes": "",
            "choices-2-DELETE": "",
        }
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.forms],
            [
                {"votes": 100, "DELETE": False, "choice": "Calexico"},
                {"votes": 900, "DELETE": True, "choice": "Fergie"},
                {},
            ],
        )
        self.assertEqual(
            [form.cleaned_data for form in formset.deleted_forms],
            [{"votes": 900, "DELETE": True, "choice": "Fergie"}],
        )

    def test_formset_with_deletion_remove_deletion_flag(self):
        """
        Tests that a formset remains valid when a form is marked for deletion, even if the form contains errors.
        """

        class CheckForm(Form):
            field = IntegerField(min_value=100)

        data = {
            "check-TOTAL_FORMS": "3",  # the number of forms rendered
            "check-INITIAL_FORMS": "2",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "check-MAX_NUM_FORMS": "0",  # max number of forms
            "check-0-field": "200",
            "check-0-DELETE": "",
            "check-1-field": "50",
            "check-1-DELETE": "on",
            "check-2-field": "",
            "check-2-DELETE": "",
        }
        CheckFormSet = formset_factory(CheckForm, can_delete=True)
        formset = CheckFormSet(data, prefix="check")
        self.assertTrue(formset.is_valid())
        # If the deletion flag is removed, validation is enabled.
        data["check-1-DELETE"] = ""
        formset = CheckFormSet(data, prefix="check")
        self.assertFalse(formset.is_valid())

    def test_formset_with_deletion_invalid_deleted_form(self):
        """
        Tests that a formset with deletion enabled still validates correctly even when a deleted form would have been invalid, ensuring the `deleted_forms` functionality works as expected.
        """
        FavoriteDrinkFormset = formset_factory(form=FavoriteDrinkForm, can_delete=True)
        formset = FavoriteDrinkFormset(
            {
                "form-0-name": "",
                "form-0-DELETE": "on",  # no name!
                "form-TOTAL_FORMS": 1,
                "form-INITIAL_FORMS": 1,
                "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1,
            }
        )
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset._errors, [])
        self.assertEqual(len(formset.deleted_forms), 1)

    def test_formset_with_deletion_custom_widget(self):
        """
        Tests formsets with custom deletion widgets to ensure correct HTML rendering.
        """
        class DeletionAttributeFormSet(BaseFormSet):
            deletion_widget = HiddenInput

        class DeletionMethodFormSet(BaseFormSet):
            def get_deletion_widget(self):
                return HiddenInput(attrs={"class": "deletion"})

        tests = [
            (DeletionAttributeFormSet, '<input type="hidden" name="form-0-DELETE">'),
            (
                DeletionMethodFormSet,
                '<input class="deletion" type="hidden" name="form-0-DELETE">',
            ),
        ]
        for formset_class, delete_html in tests:
            with self.subTest(formset_class=formset_class.__name__):
                ArticleFormSet = formset_factory(
                    ArticleForm,
                    formset=formset_class,
                    can_delete=True,
                )
                formset = ArticleFormSet(auto_id=False)
                self.assertHTMLEqual(
                    "\n".join([form.as_ul() for form in formset.forms]),
                    (
                        f'<li>Title: <input type="text" name="form-0-title"></li>'
                        f'<li>Pub date: <input type="text" name="form-0-pub_date">'
                        f"{delete_html}</li>"
                    ),
                )

    def test_formsets_with_ordering(self):
        """
        Tests the behavior of formsets with ordering, specifically the can_order argument of formset_factory, which adds an integer ordering field to each form and allows forms to be ordered based on this field, with secondary ordering by form index in case of duplicates.
        """
        ChoiceFormSet = formset_factory(Choice, can_order=True)
        initial = [
            {"choice": "Calexico", "votes": 100},
            {"choice": "Fergie", "votes": 900},
        ]
        formset = ChoiceFormSet(initial=initial, auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            '<li>Choice: <input type="text" name="choices-0-choice" value="Calexico">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-0-votes" value="100"></li>'
            '<li>Order: <input type="number" name="choices-0-ORDER" value="1"></li>'
            '<li>Choice: <input type="text" name="choices-1-choice" value="Fergie">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-1-votes" value="900"></li>'
            '<li>Order: <input type="number" name="choices-1-ORDER" value="2"></li>'
            '<li>Choice: <input type="text" name="choices-2-choice"></li>'
            '<li>Votes: <input type="number" name="choices-2-votes"></li>'
            '<li>Order: <input type="number" name="choices-2-ORDER"></li>',
        )
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "2",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-0-ORDER": "1",
            "choices-1-choice": "Fergie",
            "choices-1-votes": "900",
            "choices-1-ORDER": "2",
            "choices-2-choice": "The Decemberists",
            "choices-2-votes": "500",
            "choices-2-ORDER": "0",
        }
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.ordered_forms],
            [
                {"votes": 500, "ORDER": 0, "choice": "The Decemberists"},
                {"votes": 100, "ORDER": 1, "choice": "Calexico"},
                {"votes": 900, "ORDER": 2, "choice": "Fergie"},
            ],
        )

    def test_formsets_with_ordering_custom_widget(self):
        """
        Tests that formsets with ordering and custom widget configuration correctly render the ordering field as a hidden input. The test covers two approaches to specifying the ordering widget: using the `ordering_widget` attribute and overriding the `get_ordering_widget` method.
        """
        class OrderingAttributeFormSet(BaseFormSet):
            ordering_widget = HiddenInput

        class OrderingMethodFormSet(BaseFormSet):
            def get_ordering_widget(self):
                return HiddenInput(attrs={"class": "ordering"})

        tests = (
            (OrderingAttributeFormSet, '<input type="hidden" name="form-0-ORDER">'),
            (
                OrderingMethodFormSet,
                '<input class="ordering" type="hidden" name="form-0-ORDER">',
            ),
        )
        for formset_class, order_html in tests:
            with self.subTest(formset_class=formset_class.__name__):
                ArticleFormSet = formset_factory(
                    ArticleForm, formset=formset_class, can_order=True
                )
                formset = ArticleFormSet(auto_id=False)
                self.assertHTMLEqual(
                    "\n".join(form.as_ul() for form in formset.forms),
                    (
                        '<li>Title: <input type="text" name="form-0-title"></li>'
                        '<li>Pub date: <input type="text" name="form-0-pub_date">'
                        "%s</li>" % order_html
                    ),
                )

    def test_empty_ordered_fields(self):
        """
        Tests that ordering fields can be left blank, resulting in those items being sorted below ordered ones.
        """
        data = {
            "choices-TOTAL_FORMS": "4",  # the number of forms rendered
            "choices-INITIAL_FORMS": "3",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-0-ORDER": "1",
            "choices-1-choice": "Fergie",
            "choices-1-votes": "900",
            "choices-1-ORDER": "2",
            "choices-2-choice": "The Decemberists",
            "choices-2-votes": "500",
            "choices-2-ORDER": "",
            "choices-3-choice": "Basia Bulat",
            "choices-3-votes": "50",
            "choices-3-ORDER": "",
        }
        ChoiceFormSet = formset_factory(Choice, can_order=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.ordered_forms],
            [
                {"votes": 100, "ORDER": 1, "choice": "Calexico"},
                {"votes": 900, "ORDER": 2, "choice": "Fergie"},
                {"votes": 500, "ORDER": None, "choice": "The Decemberists"},
                {"votes": 50, "ORDER": None, "choice": "Basia Bulat"},
            ],
        )

    def test_ordering_blank_fieldsets(self):
        """
        Tests that ordering works correctly when a formset contains no fieldsets.\"\"\"
        ```
        """
        data = {
            "choices-TOTAL_FORMS": "3",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
        }
        ChoiceFormSet = formset_factory(Choice, can_order=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.ordered_forms, [])

    def test_formset_with_ordering_and_deletion(self):
        """
        Tests a formset with ordering and deletion capabilities, verifying that forms are rendered correctly, validated successfully, and that order and deletion status are correctly applied to each form.
        """
        ChoiceFormSet = formset_factory(Choice, can_order=True, can_delete=True)
        initial = [
            {"choice": "Calexico", "votes": 100},
            {"choice": "Fergie", "votes": 900},
            {"choice": "The Decemberists", "votes": 500},
        ]
        formset = ChoiceFormSet(initial=initial, auto_id=False, prefix="choices")
        self.assertHTMLEqual(
            "\n".join(form.as_ul() for form in formset.forms),
            '<li>Choice: <input type="text" name="choices-0-choice" value="Calexico">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-0-votes" value="100"></li>'
            '<li>Order: <input type="number" name="choices-0-ORDER" value="1"></li>'
            '<li>Delete: <input type="checkbox" name="choices-0-DELETE"></li>'
            '<li>Choice: <input type="text" name="choices-1-choice" value="Fergie">'
            "</li>"
            '<li>Votes: <input type="number" name="choices-1-votes" value="900"></li>'
            '<li>Order: <input type="number" name="choices-1-ORDER" value="2"></li>'
            '<li>Delete: <input type="checkbox" name="choices-1-DELETE"></li>'
            '<li>Choice: <input type="text" name="choices-2-choice" '
            'value="The Decemberists"></li>'
            '<li>Votes: <input type="number" name="choices-2-votes" value="500"></li>'
            '<li>Order: <input type="number" name="choices-2-ORDER" value="3"></li>'
            '<li>Delete: <input type="checkbox" name="choices-2-DELETE"></li>'
            '<li>Choice: <input type="text" name="choices-3-choice"></li>'
            '<li>Votes: <input type="number" name="choices-3-votes"></li>'
            '<li>Order: <input type="number" name="choices-3-ORDER"></li>'
            '<li>Delete: <input type="checkbox" name="choices-3-DELETE"></li>',
        )
        # Let's delete Fergie, and put The Decemberists ahead of Calexico.
        data = {
            "choices-TOTAL_FORMS": "4",  # the number of forms rendered
            "choices-INITIAL_FORMS": "3",  # the number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
            "choices-0-ORDER": "1",
            "choices-0-DELETE": "",
            "choices-1-choice": "Fergie",
            "choices-1-votes": "900",
            "choices-1-ORDER": "2",
            "choices-1-DELETE": "on",
            "choices-2-choice": "The Decemberists",
            "choices-2-votes": "500",
            "choices-2-ORDER": "0",
            "choices-2-DELETE": "",
            "choices-3-choice": "",
            "choices-3-votes": "",
            "choices-3-ORDER": "",
            "choices-3-DELETE": "",
        }
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            [form.cleaned_data for form in formset.ordered_forms],
            [
                {
                    "votes": 500,
                    "DELETE": False,
                    "ORDER": 0,
                    "choice": "The Decemberists",
                },
                {"votes": 100, "DELETE": False, "ORDER": 1, "choice": "Calexico"},
            ],
        )
        self.assertEqual(
            [form.cleaned_data for form in formset.deleted_forms],
            [{"votes": 900, "DELETE": True, "ORDER": 2, "choice": "Fergie"}],
        )

    def test_invalid_deleted_form_with_ordering(self):
        """
        Tests that a valid formset can still return ordered forms even if a deleted form would have been invalid, demonstrating robust formset handling in the presence of deleted, potentially invalid forms.
        """
        FavoriteDrinkFormset = formset_factory(
            form=FavoriteDrinkForm, can_delete=True, can_order=True
        )
        formset = FavoriteDrinkFormset(
            {
                "form-0-name": "",
                "form-0-DELETE": "on",  # no name!
                "form-TOTAL_FORMS": 1,
                "form-INITIAL_FORMS": 1,
                "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1,
            }
        )
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.ordered_forms, [])

    def test_clean_hook(self):
        """
        Tests the clean hook functionality of the FavoriteDrinksFormSet, ensuring it correctly handles duplicate drink names and validates the formset accordingly.
        """
        # Start out with a some duplicate data.
        data = {
            "drinks-TOTAL_FORMS": "2",  # the number of forms rendered
            "drinks-INITIAL_FORMS": "0",  # the number of forms with initial data
            "drinks-MIN_NUM_FORMS": "0",  # min number of forms
            "drinks-MAX_NUM_FORMS": "0",  # max number of forms
            "drinks-0-name": "Gin and Tonic",
            "drinks-1-name": "Gin and Tonic",
        }
        formset = FavoriteDrinksFormSet(data, prefix="drinks")
        self.assertFalse(formset.is_valid())
        # Any errors raised by formset.clean() are available via the
        # formset.non_form_errors() method.
        for error in formset.non_form_errors():
            self.assertEqual(str(error), "You may only specify a drink once.")
        # The valid case still works.
        data["drinks-1-name"] = "Bloody Mary"
        formset = FavoriteDrinksFormSet(data, prefix="drinks")
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), [])

    def test_limiting_max_forms(self):
        """
        Tests the formset functionality with the max_num parameter to limit the maximum number of forms generated, verifying that it correctly restricts form creation when the maximum is set to zero.
        """
        # When not passed, max_num will take a high default value, leaving the
        # number of forms only controlled by the value of the extra parameter.
        LimitedFavoriteDrinkFormSet = formset_factory(FavoriteDrinkForm, extra=3)
        formset = LimitedFavoriteDrinkFormSet()
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """<div><label for="id_form-0-name">Name:</label>
            <input type="text" name="form-0-name" id="id_form-0-name"></div>
<div><label for="id_form-1-name">Name:</label>
<input type="text" name="form-1-name" id="id_form-1-name"></div>
<div><label for="id_form-2-name">Name:</label>
<input type="text" name="form-2-name" id="id_form-2-name"></div>""",
        )
        # If max_num is 0 then no form is rendered at all.
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=3, max_num=0
        )
        formset = LimitedFavoriteDrinkFormSet()
        self.assertEqual(formset.forms, [])

    def test_limited_max_forms_two(self):
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=5, max_num=2
        )
        formset = LimitedFavoriteDrinkFormSet()
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """<div><label for="id_form-0-name">Name:</label>
<input type="text" name="form-0-name" id="id_form-0-name"></div>
<div><label for="id_form-1-name">Name:</label>
<input type="text" name="form-1-name" id="id_form-1-name"></div>""",
        )

    def test_limiting_extra_lest_than_max_num(self):
        """max_num has no effect when extra is less than max_num."""
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=1, max_num=2
        )
        formset = LimitedFavoriteDrinkFormSet()
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """<div><label for="id_form-0-name">Name:</label>
<input type="text" name="form-0-name" id="id_form-0-name"></div>""",
        )

    def test_max_num_with_initial_data(self):
        # When not passed, max_num will take a high default value, leaving the
        # number of forms only controlled by the value of the initial and extra
        # parameters.
        LimitedFavoriteDrinkFormSet = formset_factory(FavoriteDrinkForm, extra=1)
        formset = LimitedFavoriteDrinkFormSet(initial=[{"name": "Fernet and Coke"}])
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """
            <div><label for="id_form-0-name">Name:</label>
            <input type="text" name="form-0-name" value="Fernet and Coke"
                id="id_form-0-name"></div>
            <div><label for="id_form-1-name">Name:</label>
            <input type="text" name="form-1-name" id="id_form-1-name"></div>
            """,
        )

    def test_max_num_zero(self):
        """
        If max_num is 0 then no form is rendered at all, regardless of extra,
        unless initial data is present.
        """
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=1, max_num=0
        )
        formset = LimitedFavoriteDrinkFormSet()
        self.assertEqual(formset.forms, [])

    def test_max_num_zero_with_initial(self):
        # initial trumps max_num
        initial = [
            {"name": "Fernet and Coke"},
            {"name": "Bloody Mary"},
        ]
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=1, max_num=0
        )
        formset = LimitedFavoriteDrinkFormSet(initial=initial)
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """
            <div><label for="id_form-0-name">Name:</label>
            <input id="id_form-0-name" name="form-0-name" type="text"
                value="Fernet and Coke"></div>
            <div><label for="id_form-1-name">Name:</label>
            <input id="id_form-1-name" name="form-1-name" type="text"
                value="Bloody Mary"></div>
            """,
        )

    def test_more_initial_than_max_num(self):
        """
        Verifies that when the number of initial forms exceeds the maximum allowed, a formset will display all initial forms without adding extra forms beyond the maximum.
        """
        initial = [
            {"name": "Gin Tonic"},
            {"name": "Bloody Mary"},
            {"name": "Jack and Coke"},
        ]
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=1, max_num=2
        )
        formset = LimitedFavoriteDrinkFormSet(initial=initial)
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """
            <div><label for="id_form-0-name">Name:</label>
            <input id="id_form-0-name" name="form-0-name" type="text" value="Gin Tonic">
            </div>
            <div><label for="id_form-1-name">Name:</label>
            <input id="id_form-1-name" name="form-1-name" type="text"
                value="Bloody Mary"></div>
            <div><label for="id_form-2-name">Name:</label>
            <input id="id_form-2-name" name="form-2-name" type="text"
                value="Jack and Coke"></div>
            """,
        )

    def test_default_absolute_max(self):
        # absolute_max defaults to 2 * DEFAULT_MAX_NUM if max_num is None.
        """
        Checks that the formset has a default absolute maximum number of forms (2000) and that attempting to submit beyond that limit returns an error, enforcing the maximum of 1000 forms per submission.
        """
        data = {
            "form-TOTAL_FORMS": 2001,
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = FavoriteDrinksFormSet(data=data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 1000 forms."],
        )
        self.assertEqual(formset.absolute_max, 2000)

    def test_absolute_max(self):
        """
        Tests the validation of a formset with an absolute maximum number of forms, 
        ensuring it allows the specified maximum forms and rejects exceeding forms, 
        providing a corresponding error message.
        """
        data = {
            "form-TOTAL_FORMS": "2001",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        AbsoluteMaxFavoriteDrinksFormSet = formset_factory(
            FavoriteDrinkForm,
            absolute_max=3000,
        )
        formset = AbsoluteMaxFavoriteDrinksFormSet(data=data)
        self.assertIs(formset.is_valid(), True)
        self.assertEqual(len(formset.forms), 2001)
        # absolute_max provides a hard limit.
        data["form-TOTAL_FORMS"] = "3001"
        formset = AbsoluteMaxFavoriteDrinksFormSet(data=data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 3000)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 1000 forms."],
        )

    def test_absolute_max_with_max_num(self):
        """

        Tests the behavior of a formset with an absolute maximum number of forms.

        Verifies that the formset validation fails when the number of submitted forms exceeds the absolute maximum, 
        and that the correct error message is displayed.

        """
        data = {
            "form-TOTAL_FORMS": "1001",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        LimitedFavoriteDrinksFormSet = formset_factory(
            FavoriteDrinkForm,
            max_num=30,
            absolute_max=1000,
        )
        formset = LimitedFavoriteDrinksFormSet(data=data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 1000)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 30 forms."],
        )

    def test_absolute_max_invalid(self):
        """
        Tests that the formset_factory function raises a ValueError when 'absolute_max' is less than 'max_num', ensuring that the absolute maximum number of forms is not lower than the maximum number of forms allowed.
        """
        msg = "'absolute_max' must be greater or equal to 'max_num'."
        for max_num in [None, 31]:
            with self.subTest(max_num=max_num):
                with self.assertRaisesMessage(ValueError, msg):
                    formset_factory(FavoriteDrinkForm, max_num=max_num, absolute_max=30)

    def test_more_initial_form_result_in_one(self):
        """
        One form from initial and extra=3 with max_num=2 results in the one
        initial form and one extra.
        """
        LimitedFavoriteDrinkFormSet = formset_factory(
            FavoriteDrinkForm, extra=3, max_num=2
        )
        formset = LimitedFavoriteDrinkFormSet(initial=[{"name": "Gin Tonic"}])
        self.assertHTMLEqual(
            "\n".join(str(form) for form in formset.forms),
            """
            <div><label for="id_form-0-name">Name:</label>
            <input type="text" name="form-0-name" value="Gin Tonic" id="id_form-0-name">
            </div>
            <div><label for="id_form-1-name">Name:</label>
            <input type="text" name="form-1-name" id="id_form-1-name"></div>""",
        )

    def test_management_form_field_names(self):
        """The management form class has field names matching the constants."""
        self.assertCountEqual(
            ManagementForm.base_fields,
            [
                TOTAL_FORM_COUNT,
                INITIAL_FORM_COUNT,
                MIN_NUM_FORM_COUNT,
                MAX_NUM_FORM_COUNT,
            ],
        )

    def test_management_form_prefix(self):
        """
        Verifies that the management form prefix of a FavoriteDrinksFormSet is consistently set to 'form', regardless of the formset's initialization parameters.
        """
        formset = FavoriteDrinksFormSet()
        self.assertEqual(formset.management_form.prefix, "form")
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = FavoriteDrinksFormSet(data=data)
        self.assertEqual(formset.management_form.prefix, "form")
        formset = FavoriteDrinksFormSet(initial={})
        self.assertEqual(formset.management_form.prefix, "form")

    def test_non_form_errors(self):
        """

        Tests that the formset correctly handles errors when a drink is specified multiple times.

        Verifies that the formset is invalid and that the expected error message is returned.

        """
        data = {
            "drinks-TOTAL_FORMS": "2",  # the number of forms rendered
            "drinks-INITIAL_FORMS": "0",  # the number of forms with initial data
            "drinks-MIN_NUM_FORMS": "0",  # min number of forms
            "drinks-MAX_NUM_FORMS": "0",  # max number of forms
            "drinks-0-name": "Gin and Tonic",
            "drinks-1-name": "Gin and Tonic",
        }
        formset = FavoriteDrinksFormSet(data, prefix="drinks")
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.non_form_errors(), ["You may only specify a drink once."]
        )
        self.assertEqual(
            str(formset.non_form_errors()),
            '<ul class="errorlist nonform"><li>'
            "You may only specify a drink once.</li></ul>",
        )

    def test_formset_iteration(self):
        """
        Tests the iteration behavior of formset instances, including their ability to be iterated over and indexed, as well as custom iteration behavior implemented through subclasses.
        """
        ChoiceFormset = formset_factory(Choice, extra=3)
        formset = ChoiceFormset()
        # An iterated formset yields formset.forms.
        forms = list(formset)
        self.assertEqual(forms, formset.forms)
        self.assertEqual(len(formset), len(forms))
        # A formset may be indexed to retrieve its forms.
        self.assertEqual(formset[0], forms[0])
        with self.assertRaises(IndexError):
            formset[3]

        # Formsets can override the default iteration order
        class BaseReverseFormSet(BaseFormSet):
            def __iter__(self):
                return reversed(self.forms)

            def __getitem__(self, idx):
                return super().__getitem__(len(self) - idx - 1)

        ReverseChoiceFormset = formset_factory(Choice, BaseReverseFormSet, extra=3)
        reverse_formset = ReverseChoiceFormset()
        # __iter__() modifies the rendering order.
        # Compare forms from "reverse" formset with forms from original formset
        self.assertEqual(str(reverse_formset[0]), str(forms[-1]))
        self.assertEqual(str(reverse_formset[1]), str(forms[-2]))
        self.assertEqual(len(reverse_formset), len(forms))

    def test_formset_nonzero(self):
        """
        Checks that an empty formset evaluates as True, even without any forms.
        """
        ChoiceFormset = formset_factory(Choice, extra=0)
        formset = ChoiceFormset()
        self.assertEqual(len(formset.forms), 0)
        self.assertTrue(formset)

    def test_formset_splitdatetimefield(self):
        """
        Tests the validity of a formset containing a SplitDateTimeField with initial value set to the current date and time, ensuring it correctly handles date and time data.
        """

        class SplitDateTimeForm(Form):
            when = SplitDateTimeField(initial=datetime.datetime.now)

        SplitDateTimeFormSet = formset_factory(SplitDateTimeForm)
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-when_0": "1904-06-16",
            "form-0-when_1": "15:51:33",
        }
        formset = SplitDateTimeFormSet(data)
        self.assertTrue(formset.is_valid())

    def test_formset_error_class(self):
        """
        Verifies that forms within a formset utilize the formset's specified error class.
        """

        class CustomErrorList(ErrorList):
            pass

        formset = FavoriteDrinksFormSet(error_class=CustomErrorList)
        self.assertEqual(formset.forms[0].error_class, CustomErrorList)

    def test_formset_calls_forms_is_valid(self):
        """

        Verifies that a formset calls the is_valid method on each of its forms when validating the entire formset.

        """

        class AnotherChoice(Choice):
            def is_valid(self):
                self.is_valid_called = True
                return super().is_valid()

        AnotherChoiceFormSet = formset_factory(AnotherChoice)
        data = {
            "choices-TOTAL_FORMS": "1",  # number of forms rendered
            "choices-INITIAL_FORMS": "0",  # number of forms with initial data
            "choices-MIN_NUM_FORMS": "0",  # min number of forms
            "choices-MAX_NUM_FORMS": "0",  # max number of forms
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
        }
        formset = AnotherChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertTrue(formset.is_valid())
        self.assertTrue(all(form.is_valid_called for form in formset.forms))

    def test_hard_limit_on_instantiated_forms(self):
        """
        Tests that a formset enforces its hard limit on the number of instantiated forms, even when the user submits more forms than allowed.
        """
        # reduce the default limit of 1000 temporarily for testing
        _old_DEFAULT_MAX_NUM = formsets.DEFAULT_MAX_NUM
        try:
            formsets.DEFAULT_MAX_NUM = 2
            ChoiceFormSet = formset_factory(Choice, max_num=1)
            # someone fiddles with the mgmt form data...
            formset = ChoiceFormSet(
                {
                    "choices-TOTAL_FORMS": "4",
                    "choices-INITIAL_FORMS": "0",
                    "choices-MIN_NUM_FORMS": "0",  # min number of forms
                    "choices-MAX_NUM_FORMS": "4",
                    "choices-0-choice": "Zero",
                    "choices-0-votes": "0",
                    "choices-1-choice": "One",
                    "choices-1-votes": "1",
                    "choices-2-choice": "Two",
                    "choices-2-votes": "2",
                    "choices-3-choice": "Three",
                    "choices-3-votes": "3",
                },
                prefix="choices",
            )
            # But we still only instantiate 3 forms
            self.assertEqual(len(formset.forms), 3)
            # and the formset isn't valid
            self.assertFalse(formset.is_valid())
        finally:
            formsets.DEFAULT_MAX_NUM = _old_DEFAULT_MAX_NUM

    def test_increase_hard_limit(self):
        """
        Tests that the built-in formset limit can be increased by setting a higher max_num value, allowing more forms to be created than the default maximum.
        """
        # reduce the default limit of 1000 temporarily for testing
        _old_DEFAULT_MAX_NUM = formsets.DEFAULT_MAX_NUM
        try:
            formsets.DEFAULT_MAX_NUM = 3
            # for this form, we want a limit of 4
            ChoiceFormSet = formset_factory(Choice, max_num=4)
            formset = ChoiceFormSet(
                {
                    "choices-TOTAL_FORMS": "4",
                    "choices-INITIAL_FORMS": "0",
                    "choices-MIN_NUM_FORMS": "0",  # min number of forms
                    "choices-MAX_NUM_FORMS": "4",
                    "choices-0-choice": "Zero",
                    "choices-0-votes": "0",
                    "choices-1-choice": "One",
                    "choices-1-votes": "1",
                    "choices-2-choice": "Two",
                    "choices-2-votes": "2",
                    "choices-3-choice": "Three",
                    "choices-3-votes": "3",
                },
                prefix="choices",
            )
            # Four forms are instantiated and no exception is raised
            self.assertEqual(len(formset.forms), 4)
        finally:
            formsets.DEFAULT_MAX_NUM = _old_DEFAULT_MAX_NUM

    def test_non_form_errors_run_full_clean(self):
        """
        Tests that calling non_form_errors on a formset triggers full_clean when is_valid has not been called.
        """

        class BaseCustomFormSet(BaseFormSet):
            def clean(self):
                raise ValidationError("This is a non-form error")

        ChoiceFormSet = formset_factory(Choice, formset=BaseCustomFormSet)
        data = {
            "choices-TOTAL_FORMS": "1",
            "choices-INITIAL_FORMS": "0",
        }
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertIsInstance(formset.non_form_errors(), ErrorList)
        self.assertEqual(list(formset.non_form_errors()), ["This is a non-form error"])

    def test_validate_max_ignores_forms_marked_for_deletion(self):
        """
        Verifies that form validation with ``max_num`` constraint ignores forms marked for deletion.
        """
        class CheckForm(Form):
            field = IntegerField()

        data = {
            "check-TOTAL_FORMS": "2",
            "check-INITIAL_FORMS": "0",
            "check-MAX_NUM_FORMS": "1",
            "check-0-field": "200",
            "check-0-DELETE": "",
            "check-1-field": "50",
            "check-1-DELETE": "on",
        }
        CheckFormSet = formset_factory(
            CheckForm, max_num=1, validate_max=True, can_delete=True
        )
        formset = CheckFormSet(data, prefix="check")
        self.assertTrue(formset.is_valid())

    def test_formset_total_error_count(self):
        """
        Tests that the total error count of a formset is accurately determined, covering various validation scenarios.
        """
        data = [  # formset_data, expected error count
            ([("Calexico", "100")], 0),
            ([("Calexico", "")], 1),
            ([("", "invalid")], 2),
            ([("Calexico", "100"), ("Calexico", "")], 1),
            ([("Calexico", ""), ("Calexico", "")], 2),
        ]
        for formset_data, expected_error_count in data:
            formset = self.make_choiceformset(formset_data)
            self.assertEqual(formset.total_error_count(), expected_error_count)

    def test_formset_total_error_count_with_non_form_errors(self):
        """
        Tests the total error count for a formset, including cases where non-form errors are present, to verify it accurately reflects the number of validation issues encountered during form processing.
        """
        data = {
            "choices-TOTAL_FORMS": "2",  # the number of forms rendered
            "choices-INITIAL_FORMS": "0",  # the number of forms with initial data
            "choices-MAX_NUM_FORMS": "2",  # max number of forms - should be ignored
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice, extra=1, max_num=1, validate_max=True)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertEqual(formset.total_error_count(), 1)
        data["choices-1-votes"] = ""
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertEqual(formset.total_error_count(), 2)

    def test_html_safe(self):
        formset = self.make_choiceformset()
        self.assertTrue(hasattr(formset, "__html__"))
        self.assertEqual(str(formset), formset.__html__())

    def test_can_delete_extra_formset_forms(self):
        """
        Tests that a formset with extra forms and can_delete set to True includes a delete field in each form. Verifies the correct number of forms are presented initially.
        """
        ChoiceFormFormset = formset_factory(form=Choice, can_delete=True, extra=2)
        formset = ChoiceFormFormset()
        self.assertEqual(len(formset), 2)
        self.assertIn("DELETE", formset.forms[0].fields)
        self.assertIn("DELETE", formset.forms[1].fields)

    def test_disable_delete_extra_formset_forms(self):
        """
        Tests the behavior of a formset with the 'can_delete_extra' parameter set to False, ensuring that the 'DELETE' field is only present on initial forms and not on extra forms.
        """
        ChoiceFormFormset = formset_factory(
            form=Choice,
            can_delete=True,
            can_delete_extra=False,
            extra=2,
        )
        formset = ChoiceFormFormset()
        self.assertEqual(len(formset), 2)
        self.assertNotIn("DELETE", formset.forms[0].fields)
        self.assertNotIn("DELETE", formset.forms[1].fields)

        formset = ChoiceFormFormset(initial=[{"choice": "Zero", "votes": "1"}])
        self.assertEqual(len(formset), 3)
        self.assertIn("DELETE", formset.forms[0].fields)
        self.assertNotIn("DELETE", formset.forms[1].fields)
        self.assertNotIn("DELETE", formset.forms[2].fields)
        self.assertNotIn("DELETE", formset.empty_form.fields)

        formset = ChoiceFormFormset(
            data={
                "form-0-choice": "Zero",
                "form-0-votes": "0",
                "form-0-DELETE": "on",
                "form-1-choice": "One",
                "form-1-votes": "1",
                "form-2-choice": "",
                "form-2-votes": "",
                "form-TOTAL_FORMS": "3",
                "form-INITIAL_FORMS": "1",
            },
            initial=[{"choice": "Zero", "votes": "1"}],
        )
        self.assertEqual(
            formset.cleaned_data,
            [
                {"choice": "Zero", "votes": 0, "DELETE": True},
                {"choice": "One", "votes": 1},
                {},
            ],
        )
        self.assertIs(formset._should_delete_form(formset.forms[0]), True)
        self.assertIs(formset._should_delete_form(formset.forms[1]), False)
        self.assertIs(formset._should_delete_form(formset.forms[2]), False)

    def test_template_name_uses_renderer_value(self):
        class CustomRenderer(TemplatesSetting):
            formset_template_name = "a/custom/formset/template.html"

        ChoiceFormSet = formset_factory(Choice, renderer=CustomRenderer)

        self.assertEqual(
            ChoiceFormSet().template_name, "a/custom/formset/template.html"
        )

    def test_template_name_can_be_overridden(self):
        class CustomFormSet(BaseFormSet):
            template_name = "a/custom/formset/template.html"

        ChoiceFormSet = formset_factory(Choice, formset=CustomFormSet)

        self.assertEqual(
            ChoiceFormSet().template_name, "a/custom/formset/template.html"
        )

    def test_custom_renderer(self):
        """
        Tests that a custom renderer passed to formset_factory is applied consistently across all forms, ErrorList, and management form components within the resulting formset.
        """
        from django.forms.renderers import Jinja2

        renderer = Jinja2()
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-0-choice": "Zero",
            "choices-0-votes": "",
            "choices-1-choice": "One",
            "choices-1-votes": "",
        }
        ChoiceFormSet = formset_factory(Choice, renderer=renderer)
        formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertEqual(formset.renderer, renderer)
        self.assertEqual(formset.forms[0].renderer, renderer)
        self.assertEqual(formset.management_form.renderer, renderer)
        self.assertEqual(formset.non_form_errors().renderer, renderer)
        self.assertEqual(formset.empty_form.renderer, renderer)

    def test_form_default_renderer(self):
        """
        Test that the default renderer associated with a form is used when creating a formset without an explicitly specified renderer. This ensures that the Form.default_renderer is respected in the absence of a renderer passed to the formset_factory.
        """

        class CustomRenderer(DjangoTemplates):
            pass

        class ChoiceWithDefaultRenderer(Choice):
            default_renderer = CustomRenderer()

        data = {
            "choices-TOTAL_FORMS": "1",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
        }

        ChoiceFormSet = formset_factory(ChoiceWithDefaultRenderer)
        formset = ChoiceFormSet(data, prefix="choices")
        self.assertEqual(
            formset.forms[0].renderer, ChoiceWithDefaultRenderer.default_renderer
        )
        self.assertEqual(
            formset.empty_form.renderer, ChoiceWithDefaultRenderer.default_renderer
        )
        default_renderer = get_default_renderer()
        self.assertIsInstance(formset.renderer, type(default_renderer))

    def test_form_default_renderer_class(self):
        """
        Tests whether the default renderer class specified in a form is used when no renderer is explicitly passed to the formset_factory.
        """

        class CustomRenderer(DjangoTemplates):
            pass

        class ChoiceWithDefaultRenderer(Choice):
            default_renderer = CustomRenderer

        data = {
            "choices-TOTAL_FORMS": "1",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
        }

        ChoiceFormSet = formset_factory(ChoiceWithDefaultRenderer)
        formset = ChoiceFormSet(data, prefix="choices")
        self.assertIsInstance(formset.forms[0].renderer, CustomRenderer)
        self.assertIsInstance(formset.empty_form.renderer, CustomRenderer)
        default_renderer = get_default_renderer()
        self.assertIsInstance(formset.renderer, type(default_renderer))

    def test_repr(self):
        """
        #: Tests the representation of various formset scenarios, including empty, valid, invalid, and partially invalid formsets, to ensure they produce the expected string representation.
        """
        valid_formset = self.make_choiceformset([("test", 1)])
        valid_formset.full_clean()
        invalid_formset = self.make_choiceformset([("test", "")])
        invalid_formset.full_clean()
        partially_invalid_formset = self.make_choiceformset(
            [("test", "1"), ("test", "")],
        )
        partially_invalid_formset.full_clean()
        invalid_formset_non_form_errors_only = self.make_choiceformset(
            [("test", "")],
            formset_class=ChoiceFormsetWithNonFormError,
        )
        invalid_formset_non_form_errors_only.full_clean()

        cases = [
            (
                self.make_choiceformset(),
                "<ChoiceFormSet: bound=False valid=Unknown total_forms=1>",
            ),
            (
                self.make_choiceformset(
                    formset_class=formset_factory(Choice, extra=10),
                ),
                "<ChoiceFormSet: bound=False valid=Unknown total_forms=10>",
            ),
            (
                self.make_choiceformset([]),
                "<ChoiceFormSet: bound=True valid=Unknown total_forms=0>",
            ),
            (
                self.make_choiceformset([("test", 1)]),
                "<ChoiceFormSet: bound=True valid=Unknown total_forms=1>",
            ),
            (valid_formset, "<ChoiceFormSet: bound=True valid=True total_forms=1>"),
            (invalid_formset, "<ChoiceFormSet: bound=True valid=False total_forms=1>"),
            (
                partially_invalid_formset,
                "<ChoiceFormSet: bound=True valid=False total_forms=2>",
            ),
            (
                invalid_formset_non_form_errors_only,
                "<ChoiceFormsetWithNonFormError: bound=True valid=False total_forms=1>",
            ),
        ]
        for formset, expected_repr in cases:
            with self.subTest(expected_repr=expected_repr):
                self.assertEqual(repr(formset), expected_repr)

    def test_repr_do_not_trigger_validation(self):
        """
        Tests that the repr function of a ChoiceFormset does not trigger form validation, 
        while the is_valid method does.
        """
        formset = self.make_choiceformset([("test", 1)])
        with mock.patch.object(formset, "full_clean") as mocked_full_clean:
            repr(formset)
            mocked_full_clean.assert_not_called()
            formset.is_valid()
            mocked_full_clean.assert_called()


@jinja2_tests
class Jinja2FormsFormsetTestCase(FormsFormsetTestCase):
    pass


class FormsetAsTagTests(SimpleTestCase):
    def setUp(self):
        data = {
            "choices-TOTAL_FORMS": "1",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-MAX_NUM_FORMS": "0",
            "choices-0-choice": "Calexico",
            "choices-0-votes": "100",
        }
        self.formset = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.management_form_html = (
            '<input type="hidden" name="choices-TOTAL_FORMS" value="1">'
            '<input type="hidden" name="choices-INITIAL_FORMS" value="0">'
            '<input type="hidden" name="choices-MIN_NUM_FORMS" value="0">'
            '<input type="hidden" name="choices-MAX_NUM_FORMS" value="0">'
        )

    def test_as_table(self):
        self.assertHTMLEqual(
            self.formset.as_table(),
            self.management_form_html
            + (
                "<tr><th>Choice:</th><td>"
                '<input type="text" name="choices-0-choice" value="Calexico"></td></tr>'
                "<tr><th>Votes:</th><td>"
                '<input type="number" name="choices-0-votes" value="100"></td></tr>'
            ),
        )

    def test_as_p(self):
        self.assertHTMLEqual(
            self.formset.as_p(),
            self.management_form_html
            + (
                "<p>Choice: "
                '<input type="text" name="choices-0-choice" value="Calexico"></p>'
                '<p>Votes: <input type="number" name="choices-0-votes" value="100"></p>'
            ),
        )

    def test_as_ul(self):
        self.assertHTMLEqual(
            self.formset.as_ul(),
            self.management_form_html
            + (
                "<li>Choice: "
                '<input type="text" name="choices-0-choice" value="Calexico"></li>'
                "<li>Votes: "
                '<input type="number" name="choices-0-votes" value="100"></li>'
            ),
        )

    def test_as_div(self):
        self.assertHTMLEqual(
            self.formset.as_div(),
            self.management_form_html
            + (
                "<div>Choice: "
                '<input type="text" name="choices-0-choice" value="Calexico"></div>'
                '<div>Votes: <input type="number" name="choices-0-votes" value="100">'
                "</div>"
            ),
        )


@jinja2_tests
class Jinja2FormsetAsTagTests(FormsetAsTagTests):
    pass


class ArticleForm(Form):
    title = CharField()
    pub_date = DateField()


ArticleFormSet = formset_factory(ArticleForm)


class TestIsBoundBehavior(SimpleTestCase):
    def test_no_data_error(self):
        """
        Tests that an ArticleFormSet with no data raises the expected validation errors and produces the correct HTML representation of those errors.
        """
        formset = ArticleFormSet({})
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(
            formset.non_form_errors(),
            [
                "ManagementForm data is missing or has been tampered with. "
                "Missing fields: form-TOTAL_FORMS, form-INITIAL_FORMS. "
                "You may need to file a bug report if the issue persists.",
            ],
        )
        self.assertEqual(formset.errors, [])
        # Can still render the formset.
        self.assertHTMLEqual(
            str(formset),
            '<ul class="errorlist nonfield">'
            "<li>(Hidden field TOTAL_FORMS) This field is required.</li>"
            "<li>(Hidden field INITIAL_FORMS) This field is required.</li>"
            "</ul>"
            "<div>"
            '<input type="hidden" name="form-TOTAL_FORMS" id="id_form-TOTAL_FORMS">'
            '<input type="hidden" name="form-INITIAL_FORMS" id="id_form-INITIAL_FORMS">'
            '<input type="hidden" name="form-MIN_NUM_FORMS" id="id_form-MIN_NUM_FORMS">'
            '<input type="hidden" name="form-MAX_NUM_FORMS" id="id_form-MAX_NUM_FORMS">'
            "</div>\n",
        )

    def test_management_form_invalid_data(self):
        """
        Tests that an ArticleFormSet rejects invalid data when the management form data is incomplete or tampered with, verifying that correct error messages are displayed and that form-level validation behaves as expected.
        """
        data = {
            "form-TOTAL_FORMS": "two",
            "form-INITIAL_FORMS": "one",
        }
        formset = ArticleFormSet(data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(
            formset.non_form_errors(),
            [
                "ManagementForm data is missing or has been tampered with. "
                "Missing fields: form-TOTAL_FORMS, form-INITIAL_FORMS. "
                "You may need to file a bug report if the issue persists.",
            ],
        )
        self.assertEqual(formset.errors, [])
        # Can still render the formset.
        self.assertHTMLEqual(
            str(formset),
            '<ul class="errorlist nonfield">'
            "<li>(Hidden field TOTAL_FORMS) Enter a whole number.</li>"
            "<li>(Hidden field INITIAL_FORMS) Enter a whole number.</li>"
            "</ul>"
            "<div>"
            '<input type="hidden" name="form-TOTAL_FORMS" value="two" '
            'id="id_form-TOTAL_FORMS">'
            '<input type="hidden" name="form-INITIAL_FORMS" value="one" '
            'id="id_form-INITIAL_FORMS">'
            '<input type="hidden" name="form-MIN_NUM_FORMS" id="id_form-MIN_NUM_FORMS">'
            '<input type="hidden" name="form-MAX_NUM_FORMS" id="id_form-MAX_NUM_FORMS">'
            "</div>\n",
        )

    def test_customize_management_form_error(self):
        formset = ArticleFormSet(
            {}, error_messages={"missing_management_form": "customized"}
        )
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(formset.non_form_errors(), ["customized"])
        self.assertEqual(formset.errors, [])

    def test_with_management_data_attrs_work_fine(self):
        """
        Verifies that ArticleFormSet behaves correctly when initialized with management data attributes.

        Checks that the formset correctly interprets the total and initial form counts, and that the formset and its form are properly bound and validated.
        """
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
        }
        formset = ArticleFormSet(data)
        self.assertEqual(0, formset.initial_form_count())
        self.assertEqual(1, formset.total_form_count())
        self.assertTrue(formset.is_bound)
        self.assertTrue(formset.forms[0].is_bound)
        self.assertTrue(formset.is_valid())
        self.assertTrue(formset.forms[0].is_valid())
        self.assertEqual([{}], formset.cleaned_data)

    def test_form_errors_are_caught_by_formset(self):
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-0-title": "Test",
            "form-0-pub_date": "1904-06-16",
            "form-1-title": "Test",
            "form-1-pub_date": "",  # <-- this date is missing but required
        }
        formset = ArticleFormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            [{}, {"pub_date": ["This field is required."]}], formset.errors
        )

    def test_empty_forms_are_unbound(self):
        """
        Tests that empty forms within a formset are unbound, whether the formset itself is bound or unbound, and that their HTML representations are equal.
        """
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-0-title": "Test",
            "form-0-pub_date": "1904-06-16",
        }
        unbound_formset = ArticleFormSet()
        bound_formset = ArticleFormSet(data)
        empty_forms = [unbound_formset.empty_form, bound_formset.empty_form]
        # Empty forms should be unbound
        self.assertFalse(empty_forms[0].is_bound)
        self.assertFalse(empty_forms[1].is_bound)
        # The empty forms should be equal.
        self.assertHTMLEqual(empty_forms[0].as_p(), empty_forms[1].as_p())


@jinja2_tests
class TestIsBoundBehavior(TestIsBoundBehavior):
    pass


class TestEmptyFormSet(SimpleTestCase):
    def test_empty_formset_is_valid(self):
        """
        Tests that an empty formset still calls its clean method, ensuring validation occurs even when no forms are present.
        """

        class EmptyFsetWontValidate(BaseFormSet):
            def clean(self):
                raise ValidationError("Clean method called")

        EmptyFsetWontValidateFormset = formset_factory(
            FavoriteDrinkForm, extra=0, formset=EmptyFsetWontValidate
        )
        formset = EmptyFsetWontValidateFormset(
            data={"form-INITIAL_FORMS": "0", "form-TOTAL_FORMS": "0"},
            prefix="form",
        )
        formset2 = EmptyFsetWontValidateFormset(
            data={
                "form-INITIAL_FORMS": "0",
                "form-TOTAL_FORMS": "1",
                "form-0-name": "bah",
            },
            prefix="form",
        )
        self.assertFalse(formset.is_valid())
        self.assertFalse(formset2.is_valid())

    def test_empty_formset_media(self):
        """
        Verifies that media assets are properly included when creating an empty formset.
        """

        class MediaForm(Form):
            class Media:
                js = ("some-file.js",)

        self.assertIn("some-file.js", str(formset_factory(MediaForm, extra=0)().media))

    def test_empty_formset_is_multipart(self):
        """
        Tests that an empty formset is correctly identified as multipart when it contains a FileField, ensuring proper handling of file uploads in form processing.
        """

        class FileForm(Form):
            file = FileField()

        self.assertTrue(formset_factory(FileForm, extra=0)().is_multipart())


class AllValidTests(SimpleTestCase):
    def test_valid(self):
        """
        |/Test whether the all_valid function returns True when given two valid formsets.
        """
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-0-choice": "Zero",
            "choices-0-votes": "0",
            "choices-1-choice": "One",
            "choices-1-votes": "1",
        }
        ChoiceFormSet = formset_factory(Choice)
        formset1 = ChoiceFormSet(data, auto_id=False, prefix="choices")
        formset2 = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertIs(all_valid((formset1, formset2)), True)
        expected_errors = [{}, {}]
        self.assertEqual(formset1._errors, expected_errors)
        self.assertEqual(formset2._errors, expected_errors)

    def test_invalid(self):
        """
        Tests the all_valid function to ensure it correctly identifies invalid forms within a formset, even when multiple instances are provided.
        """
        data = {
            "choices-TOTAL_FORMS": "2",
            "choices-INITIAL_FORMS": "0",
            "choices-MIN_NUM_FORMS": "0",
            "choices-0-choice": "Zero",
            "choices-0-votes": "",
            "choices-1-choice": "One",
            "choices-1-votes": "",
        }
        ChoiceFormSet = formset_factory(Choice)
        formset1 = ChoiceFormSet(data, auto_id=False, prefix="choices")
        formset2 = ChoiceFormSet(data, auto_id=False, prefix="choices")
        self.assertIs(all_valid((formset1, formset2)), False)
        expected_errors = [
            {"votes": ["This field is required."]},
            {"votes": ["This field is required."]},
        ]
        self.assertEqual(formset1._errors, expected_errors)
        self.assertEqual(formset2._errors, expected_errors)
