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
        """
        Tests the output of a generic inline formset for a TaggedItem model, 
        verifying that the formset renders correctly in various scenarios, 
        including when no instance is provided, when an instance has no tags, 
        when an instance has a tag, and when a prefix is specified.
        """
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
        Tests the creation and behavior of a formset for editing tagged items associated with an instance, verifying the correct number of forms, form field values, and instance ordering.
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
        """

        Verifies that initial data is correctly set on a generic inline formset.

        Tests that the initial data provided to the formset is properly assigned to the form instance.

        """
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

        Tests that a factory function raises an exception when the foreign key is not to ContentType.

        The function checks that creating a generic inline formset factory fails when the provided model does not have a ForeignKey to ContentType.

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
        Test that a new object saved using a custom form with a overridden save method 
        correctly calls the custom save method and stores the saved_by attribute.
        """
        class SaveTestForm(forms.ModelForm):
            def save(self, *args, **kwargs):
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
        """
        Tests the saving of a new ForProxyModelModel instance using an inline formset, ensuring that it correctly associates the new instance with a ProxyRelatedModel instance.
        """
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
        Tests the saving of a new inline formset instance for a concrete model, ensuring the saved object is not an instance of the proxy model.
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
        Tests the initial count of forms in a formset, ensuring it is correctly calculated based on the provided data and whether the formset is being used to save new forms or edit existing ones.
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
        Tests that a formset with an absolute maximum number of forms rejects submissions with more forms than allowed, and correctly reports the maximum form limit error.
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
        """
        Tests the validation of a GenericFormSet with an absolute maximum number of forms (100) when the actual number of forms submitted exceeds the specified maximum number (20), ensuring that validation fails and the correct error message is raised.
        """
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
        Tests that a formset with can_delete_extra set to True renders delete checkboxes for extra forms.
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
        Tests that deleting extra formset forms is disabled when can_delete_extra is False, 
        while can_delete is True, verifying the absence of 'DELETE' field in the forms.
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
