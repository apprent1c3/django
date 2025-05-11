from django.contrib import admin
from django.contrib.auth.models import User as AuthUser
from django.contrib.contenttypes.models import ContentType
from django.core import checks, management
from django.db import DEFAULT_DB_ALIAS, models
from django.db.models import signals
from django.test import TestCase, override_settings
from django.test.utils import isolate_apps
from django.urls import reverse

from .admin import admin as force_admin_model_registration  # NOQA
from .models import (
    Abstract,
    BaseUser,
    Bug,
    Country,
    Improvement,
    Issue,
    LowerStatusPerson,
    MultiUserProxy,
    MyPerson,
    MyPersonProxy,
    OtherPerson,
    Person,
    ProxyBug,
    ProxyImprovement,
    ProxyProxyBug,
    ProxyTrackerUser,
    State,
    StateProxy,
    StatusPerson,
    TrackerUser,
    User,
    UserProxy,
    UserProxyProxy,
)


class ProxyModelTests(TestCase):
    def test_same_manager_queries(self):
        """
        The MyPerson model should be generating the same database queries as
        the Person model (when the same manager is used in each case).
        """
        my_person_sql = (
            MyPerson.other.all().query.get_compiler(DEFAULT_DB_ALIAS).as_sql()
        )
        person_sql = (
            Person.objects.order_by("name")
            .query.get_compiler(DEFAULT_DB_ALIAS)
            .as_sql()
        )
        self.assertEqual(my_person_sql, person_sql)

    def test_inheritance_new_table(self):
        """
        The StatusPerson models should have its own table (it's using ORM-level
        inheritance).
        """
        sp_sql = (
            StatusPerson.objects.all().query.get_compiler(DEFAULT_DB_ALIAS).as_sql()
        )
        p_sql = Person.objects.all().query.get_compiler(DEFAULT_DB_ALIAS).as_sql()
        self.assertNotEqual(sp_sql, p_sql)

    def test_basic_proxy(self):
        """

        Verifies that creating a Person instance makes it accessible through the MyPerson proxy, 
        while also testing the consistency of data between the two and a specific property of the MyPerson instance.

        """
        person = Person.objects.create(name="Foo McBar")
        self.assertEqual(len(Person.objects.all()), 1)
        self.assertEqual(len(MyPerson.objects.all()), 1)
        self.assertEqual(MyPerson.objects.get(name="Foo McBar").id, person.id)
        self.assertFalse(MyPerson.objects.get(id=person.id).has_special_name())

    def test_no_proxy(self):
        """
        Person is not proxied by StatusPerson subclass.
        """
        Person.objects.create(name="Foo McBar")
        self.assertEqual(list(StatusPerson.objects.all()), [])

    def test_basic_proxy_reverse(self):
        """

            Verifies that proxy models are correctly reflected in the database,
            ensuring that instances of a proxy model are also accessible as instances
            of the original model.

        """
        MyPerson.objects.create(name="Bazza del Frob")
        self.assertEqual(len(MyPerson.objects.all()), 1)
        self.assertEqual(len(Person.objects.all()), 1)

        LowerStatusPerson.objects.create(status="low", name="homer")
        lsps = [lsp.name for lsp in LowerStatusPerson.objects.all()]
        self.assertEqual(lsps, ["homer"])

    def test_correct_type_proxy_of_proxy(self):
        """
        Tests that proxy models return results of the correct type when querying a proxy of a proxy, ensuring proper data retrieval and sorting.
        """
        Person.objects.create(name="Foo McBar")
        MyPerson.objects.create(name="Bazza del Frob")
        LowerStatusPerson.objects.create(status="low", name="homer")
        pp = sorted(mpp.name for mpp in MyPersonProxy.objects.all())
        self.assertEqual(pp, ["Bazza del Frob", "Foo McBar", "homer"])

    def test_proxy_included_in_ancestors(self):
        """
        Tests that proxy models are properly included in the ancestors for a model, 
        ensuring that exceptions such as DoesNotExist and MultipleObjectsReturned are 
        raised correctly when querying the proxy models.
        """
        Person.objects.create(name="Foo McBar")
        MyPerson.objects.create(name="Bazza del Frob")
        LowerStatusPerson.objects.create(status="low", name="homer")
        max_id = Person.objects.aggregate(max_id=models.Max("id"))["max_id"]

        with self.assertRaises(Person.DoesNotExist):
            MyPersonProxy.objects.get(name="Zathras")
        with self.assertRaises(Person.MultipleObjectsReturned):
            MyPersonProxy.objects.get(id__lt=max_id + 1)
        with self.assertRaises(Person.DoesNotExist):
            StatusPerson.objects.get(name="Zathras")

        StatusPerson.objects.create(name="Bazza Jr.")
        StatusPerson.objects.create(name="Foo Jr.")
        max_id = Person.objects.aggregate(max_id=models.Max("id"))["max_id"]

        with self.assertRaises(Person.MultipleObjectsReturned):
            StatusPerson.objects.get(id__lt=max_id + 1)

    def test_abstract_base_with_model_fields(self):
        """
        Tests that defining an abstract base class with model fields is not allowed for proxy models, ensuring that a TypeError is raised with a descriptive error message.
        """
        msg = (
            "Abstract base class containing model fields not permitted for proxy model "
            "'NoAbstract'."
        )
        with self.assertRaisesMessage(TypeError, msg):

            class NoAbstract(Abstract):
                class Meta:
                    proxy = True

    def test_too_many_concrete_classes(self):
        """
        Tests that a proxy model cannot have more than one non-abstract model base class, ensuring proper inheritance configuration.
        """
        msg = (
            "Proxy model 'TooManyBases' has more than one non-abstract model base "
            "class."
        )
        with self.assertRaisesMessage(TypeError, msg):

            class TooManyBases(User, Person):
                class Meta:
                    proxy = True

    def test_no_base_classes(self):
        """
        Tests that a ``TypeError`` is raised when creating a proxy model without a non-abstract model base class.
        """
        msg = "Proxy model 'NoBaseClasses' has no non-abstract model base class."
        with self.assertRaisesMessage(TypeError, msg):

            class NoBaseClasses(models.Model):
                class Meta:
                    proxy = True

    @isolate_apps("proxy_models")
    def test_new_fields(self):
        """
        Tests that a model proxy cannot contain new model fields. Verifies that Django's model check for proxy models correctly identifies and reports the presence of new fields.
        """
        class NoNewFields(Person):
            newfield = models.BooleanField()

            class Meta:
                proxy = True

        errors = NoNewFields.check()
        expected = [
            checks.Error(
                "Proxy model 'NoNewFields' contains model fields.",
                id="models.E017",
            )
        ]
        self.assertEqual(errors, expected)

    @override_settings(TEST_SWAPPABLE_MODEL="proxy_models.AlternateModel")
    @isolate_apps("proxy_models")
    def test_swappable(self):
        """
        Tests that using a swappable model as a base class for a proxy model raises an error.
        """
        class SwappableModel(models.Model):
            class Meta:
                swappable = "TEST_SWAPPABLE_MODEL"

        class AlternateModel(models.Model):
            pass

        # You can't proxy a swapped model
        with self.assertRaises(TypeError):

            class ProxyModel(SwappableModel):
                class Meta:
                    proxy = True

    def test_myperson_manager(self):
        """
        Tests the MyPerson manager to ensure it returns a filtered list of Person objects, excluding 'wilma'. Verifies the consistency of the custom manager and the default manager.
        """
        Person.objects.create(name="fred")
        Person.objects.create(name="wilma")
        Person.objects.create(name="barney")

        resp = [p.name for p in MyPerson.objects.all()]
        self.assertEqual(resp, ["barney", "fred"])

        resp = [p.name for p in MyPerson._default_manager.all()]
        self.assertEqual(resp, ["barney", "fred"])

    def test_otherperson_manager(self):
        """
        Tests the OtherPerson manager to ensure it correctly filters and excludes Person objects based on specific conditions, verifying that the default manager, custom manager, and exclusion manager return the expected sets of people.
        """
        Person.objects.create(name="fred")
        Person.objects.create(name="wilma")
        Person.objects.create(name="barney")

        resp = [p.name for p in OtherPerson.objects.all()]
        self.assertEqual(resp, ["barney", "wilma"])

        resp = [p.name for p in OtherPerson.excluder.all()]
        self.assertEqual(resp, ["barney", "fred"])

        resp = [p.name for p in OtherPerson._default_manager.all()]
        self.assertEqual(resp, ["barney", "wilma"])

    def test_permissions_created(self):
        from django.contrib.auth.models import Permission

        Permission.objects.get(name="May display users information")

    def test_proxy_model_signals(self):
        """

            Verifies the correctness of save signals for proxy models.

            This test checks that pre and post save signals are emitted correctly 
            for both regular and proxy models, ensuring that the signals are 
            triggered as expected when instances of these models are saved.

        """
        output = []

        def make_handler(model, event):
            def _handler(*args, **kwargs):
                output.append("%s %s save" % (model, event))

            return _handler

        h1 = make_handler("MyPerson", "pre")
        h2 = make_handler("MyPerson", "post")
        h3 = make_handler("Person", "pre")
        h4 = make_handler("Person", "post")

        signals.pre_save.connect(h1, sender=MyPerson)
        signals.post_save.connect(h2, sender=MyPerson)
        signals.pre_save.connect(h3, sender=Person)
        signals.post_save.connect(h4, sender=Person)

        MyPerson.objects.create(name="dino")
        self.assertEqual(output, ["MyPerson pre save", "MyPerson post save"])

        output = []

        h5 = make_handler("MyPersonProxy", "pre")
        h6 = make_handler("MyPersonProxy", "post")

        signals.pre_save.connect(h5, sender=MyPersonProxy)
        signals.post_save.connect(h6, sender=MyPersonProxy)

        MyPersonProxy.objects.create(name="pebbles")

        self.assertEqual(output, ["MyPersonProxy pre save", "MyPersonProxy post save"])

        signals.pre_save.disconnect(h1, sender=MyPerson)
        signals.post_save.disconnect(h2, sender=MyPerson)
        signals.pre_save.disconnect(h3, sender=Person)
        signals.post_save.disconnect(h4, sender=Person)
        signals.pre_save.disconnect(h5, sender=MyPersonProxy)
        signals.post_save.disconnect(h6, sender=MyPersonProxy)

    def test_content_type(self):
        ctype = ContentType.objects.get_for_model
        self.assertIs(ctype(Person), ctype(OtherPerson))

    def test_user_proxy_models(self):
        """
        Tests the correctness of user proxy models by creating a user, 
        then verifying that the user's name is correctly retrieved through 
        the User, UserProxy, UserProxyProxy, and MultiUserProxy models.
        """
        User.objects.create(name="Bruce")

        resp = [u.name for u in User.objects.all()]
        self.assertEqual(resp, ["Bruce"])

        resp = [u.name for u in UserProxy.objects.all()]
        self.assertEqual(resp, ["Bruce"])

        resp = [u.name for u in UserProxyProxy.objects.all()]
        self.assertEqual(resp, ["Bruce"])

        self.assertEqual([u.name for u in MultiUserProxy.objects.all()], ["Bruce"])

    def test_proxy_for_model(self):
        self.assertEqual(UserProxy, UserProxyProxy._meta.proxy_for_model)

    def test_concrete_model(self):
        self.assertEqual(User, UserProxyProxy._meta.concrete_model)

    def test_proxy_delete(self):
        """
        Verifies that proxy objects can be deleted from the database, ensuring the deletion operation successfully removes the object without affecting other related records.
        """
        User.objects.create(name="Bruce")
        u2 = UserProxy.objects.create(name="George")

        resp = [u.name for u in UserProxy.objects.all()]
        self.assertEqual(resp, ["Bruce", "George"])

        u2.delete()

        resp = [u.name for u in UserProxy.objects.all()]
        self.assertEqual(resp, ["Bruce"])

    def test_proxy_update(self):
        """

        Tests that updating a user's information through the UserProxy model 
        successfully updates the underlying User object in a single database query.

        """
        user = User.objects.create(name="Bruce")
        with self.assertNumQueries(1):
            UserProxy.objects.filter(id=user.id).update(name="George")
        user.refresh_from_db()
        self.assertEqual(user.name, "George")

    def test_select_related(self):
        """
        Tests that select_related() can be used to include related models in querysets for both the original State model and the StateProxy model, ensuring correct results are returned.
        """
        country = Country.objects.create(name="Australia")
        State.objects.create(name="New South Wales", country=country)

        resp = [s.name for s in State.objects.select_related()]
        self.assertEqual(resp, ["New South Wales"])

        resp = [s.name for s in StateProxy.objects.select_related()]
        self.assertEqual(resp, ["New South Wales"])

        self.assertEqual(
            StateProxy.objects.get(name="New South Wales").name, "New South Wales"
        )

        resp = StateProxy.objects.select_related().get(name="New South Wales")
        self.assertEqual(resp.name, "New South Wales")

    def test_filter_proxy_relation_reverse(self):
        """
        Tests the relationship between trackers, users and proxy users through issues, verifying that 
        filter operations on the proxy and actual user models produce the expected results.
        """
        tu = TrackerUser.objects.create(name="Contributor", status="contrib")
        ptu = ProxyTrackerUser.objects.get()
        issue = Issue.objects.create(assignee=tu)
        self.assertEqual(tu.issues.get(), issue)
        self.assertEqual(ptu.issues.get(), issue)
        self.assertSequenceEqual(TrackerUser.objects.filter(issues=issue), [tu])
        self.assertSequenceEqual(ProxyTrackerUser.objects.filter(issues=issue), [ptu])

    def test_proxy_bug(self):
        """
        Tests the correct functioning of proxy objects for bugs, including their ability to load related objects and represent themselves correctly. 

        Verifies that ProxyBug, ProxyProxyBug, and ProxyImprovement instances are properly retrieved and their string representations match the expected format. 

        Covers various retrieval scenarios, such as filtering by version and selecting related objects, and ensures the integrity of associated data, including bug assignments and improvement associations.
        """
        contributor = ProxyTrackerUser.objects.create(
            name="Contributor", status="contrib"
        )
        someone = BaseUser.objects.create(name="Someone")
        Bug.objects.create(
            summary="fix this",
            version="1.1beta",
            assignee=contributor,
            reporter=someone,
        )
        pcontributor = ProxyTrackerUser.objects.create(
            name="OtherContributor", status="proxy"
        )
        Improvement.objects.create(
            summary="improve that",
            version="1.1beta",
            assignee=contributor,
            reporter=pcontributor,
            associated_bug=ProxyProxyBug.objects.all()[0],
        )

        # Related field filter on proxy
        resp = ProxyBug.objects.get(version__icontains="beta")
        self.assertEqual(repr(resp), "<ProxyBug: ProxyBug:fix this>")

        # Select related + filter on proxy
        resp = ProxyBug.objects.select_related().get(version__icontains="beta")
        self.assertEqual(repr(resp), "<ProxyBug: ProxyBug:fix this>")

        # Proxy of proxy, select_related + filter
        resp = ProxyProxyBug.objects.select_related().get(version__icontains="beta")
        self.assertEqual(repr(resp), "<ProxyProxyBug: ProxyProxyBug:fix this>")

        # Select related + filter on a related proxy field
        resp = ProxyImprovement.objects.select_related().get(
            reporter__name__icontains="butor"
        )
        self.assertEqual(
            repr(resp), "<ProxyImprovement: ProxyImprovement:improve that>"
        )

        # Select related + filter on a related proxy of proxy field
        resp = ProxyImprovement.objects.select_related().get(
            associated_bug__summary__icontains="fix"
        )
        self.assertEqual(
            repr(resp), "<ProxyImprovement: ProxyImprovement:improve that>"
        )

    def test_proxy_load_from_fixture(self):
        management.call_command("loaddata", "mypeople.json", verbosity=0)
        p = MyPerson.objects.get(pk=100)
        self.assertEqual(p.name, "Elvis Presley")

    def test_select_related_only(self):
        user = ProxyTrackerUser.objects.create(name="Joe Doe", status="test")
        issue = Issue.objects.create(summary="New issue", assignee=user)
        qs = Issue.objects.select_related("assignee").only("assignee__status")
        self.assertEqual(qs.get(), issue)

    def test_eq(self):
        self.assertEqual(MyPerson(id=100), Person(id=100))


@override_settings(ROOT_URLCONF="proxy_models.urls")
class ProxyModelAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = AuthUser.objects.create(is_superuser=True, is_staff=True)
        cls.tu1 = ProxyTrackerUser.objects.create(name="Django Pony", status="emperor")
        cls.i1 = Issue.objects.create(summary="Pony's Issue", assignee=cls.tu1)

    def test_cascade_delete_proxy_model_admin_warning(self):
        """

        Tests whether the admin interface correctly issues a warning when attempting to delete a proxy model instance 
        that has cascade delete relationships, specifically referencing concrete models and related objects.

        """
        tracker_user = TrackerUser.objects.all()[0]
        base_user = BaseUser.objects.all()[0]
        issue = Issue.objects.all()[0]
        with self.assertNumQueries(6):
            collector = admin.utils.NestedObjects("default")
            collector.collect(ProxyTrackerUser.objects.all())
        self.assertIn(tracker_user, collector.edges.get(None, ()))
        self.assertIn(base_user, collector.edges.get(None, ()))
        self.assertIn(issue, collector.edges.get(tracker_user, ()))

    def test_delete_str_in_model_admin(self):
        """
        Tests the string representation of a model instance shown on the admin delete page, ensuring it correctly displays for both regular and proxy models.
        """
        user = TrackerUser.objects.get(name="Django Pony")
        proxy = ProxyTrackerUser.objects.get(name="Django Pony")

        user_str = 'Tracker user: <a href="%s">%s</a>' % (
            reverse("admin_proxy:proxy_models_trackeruser_change", args=(user.pk,)),
            user,
        )
        proxy_str = 'Proxy tracker user: <a href="%s">%s</a>' % (
            reverse(
                "admin_proxy:proxy_models_proxytrackeruser_change", args=(proxy.pk,)
            ),
            proxy,
        )

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin_proxy:proxy_models_trackeruser_delete", args=(user.pk,))
        )
        delete_str = response.context["deleted_objects"][0]
        self.assertEqual(delete_str, user_str)
        response = self.client.get(
            reverse(
                "admin_proxy:proxy_models_proxytrackeruser_delete", args=(proxy.pk,)
            )
        )
        delete_str = response.context["deleted_objects"][0]
        self.assertEqual(delete_str, proxy_str)
