from django.contrib.admin import ModelAdmin, TabularInline
from django.contrib.admin.helpers import InlineAdminForm
from django.contrib.admin.tests import AdminSeleniumTestCase
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase, override_settings
from django.test.selenium import screenshot_cases
from django.urls import reverse
from django.utils.translation import gettext

from .admin import InnerInline
from .admin import site as admin_site
from .models import (
    Author,
    BinaryTree,
    Book,
    BothVerboseNameProfile,
    Chapter,
    Child,
    ChildModel1,
    ChildModel2,
    Fashionista,
    FootNote,
    Holder,
    Holder2,
    Holder3,
    Holder4,
    Inner,
    Inner2,
    Inner3,
    Inner4Stacked,
    Inner4Tabular,
    Novel,
    OutfitItem,
    Parent,
    ParentModelWithCustomPk,
    Person,
    Poll,
    Profile,
    ProfileCollection,
    Question,
    ShowInlineParent,
    Sighting,
    SomeChildModel,
    SomeParentModel,
    Teacher,
    UUIDChild,
    UUIDParent,
    VerboseNamePluralProfile,
    VerboseNameProfile,
)

INLINE_CHANGELINK_HTML = 'class="inlinechangelink">Change</a>'


class TestDataMixin:
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super", email="super@example.com", password="secret"
        )


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInline(TestDataMixin, TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This method creates a set of objects and relationships that can be used to test the functionality of the class.
        It includes creating a holder and an inner object, a parent and child models, as well as a user with specific permissions.
        The created data includes:

        * A holder object with associated inner object
        * A parent model with two child models
        * A user with staff status and view permissions for the parent and child models

        The created objects are stored as class attributes, allowing them to be accessed and used throughout the test class.

        """
        super().setUpTestData()
        cls.holder = Holder.objects.create(dummy=13)
        Inner.objects.create(dummy=42, holder=cls.holder)

        cls.parent = SomeParentModel.objects.create(name="a")
        SomeChildModel.objects.create(name="b", position="0", parent=cls.parent)
        SomeChildModel.objects.create(name="c", position="1", parent=cls.parent)

        cls.view_only_user = User.objects.create_user(
            username="user",
            password="pwd",
            is_staff=True,
        )
        parent_ct = ContentType.objects.get_for_model(SomeParentModel)
        child_ct = ContentType.objects.get_for_model(SomeChildModel)
        permission = Permission.objects.get(
            codename="view_someparentmodel",
            content_type=parent_ct,
        )
        cls.view_only_user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="view_somechildmodel",
            content_type=child_ct,
        )
        cls.view_only_user.user_permissions.add(permission)

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_can_delete(self):
        """
        can_delete should be passed to inlineformset factory.
        """
        response = self.client.get(
            reverse("admin:admin_inlines_holder_change", args=(self.holder.id,))
        )
        inner_formset = response.context["inline_admin_formsets"][0].formset
        expected = InnerInline.can_delete
        actual = inner_formset.can_delete
        self.assertEqual(expected, actual, "can_delete must be equal")

    def test_readonly_stacked_inline_label(self):
        """Bug #13174."""
        holder = Holder.objects.create(dummy=42)
        Inner.objects.create(holder=holder, dummy=42, readonly="")
        response = self.client.get(
            reverse("admin:admin_inlines_holder_change", args=(holder.id,))
        )
        self.assertContains(response, "<label>Inner readonly label:</label>")

    def test_excluded_id_for_inlines_uses_hidden_field(self):
        """
        Tests that the excluded inline id uses a hidden field when rendering the admin change page for a model instance with inlines.

        Verifies that when an inline model instance is excluded from the admin change page, its id is still submitted using a hidden form field.
        This ensures that the instance is properly associated with its parent model when the form is saved.
        """
        parent = UUIDParent.objects.create()
        child = UUIDChild.objects.create(title="foo", parent=parent)
        response = self.client.get(
            reverse("admin:admin_inlines_uuidparent_change", args=(parent.id,))
        )
        self.assertContains(
            response,
            f'<input type="hidden" name="uuidchild_set-0-id" value="{child.id}" '
            'id="id_uuidchild_set-0-id">',
            html=True,
        )

    def test_many_to_many_inlines(self):
        "Autogenerated many-to-many inlines are displayed correctly (#13407)"
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        # The heading for the m2m inline block uses the right text
        self.assertContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        # The "add another" label is correct
        self.assertContains(response, "Add another Author-book relationship")
        # The '+' is dropped from the autogenerated form prefix (Author_books+)
        self.assertContains(response, 'id="id_Author_books-TOTAL_FORMS"')

    def test_inline_primary(self):
        person = Person.objects.create(firstname="Imelda")
        item = OutfitItem.objects.create(name="Shoes")
        # Imelda likes shoes, but can't carry her own bags.
        data = {
            "shoppingweakness_set-TOTAL_FORMS": 1,
            "shoppingweakness_set-INITIAL_FORMS": 0,
            "shoppingweakness_set-MAX_NUM_FORMS": 0,
            "_save": "Save",
            "person": person.id,
            "max_weight": 0,
            "shoppingweakness_set-0-item": item.id,
        }
        response = self.client.post(
            reverse("admin:admin_inlines_fashionista_add"), data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(Fashionista.objects.filter(person__firstname="Imelda")), 1)

    def test_tabular_inline_column_css_class(self):
        """
        Field names are included in the context to output a field-specific
        CSS class name in the column headers.
        """
        response = self.client.get(reverse("admin:admin_inlines_poll_add"))
        text_field, call_me_field = list(
            response.context["inline_admin_formset"].fields()
        )
        # Editable field.
        self.assertEqual(text_field["name"], "text")
        self.assertContains(response, '<th class="column-text required">')
        # Read-only field.
        self.assertEqual(call_me_field["name"], "call_me")
        self.assertContains(response, '<th class="column-call_me">')

    def test_custom_form_tabular_inline_label(self):
        """
        A model form with a form field specified (TitleForm.title1) should have
        its label rendered in the tabular inline.
        """
        response = self.client.get(reverse("admin:admin_inlines_titlecollection_add"))
        self.assertContains(
            response, '<th class="column-title1 required">Title1</th>', html=True
        )

    def test_custom_form_tabular_inline_extra_field_label(self):
        """
        Tests the label of the extra field in a custom form's tabular inline admin interface.

        This test case verifies that the extra field is properly labeled in the admin interface.
        It checks the label of the extra field in the inline formset, ensuring it matches the expected value.
        The test provides assurance that the custom form's tabular inline admin interface is correctly configured and rendered.
        """
        response = self.client.get(reverse("admin:admin_inlines_outfititem_add"))
        _, extra_field = list(response.context["inline_admin_formset"].fields())
        self.assertEqual(extra_field["label"], "Extra field")

    def test_non_editable_custom_form_tabular_inline_extra_field_label(self):
        """
        Tests that the label of the extra field in a custom form tabular inline is correctly set to \"Extra field\" when rendering the \"Add\" page for a chapter admin inline. Verifies that the field is properly labeled in the admin interface.
        """
        response = self.client.get(reverse("admin:admin_inlines_chapter_add"))
        _, extra_field = list(response.context["inline_admin_formset"].fields())
        self.assertEqual(extra_field["label"], "Extra field")

    def test_custom_form_tabular_inline_overridden_label(self):
        """
        SomeChildModelForm.__init__() overrides the label of a form field.
        That label is displayed in the TabularInline.
        """
        response = self.client.get(reverse("admin:admin_inlines_someparentmodel_add"))
        field = list(response.context["inline_admin_formset"].fields())[0]
        self.assertEqual(field["label"], "new label")
        self.assertContains(
            response, '<th class="column-name required">New label</th>', html=True
        )

    def test_tabular_non_field_errors(self):
        """
        non_field_errors are displayed correctly, including the correct value
        for colspan.
        """
        data = {
            "title_set-TOTAL_FORMS": 1,
            "title_set-INITIAL_FORMS": 0,
            "title_set-MAX_NUM_FORMS": 0,
            "_save": "Save",
            "title_set-0-title1": "a title",
            "title_set-0-title2": "a different title",
        }
        response = self.client.post(
            reverse("admin:admin_inlines_titlecollection_add"), data
        )
        # Here colspan is "4": two fields (title1 and title2), one hidden field
        # and the delete checkbox.
        self.assertContains(
            response,
            '<tr class="row-form-errors"><td colspan="4">'
            '<ul class="errorlist nonfield">'
            "<li>The two titles must be the same</li></ul></td></tr>",
        )

    def test_no_parent_callable_lookup(self):
        """Admin inline `readonly_field` shouldn't invoke parent ModelAdmin callable"""
        # Identically named callable isn't present in the parent ModelAdmin,
        # rendering of the add view shouldn't explode
        response = self.client.get(reverse("admin:admin_inlines_novel_add"))
        # View should have the child inlines section
        self.assertContains(
            response,
            '<div class="js-inline-admin-formset inline-group" id="chapter_set-group"',
        )

    def test_callable_lookup(self):
        """
        Admin inline should invoke local callable when its name is listed in
        readonly_fields.
        """
        response = self.client.get(reverse("admin:admin_inlines_poll_add"))
        # Add parent object view should have the child inlines section
        self.assertContains(
            response,
            '<div class="js-inline-admin-formset inline-group" id="question_set-group"',
        )
        # The right callable should be used for the inline readonly_fields
        # column cells
        self.assertContains(response, "<p>Callable in QuestionInline</p>")

    def test_model_error_inline_with_readonly_field(self):
        """
        Tests that an error message is displayed inline when a model with a readonly field is invalid.

        This test case creates a new poll object and attempts to save it with a question set via an admin inline form.
        It then checks that the response contains an error message indicating that the model is always invalid, as expected.

        This ensures that error messages are correctly displayed for models with readonly fields, even when using inline forms in the admin interface.
        """
        poll = Poll.objects.create(name="Test poll")
        data = {
            "question_set-TOTAL_FORMS": 1,
            "question_set-INITIAL_FORMS": 0,
            "question_set-MAX_NUM_FORMS": 0,
            "_save": "Save",
            "question_set-0-text": "Question",
            "question_set-0-poll": poll.pk,
        }
        response = self.client.post(
            reverse("admin:admin_inlines_poll_change", args=(poll.pk,)),
            data,
        )
        self.assertContains(response, "Always invalid model.")

    def test_help_text(self):
        """
        The inlines' model field help texts are displayed when using both the
        stacked and tabular layouts.
        """
        response = self.client.get(reverse("admin:admin_inlines_holder4_add"))
        self.assertContains(response, "Awesome stacked help text is awesome.", 4)
        self.assertContains(
            response,
            '<img src="/static/admin/img/icon-unknown.svg" '
            'class="help help-tooltip" width="10" height="10" '
            'alt="(Awesome tabular help text is awesome.)" '
            'title="Awesome tabular help text is awesome.">',
            1,
        )
        # ReadOnly fields
        response = self.client.get(reverse("admin:admin_inlines_capofamiglia_add"))
        self.assertContains(
            response,
            '<img src="/static/admin/img/icon-unknown.svg" '
            'class="help help-tooltip" width="10" height="10" '
            'alt="(Help text for ReadOnlyInline)" '
            'title="Help text for ReadOnlyInline">',
            1,
        )

    def test_tabular_model_form_meta_readonly_field(self):
        """
        Tabular inlines use ModelForm.Meta.help_texts and labels for read-only
        fields.
        """
        response = self.client.get(reverse("admin:admin_inlines_someparentmodel_add"))
        self.assertContains(
            response,
            '<img src="/static/admin/img/icon-unknown.svg" '
            'class="help help-tooltip" width="10" height="10" '
            'alt="(Help text from ModelForm.Meta)" '
            'title="Help text from ModelForm.Meta">',
        )
        self.assertContains(response, "Label from ModelForm.Meta")

    def test_inline_hidden_field_no_column(self):
        """#18263 -- Make sure hidden fields don't get a column in tabular inlines"""
        parent = SomeParentModel.objects.create(name="a")
        SomeChildModel.objects.create(name="b", position="0", parent=parent)
        SomeChildModel.objects.create(name="c", position="1", parent=parent)
        response = self.client.get(
            reverse("admin:admin_inlines_someparentmodel_change", args=(parent.pk,))
        )
        self.assertNotContains(response, '<td class="field-position">')
        self.assertInHTML(
            '<input id="id_somechildmodel_set-1-position" '
            'name="somechildmodel_set-1-position" type="hidden" value="1">',
            response.rendered_content,
        )

    def test_tabular_inline_hidden_field_with_view_only_permissions(self):
        """
        Content of hidden field is not visible in tabular inline when user has
        view-only permission.
        """
        self.client.force_login(self.view_only_user)
        url = reverse(
            "tabular_inline_hidden_field_admin:admin_inlines_someparentmodel_change",
            args=(self.parent.pk,),
        )
        response = self.client.get(url)
        self.assertInHTML(
            '<th class="column-position hidden">Position</th>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<td class="field-position hidden"><p>0</p></td>', response.rendered_content
        )
        self.assertInHTML(
            '<td class="field-position hidden"><p>1</p></td>', response.rendered_content
        )

    def test_stacked_inline_hidden_field_with_view_only_permissions(self):
        """
        Content of hidden field is not visible in stacked inline when user has
        view-only permission.
        """
        self.client.force_login(self.view_only_user)
        url = reverse(
            "stacked_inline_hidden_field_in_group_admin:"
            "admin_inlines_someparentmodel_change",
            args=(self.parent.pk,),
        )
        response = self.client.get(url)
        # The whole line containing name + position fields is not hidden.
        self.assertContains(
            response, '<div class="form-row field-name field-position">'
        )
        # The div containing the position field is hidden.
        self.assertInHTML(
            '<div class="flex-container fieldBox field-position hidden">'
            '<label class="inline">Position:</label>'
            '<div class="readonly">0</div></div>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<div class="flex-container fieldBox field-position hidden">'
            '<label class="inline">Position:</label>'
            '<div class="readonly">1</div></div>',
            response.rendered_content,
        )

    def test_stacked_inline_single_hidden_field_in_line_with_view_only_permissions(
        self,
    ):
        """
        Content of hidden field is not visible in stacked inline when user has
        view-only permission and the field is grouped on a separate line.
        """
        self.client.force_login(self.view_only_user)
        url = reverse(
            "stacked_inline_hidden_field_on_single_line_admin:"
            "admin_inlines_someparentmodel_change",
            args=(self.parent.pk,),
        )
        response = self.client.get(url)
        # The whole line containing position field is hidden.
        self.assertInHTML(
            '<div class="form-row hidden field-position">'
            '<div><div class="flex-container"><label>Position:</label>'
            '<div class="readonly">0</div></div></div></div>',
            response.rendered_content,
        )
        self.assertInHTML(
            '<div class="form-row hidden field-position">'
            '<div><div class="flex-container"><label>Position:</label>'
            '<div class="readonly">1</div></div></div></div>',
            response.rendered_content,
        )

    def test_tabular_inline_with_hidden_field_non_field_errors_has_correct_colspan(
        self,
    ):
        """
        In tabular inlines, when a form has non-field errors, those errors
        are rendered in a table line with a single cell spanning the whole
        table width. Colspan must be equal to the number of visible columns.
        """
        parent = SomeParentModel.objects.create(name="a")
        child = SomeChildModel.objects.create(name="b", position="0", parent=parent)
        url = reverse(
            "tabular_inline_hidden_field_admin:admin_inlines_someparentmodel_change",
            args=(parent.id,),
        )
        data = {
            "name": parent.name,
            "somechildmodel_set-TOTAL_FORMS": 1,
            "somechildmodel_set-INITIAL_FORMS": 1,
            "somechildmodel_set-MIN_NUM_FORMS": 0,
            "somechildmodel_set-MAX_NUM_FORMS": 1000,
            "_save": "Save",
            "somechildmodel_set-0-id": child.id,
            "somechildmodel_set-0-parent": parent.id,
            "somechildmodel_set-0-name": child.name,
            "somechildmodel_set-0-position": 1,
        }
        response = self.client.post(url, data)
        # Form has 3 visible columns and 1 hidden column.
        self.assertInHTML(
            '<thead><tr><th class="original"></th>'
            '<th class="column-name required">Name</th>'
            '<th class="column-position required hidden">Position</th>'
            "<th>Delete?</th></tr></thead>",
            response.rendered_content,
        )
        # The non-field error must be spanned on 3 (visible) columns.
        self.assertInHTML(
            '<tr class="row-form-errors"><td colspan="3">'
            '<ul class="errorlist nonfield"><li>A non-field error</li></ul></td></tr>',
            response.rendered_content,
        )

    def test_non_related_name_inline(self):
        """
        Multiple inlines with related_name='+' have correct form prefixes.
        """
        response = self.client.get(reverse("admin:admin_inlines_capofamiglia_add"))
        self.assertContains(
            response, '<input type="hidden" name="-1-0-id" id="id_-1-0-id">', html=True
        )
        self.assertContains(
            response,
            '<input type="hidden" name="-1-0-capo_famiglia" '
            'id="id_-1-0-capo_famiglia">',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_-1-0-name" type="text" class="vTextField" name="-1-0-name" '
            'maxlength="100" aria-describedby="id_-1-0-name_helptext">',
            html=True,
        )
        self.assertContains(
            response, '<input type="hidden" name="-2-0-id" id="id_-2-0-id">', html=True
        )
        self.assertContains(
            response,
            '<input type="hidden" name="-2-0-capo_famiglia" '
            'id="id_-2-0-capo_famiglia">',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_-2-0-name" type="text" class="vTextField" name="-2-0-name" '
            'maxlength="100">',
            html=True,
        )

    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_localize_pk_shortcut(self):
        """
        The "View on Site" link is correct for locales that use thousand
        separators.
        """
        holder = Holder.objects.create(pk=123456789, dummy=42)
        inner = Inner.objects.create(pk=987654321, holder=holder, dummy=42, readonly="")
        response = self.client.get(
            reverse("admin:admin_inlines_holder_change", args=(holder.id,))
        )
        inner_shortcut = "r/%s/%s/" % (
            ContentType.objects.get_for_model(inner).pk,
            inner.pk,
        )
        self.assertContains(response, inner_shortcut)

    def test_custom_pk_shortcut(self):
        """
        The "View on Site" link is correct for models with a custom primary key
        field.
        """
        parent = ParentModelWithCustomPk.objects.create(my_own_pk="foo", name="Foo")
        child1 = ChildModel1.objects.create(my_own_pk="bar", name="Bar", parent=parent)
        child2 = ChildModel2.objects.create(my_own_pk="baz", name="Baz", parent=parent)
        response = self.client.get(
            reverse("admin:admin_inlines_parentmodelwithcustompk_change", args=("foo",))
        )
        child1_shortcut = "r/%s/%s/" % (
            ContentType.objects.get_for_model(child1).pk,
            child1.pk,
        )
        child2_shortcut = "r/%s/%s/" % (
            ContentType.objects.get_for_model(child2).pk,
            child2.pk,
        )
        self.assertContains(response, child1_shortcut)
        self.assertContains(response, child2_shortcut)

    def test_create_inlines_on_inherited_model(self):
        """
        An object can be created with inlines when it inherits another class.
        """
        data = {
            "name": "Martian",
            "sighting_set-TOTAL_FORMS": 1,
            "sighting_set-INITIAL_FORMS": 0,
            "sighting_set-MAX_NUM_FORMS": 0,
            "sighting_set-0-place": "Zone 51",
            "_save": "Save",
        }
        response = self.client.post(
            reverse("admin:admin_inlines_extraterrestrial_add"), data
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sighting.objects.filter(et__name="Martian").count(), 1)

    def test_custom_get_extra_form(self):
        """
        Tests the custom get extra form functionality in the admin interface.

        This test case covers the addition and modification of binary tree objects
        in the admin interface, verifying that the correct number of extra forms
        is displayed for both add and change views.

        Specifically, it checks that the \"MAX_NUM_FORMS\" and \"TOTAL_FORMS\" hidden
        input fields are correctly rendered in the HTML response, with the expected
        values for both newly created and existing binary tree objects.
        """
        bt_head = BinaryTree.objects.create(name="Tree Head")
        BinaryTree.objects.create(name="First Child", parent=bt_head)
        # The maximum number of forms should respect 'get_max_num' on the
        # ModelAdmin
        max_forms_input = (
            '<input id="id_binarytree_set-MAX_NUM_FORMS" '
            'name="binarytree_set-MAX_NUM_FORMS" type="hidden" value="%d">'
        )
        # The total number of forms will remain the same in either case
        total_forms_hidden = (
            '<input id="id_binarytree_set-TOTAL_FORMS" '
            'name="binarytree_set-TOTAL_FORMS" type="hidden" value="2">'
        )
        response = self.client.get(reverse("admin:admin_inlines_binarytree_add"))
        self.assertInHTML(max_forms_input % 3, response.rendered_content)
        self.assertInHTML(total_forms_hidden, response.rendered_content)

        response = self.client.get(
            reverse("admin:admin_inlines_binarytree_change", args=(bt_head.id,))
        )
        self.assertInHTML(max_forms_input % 2, response.rendered_content)
        self.assertInHTML(total_forms_hidden, response.rendered_content)

    def test_min_num(self):
        """
        min_num and extra determine number of forms.
        """

        class MinNumInline(TabularInline):
            model = BinaryTree
            min_num = 2
            extra = 3

        modeladmin = ModelAdmin(BinaryTree, admin_site)
        modeladmin.inlines = [MinNumInline]
        min_forms = (
            '<input id="id_binarytree_set-MIN_NUM_FORMS" '
            'name="binarytree_set-MIN_NUM_FORMS" type="hidden" value="2">'
        )
        total_forms = (
            '<input id="id_binarytree_set-TOTAL_FORMS" '
            'name="binarytree_set-TOTAL_FORMS" type="hidden" value="5">'
        )
        request = self.factory.get(reverse("admin:admin_inlines_binarytree_add"))
        request.user = User(username="super", is_superuser=True)
        response = modeladmin.changeform_view(request)
        self.assertInHTML(min_forms, response.rendered_content)
        self.assertInHTML(total_forms, response.rendered_content)

    def test_custom_min_num(self):
        """

        Tests the custom minimum number of inline forms for a BinaryTree model in the admin interface.

        This test covers two scenarios: adding a new BinaryTree instance and changing an existing one.
        It verifies that the minimum number of inline forms is correctly set based on the
        get_min_num method of the MinNumInline class, which returns different values depending
        on whether an object is being edited or not.

        The test checks that the HTML response contains the correct minimum and total number of forms
        for both scenarios, ensuring that the custom minimum number of inline forms is correctly applied.

        """
        bt_head = BinaryTree.objects.create(name="Tree Head")
        BinaryTree.objects.create(name="First Child", parent=bt_head)

        class MinNumInline(TabularInline):
            model = BinaryTree
            extra = 3

            def get_min_num(self, request, obj=None, **kwargs):
                """

                Retrieve the minimum number based on the provided object.

                This function returns a minimum number, which can vary depending on whether an object is provided.
                If an object is supplied, it returns 5; otherwise, it returns 2.

                :param request: The current request
                :param obj: The object to consider when determining the minimum number, defaults to None
                :param kwargs: Additional keyword arguments
                :return: The minimum number

                """
                if obj:
                    return 5
                return 2

        modeladmin = ModelAdmin(BinaryTree, admin_site)
        modeladmin.inlines = [MinNumInline]
        min_forms = (
            '<input id="id_binarytree_set-MIN_NUM_FORMS" '
            'name="binarytree_set-MIN_NUM_FORMS" type="hidden" value="%d">'
        )
        total_forms = (
            '<input id="id_binarytree_set-TOTAL_FORMS" '
            'name="binarytree_set-TOTAL_FORMS" type="hidden" value="%d">'
        )
        request = self.factory.get(reverse("admin:admin_inlines_binarytree_add"))
        request.user = User(username="super", is_superuser=True)
        response = modeladmin.changeform_view(request)
        self.assertInHTML(min_forms % 2, response.rendered_content)
        self.assertInHTML(total_forms % 5, response.rendered_content)

        request = self.factory.get(
            reverse("admin:admin_inlines_binarytree_change", args=(bt_head.id,))
        )
        request.user = User(username="super", is_superuser=True)
        response = modeladmin.changeform_view(request, object_id=str(bt_head.id))
        self.assertInHTML(min_forms % 5, response.rendered_content)
        self.assertInHTML(total_forms % 8, response.rendered_content)

    def test_inline_nonauto_noneditable_pk(self):
        """
        Tests the presence of non-auto and non-editable primary keys in the inlines form on the admin author add page.

        Verifies that the HTML response contains the expected hidden input fields for the primary keys of the non-auto PK book set, confirming that they are properly rendered and not editable by the user.

        The test ensures that the primary keys are correctly displayed as hidden fields, with the expected IDs and names, in the admin interface for adding authors with inlines.
        """
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        self.assertContains(
            response,
            '<input id="id_nonautopkbook_set-0-rand_pk" '
            'name="nonautopkbook_set-0-rand_pk" type="hidden">',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_nonautopkbook_set-2-0-rand_pk" '
            'name="nonautopkbook_set-2-0-rand_pk" type="hidden">',
            html=True,
        )

    def test_inline_nonauto_noneditable_inherited_pk(self):
        """

        Tests the render of non-auto, non-editable primary key fields in admin inlines.

        Verifies that the specified HTML elements are present in the response when adding a new author.
        The test checks for the presence of hidden input fields containing the primary key values
        for the non-auto PK book child set, ensuring correct rendering of inherited primary keys.

        """
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        self.assertContains(
            response,
            '<input id="id_nonautopkbookchild_set-0-nonautopkbook_ptr" '
            'name="nonautopkbookchild_set-0-nonautopkbook_ptr" type="hidden">',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_nonautopkbookchild_set-2-nonautopkbook_ptr" '
            'name="nonautopkbookchild_set-2-nonautopkbook_ptr" type="hidden">',
            html=True,
        )

    def test_inline_editable_pk(self):
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        self.assertContains(
            response,
            '<input class="vIntegerField" id="id_editablepkbook_set-0-manual_pk" '
            'name="editablepkbook_set-0-manual_pk" type="number">',
            html=True,
            count=1,
        )
        self.assertContains(
            response,
            '<input class="vIntegerField" id="id_editablepkbook_set-2-0-manual_pk" '
            'name="editablepkbook_set-2-0-manual_pk" type="number">',
            html=True,
            count=1,
        )

    def test_stacked_inline_edit_form_contains_has_original_class(self):
        """
        Tests that the stacked inline edit form for the Holder model contains the expected HTML structure.

        Verifies that when rendering the change form for a Holder instance in the admin interface,
        the inline formset for the inner set contains the correct classes and identifiers, 
        indicating the original and additional instances, respectively.
        """
        holder = Holder.objects.create(dummy=1)
        holder.inner_set.create(dummy=1)
        response = self.client.get(
            reverse("admin:admin_inlines_holder_change", args=(holder.pk,))
        )
        self.assertContains(
            response,
            '<div class="inline-related has_original" id="inner_set-0">',
            count=1,
        )
        self.assertContains(
            response, '<div class="inline-related" id="inner_set-1">', count=1
        )

    def test_inlines_show_change_link_registered(self):
        "Inlines `show_change_link` for registered models when enabled."
        holder = Holder4.objects.create(dummy=1)
        item1 = Inner4Stacked.objects.create(dummy=1, holder=holder)
        item2 = Inner4Tabular.objects.create(dummy=1, holder=holder)
        items = (
            ("inner4stacked", item1.pk),
            ("inner4tabular", item2.pk),
        )
        response = self.client.get(
            reverse("admin:admin_inlines_holder4_change", args=(holder.pk,))
        )
        self.assertTrue(
            response.context["inline_admin_formset"].opts.has_registered_model
        )
        for model, pk in items:
            url = reverse("admin:admin_inlines_%s_change" % model, args=(pk,))
            self.assertContains(
                response, '<a href="%s" %s' % (url, INLINE_CHANGELINK_HTML)
            )

    def test_inlines_show_change_link_unregistered(self):
        "Inlines `show_change_link` disabled for unregistered models."
        parent = ParentModelWithCustomPk.objects.create(my_own_pk="foo", name="Foo")
        ChildModel1.objects.create(my_own_pk="bar", name="Bar", parent=parent)
        ChildModel2.objects.create(my_own_pk="baz", name="Baz", parent=parent)
        response = self.client.get(
            reverse("admin:admin_inlines_parentmodelwithcustompk_change", args=("foo",))
        )
        self.assertFalse(
            response.context["inline_admin_formset"].opts.has_registered_model
        )
        self.assertNotContains(response, INLINE_CHANGELINK_HTML)

    def test_tabular_inline_show_change_link_false_registered(self):
        "Inlines `show_change_link` disabled by default."
        poll = Poll.objects.create(name="New poll")
        Question.objects.create(poll=poll)
        response = self.client.get(
            reverse("admin:admin_inlines_poll_change", args=(poll.pk,))
        )
        self.assertTrue(
            response.context["inline_admin_formset"].opts.has_registered_model
        )
        self.assertNotContains(response, INLINE_CHANGELINK_HTML)

    def test_noneditable_inline_has_field_inputs(self):
        """Inlines without change permission shows field inputs on add form."""
        response = self.client.get(
            reverse("admin:admin_inlines_novelreadonlychapter_add")
        )
        self.assertContains(
            response,
            '<input type="text" name="chapter_set-0-name" '
            'class="vTextField" maxlength="40" id="id_chapter_set-0-name">',
            html=True,
        )

    def test_inlines_plural_heading_foreign_key(self):
        response = self.client.get(reverse("admin:admin_inlines_holder4_add"))
        self.assertContains(
            response,
            (
                '<h2 id="inner4stacked_set-heading" class="inline-heading">'
                "Inner4 stackeds</h2>"
            ),
            html=True,
        )
        self.assertContains(
            response,
            (
                '<h2 id="inner4tabular_set-heading" class="inline-heading">'
                "Inner4 tabulars</h2>"
            ),
            html=True,
        )

    def test_inlines_singular_heading_one_to_one(self):
        """

        Tests the rendering of singular headings for inlines in the admin interface.

        Verifies that the add person admin page contains the correct inline headings, 
        including 'Author' and 'Fashionista', ensuring that each is displayed as an 
        h2 element with the corresponding id and class.

        """
        response = self.client.get(reverse("admin:admin_inlines_person_add"))
        self.assertContains(
            response,
            '<h2 id="author-heading" class="inline-heading">Author</h2>',
            html=True,
        )  # Tabular.
        self.assertContains(
            response,
            '<h2 id="fashionista-heading" class="inline-heading">Fashionista</h2>',
            html=True,
        )  # Stacked.

    def test_inlines_based_on_model_state(self):
        parent = ShowInlineParent.objects.create(show_inlines=False)
        data = {
            "show_inlines": "on",
            "_save": "Save",
        }
        change_url = reverse(
            "admin:admin_inlines_showinlineparent_change",
            args=(parent.id,),
        )
        response = self.client.post(change_url, data)
        self.assertEqual(response.status_code, 302)
        parent.refresh_from_db()
        self.assertIs(parent.show_inlines, True)


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInlineMedia(TestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_inline_media_only_base(self):
        holder = Holder(dummy=13)
        holder.save()
        Inner(dummy=42, holder=holder).save()
        change_url = reverse("admin:admin_inlines_holder_change", args=(holder.id,))
        response = self.client.get(change_url)
        self.assertContains(response, "my_awesome_admin_scripts.js")

    def test_inline_media_only_inline(self):
        """
        Tests the inclusion of inline media in the admin change view for the Holder3 model. 

         Specifically, it verifies that the JavaScript files required for the inline formsets are correctly included in the page. 
         The test case checks for the presence of both default Django admin scripts and custom scripts, ensuring that they are loaded in the expected order. 

         The goal of this test is to ensure that the necessary JavaScript resources are properly injected into the page when displaying inline formsets, allowing for seamless functionality and user interaction.
        """
        holder = Holder3(dummy=13)
        holder.save()
        Inner3(dummy=42, holder=holder).save()
        change_url = reverse("admin:admin_inlines_holder3_change", args=(holder.id,))
        response = self.client.get(change_url)
        self.assertEqual(
            response.context["inline_admin_formsets"][0].media._js,
            [
                "admin/js/vendor/jquery/jquery.min.js",
                "my_awesome_inline_scripts.js",
                "custom_number.js",
                "admin/js/jquery.init.js",
                "admin/js/inlines.js",
            ],
        )
        self.assertContains(response, "my_awesome_inline_scripts.js")

    def test_all_inline_media(self):
        """
        Tests that the custom JavaScript files are correctly included in the admin inline media for Holder2 instances.

        The test case verifies that both 'my_awesome_admin_scripts.js' and 'my_awesome_inline_scripts.js' are present in the admin change page for a Holder2 object, after creating a Holder2 instance and an associated Inner2 instance.
        """
        holder = Holder2(dummy=13)
        holder.save()
        Inner2(dummy=42, holder=holder).save()
        change_url = reverse("admin:admin_inlines_holder2_change", args=(holder.id,))
        response = self.client.get(change_url)
        self.assertContains(response, "my_awesome_admin_scripts.js")
        self.assertContains(response, "my_awesome_inline_scripts.js")


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInlineAdminForm(TestCase):
    def test_immutable_content_type(self):
        """Regression for #9362
        The problem depends only on InlineAdminForm and its "original"
        argument, so we can safely set the other arguments to None/{}. We just
        need to check that the content_type argument of Child isn't altered by
        the internals of the inline form."""

        sally = Teacher.objects.create(name="Sally")
        john = Parent.objects.create(name="John")
        joe = Child.objects.create(name="Joe", teacher=sally, parent=john)

        iaf = InlineAdminForm(None, None, {}, {}, joe)
        parent_ct = ContentType.objects.get_for_model(Parent)
        self.assertEqual(iaf.original.content_type, parent_ct)


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInlineProtectedOnDelete(TestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_deleting_inline_with_protected_delete_does_not_validate(self):
        lotr = Novel.objects.create(name="Lord of the rings")
        chapter = Chapter.objects.create(novel=lotr, name="Many Meetings")
        foot_note = FootNote.objects.create(chapter=chapter, note="yadda yadda")

        change_url = reverse("admin:admin_inlines_novel_change", args=(lotr.id,))
        response = self.client.get(change_url)
        data = {
            "name": lotr.name,
            "chapter_set-TOTAL_FORMS": 1,
            "chapter_set-INITIAL_FORMS": 1,
            "chapter_set-MAX_NUM_FORMS": 1000,
            "_save": "Save",
            "chapter_set-0-id": chapter.id,
            "chapter_set-0-name": chapter.name,
            "chapter_set-0-novel": lotr.id,
            "chapter_set-0-DELETE": "on",
        }
        response = self.client.post(change_url, data)
        self.assertContains(
            response,
            "Deleting chapter %s would require deleting "
            "the following protected related objects: foot note %s"
            % (chapter, foot_note),
        )


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInlinePermissions(TestCase):
    """
    Make sure the admin respects permissions for objects that are edited
    inline. Refs #8060.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User(username="admin", is_staff=True, is_active=True)
        cls.user.set_password("secret")
        cls.user.save()

        cls.author_ct = ContentType.objects.get_for_model(Author)
        cls.holder_ct = ContentType.objects.get_for_model(Holder2)
        cls.book_ct = ContentType.objects.get_for_model(Book)
        cls.inner_ct = ContentType.objects.get_for_model(Inner2)

        # User always has permissions to add and change Authors, and Holders,
        # the main (parent) models of the inlines. Permissions on the inlines
        # vary per test.
        permission = Permission.objects.get(
            codename="add_author", content_type=cls.author_ct
        )
        cls.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="change_author", content_type=cls.author_ct
        )
        cls.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="add_holder2", content_type=cls.holder_ct
        )
        cls.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="change_holder2", content_type=cls.holder_ct
        )
        cls.user.user_permissions.add(permission)

        author = Author.objects.create(pk=1, name="The Author")
        cls.book = author.books.create(name="The inline Book")
        cls.author_change_url = reverse(
            "admin:admin_inlines_author_change", args=(author.id,)
        )
        # Get the ID of the automatically created intermediate model for the
        # Author-Book m2m.
        author_book_auto_m2m_intermediate = Author.books.through.objects.get(
            author=author, book=cls.book
        )
        cls.author_book_auto_m2m_intermediate_id = author_book_auto_m2m_intermediate.pk

        cls.holder = Holder2.objects.create(dummy=13)
        cls.inner2 = Inner2.objects.create(dummy=42, holder=cls.holder)

    def setUp(self):
        self.holder_change_url = reverse(
            "admin:admin_inlines_holder2_change", args=(self.holder.id,)
        )
        self.client.force_login(self.user)

    def test_inline_add_m2m_noperm(self):
        """

        Checks that inline many-to-many relationships are not displayed 
        on the add author page when the user does not have the necessary permission.

        Verifies that the 'Author-book relationships' section and the 
        related form fields are not present in the page response.

        """
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        # No change permission on books, so no inline
        self.assertNotContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertNotContains(response, "Add another Author-Book Relationship")
        self.assertNotContains(response, 'id="id_Author_books-TOTAL_FORMS"')

    def test_inline_add_fk_noperm(self):
        response = self.client.get(reverse("admin:admin_inlines_holder2_add"))
        # No permissions on Inner2s, so no inline
        self.assertNotContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertNotContains(response, "Add another Inner2")
        self.assertNotContains(response, 'id="id_inner2_set-TOTAL_FORMS"')

    def test_inline_change_m2m_noperm(self):
        response = self.client.get(self.author_change_url)
        # No change permission on books, so no inline
        self.assertNotContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertNotContains(response, "Add another Author-Book Relationship")
        self.assertNotContains(response, 'id="id_Author_books-TOTAL_FORMS"')

    def test_inline_change_fk_noperm(self):
        response = self.client.get(self.holder_change_url)
        # No permissions on Inner2s, so no inline
        self.assertNotContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertNotContains(response, "Add another Inner2")
        self.assertNotContains(response, 'id="id_inner2_set-TOTAL_FORMS"')

    def test_inline_add_m2m_view_only_perm(self):
        """

        Tests the inline add M2M view-only permission functionality in the admin interface.

        This test case ensures that a user with the 'view_book' permission can view the inline M2M formset,
        but does not have permissions to add, change, or delete relationships. The test also verifies
        that the inline formset is rendered correctly with the expected HTML structure and does not
        contain the 'Add another' button.

        The test exercises the permission system by assigning the 'view_book' permission to a user
        and then checking the resulting permissions and HTML content of the inline admin formset.

        """
        permission = Permission.objects.get(
            codename="view_book", content_type=self.book_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        # View-only inlines. (It could be nicer to hide the empty, non-editable
        # inlines on the add page.)
        self.assertIs(
            response.context["inline_admin_formset"].has_view_permission, True
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_add_permission, False
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_change_permission, False
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_delete_permission, False
        )
        self.assertContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" name="Author_books-TOTAL_FORMS" value="0" '
            'id="id_Author_books-TOTAL_FORMS">',
            html=True,
        )
        self.assertNotContains(response, "Add another Author-Book Relationship")

    def test_inline_add_m2m_add_perm(self):
        """

        Tests that when a user does not have inline add permission for a many-to-many relationship,
        the related inline form is not displayed in the admin interface.

        This test case checks that the 'add' permission for a specific model is correctly enforced
        when adding a new object in the admin interface. Specifically, it verifies that the inline
        form for adding relationships between two models is hidden when the user lacks the necessary
        permission. The test confirms this by checking the HTML response for the absence of specific
        elements related to the inline form.

        """
        permission = Permission.objects.get(
            codename="add_book", content_type=self.book_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(reverse("admin:admin_inlines_author_add"))
        # No change permission on Books, so no inline
        self.assertNotContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertNotContains(response, "Add another Author-Book Relationship")
        self.assertNotContains(response, 'id="id_Author_books-TOTAL_FORMS"')

    def test_inline_add_fk_add_perm(self):
        """
        Tests that the 'add' permission is correctly applied to inline fields in the admin interface.

        Verifies that a user with the 'add' permission for a specific model can view the inline field
        and has the option to add new instances of that model. The test checks for the presence of
        the inline field heading, the 'Add another' button, and the correct number of form fields
        in the admin add view. 
        """
        permission = Permission.objects.get(
            codename="add_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(reverse("admin:admin_inlines_holder2_add"))
        # Add permission on inner2s, so we get the inline
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertContains(response, "Add another Inner2")
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" '
            'value="3" name="inner2_set-TOTAL_FORMS">',
            html=True,
        )

    def test_inline_change_m2m_add_perm(self):
        """
        Tests that an inline change form for a many-to-many relationship does not display when the user lacks the add permission for the related model. This ensures that users without the required permission cannot modify or add new relationships from within the inline form.
        """
        permission = Permission.objects.get(
            codename="add_book", content_type=self.book_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.author_change_url)
        # No change permission on books, so no inline
        self.assertNotContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertNotContains(response, "Add another Author-Book Relationship")
        self.assertNotContains(response, 'id="id_Author_books-TOTAL_FORMS"')
        self.assertNotContains(response, 'id="id_Author_books-0-DELETE"')

    def test_inline_change_m2m_view_only_perm(self):
        """
        Tests whether a user with \"view only\" permission on many-to-many relationship can view the inline formset, 
        but does not have permission to add, change or delete related objects on the change view. 

        The test sets up a user with the \"view_book\" permission, then checks the change view response to ensure 
        that the inline formset is displayed and has the correct permissions. It also verifies the presence of 
        expected HTML elements in the response, including the inline formset heading and fields, while ensuring 
        that delete checkboxes are not present.
        """
        permission = Permission.objects.get(
            codename="view_book", content_type=self.book_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.author_change_url)
        # View-only inlines.
        self.assertIs(
            response.context["inline_admin_formset"].has_view_permission, True
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_add_permission, False
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_change_permission, False
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_delete_permission, False
        )
        self.assertContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" name="Author_books-TOTAL_FORMS" value="1" '
            'id="id_Author_books-TOTAL_FORMS">',
            html=True,
        )
        # The field in the inline is read-only.
        self.assertContains(response, "<p>%s</p>" % self.book)
        self.assertNotContains(
            response,
            '<input type="checkbox" name="Author_books-0-DELETE" '
            'id="id_Author_books-0-DELETE">',
            html=True,
        )

    def test_inline_change_m2m_change_perm(self):
        """

        Tests if the inline change formset on the author change page correctly displays 
        and allows modifying many-to-many relationships between authors and books 
        when the user has the 'change_book' permission.

        Verifies that the formset is properly rendered, allowing the user to add, 
        change, and delete relationships, and that the necessary HTML elements are 
        present in the page response.

        """
        permission = Permission.objects.get(
            codename="change_book", content_type=self.book_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.author_change_url)
        # We have change perm on books, so we can add/change/delete inlines
        self.assertIs(
            response.context["inline_admin_formset"].has_view_permission, True
        )
        self.assertIs(response.context["inline_admin_formset"].has_add_permission, True)
        self.assertIs(
            response.context["inline_admin_formset"].has_change_permission, True
        )
        self.assertIs(
            response.context["inline_admin_formset"].has_delete_permission, True
        )
        self.assertContains(
            response,
            (
                '<h2 id="Author_books-heading" class="inline-heading">'
                "Author-book relationships</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Author-book relationship")
        self.assertContains(
            response,
            '<input type="hidden" id="id_Author_books-TOTAL_FORMS" '
            'value="4" name="Author_books-TOTAL_FORMS">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" id="id_Author_books-0-id" value="%i" '
            'name="Author_books-0-id">' % self.author_book_auto_m2m_intermediate_id,
            html=True,
        )
        self.assertContains(response, 'id="id_Author_books-0-DELETE"')

    def test_inline_change_fk_add_perm(self):
        """
        Tests that a user with the 'add_inner2' permission can view the \"Add another Inner2\" link on the holder change page.
        The test also verifies that the inline formset for Inner2 instances is rendered correctly, including the expected form headers and fields.
        It checks that the user can only add new instances and does not have access to existing ones.
        """
        permission = Permission.objects.get(
            codename="add_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.holder_change_url)
        # Add permission on inner2s, so we can add but not modify existing
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertContains(response, "Add another Inner2")
        # 3 extra forms only, not the existing instance form
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" value="3" '
            'name="inner2_set-TOTAL_FORMS">',
            html=True,
        )
        self.assertNotContains(
            response,
            '<input type="hidden" id="id_inner2_set-0-id" value="%i" '
            'name="inner2_set-0-id">' % self.inner2.id,
            html=True,
        )

    def test_inline_change_fk_change_perm(self):
        """

        Tests that the inline change form of the holder object is correctly rendered 
        when the user has the 'change_inner2' permission.

        Verifies the presence of expected HTML elements, including headings, 
        hidden input fields, and form fields, to ensure that the inline form 
        is properly displayed and populated with the correct data.

        """
        permission = Permission.objects.get(
            codename="change_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.holder_change_url)
        # Change permission on inner2s, so we can change existing but not add new
        self.assertContains(
            response,
            '<h2 id="inner2_set-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        # Just the one form for existing instances
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" value="1" '
            'name="inner2_set-TOTAL_FORMS">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-0-id" value="%i" '
            'name="inner2_set-0-id">' % self.inner2.id,
            html=True,
        )
        # max-num 0 means we can't add new ones
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-MAX_NUM_FORMS" value="0" '
            'name="inner2_set-MAX_NUM_FORMS">',
            html=True,
        )
        # TabularInline
        self.assertContains(
            response, '<th class="column-dummy required">Dummy</th>', html=True
        )
        self.assertContains(
            response,
            '<input type="number" name="inner2_set-2-0-dummy" value="%s" '
            'class="vIntegerField" id="id_inner2_set-2-0-dummy">' % self.inner2.dummy,
            html=True,
        )

    def test_inline_change_fk_add_change_perm(self):
        permission = Permission.objects.get(
            codename="add_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="change_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.holder_change_url)
        # Add/change perm, so we can add new and change existing
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        # One form for existing instance and three extra for new
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" value="4" '
            'name="inner2_set-TOTAL_FORMS">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-0-id" value="%i" '
            'name="inner2_set-0-id">' % self.inner2.id,
            html=True,
        )

    def test_inline_change_fk_change_del_perm(self):
        """

        Tests the inline change form for a model with 'change' and 'delete' permissions.

        This test case adds 'change' and 'delete' permissions for a specific object type to the test user,
        then retrieves the change form for the related model instance. It verifies that the form contains the
        expected inline formset elements, including the form heading, total forms input, and specific form
        fields, including a field for deleting an existing instance.

        """
        permission = Permission.objects.get(
            codename="change_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="delete_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.holder_change_url)
        # Change/delete perm on inner2s, so we can change/delete existing
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        # One form for existing instance only, no new
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" value="1" '
            'name="inner2_set-TOTAL_FORMS">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-0-id" value="%i" '
            'name="inner2_set-0-id">' % self.inner2.id,
            html=True,
        )
        self.assertContains(response, 'id="id_inner2_set-0-DELETE"')

    def test_inline_change_fk_all_perms(self):
        """
        Tests that a user with all permissions (add, change, delete) for a specific model (Inner2) can view and modify inline instances of that model on the change page of a related model (holder). Verifies that the page contains the necessary HTML elements for displaying and editing the inline instances, including form headers, form fields, and delete checkboxes.
        """
        permission = Permission.objects.get(
            codename="add_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="change_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        permission = Permission.objects.get(
            codename="delete_inner2", content_type=self.inner_ct
        )
        self.user.user_permissions.add(permission)
        response = self.client.get(self.holder_change_url)
        # All perms on inner2s, so we can add/change/delete
        self.assertContains(
            response,
            '<h2 id="inner2_set-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        self.assertContains(
            response,
            '<h2 id="inner2_set-2-heading" class="inline-heading">Inner2s</h2>',
            html=True,
        )
        # One form for existing instance only, three for new
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-TOTAL_FORMS" value="4" '
            'name="inner2_set-TOTAL_FORMS">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="hidden" id="id_inner2_set-0-id" value="%i" '
            'name="inner2_set-0-id">' % self.inner2.id,
            html=True,
        )
        self.assertContains(response, 'id="id_inner2_set-0-DELETE"')
        # TabularInline
        self.assertContains(
            response, '<th class="column-dummy required">Dummy</th>', html=True
        )
        self.assertContains(
            response,
            '<input type="number" name="inner2_set-2-0-dummy" value="%s" '
            'class="vIntegerField" id="id_inner2_set-2-0-dummy">' % self.inner2.dummy,
            html=True,
        )


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestReadOnlyChangeViewInlinePermissions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            "testing", password="password", is_staff=True
        )
        cls.user.user_permissions.add(
            Permission.objects.get(
                codename="view_poll",
                content_type=ContentType.objects.get_for_model(Poll),
            )
        )
        cls.user.user_permissions.add(
            *Permission.objects.filter(
                codename__endswith="question",
                content_type=ContentType.objects.get_for_model(Question),
            ).values_list("pk", flat=True)
        )

        cls.poll = Poll.objects.create(name="Survey")
        cls.add_url = reverse("admin:admin_inlines_poll_add")
        cls.change_url = reverse("admin:admin_inlines_poll_change", args=(cls.poll.id,))

    def setUp(self):
        self.client.force_login(self.user)

    def test_add_url_not_allowed(self):
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(self.add_url, {})
        self.assertEqual(response.status_code, 403)

    def test_post_to_change_url_not_allowed(self):
        response = self.client.post(self.change_url, {})
        self.assertEqual(response.status_code, 403)

    def test_get_to_change_url_is_allowed(self):
        """
        Tests that a GET request to the change URL returns a successful response, indicating that the URL is accessible and can be used to retrieve or modify data. The test verifies that the server responds with a status code of 200, which represents a standard HTTP success response.
        """
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 200)

    def test_main_model_is_rendered_as_read_only(self):
        """

        Tests that the main model is rendered as read-only when accessed through the change URL.

        Verifies that the model's name is displayed in a read-only div element and that no editable input fields are present in the response.

        """
        response = self.client.get(self.change_url)
        self.assertContains(
            response, '<div class="readonly">%s</div>' % self.poll.name, html=True
        )
        input = (
            '<input type="text" name="name" value="%s" class="vTextField" '
            'maxlength="40" required id="id_name">'
        )
        self.assertNotContains(response, input % self.poll.name, html=True)

    def test_inlines_are_rendered_as_read_only(self):
        question = Question.objects.create(
            text="How will this be rendered?", poll=self.poll
        )
        response = self.client.get(self.change_url)
        self.assertContains(
            response, '<td class="field-text"><p>%s</p></td>' % question.text, html=True
        )
        self.assertNotContains(response, 'id="id_question_set-0-text"')
        self.assertNotContains(response, 'id="id_related_objs-0-DELETE"')

    def test_submit_line_shows_only_close_button(self):
        response = self.client.get(self.change_url)
        self.assertContains(
            response,
            '<a href="/admin/admin_inlines/poll/" class="closelink">Close</a>',
            html=True,
        )
        delete_link = (
            '<a href="/admin/admin_inlines/poll/%s/delete/" class="deletelink">Delete'
            "</a>"
        )
        self.assertNotContains(response, delete_link % self.poll.id, html=True)
        self.assertNotContains(
            response,
            '<input type="submit" value="Save and add another" name="_addanother">',
        )
        self.assertNotContains(
            response,
            '<input type="submit" value="Save and continue editing" name="_continue">',
        )

    def test_inline_delete_buttons_are_not_shown(self):
        Question.objects.create(text="How will this be rendered?", poll=self.poll)
        response = self.client.get(self.change_url)
        self.assertNotContains(
            response,
            '<input type="checkbox" name="question_set-0-DELETE" '
            'id="id_question_set-0-DELETE">',
            html=True,
        )

    def test_extra_inlines_are_not_shown(self):
        """
        Tests that extra inline form fields are not displayed when rendering the change view.

        Verifies that the rendered HTML does not contain unnecessary form fields, 
        specifically those that are not expected to be shown in the initial form presentation.
        """
        response = self.client.get(self.change_url)
        self.assertNotContains(response, 'id="id_question_set-0-text"')


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestVerboseNameInlineForms(TestDataMixin, TestCase):
    factory = RequestFactory()

    def test_verbose_name_inline(self):
        """
        Tests the usage of verbose names in inline model administrators.

        This test case verifies that the verbose names defined for inline models are displayed correctly in the admin interface.
        It checks for the following scenarios:

        * Inline models without verbose names defined
        * Inline models with verbose names defined
        * Inline models with verbose plural names defined
        * Inline models with both verbose and verbose plural names defined

        The test ensures that the correct headings and \"Add another\" links are displayed for each inline model, and that default names are not used when verbose names are defined.
        """
        class NonVerboseProfileInline(TabularInline):
            model = Profile
            verbose_name = "Non-verbose childs"

        class VerboseNameProfileInline(TabularInline):
            model = VerboseNameProfile
            verbose_name = "Childs with verbose name"

        class VerboseNamePluralProfileInline(TabularInline):
            model = VerboseNamePluralProfile
            verbose_name = "Childs with verbose name plural"

        class BothVerboseNameProfileInline(TabularInline):
            model = BothVerboseNameProfile
            verbose_name = "Childs with both verbose names"

        modeladmin = ModelAdmin(ProfileCollection, admin_site)
        modeladmin.inlines = [
            NonVerboseProfileInline,
            VerboseNameProfileInline,
            VerboseNamePluralProfileInline,
            BothVerboseNameProfileInline,
        ]
        obj = ProfileCollection.objects.create()
        url = reverse("admin:admin_inlines_profilecollection_change", args=(obj.pk,))
        request = self.factory.get(url)
        request.user = self.superuser
        response = modeladmin.changeform_view(request)
        self.assertNotContains(response, "Add another Profile")
        # Non-verbose model.
        self.assertContains(
            response,
            (
                '<h2 id="profile_set-heading" class="inline-heading">'
                "Non-verbose childss</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Non-verbose child")
        self.assertNotContains(
            response,
            '<h2 id="profile_set-heading" class="inline-heading">Profiles</h2>',
            html=True,
        )
        # Model with verbose name.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
                "Childs with verbose names</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Childs with verbose name")
        self.assertNotContains(
            response,
            '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
            "Model with verbose name onlys</h2>",
            html=True,
        )
        self.assertNotContains(response, "Add another Model with verbose name only")
        # Model with verbose name plural.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
                "Childs with verbose name plurals</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Childs with verbose name plural")
        self.assertNotContains(
            response,
            '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
            "Model with verbose name plural only</h2>",
            html=True,
        )
        # Model with both verbose names.
        self.assertContains(
            response,
            (
                '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
                "Childs with both verbose namess</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Childs with both verbose names")
        self.assertNotContains(
            response,
            '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
            "Model with both - plural name</h2>",
            html=True,
        )
        self.assertNotContains(response, "Add another Model with both - name")

    def test_verbose_name_plural_inline(self):
        """

        Tests the rendering of verbose name and plural for TabularInline models in the Django admin interface.

        Checks that:
        - The verbose name plural from the model's Meta class is used if it exists.
        - The verbose name from the model's Meta class is used if it exists and verbose name plural does not.
        - A default verbose name is generated if neither verbose name nor verbose name plural is specified.
        - The correct HTML is rendered for each inline model, including headings and \"Add another\" buttons.

        """
        class NonVerboseProfileInline(TabularInline):
            model = Profile
            verbose_name_plural = "Non-verbose childs"

        class VerboseNameProfileInline(TabularInline):
            model = VerboseNameProfile
            verbose_name_plural = "Childs with verbose name"

        class VerboseNamePluralProfileInline(TabularInline):
            model = VerboseNamePluralProfile
            verbose_name_plural = "Childs with verbose name plural"

        class BothVerboseNameProfileInline(TabularInline):
            model = BothVerboseNameProfile
            verbose_name_plural = "Childs with both verbose names"

        modeladmin = ModelAdmin(ProfileCollection, admin_site)
        modeladmin.inlines = [
            NonVerboseProfileInline,
            VerboseNameProfileInline,
            VerboseNamePluralProfileInline,
            BothVerboseNameProfileInline,
        ]
        obj = ProfileCollection.objects.create()
        url = reverse("admin:admin_inlines_profilecollection_change", args=(obj.pk,))
        request = self.factory.get(url)
        request.user = self.superuser
        response = modeladmin.changeform_view(request)
        # Non-verbose model.
        self.assertContains(
            response,
            (
                '<h2 id="profile_set-heading" class="inline-heading">'
                "Non-verbose childs</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Profile")
        self.assertNotContains(
            response,
            '<h2 id="profile_set-heading" class="inline-heading">Profiles</h2>',
            html=True,
        )
        # Model with verbose name.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
                "Childs with verbose name</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Model with verbose name only")
        self.assertNotContains(
            response,
            '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
            "Model with verbose name onlys</h2>",
            html=True,
        )
        # Model with verbose name plural.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
                "Childs with verbose name plural</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Profile")
        self.assertNotContains(
            response,
            '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
            "Model with verbose name plural only</h2>",
            html=True,
        )
        # Model with both verbose names.
        self.assertContains(
            response,
            (
                '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
                "Childs with both verbose names</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Model with both - name")
        self.assertNotContains(
            response,
            '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
            "Model with both - plural name</h2>",
            html=True,
        )

    def test_both_verbose_names_inline(self):
        """

        Tests the display of inline model forms in the admin interface with different verbose name configurations.

        This test case covers four scenarios: 
        - Non-verbose names for inline models 
        - Verbose names for inline models
        - Verbose plural names for inline models
        - Both verbose and plural names for inline models

        It verifies that the display of inline model forms is correct in each case, including the headings and the \"Add another\" links.

        """
        class NonVerboseProfileInline(TabularInline):
            model = Profile
            verbose_name = "Non-verbose childs - name"
            verbose_name_plural = "Non-verbose childs - plural name"

        class VerboseNameProfileInline(TabularInline):
            model = VerboseNameProfile
            verbose_name = "Childs with verbose name - name"
            verbose_name_plural = "Childs with verbose name - plural name"

        class VerboseNamePluralProfileInline(TabularInline):
            model = VerboseNamePluralProfile
            verbose_name = "Childs with verbose name plural - name"
            verbose_name_plural = "Childs with verbose name plural - plural name"

        class BothVerboseNameProfileInline(TabularInline):
            model = BothVerboseNameProfile
            verbose_name = "Childs with both - name"
            verbose_name_plural = "Childs with both - plural name"

        modeladmin = ModelAdmin(ProfileCollection, admin_site)
        modeladmin.inlines = [
            NonVerboseProfileInline,
            VerboseNameProfileInline,
            VerboseNamePluralProfileInline,
            BothVerboseNameProfileInline,
        ]
        obj = ProfileCollection.objects.create()
        url = reverse("admin:admin_inlines_profilecollection_change", args=(obj.pk,))
        request = self.factory.get(url)
        request.user = self.superuser
        response = modeladmin.changeform_view(request)
        self.assertNotContains(response, "Add another Profile")
        # Non-verbose model.
        self.assertContains(
            response,
            (
                '<h2 id="profile_set-heading" class="inline-heading">'
                "Non-verbose childs - plural name</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Non-verbose childs - name")
        self.assertNotContains(
            response,
            '<h2 id="profile_set-heading" class="inline-heading">Profiles</h2>',
            html=True,
        )
        # Model with verbose name.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
                "Childs with verbose name - plural name</h2>"
            ),
            html=True,
        )
        self.assertContains(response, "Add another Childs with verbose name - name")
        self.assertNotContains(
            response,
            '<h2 id="verbosenameprofile_set-heading" class="inline-heading">'
            "Model with verbose name onlys</h2>",
            html=True,
        )
        # Model with verbose name plural.
        self.assertContains(
            response,
            (
                '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
                "Childs with verbose name plural - plural name</h2>"
            ),
            html=True,
        )
        self.assertContains(
            response,
            "Add another Childs with verbose name plural - name",
        )
        self.assertNotContains(
            response,
            '<h2 id="verbosenamepluralprofile_set-heading" class="inline-heading">'
            "Model with verbose name plural only</h2>",
            html=True,
        )
        # Model with both verbose names.
        self.assertContains(
            response,
            '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
            "Childs with both - plural name</h2>",
            html=True,
        )
        self.assertContains(response, "Add another Childs with both - name")
        self.assertNotContains(
            response,
            '<h2 id="bothverbosenameprofile_set-heading" class="inline-heading">'
            "Model with both - plural name</h2>",
            html=True,
        )
        self.assertNotContains(response, "Add another Model with both - name")


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class TestInlineWithFieldsets(TestDataMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.superuser)

    def test_inline_headings(self):
        response = self.client.get(reverse("admin:admin_inlines_photographer_add"))
        # Page main title.
        self.assertContains(response, "<h1>Add photographer</h1>", html=True)

        # Headings for the toplevel fieldsets. The first one has no name.
        self.assertContains(response, '<fieldset class="module aligned ">')
        # The second and third have the same "Advanced options" name, but the
        # second one has the "collapse" class.
        for x, classes in ((1, ""), (2, "collapse")):
            heading_id = f"fieldset-0-advanced-options-{x}-heading"
            with self.subTest(heading_id=heading_id):
                self.assertContains(
                    response,
                    f'<fieldset class="module aligned {classes}" '
                    f'aria-labelledby="{heading_id}">',
                )
                self.assertContains(
                    response,
                    f'<h2 id="{heading_id}" class="fieldset-heading">'
                    "Advanced options</h2>",
                )
                self.assertContains(response, f'id="{heading_id}"', count=1)

        # Headings and subheadings for all the inlines.
        for inline_admin_formset in response.context["inline_admin_formsets"]:
            prefix = inline_admin_formset.formset.prefix
            heading_id = f"{prefix}-heading"
            formset_heading = (
                f'<h2 id="{heading_id}" class="inline-heading">Photos</h2>'
            )
            self.assertContains(response, formset_heading, html=True)
            self.assertContains(response, f'id="{heading_id}"', count=1)

            # If this is a TabularInline, do not make further asserts since
            # fieldsets are not shown as such in this table layout.
            if "tabular" in inline_admin_formset.opts.template:
                continue

            if "collapse" in inline_admin_formset.classes:
                formset_heading = f"<summary>{formset_heading}</summary>"
                self.assertContains(response, formset_heading, html=True, count=1)

            # Headings for every formset (the amount depends on `extra`).
            for y, inline_admin_form in enumerate(inline_admin_formset):
                y_plus_one = y + 1
                form_heading = (
                    f'<h3><b>Photo:</b> <span class="inline_label">#{y_plus_one}</span>'
                    "</h3>"
                )
                self.assertContains(response, form_heading, html=True)

                # Every fieldset defined for an inline's form.
                for z, fieldset in enumerate(inline_admin_form):
                    if fieldset.name:
                        heading_id = f"{prefix}-{y}-details-{z}-heading"
                        self.assertContains(
                            response,
                            f'<fieldset class="module aligned {fieldset.classes}" '
                            f'aria-labelledby="{heading_id}">',
                        )
                        fieldset_heading = (
                            f'<h4 id="{heading_id}" class="fieldset-heading">'
                            f"Details</h4>"
                        )
                        self.assertContains(response, fieldset_heading)
                        if "collapse" in fieldset.classes:
                            self.assertContains(
                                response,
                                f"<summary>{fieldset_heading}</summary>",
                                html=True,
                            )
                        self.assertContains(response, f'id="{heading_id}"', count=1)

                    else:
                        fieldset_html = (
                            f'<fieldset class="module aligned {fieldset.classes}">'
                        )
                        self.assertContains(response, fieldset_html)


@override_settings(ROOT_URLCONF="admin_inlines.urls")
class SeleniumTests(AdminSeleniumTestCase):
    available_apps = ["admin_inlines"] + AdminSeleniumTestCase.available_apps

    def setUp(self):
        User.objects.create_superuser(
            username="super", password="secret", email="super@example.com"
        )

    @screenshot_cases(["desktop_size", "mobile_size", "dark", "high_contrast"])
    def test_add_stackeds(self):
        """
        The "Add another XXX" link correctly adds items to the stacked formset.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder4_add")
        )

        inline_id = "#inner4stacked_set-group"
        rows_selector = "%s .dynamic-inner4stacked_set" % inline_id

        self.assertCountSeleniumElements(rows_selector, 3)
        add_button = self.selenium.find_element(
            By.LINK_TEXT, "Add another Inner4 stacked"
        )
        add_button.click()
        self.assertCountSeleniumElements(rows_selector, 4)
        self.take_screenshot("added")

    def test_delete_stackeds(self):
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder4_add")
        )

        inline_id = "#inner4stacked_set-group"
        rows_selector = "%s .dynamic-inner4stacked_set" % inline_id

        self.assertCountSeleniumElements(rows_selector, 3)

        add_button = self.selenium.find_element(
            By.LINK_TEXT, "Add another Inner4 stacked"
        )
        add_button.click()
        add_button.click()

        self.assertCountSeleniumElements(rows_selector, 5)
        for delete_link in self.selenium.find_elements(
            By.CSS_SELECTOR, "%s .inline-deletelink" % inline_id
        ):
            delete_link.click()
        with self.disable_implicit_wait():
            self.assertCountSeleniumElements(rows_selector, 0)

    def test_delete_invalid_stacked_inlines(self):
        """

        Tests the deletion of an invalid stacked inline in the admin interface.

        This test covers the following steps:
        - Logs in as an admin user
        - Navigates to the add page for an admin inlines holder
        - Adds new inlines until there are duplicates
        - Submits the form and verifies that an error is displayed
        - Deletes the duplicate inline and verifies that the error is resolved
        - Submits the form again and verifies that the changes are saved

        The test ensures that the admin interface correctly handles the deletion of invalid stacked inlines and that the form submission works as expected.

        """
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder4_add")
        )

        inline_id = "#inner4stacked_set-group"
        rows_selector = "%s .dynamic-inner4stacked_set" % inline_id

        self.assertCountSeleniumElements(rows_selector, 3)

        add_button = self.selenium.find_element(
            By.LINK_TEXT,
            "Add another Inner4 stacked",
        )
        add_button.click()
        add_button.click()
        self.assertCountSeleniumElements("#id_inner4stacked_set-4-dummy", 1)

        # Enter some data and click 'Save'.
        self.selenium.find_element(By.NAME, "dummy").send_keys("1")
        self.selenium.find_element(By.NAME, "inner4stacked_set-0-dummy").send_keys(
            "100"
        )
        self.selenium.find_element(By.NAME, "inner4stacked_set-1-dummy").send_keys(
            "101"
        )
        self.selenium.find_element(By.NAME, "inner4stacked_set-2-dummy").send_keys(
            "222"
        )
        self.selenium.find_element(By.NAME, "inner4stacked_set-3-dummy").send_keys(
            "103"
        )
        self.selenium.find_element(By.NAME, "inner4stacked_set-4-dummy").send_keys(
            "222"
        )
        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()

        # Sanity check.
        self.assertCountSeleniumElements(rows_selector, 5)
        errorlist = self.selenium.find_element(
            By.CSS_SELECTOR,
            "%s .dynamic-inner4stacked_set .errorlist li" % inline_id,
        )
        self.assertEqual("Please correct the duplicate values below.", errorlist.text)
        delete_link = self.selenium.find_element(
            By.CSS_SELECTOR, "#inner4stacked_set-4 .inline-deletelink"
        )
        delete_link.click()
        self.assertCountSeleniumElements(rows_selector, 4)
        with self.disable_implicit_wait(), self.assertRaises(NoSuchElementException):
            self.selenium.find_element(
                By.CSS_SELECTOR,
                "%s .dynamic-inner4stacked_set .errorlist li" % inline_id,
            )

        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()

        # The objects have been created in the database.
        self.assertEqual(Inner4Stacked.objects.count(), 4)

    def test_delete_invalid_tabular_inlines(self):
        """
        Tests the deletion of an invalid tabular inline form in the admin interface.

            This test case covers the scenario where a user creates a new object with 
            duplicate field values in the inline form, and then attempts to delete 
            one of the invalid inline entries. The test verifies that after deletion, 
            the duplicate error message is no longer displayed, and the object is saved 
            successfully with the remaining valid inline entries. 

            The test performs the following steps:

            * Logs in to the admin interface
            * Navigates to the page for creating a new object
            * Adds new inline entries until a duplicate value error occurs
            * Deletes the invalid inline entry
            * Verifies that the duplicate error message is removed
            * Saves the object and checks that the remaining inline entries are preserved
            * Verifies the count of objects in the database after the test.
        """
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder4_add")
        )

        inline_id = "#inner4tabular_set-group"
        rows_selector = "%s .dynamic-inner4tabular_set" % inline_id

        self.assertCountSeleniumElements(rows_selector, 3)

        add_button = self.selenium.find_element(
            By.LINK_TEXT, "Add another Inner4 tabular"
        )
        add_button.click()
        add_button.click()
        self.assertCountSeleniumElements("#id_inner4tabular_set-4-dummy", 1)

        # Enter some data and click 'Save'.
        self.selenium.find_element(By.NAME, "dummy").send_keys("1")
        self.selenium.find_element(By.NAME, "inner4tabular_set-0-dummy").send_keys(
            "100"
        )
        self.selenium.find_element(By.NAME, "inner4tabular_set-1-dummy").send_keys(
            "101"
        )
        self.selenium.find_element(By.NAME, "inner4tabular_set-2-dummy").send_keys(
            "222"
        )
        self.selenium.find_element(By.NAME, "inner4tabular_set-3-dummy").send_keys(
            "103"
        )
        self.selenium.find_element(By.NAME, "inner4tabular_set-4-dummy").send_keys(
            "222"
        )
        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()

        # Sanity Check.
        self.assertCountSeleniumElements(rows_selector, 5)

        # Non-field errorlist is in its own <tr> just before
        # tr#inner4tabular_set-3:
        errorlist = self.selenium.find_element(
            By.CSS_SELECTOR,
            "%s #inner4tabular_set-3 + .row-form-errors .errorlist li" % inline_id,
        )
        self.assertEqual("Please correct the duplicate values below.", errorlist.text)
        delete_link = self.selenium.find_element(
            By.CSS_SELECTOR, "#inner4tabular_set-4 .inline-deletelink"
        )
        delete_link.click()

        self.assertCountSeleniumElements(rows_selector, 4)
        with self.disable_implicit_wait(), self.assertRaises(NoSuchElementException):
            self.selenium.find_element(
                By.CSS_SELECTOR,
                "%s .dynamic-inner4tabular_set .errorlist li" % inline_id,
            )

        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()

        # The objects have been created in the database.
        self.assertEqual(Inner4Tabular.objects.count(), 4)

    def test_add_inlines(self):
        """
        The "Add another XXX" link correctly adds items to the inline form.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_profilecollection_add")
        )

        # There's only one inline to start with and it has the correct ID.
        self.assertCountSeleniumElements(".dynamic-profile_set", 1)
        self.assertEqual(
            self.selenium.find_elements(By.CSS_SELECTOR, ".dynamic-profile_set")[
                0
            ].get_attribute("id"),
            "profile_set-0",
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-0 input[name=profile_set-0-first_name]", 1
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-0 input[name=profile_set-0-last_name]", 1
        )

        # Add an inline
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()

        # The inline has been added, it has the right id, and it contains the
        # correct fields.
        self.assertCountSeleniumElements(".dynamic-profile_set", 2)
        self.assertEqual(
            self.selenium.find_elements(By.CSS_SELECTOR, ".dynamic-profile_set")[
                1
            ].get_attribute("id"),
            "profile_set-1",
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-1 input[name=profile_set-1-first_name]", 1
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-1 input[name=profile_set-1-last_name]", 1
        )
        # Let's add another one to be sure
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()
        self.assertCountSeleniumElements(".dynamic-profile_set", 3)
        self.assertEqual(
            self.selenium.find_elements(By.CSS_SELECTOR, ".dynamic-profile_set")[
                2
            ].get_attribute("id"),
            "profile_set-2",
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-2 input[name=profile_set-2-first_name]", 1
        )
        self.assertCountSeleniumElements(
            ".dynamic-profile_set#profile_set-2 input[name=profile_set-2-last_name]", 1
        )

        # Enter some data and click 'Save'
        self.selenium.find_element(By.NAME, "profile_set-0-first_name").send_keys(
            "0 first name 1"
        )
        self.selenium.find_element(By.NAME, "profile_set-0-last_name").send_keys(
            "0 last name 2"
        )
        self.selenium.find_element(By.NAME, "profile_set-1-first_name").send_keys(
            "1 first name 1"
        )
        self.selenium.find_element(By.NAME, "profile_set-1-last_name").send_keys(
            "1 last name 2"
        )
        self.selenium.find_element(By.NAME, "profile_set-2-first_name").send_keys(
            "2 first name 1"
        )
        self.selenium.find_element(By.NAME, "profile_set-2-last_name").send_keys(
            "2 last name 2"
        )

        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()

        # The objects have been created in the database
        self.assertEqual(ProfileCollection.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 3)

    def test_add_inline_link_absent_for_view_only_parent_model(self):
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.common.by import By

        user = User.objects.create_user("testing", password="password", is_staff=True)
        user.user_permissions.add(
            Permission.objects.get(
                codename="view_poll",
                content_type=ContentType.objects.get_for_model(Poll),
            )
        )
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__endswith="question",
                content_type=ContentType.objects.get_for_model(Question),
            ).values_list("pk", flat=True)
        )
        self.admin_login(username="testing", password="password")
        poll = Poll.objects.create(name="Survey")
        change_url = reverse("admin:admin_inlines_poll_change", args=(poll.id,))
        self.selenium.get(self.live_server_url + change_url)
        with self.disable_implicit_wait():
            with self.assertRaises(NoSuchElementException):
                self.selenium.find_element(By.LINK_TEXT, "Add another Question")

    def test_delete_inlines(self):
        """

        Test the deletion of inline items in the admin interface.

        This test checks if the deletion of inline items, specifically profiles,
        functions correctly. It first logs in to the admin interface, navigates
        to the profile collection add page, and adds multiple profiles. It then
        verifies that the correct number of profiles are displayed. After that,
        it deletes some of the profiles and checks again that the correct number
        of profiles are displayed.

        The test covers the following scenarios:
        - Adding multiple inline items
        - Verifying the correct number of items are displayed
        - Deleting inline items
        - Verifying the correct number of items are displayed after deletion

        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_profilecollection_add")
        )

        # Add a few inlines
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()
        self.selenium.find_element(By.LINK_TEXT, "Add another Profile").click()
        self.assertCountSeleniumElements(
            "#profile_set-group table tr.dynamic-profile_set", 5
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-0", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-1", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-2", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-3", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-4", 1
        )
        # Click on a few delete buttons
        self.selenium.find_element(
            By.CSS_SELECTOR,
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-1 "
            "td.delete a",
        ).click()
        self.selenium.find_element(
            By.CSS_SELECTOR,
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-2 "
            "td.delete a",
        ).click()
        # The rows are gone and the IDs have been re-sequenced
        self.assertCountSeleniumElements(
            "#profile_set-group table tr.dynamic-profile_set", 3
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-0", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-1", 1
        )
        self.assertCountSeleniumElements(
            "form#profilecollection_form tr.dynamic-profile_set#profile_set-2", 1
        )

    @screenshot_cases(["desktop_size", "mobile_size", "rtl", "dark", "high_contrast"])
    def test_collapsed_inlines(self):
        """

        Test that inlines are properly collapsed in the admin interface.

        This test case verifies the functionality of collapsible inlines in the admin interface.
        It checks that the inlines are initially collapsed, can be expanded by clicking on the summary element,
        and can be collapsed again by clicking on the same summary element.
        The test is performed under various conditions, including different screen sizes and themes,
        to ensure that the functionality works as expected in different environments.

        The test covers the following scenarios:
        - Loading the admin interface with collapsed inlines
        - Expanding and collapsing inlines by clicking on the summary element
        - Verifying that the inlines are properly displayed after expansion and collapse

        Screenshots are taken at different stages of the test to facilitate visual verification of the results.

        """
        from selenium.webdriver.common.by import By

        # Collapsed inlines use details and summary elements.
        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_author_add")
        )
        # One field is in a stacked inline, other in a tabular one.
        test_fields = [
            "#id_nonautopkbook_set-0-title",
            "#id_nonautopkbook_set-2-0-title",
        ]
        summaries = self.selenium.find_elements(By.TAG_NAME, "summary")
        self.assertEqual(len(summaries), 3)
        self.take_screenshot("loaded")
        for show_index, field_name in enumerate(test_fields, 0):
            self.wait_until_invisible(field_name)
            summaries[show_index].click()
            self.wait_until_visible(field_name)
        self.take_screenshot("expanded")
        for hide_index, field_name in enumerate(test_fields, 0):
            self.wait_until_visible(field_name)
            summaries[hide_index].click()
            self.wait_until_invisible(field_name)
        self.take_screenshot("collapsed")

    @screenshot_cases(["desktop_size", "mobile_size", "rtl", "dark", "high_contrast"])
    def test_added_stacked_inline_with_collapsed_fields(self):
        """
        Tests the functionality of stacked inline fields in the admin interface.

        This test case covers the addition of new inline items, expansion and collapse of 
        those items, and ensures that the fields are displayed correctly in different states.

        The test is run with various screenshot cases to verify cross-browser and 
        cross-environment compatibility, including desktop and mobile screen sizes, 
        right-to-left language support, dark mode, and high contrast mode.

        It checks the initial loading of the page, the expansion of inline fields, and 
        their subsequent collapse, taking screenshots at each stage to document the 
        test results.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_teacher_add")
        )
        add_text = gettext("Add another %(verbose_name)s") % {"verbose_name": "Child"}
        self.selenium.find_element(By.LINK_TEXT, add_text).click()
        test_fields = ["#id_child_set-0-name", "#id_child_set-1-name"]
        summaries = self.selenium.find_elements(By.TAG_NAME, "summary")
        self.assertEqual(len(summaries), 3)
        self.take_screenshot("loaded")
        for show_index, field_name in enumerate(test_fields, 0):
            self.wait_until_invisible(field_name)
            summaries[show_index].click()
            self.wait_until_visible(field_name)
        self.take_screenshot("expanded")
        for hide_index, field_name in enumerate(test_fields, 0):
            self.wait_until_visible(field_name)
            summaries[hide_index].click()
            self.wait_until_invisible(field_name)
        self.take_screenshot("collapsed")

    def assertBorder(self, element, border):
        """
        Asserts the border of an element matches the given border properties.

        This function checks that the width, style, and color of an element's border
        match the provided values. It verifies that all sides (top, right, bottom, left)
        of the border have the same width and style, and that the color is a valid
        hexadecimal color code.

        Parameters
        ----------
        element : object
            The element to check the border of
        border : str
            A string containing the border properties, in the format \"width style color\"

        Example
        -------
        A valid border string would be \"1px solid #ffffff\". The function will then
        check that all sides of the element have a border width of 1px, a solid style,
        and a white color (#ffffff).
        """
        width, style, color = border.split(" ")
        border_properties = [
            "border-bottom-%s",
            "border-left-%s",
            "border-right-%s",
            "border-top-%s",
        ]
        for prop in border_properties:
            self.assertEqual(element.value_of_css_property(prop % "width"), width)
        for prop in border_properties:
            self.assertEqual(element.value_of_css_property(prop % "style"), style)
        # Convert hex color to rgb.
        self.assertRegex(color, "#[0-9a-f]{6}")
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:], 16)
        # The value may be expressed as either rgb() or rgba() depending on the
        # browser.
        colors = [
            "rgb(%d, %d, %d)" % (r, g, b),
            "rgba(%d, %d, %d, 1)" % (r, g, b),
        ]
        for prop in border_properties:
            self.assertIn(element.value_of_css_property(prop % "color"), colors)

    def test_inline_formset_error_input_border(self):
        """

        Tests the rendering of error borders around form fields in the admin interface
        when an inline formset contains invalid input.

        Verifies that fields with invalid input display a red border and that the
        correct fields are highlighted with errors in both stacked and tabular inline
        formsets.

        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder5_add")
        )
        self.wait_until_visible("#id_dummy")
        self.selenium.find_element(By.ID, "id_dummy").send_keys(1)
        fields = ["id_inner5stacked_set-0-dummy", "id_inner5tabular_set-0-dummy"]
        summaries = self.selenium.find_elements(By.TAG_NAME, "summary")
        for show_index, field_name in enumerate(fields):
            summaries[show_index].click()
            self.wait_until_visible("#" + field_name)
            self.selenium.find_element(By.ID, field_name).send_keys(1)

        # Before save all inputs have default border
        for inline in ("stacked", "tabular"):
            for field_name in ("name", "select", "text"):
                element_id = "id_inner5%s_set-0-%s" % (inline, field_name)
                self.assertBorder(
                    self.selenium.find_element(By.ID, element_id),
                    "1px solid #cccccc",
                )
        self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        # Test the red border around inputs by css selectors
        stacked_selectors = [".errors input", ".errors select", ".errors textarea"]
        for selector in stacked_selectors:
            self.assertBorder(
                self.selenium.find_element(By.CSS_SELECTOR, selector),
                "1px solid #ba2121",
            )
        tabular_selectors = [
            "td ul.errorlist + input",
            "td ul.errorlist + select",
            "td ul.errorlist + textarea",
        ]
        for selector in tabular_selectors:
            self.assertBorder(
                self.selenium.find_element(By.CSS_SELECTOR, selector),
                "1px solid #ba2121",
            )

    def test_inline_formset_error(self):
        """
        Tests that inlines are properly folded and unfolded with error details in the admin interface.

        The test logs into the admin interface, navigates to the admin_inlines_holder5_add page, 
        submits the form without filling in the required fields, and checks that the stacked and 
        tabular inline sections are initially closed. It then opens and closes each section, 
        filling in the required fields, and finally submits the form again to verify that 
        the inline sections remain open with the field summaries visible.

        This test case covers the functionality of the admin interface when dealing with 
        formset errors in inline fields, ensuring that the interface behaves as expected 
        when the user interacts with the form and the inline sections.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_holder5_add")
        )
        stacked_inline_details_selector = (
            "div#inner5stacked_set-group fieldset.module.collapse details"
        )
        tabular_inline_details_selector = (
            "div#inner5tabular_set-group fieldset.module.collapse details"
        )
        # Inlines without errors, both inlines collapsed
        self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        self.assertCountSeleniumElements(
            stacked_inline_details_selector + ":not([open])", 1
        )
        self.assertCountSeleniumElements(
            tabular_inline_details_selector + ":not([open])", 1
        )
        summaries = self.selenium.find_elements(By.TAG_NAME, "summary")
        self.assertEqual(len(summaries), 2)

        # Inlines with errors, both inlines expanded
        test_fields = ["#id_inner5stacked_set-0-dummy", "#id_inner5tabular_set-0-dummy"]
        for show_index, field_name in enumerate(test_fields):
            summaries[show_index].click()
            self.wait_until_visible(field_name)
            self.selenium.find_element(By.ID, field_name[1:]).send_keys(1)
        for hide_index, field_name in enumerate(test_fields):
            summary = summaries[hide_index]
            self.selenium.execute_script(
                "window.scrollTo(0, %s);" % summary.location["y"]
            )
            summary.click()
            self.wait_until_invisible(field_name)
        with self.wait_page_loaded():
            self.selenium.find_element(By.XPATH, '//input[@value="Save"]').click()
        self.assertCountSeleniumElements(stacked_inline_details_selector, 0)
        self.assertCountSeleniumElements(tabular_inline_details_selector, 0)

    def test_inlines_verbose_name(self):
        """
        The item added by the "Add another XXX" link must use the correct
        verbose_name in the inline form.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        # Hide sidebar.
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_course_add")
        )
        toggle_button = self.selenium.find_element(
            By.CSS_SELECTOR, "#toggle-nav-sidebar"
        )
        toggle_button.click()
        # Each combination of horizontal/vertical filter with stacked/tabular
        # inlines.
        tests = [
            "admin:admin_inlines_course_add",
            "admin:admin_inlines_courseproxy_add",
            "admin:admin_inlines_courseproxy1_add",
            "admin:admin_inlines_courseproxy2_add",
        ]
        css_selector = ".dynamic-class_set#class_set-%s h2"

        for url_name in tests:
            with self.subTest(url=url_name):
                self.selenium.get(self.live_server_url + reverse(url_name))
                # First inline shows the verbose_name.
                available, chosen = self.selenium.find_elements(
                    By.CSS_SELECTOR, css_selector % 0
                )
                self.assertEqual(available.text, "AVAILABLE ATTENDANT")
                self.assertEqual(chosen.text, "CHOSEN ATTENDANT")
                # Added inline should also have the correct verbose_name.
                self.selenium.find_element(By.LINK_TEXT, "Add another Class").click()
                available, chosen = self.selenium.find_elements(
                    By.CSS_SELECTOR, css_selector % 1
                )
                self.assertEqual(available.text, "AVAILABLE ATTENDANT")
                self.assertEqual(chosen.text, "CHOSEN ATTENDANT")
                # Third inline should also have the correct verbose_name.
                self.selenium.find_element(By.LINK_TEXT, "Add another Class").click()
                available, chosen = self.selenium.find_elements(
                    By.CSS_SELECTOR, css_selector % 2
                )
                self.assertEqual(available.text, "AVAILABLE ATTENDANT")
                self.assertEqual(chosen.text, "CHOSEN ATTENDANT")

    def test_tabular_inline_layout(self):
        """
        Tests the layout of tabular inline rows in the admin interface.

        Verifies that the tabular inline row is correctly displayed with the expected 
        columns and that no extraneous content is present. The test checks for the 
        presence of standard columns such as image, title, and dates, and also ensures 
        that no unnecessary details or group names are shown. Additionally, it confirms 
        that no collapsible content is present in the tabular inline row.

        This test is intended to ensure a clean and user-friendly layout for 
        administrators managing inline objects in the tabular view.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_inlines_photographer_add")
        )
        tabular_inline = self.selenium.find_element(
            By.CSS_SELECTOR, "[data-inline-type='tabular']"
        )
        headers = tabular_inline.find_elements(By.TAG_NAME, "th")
        self.assertEqual(
            [h.get_attribute("innerText") for h in headers],
            [
                "",
                "IMAGE",
                "TITLE",
                "DESCRIPTION",
                "CREATION DATE",
                "UPDATE DATE",
                "UPDATED BY",
                "DELETE?",
            ],
        )
        # There are no fieldset section names rendered.
        self.assertNotIn("Details", tabular_inline.text)
        # There are no fieldset section descriptions rendered.
        self.assertNotIn("First group", tabular_inline.text)
        self.assertNotIn("Second group", tabular_inline.text)
        self.assertNotIn("Third group", tabular_inline.text)
        # There are no fieldset classes applied.
        self.assertEqual(
            tabular_inline.find_elements(By.CSS_SELECTOR, ".collapse"),
            [],
        )
