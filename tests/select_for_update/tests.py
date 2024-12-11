import threading
import time
from unittest import mock

from multiple_database.routers import TestRouter

from django.core.exceptions import FieldError
from django.db import (
    DatabaseError,
    NotSupportedError,
    connection,
    connections,
    router,
    transaction,
)
from django.test import (
    TransactionTestCase,
    override_settings,
    skipIfDBFeature,
    skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext

from .models import (
    City,
    CityCountryProxy,
    Country,
    EUCity,
    EUCountry,
    Person,
    PersonProfile,
)


class SelectForUpdateTests(TransactionTestCase):
    available_apps = ["select_for_update"]

    def setUp(self):
        # This is executed in autocommit mode so that code in
        # run_select_for_update can see this data.
        self.country1 = Country.objects.create(name="Belgium")
        self.country2 = Country.objects.create(name="France")
        self.city1 = City.objects.create(name="Liberchies", country=self.country1)
        self.city2 = City.objects.create(name="Samois-sur-Seine", country=self.country2)
        self.person = Person.objects.create(
            name="Reinhardt", born=self.city1, died=self.city2
        )
        self.person_profile = PersonProfile.objects.create(person=self.person)

        # We need another database connection in transaction to test that one
        # connection issuing a SELECT ... FOR UPDATE will block.
        self.new_connection = connection.copy()

    def tearDown(self):
        try:
            self.end_blocking_transaction()
        except (DatabaseError, AttributeError):
            pass
        self.new_connection.close()

    def start_blocking_transaction(self):
        """

        Starts a blocking transaction to lock rows in the database table for exclusive access.

        This method initiates a database transaction, sets autocommit to False, and executes a SELECT query with a FOR UPDATE clause to lock the rows in the table. 
        The lock is acquired to prevent concurrent modifications to the data, ensuring data integrity and consistency.

        The transaction remains open until it is explicitly committed or rolled back. 
        It is the caller's responsibility to manage the transaction and ensure it is properly closed.

        Note: This method is typically used in scenarios where exclusive access to the data is required, such as during data updates or deletes.

        """
        self.new_connection.set_autocommit(False)
        # Start a blocking transaction. At some point,
        # end_blocking_transaction() should be called.
        self.cursor = self.new_connection.cursor()
        sql = "SELECT * FROM %(db_table)s %(for_update)s;" % {
            "db_table": Person._meta.db_table,
            "for_update": self.new_connection.ops.for_update_sql(),
        }
        self.cursor.execute(sql, ())
        self.cursor.fetchone()

    def end_blocking_transaction(self):
        # Roll back the blocking transaction.
        self.cursor.close()
        self.new_connection.rollback()
        self.new_connection.set_autocommit(True)

    def has_for_update_sql(self, queries, **kwargs):
        # Examine the SQL that was executed to determine whether it
        # contains the 'SELECT..FOR UPDATE' stanza.
        """
        Checks if any SQL query in the given list contains a \"FOR UPDATE\" SQL snippet.

        :param queries: A list of queries where each query is a dictionary containing the SQL string.
        :param kwargs: Additional keyword arguments to customize the \"FOR UPDATE\" SQL snippet.
        :return: True if any query contains the \"FOR UPDATE\" SQL snippet, False otherwise.
        """
        for_update_sql = connection.ops.for_update_sql(**kwargs)
        return any(for_update_sql in query["sql"] for query in queries)

    @skipUnlessDBFeature("has_select_for_update")
    def test_for_update_sql_generated(self):
        """
        The backend's FOR UPDATE variant appears in
        generated SQL when select_for_update is invoked.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(Person.objects.select_for_update())
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries))

    @skipUnlessDBFeature("has_select_for_update_nowait")
    def test_for_update_sql_generated_nowait(self):
        """
        The backend's FOR UPDATE NOWAIT variant appears in
        generated SQL when select_for_update is invoked.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(Person.objects.select_for_update(nowait=True))
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, nowait=True))

    @skipUnlessDBFeature("has_select_for_update_skip_locked")
    def test_for_update_sql_generated_skip_locked(self):
        """
        The backend's FOR UPDATE SKIP LOCKED variant appears in
        generated SQL when select_for_update is invoked.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(Person.objects.select_for_update(skip_locked=True))
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, skip_locked=True))

    @skipUnlessDBFeature("has_select_for_no_key_update")
    def test_update_sql_generated_no_key(self):
        """
        The backend's FOR NO KEY UPDATE variant appears in generated SQL when
        select_for_update() is invoked.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(Person.objects.select_for_update(no_key=True))
        self.assertIs(self.has_for_update_sql(ctx.captured_queries, no_key=True), True)

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_generated_of(self):
        """
        The backend's FOR UPDATE OF variant appears in the generated SQL when
        select_for_update() is invoked.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                Person.objects.select_related(
                    "born__country",
                )
                .select_for_update(
                    of=("born__country",),
                )
                .select_for_update(of=("self", "born__country"))
            )
        features = connections["default"].features
        if features.select_for_update_of_column:
            expected = [
                'select_for_update_person"."id',
                'select_for_update_country"."entity_ptr_id',
            ]
        else:
            expected = ["select_for_update_person", "select_for_update_country"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_model_inheritance_generated_of(self):
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(EUCountry.objects.select_for_update(of=("self",)))
        if connection.features.select_for_update_of_column:
            expected = ['select_for_update_eucountry"."country_ptr_id']
        else:
            expected = ["select_for_update_eucountry"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_model_inheritance_ptr_generated_of(self):
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                EUCountry.objects.select_for_update(
                    of=(
                        "self",
                        "country_ptr",
                    )
                )
            )
        if connection.features.select_for_update_of_column:
            expected = [
                'select_for_update_eucountry"."country_ptr_id',
                'select_for_update_country"."entity_ptr_id',
            ]
        else:
            expected = ["select_for_update_eucountry", "select_for_update_country"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_related_model_inheritance_generated_of(self):
        """

        Tests the 'select_for_update' method with 'of' argument on a model with related model inheritance.

        Verifies that the 'select_for_update' method generates the correct SQL query with 'OF' clause
        when applied to a model that has a related model with inheritance. The test checks the generated
        SQL query for correctness, considering database features that support column-level locking or
        table-level locking for the 'OF' clause.

        The test evaluates the query generated by the 'select_for_update' method with the 'of' argument
        set to include the related model, ensuring that the resulting SQL query correctly includes the
        required models and columns in the 'FOR UPDATE OF' clause.

        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                EUCity.objects.select_related("country").select_for_update(
                    of=("self", "country"),
                )
            )
        if connection.features.select_for_update_of_column:
            expected = [
                'select_for_update_eucity"."id',
                'select_for_update_eucountry"."country_ptr_id',
            ]
        else:
            expected = ["select_for_update_eucity", "select_for_update_eucountry"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_model_inheritance_nested_ptr_generated_of(self):
        """
        .Tests the SQL query generated by `select_for_update` method when using model inheritance and nested pointers.

        This test case ensures that the `select_for_update` method correctly generates SQL queries for models that use inheritance and nested pointers. It verifies that the queries are generated with the correct table and column names, taking into account the database feature of selecting for update of specific columns. The test covers both cases where the database supports selecting for update of specific columns and where it does not.
        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                EUCity.objects.select_related("country").select_for_update(
                    of=(
                        "self",
                        "country__country_ptr",
                    ),
                )
            )
        if connection.features.select_for_update_of_column:
            expected = [
                'select_for_update_eucity"."id',
                'select_for_update_country"."entity_ptr_id',
            ]
        else:
            expected = ["select_for_update_eucity", "select_for_update_country"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_multilevel_model_inheritance_ptr_generated_of(self):
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                EUCountry.objects.select_for_update(
                    of=("country_ptr", "country_ptr__entity_ptr"),
                )
            )
        if connection.features.select_for_update_of_column:
            expected = [
                'select_for_update_country"."entity_ptr_id',
                'select_for_update_entity"."id',
            ]
        else:
            expected = ["select_for_update_country", "select_for_update_entity"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_sql_model_proxy_generated_of(self):
        """

        Tests the generation of SQL queries when using select_for_update with of parameter on model proxy objects.

        This test case verifies that the select_for_update method generates the correct SQL query
        with the \"of\" parameter when used on a model proxy object that is related to another model.
        The test checks if the generated SQL query correctly locks the related model (\"country\") 
        instead of the model proxy itself (\"CityCountryProxy\").

        The test is skipped unless the database feature 'has_select_for_update_of' is supported.

        The test validates the generated SQL query against expected query patterns, 
        taking into account the database dialect's quoting rules.

        """
        with transaction.atomic(), CaptureQueriesContext(connection) as ctx:
            list(
                CityCountryProxy.objects.select_related("country").select_for_update(
                    of=("country",),
                )
            )
        if connection.features.select_for_update_of_column:
            expected = ['select_for_update_country"."entity_ptr_id']
        else:
            expected = ["select_for_update_country"]
        expected = [connection.ops.quote_name(value) for value in expected]
        self.assertTrue(self.has_for_update_sql(ctx.captured_queries, of=expected))

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_of_followed_by_values(self):
        """
        Tests the functionality of the select_for_update method with the of parameter 
        when retrieving values from the database. This test checks that when 'self' is 
        specified as the of parameter, it correctly locks the specified rows until the 
        end of the transaction, allowing for atomic updates.

        The test verifies that the values retrieved from the Person model match the 
        expected values, ensuring the lock is applied correctly and data consistency is 
        maintained.

        Requires the 'has_select_for_update_of' database feature to be supported.
        """
        with transaction.atomic():
            values = list(Person.objects.select_for_update(of=("self",)).values("pk"))
        self.assertEqual(values, [{"pk": self.person.pk}])

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_of_followed_by_values_list(self):
        with transaction.atomic():
            values = list(
                Person.objects.select_for_update(of=("self",)).values_list("pk")
            )
        self.assertEqual(values, [(self.person.pk,)])

    @skipUnlessDBFeature("has_select_for_update_of")
    def test_for_update_of_self_when_self_is_not_selected(self):
        """
        select_for_update(of=['self']) when the only columns selected are from
        related tables.
        """
        with transaction.atomic():
            values = list(
                Person.objects.select_related("born")
                .select_for_update(of=("self",))
                .values("born__name")
            )
        self.assertEqual(values, [{"born__name": self.city1.name}])

    @skipUnlessDBFeature(
        "has_select_for_update_of",
        "supports_select_for_update_with_limit",
    )
    def test_for_update_of_with_exists(self):
        with transaction.atomic():
            qs = Person.objects.select_for_update(of=("self", "born"))
            self.assertIs(qs.exists(), True)

    @skipUnlessDBFeature("has_select_for_update_nowait", "supports_transactions")
    def test_nowait_raises_error_on_block(self):
        """
        If nowait is specified, we expect an error to be raised rather
        than blocking.
        """
        self.start_blocking_transaction()
        status = []

        thread = threading.Thread(
            target=self.run_select_for_update,
            args=(status,),
            kwargs={"nowait": True},
        )

        thread.start()
        time.sleep(1)
        thread.join()
        self.end_blocking_transaction()
        self.assertIsInstance(status[-1], DatabaseError)

    @skipUnlessDBFeature("has_select_for_update_skip_locked", "supports_transactions")
    def test_skip_locked_skips_locked_rows(self):
        """
        If skip_locked is specified, the locked row is skipped resulting in
        Person.DoesNotExist.
        """
        self.start_blocking_transaction()
        status = []
        thread = threading.Thread(
            target=self.run_select_for_update,
            args=(status,),
            kwargs={"skip_locked": True},
        )
        thread.start()
        time.sleep(1)
        thread.join()
        self.end_blocking_transaction()
        self.assertIsInstance(status[-1], Person.DoesNotExist)

    @skipIfDBFeature("has_select_for_update_nowait")
    @skipUnlessDBFeature("has_select_for_update")
    def test_unsupported_nowait_raises_error(self):
        """
        NotSupportedError is raised if a SELECT...FOR UPDATE NOWAIT is run on
        a database backend that supports FOR UPDATE but not NOWAIT.
        """
        with self.assertRaisesMessage(
            NotSupportedError, "NOWAIT is not supported on this database backend."
        ):
            with transaction.atomic():
                Person.objects.select_for_update(nowait=True).get()

    @skipIfDBFeature("has_select_for_update_skip_locked")
    @skipUnlessDBFeature("has_select_for_update")
    def test_unsupported_skip_locked_raises_error(self):
        """
        NotSupportedError is raised if a SELECT...FOR UPDATE SKIP LOCKED is run
        on a database backend that supports FOR UPDATE but not SKIP LOCKED.
        """
        with self.assertRaisesMessage(
            NotSupportedError, "SKIP LOCKED is not supported on this database backend."
        ):
            with transaction.atomic():
                Person.objects.select_for_update(skip_locked=True).get()

    @skipIfDBFeature("has_select_for_update_of")
    @skipUnlessDBFeature("has_select_for_update")
    def test_unsupported_of_raises_error(self):
        """
        NotSupportedError is raised if a SELECT...FOR UPDATE OF... is run on
        a database backend that supports FOR UPDATE but not OF.
        """
        msg = "FOR UPDATE OF is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            with transaction.atomic():
                Person.objects.select_for_update(of=("self",)).get()

    @skipIfDBFeature("has_select_for_no_key_update")
    @skipUnlessDBFeature("has_select_for_update")
    def test_unsuported_no_key_raises_error(self):
        """
        NotSupportedError is raised if a SELECT...FOR NO KEY UPDATE... is run
        on a database backend that supports FOR UPDATE but not NO KEY.
        """
        msg = "FOR NO KEY UPDATE is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            with transaction.atomic():
                Person.objects.select_for_update(no_key=True).get()

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_of")
    def test_unrelated_of_argument_raises_error(self):
        """
        FieldError is raised if a non-relation field is specified in of=(...).
        """
        msg = (
            "Invalid field name(s) given in select_for_update(of=(...)): %s. "
            "Only relational fields followed in the query are allowed. "
            "Choices are: self, born, born__country, "
            "born__country__entity_ptr."
        )
        invalid_of = [
            ("nonexistent",),
            ("name",),
            ("born__nonexistent",),
            ("born__name",),
            ("born__nonexistent", "born__name"),
        ]
        for of in invalid_of:
            with self.subTest(of=of):
                with self.assertRaisesMessage(FieldError, msg % ", ".join(of)):
                    with transaction.atomic():
                        Person.objects.select_related(
                            "born__country"
                        ).select_for_update(of=of).get()

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_of")
    def test_related_but_unselected_of_argument_raises_error(self):
        """
        FieldError is raised if a relation field that is not followed in the
        query is specified in of=(...).
        """
        msg = (
            "Invalid field name(s) given in select_for_update(of=(...)): %s. "
            "Only relational fields followed in the query are allowed. "
            "Choices are: self, born, profile."
        )
        for name in ["born__country", "died", "died__country"]:
            with self.subTest(name=name):
                with self.assertRaisesMessage(FieldError, msg % name):
                    with transaction.atomic():
                        Person.objects.select_related("born", "profile").exclude(
                            profile=None
                        ).select_for_update(of=(name,)).get()

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_of")
    def test_model_inheritance_of_argument_raises_error_ptr_in_choices(self):
        msg = (
            "Invalid field name(s) given in select_for_update(of=(...)): "
            "name. Only relational fields followed in the query are allowed. "
            "Choices are: self, %s."
        )
        with self.assertRaisesMessage(
            FieldError,
            msg % "country, country__country_ptr, country__country_ptr__entity_ptr",
        ):
            with transaction.atomic():
                EUCity.objects.select_related(
                    "country",
                ).select_for_update(of=("name",)).get()
        with self.assertRaisesMessage(
            FieldError, msg % "country_ptr, country_ptr__entity_ptr"
        ):
            with transaction.atomic():
                EUCountry.objects.select_for_update(of=("name",)).get()

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_of")
    def test_model_proxy_of_argument_raises_error_proxy_field_in_choices(self):
        msg = (
            "Invalid field name(s) given in select_for_update(of=(...)): "
            "name. Only relational fields followed in the query are allowed. "
            "Choices are: self, country, country__entity_ptr."
        )
        with self.assertRaisesMessage(FieldError, msg):
            with transaction.atomic():
                CityCountryProxy.objects.select_related(
                    "country",
                ).select_for_update(of=("name",)).get()

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_of")
    def test_reverse_one_to_one_of_arguments(self):
        """
        Reverse OneToOneFields may be included in of=(...) as long as NULLs
        are excluded because LEFT JOIN isn't allowed in SELECT FOR UPDATE.
        """
        with transaction.atomic():
            person = (
                Person.objects.select_related(
                    "profile",
                )
                .exclude(profile=None)
                .select_for_update(of=("profile",))
                .get()
            )
            self.assertEqual(person.profile, self.person_profile)

    @skipUnlessDBFeature("has_select_for_update")
    def test_for_update_after_from(self):
        """

        Tests the behavior of the select_for_update method when used after a FROM clause.

        This test case checks that the 'FOR UPDATE WHERE' clause is correctly added to the query
        when select_for_update is called on a QuerySet. It simulates a scenario where the
        database connection features support the 'for_update_after_from' attribute, and verifies
        that the resulting SQL query contains the expected 'FOR UPDATE WHERE' clause.

        The test is skipped if the database connection does not support the 'has_select_for_update' feature.

        :return: None

        """
        features_class = connections["default"].features.__class__
        attribute_to_patch = "%s.%s.for_update_after_from" % (
            features_class.__module__,
            features_class.__name__,
        )
        with mock.patch(attribute_to_patch, return_value=True):
            with transaction.atomic():
                self.assertIn(
                    "FOR UPDATE WHERE",
                    str(Person.objects.filter(name="foo").select_for_update().query),
                )

    @skipUnlessDBFeature("has_select_for_update", "supports_transactions")
    def test_for_update_requires_transaction(self):
        """
        A TransactionManagementError is raised
        when a select_for_update query is executed outside of a transaction.
        """
        msg = "select_for_update cannot be used outside of a transaction."
        with self.assertRaisesMessage(transaction.TransactionManagementError, msg):
            list(Person.objects.select_for_update())

    @skipUnlessDBFeature("has_select_for_update", "supports_transactions")
    def test_for_update_requires_transaction_only_in_execution(self):
        """
        No TransactionManagementError is raised
        when select_for_update is invoked outside of a transaction -
        only when the query is executed.
        """
        people = Person.objects.select_for_update()
        msg = "select_for_update cannot be used outside of a transaction."
        with self.assertRaisesMessage(transaction.TransactionManagementError, msg):
            list(people)

    @skipUnlessDBFeature("supports_select_for_update_with_limit")
    def test_select_for_update_with_limit(self):
        """

        Tests the functionality of selecting objects for update with a limit.

        This test case verifies that the database correctly locks a subset of objects
        for update, allowing for exclusive access to those objects. The test creates
        a new person object and then uses a transaction to select a limited subset
        of objects for update, checking that the locked object matches the one created.

        The test requires a database that supports selecting for update with a limit.

        """
        other = Person.objects.create(name="Grappeli", born=self.city1, died=self.city2)
        with transaction.atomic():
            qs = list(Person.objects.order_by("pk").select_for_update()[1:2])
            self.assertEqual(qs[0], other)

    @skipIfDBFeature("supports_select_for_update_with_limit")
    def test_unsupported_select_for_update_with_limit(self):
        msg = (
            "LIMIT/OFFSET is not supported with select_for_update on this database "
            "backend."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with transaction.atomic():
                list(Person.objects.order_by("pk").select_for_update()[1:2])

    def run_select_for_update(self, status, **kwargs):
        """
        Utility method that runs a SELECT FOR UPDATE against all
        Person instances. After the select_for_update, it attempts
        to update the name of the only record, save, and commit.

        This function expects to run in a separate thread.
        """
        status.append("started")
        try:
            # We need to enter transaction management again, as this is done on
            # per-thread basis
            with transaction.atomic():
                person = Person.objects.select_for_update(**kwargs).get()
                person.name = "Fred"
                person.save()
        except (DatabaseError, Person.DoesNotExist) as e:
            status.append(e)
        finally:
            # This method is run in a separate thread. It uses its own
            # database connection. Close it without waiting for the GC.
            connection.close()

    @skipUnlessDBFeature("has_select_for_update")
    @skipUnlessDBFeature("supports_transactions")
    def test_block(self):
        """
        A thread running a select_for_update that accesses rows being touched
        by a similar operation on another connection blocks correctly.
        """
        # First, let's start the transaction in our thread.
        self.start_blocking_transaction()

        # Now, try it again using the ORM's select_for_update
        # facility. Do this in a separate thread.
        status = []
        thread = threading.Thread(target=self.run_select_for_update, args=(status,))

        # The thread should immediately block, but we'll sleep
        # for a bit to make sure.
        thread.start()
        sanity_count = 0
        while len(status) != 1 and sanity_count < 10:
            sanity_count += 1
            time.sleep(1)
        if sanity_count >= 10:
            raise ValueError("Thread did not run and block")

        # Check the person hasn't been updated. Since this isn't
        # using FOR UPDATE, it won't block.
        p = Person.objects.get(pk=self.person.pk)
        self.assertEqual("Reinhardt", p.name)

        # When we end our blocking transaction, our thread should
        # be able to continue.
        self.end_blocking_transaction()
        thread.join(5.0)

        # Check the thread has finished. Assuming it has, we should
        # find that it has updated the person's name.
        self.assertFalse(thread.is_alive())

        # We must commit the transaction to ensure that MySQL gets a fresh read,
        # since by default it runs in REPEATABLE READ mode
        transaction.commit()

        p = Person.objects.get(pk=self.person.pk)
        self.assertEqual("Fred", p.name)

    @skipUnlessDBFeature("has_select_for_update", "supports_transactions")
    def test_raw_lock_not_available(self):
        """
        Running a raw query which can't obtain a FOR UPDATE lock raises
        the correct exception
        """
        self.start_blocking_transaction()

        def raw(status):
            try:
                list(
                    Person.objects.raw(
                        "SELECT * FROM %s %s"
                        % (
                            Person._meta.db_table,
                            connection.ops.for_update_sql(nowait=True),
                        )
                    )
                )
            except DatabaseError as e:
                status.append(e)
            finally:
                # This method is run in a separate thread. It uses its own
                # database connection. Close it without waiting for the GC.
                # Connection cannot be closed on Oracle because cursor is still
                # open.
                if connection.vendor != "oracle":
                    connection.close()

        status = []
        thread = threading.Thread(target=raw, kwargs={"status": status})
        thread.start()
        time.sleep(1)
        thread.join()
        self.end_blocking_transaction()
        self.assertIsInstance(status[-1], DatabaseError)

    @skipUnlessDBFeature("has_select_for_update")
    @override_settings(DATABASE_ROUTERS=[TestRouter()])
    def test_select_for_update_on_multidb(self):
        query = Person.objects.select_for_update()
        self.assertEqual(router.db_for_write(Person), query.db)

    @skipUnlessDBFeature("has_select_for_update")
    def test_select_for_update_with_get(self):
        with transaction.atomic():
            person = Person.objects.select_for_update().get(name="Reinhardt")
        self.assertEqual(person.name, "Reinhardt")

    def test_nowait_and_skip_locked(self):
        with self.assertRaisesMessage(
            ValueError, "The nowait option cannot be used with skip_locked."
        ):
            Person.objects.select_for_update(nowait=True, skip_locked=True)

    def test_ordered_select_for_update(self):
        """
        Subqueries should respect ordering as an ORDER BY clause may be useful
        to specify a row locking order to prevent deadlocks (#27193).
        """
        with transaction.atomic():
            qs = Person.objects.filter(
                id__in=Person.objects.order_by("-id").select_for_update()
            )
            self.assertIn("ORDER BY", str(qs.query))
