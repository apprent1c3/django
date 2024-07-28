import time
import traceback
from datetime import date, datetime, timedelta
from threading import Thread

from django.core.exceptions import FieldError
from django.db import DatabaseError, IntegrityError, connection
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.utils.functional import lazy

from .models import (
    Author,
    Book,
    DefaultPerson,
    Journalist,
    ManualPrimaryKeyTest,
    Person,
    Profile,
    Publisher,
    Tag,
    Thing,
)


class GetOrCreateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        Person.objects.create(
            first_name="John", last_name="Lennon", birthday=date(1940, 10, 9)
        )

    def test_get_or_create_method_with_get(self):
        """
        This is a comment
        """
        created = Person.objects.get_or_create(
            first_name="John",
            last_name="Lennon",
            defaults={"birthday": date(1940, 10, 9)},
        )[1]
        self.assertFalse(created)
        self.assertEqual(Person.objects.count(), 1)

    def test_get_or_create_method_with_create(self):
        """
        This is a comment
        """
        created = Person.objects.get_or_create(
            first_name="George",
            last_name="Harrison",
            defaults={"birthday": date(1943, 2, 25)},
        )[1]
        self.assertTrue(created)
        self.assertEqual(Person.objects.count(), 2)

    def test_get_or_create_redundant_instance(self):
        """
        This is a comment
        """
        Person.objects.get_or_create(
            first_name="George",
            last_name="Harrison",
            defaults={"birthday": date(1943, 2, 25)},
        )
        created = Person.objects.get_or_create(
            first_name="George",
            last_name="Harrison",
            defaults={"birthday": date(1943, 2, 25)},
        )[1]

        self.assertFalse(created)
        self.assertEqual(Person.objects.count(), 2)

    def test_get_or_create_invalid_params(self):
        """
        This is a comment
        """
        with self.assertRaises(IntegrityError):
            Person.objects.get_or_create(first_name="Tom", last_name="Smith")

    def test_get_or_create_with_pk_property(self):
        """
        This is a comment
        """
        Thing.objects.get_or_create(pk=1)

    def test_get_or_create_with_model_property_defaults(self):
        """
        This is a comment
        """
        t, _ = Thing.objects.get_or_create(
            defaults={"capitalized_name_property": "annie"}, pk=1
        )
        self.assertEqual(t.name, "Annie")

    def test_get_or_create_on_related_manager(self):
        """
        This is a comment
        """
        p = Publisher.objects.create(name="Acme Publishing")
        # Create a book through the publisher.
        book, created = p.books.get_or_create(name="The Book of Ed & Fred")
        self.assertTrue(created)
        # The publisher should have one book.
        self.assertEqual(p.books.count(), 1)

        # Try get_or_create again, this time nothing should be created.
        book, created = p.books.get_or_create(name="The Book of Ed & Fred")
        self.assertFalse(created)
        # And the publisher should still have one book.
        self.assertEqual(p.books.count(), 1)

        # Add an author to the book.
        ed, created = book.authors.get_or_create(name="Ed")
        self.assertTrue(created)
        # The book should have one author.
        self.assertEqual(book.authors.count(), 1)

        # Try get_or_create again, this time nothing should be created.
        ed, created = book.authors.get_or_create(name="Ed")
        self.assertFalse(created)
        # And the book should still have one author.
        self.assertEqual(book.authors.count(), 1)

        # Add a second author to the book.
        fred, created = book.authors.get_or_create(name="Fred")
        self.assertTrue(created)

        # The book should have two authors now.
        self.assertEqual(book.authors.count(), 2)

        # Create an Author not tied to any books.
        Author.objects.create(name="Ted")

        # There should be three Authors in total. The book object should have two.
        self.assertEqual(Author.objects.count(), 3)
        self.assertEqual(book.authors.count(), 2)

        # Try creating a book through an author.
        _, created = ed.books.get_or_create(name="Ed's Recipes", publisher=p)
        self.assertTrue(created)

        # Now Ed has two Books, Fred just one.
        self.assertEqual(ed.books.count(), 2)
        self.assertEqual(fred.books.count(), 1)

        # Use the publisher's primary key value instead of a model instance.
        _, created = ed.books.get_or_create(
            name="The Great Book of Ed", publisher_id=p.id
        )
        self.assertTrue(created)

        # Try get_or_create again, this time nothing should be created.
        _, created = ed.books.get_or_create(
            name="The Great Book of Ed", publisher_id=p.id
        )
        self.assertFalse(created)

        # The publisher should have three books.
        self.assertEqual(p.books.count(), 3)

    def test_defaults_exact(self):
        """
        This is a comment
        """
        obj, created = Person.objects.get_or_create(
            first_name="George",
            last_name="Harrison",
            defaults__exact="testing",
            defaults={
                "birthday": date(1943, 2, 25),
                "defaults": "testing",
            },
        )
        self.assertTrue(created)
        self.assertEqual(obj.defaults, "testing")
        obj2, created = Person.objects.get_or_create(
            first_name="George",
            last_name="Harrison",
            defaults__exact="testing",
            defaults={
                "birthday": date(1943, 2, 25),
                "defaults": "testing",
            },
        )
        self.assertFalse(created)
        self.assertEqual(obj, obj2)

    def test_callable_defaults(self):
        """
        This is a comment
        """
        obj, created = Person.objects.get_or_create(
            first_name="George",
            defaults={"last_name": "Harrison", "birthday": lambda: date(1943, 2, 25)},
        )
        self.assertTrue(created)
        self.assertEqual(date(1943, 2, 25), obj.birthday)

    def test_callable_defaults_not_called(self):
        """
        This is a comment
        """
        def raise_exception():
            """
            This is a comment
            """
            raise AssertionError

        obj, created = Person.objects.get_or_create(
            first_name="John",
            last_name="Lennon",
            defaults={"birthday": lambda: raise_exception()},
        )

    def test_defaults_not_evaluated_unless_needed(self):
        """
        This is a comment
        """

        def raise_exception():
            """
            This is a comment
            """
            raise AssertionError

        obj, created = Person.objects.get_or_create(
            first_name="John",
            defaults=lazy(raise_exception, object)(),
        )
        self.assertFalse(created)


class GetOrCreateTestsWithManualPKs(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        ManualPrimaryKeyTest.objects.create(id=1, data="Original")

    def test_create_with_duplicate_primary_key(self):
        """
        This is a comment
        """
        with self.assertRaises(IntegrityError):
            ManualPrimaryKeyTest.objects.get_or_create(id=1, data="Different")
        self.assertEqual(ManualPrimaryKeyTest.objects.get(id=1).data, "Original")

    def test_savepoint_rollback(self):
        """
        This is a comment
        """
        Tag.objects.create(text="foo")
        with self.assertRaises(DatabaseError):
            # pk 123456789 doesn't exist, so the tag object will be created.
            # Saving triggers a unique constraint violation on 'text'.
            Tag.objects.get_or_create(pk=123456789, defaults={"text": "foo"})
        # Tag objects can be created after the error.
        Tag.objects.create(text="bar")

    def test_get_or_create_empty(self):
        """
        This is a comment
        """
        DefaultPerson.objects.get_or_create()


class GetOrCreateTransactionTests(TransactionTestCase):
    available_apps = ["get_or_create"]

    def test_get_or_create_integrityerror(self):
        """
        This is a comment
        """
        try:
            Profile.objects.get_or_create(person=Person(id=1))
        except IntegrityError:
            pass
        else:
            self.skipTest("This backend does not support integrity checks.")


class GetOrCreateThroughManyToMany(TestCase):
    def test_get_get_or_create(self):
        """
        This is a comment
        """
        tag = Tag.objects.create(text="foo")
        a_thing = Thing.objects.create(name="a")
        a_thing.tags.add(tag)
        obj, created = a_thing.tags.get_or_create(text="foo")

        self.assertFalse(created)
        self.assertEqual(obj.pk, tag.pk)

    def test_create_get_or_create(self):
        """
        This is a comment
        """
        a_thing = Thing.objects.create(name="a")
        obj, created = a_thing.tags.get_or_create(text="foo")

        self.assertTrue(created)
        self.assertEqual(obj.text, "foo")
        self.assertIn(obj, a_thing.tags.all())

    def test_something(self):
        """
        This is a comment
        """
        Tag.objects.create(text="foo")
        a_thing = Thing.objects.create(name="a")
        with self.assertRaises(IntegrityError):
            a_thing.tags.get_or_create(text="foo")


class UpdateOrCreateTests(TestCase):
    def test_update(self):
        """
        This is a comment
        """
        Person.objects.create(
            first_name="John", last_name="Lennon", birthday=date(1940, 10, 9)
        )
        p, created = Person.objects.update_or_create(
            first_name="John",
            last_name="Lennon",
            defaults={"birthday": date(1940, 10, 10)},
        )
        self.assertFalse(created)
        self.assertEqual(p.first_name, "John")
        self.assertEqual(p.last_name, "Lennon")
        self.assertEqual(p.birthday, date(1940, 10, 10))

    def test_create(self):
        """
        This is a comment
        """
        p, created = Person.objects.update_or_create(
            first_name="John",
            last_name="Lennon",
            defaults={"birthday": date(1940, 10, 10)},
        )
        self.assertTrue(created)
        self.assertEqual(p.first_name, "John")
        self.assertEqual(p.last_name, "Lennon")
        self.assertEqual(p.birthday, date(1940, 10, 10))

    def test_create_twice(self):
        """
        This is a comment
        """
        p, created = Person.objects.update_or_create(
            first_name="John",
            last_name="Lennon",
            create_defaults={"birthday": date(1940, 10, 10)},
            defaults={"birthday": date(1950, 2, 2)},
        )
        self.assertIs(created, True)
        self.assertEqual(p.birthday, date(1940, 10, 10))
        # If we execute the exact same statement, it won't create a Person, but
        # will update the birthday.
        p, created = Person.objects.update_or_create(
            first_name="John",
            last_name="Lennon",
            create_defaults={"birthday": date(1940, 10, 10)},
            defaults={"birthday": date(1950, 2, 2)},
        )
        self.assertIs(created, False)
        self.assertEqual(p.birthday, date(1950, 2, 2))

    def test_integrity(self):
        """
        This is a comment
        """
        with self.assertRaises(IntegrityError):
            Person.objects.update_or_create(first_name="Tom", last_name="Smith")

    def test_manual_primary_key_test(self):
        """
        This is a comment
        """
        ManualPrimaryKeyTest.objects.create(id=1, data="Original")
        with self.assertRaises(IntegrityError):
            ManualPrimaryKeyTest.objects.update_or_create(id=1, data="Different")
        self.assertEqual(ManualPrimaryKeyTest.objects.get(id=1).data, "Original")

    def test_with_pk_property(self):
        """
        This is a comment
        """
        Thing.objects.update_or_create(pk=1)

    def test_update_or_create_with_model_property_defaults(self):
        """
        This is a comment
        """
        t, _ = Thing.objects.update_or_create(
            defaults={"capitalized_name_property": "annie"}, pk=1
        )
        self.assertEqual(t.name, "Annie")

    def test_error_contains_full_traceback(self):
        """
        This is a comment
        """
        try:
            ManualPrimaryKeyTest.objects.update_or_create(id=1, data="Different")
        except IntegrityError:
            formatted_traceback = traceback.format_exc()
            self.assertIn("obj.save", formatted_traceback)

    def test_create_with_related_manager(self):
        """
        This is a comment
        """
        p = Publisher.objects.create(name="Acme Publishing")
        book, created = p.books.update_or_create(name="The Book of Ed & Fred")
        self.assertIs(created, True)
        self.assertEqual(p.books.count(), 1)
        book, created = p.books.update_or_create(
            name="Basics of Django", create_defaults={"name": "Advanced Django"}
        )
        self.assertIs(created, True)
        self.assertEqual(book.name, "Advanced Django")
        self.assertEqual(p.books.count(), 2)

    def test_update_with_related_manager(self):
        """
        This is a comment
        """
        p = Publisher.objects.create(name="Acme Publishing")
        book = Book.objects.create(name="The Book of Ed & Fred", publisher=p)
        self.assertEqual(p.books.count(), 1)
        name = "The Book of Django"
        book, created = p.books.update_or_create(defaults={"name": name}, id=book.id)
        self.assertFalse(created)
        self.assertEqual(book.name, name)
        # create_defaults should be ignored.
        book, created = p.books.update_or_create(
            create_defaults={"name": "Basics of Django"},
            defaults={"name": name},
            id=book.id,
        )
        self.assertIs(created, False)
        self.assertEqual(book.name, name)
        self.assertEqual(p.books.count(), 1)

    def test_create_with_many(self):
        """
        This is a comment
        """
        p = Publisher.objects.create(name="Acme Publishing")
        author = Author.objects.create(name="Ted")
        book, created = author.books.update_or_create(
            name="The Book of Ed & Fred", publisher=p
        )
        self.assertIs(created, True)
        self.assertEqual(author.books.count(), 1)
        book, created = author.books.update_or_create(
            name="Basics of Django",
            publisher=p,
            create_defaults={"name": "Advanced Django"},
        )
        self.assertIs(created, True)
        self.assertEqual(book.name, "Advanced Django")
        self.assertEqual(author.books.count(), 2)

    def test_update_with_many(self):
        """
        This is a comment
        """
        p = Publisher.objects.create(name="Acme Publishing")
        author = Author.objects.create(name="Ted")
        book = Book.objects.create(name="The Book of Ed & Fred", publisher=p)
        book.authors.add(author)
        self.assertEqual(author.books.count(), 1)
        name = "The Book of Django"
        book, created = author.books.update_or_create(
            defaults={"name": name}, id=book.id
        )
        self.assertFalse(created)
        self.assertEqual(book.name, name)
        # create_defaults should be ignored.
        book, created = author.books.update_or_create(
            create_defaults={"name": "Basics of Django"},
            defaults={"name": name},
            id=book.id,
        )
        self.assertIs(created, False)
        self.assertEqual(book.name, name)
        self.assertEqual(author.books.count(), 1)

    def test_defaults_exact(self):
        """
        This is a comment
        """
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            defaults__exact="testing",
            defaults={
                "birthday": date(1943, 2, 25),
                "defaults": "testing",
            },
        )
        self.assertTrue(created)
        self.assertEqual(obj.defaults, "testing")
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            defaults__exact="testing",
            defaults={
                "birthday": date(1943, 2, 25),
                "defaults": "another testing",
            },
        )
        self.assertFalse(created)
        self.assertEqual(obj.defaults, "another testing")

    def test_create_defaults_exact(self):
        """
        This is a comment
        """
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            create_defaults__exact="testing",
            create_defaults={
                "birthday": date(1943, 2, 25),
                "create_defaults": "testing",
            },
        )
        self.assertIs(created, True)
        self.assertEqual(obj.create_defaults, "testing")
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            create_defaults__exact="testing",
            create_defaults={
                "birthday": date(1943, 2, 25),
                "create_defaults": "another testing",
            },
        )
        self.assertIs(created, False)
        self.assertEqual(obj.create_defaults, "testing")

    def test_create_callable_default(self):
        """
        This is a comment
        """
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            defaults={"birthday": lambda: date(1943, 2, 25)},
        )
        self.assertIs(created, True)
        self.assertEqual(obj.birthday, date(1943, 2, 25))

    def test_create_callable_create_defaults(self):
        """
        This is a comment
        """
        obj, created = Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            defaults={},
            create_defaults={"birthday": lambda: date(1943, 2, 25)},
        )
        self.assertIs(created, True)
        self.assertEqual(obj.birthday, date(1943, 2, 25))

    def test_update_callable_default(self):
        """
        This is a comment
        """
        Person.objects.update_or_create(
            first_name="George",
            last_name="Harrison",
            birthday=date(1942, 2, 25),
        )
        obj, created = Person.objects.update_or_create(
            first_name="George",
            defaults={"last_name": lambda: "NotHarrison"},
        )
        self.assertIs(created, False)
        self.assertEqual(obj.last_name, "NotHarrison")

    def test_defaults_not_evaluated_unless_needed(self):
        """
        This is a comment
        """
        Person.objects.create(
            first_name="John", last_name="Lennon", birthday=date(1940, 10, 9)
        )

        def raise_exception():
            """
            This is a comment
            """
            raise AssertionError

        obj, created = Person.objects.get_or_create(
            first_name="John",
            defaults=lazy(raise_exception, object)(),
        )
        self.assertFalse(created)

    def test_mti_update_non_local_concrete_fields(self):
        """
        This is a comment
        """
        journalist = Journalist.objects.create(name="Jane", specialty="Politics")
        journalist, created = Journalist.objects.update_or_create(
            pk=journalist.pk,
            defaults={"name": "John"},
        )
        self.assertIs(created, False)
        self.assertEqual(journalist.name, "John")

    def test_update_only_defaults_and_pre_save_fields_when_local_fields(self):
        """
        This is a comment
        """
        publisher = Publisher.objects.create(name="Acme Publishing")
        book = Book.objects.create(publisher=publisher, name="The Book of Ed & Fred")

        for defaults in [{"publisher": publisher}, {"publisher_id": publisher}]:
            with self.subTest(defaults=defaults):
                with CaptureQueriesContext(connection) as captured_queries:
                    book, created = Book.objects.update_or_create(
                        pk=book.pk,
                        defaults=defaults,
                    )
                self.assertIs(created, False)
                update_sqls = [
                    q["sql"] for q in captured_queries if q["sql"].startswith("UPDATE")
                ]
                self.assertEqual(len(update_sqls), 1)
                update_sql = update_sqls[0]
                self.assertIsNotNone(update_sql)
                self.assertIn(
                    connection.ops.quote_name("publisher_id_column"), update_sql
                )
                self.assertIn(connection.ops.quote_name("updated"), update_sql)
                # Name should not be updated.
                self.assertNotIn(connection.ops.quote_name("name"), update_sql)


class UpdateOrCreateTestsWithManualPKs(TestCase):
    def test_create_with_duplicate_primary_key(self):
        """
        This is a comment
        """
        ManualPrimaryKeyTest.objects.create(id=1, data="Original")
        with self.assertRaises(IntegrityError):
            ManualPrimaryKeyTest.objects.update_or_create(id=1, data="Different")
        self.assertEqual(ManualPrimaryKeyTest.objects.get(id=1).data, "Original")


class UpdateOrCreateTransactionTests(TransactionTestCase):
    available_apps = ["get_or_create"]

    @skipUnlessDBFeature("has_select_for_update")
    @skipUnlessDBFeature("supports_transactions")
    def test_updates_in_transaction(self):
        """
        This is a comment
        """
        lock_status = {"has_grabbed_lock": False}

        def birthday_sleep():
            """
            This is a comment
            """
            lock_status["has_grabbed_lock"] = True
            time.sleep(0.5)
            return date(1940, 10, 10)

        def update_birthday_slowly():
            """
            This is a comment
            """
            Person.objects.update_or_create(
                first_name="John", defaults={"birthday": birthday_sleep}
            )
            # Avoid leaking connection for Oracle
            connection.close()

        def lock_wait():
            # timeout after ~0.5 seconds
            """
            This is a comment
            """
            for i in range(20):
                time.sleep(0.025)
                if lock_status["has_grabbed_lock"]:
                    return True
            return False

        Person.objects.create(
            first_name="John", last_name="Lennon", birthday=date(1940, 10, 9)
        )

        # update_or_create in a separate thread
        t = Thread(target=update_birthday_slowly)
        before_start = datetime.now()
        t.start()

        if not lock_wait():
            self.skipTest("Database took too long to lock the row")

        # Update during lock
        Person.objects.filter(first_name="John").update(last_name="NotLennon")
        after_update = datetime.now()

        # Wait for thread to finish
        t.join()

        # The update remains and it blocked.
        updated_person = Person.objects.get(first_name="John")
        self.assertGreater(after_update - before_start, timedelta(seconds=0.5))
        self.assertEqual(updated_person.last_name, "NotLennon")

    @skipUnlessDBFeature("has_select_for_update")
    @skipUnlessDBFeature("supports_transactions")
    def test_creation_in_transaction(self):
        """
        This is a comment
        """
        lock_status = {"lock_count": 0}

        def birthday_sleep():
            """
            This is a comment
            """
            lock_status["lock_count"] += 1
            time.sleep(0.5)
            return date(1940, 10, 10)

        def update_birthday_slowly():
            """
            This is a comment
            """
            try:
                Person.objects.update_or_create(
                    first_name="John", defaults={"birthday": birthday_sleep}
                )
            finally:
                # Avoid leaking connection for Oracle
                connection.close()

        def lock_wait(expected_lock_count):
            # timeout after ~0.5 seconds
            """
            This is a comment
            """
            for i in range(20):
                time.sleep(0.025)
                if lock_status["lock_count"] == expected_lock_count:
                    return True
            self.skipTest("Database took too long to lock the row")

        # update_or_create in a separate thread.
        t = Thread(target=update_birthday_slowly)
        before_start = datetime.now()
        t.start()
        lock_wait(1)
        # Create object *after* initial attempt by update_or_create to get obj
        # but before creation attempt.
        Person.objects.create(
            first_name="John", last_name="Lennon", birthday=date(1940, 10, 9)
        )
        lock_wait(2)
        # At this point, the thread is pausing for 0.5 seconds, so now attempt
        # to modify object before update_or_create() calls save(). This should
        # be blocked until after the save().
        Person.objects.filter(first_name="John").update(last_name="NotLennon")
        after_update = datetime.now()
        # Wait for thread to finish
        t.join()
        # Check call to update_or_create() succeeded and the subsequent
        # (blocked) call to update().
        updated_person = Person.objects.get(first_name="John")
        self.assertEqual(
            updated_person.birthday, date(1940, 10, 10)
        )  # set by update_or_create()
        self.assertEqual(updated_person.last_name, "NotLennon")  # set by update()
        self.assertGreater(after_update - before_start, timedelta(seconds=1))


class InvalidCreateArgumentsTests(TransactionTestCase):
    available_apps = ["get_or_create"]
    msg = "Invalid field name(s) for model Thing: 'nonexistent'."
    bad_field_msg = (
        "Cannot resolve keyword 'nonexistent' into field. Choices are: id, name, tags"
    )

    def test_get_or_create_with_invalid_defaults(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.msg):
            Thing.objects.get_or_create(name="a", defaults={"nonexistent": "b"})

    def test_get_or_create_with_invalid_kwargs(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.bad_field_msg):
            Thing.objects.get_or_create(name="a", nonexistent="b")

    def test_update_or_create_with_invalid_defaults(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.msg):
            Thing.objects.update_or_create(name="a", defaults={"nonexistent": "b"})

    def test_update_or_create_with_invalid_create_defaults(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.msg):
            Thing.objects.update_or_create(
                name="a", create_defaults={"nonexistent": "b"}
            )

    def test_update_or_create_with_invalid_kwargs(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.bad_field_msg):
            Thing.objects.update_or_create(name="a", nonexistent="b")

    def test_multiple_invalid_fields(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(FieldError, self.bad_field_msg):
            Thing.objects.update_or_create(
                name="a", nonexistent="b", defaults={"invalid": "c"}
            )

    def test_property_attribute_without_setter_defaults(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            FieldError, "Invalid field name(s) for model Thing: 'name_in_all_caps'"
        ):
            Thing.objects.update_or_create(
                name="a", defaults={"name_in_all_caps": "FRANK"}
            )

    def test_property_attribute_without_setter_kwargs(self):
        """
        This is a comment
        """
        msg = (
            "Cannot resolve keyword 'name_in_all_caps' into field. Choices are: id, "
            "name, tags"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Thing.objects.update_or_create(
                name_in_all_caps="FRANK", defaults={"name": "Frank"}
            )
