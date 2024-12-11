from django import forms
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps

from .models import (
    Animal,
    ForProxyModelModel,
    Gecko,
    Mineral,
    ProxyRelatedModel,
    TaggedItem,
)


class CustomWidget(forms.TextInput):
    pass


class TaggedItemForm(forms.ModelForm):
    class Meta:
        model = TaggedItem
        fields = "__all__"
        widgets = {"tag": CustomWidget}


class GenericInlineFormsetTests(TestCase):
    def test_output(self):
        GenericFormSet = generic_inlineformset_factory(TaggedItem, extra=1)
        formset = GenericFormSet()
        self.assertHTMLEqual(
            "".join(form.as_p() for form in formset.forms),
            """
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-tag">
            Tag:</label>
            <input id="id_generic_relations-taggeditem-content_type-object_id-0-tag"
                type="text"
                name="generic_relations-taggeditem-content_type-object_id-0-tag"
                maxlength="50"></p>
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            Delete:</label>
            <input type="checkbox"
                name="generic_relations-taggeditem-content_type-object_id-0-DELETE"
                id="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            <input type="hidden"
                name="generic_relations-taggeditem-content_type-object_id-0-id"
                id="id_generic_relations-taggeditem-content_type-object_id-0-id"></p>
            """,
        )
        formset = GenericFormSet(instance=Animal())
        self.assertHTMLEqual(
            "".join(form.as_p() for form in formset.forms),
            """
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-tag">
            Tag:</label>
            <input id="id_generic_relations-taggeditem-content_type-object_id-0-tag"
                type="text"
                name="generic_relations-taggeditem-content_type-object_id-0-tag"
                maxlength="50"></p>
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            Delete:</label>
            <input type="checkbox"
                name="generic_relations-taggeditem-content_type-object_id-0-DELETE"
                id="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            <input type="hidden"
                name="generic_relations-taggeditem-content_type-object_id-0-id"
                id="id_generic_relations-taggeditem-content_type-object_id-0-id"></p>
            """,
        )
        platypus = Animal.objects.create(
            common_name="Platypus",
            latin_name="Ornithorhynchus anatinus",
        )
        platypus.tags.create(tag="shiny")
        GenericFormSet = generic_inlineformset_factory(TaggedItem, extra=1)
        formset = GenericFormSet(instance=platypus)
        tagged_item_id = TaggedItem.objects.get(tag="shiny", object_id=platypus.id).id
        self.assertHTMLEqual(
            "".join(form.as_p() for form in formset.forms),
            """
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-tag">
            Tag:</label>
            <input id="id_generic_relations-taggeditem-content_type-object_id-0-tag"
                type="text"
                name="generic_relations-taggeditem-content_type-object_id-0-tag"
                value="shiny" maxlength="50"></p>
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            Delete:</label>
            <input type="checkbox"
                name="generic_relations-taggeditem-content_type-object_id-0-DELETE"
                id="id_generic_relations-taggeditem-content_type-object_id-0-DELETE">
            <input type="hidden"
                name="generic_relations-taggeditem-content_type-object_id-0-id"
                value="%s"
                id="id_generic_relations-taggeditem-content_type-object_id-0-id"></p>
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-1-tag">
            Tag:</label>
            <input id="id_generic_relations-taggeditem-content_type-object_id-1-tag"
                type="text"
                name="generic_relations-taggeditem-content_type-object_id-1-tag"
                maxlength="50"></p>
            <p><label
                for="id_generic_relations-taggeditem-content_type-object_id-1-DELETE">
            Delete:</label>
            <input type="checkbox"
                name="generic_relations-taggeditem-content_type-object_id-1-DELETE"
                id="id_generic_relations-taggeditem-content_type-object_id-1-DELETE">
            <input type="hidden"
                name="generic_relations-taggeditem-content_type-object_id-1-id"
                id="id_generic_relations-taggeditem-content_type-object_id-1-id"></p>
            """
            % tagged_item_id,
        )
        lion = Animal.objects.create(common_name="Lion", latin_name="Panthera leo")
        formset = GenericFormSet(instance=lion, prefix="x")
        self.assertHTMLEqual(
            "".join(form.as_p() for form in formset.forms),
            """
            <p><label for="id_x-0-tag">Tag:</label>
            <input id="id_x-0-tag" type="text" name="x-0-tag" maxlength="50"></p>
            <p><label for="id_x-0-DELETE">Delete:</label>
            <input type="checkbox" name="x-0-DELETE" id="id_x-0-DELETE">
            <input type="hidden" name="x-0-id" id="id_x-0-id"></p>
            """,
        )

    def test_options(self):
        """
        Tests the functionality of the TaggedItemFormSet, specifically the way it handles related instances of TaggedItem for a given object.

        It checks that the formset is populated with existing instances, and that new instances can be added.

        It also tests the impact of specifying a queryset on the formset, including ordering and filtering existing instances.

        The test covers scenarios where the queryset affects the order and selection of existing instances, as well as the creation of new instances in the formset.
        """
        TaggedItemFormSet = generic_inlineformset_factory(
            TaggedItem,
            can_delete=False,
            exclude=["tag"],
            extra=3,
        )
        platypus = Animal.objects.create(
            common_name="Platypus", latin_name="Ornithorhynchus anatinus"
        )
        harmless = platypus.tags.create(tag="harmless")
        mammal = platypus.tags.create(tag="mammal")
        # Works without a queryset.
        formset = TaggedItemFormSet(instance=platypus)
        self.assertEqual(len(formset.forms), 5)
        self.assertHTMLEqual(
            formset.forms[0].as_p(),
            '<input type="hidden" '
            'name="generic_relations-taggeditem-content_type-object_id-0-id" '
            'value="%s" '
            'id="id_generic_relations-taggeditem-content_type-object_id-0-id">'
            % harmless.pk,
        )
        self.assertEqual(formset.forms[0].instance, harmless)
        self.assertEqual(formset.forms[1].instance, mammal)
        self.assertIsNone(formset.forms[2].instance.pk)
        # A queryset can be used to alter display ordering.
        formset = TaggedItemFormSet(
            instance=platypus, queryset=TaggedItem.objects.order_by("-tag")
        )
        self.assertEqual(len(formset.forms), 5)
        self.assertEqual(formset.forms[0].instance, mammal)
        self.assertEqual(formset.forms[1].instance, harmless)
        self.assertIsNone(formset.forms[2].instance.pk)
        # A queryset that omits items.
        formset = TaggedItemFormSet(
            instance=platypus,
            queryset=TaggedItem.objects.filter(tag__startswith="harm"),
        )
        self.assertEqual(len(formset.forms), 4)
        self.assertEqual(formset.forms[0].instance, harmless)
        self.assertIsNone(formset.forms[1].instance.pk)

    def test_get_queryset_ordering(self):
        """
        BaseGenericInlineFormSet.get_queryset() adds default ordering, if
        needed.
        """
        inline_formset = generic_inlineformset_factory(TaggedItem, exclude=("tag",))
        formset = inline_formset(instance=Gecko.objects.create())
        self.assertIs(formset.get_queryset().ordered, True)

    def test_initial(self):
        quartz = Mineral.objects.create(name="Quartz", hardness=7)
        GenericFormSet = generic_inlineformset_factory(TaggedItem, extra=1)
        ctype = ContentType.objects.get_for_model(quartz)
        initial_data = [
            {
                "tag": "lizard",
                "content_type": ctype.pk,
                "object_id": quartz.pk,
            }
        ]
        formset = GenericFormSet(initial=initial_data)
        self.assertEqual(formset.forms[0].initial, initial_data[0])

    def test_meta_widgets(self):
        """TaggedItemForm has a widget defined in Meta."""
        Formset = generic_inlineformset_factory(TaggedItem, TaggedItemForm)
        form = Formset().forms[0]
        self.assertIsInstance(form["tag"].field.widget, CustomWidget)

    @isolate_apps("generic_relations")
    def test_incorrect_content_type(self):
        """
        Tests that a InvalidModelException is raised when generating an inline formset factory for a model 
        where the 'content_type' field is not a ForeignKey to ContentType.

        Verifies that the generic_inlineformset_factory correctly checks the model's 'content_type' field 
        and raises an exception with a descriptive error message when the field is not properly defined.
        """
        class BadModel(models.Model):
            content_type = models.PositiveIntegerField()

        msg = (
            "fk_name 'generic_relations.BadModel.content_type' is not a ForeignKey to "
            "ContentType"
        )
        with self.assertRaisesMessage(Exception, msg):
            generic_inlineformset_factory(BadModel, TaggedItemForm)

    def test_save_new_uses_form_save(self):
        """

        Tests that saving a new instance using a formset calls the custom save method.

        This test verifies that when a new instance is saved through a formset, 
        the overridden save method of the form is invoked, allowing for custom 
        logic to be executed during the save process.

        The test creates a formset with a custom save method, saves a new instance 
        using the formset, and asserts that the custom save method was called by 
        checking the value of the 'saved_by' attribute.

        """
        class SaveTestForm(forms.ModelForm):
            def save(self, *args, **kwargs):
                """
                Saves the instance to the database, setting the saved_by attribute to 'custom method' before delegating the actual save operation to the parent class. This allows for custom behavior while still utilizing the default save functionality.
                """
                self.instance.saved_by = "custom method"
                return super().save(*args, **kwargs)

        Formset = generic_inlineformset_factory(
            ForProxyModelModel, fields="__all__", form=SaveTestForm
        )
        instance = ProxyRelatedModel.objects.create()
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "foo",
        }
        formset = Formset(data, instance=instance, prefix="form")
        self.assertTrue(formset.is_valid())
        new_obj = formset.save()[0]
        self.assertEqual(new_obj.saved_by, "custom method")

    def test_save_new_for_proxy(self):
        Formset = generic_inlineformset_factory(
            ForProxyModelModel, fields="__all__", for_concrete_model=False
        )
        instance = ProxyRelatedModel.objects.create()
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "foo",
        }
        formset = Formset(data, instance=instance, prefix="form")
        self.assertTrue(formset.is_valid())
        (new_obj,) = formset.save()
        self.assertEqual(new_obj.obj, instance)

    def test_save_new_for_concrete(self):
        """

        Tests the creation and saving of a new ForProxyModelModel instance 
        through a formset, specifically when using a concrete model.

        Verifies that the formset is valid and that the saved object is not an instance of 
        ProxyRelatedModel, confirming the correct usage of the formset factory with 
        the for_concrete_model parameter set to True.

        """
        Formset = generic_inlineformset_factory(
            ForProxyModelModel, fields="__all__", for_concrete_model=True
        )
        instance = ProxyRelatedModel.objects.create()
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "",
            "form-0-title": "foo",
        }
        formset = Formset(data, instance=instance, prefix="form")
        self.assertTrue(formset.is_valid())
        (new_obj,) = formset.save()
        self.assertNotIsInstance(new_obj.obj, ProxyRelatedModel)

    def test_initial_count(self):
        """
        Tests that the initial count of forms in a formset is correctly determined.

        The function checks the initial form count in two scenarios:
        - when the formset is not saving as new, the initial form count should match the number of initial forms specified in the data
        - when the formset is saving as new, the initial form count should be zero, as no existing forms are being edited

        This test ensures that the formset's initial form count method behaves as expected under different conditions, providing a foundation for other tests and usage of the formset functionality.
        """
        GenericFormSet = generic_inlineformset_factory(TaggedItem)
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "",
        }
        formset = GenericFormSet(data=data, prefix="form")
        self.assertEqual(formset.initial_form_count(), 3)
        formset = GenericFormSet(data=data, prefix="form", save_as_new=True)
        self.assertEqual(formset.initial_form_count(), 0)

    def test_save_as_new(self):
        """
        The save_as_new parameter creates new items that are associated with
        the object.
        """
        lion = Animal.objects.create(common_name="Lion", latin_name="Panthera leo")
        yellow = lion.tags.create(tag="yellow")
        hairy = lion.tags.create(tag="hairy")
        GenericFormSet = generic_inlineformset_factory(TaggedItem)
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "2",
            "form-MAX_NUM_FORMS": "",
            "form-0-id": str(yellow.pk),
            "form-0-tag": "hunts",
            "form-1-id": str(hairy.pk),
            "form-1-tag": "roars",
        }
        formset = GenericFormSet(data, instance=lion, prefix="form", save_as_new=True)
        self.assertTrue(formset.is_valid())
        tags = formset.save()
        self.assertEqual([tag.tag for tag in tags], ["hunts", "roars"])
        hunts, roars = tags
        self.assertSequenceEqual(
            lion.tags.order_by("tag"), [hairy, hunts, roars, yellow]
        )

    def test_absolute_max(self):
        """

        Tests the absolute maximum limit of forms in a formset.

        This test verifies that when the absolute maximum number of forms is exceeded,
        the formset is considered invalid and the correct error message is displayed.
        The test also checks that the number of forms in the formset is capped at the
        absolute maximum, rather than allowing more forms to be added.

        The test case simulates a scenario where the user attempts to submit more forms
        than the absolute maximum allowed, and verifies that the formset validation
        behaves as expected.

        """
        GenericFormSet = generic_inlineformset_factory(TaggedItem, absolute_max=1500)
        data = {
            "form-TOTAL_FORMS": "1501",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = GenericFormSet(data=data, prefix="form")
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 1500)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 1000 forms."],
        )

    def test_absolute_max_with_max_num(self):
        GenericFormSet = generic_inlineformset_factory(
            TaggedItem,
            max_num=20,
            absolute_max=100,
        )
        data = {
            "form-TOTAL_FORMS": "101",
            "form-INITIAL_FORMS": "0",
            "form-MAX_NUM_FORMS": "0",
        }
        formset = GenericFormSet(data=data, prefix="form")
        self.assertIs(formset.is_valid(), False)
        self.assertEqual(len(formset.forms), 100)
        self.assertEqual(
            formset.non_form_errors(),
            ["Please submit at most 20 forms."],
        )

    def test_can_delete_extra(self):
        """
        Tests the ability to delete extra forms in a formset.

        This test case verifies that a formset with the can_delete_extra option enabled
        includes a delete checkbox for each extra form, allowing users to remove them.
        It checks the formset length and confirms the presence of the DELETE field in each form.
        """
        GenericFormSet = generic_inlineformset_factory(
            TaggedItem,
            can_delete=True,
            can_delete_extra=True,
            extra=2,
        )
        formset = GenericFormSet()
        self.assertEqual(len(formset), 2)
        self.assertIn("DELETE", formset.forms[0].fields)
        self.assertIn("DELETE", formset.forms[1].fields)

    def test_disable_delete_extra(self):
        """

        Tests the configuration of a generic inline formset with the ability to delete extra forms disabled.

        This test case creates a formset for TaggedItem instances, allowing two extra forms to be rendered.
        It verifies that the formset contains the expected number of forms and that the delete checkbox is not present in any of the forms.

        The purpose of this test is to ensure that the formset behaves correctly when the can_delete_extra parameter is set to False.

        """
        GenericFormSet = generic_inlineformset_factory(
            TaggedItem,
            can_delete=True,
            can_delete_extra=False,
            extra=2,
        )
        formset = GenericFormSet()
        self.assertEqual(len(formset), 2)
        self.assertNotIn("DELETE", formset.forms[0].fields)
        self.assertNotIn("DELETE", formset.forms[1].fields)
