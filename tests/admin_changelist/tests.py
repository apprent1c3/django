import datetime
from unittest import mock

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.templatetags.admin_list import pagination
from django.contrib.admin.tests import AdminSeleniumTestCase
from django.contrib.admin.views.main import (
    ALL_VAR,
    IS_FACETS_VAR,
    IS_POPUP_VAR,
    ORDER_VAR,
    PAGE_VAR,
    SEARCH_VAR,
    TO_FIELD_VAR,
)
from django.contrib.auth.models import User
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import DatabaseError, connection, models
from django.db.models import F, Field, IntegerField
from django.db.models.functions import Upper
from django.db.models.lookups import Contains, Exact
from django.template import Context, Template, TemplateSyntaxError
from django.test import TestCase, override_settings, skipUnlessDBFeature
from django.test.client import RequestFactory
from django.test.utils import CaptureQueriesContext, isolate_apps, register_lookup
from django.urls import reverse
from django.utils import formats

from .admin import (
    BandAdmin,
    ChildAdmin,
    ChordsBandAdmin,
    ConcertAdmin,
    CustomPaginationAdmin,
    CustomPaginator,
    DynamicListDisplayChildAdmin,
    DynamicListDisplayLinksChildAdmin,
    DynamicListFilterChildAdmin,
    DynamicSearchFieldsChildAdmin,
    EmptyValueChildAdmin,
    EventAdmin,
    FilteredChildAdmin,
    GrandChildAdmin,
    GroupAdmin,
    InvitationAdmin,
    NoListDisplayLinksParentAdmin,
    ParentAdmin,
    ParentAdminTwoSearchFields,
    QuartetAdmin,
    SwallowAdmin,
)
from .admin import site as custom_site
from .models import (
    Band,
    CharPK,
    Child,
    ChordsBand,
    ChordsMusician,
    Concert,
    CustomIdUser,
    Event,
    Genre,
    GrandChild,
    Group,
    Invitation,
    Membership,
    Musician,
    OrderedObject,
    Parent,
    Quartet,
    Swallow,
    SwallowOneToOne,
    UnorderedObject,
)


def build_tbody_html(obj, href, field_name, extra_fields):
    return (
        "<tbody><tr>"
        '<td class="action-checkbox">'
        '<input type="checkbox" name="_selected_action" value="{}" '
        'class="action-select" aria-label="Select this object for an action - {}"></td>'
        '<th class="field-name"><a href="{}">{}</a></th>'
        "{}</tr></tbody>"
    ).format(obj.pk, str(obj), href, field_name, extra_fields)


@override_settings(ROOT_URLCONF="admin_changelist.urls")
class ChangeListTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super", email="a@b.com", password="xxx"
        )

    def _create_superuser(self, username):
        return User.objects.create_superuser(
            username=username, email="a@b.com", password="xxx"
        )

    def _mocked_authenticated_request(self, url, user):
        """
        Creates a mocked authenticated HTTP request instance for testing purposes.

        This function generates a request object for the specified URL and associates it with the provided user, simulating an authenticated request.

        :param url: The URL of the request
        :param user: The user to be associated with the request
        :return: A request object with the user set
        """
        request = self.factory.get(url)
        request.user = user
        return request

    def test_repr(self):
        """

        Tests the string representation of the ChangeList instance returned by the ChildAdmin model.

        This test case verifies that the repr method of the ChangeList object returns the expected string format,
        including the model and model admin information. It ensures that the ChangeList object can be properly
        represented as a string for debugging and logging purposes.

        """
        m = ChildAdmin(Child, custom_site)
        request = self.factory.get("/child/")
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(repr(cl), "<ChangeList: model=Child model_admin=ChildAdmin>")

    def test_specified_ordering_by_f_expression(self):
        """
        Tests the specified ordering by F expression in the Django admin changelist view.

        This test case verifies that the 'ordering' parameter in the ModelAdmin class 
        is correctly applied when using F expressions for ordering fields. The ordering 
        is specified as a tuple of F expressions, including 'desc' and 'asc' ordering 
        with and without nulls_last parameter. The test checks if the changelist view 
        correctly applies the specified ordering when the view is rendered. 

        The test uses a custom ModelAdmin class 'OrderedByFBandAdmin' to test the 
        ordering of the 'Band' model in the admin interface.

        Args: None

        Returns: None

        Raises: AssertionError if the ordering is not correctly applied.

        """
        class OrderedByFBandAdmin(admin.ModelAdmin):
            list_display = ["name", "genres", "nr_of_members"]
            ordering = (
                F("nr_of_members").desc(nulls_last=True),
                Upper(F("name")).asc(),
                F("genres").asc(),
            )

        m = OrderedByFBandAdmin(Band, custom_site)
        request = self.factory.get("/band/")
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.get_ordering_field_columns(), {3: "desc", 2: "asc"})

    def test_specified_ordering_by_f_expression_without_asc_desc(self):
        """

        Tests the specified ordering by F-expression in the model admin without explicit 'asc' or 'desc' parameters.

        The ordering is defined by a combination of F-expressions and model fields. This test case verifies that the model admin 
        applies the default ascending order to the specified fields when 'asc' or 'desc' is not explicitly provided in the ordering.

        It checks if the resulting ordering field columns match the expected ascending order for all fields in the specified ordering.

        """
        class OrderedByFBandAdmin(admin.ModelAdmin):
            list_display = ["name", "genres", "nr_of_members"]
            ordering = (F("nr_of_members"), Upper("name"), F("genres"))

        m = OrderedByFBandAdmin(Band, custom_site)
        request = self.factory.get("/band/")
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.get_ordering_field_columns(), {3: "asc", 2: "asc"})

    def test_select_related_preserved(self):
        """
        Regression test for #10348: ChangeList.get_queryset() shouldn't
        overwrite a custom select_related provided by ModelAdmin.get_queryset().
        """
        m = ChildAdmin(Child, custom_site)
        request = self.factory.get("/child/")
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.query.select_related, {"parent": {}})

    def test_select_related_preserved_when_multi_valued_in_search_fields(self):
        """
        Test that select_related preservation works correctly when a multi-valued search is performed.

        This test case verifies that the select_related query optimization is preserved when a search query
        contains multiple values, ensuring efficient database queries even in complex search scenarios.

        The test scenario involves creating a parent object with multiple child objects, then performing a search
        on the parent object using a query that matches multiple child objects. It asserts that the resulting
        queryset count is correct and that the select_related optimization is applied to the queryset query.

        The purpose of this test is to ensure that the django admin changelist view correctly handles search
        queries with multiple values, maintaining optimal database performance while still returning accurate results.
        """
        parent = Parent.objects.create(name="Mary")
        Child.objects.create(parent=parent, name="Danielle")
        Child.objects.create(parent=parent, name="Daniel")

        m = ParentAdmin(Parent, custom_site)
        request = self.factory.get("/parent/", data={SEARCH_VAR: "daniel"})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 1)
        # select_related is preserved.
        self.assertEqual(cl.queryset.query.select_related, {"child": {}})

    def test_select_related_as_tuple(self):
        """

        Tests that the select_related query is correctly applied as a tuple in the InvitationAdmin changelist.

        This test case verifies that the queryset used in the changelist view of the InvitationAdmin
        includes the 'player' model in the select_related clause, optimizing database queries.

        """
        ia = InvitationAdmin(Invitation, custom_site)
        request = self.factory.get("/invitation/")
        request.user = self.superuser
        cl = ia.get_changelist_instance(request)
        self.assertEqual(cl.queryset.query.select_related, {"player": {}})

    def test_select_related_as_empty_tuple(self):
        """
        Tests that when the list_select_related attribute is set to an empty tuple,
        the changelist queryset does not use select_related, ensuring that no related
        objects are joined in the query, thereby preventing unnecessary database queries.
        This test case verifies the expected behavior of the InvitationAdmin class when
        configured to not select related objects.
        """
        ia = InvitationAdmin(Invitation, custom_site)
        ia.list_select_related = ()
        request = self.factory.get("/invitation/")
        request.user = self.superuser
        cl = ia.get_changelist_instance(request)
        self.assertIs(cl.queryset.query.select_related, False)

    def test_get_select_related_custom_method(self):
        """

        Tests the get_list_select_related method of a custom ModelAdmin class.

        This test case verifies that the get_list_select_related method correctly returns
        a tuple of related fields to be used for select_related queries in the admin changelist view.
        In this scenario, the test checks that the 'band' and 'player' fields are properly selected
        for the Invitation model, optimizing the database query performance.

        """
        class GetListSelectRelatedAdmin(admin.ModelAdmin):
            list_display = ("band", "player")

            def get_list_select_related(self, request):
                return ("band", "player")

        ia = GetListSelectRelatedAdmin(Invitation, custom_site)
        request = self.factory.get("/invitation/")
        request.user = self.superuser
        cl = ia.get_changelist_instance(request)
        self.assertEqual(cl.queryset.query.select_related, {"player": {}, "band": {}})

    def test_many_search_terms(self):
        """

        Tests the ParentAdmin changelist view with many search terms.

        This test case checks that the changelist view correctly filters results when
        a large number of search terms are provided. It creates a Parent and two Children,
        then simulates a GET request to the Parent changelist view with a query string
        containing a large number of search terms.

        The test verifies that the resulting queryset contains the expected number of
        objects and that the database query uses the correct number of JOINs, ensuring
        efficient query execution even with a large number of search terms.

        """
        parent = Parent.objects.create(name="Mary")
        Child.objects.create(parent=parent, name="Danielle")
        Child.objects.create(parent=parent, name="Daniel")

        m = ParentAdmin(Parent, custom_site)
        request = self.factory.get("/parent/", data={SEARCH_VAR: "daniel " * 80})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        with CaptureQueriesContext(connection) as context:
            object_count = cl.queryset.count()
        self.assertEqual(object_count, 1)
        self.assertEqual(context.captured_queries[0]["sql"].count("JOIN"), 1)

    def test_related_field_multiple_search_terms(self):
        """
        Searches over multi-valued relationships return rows from related
        models only when all searched fields match that row.
        """
        parent = Parent.objects.create(name="Mary")
        Child.objects.create(parent=parent, name="Danielle", age=18)
        Child.objects.create(parent=parent, name="Daniel", age=19)

        m = ParentAdminTwoSearchFields(Parent, custom_site)

        request = self.factory.get("/parent/", data={SEARCH_VAR: "danielle 19"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 0)

        request = self.factory.get("/parent/", data={SEARCH_VAR: "daniel 19"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 1)

    def test_result_list_empty_changelist_value(self):
        """
        Regression test for #14982: EMPTY_CHANGELIST_VALUE should be honored
        for relationship fields
        """
        new_child = Child.objects.create(name="name", parent=None)
        request = self.factory.get("/child/")
        request.user = self.superuser
        m = ChildAdmin(Child, custom_site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        link = reverse("admin:admin_changelist_child_change", args=(new_child.id,))
        row_html = build_tbody_html(
            new_child, link, "name", '<td class="field-parent nowrap">-</td>'
        )
        self.assertNotEqual(
            table_output.find(row_html),
            -1,
            "Failed to find expected row element: %s" % table_output,
        )

    def test_result_list_empty_changelist_value_blank_string(self):
        new_child = Child.objects.create(name="", parent=None)
        request = self.factory.get("/child/")
        request.user = self.superuser
        m = ChildAdmin(Child, custom_site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        link = reverse("admin:admin_changelist_child_change", args=(new_child.id,))
        row_html = build_tbody_html(
            new_child, link, "-", '<td class="field-parent nowrap">-</td>'
        )
        self.assertInHTML(row_html, table_output)

    def test_result_list_set_empty_value_display_on_admin_site(self):
        """
        Empty value display can be set on AdminSite.
        """
        new_child = Child.objects.create(name="name", parent=None)
        request = self.factory.get("/child/")
        request.user = self.superuser
        # Set a new empty display value on AdminSite.
        admin.site.empty_value_display = "???"
        m = ChildAdmin(Child, admin.site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        link = reverse("admin:admin_changelist_child_change", args=(new_child.id,))
        row_html = build_tbody_html(
            new_child, link, "name", '<td class="field-parent nowrap">???</td>'
        )
        self.assertNotEqual(
            table_output.find(row_html),
            -1,
            "Failed to find expected row element: %s" % table_output,
        )

    def test_result_list_set_empty_value_display_in_model_admin(self):
        """
        Empty value display can be set in ModelAdmin or individual fields.
        """
        new_child = Child.objects.create(name="name", parent=None)
        request = self.factory.get("/child/")
        request.user = self.superuser
        m = EmptyValueChildAdmin(Child, admin.site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        link = reverse("admin:admin_changelist_child_change", args=(new_child.id,))
        row_html = build_tbody_html(
            new_child,
            link,
            "name",
            '<td class="field-age_display">&amp;dagger;</td>'
            '<td class="field-age">-empty-</td>',
        )
        self.assertNotEqual(
            table_output.find(row_html),
            -1,
            "Failed to find expected row element: %s" % table_output,
        )

    def test_result_list_html(self):
        """
        Inclusion tag result_list generates a table when with default
        ModelAdmin settings.
        """
        new_parent = Parent.objects.create(name="parent")
        new_child = Child.objects.create(name="name", parent=new_parent)
        request = self.factory.get("/child/")
        request.user = self.superuser
        m = ChildAdmin(Child, custom_site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        link = reverse("admin:admin_changelist_child_change", args=(new_child.id,))
        row_html = build_tbody_html(
            new_child,
            link,
            "name",
            '<td class="field-parent nowrap">%s</td>' % new_parent,
        )
        self.assertNotEqual(
            table_output.find(row_html),
            -1,
            "Failed to find expected row element: %s" % table_output,
        )
        self.assertInHTML(
            '<input type="checkbox" id="action-toggle" '
            'aria-label="Select all objects on this page for an action">',
            table_output,
        )

    def test_action_checkbox_for_model_with_dunder_html(self):
        """

        Tests the rendering of action checkboxes for a model in the admin changelist view.

        Verifies that the action checkbox is correctly displayed for a model instance
        in the changelist table, ensuring that the checkbox is present and can be used
        to select the instance for bulk actions. The test covers the case where the
        model instance is a grandchild object with a custom admin site.

        """
        grandchild = GrandChild.objects.create(name="name")
        request = self._mocked_authenticated_request("/grandchild/", self.superuser)
        m = GrandChildAdmin(GrandChild, custom_site)
        cl = m.get_changelist_instance(request)
        cl.formset = None
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": GrandChild._meta})
        table_output = template.render(context)
        link = reverse(
            "admin:admin_changelist_grandchild_change", args=(grandchild.id,)
        )
        row_html = build_tbody_html(
            grandchild,
            link,
            "name",
            '<td class="field-parent__name">-</td>'
            '<td class="field-parent__parent__name">-</td>',
        )
        self.assertNotEqual(
            table_output.find(row_html),
            -1,
            "Failed to find expected row element: %s" % table_output,
        )

    def test_result_list_editable_html(self):
        """
        Regression tests for #11791: Inclusion tag result_list generates a
        table and this checks that the items are nested within the table
        element tags.
        Also a regression test for #13599, verifies that hidden fields
        when list_editable is enabled are rendered in a div outside the
        table.
        """
        new_parent = Parent.objects.create(name="parent")
        new_child = Child.objects.create(name="name", parent=new_parent)
        request = self.factory.get("/child/")
        request.user = self.superuser
        m = ChildAdmin(Child, custom_site)

        # Test with list_editable fields
        m.list_display = ["id", "name", "parent"]
        m.list_display_links = ["id"]
        m.list_editable = ["name"]
        cl = m.get_changelist_instance(request)
        FormSet = m.get_changelist_formset(request)
        cl.formset = FormSet(queryset=cl.result_list)
        template = Template(
            "{% load admin_list %}{% spaceless %}{% result_list cl %}{% endspaceless %}"
        )
        context = Context({"cl": cl, "opts": Child._meta})
        table_output = template.render(context)
        # make sure that hidden fields are in the correct place
        hiddenfields_div = (
            '<div class="hiddenfields">'
            '<input type="hidden" name="form-0-id" value="%d" id="id_form-0-id">'
            "</div>"
        ) % new_child.id
        self.assertInHTML(
            hiddenfields_div, table_output, msg_prefix="Failed to find hidden fields"
        )

        # make sure that list editable fields are rendered in divs correctly
        editable_name_field = (
            '<input name="form-0-name" value="name" class="vTextField" '
            'maxlength="30" type="text" id="id_form-0-name">'
        )
        self.assertInHTML(
            '<td class="field-name">%s</td>' % editable_name_field,
            table_output,
            msg_prefix='Failed to find "name" list_editable field',
        )

    def test_result_list_editable(self):
        """
        Regression test for #14312: list_editable with pagination
        """
        new_parent = Parent.objects.create(name="parent")
        for i in range(1, 201):
            Child.objects.create(name="name %s" % i, parent=new_parent)
        request = self.factory.get("/child/", data={"p": -1})  # Anything outside range
        request.user = self.superuser
        m = ChildAdmin(Child, custom_site)

        # Test with list_editable fields
        m.list_display = ["id", "name", "parent"]
        m.list_display_links = ["id"]
        m.list_editable = ["name"]
        with self.assertRaises(IncorrectLookupParameters):
            m.get_changelist_instance(request)

    @skipUnlessDBFeature("supports_transactions")
    def test_list_editable_atomicity(self):
        """
        Tests the atomicity of list editable views in the Django admin interface.

        This test ensures that when saving multiple objects through the admin changelist view,
        either all changes are saved or none are, in order to maintain data consistency.

        It covers two scenarios:
        - A `DatabaseError` occurs when saving both objects, in which case no changes should be applied.
        - A `DatabaseError` occurs when saving the second object, after the first object has been saved successfully, 
          in which case the changes to the first object should be rolled back. 

        The test verifies that the original state of the objects is preserved in both cases.
        """
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        b = Swallow.objects.create(origin="Swallow B", load=2, speed=2)

        self.client.force_login(self.superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-uuid": str(a.pk),
            "form-1-uuid": str(b.pk),
            "form-0-load": "9.0",
            "form-0-speed": "3.0",
            "form-1-load": "5.0",
            "form-1-speed": "1.0",
            "_save": "Save",
        }
        with mock.patch(
            "django.contrib.admin.ModelAdmin.log_change", side_effect=DatabaseError
        ):
            with self.assertRaises(DatabaseError):
                self.client.post(changelist_url, data)
        # Original values are preserved.
        a.refresh_from_db()
        self.assertEqual(a.load, 4)
        self.assertEqual(a.speed, 1)
        b.refresh_from_db()
        self.assertEqual(b.load, 2)
        self.assertEqual(b.speed, 2)

        with mock.patch(
            "django.contrib.admin.ModelAdmin.log_change",
            side_effect=[None, DatabaseError],
        ):
            with self.assertRaises(DatabaseError):
                self.client.post(changelist_url, data)
        # Original values are preserved.
        a.refresh_from_db()
        self.assertEqual(a.load, 4)
        self.assertEqual(a.speed, 1)
        b.refresh_from_db()
        self.assertEqual(b.load, 2)
        self.assertEqual(b.speed, 2)

    def test_custom_paginator(self):
        """

        Tests the custom paginator functionality in the admin interface.

        This test case creates a parent object and 200 child objects associated with it.
        It then simulates a GET request to the child changelist page with a superuser.
        The test verifies that the changelist instance uses the custom paginator to paginate the results.

        """
        new_parent = Parent.objects.create(name="parent")
        for i in range(1, 201):
            Child.objects.create(name="name %s" % i, parent=new_parent)

        request = self.factory.get("/child/")
        request.user = self.superuser
        m = CustomPaginationAdmin(Child, custom_site)

        cl = m.get_changelist_instance(request)
        cl.get_results(request)
        self.assertIsInstance(cl.paginator, CustomPaginator)

    def test_distinct_for_m2m_in_list_filter(self):
        """
        Regression test for #13902: When using a ManyToMany in list_filter,
        results shouldn't appear more than once. Basic ManyToMany.
        """
        blues = Genre.objects.create(name="Blues")
        band = Band.objects.create(name="B.B. King Review", nr_of_members=11)

        band.genres.add(blues)
        band.genres.add(blues)

        m = BandAdmin(Band, custom_site)
        request = self.factory.get("/band/", data={"genres": blues.pk})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        cl.get_results(request)

        # There's only one Group instance
        self.assertEqual(cl.result_count, 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_distinct_for_through_m2m_in_list_filter(self):
        """
        Regression test for #13902: When using a ManyToMany in list_filter,
        results shouldn't appear more than once. With an intermediate model.
        """
        lead = Musician.objects.create(name="Vox")
        band = Group.objects.create(name="The Hype")
        Membership.objects.create(group=band, music=lead, role="lead voice")
        Membership.objects.create(group=band, music=lead, role="bass player")

        m = GroupAdmin(Group, custom_site)
        request = self.factory.get("/group/", data={"members": lead.pk})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        cl.get_results(request)

        # There's only one Group instance
        self.assertEqual(cl.result_count, 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_distinct_for_through_m2m_at_second_level_in_list_filter(self):
        """
        When using a ManyToMany in list_filter at the second level behind a
        ForeignKey, distinct() must be called and results shouldn't appear more
        than once.
        """
        lead = Musician.objects.create(name="Vox")
        band = Group.objects.create(name="The Hype")
        Concert.objects.create(name="Woodstock", group=band)
        Membership.objects.create(group=band, music=lead, role="lead voice")
        Membership.objects.create(group=band, music=lead, role="bass player")

        m = ConcertAdmin(Concert, custom_site)
        request = self.factory.get("/concert/", data={"group__members": lead.pk})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        cl.get_results(request)

        # There's only one Concert instance
        self.assertEqual(cl.result_count, 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_distinct_for_inherited_m2m_in_list_filter(self):
        """
        Regression test for #13902: When using a ManyToMany in list_filter,
        results shouldn't appear more than once. Model managed in the
        admin inherits from the one that defines the relationship.
        """
        lead = Musician.objects.create(name="John")
        four = Quartet.objects.create(name="The Beatles")
        Membership.objects.create(group=four, music=lead, role="lead voice")
        Membership.objects.create(group=four, music=lead, role="guitar player")

        m = QuartetAdmin(Quartet, custom_site)
        request = self.factory.get("/quartet/", data={"members": lead.pk})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        cl.get_results(request)

        # There's only one Quartet instance
        self.assertEqual(cl.result_count, 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_distinct_for_m2m_to_inherited_in_list_filter(self):
        """
        Regression test for #13902: When using a ManyToMany in list_filter,
        results shouldn't appear more than once. Target of the relationship
        inherits from another.
        """
        lead = ChordsMusician.objects.create(name="Player A")
        three = ChordsBand.objects.create(name="The Chords Trio")
        Invitation.objects.create(band=three, player=lead, instrument="guitar")
        Invitation.objects.create(band=three, player=lead, instrument="bass")

        m = ChordsBandAdmin(ChordsBand, custom_site)
        request = self.factory.get("/chordsband/", data={"members": lead.pk})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        cl.get_results(request)

        # There's only one ChordsBand instance
        self.assertEqual(cl.result_count, 1)

    def test_distinct_for_non_unique_related_object_in_list_filter(self):
        """
        Regressions tests for #15819: If a field listed in list_filters
        is a non-unique related object, distinct() must be called.
        """
        parent = Parent.objects.create(name="Mary")
        # Two children with the same name
        Child.objects.create(parent=parent, name="Daniel")
        Child.objects.create(parent=parent, name="Daniel")

        m = ParentAdmin(Parent, custom_site)
        request = self.factory.get("/parent/", data={"child__name": "Daniel"})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        # Make sure distinct() was called
        self.assertEqual(cl.queryset.count(), 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_changelist_search_form_validation(self):
        """

        Tests the validation of the search form in the changelist view of the ConcertAdmin class.

        Specifically, it checks that the search form correctly handles input containing null characters,
        rejecting such input and displaying an appropriate error message to the user.

        The test covers various cases of invalid input, ensuring that the validation logic is robust and
        effective in preventing null characters from being processed.

        """
        m = ConcertAdmin(Concert, custom_site)
        tests = [
            ({SEARCH_VAR: "\x00"}, "Null characters are not allowed."),
            ({SEARCH_VAR: "some\x00thing"}, "Null characters are not allowed."),
        ]
        for case, error in tests:
            with self.subTest(case=case):
                request = self.factory.get("/concert/", case)
                request.user = self.superuser
                request._messages = CookieStorage(request)
                m.get_changelist_instance(request)
                messages = [m.message for m in request._messages]
                self.assertEqual(1, len(messages))
                self.assertEqual(error, messages[0])

    def test_distinct_for_non_unique_related_object_in_search_fields(self):
        """
        Regressions tests for #15819: If a field listed in search_fields
        is a non-unique related object, distinct() must be called.
        """
        parent = Parent.objects.create(name="Mary")
        Child.objects.create(parent=parent, name="Danielle")
        Child.objects.create(parent=parent, name="Daniel")

        m = ParentAdmin(Parent, custom_site)
        request = self.factory.get("/parent/", data={SEARCH_VAR: "daniel"})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        # Make sure distinct() was called
        self.assertEqual(cl.queryset.count(), 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_distinct_for_many_to_many_at_second_level_in_search_fields(self):
        """
        When using a ManyToMany in search_fields at the second level behind a
        ForeignKey, distinct() must be called and results shouldn't appear more
        than once.
        """
        lead = Musician.objects.create(name="Vox")
        band = Group.objects.create(name="The Hype")
        Concert.objects.create(name="Woodstock", group=band)
        Membership.objects.create(group=band, music=lead, role="lead voice")
        Membership.objects.create(group=band, music=lead, role="bass player")

        m = ConcertAdmin(Concert, custom_site)
        request = self.factory.get("/concert/", data={SEARCH_VAR: "vox"})
        request.user = self.superuser

        cl = m.get_changelist_instance(request)
        # There's only one Concert instance
        self.assertEqual(cl.queryset.count(), 1)
        # Queryset must be deletable.
        cl.queryset.delete()
        self.assertEqual(cl.queryset.count(), 0)

    def test_multiple_search_fields(self):
        """
        All rows containing each of the searched words are returned, where each
        word must be in one of search_fields.
        """
        band_duo = Group.objects.create(name="Duo")
        band_hype = Group.objects.create(name="The Hype")
        mary = Musician.objects.create(name="Mary Halvorson")
        jonathan = Musician.objects.create(name="Jonathan Finlayson")
        band_duo.members.set([mary, jonathan])
        Concert.objects.create(name="Tiny desk concert", group=band_duo)
        Concert.objects.create(name="Woodstock concert", group=band_hype)
        # FK lookup.
        concert_model_admin = ConcertAdmin(Concert, custom_site)
        concert_model_admin.search_fields = ["group__name", "name"]
        # Reverse FK lookup.
        group_model_admin = GroupAdmin(Group, custom_site)
        group_model_admin.search_fields = ["name", "concert__name", "members__name"]
        for search_string, result_count in (
            ("Duo Concert", 1),
            ("Tiny Desk Concert", 1),
            ("Concert", 2),
            ("Other Concert", 0),
            ("Duo Woodstock", 0),
        ):
            with self.subTest(search_string=search_string):
                # FK lookup.
                request = self.factory.get(
                    "/concert/", data={SEARCH_VAR: search_string}
                )
                request.user = self.superuser
                concert_changelist = concert_model_admin.get_changelist_instance(
                    request
                )
                self.assertEqual(concert_changelist.queryset.count(), result_count)
                # Reverse FK lookup.
                request = self.factory.get("/group/", data={SEARCH_VAR: search_string})
                request.user = self.superuser
                group_changelist = group_model_admin.get_changelist_instance(request)
                self.assertEqual(group_changelist.queryset.count(), result_count)
        # Many-to-many lookup.
        for search_string, result_count in (
            ("Finlayson Duo Tiny", 1),
            ("Finlayson", 1),
            ("Finlayson Hype", 0),
            ("Jonathan Finlayson Duo", 1),
            ("Mary Jonathan Duo", 0),
            ("Oscar Finlayson Duo", 0),
        ):
            with self.subTest(search_string=search_string):
                request = self.factory.get("/group/", data={SEARCH_VAR: search_string})
                request.user = self.superuser
                group_changelist = group_model_admin.get_changelist_instance(request)
                self.assertEqual(group_changelist.queryset.count(), result_count)

    def test_pk_in_search_fields(self):
        band = Group.objects.create(name="The Hype")
        Concert.objects.create(name="Woodstock", group=band)

        m = ConcertAdmin(Concert, custom_site)
        m.search_fields = ["group__pk"]

        request = self.factory.get("/concert/", data={SEARCH_VAR: band.pk})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 1)

        request = self.factory.get("/concert/", data={SEARCH_VAR: band.pk + 5})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 0)

    def test_builtin_lookup_in_search_fields(self):
        band = Group.objects.create(name="The Hype")
        concert = Concert.objects.create(name="Woodstock", group=band)

        m = ConcertAdmin(Concert, custom_site)
        m.search_fields = ["name__iexact"]

        request = self.factory.get("/", data={SEARCH_VAR: "woodstock"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertCountEqual(cl.queryset, [concert])

        request = self.factory.get("/", data={SEARCH_VAR: "wood"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertCountEqual(cl.queryset, [])

    def test_custom_lookup_in_search_fields(self):
        """

        Tests the functionality of a custom lookup in the search fields of the Concert admin interface.

        The test creates a group and a concert, then sets up a custom search field on the Concert model's admin
        interface to search the group name using a case-insensitive contains lookup. It then tests that searching 
        for the group name returns the expected concert, and that searching for the concert name does not return 
        any results when the search is not configured to search the concert name itself.

        Verifies that the custom lookup is properly integrated with the admin interface's search functionality.

        """
        band = Group.objects.create(name="The Hype")
        concert = Concert.objects.create(name="Woodstock", group=band)

        m = ConcertAdmin(Concert, custom_site)
        m.search_fields = ["group__name__cc"]
        with register_lookup(Field, Contains, lookup_name="cc"):
            request = self.factory.get("/", data={SEARCH_VAR: "Hype"})
            request.user = self.superuser
            cl = m.get_changelist_instance(request)
            self.assertCountEqual(cl.queryset, [concert])

            request = self.factory.get("/", data={SEARCH_VAR: "Woodstock"})
            request.user = self.superuser
            cl = m.get_changelist_instance(request)
            self.assertCountEqual(cl.queryset, [])

    def test_spanning_relations_with_custom_lookup_in_search_fields(self):
        hype = Group.objects.create(name="The Hype")
        concert = Concert.objects.create(name="Woodstock", group=hype)
        vox = Musician.objects.create(name="Vox", age=20)
        Membership.objects.create(music=vox, group=hype)
        # Register a custom lookup on IntegerField to ensure that field
        # traversing logic in ModelAdmin.get_search_results() works.
        with register_lookup(IntegerField, Exact, lookup_name="exactly"):
            m = ConcertAdmin(Concert, custom_site)
            m.search_fields = ["group__members__age__exactly"]

            request = self.factory.get("/", data={SEARCH_VAR: "20"})
            request.user = self.superuser
            cl = m.get_changelist_instance(request)
            self.assertCountEqual(cl.queryset, [concert])

            request = self.factory.get("/", data={SEARCH_VAR: "21"})
            request.user = self.superuser
            cl = m.get_changelist_instance(request)
            self.assertCountEqual(cl.queryset, [])

    def test_custom_lookup_with_pk_shortcut(self):
        """

        Tests the custom lookup functionality with a primary key shortcut in the admin interface.

        Verifies that searching for a specific primary key value returns the corresponding object.
        The test covers the following scenarios:
        - Searching for an object by its primary key using the 'pk__exact' lookup type.
        - Ensuring that the search results are accurate and only return the object(s) with the matching primary key.

        This test case checks the functionality of the admin interface's search feature with custom primary key fields.

        """
        self.assertEqual(CharPK._meta.pk.name, "char_pk")  # Not equal to 'pk'.
        m = admin.ModelAdmin(CustomIdUser, custom_site)

        abc = CharPK.objects.create(char_pk="abc")
        abcd = CharPK.objects.create(char_pk="abcd")
        m = admin.ModelAdmin(CharPK, custom_site)
        m.search_fields = ["pk__exact"]

        request = self.factory.get("/", data={SEARCH_VAR: "abc"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertCountEqual(cl.queryset, [abc])

        request = self.factory.get("/", data={SEARCH_VAR: "abcd"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertCountEqual(cl.queryset, [abcd])

    def test_no_distinct_for_m2m_in_list_filter_without_params(self):
        """
        If a ManyToManyField is in list_filter but isn't in any lookup params,
        the changelist's query shouldn't have distinct.
        """
        m = BandAdmin(Band, custom_site)
        for lookup_params in ({}, {"name": "test"}):
            request = self.factory.get("/band/", lookup_params)
            request.user = self.superuser
            cl = m.get_changelist_instance(request)
            self.assertIs(cl.queryset.query.distinct, False)

        # A ManyToManyField in params does have distinct applied.
        request = self.factory.get("/band/", {"genres": "0"})
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        self.assertIs(cl.queryset.query.distinct, True)

    def test_pagination(self):
        """
        Regression tests for #12893: Pagination in admins changelist doesn't
        use queryset set by modeladmin.
        """
        parent = Parent.objects.create(name="anything")
        for i in range(1, 31):
            Child.objects.create(name="name %s" % i, parent=parent)
            Child.objects.create(name="filtered %s" % i, parent=parent)

        request = self.factory.get("/child/")
        request.user = self.superuser

        # Test default queryset
        m = ChildAdmin(Child, custom_site)
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 60)
        self.assertEqual(cl.paginator.count, 60)
        self.assertEqual(list(cl.paginator.page_range), [1, 2, 3, 4, 5, 6])

        # Test custom queryset
        m = FilteredChildAdmin(Child, custom_site)
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.queryset.count(), 30)
        self.assertEqual(cl.paginator.count, 30)
        self.assertEqual(list(cl.paginator.page_range), [1, 2, 3])

    def test_computed_list_display_localization(self):
        """
        Regression test for #13196: output of functions should be  localized
        in the changelist.
        """
        self.client.force_login(self.superuser)
        event = Event.objects.create(date=datetime.date.today())
        response = self.client.get(reverse("admin:admin_changelist_event_changelist"))
        self.assertContains(response, formats.localize(event.date))
        self.assertNotContains(response, str(event.date))

    def test_dynamic_list_display(self):
        """
        Regression tests for #14206: dynamic list_display support.
        """
        parent = Parent.objects.create(name="parent")
        for i in range(10):
            Child.objects.create(name="child %s" % i, parent=parent)

        user_noparents = self._create_superuser("noparents")
        user_parents = self._create_superuser("parents")

        # Test with user 'noparents'
        m = custom_site.get_model_admin(Child)
        request = self._mocked_authenticated_request("/child/", user_noparents)
        response = m.changelist_view(request)
        self.assertNotContains(response, "Parent object")

        list_display = m.get_list_display(request)
        list_display_links = m.get_list_display_links(request, list_display)
        self.assertEqual(list_display, ["name", "age"])
        self.assertEqual(list_display_links, ["name"])

        # Test with user 'parents'
        m = DynamicListDisplayChildAdmin(Child, custom_site)
        request = self._mocked_authenticated_request("/child/", user_parents)
        response = m.changelist_view(request)
        self.assertContains(response, "Parent object")

        custom_site.unregister(Child)

        list_display = m.get_list_display(request)
        list_display_links = m.get_list_display_links(request, list_display)
        self.assertEqual(list_display, ("parent", "name", "age"))
        self.assertEqual(list_display_links, ["parent"])

        # Test default implementation
        custom_site.register(Child, ChildAdmin)
        m = custom_site.get_model_admin(Child)
        request = self._mocked_authenticated_request("/child/", user_noparents)
        response = m.changelist_view(request)
        self.assertContains(response, "Parent object")

    def test_show_all(self):
        """
        Test the functionality of showing all objects in the changelist view.

        This test verifies that the changelist view correctly handles the \"show all\" option
        when the number of objects exceeds the default limit. It checks that all objects are
        displayed when the limit is raised above the number of objects, and that only the
        default number of objects are shown when the limit is set below the number of objects.

        The test creates a large number of child objects, then tests the changelist view
        with different settings for the maximum number of objects to show. It checks that
        the correct number of objects are displayed in each case.
        """
        parent = Parent.objects.create(name="anything")
        for i in range(1, 31):
            Child.objects.create(name="name %s" % i, parent=parent)
            Child.objects.create(name="filtered %s" % i, parent=parent)

        # Add "show all" parameter to request
        request = self.factory.get("/child/", data={ALL_VAR: ""})
        request.user = self.superuser

        # Test valid "show all" request (number of total objects is under max)
        m = ChildAdmin(Child, custom_site)
        m.list_max_show_all = 200
        # 200 is the max we'll pass to ChangeList
        cl = m.get_changelist_instance(request)
        cl.get_results(request)
        self.assertEqual(len(cl.result_list), 60)

        # Test invalid "show all" request (number of total objects over max)
        # falls back to paginated pages
        m = ChildAdmin(Child, custom_site)
        m.list_max_show_all = 30
        # 30 is the max we'll pass to ChangeList for this test
        cl = m.get_changelist_instance(request)
        cl.get_results(request)
        self.assertEqual(len(cl.result_list), 10)

    def test_dynamic_list_display_links(self):
        """
        Regression tests for #16257: dynamic list_display_links support.
        """
        parent = Parent.objects.create(name="parent")
        for i in range(1, 10):
            Child.objects.create(id=i, name="child %s" % i, parent=parent, age=i)

        m = DynamicListDisplayLinksChildAdmin(Child, custom_site)
        superuser = self._create_superuser("superuser")
        request = self._mocked_authenticated_request("/child/", superuser)
        response = m.changelist_view(request)
        for i in range(1, 10):
            link = reverse("admin:admin_changelist_child_change", args=(i,))
            self.assertContains(response, '<a href="%s">%s</a>' % (link, i))

        list_display = m.get_list_display(request)
        list_display_links = m.get_list_display_links(request, list_display)
        self.assertEqual(list_display, ("parent", "name", "age"))
        self.assertEqual(list_display_links, ["age"])

    def test_no_list_display_links(self):
        """#15185 -- Allow no links from the 'change list' view grid."""
        p = Parent.objects.create(name="parent")
        m = NoListDisplayLinksParentAdmin(Parent, custom_site)
        superuser = self._create_superuser("superuser")
        request = self._mocked_authenticated_request("/parent/", superuser)
        response = m.changelist_view(request)
        link = reverse("admin:admin_changelist_parent_change", args=(p.pk,))
        self.assertNotContains(response, '<a href="%s">' % link)

    def test_clear_all_filters_link(self):
        """
        Tests the functionality of the \"Clear all filters\" link in the admin user changelist view.

        This test checks that the link is not present when no filters are applied, and that it is correctly displayed when various filters are applied.
        The test covers different filtering scenarios, including exact matches, starts with searches, and popup searches, verifying that the link's href attribute is correctly constructed for each case.
        """
        self.client.force_login(self.superuser)
        url = reverse("admin:auth_user_changelist")
        response = self.client.get(url)
        self.assertNotContains(response, "&#10006; Clear all filters")
        link = '<a href="%s">&#10006; Clear all filters</a>'
        for data, href in (
            ({"is_staff__exact": "0"}, "?"),
            (
                {"is_staff__exact": "0", "username__startswith": "test"},
                "?username__startswith=test",
            ),
            (
                {"is_staff__exact": "0", SEARCH_VAR: "test"},
                "?%s=test" % SEARCH_VAR,
            ),
            (
                {"is_staff__exact": "0", IS_POPUP_VAR: "id"},
                "?%s=id" % IS_POPUP_VAR,
            ),
        ):
            with self.subTest(data=data):
                response = self.client.get(url, data=data)
                self.assertContains(response, link % href)

    def test_clear_all_filters_link_callable_filter(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:admin_changelist_band_changelist")
        response = self.client.get(url)
        self.assertNotContains(response, "&#10006; Clear all filters")
        link = '<a href="%s">&#10006; Clear all filters</a>'
        for data, href in (
            ({"nr_of_members_partition": "5"}, "?"),
            (
                {"nr_of_members_partition": "more", "name__startswith": "test"},
                "?name__startswith=test",
            ),
            (
                {"nr_of_members_partition": "5", IS_POPUP_VAR: "id"},
                "?%s=id" % IS_POPUP_VAR,
            ),
        ):
            with self.subTest(data=data):
                response = self.client.get(url, data=data)
                self.assertContains(response, link % href)

    def test_no_clear_all_filters_link(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:auth_user_changelist")
        link = ">&#10006; Clear all filters</a>"
        for data in (
            {SEARCH_VAR: "test"},
            {ORDER_VAR: "-1"},
            {TO_FIELD_VAR: "id"},
            {PAGE_VAR: "1"},
            {IS_POPUP_VAR: "1"},
            {IS_FACETS_VAR: ""},
            {"username__startswith": "test"},
        ):
            with self.subTest(data=data):
                response = self.client.get(url, data=data)
                self.assertNotContains(response, link)

    def test_tuple_list_display(self):
        """
        Tests the display of a Swallow instance and its associated SwallowOneToOne instance in the admin changelist view.

        Verifies that the changelist view correctly renders the origin, load, and speed attributes of a Swallow instance.
        Additionally, checks that the SwallowOneToOne instance is properly displayed, with an empty value shown for Swallow instances without a one-to-one relationship.

        Ensures that the admin view accurately represents the underlying data, providing a correct and user-friendly interface for administrators to manage Swallow instances and their associated relationships.
        """
        swallow = Swallow.objects.create(origin="Africa", load="12.34", speed="22.2")
        swallow2 = Swallow.objects.create(origin="Africa", load="12.34", speed="22.2")
        swallow_o2o = SwallowOneToOne.objects.create(swallow=swallow2)

        model_admin = SwallowAdmin(Swallow, custom_site)
        superuser = self._create_superuser("superuser")
        request = self._mocked_authenticated_request("/swallow/", superuser)
        response = model_admin.changelist_view(request)
        # just want to ensure it doesn't blow up during rendering
        self.assertContains(response, str(swallow.origin))
        self.assertContains(response, str(swallow.load))
        self.assertContains(response, str(swallow.speed))
        # Reverse one-to-one relations should work.
        self.assertContains(response, '<td class="field-swallowonetoone">-</td>')
        self.assertContains(
            response, '<td class="field-swallowonetoone">%s</td>' % swallow_o2o
        )

    def test_multiuser_edit(self):
        """
        Simultaneous edits of list_editable fields on the changelist by
        different users must not result in one user's edits creating a new
        object instead of modifying the correct existing object (#11313).
        """
        # To replicate this issue, simulate the following steps:
        # 1. User1 opens an admin changelist with list_editable fields.
        # 2. User2 edits object "Foo" such that it moves to another page in
        #    the pagination order and saves.
        # 3. User1 edits object "Foo" and saves.
        # 4. The edit made by User1 does not get applied to object "Foo" but
        #    instead is used to create a new object (bug).

        # For this test, order the changelist by the 'speed' attribute and
        # display 3 objects per page (SwallowAdmin.list_per_page = 3).

        # Setup the test to reflect the DB state after step 2 where User2 has
        # edited the first swallow object's speed from '4' to '1'.
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        b = Swallow.objects.create(origin="Swallow B", load=2, speed=2)
        c = Swallow.objects.create(origin="Swallow C", load=5, speed=5)
        d = Swallow.objects.create(origin="Swallow D", load=9, speed=9)

        superuser = self._create_superuser("superuser")
        self.client.force_login(superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")

        # Send the POST from User1 for step 3. It's still using the changelist
        # ordering from before User2's edits in step 2.
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-uuid": str(d.pk),
            "form-1-uuid": str(c.pk),
            "form-2-uuid": str(a.pk),
            "form-0-load": "9.0",
            "form-0-speed": "9.0",
            "form-1-load": "5.0",
            "form-1-speed": "5.0",
            "form-2-load": "5.0",
            "form-2-speed": "4.0",
            "_save": "Save",
        }
        response = self.client.post(
            changelist_url, data, follow=True, extra={"o": "-2"}
        )

        # The object User1 edited in step 3 is displayed on the changelist and
        # has the correct edits applied.
        self.assertContains(response, "1 swallow was changed successfully.")
        self.assertContains(response, a.origin)
        a.refresh_from_db()
        self.assertEqual(a.load, float(data["form-2-load"]))
        self.assertEqual(a.speed, float(data["form-2-speed"]))
        b.refresh_from_db()
        self.assertEqual(b.load, 2)
        self.assertEqual(b.speed, 2)
        c.refresh_from_db()
        self.assertEqual(c.load, float(data["form-1-load"]))
        self.assertEqual(c.speed, float(data["form-1-speed"]))
        d.refresh_from_db()
        self.assertEqual(d.load, float(data["form-0-load"]))
        self.assertEqual(d.speed, float(data["form-0-speed"]))
        # No new swallows were created.
        self.assertEqual(len(Swallow.objects.all()), 4)

    def test_get_edited_object_ids(self):
        """

        Test the retrieval of edited object IDs in the changelist view.

        This test case verifies that the function correctly identifies and returns the IDs
        of objects that have been modified through the changelist form.

        The test creates multiple swallow objects and a superuser, then simulates a POST
        request to the changelist view with modified data. It checks that the function
        returns the IDs of all objects that were edited in the request.

        The purpose of this test is to ensure that the function accurately determines
        which objects have been changed, allowing for proper processing and saving of the
        edited data.

        """
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        b = Swallow.objects.create(origin="Swallow B", load=2, speed=2)
        c = Swallow.objects.create(origin="Swallow C", load=5, speed=5)
        superuser = self._create_superuser("superuser")
        self.client.force_login(superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")
        m = SwallowAdmin(Swallow, custom_site)
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-uuid": str(a.pk),
            "form-1-uuid": str(b.pk),
            "form-2-uuid": str(c.pk),
            "form-0-load": "9.0",
            "form-0-speed": "9.0",
            "form-1-load": "5.0",
            "form-1-speed": "5.0",
            "form-2-load": "5.0",
            "form-2-speed": "4.0",
            "_save": "Save",
        }
        request = self.factory.post(changelist_url, data=data)
        pks = m._get_edited_object_pks(request, prefix="form")
        self.assertEqual(sorted(pks), sorted([str(a.pk), str(b.pk), str(c.pk)]))

    def test_get_list_editable_queryset(self):
        """
        Tests the _get_list_editable_queryset method of the SwallowAdmin class.

        This method is responsible for determining the queryset of objects that can be edited 
        in the changelist view of the admin interface. The test checks two scenarios:

        * When a valid primary key is provided, the queryset should only contain the 
          corresponding object.
        * When an invalid primary key is provided, the queryset should contain all objects, 
          as no object can be edited.

        The test creates a superuser, logs in, and then sends a POST request to the 
        changelist URL with the provided data. It then checks the count of the resulting 
        queryset to ensure it matches the expected behavior.
        """
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        Swallow.objects.create(origin="Swallow B", load=2, speed=2)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-uuid": str(a.pk),
            "form-0-load": "10",
            "_save": "Save",
        }
        superuser = self._create_superuser("superuser")
        self.client.force_login(superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")
        m = SwallowAdmin(Swallow, custom_site)
        request = self.factory.post(changelist_url, data=data)
        queryset = m._get_list_editable_queryset(request, prefix="form")
        self.assertEqual(queryset.count(), 1)
        data["form-0-uuid"] = "INVALD_PRIMARY_KEY"
        # The unfiltered queryset is returned if there's invalid data.
        request = self.factory.post(changelist_url, data=data)
        queryset = m._get_list_editable_queryset(request, prefix="form")
        self.assertEqual(queryset.count(), 2)

    def test_get_list_editable_queryset_with_regex_chars_in_prefix(self):
        """
        Tests the functionality of retrieving a queryset of list editable objects 
        from the admin changelist view when the prefix contains regex characters.

        Verifies that the _get_list_editable_queryset method correctly filters objects 
        based on the provided prefix, returning a queryset that contains only the 
        objects that match the specified criteria. This test case covers a scenario 
        where the prefix includes regex characters, ensuring that the method handles 
        such cases as expected.

        The test scenario involves creating test data, including Swallow objects, 
        and then simulating a POST request to the admin changelist view with a 
        specific prefix containing regex characters. The method's result is then 
        asserted to contain the expected number of objects, confirming its correctness 
        in handling regex characters in the prefix.
        """
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        Swallow.objects.create(origin="Swallow B", load=2, speed=2)
        data = {
            "form$-TOTAL_FORMS": "2",
            "form$-INITIAL_FORMS": "2",
            "form$-MIN_NUM_FORMS": "0",
            "form$-MAX_NUM_FORMS": "1000",
            "form$-0-uuid": str(a.pk),
            "form$-0-load": "10",
            "_save": "Save",
        }
        superuser = self._create_superuser("superuser")
        self.client.force_login(superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")
        m = SwallowAdmin(Swallow, custom_site)
        request = self.factory.post(changelist_url, data=data)
        queryset = m._get_list_editable_queryset(request, prefix="form$")
        self.assertEqual(queryset.count(), 1)

    def test_changelist_view_list_editable_changed_objects_uses_filter(self):
        """list_editable edits use a filtered queryset to limit memory usage."""
        a = Swallow.objects.create(origin="Swallow A", load=4, speed=1)
        Swallow.objects.create(origin="Swallow B", load=2, speed=2)
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-uuid": str(a.pk),
            "form-0-load": "10",
            "_save": "Save",
        }
        superuser = self._create_superuser("superuser")
        self.client.force_login(superuser)
        changelist_url = reverse("admin:admin_changelist_swallow_changelist")
        with CaptureQueriesContext(connection) as context:
            response = self.client.post(changelist_url, data=data)
            self.assertEqual(response.status_code, 200)
            self.assertIn("WHERE", context.captured_queries[4]["sql"])
            self.assertIn("IN", context.captured_queries[4]["sql"])
            # Check only the first few characters since the UUID may have dashes.
            self.assertIn(str(a.pk)[:8], context.captured_queries[4]["sql"])

    def test_deterministic_order_for_unordered_model(self):
        """
        The primary key is used in the ordering of the changelist's results to
        guarantee a deterministic order, even when the model doesn't have any
        default ordering defined (#17198).
        """
        superuser = self._create_superuser("superuser")

        for counter in range(1, 51):
            UnorderedObject.objects.create(id=counter, bool=True)

        class UnorderedObjectAdmin(admin.ModelAdmin):
            list_per_page = 10

        def check_results_order(ascending=False):
            """

            Checks the order of results in the changelist view.

            This function verifies that the results are displayed in the correct order,
            either ascending or descending, by iterating through multiple pages and
            comparing the IDs of the objects with an expected counter value.

            :param ascending: A boolean indicating whether to check for ascending order (True) or descending order (False). Defaults to False.

            """
            custom_site.register(UnorderedObject, UnorderedObjectAdmin)
            model_admin = UnorderedObjectAdmin(UnorderedObject, custom_site)
            counter = 0 if ascending else 51
            for page in range(1, 6):
                request = self._mocked_authenticated_request(
                    "/unorderedobject/?p=%s" % page, superuser
                )
                response = model_admin.changelist_view(request)
                for result in response.context_data["cl"].result_list:
                    counter += 1 if ascending else -1
                    self.assertEqual(result.id, counter)
            custom_site.unregister(UnorderedObject)

        # When no order is defined at all, everything is ordered by '-pk'.
        check_results_order()

        # When an order field is defined but multiple records have the same
        # value for that field, make sure everything gets ordered by -pk as well.
        UnorderedObjectAdmin.ordering = ["bool"]
        check_results_order()

        # When order fields are defined, including the pk itself, use them.
        UnorderedObjectAdmin.ordering = ["bool", "-pk"]
        check_results_order()
        UnorderedObjectAdmin.ordering = ["bool", "pk"]
        check_results_order(ascending=True)
        UnorderedObjectAdmin.ordering = ["-id", "bool"]
        check_results_order()
        UnorderedObjectAdmin.ordering = ["id", "bool"]
        check_results_order(ascending=True)

    def test_deterministic_order_for_model_ordered_by_its_manager(self):
        """
        The primary key is used in the ordering of the changelist's results to
        guarantee a deterministic order, even when the model has a manager that
        defines a default ordering (#17198).
        """
        superuser = self._create_superuser("superuser")

        for counter in range(1, 51):
            OrderedObject.objects.create(id=counter, bool=True, number=counter)

        class OrderedObjectAdmin(admin.ModelAdmin):
            list_per_page = 10

        def check_results_order(ascending=False):
            custom_site.register(OrderedObject, OrderedObjectAdmin)
            model_admin = OrderedObjectAdmin(OrderedObject, custom_site)
            counter = 0 if ascending else 51
            for page in range(1, 6):
                request = self._mocked_authenticated_request(
                    "/orderedobject/?p=%s" % page, superuser
                )
                response = model_admin.changelist_view(request)
                for result in response.context_data["cl"].result_list:
                    counter += 1 if ascending else -1
                    self.assertEqual(result.id, counter)
            custom_site.unregister(OrderedObject)

        # When no order is defined at all, use the model's default ordering
        # (i.e. 'number').
        check_results_order(ascending=True)

        # When an order field is defined but multiple records have the same
        # value for that field, make sure everything gets ordered by -pk as well.
        OrderedObjectAdmin.ordering = ["bool"]
        check_results_order()

        # When order fields are defined, including the pk itself, use them.
        OrderedObjectAdmin.ordering = ["bool", "-pk"]
        check_results_order()
        OrderedObjectAdmin.ordering = ["bool", "pk"]
        check_results_order(ascending=True)
        OrderedObjectAdmin.ordering = ["-id", "bool"]
        check_results_order()
        OrderedObjectAdmin.ordering = ["id", "bool"]
        check_results_order(ascending=True)

    @isolate_apps("admin_changelist")
    def test_total_ordering_optimization(self):
        """
        Test the optimization of total ordering in the changelist view of the admin interface.

        This test checks that the admin interface correctly handles various ordering scenarios,
        including unique fields, nullable fields, and foreign key fields. It also tests the
        optimization of total ordering, which is used to ensure that rows in the changelist view
        are consistently ordered when there are multiple possible orderings.

        The test covers a range of ordering scenarios, including ascending and descending order,
        null and non-null fields, and fields with unique and non-unique constraints. It also tests
        the behavior of total ordering optimization, which is used to eliminate unnecessary order
        by clauses in the database query.

        The expected output of the test is a list of ordering clauses that are used to determine
        the final ordering of the rows in the changelist view. The test checks that the actual
        output matches the expected output for each test case.

        """
        class Related(models.Model):
            unique_field = models.BooleanField(unique=True)

            class Meta:
                ordering = ("unique_field",)

        class Model(models.Model):
            unique_field = models.BooleanField(unique=True)
            unique_nullable_field = models.BooleanField(unique=True, null=True)
            related = models.ForeignKey(Related, models.CASCADE)
            other_related = models.ForeignKey(Related, models.CASCADE)
            related_unique = models.OneToOneField(Related, models.CASCADE)
            field = models.BooleanField()
            other_field = models.BooleanField()
            null_field = models.BooleanField(null=True)

            class Meta:
                unique_together = {
                    ("field", "other_field"),
                    ("field", "null_field"),
                    ("related", "other_related_id"),
                }

        class ModelAdmin(admin.ModelAdmin):
            def get_queryset(self, request):
                return Model.objects.none()

        request = self._mocked_authenticated_request("/", self.superuser)
        site = admin.AdminSite(name="admin")
        model_admin = ModelAdmin(Model, site)
        change_list = model_admin.get_changelist_instance(request)
        tests = (
            ([], ["-pk"]),
            # Unique non-nullable field.
            (["unique_field"], ["unique_field"]),
            (["-unique_field"], ["-unique_field"]),
            # Unique nullable field.
            (["unique_nullable_field"], ["unique_nullable_field", "-pk"]),
            # Field.
            (["field"], ["field", "-pk"]),
            # Related field introspection is not implemented.
            (["related__unique_field"], ["related__unique_field", "-pk"]),
            # Related attname unique.
            (["related_unique_id"], ["related_unique_id"]),
            # Related ordering introspection is not implemented.
            (["related_unique"], ["related_unique", "-pk"]),
            # Composite unique.
            (["field", "-other_field"], ["field", "-other_field"]),
            # Composite unique nullable.
            (["-field", "null_field"], ["-field", "null_field", "-pk"]),
            # Composite unique and nullable.
            (
                ["-field", "null_field", "other_field"],
                ["-field", "null_field", "other_field"],
            ),
            # Composite unique attnames.
            (["related_id", "-other_related_id"], ["related_id", "-other_related_id"]),
            # Composite unique names.
            (["related", "-other_related_id"], ["related", "-other_related_id", "-pk"]),
        )
        # F() objects composite unique.
        total_ordering = [F("field"), F("other_field").desc(nulls_last=True)]
        # F() objects composite unique nullable.
        non_total_ordering = [F("field"), F("null_field").desc(nulls_last=True)]
        tests += (
            (total_ordering, total_ordering),
            (non_total_ordering, non_total_ordering + ["-pk"]),
        )
        for ordering, expected in tests:
            with self.subTest(ordering=ordering):
                self.assertEqual(
                    change_list._get_deterministic_ordering(ordering), expected
                )

    @isolate_apps("admin_changelist")
    def test_total_ordering_optimization_meta_constraints(self):
        """

        Tests the optimization of meta constraints for models with unique fields and foreign keys.

        This test case covers the following scenarios:
        - Ordering by unique fields
        - Ordering by nullable fields
        - Ordering by related fields
        - Ordering by fields with unique constraints
        - Ordering by fields with check constraints

        It ensures that the deterministic ordering is applied correctly in all cases.

        """
        class Related(models.Model):
            unique_field = models.BooleanField(unique=True)

            class Meta:
                ordering = ("unique_field",)

        class Model(models.Model):
            field_1 = models.BooleanField()
            field_2 = models.BooleanField()
            field_3 = models.BooleanField()
            field_4 = models.BooleanField()
            field_5 = models.BooleanField()
            field_6 = models.BooleanField()
            nullable_1 = models.BooleanField(null=True)
            nullable_2 = models.BooleanField(null=True)
            related_1 = models.ForeignKey(Related, models.CASCADE)
            related_2 = models.ForeignKey(Related, models.CASCADE)
            related_3 = models.ForeignKey(Related, models.CASCADE)
            related_4 = models.ForeignKey(Related, models.CASCADE)

            class Meta:
                constraints = [
                    *[
                        models.UniqueConstraint(fields=fields, name="".join(fields))
                        for fields in (
                            ["field_1"],
                            ["nullable_1"],
                            ["related_1"],
                            ["related_2_id"],
                            ["field_2", "field_3"],
                            ["field_2", "nullable_2"],
                            ["field_2", "related_3"],
                            ["field_3", "related_4_id"],
                        )
                    ],
                    models.CheckConstraint(condition=models.Q(id__gt=0), name="foo"),
                    models.UniqueConstraint(
                        fields=["field_5"],
                        condition=models.Q(id__gt=10),
                        name="total_ordering_1",
                    ),
                    models.UniqueConstraint(
                        fields=["field_6"],
                        condition=models.Q(),
                        name="total_ordering",
                    ),
                ]

        class ModelAdmin(admin.ModelAdmin):
            def get_queryset(self, request):
                return Model.objects.none()

        request = self._mocked_authenticated_request("/", self.superuser)
        site = admin.AdminSite(name="admin")
        model_admin = ModelAdmin(Model, site)
        change_list = model_admin.get_changelist_instance(request)
        tests = (
            # Unique non-nullable field.
            (["field_1"], ["field_1"]),
            # Unique nullable field.
            (["nullable_1"], ["nullable_1", "-pk"]),
            # Related attname unique.
            (["related_1_id"], ["related_1_id"]),
            (["related_2_id"], ["related_2_id"]),
            # Related ordering introspection is not implemented.
            (["related_1"], ["related_1", "-pk"]),
            # Composite unique.
            (["-field_2", "field_3"], ["-field_2", "field_3"]),
            # Composite unique nullable.
            (["field_2", "-nullable_2"], ["field_2", "-nullable_2", "-pk"]),
            # Composite unique and nullable.
            (
                ["field_2", "-nullable_2", "field_3"],
                ["field_2", "-nullable_2", "field_3"],
            ),
            # Composite field and related field name.
            (["field_2", "-related_3"], ["field_2", "-related_3", "-pk"]),
            (["field_3", "related_4"], ["field_3", "related_4", "-pk"]),
            # Composite field and related field attname.
            (["field_2", "related_3_id"], ["field_2", "related_3_id"]),
            (["field_3", "-related_4_id"], ["field_3", "-related_4_id"]),
            # Partial unique constraint is ignored.
            (["field_5"], ["field_5", "-pk"]),
            # Unique constraint with an empty condition.
            (["field_6"], ["field_6"]),
        )
        for ordering, expected in tests:
            with self.subTest(ordering=ordering):
                self.assertEqual(
                    change_list._get_deterministic_ordering(ordering), expected
                )

    def test_dynamic_list_filter(self):
        """
        Regression tests for ticket #17646: dynamic list_filter support.
        """
        parent = Parent.objects.create(name="parent")
        for i in range(10):
            Child.objects.create(name="child %s" % i, parent=parent)

        user_noparents = self._create_superuser("noparents")
        user_parents = self._create_superuser("parents")

        # Test with user 'noparents'
        m = DynamicListFilterChildAdmin(Child, custom_site)
        request = self._mocked_authenticated_request("/child/", user_noparents)
        response = m.changelist_view(request)
        self.assertEqual(response.context_data["cl"].list_filter, ["name", "age"])

        # Test with user 'parents'
        m = DynamicListFilterChildAdmin(Child, custom_site)
        request = self._mocked_authenticated_request("/child/", user_parents)
        response = m.changelist_view(request)
        self.assertEqual(
            response.context_data["cl"].list_filter, ("parent", "name", "age")
        )

    def test_dynamic_search_fields(self):
        child = self._create_superuser("child")
        m = DynamicSearchFieldsChildAdmin(Child, custom_site)
        request = self._mocked_authenticated_request("/child/", child)
        response = m.changelist_view(request)
        self.assertEqual(response.context_data["cl"].search_fields, ("name", "age"))

    def test_pagination_page_range(self):
        """
        Regression tests for ticket #15653: ensure the number of pages
        generated for changelist views are correct.
        """
        # instantiating and setting up ChangeList object
        m = GroupAdmin(Group, custom_site)
        request = self.factory.get("/group/")
        request.user = self.superuser
        cl = m.get_changelist_instance(request)
        cl.list_per_page = 10

        ELLIPSIS = cl.paginator.ELLIPSIS
        for number, pages, expected in [
            (1, 1, []),
            (1, 2, [1, 2]),
            (6, 11, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
            (6, 12, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]),
            (6, 13, [1, 2, 3, 4, 5, 6, 7, 8, 9, ELLIPSIS, 12, 13]),
            (7, 12, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]),
            (7, 13, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),
            (7, 14, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ELLIPSIS, 13, 14]),
            (8, 13, [1, 2, ELLIPSIS, 5, 6, 7, 8, 9, 10, 11, 12, 13]),
            (8, 14, [1, 2, ELLIPSIS, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]),
            (8, 15, [1, 2, ELLIPSIS, 5, 6, 7, 8, 9, 10, 11, ELLIPSIS, 14, 15]),
        ]:
            with self.subTest(number=number, pages=pages):
                # assuming exactly `pages * cl.list_per_page` objects
                Group.objects.all().delete()
                for i in range(pages * cl.list_per_page):
                    Group.objects.create(name="test band")

                # setting page number and calculating page range
                cl.page_num = number
                cl.get_results(request)
                self.assertEqual(list(pagination(cl)["page_range"]), expected)

    def test_object_tools_displayed_no_add_permission(self):
        """
        When ModelAdmin.has_add_permission() returns False, the object-tools
        block is still shown.
        """
        superuser = self._create_superuser("superuser")
        m = EventAdmin(Event, custom_site)
        request = self._mocked_authenticated_request("/event/", superuser)
        self.assertFalse(m.has_add_permission(request))
        response = m.changelist_view(request)
        self.assertIn('<ul class="object-tools">', response.rendered_content)
        # The "Add" button inside the object-tools shouldn't appear.
        self.assertNotIn("Add ", response.rendered_content)

    def test_search_help_text(self):
        superuser = self._create_superuser("superuser")
        m = BandAdmin(Band, custom_site)
        # search_fields without search_help_text.
        m.search_fields = ["name"]
        request = self._mocked_authenticated_request("/band/", superuser)
        response = m.changelist_view(request)
        self.assertIsNone(response.context_data["cl"].search_help_text)
        self.assertNotContains(response, '<div class="help id="searchbar_helptext">')
        # search_fields with search_help_text.
        m.search_help_text = "Search help text"
        request = self._mocked_authenticated_request("/band/", superuser)
        response = m.changelist_view(request)
        self.assertEqual(
            response.context_data["cl"].search_help_text, "Search help text"
        )
        self.assertContains(
            response, '<div class="help" id="searchbar_helptext">Search help text</div>'
        )
        self.assertContains(
            response,
            '<input type="text" size="40" name="q" value="" id="searchbar" '
            'aria-describedby="searchbar_helptext">',
        )

    def test_search_role(self):
        """
        Tests the search functionality for the Band model in the admin interface.

        Verifies that the changelist view renders a search form with the role 'search' 
        when the search fields are properly configured. This ensures that the search 
        functionality is accessible and usable for administrators.

        The test checks for the presence of a specific HTML form element in the 
        response, confirming that the search form is correctly rendered with the 
        expected role attribute.
        """
        m = BandAdmin(Band, custom_site)
        m.search_fields = ["name"]
        request = self._mocked_authenticated_request("/band/", self.superuser)
        response = m.changelist_view(request)
        self.assertContains(
            response,
            '<form id="changelist-search" method="get" role="search">',
        )

    def test_search_bar_total_link_preserves_options(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:auth_user_changelist")
        for data, href in (
            ({"is_staff__exact": "0"}, "?"),
            ({"is_staff__exact": "0", IS_POPUP_VAR: "1"}, f"?{IS_POPUP_VAR}=1"),
            ({"is_staff__exact": "0", IS_FACETS_VAR: ""}, f"?{IS_FACETS_VAR}"),
            (
                {"is_staff__exact": "0", IS_POPUP_VAR: "1", IS_FACETS_VAR: ""},
                f"?{IS_POPUP_VAR}=1&{IS_FACETS_VAR}",
            ),
        ):
            with self.subTest(data=data):
                response = self.client.get(url, data=data)
                self.assertContains(
                    response, f'0 results (<a href="{href}">1 total</a>)'
                )

    def test_list_display_related_field(self):
        """

        Tests the display of related fields in the list view of the GrandChild admin interface.

        Verifies that the names of the parent and grandparent objects are correctly displayed
        in the changelist view of the GrandChild model. This ensures that the related fields
        are properly rendered and visible to users with appropriate permissions.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the parent or child names are not found in the response.

        """
        parent = Parent.objects.create(name="I am your father")
        child = Child.objects.create(name="I am your child", parent=parent)
        GrandChild.objects.create(name="I am your grandchild", parent=child)
        request = self._mocked_authenticated_request("/grandchild/", self.superuser)

        m = GrandChildAdmin(GrandChild, custom_site)
        response = m.changelist_view(request)
        self.assertContains(response, parent.name)
        self.assertContains(response, child.name)

    def test_list_display_related_field_null(self):
        """
        Tests that the changelist view of the GrandChildAdmin correctly displays null related fields. 

        Specifically, it verifies that when a GrandChild object has no parent and no grandparent, the corresponding fields in the changelist view are displayed with a \"-\" symbol, indicating the null or empty value. 

        This test ensures that the administration interface handles null related fields as expected, providing a correct representation of the data to the user.
        """
        GrandChild.objects.create(name="I am parentless", parent=None)
        request = self._mocked_authenticated_request("/grandchild/", self.superuser)

        m = GrandChildAdmin(GrandChild, custom_site)
        response = m.changelist_view(request)
        self.assertContains(response, '<td class="field-parent__name">-</td>')
        self.assertContains(response, '<td class="field-parent__parent__name">-</td>')

    def test_list_display_related_field_ordering(self):
        """

        Tests the ordering of related fields in the admin list display.

        This test case verifies that the ordering of related fields in the list display
        of a ModelAdmin instance works as expected. It creates two parent objects and
        two child objects, then tests that the list display of the child objects is
        ordered correctly by the parent's name when the 'o' query parameter is used.

        The test covers both ascending and descending ordering, ensuring that the
        administration interface behaves as expected when sorting related fields.

        """
        parent_a = Parent.objects.create(name="Alice")
        parent_z = Parent.objects.create(name="Zara")
        Child.objects.create(name="Alice's child", parent=parent_a)
        Child.objects.create(name="Zara's child", parent=parent_z)

        class ChildAdmin(admin.ModelAdmin):
            list_display = ["name", "parent__name"]
            list_per_page = 1

        m = ChildAdmin(Child, custom_site)

        # Order ascending.
        request = self._mocked_authenticated_request("/grandchild/?o=1", self.superuser)
        response = m.changelist_view(request)
        self.assertContains(response, parent_a.name)
        self.assertNotContains(response, parent_z.name)

        # Order descending.
        request = self._mocked_authenticated_request(
            "/grandchild/?o=-1", self.superuser
        )
        response = m.changelist_view(request)
        self.assertNotContains(response, parent_a.name)
        self.assertContains(response, parent_z.name)

    def test_list_display_related_field_ordering_fields(self):
        class ChildAdmin(admin.ModelAdmin):
            list_display = ["name", "parent__name"]
            ordering = ["parent__name"]

        m = ChildAdmin(Child, custom_site)
        request = self._mocked_authenticated_request("/", self.superuser)
        cl = m.get_changelist_instance(request)
        self.assertEqual(cl.get_ordering_field_columns(), {2: "asc"})


class GetAdminLogTests(TestCase):
    def test_custom_user_pk_not_named_id(self):
        """
        {% get_admin_log %} works if the user model's primary key isn't named
        'id'.
        """
        context = Context(
            {
                "user": CustomIdUser(),
                "log_entries": LogEntry.objects.all(),
            }
        )
        template = Template(
            "{% load log %}{% get_admin_log 10 as admin_log for_user user %}"
        )
        # This template tag just logs.
        self.assertEqual(template.render(context), "")

    def test_no_user(self):
        """{% get_admin_log %} works without specifying a user."""
        user = User(username="jondoe", password="secret", email="super@example.com")
        user.save()
        LogEntry.objects.log_actions(user.pk, [user], 1, single_object=True)
        context = Context({"log_entries": LogEntry.objects.all()})
        t = Template(
            "{% load log %}"
            "{% get_admin_log 100 as admin_log %}"
            "{% for entry in admin_log %}"
            "{{ entry|safe }}"
            "{% endfor %}"
        )
        self.assertEqual(t.render(context), "Added “jondoe”.")

    def test_missing_args(self):
        """
        Tests that the 'get_admin_log' template tag raises a TemplateSyntaxError when not provided with the required two arguments.
        """
        msg = "'get_admin_log' statements require two arguments"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            Template("{% load log %}{% get_admin_log 10 as %}")

    def test_non_integer_limit(self):
        msg = "First argument to 'get_admin_log' must be an integer"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            Template(
                '{% load log %}{% get_admin_log "10" as admin_log for_user user %}'
            )

    def test_without_as(self):
        """

        Tests that the 'get_admin_log' template tag raises a TemplateSyntaxError when 
        the second argument is not 'as'. This ensures that the template tag is used 
        correctly and the results are assigned to a variable, following the expected syntax.

        """
        msg = "Second argument to 'get_admin_log' must be 'as'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            Template("{% load log %}{% get_admin_log 10 ad admin_log for_user user %}")

    def test_without_for_user(self):
        """

        Tests that the 'get_admin_log' template tag raises a TemplateSyntaxError when the fourth argument is not 'for_user'.

        This test ensures that the template tag is used correctly and that an error is raised when the 'for_user' keyword is not provided as the fourth argument. The error message checks for the correct syntax error message being raised.

        """
        msg = "Fourth argument to 'get_admin_log' must be 'for_user'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            Template("{% load log %}{% get_admin_log 10 as admin_log foruser user %}")


@override_settings(ROOT_URLCONF="admin_changelist.urls")
class SeleniumTests(AdminSeleniumTestCase):
    available_apps = ["admin_changelist"] + AdminSeleniumTestCase.available_apps

    def setUp(self):
        User.objects.create_superuser(username="super", password="secret", email=None)

    def test_add_row_selection(self):
        """
        The status line for selected rows gets updated correctly (#22038).
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(self.live_server_url + reverse("admin:auth_user_changelist"))

        form_id = "#changelist-form"

        # Test amount of rows in the Changelist
        rows = self.selenium.find_elements(
            By.CSS_SELECTOR, "%s #result_list tbody tr" % form_id
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]

        selection_indicator = self.selenium.find_element(
            By.CSS_SELECTOR, "%s .action-counter" % form_id
        )
        all_selector = self.selenium.find_element(By.ID, "action-toggle")
        row_selector = self.selenium.find_element(
            By.CSS_SELECTOR,
            "%s #result_list tbody tr:first-child .action-select" % form_id,
        )

        # Test current selection
        self.assertEqual(selection_indicator.text, "0 of 1 selected")
        self.assertIs(all_selector.get_property("checked"), False)
        self.assertEqual(row.get_attribute("class"), "")

        # Select a row and check again
        row_selector.click()
        self.assertEqual(selection_indicator.text, "1 of 1 selected")
        self.assertIs(all_selector.get_property("checked"), True)
        self.assertEqual(row.get_attribute("class"), "selected")

        # Deselect a row and check again
        row_selector.click()
        self.assertEqual(selection_indicator.text, "0 of 1 selected")
        self.assertIs(all_selector.get_property("checked"), False)
        self.assertEqual(row.get_attribute("class"), "")

    def test_modifier_allows_multiple_section(self):
        """
        Selecting a row and then selecting another row whilst holding shift
        should select all rows in-between.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        Parent.objects.bulk_create([Parent(name="parent%d" % i) for i in range(5)])
        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )
        checkboxes = self.selenium.find_elements(
            By.CSS_SELECTOR, "tr input.action-select"
        )
        self.assertEqual(len(checkboxes), 5)
        for c in checkboxes:
            self.assertIs(c.get_property("checked"), False)
        # Check first row. Hold-shift and check next-to-last row.
        checkboxes[0].click()
        ActionChains(self.selenium).key_down(Keys.SHIFT).click(checkboxes[-2]).key_up(
            Keys.SHIFT
        ).perform()
        for c in checkboxes[:-2]:
            self.assertIs(c.get_property("checked"), True)
        self.assertIs(checkboxes[-1].get_property("checked"), False)

    def test_selection_counter_is_synced_when_page_is_shown(self):
        """
        Tests whether the selection counter in the admin changelist page remains synchronized 
        when the page is shown after navigating to another page and then returning.

        This test case checks that the selection counter accurately reflects the number of rows 
        selected after navigating away from the changelist page and then returning to it, 
        ensuring that the selection state is preserved and the counter is updated correctly.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(self.live_server_url + reverse("admin:auth_user_changelist"))

        form_id = "#changelist-form"
        first_row_checkbox_selector = (
            f"{form_id} #result_list tbody tr:first-child .action-select"
        )
        selection_indicator_selector = f"{form_id} .action-counter"
        selection_indicator = self.selenium.find_element(
            By.CSS_SELECTOR, selection_indicator_selector
        )
        row_checkbox = self.selenium.find_element(
            By.CSS_SELECTOR, first_row_checkbox_selector
        )
        # Select a row.
        row_checkbox.click()
        self.assertEqual(selection_indicator.text, "1 of 1 selected")
        # Go to another page and get back.
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )
        self.selenium.back()
        # The selection indicator is synced with the selected checkboxes.
        selection_indicator = self.selenium.find_element(
            By.CSS_SELECTOR, selection_indicator_selector
        )
        row_checkbox = self.selenium.find_element(
            By.CSS_SELECTOR, first_row_checkbox_selector
        )
        selected_rows = 1 if row_checkbox.is_selected() else 0
        self.assertEqual(selection_indicator.text, f"{selected_rows} of 1 selected")

    def test_select_all_across_pages(self):
        """

        Tests the functionality of selecting all items across pages in the admin changelist view.

        This test case covers the following scenarios:
        - Initial state of the selection indicators and buttons
        - Selecting all items on the current page
        - Confirming selection across all pages
        - Clearing the selection

        It verifies the correct display and behavior of various UI elements, including:
        - Selection indicator
        - Select all checkbox
        - Question button
        - Clear button
        - Select across pages hidden inputs

        The test ensures that the selection functionality works as expected, including selecting and deselecting all items across multiple pages.

        """
        from selenium.webdriver.common.by import By

        Parent.objects.bulk_create([Parent(name="parent%d" % i) for i in range(101)])
        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )

        selection_indicator = self.selenium.find_element(
            By.CSS_SELECTOR, ".action-counter"
        )
        select_all_indicator = self.selenium.find_element(
            By.CSS_SELECTOR, ".actions .all"
        )
        question = self.selenium.find_element(By.CSS_SELECTOR, ".actions > .question")
        clear = self.selenium.find_element(By.CSS_SELECTOR, ".actions > .clear")
        select_all = self.selenium.find_element(By.ID, "action-toggle")
        select_across = self.selenium.find_elements(By.NAME, "select_across")

        self.assertIs(question.is_displayed(), False)
        self.assertIs(clear.is_displayed(), False)
        self.assertIs(select_all.get_property("checked"), False)
        for hidden_input in select_across:
            self.assertEqual(hidden_input.get_property("value"), "0")
        self.assertIs(selection_indicator.is_displayed(), True)
        self.assertEqual(selection_indicator.text, "0 of 100 selected")
        self.assertIs(select_all_indicator.is_displayed(), False)

        select_all.click()
        self.assertIs(question.is_displayed(), True)
        self.assertIs(clear.is_displayed(), False)
        self.assertIs(select_all.get_property("checked"), True)
        for hidden_input in select_across:
            self.assertEqual(hidden_input.get_property("value"), "0")
        self.assertIs(selection_indicator.is_displayed(), True)
        self.assertEqual(selection_indicator.text, "100 of 100 selected")
        self.assertIs(select_all_indicator.is_displayed(), False)

        question.click()
        self.assertIs(question.is_displayed(), False)
        self.assertIs(clear.is_displayed(), True)
        self.assertIs(select_all.get_property("checked"), True)
        for hidden_input in select_across:
            self.assertEqual(hidden_input.get_property("value"), "1")
        self.assertIs(selection_indicator.is_displayed(), False)
        self.assertIs(select_all_indicator.is_displayed(), True)

        clear.click()
        self.assertIs(question.is_displayed(), False)
        self.assertIs(clear.is_displayed(), False)
        self.assertIs(select_all.get_property("checked"), False)
        for hidden_input in select_across:
            self.assertEqual(hidden_input.get_property("value"), "0")
        self.assertIs(selection_indicator.is_displayed(), True)
        self.assertEqual(selection_indicator.text, "0 of 100 selected")
        self.assertIs(select_all_indicator.is_displayed(), False)

    def test_actions_warn_on_pending_edits(self):
        """

        Tests that a warning is displayed when attempting to perform an action in the admin interface 
        while there are pending edits to individual fields. 

        This test scenario covers the case where a user makes changes to a field in the admin change list 
        page, then attempts to run an action without saving those changes. It verifies that a warning 
        prompt is displayed to the user, alerting them that their unsaved changes will be lost if the action 
        is performed.

        """
        from selenium.webdriver.common.by import By

        Parent.objects.create(name="foo")

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )

        name_input = self.selenium.find_element(By.ID, "id_form-0-name")
        name_input.clear()
        name_input.send_keys("bar")
        self.selenium.find_element(By.ID, "action-toggle").click()
        self.selenium.find_element(By.NAME, "index").click()  # Go
        alert = self.selenium.switch_to.alert
        try:
            self.assertEqual(
                alert.text,
                "You have unsaved changes on individual editable fields. If you "
                "run an action, your unsaved changes will be lost.",
            )
        finally:
            alert.dismiss()

    def test_save_with_changes_warns_on_pending_action(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select

        Parent.objects.create(name="parent")

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )

        name_input = self.selenium.find_element(By.ID, "id_form-0-name")
        name_input.clear()
        name_input.send_keys("other name")
        Select(self.selenium.find_element(By.NAME, "action")).select_by_value(
            "delete_selected"
        )
        self.selenium.find_element(By.NAME, "_save").click()
        alert = self.selenium.switch_to.alert
        try:
            self.assertEqual(
                alert.text,
                "You have selected an action, but you haven’t saved your "
                "changes to individual fields yet. Please click OK to save. "
                "You’ll need to re-run the action.",
            )
        finally:
            alert.dismiss()

    def test_save_without_changes_warns_on_pending_action(self):
        """
        Tests that attempting to save a changelist in the admin interface without making any changes, when a pending action is selected, triggers an alert warning the user they likely intended to use the 'Go' button instead of 'Save'.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import Select

        Parent.objects.create(name="parent")

        self.admin_login(username="super", password="secret")
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_parent_changelist")
        )

        Select(self.selenium.find_element(By.NAME, "action")).select_by_value(
            "delete_selected"
        )
        self.selenium.find_element(By.NAME, "_save").click()
        alert = self.selenium.switch_to.alert
        try:
            self.assertEqual(
                alert.text,
                "You have selected an action, and you haven’t made any "
                "changes on individual fields. You’re probably looking for "
                "the Go button rather than the Save button.",
            )
        finally:
            alert.dismiss()

    def test_collapse_filters(self):
        """
        Tests that filter sections on admin changelist pages can be collapsed and that the state of these sections is persisted across page reloads. 

        The test logs into the admin interface, navigates to the user changelist page, and verifies that all filter sections are initially expanded. 

        It then collapses two filter sections, reloads the page, and checks that the collapsed state is preserved for the specified sections, while ensuring that other sections remain expanded.

        The test also verifies that filter state is preserved when navigating to a different admin changelist page and back.
        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        self.selenium.get(self.live_server_url + reverse("admin:auth_user_changelist"))

        # The UserAdmin has 3 field filters by default: "staff status",
        # "superuser status", and "active".
        details = self.selenium.find_elements(By.CSS_SELECTOR, "details")
        # All filters are opened at first.
        for detail in details:
            self.assertTrue(detail.get_attribute("open"))
        # Collapse "staff' and "superuser" filters.
        for detail in details[:2]:
            summary = detail.find_element(By.CSS_SELECTOR, "summary")
            summary.click()
            self.assertFalse(detail.get_attribute("open"))
        # Filters are in the same state after refresh.
        self.selenium.refresh()
        self.assertFalse(
            self.selenium.find_element(
                By.CSS_SELECTOR, "[data-filter-title='staff status']"
            ).get_attribute("open")
        )
        self.assertFalse(
            self.selenium.find_element(
                By.CSS_SELECTOR, "[data-filter-title='superuser status']"
            ).get_attribute("open")
        )
        self.assertTrue(
            self.selenium.find_element(
                By.CSS_SELECTOR, "[data-filter-title='active']"
            ).get_attribute("open")
        )
        # Collapse a filter on another view (Bands).
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_band_changelist")
        )
        self.selenium.find_element(By.CSS_SELECTOR, "summary").click()
        # Go to Users view and then, back again to Bands view.
        self.selenium.get(self.live_server_url + reverse("admin:auth_user_changelist"))
        self.selenium.get(
            self.live_server_url + reverse("admin:admin_changelist_band_changelist")
        )
        # The filter remains in the same state.
        self.assertFalse(
            self.selenium.find_element(
                By.CSS_SELECTOR,
                "[data-filter-title='number of members']",
            ).get_attribute("open")
        )

    def test_collapse_filter_with_unescaped_title(self):
        """

        Tests the collapsing functionality of a filter with an unescaped title in the admin changelist.

        The test logs in as an admin, navigates to the changelist page for proxy users,
        and locates a filter with the title 'It's OK'. It then collapses the filter and verifies that it remains closed
        after a page refresh, ensuring that the filter's state is persisted correctly.

        """
        from selenium.webdriver.common.by import By

        self.admin_login(username="super", password="secret")
        changelist_url = reverse("admin:admin_changelist_proxyuser_changelist")
        self.selenium.get(self.live_server_url + changelist_url)
        # Title is escaped.
        filter_title = self.selenium.find_element(
            By.CSS_SELECTOR, "[data-filter-title='It\\'s OK']"
        )
        filter_title.find_element(By.CSS_SELECTOR, "summary").click()
        self.assertFalse(filter_title.get_attribute("open"))
        # Filter is in the same state after refresh.
        self.selenium.refresh()
        self.assertFalse(
            self.selenium.find_element(
                By.CSS_SELECTOR, "[data-filter-title='It\\'s OK']"
            ).get_attribute("open")
        )

    def test_list_display_ordering(self):
        from selenium.webdriver.common.by import By

        parent_a = Parent.objects.create(name="Parent A")
        child_l = Child.objects.create(name="Child L", parent=None)
        child_m = Child.objects.create(name="Child M", parent=parent_a)
        GrandChild.objects.create(name="Grandchild X", parent=child_m)
        GrandChild.objects.create(name="Grandchild Y", parent=child_l)
        GrandChild.objects.create(name="Grandchild Z", parent=None)

        self.admin_login(username="super", password="secret")
        changelist_url = reverse("admin:admin_changelist_grandchild_changelist")
        self.selenium.get(self.live_server_url + changelist_url)

        def find_result_row_texts():
            table = self.selenium.find_element(By.ID, "result_list")
            # Drop header from the result list
            return [row.text for row in table.find_elements(By.TAG_NAME, "tr")][1:]

        def expected_from_queryset(qs):
            return [
                " ".join("-" if i is None else i for i in item)
                for item in qs.values_list(
                    "name", "parent__name", "parent__parent__name"
                )
            ]

        cases = [
            # Order ascending by `name`.
            ("th.sortable.column-name", ("name",)),
            # Order descending by `name`.
            ("th.sortable.column-name", ("-name",)),
            # Order ascending by `parent__name`.
            ("th.sortable.column-parent__name", ("parent__name", "-name")),
            # Order descending by `parent__name`.
            ("th.sortable.column-parent__name", ("-parent__name", "-name")),
            # Order ascending by `parent__parent__name`.
            (
                "th.sortable.column-parent__parent__name",
                ("parent__parent__name", "-parent__name", "-name"),
            ),
            # Order descending by `parent__parent__name`.
            (
                "th.sortable.column-parent__parent__name",
                ("-parent__parent__name", "-parent__name", "-name"),
            ),
        ]
        for css_selector, ordering in cases:
            with self.subTest(ordering=ordering):
                self.selenium.find_element(By.CSS_SELECTOR, css_selector).click()
                expected = expected_from_queryset(
                    GrandChild.objects.all().order_by(*ordering)
                )
                self.assertEqual(find_result_row_texts(), expected)
