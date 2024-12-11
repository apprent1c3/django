import datetime
import re
from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.forms.formsets import formset_factory
from django.forms.models import (
    BaseModelFormSet,
    ModelForm,
    _get_foreign_key,
    inlineformset_factory,
    modelformset_factory,
)
from django.forms.renderers import DjangoTemplates
from django.http import QueryDict
from django.test import TestCase, skipUnlessDBFeature

from .models import (
    AlternateBook,
    Author,
    AuthorMeeting,
    BetterAuthor,
    Book,
    BookWithCustomPK,
    BookWithOptionalAltEditor,
    ClassyMexicanRestaurant,
    CustomPrimaryKey,
    Location,
    Membership,
    MexicanRestaurant,
    Owner,
    OwnerProfile,
    Person,
    Place,
    Player,
    Poem,
    Poet,
    Post,
    Price,
    Product,
    Repository,
    Restaurant,
    Revision,
    Team,
)


class DeletionTests(TestCase):
    def test_deletion(self):
        """

        Tests the deletion of a Poet instance using a ModelFormSet.

        Verifies that when a Poet instance is marked for deletion in the formset,
        it is removed from the database after the formset is saved.

        Checks the following scenarios:
        - The initial count of Poet instances before deletion
        - The validity of the formset after deletion
        - The count of Poet instances after deletion

        Ensures that the deletion process works correctly and the instance is successfully removed.

        """
        PoetFormSet = modelformset_factory(Poet, fields="__all__", can_delete=True)
        poet = Poet.objects.create(name="test")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": str(poet.pk),
            "form-0-name": "test",
            "form-0-DELETE": "on",
        }
        formset = PoetFormSet(data, queryset=Poet.objects.all())
        formset.save(commit=False)
        self.assertEqual(Poet.objects.count(), 1)

        formset.save()
        self.assertTrue(formset.is_valid())
        self.assertEqual(Poet.objects.count(), 0)

    def test_add_form_deletion_when_invalid(self):
        """
        Make sure that an add form that is filled out, but marked for deletion
        doesn't cause validation errors.
        """
        PoetFormSet = modelformset_factory(Poet, fields="__all__", can_delete=True)
        poet = Poet.objects.create(name="test")
        # One existing untouched and two new unvalid forms
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": str(poet.id),
            "form-0-name": "test",
            "form-1-id": "",
            "form-1-name": "x" * 1000,  # Too long
            "form-2-id": str(poet.id),  # Violate unique constraint
            "form-2-name": "test2",
        }
        formset = PoetFormSet(data, queryset=Poet.objects.all())
        # Make sure this form doesn't pass validation.
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(Poet.objects.count(), 1)

        # Then make sure that it *does* pass validation and delete the object,
        # even though the data in new forms aren't actually valid.
        data["form-0-DELETE"] = "on"
        data["form-1-DELETE"] = "on"
        data["form-2-DELETE"] = "on"
        formset = PoetFormSet(data, queryset=Poet.objects.all())
        self.assertIs(formset.is_valid(), True)
        formset.save()
        self.assertEqual(Poet.objects.count(), 0)

    def test_change_form_deletion_when_invalid(self):
        """
        Make sure that a change form that is filled out, but marked for deletion
        doesn't cause validation errors.
        """
        PoetFormSet = modelformset_factory(Poet, fields="__all__", can_delete=True)
        poet = Poet.objects.create(name="test")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": str(poet.id),
            "form-0-name": "x" * 1000,
        }
        formset = PoetFormSet(data, queryset=Poet.objects.all())
        # Make sure this form doesn't pass validation.
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(Poet.objects.count(), 1)

        # Then make sure that it *does* pass validation and delete the object,
        # even though the data isn't actually valid.
        data["form-0-DELETE"] = "on"
        formset = PoetFormSet(data, queryset=Poet.objects.all())
        self.assertIs(formset.is_valid(), True)
        formset.save()
        self.assertEqual(Poet.objects.count(), 0)

    def test_outdated_deletion(self):
        poet = Poet.objects.create(name="test")
        poem = Poem.objects.create(name="Brevity is the soul of wit", poet=poet)

        PoemFormSet = inlineformset_factory(
            Poet, Poem, fields="__all__", can_delete=True
        )

        # Simulate deletion of an object that doesn't exist in the database
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-0-id": str(poem.pk),
            "form-0-name": "foo",
            "form-1-id": str(poem.pk + 1),  # doesn't exist
            "form-1-name": "bar",
            "form-1-DELETE": "on",
        }
        formset = PoemFormSet(data, instance=poet, prefix="form")

        # The formset is valid even though poem.pk + 1 doesn't exist,
        # because it's marked for deletion anyway
        self.assertTrue(formset.is_valid())

        formset.save()

        # Make sure the save went through correctly
        self.assertEqual(Poem.objects.get(pk=poem.pk).name, "foo")
        self.assertEqual(poet.poem_set.count(), 1)
        self.assertFalse(Poem.objects.filter(pk=poem.pk + 1).exists())


class ModelFormsetTest(TestCase):
    def test_modelformset_factory_without_fields(self):
        """Regression for #19733"""
        message = (
            "Calling modelformset_factory without defining 'fields' or 'exclude' "
            "explicitly is prohibited."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            modelformset_factory(Author)

    def test_simple_save(self):
        qs = Author.objects.all()
        AuthorFormSet = modelformset_factory(Author, fields="__all__", extra=3)

        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 3)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-name">Name:</label>'
            '<input id="id_form-0-name" type="text" name="form-0-name" maxlength="100">'
            '<input type="hidden" name="form-0-id" id="id_form-0-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_form-1-name">Name:</label>'
            '<input id="id_form-1-name" type="text" name="form-1-name" maxlength="100">'
            '<input type="hidden" name="form-1-id" id="id_form-1-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_form-2-name">Name:</label>'
            '<input id="id_form-2-name" type="text" name="form-2-name" maxlength="100">'
            '<input type="hidden" name="form-2-id" id="id_form-2-id"></p>',
        )

        data = {
            "form-TOTAL_FORMS": "3",  # the number of forms rendered
            "form-INITIAL_FORMS": "0",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-name": "Charles Baudelaire",
            "form-1-name": "Arthur Rimbaud",
            "form-2-name": "",
        }

        formset = AuthorFormSet(data=data, queryset=qs)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 2)
        author1, author2 = saved
        self.assertEqual(author1, Author.objects.get(name="Charles Baudelaire"))
        self.assertEqual(author2, Author.objects.get(name="Arthur Rimbaud"))

        authors = list(Author.objects.order_by("name"))
        self.assertEqual(authors, [author2, author1])

        # Gah! We forgot Paul Verlaine. Let's create a formset to edit the
        # existing authors with an extra form to add him. We *could* pass in a
        # queryset to restrict the Author objects we edit, but in this case
        # we'll use it to display them in alphabetical order by name.

        qs = Author.objects.order_by("name")
        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", extra=1, can_delete=False
        )

        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 3)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-name">Name:</label>'
            '<input id="id_form-0-name" type="text" name="form-0-name" '
            'value="Arthur Rimbaud" maxlength="100">'
            '<input type="hidden" name="form-0-id" value="%d" id="id_form-0-id"></p>'
            % author2.id,
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_form-1-name">Name:</label>'
            '<input id="id_form-1-name" type="text" name="form-1-name" '
            'value="Charles Baudelaire" maxlength="100">'
            '<input type="hidden" name="form-1-id" value="%d" id="id_form-1-id"></p>'
            % author1.id,
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_form-2-name">Name:</label>'
            '<input id="id_form-2-name" type="text" name="form-2-name" maxlength="100">'
            '<input type="hidden" name="form-2-id" id="id_form-2-id"></p>',
        )

        data = {
            "form-TOTAL_FORMS": "3",  # the number of forms rendered
            "form-INITIAL_FORMS": "2",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-id": str(author2.id),
            "form-0-name": "Arthur Rimbaud",
            "form-1-id": str(author1.id),
            "form-1-name": "Charles Baudelaire",
            "form-2-name": "Paul Verlaine",
        }

        formset = AuthorFormSet(data=data, queryset=qs)
        self.assertTrue(formset.is_valid())

        # Only changed or new objects are returned from formset.save()
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        author3 = saved[0]
        self.assertEqual(author3, Author.objects.get(name="Paul Verlaine"))

        authors = list(Author.objects.order_by("name"))
        self.assertEqual(authors, [author2, author1, author3])

        # This probably shouldn't happen, but it will. If an add form was
        # marked for deletion, make sure we don't save that form.

        qs = Author.objects.order_by("name")
        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", extra=1, can_delete=True
        )

        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 4)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-name">Name:</label>'
            '<input id="id_form-0-name" type="text" name="form-0-name" '
            'value="Arthur Rimbaud" maxlength="100"></p>'
            '<p><label for="id_form-0-DELETE">Delete:</label>'
            '<input type="checkbox" name="form-0-DELETE" id="id_form-0-DELETE">'
            '<input type="hidden" name="form-0-id" value="%d" id="id_form-0-id"></p>'
            % author2.id,
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_form-1-name">Name:</label>'
            '<input id="id_form-1-name" type="text" name="form-1-name" '
            'value="Charles Baudelaire" maxlength="100"></p>'
            '<p><label for="id_form-1-DELETE">Delete:</label>'
            '<input type="checkbox" name="form-1-DELETE" id="id_form-1-DELETE">'
            '<input type="hidden" name="form-1-id" value="%d" id="id_form-1-id"></p>'
            % author1.id,
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_form-2-name">Name:</label>'
            '<input id="id_form-2-name" type="text" name="form-2-name" '
            'value="Paul Verlaine" maxlength="100"></p>'
            '<p><label for="id_form-2-DELETE">Delete:</label>'
            '<input type="checkbox" name="form-2-DELETE" id="id_form-2-DELETE">'
            '<input type="hidden" name="form-2-id" value="%d" id="id_form-2-id"></p>'
            % author3.id,
        )
        self.assertHTMLEqual(
            formset.forms[3].as_p(),
            '<p><label for="id_form-3-name">Name:</label>'
            '<input id="id_form-3-name" type="text" name="form-3-name" maxlength="100">'
            '</p><p><label for="id_form-3-DELETE">Delete:</label>'
            '<input type="checkbox" name="form-3-DELETE" id="id_form-3-DELETE">'
            '<input type="hidden" name="form-3-id" id="id_form-3-id"></p>',
        )

        data = {
            "form-TOTAL_FORMS": "4",  # the number of forms rendered
            "form-INITIAL_FORMS": "3",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-id": str(author2.id),
            "form-0-name": "Arthur Rimbaud",
            "form-1-id": str(author1.id),
            "form-1-name": "Charles Baudelaire",
            "form-2-id": str(author3.id),
            "form-2-name": "Paul Verlaine",
            "form-3-name": "Walt Whitman",
            "form-3-DELETE": "on",
        }

        formset = AuthorFormSet(data=data, queryset=qs)
        self.assertTrue(formset.is_valid())

        # No objects were changed or saved so nothing will come back.

        self.assertEqual(formset.save(), [])

        authors = list(Author.objects.order_by("name"))
        self.assertEqual(authors, [author2, author1, author3])

        # Let's edit a record to ensure save only returns that one record.

        data = {
            "form-TOTAL_FORMS": "4",  # the number of forms rendered
            "form-INITIAL_FORMS": "3",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-id": str(author2.id),
            "form-0-name": "Walt Whitman",
            "form-1-id": str(author1.id),
            "form-1-name": "Charles Baudelaire",
            "form-2-id": str(author3.id),
            "form-2-name": "Paul Verlaine",
            "form-3-name": "",
            "form-3-DELETE": "",
        }

        formset = AuthorFormSet(data=data, queryset=qs)
        self.assertTrue(formset.is_valid())

        # One record has changed.

        saved = formset.save()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0], Author.objects.get(name="Walt Whitman"))

    def test_commit_false(self):
        # Test the behavior of commit=False and save_m2m

        author1 = Author.objects.create(name="Charles Baudelaire")
        author2 = Author.objects.create(name="Paul Verlaine")
        author3 = Author.objects.create(name="Walt Whitman")

        meeting = AuthorMeeting.objects.create(created=date.today())
        meeting.authors.set(Author.objects.all())

        # create an Author instance to add to the meeting.

        author4 = Author.objects.create(name="John Steinbeck")

        AuthorMeetingFormSet = modelformset_factory(
            AuthorMeeting, fields="__all__", extra=1, can_delete=True
        )
        data = {
            "form-TOTAL_FORMS": "2",  # the number of forms rendered
            "form-INITIAL_FORMS": "1",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-id": str(meeting.id),
            "form-0-name": "2nd Tuesday of the Week Meeting",
            "form-0-authors": [author2.id, author1.id, author3.id, author4.id],
            "form-1-name": "",
            "form-1-authors": "",
            "form-1-DELETE": "",
        }
        formset = AuthorMeetingFormSet(data=data, queryset=AuthorMeeting.objects.all())
        self.assertTrue(formset.is_valid())

        instances = formset.save(commit=False)
        for instance in instances:
            instance.created = date.today()
            instance.save()
        formset.save_m2m()
        self.assertSequenceEqual(
            instances[0].authors.all(),
            [author1, author4, author2, author3],
        )

    def test_max_num(self):
        # Test the behavior of max_num with model formsets. It should allow
        # all existing related objects/inlines for a given object to be
        # displayed, but not allow the creation of new inlines beyond max_num.

        a1 = Author.objects.create(name="Charles Baudelaire")
        a2 = Author.objects.create(name="Paul Verlaine")
        a3 = Author.objects.create(name="Walt Whitman")

        qs = Author.objects.order_by("name")

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", max_num=None, extra=3
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 6)
        self.assertEqual(len(formset.extra_forms), 3)

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", max_num=4, extra=3
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 4)
        self.assertEqual(len(formset.extra_forms), 1)

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", max_num=0, extra=3
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 3)
        self.assertEqual(len(formset.extra_forms), 0)

        AuthorFormSet = modelformset_factory(Author, fields="__all__", max_num=None)
        formset = AuthorFormSet(queryset=qs)
        self.assertSequenceEqual(formset.get_queryset(), [a1, a2, a3])

        AuthorFormSet = modelformset_factory(Author, fields="__all__", max_num=0)
        formset = AuthorFormSet(queryset=qs)
        self.assertSequenceEqual(formset.get_queryset(), [a1, a2, a3])

        AuthorFormSet = modelformset_factory(Author, fields="__all__", max_num=4)
        formset = AuthorFormSet(queryset=qs)
        self.assertSequenceEqual(formset.get_queryset(), [a1, a2, a3])

    def test_min_num(self):
        # Test the behavior of min_num with model formsets. It should be
        # added to extra.
        """

        Tests the behavior of a formset when specifying the minimum number of forms.

        This test case verifies that a formset created with a minimum number of forms
        (min_num) will render at least that number of forms, even if the queryset is empty.
        It also checks that the extra parameter works as expected, adding additional
        forms to the minimum number specified.

        The test covers the following scenarios:

        * Creating a formset with no minimum number of forms and an empty queryset
        * Creating a formset with a minimum number of forms and an empty queryset
        * Creating a formset with a minimum number of forms, extra forms, and an empty queryset

        """
        qs = Author.objects.none()

        AuthorFormSet = modelformset_factory(Author, fields="__all__", extra=0)
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 0)

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", min_num=1, extra=0
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 1)

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", min_num=1, extra=1
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 2)

    def test_min_num_with_existing(self):
        # Test the behavior of min_num with existing objects.
        """
        Tests that a ModelFormSet with a minimum number of forms requirement 
        enforces this constraint when there are existing objects in the database.

        Verifies that the formset is initialized with the correct number of forms 
        when the minimum number of forms is set to 1 and there is at least one 
        existing object in the queryset.
        """
        Author.objects.create(name="Charles Baudelaire")
        qs = Author.objects.all()

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", extra=0, min_num=1
        )
        formset = AuthorFormSet(queryset=qs)
        self.assertEqual(len(formset.forms), 1)

    def test_custom_save_method(self):
        class PoetForm(forms.ModelForm):
            def save(self, commit=True):
                # change the name to "Vladimir Mayakovsky" just to be a jerk.
                author = super().save(commit=False)
                author.name = "Vladimir Mayakovsky"
                if commit:
                    author.save()
                return author

        PoetFormSet = modelformset_factory(Poet, fields="__all__", form=PoetForm)

        data = {
            "form-TOTAL_FORMS": "3",  # the number of forms rendered
            "form-INITIAL_FORMS": "0",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-name": "Walt Whitman",
            "form-1-name": "Charles Baudelaire",
            "form-2-name": "",
        }

        qs = Poet.objects.all()
        formset = PoetFormSet(data=data, queryset=qs)
        self.assertTrue(formset.is_valid())

        poets = formset.save()
        self.assertEqual(len(poets), 2)
        poet1, poet2 = poets
        self.assertEqual(poet1.name, "Vladimir Mayakovsky")
        self.assertEqual(poet2.name, "Vladimir Mayakovsky")

    def test_custom_form(self):
        """
        model_formset_factory() respects fields and exclude parameters of a
        custom form.
        """

        class PostForm1(forms.ModelForm):
            class Meta:
                model = Post
                fields = ("title", "posted")

        class PostForm2(forms.ModelForm):
            class Meta:
                model = Post
                exclude = ("subtitle",)

        PostFormSet = modelformset_factory(Post, form=PostForm1)
        formset = PostFormSet()
        self.assertNotIn("subtitle", formset.forms[0].fields)

        PostFormSet = modelformset_factory(Post, form=PostForm2)
        formset = PostFormSet()
        self.assertNotIn("subtitle", formset.forms[0].fields)

    def test_custom_queryset_init(self):
        """
        A queryset can be overridden in the formset's __init__() method.
        """
        Author.objects.create(name="Charles Baudelaire")
        Author.objects.create(name="Paul Verlaine")

        class BaseAuthorFormSet(BaseModelFormSet):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.queryset = Author.objects.filter(name__startswith="Charles")

        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", formset=BaseAuthorFormSet
        )
        formset = AuthorFormSet()
        self.assertEqual(len(formset.get_queryset()), 1)

    def test_model_inheritance(self):
        """
        Tests model formset functionality for the BetterAuthor model, specifically its inheritance behavior.

        The test suite covers several key scenarios:

        * Creation of a formset with a single empty form
        * Submission of form data to create a new BetterAuthor instance
        * Verification of the saved instance and its properties
        * Validation of the formset's HTML structure and auto-population of existing data
        * Testing the formset's behavior with both new and existing instances of the BetterAuthor model

        Ensures that the model formset correctly handles inheritance, data validation, and instance creation, providing a solid foundation for reliable and consistent form handling.
        """
        BetterAuthorFormSet = modelformset_factory(BetterAuthor, fields="__all__")
        formset = BetterAuthorFormSet()
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-name">Name:</label>'
            '<input id="id_form-0-name" type="text" name="form-0-name" maxlength="100">'
            '</p><p><label for="id_form-0-write_speed">Write speed:</label>'
            '<input type="number" name="form-0-write_speed" id="id_form-0-write_speed">'
            '<input type="hidden" name="form-0-author_ptr" id="id_form-0-author_ptr">'
            "</p>",
        )

        data = {
            "form-TOTAL_FORMS": "1",  # the number of forms rendered
            "form-INITIAL_FORMS": "0",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-author_ptr": "",
            "form-0-name": "Ernest Hemingway",
            "form-0-write_speed": "10",
        }

        formset = BetterAuthorFormSet(data)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (author1,) = saved
        self.assertEqual(author1, BetterAuthor.objects.get(name="Ernest Hemingway"))
        hemingway_id = BetterAuthor.objects.get(name="Ernest Hemingway").pk

        formset = BetterAuthorFormSet()
        self.assertEqual(len(formset.forms), 2)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-name">Name:</label>'
            '<input id="id_form-0-name" type="text" name="form-0-name" '
            'value="Ernest Hemingway" maxlength="100"></p>'
            '<p><label for="id_form-0-write_speed">Write speed:</label>'
            '<input type="number" name="form-0-write_speed" value="10" '
            'id="id_form-0-write_speed">'
            '<input type="hidden" name="form-0-author_ptr" value="%d" '
            'id="id_form-0-author_ptr"></p>' % hemingway_id,
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_form-1-name">Name:</label>'
            '<input id="id_form-1-name" type="text" name="form-1-name" maxlength="100">'
            '</p><p><label for="id_form-1-write_speed">Write speed:</label>'
            '<input type="number" name="form-1-write_speed" id="id_form-1-write_speed">'
            '<input type="hidden" name="form-1-author_ptr" id="id_form-1-author_ptr">'
            "</p>",
        )

        data = {
            "form-TOTAL_FORMS": "2",  # the number of forms rendered
            "form-INITIAL_FORMS": "1",  # the number of forms with initial data
            "form-MAX_NUM_FORMS": "",  # the max number of forms
            "form-0-author_ptr": hemingway_id,
            "form-0-name": "Ernest Hemingway",
            "form-0-write_speed": "10",
            "form-1-author_ptr": "",
            "form-1-name": "",
            "form-1-write_speed": "",
        }

        formset = BetterAuthorFormSet(data)
        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.save(), [])

    def test_inline_formsets(self):
        # We can also create a formset that is tied to a parent model. This is
        # how the admin system's edit inline functionality works.

        AuthorBooksFormSet = inlineformset_factory(
            Author, Book, can_delete=False, extra=3, fields="__all__"
        )
        author = Author.objects.create(name="Charles Baudelaire")

        formset = AuthorBooksFormSet(instance=author)
        self.assertEqual(len(formset.forms), 3)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_book_set-0-title">Title:</label>'
            '<input id="id_book_set-0-title" type="text" name="book_set-0-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-0-author" value="%d" '
            'id="id_book_set-0-author">'
            '<input type="hidden" name="book_set-0-id" id="id_book_set-0-id">'
            "</p>" % author.id,
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_book_set-1-title">Title:</label>'
            '<input id="id_book_set-1-title" type="text" name="book_set-1-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-1-author" value="%d" '
            'id="id_book_set-1-author">'
            '<input type="hidden" name="book_set-1-id" id="id_book_set-1-id"></p>'
            % author.id,
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_book_set-2-title">Title:</label>'
            '<input id="id_book_set-2-title" type="text" name="book_set-2-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-2-author" value="%d" '
            'id="id_book_set-2-author">'
            '<input type="hidden" name="book_set-2-id" id="id_book_set-2-id"></p>'
            % author.id,
        )

        data = {
            "book_set-TOTAL_FORMS": "3",  # the number of forms rendered
            "book_set-INITIAL_FORMS": "0",  # the number of forms with initial data
            "book_set-MAX_NUM_FORMS": "",  # the max number of forms
            "book_set-0-title": "Les Fleurs du Mal",
            "book_set-1-title": "",
            "book_set-2-title": "",
        }

        formset = AuthorBooksFormSet(data, instance=author)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (book1,) = saved
        self.assertEqual(book1, Book.objects.get(title="Les Fleurs du Mal"))
        self.assertSequenceEqual(author.book_set.all(), [book1])

        # Now that we've added a book to Charles Baudelaire, let's try adding
        # another one. This time though, an edit form will be available for
        # every existing book.

        AuthorBooksFormSet = inlineformset_factory(
            Author, Book, can_delete=False, extra=2, fields="__all__"
        )
        author = Author.objects.get(name="Charles Baudelaire")

        formset = AuthorBooksFormSet(instance=author)
        self.assertEqual(len(formset.forms), 3)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_book_set-0-title">Title:</label>'
            '<input id="id_book_set-0-title" type="text" name="book_set-0-title" '
            'value="Les Fleurs du Mal" maxlength="100">'
            '<input type="hidden" name="book_set-0-author" value="%d" '
            'id="id_book_set-0-author">'
            '<input type="hidden" name="book_set-0-id" value="%d" '
            'id="id_book_set-0-id"></p>'
            % (
                author.id,
                book1.id,
            ),
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_book_set-1-title">Title:</label>'
            '<input id="id_book_set-1-title" type="text" name="book_set-1-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-1-author" value="%d" '
            'id="id_book_set-1-author">'
            '<input type="hidden" name="book_set-1-id" id="id_book_set-1-id"></p>'
            % author.id,
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_book_set-2-title">Title:</label>'
            '<input id="id_book_set-2-title" type="text" name="book_set-2-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-2-author" value="%d" '
            'id="id_book_set-2-author">'
            '<input type="hidden" name="book_set-2-id" id="id_book_set-2-id"></p>'
            % author.id,
        )

        data = {
            "book_set-TOTAL_FORMS": "3",  # the number of forms rendered
            "book_set-INITIAL_FORMS": "1",  # the number of forms with initial data
            "book_set-MAX_NUM_FORMS": "",  # the max number of forms
            "book_set-0-id": str(book1.id),
            "book_set-0-title": "Les Fleurs du Mal",
            "book_set-1-title": "Les Paradis Artificiels",
            "book_set-2-title": "",
        }

        formset = AuthorBooksFormSet(data, instance=author)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (book2,) = saved
        self.assertEqual(book2, Book.objects.get(title="Les Paradis Artificiels"))

        # As you can see, 'Les Paradis Artificiels' is now a book belonging to
        # Charles Baudelaire.
        self.assertSequenceEqual(author.book_set.order_by("title"), [book1, book2])

    def test_inline_formsets_save_as_new(self):
        # The save_as_new parameter lets you re-associate the data to a new
        # instance.  This is used in the admin for save_as functionality.
        """

        Tests the functionality of saving inline formsets as new instances.

        This test case verifies that the inline formset is valid, and when saved,
        it correctly creates new book instances associated with a given author.
        It also checks that the formset is rendered correctly with the expected HTML output.

        The test covers the following scenarios:

        * Creating an inline formset with an empty instance and saving it as new
        * Creating a new instance and saving the formset with the new instance
        * Verifying the number of saved instances and their attributes
        * Rendering the formset with a prefix and checking the HTML output

        """
        AuthorBooksFormSet = inlineformset_factory(
            Author, Book, can_delete=False, extra=2, fields="__all__"
        )
        Author.objects.create(name="Charles Baudelaire")

        # An immutable QueryDict simulates request.POST.
        data = QueryDict(mutable=True)
        data.update(
            {
                "book_set-TOTAL_FORMS": "3",  # the number of forms rendered
                "book_set-INITIAL_FORMS": "2",  # the number of forms with initial data
                "book_set-MAX_NUM_FORMS": "",  # the max number of forms
                "book_set-0-id": "1",
                "book_set-0-title": "Les Fleurs du Mal",
                "book_set-1-id": "2",
                "book_set-1-title": "Les Paradis Artificiels",
                "book_set-2-title": "",
            }
        )
        data._mutable = False

        formset = AuthorBooksFormSet(data, instance=Author(), save_as_new=True)
        self.assertTrue(formset.is_valid())
        self.assertIs(data._mutable, False)

        new_author = Author.objects.create(name="Charles Baudelaire")
        formset = AuthorBooksFormSet(data, instance=new_author, save_as_new=True)
        saved = formset.save()
        self.assertEqual(len(saved), 2)
        book1, book2 = saved
        self.assertEqual(book1.title, "Les Fleurs du Mal")
        self.assertEqual(book2.title, "Les Paradis Artificiels")

        # Test using a custom prefix on an inline formset.

        formset = AuthorBooksFormSet(prefix="test")
        self.assertEqual(len(formset.forms), 2)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_test-0-title">Title:</label>'
            '<input id="id_test-0-title" type="text" name="test-0-title" '
            'maxlength="100">'
            '<input type="hidden" name="test-0-author" id="id_test-0-author">'
            '<input type="hidden" name="test-0-id" id="id_test-0-id"></p>',
        )

        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_test-1-title">Title:</label>'
            '<input id="id_test-1-title" type="text" name="test-1-title" '
            'maxlength="100">'
            '<input type="hidden" name="test-1-author" id="id_test-1-author">'
            '<input type="hidden" name="test-1-id" id="id_test-1-id"></p>',
        )

    def test_inline_formsets_with_custom_pk(self):
        # Test inline formsets where the inline-edited object has a custom
        # primary key that is not the fk to the parent object.
        """

        Tests the functionality of inline formsets with custom primary key values.

        This test case creates an inline formset for the Author model, which is
        associated with the BookWithCustomPK model. It verifies that the formset
        is properly initialized with a single form, and that the form's HTML
        representation matches the expected output.

        The test also submits data to the formset, saves the formset, and checks
        that the saved book has the correct custom primary key value and title.
        The test ensures that the formset is valid and that the book is correctly
        associated with the author.

        This test case covers the creation and saving of a new book with a custom
        primary key value using an inline formset, and verifies that the book's
        attributes are correctly saved and retrieved.

        """
        self.maxDiff = 1024

        AuthorBooksFormSet2 = inlineformset_factory(
            Author, BookWithCustomPK, can_delete=False, extra=1, fields="__all__"
        )
        author = Author.objects.create(pk=1, name="Charles Baudelaire")

        formset = AuthorBooksFormSet2(instance=author)
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_bookwithcustompk_set-0-my_pk">My pk:</label>'
            '<input id="id_bookwithcustompk_set-0-my_pk" type="number" '
            'name="bookwithcustompk_set-0-my_pk" step="1"></p>'
            '<p><label for="id_bookwithcustompk_set-0-title">Title:</label>'
            '<input id="id_bookwithcustompk_set-0-title" type="text" '
            'name="bookwithcustompk_set-0-title" maxlength="100">'
            '<input type="hidden" name="bookwithcustompk_set-0-author" '
            'value="1" id="id_bookwithcustompk_set-0-author"></p>',
        )

        data = {
            # The number of forms rendered.
            "bookwithcustompk_set-TOTAL_FORMS": "1",
            # The number of forms with initial data.
            "bookwithcustompk_set-INITIAL_FORMS": "0",
            # The max number of forms.
            "bookwithcustompk_set-MAX_NUM_FORMS": "",
            "bookwithcustompk_set-0-my_pk": "77777",
            "bookwithcustompk_set-0-title": "Les Fleurs du Mal",
        }

        formset = AuthorBooksFormSet2(data, instance=author)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (book1,) = saved
        self.assertEqual(book1.pk, 77777)

        book1 = author.bookwithcustompk_set.get()
        self.assertEqual(book1.title, "Les Fleurs du Mal")

    def test_inline_formsets_with_multi_table_inheritance(self):
        # Test inline formsets where the inline-edited object uses multi-table
        # inheritance, thus has a non AutoField yet auto-created primary key.

        """
        Tests the functionality of inline formsets when used with multi-table inheritance. 
        This test case checks if the formset can successfully create and validate a new instance of a related model (AlternateBook) that inherits from a parent model (Book) and is associated with another model (Author). 
        The test verifies that the formset is rendered correctly, that the data submitted through the formset is valid, and that the new instance is saved to the database with the expected attributes.
        """
        AuthorBooksFormSet3 = inlineformset_factory(
            Author, AlternateBook, can_delete=False, extra=1, fields="__all__"
        )
        author = Author.objects.create(pk=1, name="Charles Baudelaire")

        formset = AuthorBooksFormSet3(instance=author)
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_alternatebook_set-0-title">Title:</label>'
            '<input id="id_alternatebook_set-0-title" type="text" '
            'name="alternatebook_set-0-title" maxlength="100"></p>'
            '<p><label for="id_alternatebook_set-0-notes">Notes:</label>'
            '<input id="id_alternatebook_set-0-notes" type="text" '
            'name="alternatebook_set-0-notes" maxlength="100">'
            '<input type="hidden" name="alternatebook_set-0-author" value="1" '
            'id="id_alternatebook_set-0-author">'
            '<input type="hidden" name="alternatebook_set-0-book_ptr" '
            'id="id_alternatebook_set-0-book_ptr"></p>',
        )

        data = {
            # The number of forms rendered.
            "alternatebook_set-TOTAL_FORMS": "1",
            # The number of forms with initial data.
            "alternatebook_set-INITIAL_FORMS": "0",
            # The max number of forms.
            "alternatebook_set-MAX_NUM_FORMS": "",
            "alternatebook_set-0-title": "Flowers of Evil",
            "alternatebook_set-0-notes": "English translation of Les Fleurs du Mal",
        }

        formset = AuthorBooksFormSet3(data, instance=author)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (book1,) = saved
        self.assertEqual(book1.title, "Flowers of Evil")
        self.assertEqual(book1.notes, "English translation of Les Fleurs du Mal")

    @skipUnlessDBFeature("supports_partially_nullable_unique_constraints")
    def test_inline_formsets_with_nullable_unique_together(self):
        # Test inline formsets where the inline-edited object has a
        # unique_together constraint with a nullable member

        """
        Tests the use of inline formsets for models with nullable unique together constraints.

        This test case creates an inline formset for the BookWithOptionalAltEditor model, 
        which is related to the Author model. It then creates an instance of the Author model 
        and sets up a formset with two forms, both representing books written by the same author 
        with the same title. The test verifies that the formset is valid and can be saved 
        successfully, resulting in the creation of two new books. This tests the behavior 
        of Django's formset validation and saving when dealing with partially nullable unique 
        constraints. The test also checks that the saved books have the expected author and title.
        """
        AuthorBooksFormSet4 = inlineformset_factory(
            Author,
            BookWithOptionalAltEditor,
            can_delete=False,
            extra=2,
            fields="__all__",
        )
        author = Author.objects.create(pk=1, name="Charles Baudelaire")

        data = {
            # The number of forms rendered.
            "bookwithoptionalalteditor_set-TOTAL_FORMS": "2",
            # The number of forms with initial data.
            "bookwithoptionalalteditor_set-INITIAL_FORMS": "0",
            # The max number of forms.
            "bookwithoptionalalteditor_set-MAX_NUM_FORMS": "",
            "bookwithoptionalalteditor_set-0-author": "1",
            "bookwithoptionalalteditor_set-0-title": "Les Fleurs du Mal",
            "bookwithoptionalalteditor_set-1-author": "1",
            "bookwithoptionalalteditor_set-1-title": "Les Fleurs du Mal",
        }
        formset = AuthorBooksFormSet4(data, instance=author)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 2)
        book1, book2 = saved
        self.assertEqual(book1.author_id, 1)
        self.assertEqual(book1.title, "Les Fleurs du Mal")
        self.assertEqual(book2.author_id, 1)
        self.assertEqual(book2.title, "Les Fleurs du Mal")

    def test_inline_formsets_with_custom_save_method(self):
        """
        (\"\"\"Tests the inline formsets with a custom save method.

        The test case checks the following scenarios:
        - Creating an inline formset with a custom save method using ModelForm.
        - Saving the formset with valid data and verifying the saved instances.
        - Creating an inline formset with a custom queryset and verifying the rendered forms.
        - Saving the formset with valid data and a custom queryset, and verifying the saved instances.

        It ensures that the formset is valid, saved correctly, and the rendered forms match the expected output.
        \"\"\")
        """
        AuthorBooksFormSet = inlineformset_factory(
            Author, Book, can_delete=False, extra=2, fields="__all__"
        )
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        book1 = Book.objects.create(
            pk=1, author=author, title="Les Paradis Artificiels"
        )
        book2 = Book.objects.create(pk=2, author=author, title="Les Fleurs du Mal")
        book3 = Book.objects.create(pk=3, author=author, title="Flowers of Evil")

        class PoemForm(forms.ModelForm):
            def save(self, commit=True):
                # change the name to "Brooklyn Bridge" just to be a jerk.
                poem = super().save(commit=False)
                poem.name = "Brooklyn Bridge"
                if commit:
                    poem.save()
                return poem

        PoemFormSet = inlineformset_factory(Poet, Poem, form=PoemForm, fields="__all__")

        data = {
            "poem_set-TOTAL_FORMS": "3",  # the number of forms rendered
            "poem_set-INITIAL_FORMS": "0",  # the number of forms with initial data
            "poem_set-MAX_NUM_FORMS": "",  # the max number of forms
            "poem_set-0-name": "The Cloud in Trousers",
            "poem_set-1-name": "I",
            "poem_set-2-name": "",
        }

        poet = Poet.objects.create(name="Vladimir Mayakovsky")
        formset = PoemFormSet(data=data, instance=poet)
        self.assertTrue(formset.is_valid())

        saved = formset.save()
        self.assertEqual(len(saved), 2)
        poem1, poem2 = saved
        self.assertEqual(poem1.name, "Brooklyn Bridge")
        self.assertEqual(poem2.name, "Brooklyn Bridge")

        # We can provide a custom queryset to our InlineFormSet:

        custom_qs = Book.objects.order_by("-title")
        formset = AuthorBooksFormSet(instance=author, queryset=custom_qs)
        self.assertEqual(len(formset.forms), 5)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_book_set-0-title">Title:</label>'
            '<input id="id_book_set-0-title" type="text" name="book_set-0-title" '
            'value="Les Paradis Artificiels" maxlength="100">'
            '<input type="hidden" name="book_set-0-author" value="1" '
            'id="id_book_set-0-author">'
            '<input type="hidden" name="book_set-0-id" value="1" id="id_book_set-0-id">'
            "</p>",
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_book_set-1-title">Title:</label>'
            '<input id="id_book_set-1-title" type="text" name="book_set-1-title" '
            'value="Les Fleurs du Mal" maxlength="100">'
            '<input type="hidden" name="book_set-1-author" value="1" '
            'id="id_book_set-1-author">'
            '<input type="hidden" name="book_set-1-id" value="2" id="id_book_set-1-id">'
            "</p>",
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_book_set-2-title">Title:</label>'
            '<input id="id_book_set-2-title" type="text" name="book_set-2-title" '
            'value="Flowers of Evil" maxlength="100">'
            '<input type="hidden" name="book_set-2-author" value="1" '
            'id="id_book_set-2-author">'
            '<input type="hidden" name="book_set-2-id" value="3" '
            'id="id_book_set-2-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[3].as_p(),
            '<p><label for="id_book_set-3-title">Title:</label>'
            '<input id="id_book_set-3-title" type="text" name="book_set-3-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-3-author" value="1" '
            'id="id_book_set-3-author">'
            '<input type="hidden" name="book_set-3-id" id="id_book_set-3-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[4].as_p(),
            '<p><label for="id_book_set-4-title">Title:</label>'
            '<input id="id_book_set-4-title" type="text" name="book_set-4-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-4-author" value="1" '
            'id="id_book_set-4-author">'
            '<input type="hidden" name="book_set-4-id" id="id_book_set-4-id"></p>',
        )

        data = {
            "book_set-TOTAL_FORMS": "5",  # the number of forms rendered
            "book_set-INITIAL_FORMS": "3",  # the number of forms with initial data
            "book_set-MAX_NUM_FORMS": "",  # the max number of forms
            "book_set-0-id": str(book1.id),
            "book_set-0-title": "Les Paradis Artificiels",
            "book_set-1-id": str(book2.id),
            "book_set-1-title": "Les Fleurs du Mal",
            "book_set-2-id": str(book3.id),
            "book_set-2-title": "Flowers of Evil",
            "book_set-3-title": "Revue des deux mondes",
            "book_set-4-title": "",
        }
        formset = AuthorBooksFormSet(data, instance=author, queryset=custom_qs)
        self.assertTrue(formset.is_valid())

        custom_qs = Book.objects.filter(title__startswith="F")
        formset = AuthorBooksFormSet(instance=author, queryset=custom_qs)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_book_set-0-title">Title:</label>'
            '<input id="id_book_set-0-title" type="text" name="book_set-0-title" '
            'value="Flowers of Evil" maxlength="100">'
            '<input type="hidden" name="book_set-0-author" value="1" '
            'id="id_book_set-0-author">'
            '<input type="hidden" name="book_set-0-id" value="3" '
            'id="id_book_set-0-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_book_set-1-title">Title:</label>'
            '<input id="id_book_set-1-title" type="text" name="book_set-1-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-1-author" value="1" '
            'id="id_book_set-1-author">'
            '<input type="hidden" name="book_set-1-id" id="id_book_set-1-id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_book_set-2-title">Title:</label>'
            '<input id="id_book_set-2-title" type="text" name="book_set-2-title" '
            'maxlength="100">'
            '<input type="hidden" name="book_set-2-author" value="1" '
            'id="id_book_set-2-author">'
            '<input type="hidden" name="book_set-2-id" id="id_book_set-2-id"></p>',
        )

        data = {
            "book_set-TOTAL_FORMS": "3",  # the number of forms rendered
            "book_set-INITIAL_FORMS": "1",  # the number of forms with initial data
            "book_set-MAX_NUM_FORMS": "",  # the max number of forms
            "book_set-0-id": str(book3.id),
            "book_set-0-title": "Flowers of Evil",
            "book_set-1-title": "Revue des deux mondes",
            "book_set-2-title": "",
        }
        formset = AuthorBooksFormSet(data, instance=author, queryset=custom_qs)
        self.assertTrue(formset.is_valid())

    def test_inline_formsets_with_custom_save_method_related_instance(self):
        """
        The ModelForm.save() method should be able to access the related object
        if it exists in the database (#24395).
        """

        class PoemForm2(forms.ModelForm):
            def save(self, commit=True):
                poem = super().save(commit=False)
                poem.name = "%s by %s" % (poem.name, poem.poet.name)
                if commit:
                    poem.save()
                return poem

        PoemFormSet = inlineformset_factory(
            Poet, Poem, form=PoemForm2, fields="__all__"
        )
        data = {
            "poem_set-TOTAL_FORMS": "1",
            "poem_set-INITIAL_FORMS": "0",
            "poem_set-MAX_NUM_FORMS": "",
            "poem_set-0-name": "Le Lac",
        }
        poet = Poet()
        formset = PoemFormSet(data=data, instance=poet)
        self.assertTrue(formset.is_valid())

        # The Poet instance is saved after the formset instantiation. This
        # happens in admin's changeform_view() when adding a new object and
        # some inlines in the same request.
        poet.name = "Lamartine"
        poet.save()
        poem = formset.save()[0]
        self.assertEqual(poem.name, "Le Lac by Lamartine")

    def test_inline_formsets_with_wrong_fk_name(self):
        """Regression for #23451"""
        message = "fk_name 'title' is not a ForeignKey to 'model_formsets.Author'."
        with self.assertRaisesMessage(ValueError, message):
            inlineformset_factory(Author, Book, fields="__all__", fk_name="title")

    def test_custom_pk(self):
        # We need to ensure that it is displayed

        CustomPrimaryKeyFormSet = modelformset_factory(
            CustomPrimaryKey, fields="__all__"
        )
        formset = CustomPrimaryKeyFormSet()
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-my_pk">My pk:</label>'
            '<input id="id_form-0-my_pk" type="text" name="form-0-my_pk" '
            'maxlength="10"></p>'
            '<p><label for="id_form-0-some_field">Some field:</label>'
            '<input id="id_form-0-some_field" type="text" name="form-0-some_field" '
            'maxlength="100"></p>',
        )

        # Custom primary keys with ForeignKey, OneToOneField and AutoField ############

        place = Place.objects.create(pk=1, name="Giordanos", city="Chicago")

        FormSet = inlineformset_factory(
            Place, Owner, extra=2, can_delete=False, fields="__all__"
        )
        formset = FormSet(instance=place)
        self.assertEqual(len(formset.forms), 2)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_owner_set-0-name">Name:</label>'
            '<input id="id_owner_set-0-name" type="text" name="owner_set-0-name" '
            'maxlength="100">'
            '<input type="hidden" name="owner_set-0-place" value="1" '
            'id="id_owner_set-0-place">'
            '<input type="hidden" name="owner_set-0-auto_id" '
            'id="id_owner_set-0-auto_id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_owner_set-1-name">Name:</label>'
            '<input id="id_owner_set-1-name" type="text" name="owner_set-1-name" '
            'maxlength="100">'
            '<input type="hidden" name="owner_set-1-place" value="1" '
            'id="id_owner_set-1-place">'
            '<input type="hidden" name="owner_set-1-auto_id" '
            'id="id_owner_set-1-auto_id"></p>',
        )

        data = {
            "owner_set-TOTAL_FORMS": "2",
            "owner_set-INITIAL_FORMS": "0",
            "owner_set-MAX_NUM_FORMS": "",
            "owner_set-0-auto_id": "",
            "owner_set-0-name": "Joe Perry",
            "owner_set-1-auto_id": "",
            "owner_set-1-name": "",
        }
        formset = FormSet(data, instance=place)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (owner1,) = saved
        self.assertEqual(owner1.name, "Joe Perry")
        self.assertEqual(owner1.place.name, "Giordanos")

        formset = FormSet(instance=place)
        self.assertEqual(len(formset.forms), 3)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_owner_set-0-name">Name:</label>'
            '<input id="id_owner_set-0-name" type="text" name="owner_set-0-name" '
            'value="Joe Perry" maxlength="100">'
            '<input type="hidden" name="owner_set-0-place" value="1" '
            'id="id_owner_set-0-place">'
            '<input type="hidden" name="owner_set-0-auto_id" value="%d" '
            'id="id_owner_set-0-auto_id"></p>' % owner1.auto_id,
        )
        self.assertHTMLEqual(
            formset.forms[1].as_p(),
            '<p><label for="id_owner_set-1-name">Name:</label>'
            '<input id="id_owner_set-1-name" type="text" name="owner_set-1-name" '
            'maxlength="100">'
            '<input type="hidden" name="owner_set-1-place" value="1" '
            'id="id_owner_set-1-place">'
            '<input type="hidden" name="owner_set-1-auto_id" '
            'id="id_owner_set-1-auto_id"></p>',
        )
        self.assertHTMLEqual(
            formset.forms[2].as_p(),
            '<p><label for="id_owner_set-2-name">Name:</label>'
            '<input id="id_owner_set-2-name" type="text" name="owner_set-2-name" '
            'maxlength="100">'
            '<input type="hidden" name="owner_set-2-place" value="1" '
            'id="id_owner_set-2-place">'
            '<input type="hidden" name="owner_set-2-auto_id" '
            'id="id_owner_set-2-auto_id"></p>',
        )

        data = {
            "owner_set-TOTAL_FORMS": "3",
            "owner_set-INITIAL_FORMS": "1",
            "owner_set-MAX_NUM_FORMS": "",
            "owner_set-0-auto_id": str(owner1.auto_id),
            "owner_set-0-name": "Joe Perry",
            "owner_set-1-auto_id": "",
            "owner_set-1-name": "Jack Berry",
            "owner_set-2-auto_id": "",
            "owner_set-2-name": "",
        }
        formset = FormSet(data, instance=place)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (owner2,) = saved
        self.assertEqual(owner2.name, "Jack Berry")
        self.assertEqual(owner2.place.name, "Giordanos")

        # A custom primary key that is a ForeignKey or OneToOneField get
        # rendered for the user to choose.
        FormSet = modelformset_factory(OwnerProfile, fields="__all__")
        formset = FormSet()
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_form-0-owner">Owner:</label>'
            '<select name="form-0-owner" id="id_form-0-owner">'
            '<option value="" selected>---------</option>'
            '<option value="%d">Joe Perry at Giordanos</option>'
            '<option value="%d">Jack Berry at Giordanos</option>'
            "</select></p>"
            '<p><label for="id_form-0-age">Age:</label>'
            '<input type="number" name="form-0-age" id="id_form-0-age" min="0"></p>'
            % (owner1.auto_id, owner2.auto_id),
        )

        owner1 = Owner.objects.get(name="Joe Perry")
        FormSet = inlineformset_factory(
            Owner, OwnerProfile, max_num=1, can_delete=False, fields="__all__"
        )
        self.assertEqual(FormSet.max_num, 1)

        formset = FormSet(instance=owner1)
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_ownerprofile-0-age">Age:</label>'
            '<input type="number" name="ownerprofile-0-age" '
            'id="id_ownerprofile-0-age" min="0">'
            '<input type="hidden" name="ownerprofile-0-owner" value="%d" '
            'id="id_ownerprofile-0-owner"></p>' % owner1.auto_id,
        )

        data = {
            "ownerprofile-TOTAL_FORMS": "1",
            "ownerprofile-INITIAL_FORMS": "0",
            "ownerprofile-MAX_NUM_FORMS": "1",
            "ownerprofile-0-owner": "",
            "ownerprofile-0-age": "54",
        }
        formset = FormSet(data, instance=owner1)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (profile1,) = saved
        self.assertEqual(profile1.owner, owner1)
        self.assertEqual(profile1.age, 54)

        formset = FormSet(instance=owner1)
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_ownerprofile-0-age">Age:</label>'
            '<input type="number" name="ownerprofile-0-age" value="54" '
            'id="id_ownerprofile-0-age" min="0">'
            '<input type="hidden" name="ownerprofile-0-owner" value="%d" '
            'id="id_ownerprofile-0-owner"></p>' % owner1.auto_id,
        )

        data = {
            "ownerprofile-TOTAL_FORMS": "1",
            "ownerprofile-INITIAL_FORMS": "1",
            "ownerprofile-MAX_NUM_FORMS": "1",
            "ownerprofile-0-owner": str(owner1.auto_id),
            "ownerprofile-0-age": "55",
        }
        formset = FormSet(data, instance=owner1)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (profile1,) = saved
        self.assertEqual(profile1.owner, owner1)
        self.assertEqual(profile1.age, 55)

    def test_unique_true_enforces_max_num_one(self):
        # ForeignKey with unique=True should enforce max_num=1

        """
        Tests that when the `unique` attribute is set to `True`, it enforces a maximum of one form in the formset, created for a specific instance of a model, ensuring that only one form is available for editing. It verifies this by checking the formset's `max_num` attribute and the number of forms generated, as well as the HTML structure of the first form in the formset.
        """
        place = Place.objects.create(pk=1, name="Giordanos", city="Chicago")

        FormSet = inlineformset_factory(
            Place, Location, can_delete=False, fields="__all__"
        )
        self.assertEqual(FormSet.max_num, 1)

        formset = FormSet(instance=place)
        self.assertEqual(len(formset.forms), 1)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<p><label for="id_location_set-0-lat">Lat:</label>'
            '<input id="id_location_set-0-lat" type="text" name="location_set-0-lat" '
            'maxlength="100"></p>'
            '<p><label for="id_location_set-0-lon">Lon:</label>'
            '<input id="id_location_set-0-lon" type="text" name="location_set-0-lon" '
            'maxlength="100">'
            '<input type="hidden" name="location_set-0-place" value="1" '
            'id="id_location_set-0-place">'
            '<input type="hidden" name="location_set-0-id" '
            'id="id_location_set-0-id"></p>',
        )

    def test_foreign_keys_in_parents(self):
        """

        Tests if the foreign keys defined in parent classes are correctly recognized.

        This test case checks if the foreign key relationship between the Owner model and 
        its children (i.e., Restaurant and MexicanRestaurant) is properly established.
        It verifies that the foreign key type is correctly identified as a models.ForeignKey.

        """
        self.assertEqual(type(_get_foreign_key(Restaurant, Owner)), models.ForeignKey)
        self.assertEqual(
            type(_get_foreign_key(MexicanRestaurant, Owner)), models.ForeignKey
        )

    def test_unique_validation(self):
        """

        Tests that validation correctly prevents creating multiple products with the same slug.

        Verifies that the formset will:
        - Successfully save a new product when given a unique slug.
        - Fail to save a product when given a slug that already exists.
        - Return the expected error message in the formset's errors attribute when the save fails due to a duplicate slug.

        """
        FormSet = modelformset_factory(Product, fields="__all__", extra=1)
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-slug": "car-red",
        }
        formset = FormSet(data)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (product1,) = saved
        self.assertEqual(product1.slug, "car-red")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-slug": "car-red",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.errors, [{"slug": ["Product with this Slug already exists."]}]
        )

    def test_modelformset_validate_max_flag(self):
        # If validate_max is set and max_num is less than TOTAL_FORMS in the
        # data, then throw an exception. MAX_NUM_FORMS in the data is
        # irrelevant here (it's output as a hint for the client but its
        # value in the returned data is not checked)

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "2",  # should be ignored
            "form-0-price": "12.00",
            "form-0-quantity": "1",
            "form-1-price": "24.00",
            "form-1-quantity": "2",
        }

        FormSet = modelformset_factory(
            Price, fields="__all__", extra=1, max_num=1, validate_max=True
        )
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at most 1 form."])

        # Now test the same thing without the validate_max flag to ensure
        # default behavior is unchanged
        FormSet = modelformset_factory(Price, fields="__all__", extra=1, max_num=1)
        formset = FormSet(data)
        self.assertTrue(formset.is_valid())

    def test_modelformset_min_num_equals_max_num_less_than(self):
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "2",
            "form-0-slug": "car-red",
            "form-1-slug": "car-blue",
            "form-2-slug": "car-black",
        }
        FormSet = modelformset_factory(
            Product,
            fields="__all__",
            extra=1,
            max_num=2,
            validate_max=True,
            min_num=2,
            validate_min=True,
        )
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at most 2 forms."])

    def test_modelformset_min_num_equals_max_num_more_than(self):
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "2",
            "form-0-slug": "car-red",
        }
        FormSet = modelformset_factory(
            Product,
            fields="__all__",
            extra=1,
            max_num=2,
            validate_max=True,
            min_num=2,
            validate_min=True,
        )
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ["Please submit at least 2 forms."])

    def test_unique_together_validation(self):
        """
        Tests the unique together validation for the Price model.

        This test case ensures that the Price model's unique_together constraint on price and quantity is enforced when creating new instances using a formset.
        It verifies that an initial valid formset is saved successfully with the expected data, and then checks that attempting to save a duplicate instance results in a validation error.
        The test covers the expected behavior of the formset's is_valid method, the saving of valid data, and the error messages generated when trying to save duplicate data.
        """
        FormSet = modelformset_factory(Price, fields="__all__", extra=1)
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-price": "12.00",
            "form-0-quantity": "1",
        }
        formset = FormSet(data)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (price1,) = saved
        self.assertEqual(price1.price, Decimal("12.00"))
        self.assertEqual(price1.quantity, 1)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-price": "12.00",
            "form-0-quantity": "1",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.errors,
            [{"__all__": ["Price with this Price and Quantity already exists."]}],
        )

    def test_unique_together_with_inlineformset_factory(self):
        # Also see bug #8882.

        """

        Tests the unique_together constraint on the Repository and Revision models using an inline formset.

        This test case creates a Repository instance and a formset for creating new Revision instances.
        It then attempts to create a new Revision instance with a unique revision, verifies its validity,
        and ensures that it is associated with the correct Repository instance.

        The test also checks that attempting to create a duplicate Revision instance with the same
        repository and revision raises a validation error with the expected message.

        Additionally, it tests the case where the formset only includes the revision field, ensuring
        that the unique_together constraint is still enforced correctly.

        """
        repository = Repository.objects.create(name="Test Repo")
        FormSet = inlineformset_factory(Repository, Revision, extra=1, fields="__all__")
        data = {
            "revision_set-TOTAL_FORMS": "1",
            "revision_set-INITIAL_FORMS": "0",
            "revision_set-MAX_NUM_FORMS": "",
            "revision_set-0-repository": repository.pk,
            "revision_set-0-revision": "146239817507f148d448db38840db7c3cbf47c76",
            "revision_set-0-DELETE": "",
        }
        formset = FormSet(data, instance=repository)
        self.assertTrue(formset.is_valid())
        saved = formset.save()
        self.assertEqual(len(saved), 1)
        (revision1,) = saved
        self.assertEqual(revision1.repository, repository)
        self.assertEqual(revision1.revision, "146239817507f148d448db38840db7c3cbf47c76")

        # attempt to save the same revision against the same repo.
        data = {
            "revision_set-TOTAL_FORMS": "1",
            "revision_set-INITIAL_FORMS": "0",
            "revision_set-MAX_NUM_FORMS": "",
            "revision_set-0-repository": repository.pk,
            "revision_set-0-revision": "146239817507f148d448db38840db7c3cbf47c76",
            "revision_set-0-DELETE": "",
        }
        formset = FormSet(data, instance=repository)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.errors,
            [
                {
                    "__all__": [
                        "Revision with this Repository and Revision already exists."
                    ]
                }
            ],
        )

        # unique_together with inlineformset_factory with overridden form fields
        # Also see #9494

        FormSet = inlineformset_factory(
            Repository, Revision, fields=("revision",), extra=1
        )
        data = {
            "revision_set-TOTAL_FORMS": "1",
            "revision_set-INITIAL_FORMS": "0",
            "revision_set-MAX_NUM_FORMS": "",
            "revision_set-0-repository": repository.pk,
            "revision_set-0-revision": "146239817507f148d448db38840db7c3cbf47c76",
            "revision_set-0-DELETE": "",
        }
        formset = FormSet(data, instance=repository)
        self.assertFalse(formset.is_valid())

    def test_callable_defaults(self):
        # Use of callable defaults (see bug #7975).

        """
        Tests the functionality of callable default values in Django forms and formsets.

        This test suite verifies that the initial value of a DateTimeField in a formset
        is correctly set to the current date and time when the form is created. It also
        checks that the formset validates correctly when the form data matches the initial
        value, and fails validation when the form data does not match.

        The test uses the inlineformset_factory function to create a formset for the
        Membership model, with a DateTimeField that has a callable default value. It then
        tests the formset with different sets of form data, including data that matches the
        initial value and data that does not match.

        The test also verifies that the formset behaves correctly when the DateTimeField
        is rendered as a SplitDateTimeField, which is a widget that splits the date and time
        into separate fields. This is tested by creating a custom form class, MembershipForm,
        that uses a SplitDateTimeField for the date_joined field, and then using this form
        class to create a formset.

        Overall, this test suite ensures that the callable default values in Django forms
        and formsets are working correctly, and that the formset validation is behaving as
        expected in different scenarios.
        """
        person = Person.objects.create(name="Ringo")
        FormSet = inlineformset_factory(
            Person, Membership, can_delete=False, extra=1, fields="__all__"
        )
        formset = FormSet(instance=person)

        # Django will render a hidden field for model fields that have a callable
        # default. This is required to ensure the value is tested for change correctly
        # when determine what extra forms have changed to save.

        self.assertEqual(len(formset.forms), 1)  # this formset only has one form
        form = formset.forms[0]
        now = form.fields["date_joined"].initial()
        result = form.as_p()
        result = re.sub(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?",
            "__DATETIME__",
            result,
        )
        self.assertHTMLEqual(
            result,
            '<p><label for="id_membership_set-0-date_joined">Date joined:</label>'
            '<input type="text" name="membership_set-0-date_joined" '
            'value="__DATETIME__" id="id_membership_set-0-date_joined">'
            '<input type="hidden" name="initial-membership_set-0-date_joined" '
            'value="__DATETIME__" '
            'id="initial-membership_set-0-id_membership_set-0-date_joined"></p>'
            '<p><label for="id_membership_set-0-karma">Karma:</label>'
            '<input type="number" name="membership_set-0-karma" '
            'id="id_membership_set-0-karma">'
            '<input type="hidden" name="membership_set-0-person" value="%d" '
            'id="id_membership_set-0-person">'
            '<input type="hidden" name="membership_set-0-id" '
            'id="id_membership_set-0-id"></p>' % person.id,
        )

        # test for validation with callable defaults. Validations rely on hidden fields

        data = {
            "membership_set-TOTAL_FORMS": "1",
            "membership_set-INITIAL_FORMS": "0",
            "membership_set-MAX_NUM_FORMS": "",
            "membership_set-0-date_joined": now.strftime("%Y-%m-%d %H:%M:%S"),
            "initial-membership_set-0-date_joined": now.strftime("%Y-%m-%d %H:%M:%S"),
            "membership_set-0-karma": "",
        }
        formset = FormSet(data, instance=person)
        self.assertTrue(formset.is_valid())

        # now test for when the data changes

        one_day_later = now + datetime.timedelta(days=1)
        filled_data = {
            "membership_set-TOTAL_FORMS": "1",
            "membership_set-INITIAL_FORMS": "0",
            "membership_set-MAX_NUM_FORMS": "",
            "membership_set-0-date_joined": one_day_later.strftime("%Y-%m-%d %H:%M:%S"),
            "initial-membership_set-0-date_joined": now.strftime("%Y-%m-%d %H:%M:%S"),
            "membership_set-0-karma": "",
        }
        formset = FormSet(filled_data, instance=person)
        self.assertFalse(formset.is_valid())

        # now test with split datetime fields

        class MembershipForm(forms.ModelForm):
            date_joined = forms.SplitDateTimeField(initial=now)

            class Meta:
                model = Membership
                fields = "__all__"

            def __init__(self, **kwargs):
                """
                Initializes a new instance of the class, inheriting from its parent and configuring the date_joined field to use a split date and time widget for user-friendly input. 

                This allows for separate input fields for date and time, making it easier to select a specific date and time when a user is joining. 

                The initializer accepts additional keyword arguments, which are passed to the parent class's initializer.
                """
                super().__init__(**kwargs)
                self.fields["date_joined"].widget = forms.SplitDateTimeWidget()

        FormSet = inlineformset_factory(
            Person,
            Membership,
            form=MembershipForm,
            can_delete=False,
            extra=1,
            fields="__all__",
        )
        data = {
            "membership_set-TOTAL_FORMS": "1",
            "membership_set-INITIAL_FORMS": "0",
            "membership_set-MAX_NUM_FORMS": "",
            "membership_set-0-date_joined_0": now.strftime("%Y-%m-%d"),
            "membership_set-0-date_joined_1": now.strftime("%H:%M:%S"),
            "initial-membership_set-0-date_joined": now.strftime("%Y-%m-%d %H:%M:%S"),
            "membership_set-0-karma": "",
        }
        formset = FormSet(data, instance=person)
        self.assertTrue(formset.is_valid())

    def test_inlineformset_factory_with_null_fk(self):
        # inlineformset_factory tests with fk having null=True. see #9462.
        # create some data that will exhibit the issue
        """

        Tests the functionality of inline formset factory with a null foreign key.

        This test case creates a team and two players, one of which is associated with the team.
        It then uses the inline formset factory to generate a formset for the players associated with the team.
        The test checks that the formset correctly returns an empty queryset when no instance is provided,
        and that it returns the correct player when an instance is provided.

        Verifies that the formset is able to correctly handle the relationship between the team and its players,
        including the case where a player does not have a team (i.e., the foreign key is null).

        """
        team = Team.objects.create(name="Red Vipers")
        Player(name="Timmy").save()
        Player(name="Bobby", team=team).save()

        PlayerInlineFormSet = inlineformset_factory(Team, Player, fields="__all__")
        formset = PlayerInlineFormSet()
        self.assertQuerySetEqual(formset.get_queryset(), [])

        formset = PlayerInlineFormSet(instance=team)
        players = formset.get_queryset()
        self.assertEqual(len(players), 1)
        (player1,) = players
        self.assertEqual(player1.team, team)
        self.assertEqual(player1.name, "Bobby")

    def test_inlineformset_with_arrayfield(self):
        class SimpleArrayField(forms.CharField):
            """A proxy for django.contrib.postgres.forms.SimpleArrayField."""

            def to_python(self, value):
                value = super().to_python(value)
                return value.split(",") if value else []

        class BookForm(forms.ModelForm):
            title = SimpleArrayField()

            class Meta:
                model = Book
                fields = ("title",)

        BookFormSet = inlineformset_factory(Author, Book, form=BookForm)
        data = {
            "book_set-TOTAL_FORMS": "3",
            "book_set-INITIAL_FORMS": "0",
            "book_set-MAX_NUM_FORMS": "",
            "book_set-0-title": "test1,test2",
            "book_set-1-title": "test1,test2",
            "book_set-2-title": "test3,test4",
        }
        author = Author.objects.create(name="test")
        formset = BookFormSet(data, instance=author)
        self.assertEqual(
            formset.errors,
            [{}, {"__all__": ["Please correct the duplicate values below."]}, {}],
        )

    def test_inlineformset_with_jsonfield(self):
        """

        Test the functionality of an inline formset with a JSONField.

        This test case verifies that the formset correctly handles duplicate values 
        in the JSONField and raises an error for the form with duplicate data.

        The test creates an instance of Author and a corresponding inline formset 
        for Book objects, with a JSONField in the form. It then submits data with 
        duplicate values in one of the forms and checks that the formset returns 
        an error for the form with the duplicate data, while the other forms are valid.

        """
        class BookForm(forms.ModelForm):
            title = forms.JSONField()

            class Meta:
                model = Book
                fields = ("title",)

        BookFormSet = inlineformset_factory(Author, Book, form=BookForm)
        data = {
            "book_set-TOTAL_FORMS": "3",
            "book_set-INITIAL_FORMS": "0",
            "book_set-MAX_NUM_FORMS": "",
            "book_set-0-title": {"test1": "test2"},
            "book_set-1-title": {"test1": "test2"},
            "book_set-2-title": {"test3": "test4"},
        }
        author = Author.objects.create(name="test")
        formset = BookFormSet(data, instance=author)
        self.assertEqual(
            formset.errors,
            [{}, {"__all__": ["Please correct the duplicate values below."]}, {}],
        )

    def test_model_formset_with_custom_pk(self):
        # a formset for a Model that has a custom primary key that still needs to be
        # added to the formset automatically
        """
        Tests a formset generated from the ClassyMexicanRestaurant model, 
        verifying that it correctly includes the specified fields and the custom primary key field when instantiated. 
        The formset is created with a factory, specifying fields to include, and then checked for the expected fields.
        """
        FormSet = modelformset_factory(
            ClassyMexicanRestaurant, fields=["tacos_are_yummy"]
        )
        self.assertEqual(
            sorted(FormSet().forms[0].fields), ["tacos_are_yummy", "the_restaurant"]
        )

    def test_model_formset_with_initial_model_instance(self):
        # has_changed should compare model instance and primary key
        # see #18898
        FormSet = modelformset_factory(Poem, fields="__all__")
        john_milton = Poet(name="John Milton")
        john_milton.save()
        data = {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 0,
            "form-MAX_NUM_FORMS": "",
            "form-0-name": "",
            "form-0-poet": str(john_milton.id),
        }
        formset = FormSet(initial=[{"poet": john_milton}], data=data)
        self.assertFalse(formset.extra_forms[0].has_changed())

    def test_model_formset_with_initial_queryset(self):
        # has_changed should work with queryset and list of pk's
        # see #18898
        FormSet = modelformset_factory(AuthorMeeting, fields="__all__")
        Author.objects.create(pk=1, name="Charles Baudelaire")
        data = {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 0,
            "form-MAX_NUM_FORMS": "",
            "form-0-name": "",
            "form-0-created": "",
            "form-0-authors": list(Author.objects.values_list("id", flat=True)),
        }
        formset = FormSet(initial=[{"authors": Author.objects.all()}], data=data)
        self.assertFalse(formset.extra_forms[0].has_changed())

    def test_prevent_duplicates_from_with_the_same_formset(self):
        FormSet = modelformset_factory(Product, fields="__all__", extra=2)
        data = {
            "form-TOTAL_FORMS": 2,
            "form-INITIAL_FORMS": 0,
            "form-MAX_NUM_FORMS": "",
            "form-0-slug": "red_car",
            "form-1-slug": "red_car",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors, ["Please correct the duplicate data for slug."]
        )

        FormSet = modelformset_factory(Price, fields="__all__", extra=2)
        data = {
            "form-TOTAL_FORMS": 2,
            "form-INITIAL_FORMS": 0,
            "form-MAX_NUM_FORMS": "",
            "form-0-price": "25",
            "form-0-quantity": "7",
            "form-1-price": "25",
            "form-1-quantity": "7",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors,
            [
                "Please correct the duplicate data for price and quantity, which must "
                "be unique."
            ],
        )

        # Only the price field is specified, this should skip any unique
        # checks since the unique_together is not fulfilled. This will fail
        # with a KeyError if broken.
        FormSet = modelformset_factory(Price, fields=("price",), extra=2)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-price": "24",
            "form-1-price": "24",
        }
        formset = FormSet(data)
        self.assertTrue(formset.is_valid())

        FormSet = inlineformset_factory(Author, Book, extra=0, fields="__all__")
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        Book.objects.create(pk=1, author=author, title="Les Paradis Artificiels")
        Book.objects.create(pk=2, author=author, title="Les Fleurs du Mal")
        Book.objects.create(pk=3, author=author, title="Flowers of Evil")

        book_ids = author.book_set.order_by("id").values_list("id", flat=True)
        data = {
            "book_set-TOTAL_FORMS": "2",
            "book_set-INITIAL_FORMS": "2",
            "book_set-MAX_NUM_FORMS": "",
            "book_set-0-title": "The 2008 Election",
            "book_set-0-author": str(author.id),
            "book_set-0-id": str(book_ids[0]),
            "book_set-1-title": "The 2008 Election",
            "book_set-1-author": str(author.id),
            "book_set-1-id": str(book_ids[1]),
        }
        formset = FormSet(data=data, instance=author)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors, ["Please correct the duplicate data for title."]
        )
        self.assertEqual(
            formset.errors,
            [{}, {"__all__": ["Please correct the duplicate values below."]}],
        )

        FormSet = modelformset_factory(Post, fields="__all__", extra=2)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "blah",
            "form-0-slug": "Morning",
            "form-0-subtitle": "foo",
            "form-0-posted": "2009-01-01",
            "form-1-title": "blah",
            "form-1-slug": "Morning in Prague",
            "form-1-subtitle": "rawr",
            "form-1-posted": "2009-01-01",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors,
            [
                "Please correct the duplicate data for title which must be unique for "
                "the date in posted."
            ],
        )
        self.assertEqual(
            formset.errors,
            [{}, {"__all__": ["Please correct the duplicate values below."]}],
        )

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "foo",
            "form-0-slug": "Morning in Prague",
            "form-0-subtitle": "foo",
            "form-0-posted": "2009-01-01",
            "form-1-title": "blah",
            "form-1-slug": "Morning in Prague",
            "form-1-subtitle": "rawr",
            "form-1-posted": "2009-08-02",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors,
            [
                "Please correct the duplicate data for slug which must be unique for "
                "the year in posted."
            ],
        )

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "foo",
            "form-0-slug": "Morning in Prague",
            "form-0-subtitle": "rawr",
            "form-0-posted": "2008-08-01",
            "form-1-title": "blah",
            "form-1-slug": "Prague",
            "form-1-subtitle": "rawr",
            "form-1-posted": "2009-08-02",
        }
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset._non_form_errors,
            [
                "Please correct the duplicate data for subtitle which must be unique "
                "for the month in posted."
            ],
        )

    def test_prevent_change_outer_model_and_create_invalid_data(self):
        """

        Test that trying to change an outer model using a formset does not alter the original data.

        The test creates two authors and a formset for editing authors. It then attempts to save changes to the author names through the formset, 
        but restricts the queryset to only include one of the authors. The test verifies that the formset is valid and can be saved, 
        but the changes to the outer model (in this case, the author not included in the queryset) are not applied, 
        thus preventing any data corruption or inconsistencies.

        The test ensures that the formset's save method does not affect the original database state for objects outside of its queryset.

        """
        author = Author.objects.create(name="Charles")
        other_author = Author.objects.create(name="Walt")
        AuthorFormSet = modelformset_factory(Author, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MAX_NUM_FORMS": "",
            "form-0-id": str(author.id),
            "form-0-name": "Charles",
            "form-1-id": str(other_author.id),  # A model not in the formset's queryset.
            "form-1-name": "Changed name",
        }
        # This formset is only for Walt Whitman and shouldn't accept data for
        # other_author.
        formset = AuthorFormSet(
            data=data, queryset=Author.objects.filter(id__in=(author.id,))
        )
        self.assertTrue(formset.is_valid())
        formset.save()
        # The name of other_author shouldn't be changed and new models aren't
        # created.
        self.assertSequenceEqual(Author.objects.all(), [author, other_author])

    def test_validation_without_id(self):
        """
        ).. 
            Tests validation of the Author formset without providing an id.

            This test case creates an Author formset with a single form, 
            containing data for a new author but missing the required id field.

            It then checks if the formset correctly raises a validation error 
            for the missing id field, ensuring that the formset's validation behaves as expected.
        """
        AuthorFormSet = modelformset_factory(Author, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "",
            "form-0-name": "Charles",
        }
        formset = AuthorFormSet(data)
        self.assertEqual(
            formset.errors,
            [{"id": ["This field is required."]}],
        )

    def test_validation_with_child_model_without_id(self):
        """

        Validate the behavior of a formset when a child model instance is created without an ID.

        This test checks that the formset correctly identifies and reports the missing ID 
        for the child model instance, ensuring data integrity and consistency.

        Returns:
            None

        Raises:
            AssertionError: If the expected validation error is not raised.

        """
        BetterAuthorFormSet = modelformset_factory(BetterAuthor, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "",
            "form-0-name": "Charles",
            "form-0-write_speed": "10",
        }
        formset = BetterAuthorFormSet(data)
        self.assertEqual(
            formset.errors,
            [{"author_ptr": ["This field is required."]}],
        )

    def test_validation_with_invalid_id(self):
        """

        Tests that the validation of AuthorFormSet correctly handles an invalid id.

        Verifies that when an invalid id is provided in the form data, the formset
        raises a validation error indicating that the choice is not valid.

        The test covers a scenario where the id field is populated with a string value 
        that does not correspond to a valid choice, and checks that the expected error 
        message is returned in the formset's errors dictionary.

        """
        AuthorFormSet = modelformset_factory(Author, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "",
            "form-0-id": "abc",
            "form-0-name": "Charles",
        }
        formset = AuthorFormSet(data)
        self.assertEqual(
            formset.errors,
            [
                {
                    "id": [
                        "Select a valid choice. That choice is not one of the "
                        "available choices."
                    ]
                }
            ],
        )

    def test_validation_with_nonexistent_id(self):
        """

        Tests the validation of an AuthorFormSet when an invalid, non-existent ID is provided.

        This test case verifies that the formset correctly identifies and reports an error when a submitted ID does not match any existing Author instance.

        The expected outcome is a formset error indicating that the selected ID is not a valid choice.

        """
        AuthorFormSet = modelformset_factory(Author, fields="__all__")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "",
            "form-0-id": "12345",
            "form-0-name": "Charles",
        }
        formset = AuthorFormSet(data)
        self.assertEqual(
            formset.errors,
            [
                {
                    "id": [
                        "Select a valid choice. That choice is not one of the "
                        "available choices."
                    ]
                }
            ],
        )

    def test_initial_form_count_empty_data(self):
        """
        Tests that the initial form count of a formset with empty data is zero.

        This test case verifies the behavior of a formset when no initial data is provided.
        It checks that the initial form count, which represents the number of forms that
        would be displayed in the formset when it is first rendered, is correctly set to
        zero, indicating that no forms should be displayed initially.
        """
        AuthorFormSet = modelformset_factory(Author, fields="__all__")
        formset = AuthorFormSet({})
        self.assertEqual(formset.initial_form_count(), 0)

    def test_edit_only(self):
        charles = Author.objects.create(name="Charles Baudelaire")
        AuthorFormSet = modelformset_factory(Author, fields="__all__", edit_only=True)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
            "form-0-name": "Arthur Rimbaud",
            "form-1-name": "Walt Whitman",
        }
        formset = AuthorFormSet(data)
        self.assertIs(formset.is_valid(), True)
        formset.save()
        self.assertSequenceEqual(Author.objects.all(), [charles])
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": charles.pk,
            "form-0-name": "Arthur Rimbaud",
            "form-1-name": "Walt Whitman",
        }
        formset = AuthorFormSet(data)
        self.assertIs(formset.is_valid(), True)
        formset.save()
        charles.refresh_from_db()
        self.assertEqual(charles.name, "Arthur Rimbaud")
        self.assertSequenceEqual(Author.objects.all(), [charles])

    def test_edit_only_inlineformset_factory(self):
        """

        Tests the editing of an inline formset factory.

        This test case verifies that an inline formset factory can be used to edit
        existing objects, while preventing the creation of new objects. It creates an
        author and a book, then uses the formset to update the book's title.

        The test checks that the formset is valid, saves the changes, and verifies that
        the book's title has been updated correctly. It also ensures that no new books
        have been created during the editing process.

        :param None
        :raises AssertionError: If the formset is not valid, or if the book's title
            has not been updated correctly.
        :returns: None

        """
        charles = Author.objects.create(name="Charles Baudelaire")
        book = Book.objects.create(author=charles, title="Les Paradis Artificiels")
        AuthorFormSet = inlineformset_factory(
            Author,
            Book,
            can_delete=False,
            fields="__all__",
            edit_only=True,
        )
        data = {
            "book_set-TOTAL_FORMS": "4",
            "book_set-INITIAL_FORMS": "1",
            "book_set-MAX_NUM_FORMS": "0",
            "book_set-0-id": book.pk,
            "book_set-0-title": "Les Fleurs du Mal",
            "book_set-0-author": charles.pk,
            "book_set-1-title": "Flowers of Evil",
            "book_set-1-author": charles.pk,
        }
        formset = AuthorFormSet(data, instance=charles)
        self.assertIs(formset.is_valid(), True)
        formset.save()
        book.refresh_from_db()
        self.assertEqual(book.title, "Les Fleurs du Mal")
        self.assertSequenceEqual(Book.objects.all(), [book])

    def test_edit_only_object_outside_of_queryset(self):
        charles = Author.objects.create(name="Charles Baudelaire")
        walt = Author.objects.create(name="Walt Whitman")
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-0-id": walt.pk,
            "form-0-name": "Parth Patil",
        }
        AuthorFormSet = modelformset_factory(Author, fields="__all__", edit_only=True)
        formset = AuthorFormSet(data, queryset=Author.objects.filter(pk=charles.pk))
        self.assertIs(formset.is_valid(), True)
        formset.save()
        self.assertCountEqual(Author.objects.all(), [charles, walt])

    def test_edit_only_formset_factory_with_basemodelformset(self):
        charles = Author.objects.create(name="Charles Baudelaire")

        class AuthorForm(forms.ModelForm):
            class Meta:
                model = Author
                fields = "__all__"

        class BaseAuthorFormSet(BaseModelFormSet):
            def __init__(self, *args, **kwargs):
                self.model = Author
                super().__init__(*args, **kwargs)

        AuthorFormSet = formset_factory(AuthorForm, formset=BaseAuthorFormSet)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",
            "form-0-id": charles.pk,
            "form-0-name": "Shawn Dong",
            "form-1-name": "Walt Whitman",
        }
        formset = AuthorFormSet(data)
        self.assertIs(formset.is_valid(), True)
        formset.save()
        self.assertEqual(Author.objects.count(), 2)
        charles.refresh_from_db()
        self.assertEqual(charles.name, "Shawn Dong")
        self.assertEqual(Author.objects.count(), 2)


class TestModelFormsetOverridesTroughFormMeta(TestCase):
    def test_modelformset_factory_widgets(self):
        """

        Tests the creation of a model formset factory with custom widgets.

        This test case verifies that the modelformset_factory function correctly applies
        custom widget attributes to the generated form fields. Specifically, it checks
        that the 'name' field is rendered as a TextInput with the class 'poet'.

        The test creates a formset factory for the Poet model, specifying that all fields
        should be included and using a custom widget dictionary to override the default
        widget for the 'name' field. It then generates a form instance from the formset
        factory and asserts that the HTML representation of the 'name' field matches the
        expected output.

        """
        widgets = {"name": forms.TextInput(attrs={"class": "poet"})}
        PoetFormSet = modelformset_factory(Poet, fields="__all__", widgets=widgets)
        form = PoetFormSet.form()
        self.assertHTMLEqual(
            str(form["name"]),
            '<input id="id_name" maxlength="100" type="text" class="poet" name="name" '
            "required>",
        )

    def test_inlineformset_factory_widgets(self):
        """
        Tests the creation of an inline formset factory with custom widgets.

        This test verifies that the inline formset factory correctly applies custom widgets to
        the generated form fields. Specifically, it checks that a TextInput widget with a
        custom CSS class is applied to the 'title' field of the form.

        The test creates an inline formset factory for the Book model, associated with the
        Author model, and specifies the custom widget for the 'title' field. It then instantiates
        the form and asserts that the rendered HTML matches the expected output, including
        the custom CSS class.

        """
        widgets = {"title": forms.TextInput(attrs={"class": "book"})}
        BookFormSet = inlineformset_factory(
            Author, Book, widgets=widgets, fields="__all__"
        )
        form = BookFormSet.form()
        self.assertHTMLEqual(
            str(form["title"]),
            '<input class="book" id="id_title" maxlength="100" name="title" '
            'type="text" required>',
        )

    def test_modelformset_factory_labels_overrides(self):
        """
        Tests the functionality of overriding field labels in a model formset.

        Verifies that the label for the specified field is correctly overridden in both the `label_tag` and `legend_tag` methods, ensuring that the custom label is used instead of the default field name.
        """
        BookFormSet = modelformset_factory(
            Book, fields="__all__", labels={"title": "Name"}
        )
        form = BookFormSet.form()
        self.assertHTMLEqual(
            form["title"].label_tag(), '<label for="id_title">Name:</label>'
        )
        self.assertHTMLEqual(
            form["title"].legend_tag(),
            '<legend for="id_title">Name:</legend>',
        )

    def test_inlineformset_factory_labels_overrides(self):
        BookFormSet = inlineformset_factory(
            Author, Book, fields="__all__", labels={"title": "Name"}
        )
        form = BookFormSet.form()
        self.assertHTMLEqual(
            form["title"].label_tag(), '<label for="id_title">Name:</label>'
        )
        self.assertHTMLEqual(
            form["title"].legend_tag(),
            '<legend for="id_title">Name:</legend>',
        )

    def test_modelformset_factory_help_text_overrides(self):
        """
        Tests the override of help text for a form field in a ModelFormSet.

        Verifies that the help_texts parameter in modelformset_factory correctly overrides 
        the default help text for a specified field. In this case, the 'title' field is 
        expected to display the custom help text 'Choose carefully.' instead of its default 
        help text. This test ensures that the custom help text is properly applied to the 
        form field, allowing developers to provide more informative and contextual help 
        to users when filling out the form.
        """
        BookFormSet = modelformset_factory(
            Book, fields="__all__", help_texts={"title": "Choose carefully."}
        )
        form = BookFormSet.form()
        self.assertEqual(form["title"].help_text, "Choose carefully.")

    def test_inlineformset_factory_help_text_overrides(self):
        BookFormSet = inlineformset_factory(
            Author, Book, fields="__all__", help_texts={"title": "Choose carefully."}
        )
        form = BookFormSet.form()
        self.assertEqual(form["title"].help_text, "Choose carefully.")

    def test_modelformset_factory_error_messages_overrides(self):
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        BookFormSet = modelformset_factory(
            Book,
            fields="__all__",
            error_messages={"title": {"max_length": "Title too long!!"}},
        )
        form = BookFormSet.form(data={"title": "Foo " * 30, "author": author.id})
        form.full_clean()
        self.assertEqual(form.errors, {"title": ["Title too long!!"]})

    def test_inlineformset_factory_error_messages_overrides(self):
        """

        Tests the usage of error messages overrides in an inline formset factory.

        This test case verifies that custom error messages can be successfully applied to 
        a formset created with the inlineformset_factory function. Specifically, it checks 
        that a custom error message for the 'max_length' validation of the 'title' field 
        is correctly displayed when the provided title exceeds the allowed length.

        The test creates an instance of an Author, generates a formset for the associated 
        Book instances, and then attempts to validate a form with a title that triggers 
        the 'max_length' error. The test asserts that the custom error message is 
        correctly returned in the form's errors dictionary.

        """
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            error_messages={"title": {"max_length": "Title too long!!"}},
        )
        form = BookFormSet.form(data={"title": "Foo " * 30, "author": author.id})
        form.full_clean()
        self.assertEqual(form.errors, {"title": ["Title too long!!"]})

    def test_modelformset_factory_field_class_overrides(self):
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        BookFormSet = modelformset_factory(
            Book,
            fields="__all__",
            field_classes={
                "title": forms.SlugField,
            },
        )
        form = BookFormSet.form(data={"title": "Foo " * 30, "author": author.id})
        self.assertIs(Book._meta.get_field("title").__class__, models.CharField)
        self.assertIsInstance(form.fields["title"], forms.SlugField)

    def test_inlineformset_factory_field_class_overrides(self):
        """
        Tests that field classes can be overridden when creating an inline formset factory.

        Verifies that when an inline formset factory is created with a field class override, the form field
        instance uses the overridden class, while the model field remains unchanged. This ensures that the
        inline formset factory correctly applies custom field classes to its generated forms.

        Checks specifically that a SlugField override for a CharField model field results in a SlugField
        instance in the form, while the underlying model field remains a CharField.
        """
        author = Author.objects.create(pk=1, name="Charles Baudelaire")
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            field_classes={
                "title": forms.SlugField,
            },
        )
        form = BookFormSet.form(data={"title": "Foo " * 30, "author": author.id})
        self.assertIs(Book._meta.get_field("title").__class__, models.CharField)
        self.assertIsInstance(form.fields["title"], forms.SlugField)

    def test_modelformset_factory_absolute_max(self):
        """

        Tests that modelformset_factory enforces the absolute_max parameter.

        This test checks the behavior of a model formset when the absolute maximum number
        of forms to be validated is exceeded. It verifies that the formset is invalid and
        that the number of forms is capped at the specified absolute maximum (1500 in this
        case) and also verifies that it raises an error requiring at most 1000 forms.

        The test ensures that the formset validation fails with an error message when the
        number of forms submitted exceeds the allowed maximum, ensuring data integrity and
        preventing excessive data submission.

        """
        AuthorFormSet = modelformset_factory(
            Author, fields="__all__", absolute_max=1500
        )
        data = {
            "form-TOTAL_FORMS": "1501",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = AuthorFormSet(data=data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 1500)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 1000 forms."],
        )

    def test_modelformset_factory_absolute_max_with_max_num(self):
        AuthorFormSet = modelformset_factory(
            Author,
            fields="__all__",
            max_num=20,
            absolute_max=100,
        )
        data = {
            "form-TOTAL_FORMS": "101",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = AuthorFormSet(data=data)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 100)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 20 forms."],
        )

    def test_inlineformset_factory_absolute_max(self):
        author = Author.objects.create(name="Charles Baudelaire")
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            absolute_max=1500,
        )
        data = {
            "book_set-TOTAL_FORMS": "1501",
            "book_set-INITIAL_FORMS": "0",
            "book_set-MAX_NUM_FORMS": "0",
        }
        formset = BookFormSet(data, instance=author)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 1500)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 1000 forms."],
        )

    def test_inlineformset_factory_absolute_max_with_max_num(self):
        """
        Tests the behavior of an inline formset factory when the absolute maximum number of forms exceeds the maximum number of forms.

        This test case verifies that the formset validation correctly enforces the maximum number of forms (max_num) when the absolute maximum number of forms is higher. It checks that the formset is invalid when the number of submitted forms exceeds the maximum allowed, and that the error message correctly indicates the maximum allowed number of forms.

        The test covers the scenario where the absolute maximum number of forms is set to a higher value than the maximum number of forms, and the formset is validated with a number of forms exceeding the maximum allowed. The expected behavior is that the formset is marked as invalid and an error message is displayed, indicating the maximum allowed number of forms.
        """
        author = Author.objects.create(name="Charles Baudelaire")
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            max_num=20,
            absolute_max=100,
        )
        data = {
            "book_set-TOTAL_FORMS": "101",
            "book_set-INITIAL_FORMS": "0",
            "book_set-MAX_NUM_FORMS": "0",
        }
        formset = BookFormSet(data, instance=author)
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 100)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 20 forms."],
        )

    def test_modelformset_factory_can_delete_extra(self):
        """

        Tests that a ModelFormSet factory correctly includes deletion fields when both 'can_delete' and 'can_delete_extra' are enabled.

        Verifies that the formset includes the 'DELETE' field for each form, allowing for the deletion of existing and extra instances.

        """
        AuthorFormSet = modelformset_factory(
            Author,
            fields="__all__",
            can_delete=True,
            can_delete_extra=True,
            extra=2,
        )
        formset = AuthorFormSet()
        self.assertEqual(len(formset), 2)
        self.assertIn("DELETE", formset.forms[0].fields)
        self.assertIn("DELETE", formset.forms[1].fields)

    def test_modelformset_factory_disable_delete_extra(self):
        AuthorFormSet = modelformset_factory(
            Author,
            fields="__all__",
            can_delete=True,
            can_delete_extra=False,
            extra=2,
        )
        formset = AuthorFormSet()
        self.assertEqual(len(formset), 2)
        self.assertNotIn("DELETE", formset.forms[0].fields)
        self.assertNotIn("DELETE", formset.forms[1].fields)

    def test_inlineformset_factory_can_delete_extra(self):
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            can_delete=True,
            can_delete_extra=True,
            extra=2,
        )
        formset = BookFormSet()
        self.assertEqual(len(formset), 2)
        self.assertIn("DELETE", formset.forms[0].fields)
        self.assertIn("DELETE", formset.forms[1].fields)

    def test_inlineformset_factory_can_not_delete_extra(self):
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            can_delete=True,
            can_delete_extra=False,
            extra=2,
        )
        formset = BookFormSet()
        self.assertEqual(len(formset), 2)
        self.assertNotIn("DELETE", formset.forms[0].fields)
        self.assertNotIn("DELETE", formset.forms[1].fields)

    def test_inlineformset_factory_passes_renderer(self):
        """

        Tests if the inline formset factory correctly passes the provided renderer.

        This test case verifies that when creating an inline formset using the
        inlineformset_factory function, the specified renderer is properly assigned
        to the resulting formset instance. This ensures that the formset is rendered
        using the desired template engine.

        وية Args:
            None

        >Returns:
            None

         ///</test_description>
        \"\"\"

        is not suitable, here is a simplified and accurate version:
        \"\"\"
        Tests the renderer assignment in the inline formset factory.

        Verifies that the provided renderer is correctly passed to the resulting formset.

        """
        from django.forms.renderers import Jinja2

        renderer = Jinja2()
        BookFormSet = inlineformset_factory(
            Author,
            Book,
            fields="__all__",
            renderer=renderer,
        )
        formset = BookFormSet()
        self.assertEqual(formset.renderer, renderer)

    def test_modelformset_factory_passes_renderer(self):
        """
        Test that a ModelFormSet created with a custom renderer instance correctly sets the renderer attribute.

        This test ensures that when creating a ModelFormSet using the modelformset_factory function with a specified renderer, the resulting formset has the expected renderer assigned to it. In this case, the Jinja2 renderer is used to test this functionality.
        """
        from django.forms.renderers import Jinja2

        renderer = Jinja2()
        BookFormSet = modelformset_factory(Author, fields="__all__", renderer=renderer)
        formset = BookFormSet()
        self.assertEqual(formset.renderer, renderer)

    def test_modelformset_factory_default_renderer(self):
        class CustomRenderer(DjangoTemplates):
            pass

        class ModelFormWithDefaultRenderer(ModelForm):
            default_renderer = CustomRenderer()

        BookFormSet = modelformset_factory(
            Author, form=ModelFormWithDefaultRenderer, fields="__all__"
        )
        formset = BookFormSet()
        self.assertEqual(
            formset.forms[0].renderer, ModelFormWithDefaultRenderer.default_renderer
        )
        self.assertEqual(
            formset.empty_form.renderer, ModelFormWithDefaultRenderer.default_renderer
        )
        self.assertIsInstance(formset.renderer, DjangoTemplates)

    def test_inlineformset_factory_default_renderer(self):
        """

        Tests the usage of the inlineformset_factory with a custom form renderer.

        This test case verifies that the default renderer specified in a ModelForm is 
        properly applied to the forms generated by the inline formset. It also checks 
        that the formset itself uses the default Django template renderer.

        """
        class CustomRenderer(DjangoTemplates):
            pass

        class ModelFormWithDefaultRenderer(ModelForm):
            default_renderer = CustomRenderer()

        BookFormSet = inlineformset_factory(
            Author,
            Book,
            form=ModelFormWithDefaultRenderer,
            fields="__all__",
        )
        formset = BookFormSet()
        self.assertEqual(
            formset.forms[0].renderer, ModelFormWithDefaultRenderer.default_renderer
        )
        self.assertEqual(
            formset.empty_form.renderer, ModelFormWithDefaultRenderer.default_renderer
        )
        self.assertIsInstance(formset.renderer, DjangoTemplates)
