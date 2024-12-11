import inspect
import threading
from datetime import datetime, timedelta
from unittest import mock

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import (
    DEFAULT_DB_ALIAS,
    DatabaseError,
    connection,
    connections,
    models,
    transaction,
)
from django.db.models.manager import BaseManager
from django.db.models.query import MAX_GET_RESULTS, EmptyQuerySet
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext, ignore_warnings
from django.utils.connection import ConnectionDoesNotExist
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.translation import gettext_lazy

from .models import (
    Article,
    ArticleSelectOnSave,
    ChildPrimaryKeyWithDefault,
    FeaturedArticle,
    PrimaryKeyWithDbDefault,
    PrimaryKeyWithDefault,
    SelfRef,
)


class ModelInstanceCreationTests(TestCase):
    def test_object_is_not_written_to_database_until_save_was_called(self):
        """
        Tests that an object is not persisted to the database until the save method is explicitly called.

        Verifies the object's id remains null and the database does not contain the object before save is called.
        After save is called, confirms the object's id is populated and the object exists in the database.
        """
        a = Article(
            id=None,
            headline="Parrot programs in Python",
            pub_date=datetime(2005, 7, 28),
        )
        self.assertIsNone(a.id)
        self.assertEqual(Article.objects.count(), 0)

        # Save it into the database. You have to call save() explicitly.
        a.save()
        self.assertIsNotNone(a.id)
        self.assertEqual(Article.objects.count(), 1)

    def test_can_initialize_model_instance_using_positional_arguments(self):
        """
        You can initialize a model instance using positional arguments,
        which should match the field order as defined in the model.
        """
        a = Article(None, "Second article", datetime(2005, 7, 29))
        a.save()

        self.assertEqual(a.headline, "Second article")
        self.assertEqual(a.pub_date, datetime(2005, 7, 29, 0, 0))

    def test_can_create_instance_using_kwargs(self):
        """
        Tests that an instance of Article can be successfully created using keyword arguments.

        This test case verifies that an Article object can be instantiated with the required attributes (headline and pub_date) and saved, 
        and that the attributes are correctly set and persisted.

        The test also checks that the default time component of the pub_date is correctly set to midnight (00:00) when not explicitly provided. 

        The expected outcome is that the created Article instance has the specified headline and pub_date, confirming that the instantiation 
        and saving process works as intended for Article objects created using keyword arguments.
        """
        a = Article(
            id=None,
            headline="Third article",
            pub_date=datetime(2005, 7, 30),
        )
        a.save()
        self.assertEqual(a.headline, "Third article")
        self.assertEqual(a.pub_date, datetime(2005, 7, 30, 0, 0))

    def test_autofields_generate_different_values_for_each_instance(self):
        """
        Tests that the autofields generate different values for each instance of a model.

        This test case verifies that when multiple instances of the same model are created,
        they are assigned unique identifier values, ensuring data integrity and preventing
        overwrites. The test creates multiple instances of the Article model with the same
        attributes and checks that their autofields (in this case, the 'id' field) have distinct values.
        """
        a1 = Article.objects.create(
            headline="First", pub_date=datetime(2005, 7, 30, 0, 0)
        )
        a2 = Article.objects.create(
            headline="First", pub_date=datetime(2005, 7, 30, 0, 0)
        )
        a3 = Article.objects.create(
            headline="First", pub_date=datetime(2005, 7, 30, 0, 0)
        )
        self.assertNotEqual(a3.id, a1.id)
        self.assertNotEqual(a3.id, a2.id)

    def test_can_mix_and_match_position_and_kwargs(self):
        # You can also mix and match position and keyword arguments, but
        # be sure not to duplicate field information.
        """
        Tests the ability to mix and match positional and keyword arguments when creating an Article instance. Verifies that the article's properties are correctly set and saved, ensuring that the headline is correctly assigned and retrieved.
        """
        a = Article(None, "Fourth article", pub_date=datetime(2005, 7, 31))
        a.save()
        self.assertEqual(a.headline, "Fourth article")

    def test_positional_and_keyword_args_for_the_same_field(self):
        msg = "Article() got both positional and keyword arguments for field '%s'."
        with self.assertRaisesMessage(TypeError, msg % "headline"):
            Article(None, "Fifth article", headline="Other headline.")
        with self.assertRaisesMessage(TypeError, msg % "headline"):
            Article(None, "Sixth article", headline="")
        with self.assertRaisesMessage(TypeError, msg % "pub_date"):
            Article(None, "Seventh article", datetime(2021, 3, 1), pub_date=None)

    def test_cannot_create_instance_with_invalid_kwargs(self):
        msg = "Article() got unexpected keyword arguments: 'foo'"
        with self.assertRaisesMessage(TypeError, msg):
            Article(
                id=None,
                headline="Some headline",
                pub_date=datetime(2005, 7, 31),
                foo="bar",
            )
        msg = "Article() got unexpected keyword arguments: 'foo', 'bar'"
        with self.assertRaisesMessage(TypeError, msg):
            Article(
                id=None,
                headline="Some headline",
                pub_date=datetime(2005, 7, 31),
                foo="bar",
                bar="baz",
            )

    def test_can_leave_off_value_for_autofield_and_it_gets_value_on_save(self):
        """
        You can leave off the value for an AutoField when creating an
        object, because it'll get filled in automatically when you save().
        """
        a = Article(headline="Article 5", pub_date=datetime(2005, 7, 31))
        a.save()
        self.assertEqual(a.headline, "Article 5")
        self.assertIsNotNone(a.id)

    def test_leaving_off_a_field_with_default_set_the_default_will_be_saved(self):
        """

        Verifies that when a field with a default value is not explicitly set, the default value is saved to the database.

        This test case ensures that the default value of an object's attribute is correctly persisted when the object is saved, even if the attribute is not explicitly assigned a value.

        """
        a = Article(pub_date=datetime(2005, 7, 31))
        a.save()
        self.assertEqual(a.headline, "Default headline")

    def test_for_datetimefields_saves_as_much_precision_as_was_given(self):
        """as much precision in *seconds*"""
        a1 = Article(
            headline="Article 7",
            pub_date=datetime(2005, 7, 31, 12, 30),
        )
        a1.save()
        self.assertEqual(
            Article.objects.get(id__exact=a1.id).pub_date, datetime(2005, 7, 31, 12, 30)
        )

        a2 = Article(
            headline="Article 8",
            pub_date=datetime(2005, 7, 31, 12, 30, 45),
        )
        a2.save()
        self.assertEqual(
            Article.objects.get(id__exact=a2.id).pub_date,
            datetime(2005, 7, 31, 12, 30, 45),
        )

    def test_saving_an_object_again_does_not_create_a_new_object(self):
        """
        Tests that saving an object multiple times does not create a new object instance.

        This test verifies that saving an object, either initially or after making changes to its attributes, 
        reuses the existing database entry instead of creating a new one. The object's unique identifier 
        remains consistent across all save operations, ensuring that updates are applied to the original 
        object rather than creating duplicate entries.
        """
        a = Article(headline="original", pub_date=datetime(2014, 5, 16))
        a.save()
        current_id = a.id

        a.save()
        self.assertEqual(a.id, current_id)

        a.headline = "Updated headline"
        a.save()
        self.assertEqual(a.id, current_id)

    def test_querysets_checking_for_membership(self):
        """

        Tests the membership of an Article instance in a Django queryset.

        Checks if an Article object is correctly added to the database and can be 
        retrieved using Django's ORM, ensuring that the object is a member of the 
        queryset returned by Article.objects.all(). Additionally, verifies that the 
        object can be filtered by its id using Article.objects.filter(id=a.id).exists().

        This test case covers the basic CRUD (Create, Read) operations for an Article 
        instance and validates the correct behavior of Django's queryset membership 
        checking methods.

        """
        headlines = ["Parrot programs in Python", "Second article", "Third article"]
        some_pub_date = datetime(2014, 5, 16, 12, 1)
        for headline in headlines:
            Article(headline=headline, pub_date=some_pub_date).save()
        a = Article(headline="Some headline", pub_date=some_pub_date)
        a.save()

        # You can use 'in' to test for membership...
        self.assertIn(a, Article.objects.all())
        # ... but there will often be more efficient ways if that is all you need:
        self.assertTrue(Article.objects.filter(id=a.id).exists())

    def test_save_primary_with_default(self):
        # An UPDATE attempt is skipped when a primary key has default.
        """
        Tests the saving of a PrimaryKeyWithDefault object, verifying that it only generates a single database query.
        """
        with self.assertNumQueries(1):
            PrimaryKeyWithDefault().save()

    def test_save_primary_with_default_force_update(self):
        # An UPDATE attempt is made if explicitly requested.
        obj = PrimaryKeyWithDefault.objects.create()
        with self.assertNumQueries(1):
            PrimaryKeyWithDefault(uuid=obj.pk).save(force_update=True)

    def test_save_primary_with_db_default(self):
        # An UPDATE attempt is skipped when a primary key has db_default.
        """
        Tests the saving of a PrimaryKeyWithDbDefault instance to the database with a single query.

        This test case verifies that the save operation of a PrimaryKeyWithDbDefault object utilizes the database's default values and completes in a single database query, ensuring optimized performance and data integrity.

        The test asserts that exactly one query is executed during the save process, confirming the expected database interaction behavior.
        """
        with self.assertNumQueries(1):
            PrimaryKeyWithDbDefault().save()

    def test_save_parent_primary_with_default(self):
        # An UPDATE attempt is skipped when an inherited primary key has
        # default.
        """

        Tests the saving of a ChildPrimaryKeyWithDefault instance with default values.

        This test case verifies that the primary key of the child object is properly
        assigned when the object is saved, using default values where applicable.
        It also checks the number of database queries executed during this operation.

        The test expects exactly 2 database queries to be performed during the save
        operation, ensuring efficient data persistence.

        """
        with self.assertNumQueries(2):
            ChildPrimaryKeyWithDefault().save()

    def test_save_deprecation(self):
        """
        Tests deprecation warning for passing positional arguments to the save method.

        This test case verifies that a warning is raised when using positional arguments
        with the save method, as this functionality is planned for removal in Django 6.0.
        It checks for the correct warning message and ensures that the object is saved
        successfully despite the deprecation warning.

        Args:
            None

        Returns:
            None

        Raises:
            RemovedInDjango60Warning: If positional arguments are passed to the save method.

        """
        a = Article(headline="original", pub_date=datetime(2014, 5, 16))
        msg = "Passing positional arguments to save() is deprecated"
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            a.save(False, False, None, None)
            self.assertEqual(Article.objects.count(), 1)

    def test_save_deprecation_positional_arguments_used(self):
        """

        Tests that using positional arguments with the save method of an Article instance 
        triggers a RemovedInDjango60Warning and that the method call is correctly translated 
        to the new keyword-based argument format.

        This test checks that the deprecated positional arguments are correctly converted 
        to their corresponding keyword arguments (using, force_insert, force_update, and update_fields) 
        when the save method is called, ensuring backwards compatibility.

        """
        a = Article()
        fields = ["headline"]
        with (
            self.assertWarns(RemovedInDjango60Warning),
            mock.patch.object(a, "save_base") as mock_save_base,
        ):
            a.save(None, 1, 2, fields)
        self.assertEqual(
            mock_save_base.mock_calls,
            [
                mock.call(
                    using=2,
                    force_insert=None,
                    force_update=1,
                    update_fields=frozenset(fields),
                )
            ],
        )

    def test_save_too_many_positional_arguments(self):
        """
        Tests that the Article.save method correctly raises a TypeError when given too many positional arguments.

        The test verifies that providing more than the maximum allowed number of positional arguments to the save method
        results in a TypeError being raised, while also triggering a RemovedInDjango60Warning.

        The expected error message is provided to ensure the correct exception is being raised with the correct message,
        indicating that the save method is being called with an excessive number of positional arguments.

        """
        a = Article()
        msg = "Model.save() takes from 1 to 5 positional arguments but 6 were given"
        with (
            self.assertWarns(RemovedInDjango60Warning),
            self.assertRaisesMessage(TypeError, msg),
        ):
            a.save(False, False, None, None, None)

    def test_save_conflicting_positional_and_named_arguments(self):
        """

        Tests that using both positional and named arguments for the same parameter in the :meth:`save` method raises a :class:`TypeError`.

        This test case checks for the parameters 'force_insert', 'force_update', 'using', and 'update_fields' to ensure that passing both a positional and a named argument for the same parameter results in the expected error message.

        """
        a = Article()
        cases = [
            ("force_insert", True, [42]),
            ("force_update", None, [42, 41]),
            ("using", "some-db", [42, 41, 40]),
            ("update_fields", ["foo"], [42, 41, 40, 39]),
        ]
        for param_name, param_value, args in cases:
            with self.subTest(param_name=param_name):
                msg = f"Model.save() got multiple values for argument '{param_name}'"
                with (
                    self.assertWarns(RemovedInDjango60Warning),
                    self.assertRaisesMessage(TypeError, msg),
                ):
                    a.save(*args, **{param_name: param_value})

    async def test_asave_deprecation(self):
        """

        Tests the deprecation warning for passing positional arguments to the asave() method.

        This test ensures that a RemovedInDjango60Warning is raised when positional arguments are passed to asave(),
        and verifies that the object is successfully saved despite the deprecation warning.

        The test case creates an Article object, passes positional arguments to asave(), and checks that the warning is raised
        with the correct message. Additionally, it confirms that the object count in the database is updated correctly after saving.

        """
        a = Article(headline="original", pub_date=datetime(2014, 5, 16))
        msg = "Passing positional arguments to asave() is deprecated"
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            await a.asave(False, False, None, None)
            self.assertEqual(await Article.objects.acount(), 1)

    async def test_asave_deprecation_positional_arguments_used(self):
        """

        Tests the deprecation of positional arguments in the asave method of the Article class.

        The test verifies that using positional arguments in asave triggers a RemovedInDjango60Warning
        and that the method calls save_base with the correct keyword arguments.

        It checks that the 'using' keyword argument corresponds to the third positional argument,
        the 'force_insert' and 'force_update' keyword arguments correspond to the first and second 
        positional arguments respectively, and the 'update_fields' keyword argument corresponds 
        to the fields list passed as the fourth positional argument.

        """
        a = Article()
        fields = ["headline"]
        with (
            self.assertWarns(RemovedInDjango60Warning),
            mock.patch.object(a, "save_base") as mock_save_base,
        ):
            await a.asave(None, 1, 2, fields)
        self.assertEqual(
            mock_save_base.mock_calls,
            [
                mock.call(
                    using=2,
                    force_insert=None,
                    force_update=1,
                    update_fields=frozenset(fields),
                )
            ],
        )

    async def test_asave_too_many_positional_arguments(self):
        a = Article()
        msg = "Model.asave() takes from 1 to 5 positional arguments but 6 were given"
        with (
            self.assertWarns(RemovedInDjango60Warning),
            self.assertRaisesMessage(TypeError, msg),
        ):
            await a.asave(False, False, None, None, None)

    async def test_asave_conflicting_positional_and_named_arguments(self):
        """

        Tests that Article.asave() correctly raises an error when passed both positional and named arguments for the same parameter.

        This test case covers various parameters, including 'force_insert', 'force_update', 'using', and 'update_fields', 
        to ensure that the function behaves as expected in all scenarios.

        The test verifies that a RemovedInDjango60Warning is issued and a TypeError is raised with a message indicating 
        that multiple values were provided for a single argument.

        """
        a = Article()
        cases = [
            ("force_insert", True, [42]),
            ("force_update", None, [42, 41]),
            ("using", "some-db", [42, 41, 40]),
            ("update_fields", ["foo"], [42, 41, 40, 39]),
        ]
        for param_name, param_value, args in cases:
            with self.subTest(param_name=param_name):
                msg = f"Model.asave() got multiple values for argument '{param_name}'"
                with (
                    self.assertWarns(RemovedInDjango60Warning),
                    self.assertRaisesMessage(TypeError, msg),
                ):
                    await a.asave(*args, **{param_name: param_value})

    @ignore_warnings(category=RemovedInDjango60Warning)
    def test_save_positional_arguments(self):
        """

        Tests that the save method with positional arguments updates the model instance correctly.

        This test case verifies that when saving a model instance with positional arguments,
        the specified fields are updated, while others remain unchanged. It checks the behavior
        of the save method with different combinations of positional arguments to ensure data
        integrity and consistency.

        The test creates an Article instance, modifies one of its fields (headline), and then
        saves the instance with specific fields (pub_date, headline) to be updated or ignored.
        It then checks the updated values to ensure they match the expected results.

        """
        a = Article.objects.create(headline="original", pub_date=datetime(2014, 5, 16))
        a.headline = "changed"

        a.save(False, False, None, ["pub_date"])
        a.refresh_from_db()
        self.assertEqual(a.headline, "original")

        a.headline = "changed"
        a.save(False, False, None, ["pub_date", "headline"])
        a.refresh_from_db()
        self.assertEqual(a.headline, "changed")

    @ignore_warnings(category=RemovedInDjango60Warning)
    async def test_asave_positional_arguments(self):
        """

        Tests the asynchronous save method of a model instance with positional arguments.

        This test case verifies that the asave method updates the model instance in the database
        while allowing for selective field updates. It checks that only the specified fields are
        updated, leaving other fields unchanged.

        The test covers two scenarios:

        * Updating a model instance with a subset of fields, ensuring that other fields remain
          unchanged in the database.
        * Updating a model instance with a specific set of fields, verifying that the changes are
          persisted in the database.

        """
        a = await Article.objects.acreate(
            headline="original", pub_date=datetime(2014, 5, 16)
        )
        a.headline = "changed"

        await a.asave(False, False, None, ["pub_date"])
        await a.arefresh_from_db()
        self.assertEqual(a.headline, "original")

        a.headline = "changed"
        await a.asave(False, False, None, ["pub_date", "headline"])
        await a.arefresh_from_db()
        self.assertEqual(a.headline, "changed")


class ModelTest(TestCase):
    def test_objects_attribute_is_only_available_on_the_class_itself(self):
        with self.assertRaisesMessage(
            AttributeError, "Manager isn't accessible via Article instances"
        ):
            getattr(
                Article(),
                "objects",
            )
        self.assertFalse(hasattr(Article(), "objects"))
        self.assertTrue(hasattr(Article, "objects"))

    def test_queryset_delete_removes_all_items_in_that_queryset(self):
        headlines = ["An article", "Article One", "Amazing article", "Boring article"]
        some_pub_date = datetime(2014, 5, 16, 12, 1)
        for headline in headlines:
            Article(headline=headline, pub_date=some_pub_date).save()
        self.assertQuerySetEqual(
            Article.objects.order_by("headline"),
            sorted(headlines),
            transform=lambda a: a.headline,
        )
        Article.objects.filter(headline__startswith="A").delete()
        self.assertEqual(Article.objects.get().headline, "Boring article")

    def test_not_equal_and_equal_operators_behave_as_expected_on_instances(self):
        some_pub_date = datetime(2014, 5, 16, 12, 1)
        a1 = Article.objects.create(headline="First", pub_date=some_pub_date)
        a2 = Article.objects.create(headline="Second", pub_date=some_pub_date)
        self.assertNotEqual(a1, a2)
        self.assertEqual(a1, Article.objects.get(id__exact=a1.id))

        self.assertNotEqual(
            Article.objects.get(id__exact=a1.id), Article.objects.get(id__exact=a2.id)
        )

    def test_microsecond_precision(self):
        """
        Tests that the microseconds component of a datetime object is preserved when stored and retrieved from the database.

        Verifies that the publication date of an Article instance, when saved and then retrieved, retains its original microsecond precision.

        Ensures that the database storage and retrieval process does not truncate or otherwise alter the microseconds component of the datetime object, confirming accurate precision in the stored data.
        """
        a9 = Article(
            headline="Article 9",
            pub_date=datetime(2005, 7, 31, 12, 30, 45, 180),
        )
        a9.save()
        self.assertEqual(
            Article.objects.get(pk=a9.pk).pub_date,
            datetime(2005, 7, 31, 12, 30, 45, 180),
        )

    def test_manually_specify_primary_key(self):
        # You can manually specify the primary key when creating a new object.
        """

        Tests the ability to manually specify a primary key for an article object.

        Verifies that an article with a manually specified primary key can be successfully saved and retrieved.

        """
        a101 = Article(
            id=101,
            headline="Article 101",
            pub_date=datetime(2005, 7, 31, 12, 30, 45),
        )
        a101.save()
        a101 = Article.objects.get(pk=101)
        self.assertEqual(a101.headline, "Article 101")

    def test_create_method(self):
        # You can create saved objects in a single step
        """
        Tests the creation of an Article object using the create method.

        Verifies that the newly created article can be successfully retrieved 
        from the database and matches the original article object.

        Ensures data consistency and correct functionality of the create method 
        in the Article model.
        """
        a10 = Article.objects.create(
            headline="Article 10",
            pub_date=datetime(2005, 7, 31, 12, 30, 45),
        )
        self.assertEqual(Article.objects.get(headline="Article 10"), a10)

    def test_year_lookup_edge_case(self):
        # Edge-case test: A year lookup should retrieve all objects in
        # the given year, including Jan. 1 and Dec. 31.
        """
        Tests that the year lookup functionality in the Article model correctly handles edge cases, 
        specifically articles published on the first and last day of a year, ensuring they are both 
        included in the results when filtering by that year.
        """
        a11 = Article.objects.create(
            headline="Article 11",
            pub_date=datetime(2008, 1, 1),
        )
        a12 = Article.objects.create(
            headline="Article 12",
            pub_date=datetime(2008, 12, 31, 23, 59, 59, 999999),
        )
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__year=2008),
            [a11, a12],
        )

    def test_unicode_data(self):
        # Unicode data works, too.
        """
        Tests the handling of Unicode data in article headlines.

        Verifies that an article with a Unicode headline can be saved to the database and
        retrieved correctly, ensuring that the original Unicode characters are preserved.

        This test case covers the basic functionality of storing and retrieving Unicode
        data in the Article model, providing confidence in the model's ability to handle
        non-ASCII characters in article headlines.
        """
        a = Article(
            headline="\u6797\u539f \u3081\u3050\u307f",
            pub_date=datetime(2005, 7, 28),
        )
        a.save()
        self.assertEqual(
            Article.objects.get(pk=a.id).headline, "\u6797\u539f \u3081\u3050\u307f"
        )

    def test_hash_function(self):
        # Model instances have a hash function, so they can be used in sets
        # or as dictionary keys. Two models compare as equal if their primary
        # keys are equal.
        """
        Tests the hashing functionality of the Article model.

        This test case creates multiple Article instances with varying publication dates, 
        adds them to a set, and verifies that the instance with a specific headline can be 
        found within the set. This ensures that the Article model's implementation of the 
        hash function allows for correct membership testing in a set data structure.
        """
        a10 = Article.objects.create(
            headline="Article 10",
            pub_date=datetime(2005, 7, 31, 12, 30, 45),
        )
        a11 = Article.objects.create(
            headline="Article 11",
            pub_date=datetime(2008, 1, 1),
        )
        a12 = Article.objects.create(
            headline="Article 12",
            pub_date=datetime(2008, 12, 31, 23, 59, 59, 999999),
        )

        s = {a10, a11, a12}
        self.assertIn(Article.objects.get(headline="Article 11"), s)

    def test_extra_method_select_argument_with_dashes_and_values(self):
        # The 'select' argument to extra() supports names with dashes in
        # them, as long as you use values().
        """
        Tests that the extra method's select argument can handle field names with dashes and returns the expected values.

        This test case creates articles with specific publication dates, filters them by year, and uses the extra method to select additional data. It then verifies that the resulting dictionaries contain the correct data, including the expected value for the dashed field name.

        The test covers the scenario where the select argument of the extra method contains a field name with dashes, ensuring that the ORM can handle such cases correctly and return the expected results.
        """
        Article.objects.bulk_create(
            [
                Article(
                    headline="Article 10", pub_date=datetime(2005, 7, 31, 12, 30, 45)
                ),
                Article(headline="Article 11", pub_date=datetime(2008, 1, 1)),
                Article(
                    headline="Article 12",
                    pub_date=datetime(2008, 12, 31, 23, 59, 59, 999999),
                ),
            ]
        )
        dicts = (
            Article.objects.filter(pub_date__year=2008)
            .extra(select={"dashed-value": "1"})
            .values("headline", "dashed-value")
        )
        self.assertEqual(
            [sorted(d.items()) for d in dicts],
            [
                [("dashed-value", 1), ("headline", "Article 11")],
                [("dashed-value", 1), ("headline", "Article 12")],
            ],
        )

    def test_extra_method_select_argument_with_dashes(self):
        # If you use 'select' with extra() and names containing dashes on a
        # query that's *not* a values() query, those extra 'select' values
        # will silently be ignored.
        """

        Tests the ability to use the extra select argument with dashes in the field name.

        Verifies that Django's ORM correctly handles field names containing dashes when using the extra select argument.
        Ensures that the selected values can be accessed as attributes on the model instances.

        """
        Article.objects.bulk_create(
            [
                Article(
                    headline="Article 10", pub_date=datetime(2005, 7, 31, 12, 30, 45)
                ),
                Article(headline="Article 11", pub_date=datetime(2008, 1, 1)),
                Article(
                    headline="Article 12",
                    pub_date=datetime(2008, 12, 31, 23, 59, 59, 999999),
                ),
            ]
        )
        articles = Article.objects.filter(pub_date__year=2008).extra(
            select={"dashed-value": "1", "undashedvalue": "2"}
        )
        self.assertEqual(articles[0].undashedvalue, 2)

    def test_create_relation_with_gettext_lazy(self):
        """
        gettext_lazy objects work when saving model instances
        through various methods. Refs #10498.
        """
        notlazy = "test"
        lazy = gettext_lazy(notlazy)
        Article.objects.create(headline=lazy, pub_date=datetime.now())
        article = Article.objects.get()
        self.assertEqual(article.headline, notlazy)
        # test that assign + save works with Promise objects
        article.headline = lazy
        article.save()
        self.assertEqual(article.headline, notlazy)
        # test .update()
        Article.objects.update(headline=lazy)
        article = Article.objects.get()
        self.assertEqual(article.headline, notlazy)
        # still test bulk_create()
        Article.objects.all().delete()
        Article.objects.bulk_create([Article(headline=lazy, pub_date=datetime.now())])
        article = Article.objects.get()
        self.assertEqual(article.headline, notlazy)

    def test_emptyqs(self):
        """

        Verifies the correct behavior of the EmptyQuerySet class.

        This test ensures that an EmptyQuerySet cannot be directly instantiated, 
        raising a TypeError with a descriptive message. It also checks that 
        calling the 'none()' method on a QuerySet (e.g., Article.objects) returns 
        an instance of EmptyQuerySet, while other objects (e.g., an empty string) 
        do not.

        """
        msg = "EmptyQuerySet can't be instantiated"
        with self.assertRaisesMessage(TypeError, msg):
            EmptyQuerySet()
        self.assertIsInstance(Article.objects.none(), EmptyQuerySet)
        self.assertNotIsInstance("", EmptyQuerySet)

    def test_emptyqs_values(self):
        # test for #15959
        """

        Tests that an empty QuerySet with values returns an EmptyQuerySet instance.

        Verifies that when calling `values_list` on an empty QuerySet, the resulting object 
        is of type EmptyQuerySet and has a length of 0, without executing any database queries.

        """
        Article.objects.create(headline="foo", pub_date=datetime.now())
        with self.assertNumQueries(0):
            qs = Article.objects.none().values_list("pk")
            self.assertIsInstance(qs, EmptyQuerySet)
            self.assertEqual(len(qs), 0)

    def test_emptyqs_customqs(self):
        # A hacky test for custom QuerySet subclass - refs #17271
        """

        Tests the behavior of an empty queryset with a custom queryset class.

        This test case verifies that an empty queryset, modified to use a custom
        QuerySet class, behaves as expected. Specifically, it checks that the length
        of the empty queryset is 0, that it is an instance of EmptyQuerySet, and that
        it responds to custom methods defined in the custom QuerySet class.

        The test also ensures that no database queries are executed when accessing
        the empty queryset.

        """
        Article.objects.create(headline="foo", pub_date=datetime.now())

        class CustomQuerySet(models.QuerySet):
            def do_something(self):
                return "did something"

        qs = Article.objects.all()
        qs.__class__ = CustomQuerySet
        qs = qs.none()
        with self.assertNumQueries(0):
            self.assertEqual(len(qs), 0)
            self.assertIsInstance(qs, EmptyQuerySet)
            self.assertEqual(qs.do_something(), "did something")

    def test_emptyqs_values_order(self):
        # Tests for ticket #17712
        """

        Tests that the values_list and filter methods with an empty QuerySet do not execute database queries.

        This test case verifies that when operating on an empty QuerySet, the `values_list` method 
        with an `order_by` clause and the `filter` method with `id__in` do not result in any database queries.
        It checks that the lengths of the result sets are as expected (i.e., 0) and that no queries are executed.

        """
        Article.objects.create(headline="foo", pub_date=datetime.now())
        with self.assertNumQueries(0):
            self.assertEqual(
                len(Article.objects.none().values_list("id").order_by("id")), 0
            )
        with self.assertNumQueries(0):
            self.assertEqual(
                len(
                    Article.objects.none().filter(
                        id__in=Article.objects.values_list("id", flat=True)
                    )
                ),
                0,
            )

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_emptyqs_distinct(self):
        # Tests for #19426
        """
        Tests that using the distinct method on an empty QuerySet does not execute any database queries and correctly returns an empty QuerySet. The test case verifies the behavior of the distinct method when used on fields in a QuerySet that contains no results, ensuring that it does not incur unnecessary database queries.
        """
        Article.objects.create(headline="foo", pub_date=datetime.now())
        with self.assertNumQueries(0):
            self.assertEqual(
                len(Article.objects.none().distinct("headline", "pub_date")), 0
            )

    def test_ticket_20278(self):
        """
        Tests that attempting to retrieve a SelfRef object by its self-referential attribute raises an ObjectDoesNotExist exception, ensuring the correct handling of self-referential relationships in the database.
        """
        sr = SelfRef.objects.create()
        with self.assertRaises(ObjectDoesNotExist):
            SelfRef.objects.get(selfref=sr)

    def test_eq(self):
        """
        Tests the equality of Article instances.

        Verifies that Article objects are considered equal when they have the same attributes,
        and not equal when they don't. Also checks for correct behavior when comparing Article
        objects to other types of objects, as well as when using mock objects.

        Specifically, this test covers the following scenarios:
        - Equality between two Article objects with the same id
        - Inequality between an Article object and a generic object
        - Inequality between a generic object and an Article object
        - Equality between an Article object and itself
        - Equality between an Article object and a mock object
        - Inequality between two distinct Article objects
        """
        self.assertEqual(Article(id=1), Article(id=1))
        self.assertNotEqual(Article(id=1), object())
        self.assertNotEqual(object(), Article(id=1))
        a = Article()
        self.assertEqual(a, a)
        self.assertEqual(a, mock.ANY)
        self.assertNotEqual(Article(), a)

    def test_hash(self):
        # Value based on PK
        self.assertEqual(hash(Article(id=1)), hash(1))
        msg = "Model instances without primary key value are unhashable"
        with self.assertRaisesMessage(TypeError, msg):
            # No PK value -> unhashable (because save() would then change
            # hash)
            hash(Article())

    def test_missing_hash_not_inherited(self):
        """

        Tests that a model without a properly implemented __hash__ method does not 
        inherit hash functionality from its parent class, and raises a TypeError 
        instead when attempting to hash an instance of the model. 

        This test ensures that models without a hash function do not behave as if 
        they have one, which could lead to unexpected behavior in sets and other 
        hash-based data structures.

        """
        class NoHash(models.Model):
            def __eq__(self, other):
                return super.__eq__(other)

        with self.assertRaisesMessage(TypeError, "unhashable type: 'NoHash'"):
            hash(NoHash(id=1))

    def test_specified_parent_hash_inherited(self):
        """
        Tests whether the hash of an instance of a model class is inherited from its parent.

        This test case verifies that when a model class does not explicitly define its own __hash__ method,
        it will use the __hash__ method from its parent class. In this scenario, the hash of the instance
        is expected to be equal to its primary key value.

        The test creates a simple model class ParentHash and checks if the hash of an instance with a given
        id is equal to that id, confirming the inheritance of the parent's hash behavior.
        """
        class ParentHash(models.Model):
            def __eq__(self, other):
                return super.__eq__(other)

            __hash__ = models.Model.__hash__

        self.assertEqual(hash(ParentHash(id=1)), 1)

    def test_delete_and_access_field(self):
        # Accessing a field after it's deleted from a model reloads its value.
        """

        Tests the behavior of deleting and accessing a field from a model instance.

        This test case verifies that after deleting a field, the original value is
        retrieved from the database when accessed. It checks this behavior for both
        modified and unmodified fields, ensuring data consistency and correct
        database interaction.

        Specifically, it creates an Article instance, modifies its headline and pub_date
        fields, deletes the headline field, and then asserts that the original headline
        value is retrieved from the database while the modified pub_date value remains
        unchanged. The test also verifies that only one database query is executed
        when accessing the deleted field.

        """
        pub_date = datetime.now()
        article = Article.objects.create(headline="foo", pub_date=pub_date)
        new_pub_date = article.pub_date + timedelta(days=10)
        article.headline = "bar"
        article.pub_date = new_pub_date
        del article.headline
        with self.assertNumQueries(1):
            self.assertEqual(article.headline, "foo")
        # Fields that weren't deleted aren't reloaded.
        self.assertEqual(article.pub_date, new_pub_date)

    def test_multiple_objects_max_num_fetched(self):
        max_results = MAX_GET_RESULTS - 1
        Article.objects.bulk_create(
            Article(headline="Area %s" % i, pub_date=datetime(2005, 7, 28))
            for i in range(max_results)
        )
        self.assertRaisesMessage(
            MultipleObjectsReturned,
            "get() returned more than one Article -- it returned %d!" % max_results,
            Article.objects.get,
            headline__startswith="Area",
        )
        Article.objects.create(
            headline="Area %s" % max_results, pub_date=datetime(2005, 7, 28)
        )
        self.assertRaisesMessage(
            MultipleObjectsReturned,
            "get() returned more than one Article -- it returned more than %d!"
            % max_results,
            Article.objects.get,
            headline__startswith="Area",
        )


class ModelLookupTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create an Article.
        """
        Sets up test data for the class, creating a single Article instance.

        This method is used to prepare the test environment by creating an Article object 
        with a headline and publication date, and then saving it. The created article is 
        assigned to the class variable 'a' and can be accessed in subsequent tests.

        The purpose of this setup is to provide a baseline dataset for testing, allowing 
        test cases to focus on verifying specific functionality without needing to create 
        test data from scratch each time.

        The Article instance is populated with the following attributes:
            - id: Automatically generated
            - headline: 'Swallow programs in Python'
            - pub_date: July 28, 2005
        """
        cls.a = Article(
            id=None,
            headline="Swallow programs in Python",
            pub_date=datetime(2005, 7, 28),
        )
        # Save it into the database. You have to call save() explicitly.
        cls.a.save()

    def test_all_lookup(self):
        # Change values by changing the attributes, then calling save().
        """
        Tests the retrieval of all articles from the database, 
        verifying that a saved article is correctly included in the result set.
        The test first sets up an article with a specific headline, saves it, 
        and then checks that the article is the only one returned by the all() method.
        """
        self.a.headline = "Parrot programs in Python"
        self.a.save()

        # Article.objects.all() returns all the articles in the database.
        self.assertSequenceEqual(Article.objects.all(), [self.a])

    def test_rich_lookup(self):
        # Django provides a rich database lookup API.
        self.assertEqual(Article.objects.get(id__exact=self.a.id), self.a)
        self.assertEqual(Article.objects.get(headline__startswith="Swallow"), self.a)
        self.assertEqual(Article.objects.get(pub_date__year=2005), self.a)
        self.assertEqual(
            Article.objects.get(pub_date__year=2005, pub_date__month=7), self.a
        )
        self.assertEqual(
            Article.objects.get(
                pub_date__year=2005, pub_date__month=7, pub_date__day=28
            ),
            self.a,
        )
        self.assertEqual(Article.objects.get(pub_date__week_day=5), self.a)

    def test_equal_lookup(self):
        # The "__exact" lookup type can be omitted, as a shortcut.
        self.assertEqual(Article.objects.get(id=self.a.id), self.a)
        self.assertEqual(
            Article.objects.get(headline="Swallow programs in Python"), self.a
        )

        self.assertSequenceEqual(
            Article.objects.filter(pub_date__year=2005),
            [self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__year=2004),
            [],
        )
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__year=2005, pub_date__month=7),
            [self.a],
        )

        self.assertSequenceEqual(
            Article.objects.filter(pub_date__week_day=5),
            [self.a],
        )
        self.assertSequenceEqual(
            Article.objects.filter(pub_date__week_day=6),
            [],
        )

    def test_does_not_exist(self):
        # Django raises an Article.DoesNotExist exception for get() if the
        # parameters don't match any object.
        """
        Tests the handling of non-existent objects when using the ORM's get method.

        This test suite verifies that ObjectDoesNotExist exceptions are raised when attempting to retrieve articles that do not exist in the database.
        It covers scenarios where the query is based on an incorrect primary key, as well as when filtering on specific date fields (year, month, week day) 
        that do not match any existing articles. The test also checks that the error message provided with the exception is as expected in certain cases.
        """
        with self.assertRaisesMessage(
            ObjectDoesNotExist, "Article matching query does not exist."
        ):
            Article.objects.get(
                id__exact=2000,
            )
        # To avoid dict-ordering related errors check only one lookup
        # in single assert.
        with self.assertRaises(ObjectDoesNotExist):
            Article.objects.get(pub_date__year=2005, pub_date__month=8)
        with self.assertRaisesMessage(
            ObjectDoesNotExist, "Article matching query does not exist."
        ):
            Article.objects.get(
                pub_date__week_day=6,
            )

    def test_lookup_by_primary_key(self):
        # Lookup by a primary key is the most common case, so Django
        # provides a shortcut for primary-key exact lookups.
        # The following is identical to articles.get(id=a.id).
        self.assertEqual(Article.objects.get(pk=self.a.id), self.a)

        # pk can be used as a shortcut for the primary key name in any query.
        self.assertSequenceEqual(Article.objects.filter(pk__in=[self.a.id]), [self.a])

        # Model instances of the same type and same ID are considered equal.
        a = Article.objects.get(pk=self.a.id)
        b = Article.objects.get(pk=self.a.id)
        self.assertEqual(a, b)

    def test_too_many(self):
        # Create a very similar object
        a = Article(
            id=None,
            headline="Swallow bites Python",
            pub_date=datetime(2005, 7, 28),
        )
        a.save()

        self.assertEqual(Article.objects.count(), 2)

        # Django raises an Article.MultipleObjectsReturned exception if the
        # lookup matches more than one object
        msg = "get() returned more than one Article -- it returned 2!"
        with self.assertRaisesMessage(MultipleObjectsReturned, msg):
            Article.objects.get(
                headline__startswith="Swallow",
            )
        with self.assertRaisesMessage(MultipleObjectsReturned, msg):
            Article.objects.get(
                pub_date__year=2005,
            )
        with self.assertRaisesMessage(MultipleObjectsReturned, msg):
            Article.objects.get(pub_date__year=2005, pub_date__month=7)


class ConcurrentSaveTests(TransactionTestCase):
    available_apps = ["basic"]

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_concurrent_delete_with_save(self):
        """
        Test fetching, deleting and finally saving an object - we should get
        an insert in this case.
        """
        a = Article.objects.create(headline="foo", pub_date=datetime.now())
        exceptions = []

        def deleter():
            """

            Delete an article from the database.

            This function removes an article instance from the database. It attempts to filter 
            the articles by primary key and delete the matching record. If any exceptions occur 
            during this process, they are caught and appended to the exceptions list. Regardless 
            of whether an exception was raised, the database connection is closed after deletion.

            :raises: Exception
            :returns: None

            """
            try:
                # Do not delete a directly - doing so alters its state.
                Article.objects.filter(pk=a.pk).delete()
            except Exception as e:
                exceptions.append(e)
            finally:
                connections[DEFAULT_DB_ALIAS].close()

        self.assertEqual(len(exceptions), 0)
        t = threading.Thread(target=deleter)
        t.start()
        t.join()
        a.save()
        self.assertEqual(Article.objects.get(pk=a.pk).headline, "foo")


class ManagerTest(SimpleTestCase):
    QUERYSET_PROXY_METHODS = [
        "none",
        "count",
        "dates",
        "datetimes",
        "distinct",
        "extra",
        "get",
        "get_or_create",
        "update_or_create",
        "create",
        "bulk_create",
        "bulk_update",
        "filter",
        "aggregate",
        "annotate",
        "alias",
        "complex_filter",
        "exclude",
        "in_bulk",
        "iterator",
        "earliest",
        "latest",
        "first",
        "last",
        "order_by",
        "select_for_update",
        "select_related",
        "prefetch_related",
        "values",
        "values_list",
        "update",
        "reverse",
        "defer",
        "only",
        "using",
        "exists",
        "contains",
        "explain",
        "_insert",
        "_update",
        "raw",
        "union",
        "intersection",
        "difference",
        "aaggregate",
        "abulk_create",
        "abulk_update",
        "acontains",
        "acount",
        "acreate",
        "aearliest",
        "aexists",
        "aexplain",
        "afirst",
        "aget",
        "aget_or_create",
        "ain_bulk",
        "aiterator",
        "alast",
        "alatest",
        "aupdate",
        "aupdate_or_create",
    ]

    def test_manager_methods(self):
        """
        This test ensures that the correct set of methods from `QuerySet`
        are copied onto `Manager`.

        It's particularly useful to prevent accidentally leaking new methods
        into `Manager`. New `QuerySet` methods that should also be copied onto
        `Manager` will need to be added to `ManagerTest.QUERYSET_PROXY_METHODS`.
        """
        self.assertEqual(
            sorted(BaseManager._get_queryset_methods(models.QuerySet)),
            sorted(self.QUERYSET_PROXY_METHODS),
        )

    def test_manager_method_attributes(self):
        """
        Tests that the method attributes of the Manager instance in the Article model 
        are correctly inherited from the QuerySet class in Django's models module. 
        Specifically, it verifies that the docstring of the get method and the name 
        of the count method match their equivalents in the QuerySet class.
        """
        self.assertEqual(Article.objects.get.__doc__, models.QuerySet.get.__doc__)
        self.assertEqual(Article.objects.count.__name__, models.QuerySet.count.__name__)

    def test_manager_method_signature(self):
        self.assertEqual(
            str(inspect.signature(Article.objects.bulk_create)),
            "(objs, batch_size=None, ignore_conflicts=False, update_conflicts=False, "
            "update_fields=None, unique_fields=None)",
        )


class SelectOnSaveTests(TestCase):
    def test_select_on_save(self):
        a1 = Article.objects.create(pub_date=datetime.now())
        with self.assertNumQueries(1):
            a1.save()
        asos = ArticleSelectOnSave.objects.create(pub_date=datetime.now())
        with self.assertNumQueries(2):
            asos.save()
        with self.assertNumQueries(1):
            asos.save(force_update=True)
        Article.objects.all().delete()
        with self.assertRaisesMessage(
            DatabaseError, "Forced update did not affect any rows."
        ):
            with self.assertNumQueries(1):
                asos.save(force_update=True)

    def test_select_on_save_lying_update(self):
        """
        select_on_save works correctly if the database doesn't return correct
        information about matched rows from UPDATE.
        """
        # Change the manager to not return "row matched" for update().
        # We are going to change the Article's _base_manager class
        # dynamically. This is a bit of a hack, but it seems hard to
        # test this properly otherwise. Article's manager, because
        # proxy models use their parent model's _base_manager.

        orig_class = Article._base_manager._queryset_class

        class FakeQuerySet(models.QuerySet):
            # Make sure the _update method below is in fact called.
            called = False

            def _update(self, *args, **kwargs):
                FakeQuerySet.called = True
                super()._update(*args, **kwargs)
                return 0

        try:
            Article._base_manager._queryset_class = FakeQuerySet
            asos = ArticleSelectOnSave.objects.create(pub_date=datetime.now())
            with self.assertNumQueries(3):
                asos.save()
                self.assertTrue(FakeQuerySet.called)
            # This is not wanted behavior, but this is how Django has always
            # behaved for databases that do not return correct information
            # about matched rows for UPDATE.
            with self.assertRaisesMessage(
                DatabaseError, "Forced update did not affect any rows."
            ):
                asos.save(force_update=True)
            msg = (
                "An error occurred in the current transaction. You can't "
                "execute queries until the end of the 'atomic' block."
            )
            with self.assertRaisesMessage(DatabaseError, msg) as cm:
                asos.save(update_fields=["pub_date"])
            self.assertIsInstance(cm.exception.__cause__, DatabaseError)
        finally:
            Article._base_manager._queryset_class = orig_class


class ModelRefreshTests(TestCase):
    def test_refresh(self):
        """

        Refreshes an article instance from the database, ensuring its attributes are up-to-date.

        Tests the functionality of the `refresh_from_db` method, verifying that it updates the
        instance with the latest changes from the database. This includes updates to individual
        fields, as well as full refreshes of the instance.

        The test scenario covers the following cases:
        - Updating a single field and refreshing the instance
        - Updating multiple fields and refreshing specific fields
        - Refreshing the entire instance after updating multiple fields

        """
        a = Article.objects.create(pub_date=datetime.now())
        Article.objects.create(pub_date=datetime.now())
        Article.objects.filter(pk=a.pk).update(headline="new headline")
        with self.assertNumQueries(1):
            a.refresh_from_db()
            self.assertEqual(a.headline, "new headline")

        orig_pub_date = a.pub_date
        new_pub_date = a.pub_date + timedelta(10)
        Article.objects.update(headline="new headline 2", pub_date=new_pub_date)
        with self.assertNumQueries(1):
            a.refresh_from_db(fields=["headline"])
            self.assertEqual(a.headline, "new headline 2")
            self.assertEqual(a.pub_date, orig_pub_date)
        with self.assertNumQueries(1):
            a.refresh_from_db()
            self.assertEqual(a.pub_date, new_pub_date)

    def test_unknown_kwarg(self):
        """
        Tests that calling refresh_from_db with an unknown keyword argument raises a TypeError.

        This test case verifies that the refresh_from_db method correctly handles invalid input by
        raising an exception when an unexpected keyword argument is provided.

        The expected exception message is also checked to ensure it matches the expected error message,
        providing a clear indication of the problem to the user.
        """
        s = SelfRef.objects.create()
        msg = "refresh_from_db() got an unexpected keyword argument 'unknown_kwarg'"
        with self.assertRaisesMessage(TypeError, msg):
            s.refresh_from_db(unknown_kwarg=10)

    def test_lookup_in_fields(self):
        """
        Tests that a ValueError is raised when attempting to refresh an object from the database 
        with a fields argument that includes a relation or transform, such as a lookup using double underscore syntax.
        """
        s = SelfRef.objects.create()
        msg = (
            'Found "__" in fields argument. Relations and transforms are not allowed '
            "in fields."
        )
        with self.assertRaisesMessage(ValueError, msg):
            s.refresh_from_db(fields=["foo__bar"])

    def test_refresh_fk(self):
        """
        TestUtils for the refresh_from_db() method when foreign key relationships are involved.

         Checks that when a foreign key relationship is updated, calling refresh_from_db() 
         on an object that was retrieved earlier will correctly refresh the foreign key 
         relationship and not retain the original relationship.

         Additionally, verifies that any cached attributes on the related object are not 
         retained after the refresh operation, ensuring data consistency and preventing 
         stale data from being used in the application.
        """
        s1 = SelfRef.objects.create()
        s2 = SelfRef.objects.create()
        s3 = SelfRef.objects.create(selfref=s1)
        s3_copy = SelfRef.objects.get(pk=s3.pk)
        s3_copy.selfref.touched = True
        s3.selfref = s2
        s3.save()
        with self.assertNumQueries(1):
            s3_copy.refresh_from_db()
        with self.assertNumQueries(1):
            # The old related instance was thrown away (the selfref_id has
            # changed). It needs to be reloaded on access, so one query
            # executed.
            self.assertFalse(hasattr(s3_copy.selfref, "touched"))
            self.assertEqual(s3_copy.selfref, s2)

    def test_refresh_null_fk(self):
        """
        Tests the behavior of the refresh_from_db method when a null foreign key is set.

        Ensures that after setting a foreign key to null and then refreshing the object from the database,
        the foreign key is restored to its original value, rather than being persisted as null.

        Verifies the correct functionality of the foreign key relationship and the refresh_from_db method
        in cases where the foreign key is temporarily set to null, but not persisted to the database.
        """
        s1 = SelfRef.objects.create()
        s2 = SelfRef.objects.create(selfref=s1)
        s2.selfref = None
        s2.refresh_from_db()
        self.assertEqual(s2.selfref, s1)

    def test_refresh_unsaved(self):
        """
        Tests the refresh_from_db method on an unsaved model instance.

        Verifies that a single database query is executed when refresh_from_db is called
        and that the instance's attributes are updated with the latest values from the database.
        Specifically, it checks that the pub_date attribute is correctly refreshed and 
        that the instance is aware of the database it was refreshed from.
        """
        pub_date = datetime.now()
        a = Article.objects.create(pub_date=pub_date)
        a2 = Article(id=a.pk)
        with self.assertNumQueries(1):
            a2.refresh_from_db()
        self.assertEqual(a2.pub_date, pub_date)
        self.assertEqual(a2._state.db, "default")

    def test_refresh_fk_on_delete_set_null(self):
        a = Article.objects.create(
            headline="Parrot programs in Python",
            pub_date=datetime(2005, 7, 28),
        )
        s1 = SelfRef.objects.create(article=a)
        a.delete()
        s1.refresh_from_db()
        self.assertIsNone(s1.article_id)
        self.assertIsNone(s1.article)

    def test_refresh_no_fields(self):
        """

        Tests the refresh_from_db method of an Article instance when no fields are specified.

        This test ensures that no database queries are executed when calling refresh_from_db without specifying any fields to refresh.

        The test creates an Article instance, then attempts to refresh it from the database without specifying any fields. It asserts that this operation does not result in any database queries being executed.

        """
        a = Article.objects.create(pub_date=datetime.now())
        with self.assertNumQueries(0):
            a.refresh_from_db(fields=[])

    def test_refresh_clears_reverse_related(self):
        """refresh_from_db() clear cached reverse relations."""
        article = Article.objects.create(
            headline="Parrot programs in Python",
            pub_date=datetime(2005, 7, 28),
        )
        self.assertFalse(hasattr(article, "featured"))
        FeaturedArticle.objects.create(article_id=article.pk)
        article.refresh_from_db()
        self.assertTrue(hasattr(article, "featured"))

    def test_refresh_clears_reverse_related_explicit_fields(self):
        """

        Tests that refreshing an Article instance from the database clears and then 
        correctly updates its reverse-related 'featured' field after an explicit 
        FeaturedArticle relation has been established.

        Verifies the correct behavior of the refresh_from_db method with respect to 
        explicit model field specification in the context of reverse relationships.

        """
        article = Article.objects.create(headline="Test", pub_date=datetime(2024, 2, 4))
        self.assertFalse(hasattr(article, "featured"))
        FeaturedArticle.objects.create(article_id=article.pk)
        article.refresh_from_db(fields=["featured"])
        self.assertTrue(hasattr(article, "featured"))

    def test_refresh_clears_one_to_one_field(self):
        """
        Tests that refreshing a featured article instance from the database updates its related one-to-one fields after the related object has been modified.
        """
        article = Article.objects.create(
            headline="Parrot programs in Python",
            pub_date=datetime(2005, 7, 28),
        )
        featured = FeaturedArticle.objects.create(article_id=article.pk)
        self.assertEqual(featured.article.headline, "Parrot programs in Python")
        article.headline = "Parrot programs in Python 2.0"
        article.save()
        featured.refresh_from_db()
        self.assertEqual(featured.article.headline, "Parrot programs in Python 2.0")

    def test_prefetched_cache_cleared(self):
        a = Article.objects.create(pub_date=datetime(2005, 7, 28))
        s = SelfRef.objects.create(article=a, article_cited=a)
        # refresh_from_db() without fields=[...]
        a1_prefetched = Article.objects.prefetch_related("selfref_set", "cited").first()
        self.assertCountEqual(a1_prefetched.selfref_set.all(), [s])
        self.assertCountEqual(a1_prefetched.cited.all(), [s])
        s.article = None
        s.article_cited = None
        s.save()
        # Relation is cleared and prefetch cache is stale.
        self.assertCountEqual(a1_prefetched.selfref_set.all(), [s])
        self.assertCountEqual(a1_prefetched.cited.all(), [s])
        a1_prefetched.refresh_from_db()
        # Cache was cleared and new results are available.
        self.assertCountEqual(a1_prefetched.selfref_set.all(), [])
        self.assertCountEqual(a1_prefetched.cited.all(), [])
        # refresh_from_db() with fields=[...]
        a2_prefetched = Article.objects.prefetch_related("selfref_set", "cited").first()
        self.assertCountEqual(a2_prefetched.selfref_set.all(), [])
        self.assertCountEqual(a2_prefetched.cited.all(), [])
        s.article = a
        s.article_cited = a
        s.save()
        # Relation is added and prefetch cache is stale.
        self.assertCountEqual(a2_prefetched.selfref_set.all(), [])
        self.assertCountEqual(a2_prefetched.cited.all(), [])
        fields = ["selfref_set", "cited"]
        a2_prefetched.refresh_from_db(fields=fields)
        self.assertEqual(fields, ["selfref_set", "cited"])
        # Cache was cleared and new results are available.
        self.assertCountEqual(a2_prefetched.selfref_set.all(), [s])
        self.assertCountEqual(a2_prefetched.cited.all(), [s])

    @skipUnlessDBFeature("has_select_for_update")
    def test_refresh_for_update(self):
        """

        Tests the functionality of refreshing an object from the database using `select_for_update`.

        This test case verifies that when `refresh_from_db` is called with a queryset that uses `select_for_update`, 
        the underlying SQL query includes the necessary `FOR UPDATE` clause to lock the selected row until the end of the transaction.

        The test creates an instance of an `Article` object, refreshes it from the database using `select_for_update`, 
        and then checks the captured SQL queries to ensure that the `FOR UPDATE` clause was used.

        """
        a = Article.objects.create(pub_date=datetime.now())
        for_update_sql = connection.ops.for_update_sql()

        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            a.refresh_from_db(from_queryset=Article.objects.select_for_update())
        self.assertTrue(
            any(for_update_sql in query["sql"] for query in ctx.captured_queries)
        )

    def test_refresh_with_related(self):
        """

        Tests the refresh_from_db method of a FeaturedArticle instance, 
        ensuring it correctly updates the object's data from the database.

        Specifically, it checks the behavior when using select_related to prefetch 
        related objects, verifying that the article associated with the featured 
        article is updated correctly in both cases: when using a queryset that has 
        prefetched related objects and when not using such a queryset.

        The test asserts that the number of database queries is as expected in each 
        scenario, and that the article's publication date is correctly updated to 
        match the original article's publication date.

        """
        a = Article.objects.create(pub_date=datetime.now())
        fa = FeaturedArticle.objects.create(article=a)

        from_queryset = FeaturedArticle.objects.select_related("article")
        with self.assertNumQueries(1):
            fa.refresh_from_db(from_queryset=from_queryset)
            self.assertEqual(fa.article.pub_date, a.pub_date)
        with self.assertNumQueries(2):
            fa.refresh_from_db()
            self.assertEqual(fa.article.pub_date, a.pub_date)

    def test_refresh_overwrites_queryset_using(self):
        """
        Tests the behavior of the refresh_from_db method when overwriting the queryset.

        Verifies that attempting to refresh an object using a queryset from a nonexistent database raises a ConnectionDoesNotExist exception.

        Also checks that the refresh operation succeeds when specifying a valid database to use, even if the original queryset is from a different database.

        This ensures that the refresh_from_db method correctly handles cases where the queryset's database does not match the object's database, and that it can be forced to use a specific database when needed.
        """
        a = Article.objects.create(pub_date=datetime.now())

        from_queryset = Article.objects.using("nonexistent")
        with self.assertRaises(ConnectionDoesNotExist):
            a.refresh_from_db(from_queryset=from_queryset)
        a.refresh_from_db(using="default", from_queryset=from_queryset)

    def test_refresh_overwrites_queryset_fields(self):
        """

        Tests the behavior of refresh_from_db method when used with a queryset 
        that only retrieves a limited set of fields.

        Specifically, it checks that when refresh_from_db is called with 
        a queryset that does not include all model fields, the model instance 
        is updated correctly. It also verifies that when specific fields 
        are requested, only those fields are updated.

        This test ensures that the refresh_from_db method behaves as expected 
        when used in conjunction with querysets that use the only method 
        to limit the fields retrieved from the database.

        """
        a = Article.objects.create(pub_date=datetime.now())
        headline = "headline"
        Article.objects.filter(pk=a.pk).update(headline=headline)

        from_queryset = Article.objects.only("pub_date")
        with self.assertNumQueries(1):
            a.refresh_from_db(from_queryset=from_queryset)
            self.assertNotEqual(a.headline, headline)
        with self.assertNumQueries(1):
            a.refresh_from_db(fields=["headline"], from_queryset=from_queryset)
            self.assertEqual(a.headline, headline)
