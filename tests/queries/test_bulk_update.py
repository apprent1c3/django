import datetime

from django.core.exceptions import FieldDoesNotExist
from django.db.models import F
from django.db.models.functions import Lower
from django.db.utils import IntegrityError
from django.test import TestCase, override_settings, skipUnlessDBFeature

from .models import (
    Article,
    CustomDbColumn,
    CustomPk,
    Detail,
    Food,
    Individual,
    JSONFieldNullable,
    Member,
    Note,
    Number,
    Order,
    Paragraph,
    RelatedObject,
    SingleObject,
    SpecialCategory,
    Tag,
    Valid,
)


class WriteToOtherRouter:
    def db_for_write(self, model, **hints):
        return "other"


class BulkUpdateNoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.notes = [Note.objects.create(note=str(i), misc=str(i)) for i in range(10)]

    def create_tags(self):
        self.tags = [Tag.objects.create(name=str(i)) for i in range(10)]

    def test_simple(self):
        for note in self.notes:
            note.note = "test-%s" % note.id
        with self.assertNumQueries(1):
            Note.objects.bulk_update(self.notes, ["note"])
        self.assertCountEqual(
            Note.objects.values_list("note", flat=True),
            [cat.note for cat in self.notes],
        )

    def test_multiple_fields(self):
        """
        Tests the bulk update functionality for multiple fields.

        This function updates the 'note' and 'misc' fields of multiple note objects in bulk,
        then verifies that the database reflects the changes. The bulk update is performed
        in a single database query, ensuring efficient database interaction. The function
        then verifies that the updated values are correctly stored in the database by 
        comparing the updated note objects with the values retrieved from the database.

        The test covers the case where multiple fields are updated simultaneously, 
        ensuring data consistency and integrity.

        """
        for note in self.notes:
            note.note = "test-%s" % note.id
            note.misc = "misc-%s" % note.id
        with self.assertNumQueries(1):
            Note.objects.bulk_update(self.notes, ["note", "misc"])
        self.assertCountEqual(
            Note.objects.values_list("note", flat=True),
            [cat.note for cat in self.notes],
        )
        self.assertCountEqual(
            Note.objects.values_list("misc", flat=True),
            [cat.misc for cat in self.notes],
        )

    def test_batch_size(self):
        """
        Tests the bulk update functionality of Note objects with a specified batch size.

        This test case asserts that the number of database queries executed matches the number of Note objects being updated, 
        when the batch size is set to 1. It ensures that each note is updated in a separate query, resulting in a total 
        number of queries equal to the number of notes. The test validates the performance of bulk updates in this specific 
        scenario, providing assurance that the database interactions are as expected.
        """
        with self.assertNumQueries(len(self.notes)):
            Note.objects.bulk_update(self.notes, fields=["note"], batch_size=1)

    def test_unsaved_models(self):
        """
        Tests that attempting to bulk update unsaved models using Note.objects.bulk_update() raises a ValueError.

        The test case verifies that a ValueError is raised with a specific error message when the bulk_update() method is called with a list of objects that includes at least one object without a primary key set. This ensures that the bulk_update() method behaves as expected and prevents accidental updates to non-existent database records.
        """
        objs = self.notes + [Note(note="test", misc="test")]
        msg = "All bulk_update() objects must have a primary key set."
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update(objs, fields=["note"])

    def test_foreign_keys_do_not_lookup(self):
        """

        Tests that bulk updating of foreign key fields in the Note model does not trigger redundant database lookups.

        Verifies that when updating the 'tag' field of multiple Note instances, the database is only queried once, 
        and that the updated Note instances are correctly filtered by their associated tags.

        """
        self.create_tags()
        for note, tag in zip(self.notes, self.tags):
            note.tag = tag
        with self.assertNumQueries(1):
            Note.objects.bulk_update(self.notes, ["tag"])
        self.assertSequenceEqual(Note.objects.filter(tag__isnull=False), self.notes)

    def test_set_field_to_null(self):
        self.create_tags()
        Note.objects.update(tag=self.tags[0])
        for note in self.notes:
            note.tag = None
        Note.objects.bulk_update(self.notes, ["tag"])
        self.assertCountEqual(Note.objects.filter(tag__isnull=True), self.notes)

    def test_set_mixed_fields_to_null(self):
        """

        Test setting mixed fields to null in the database.

        This test case verifies the behavior of setting the 'tag' field to null for a subset of notes,
        while keeping it populated for the rest. It checks that the database correctly stores and retrieves
        these changes, ensuring that notes with a null tag are properly distinguished from those with a tag.

        The test splits the set of notes into two parts, sets the 'tag' field to null for the first part and
        to a specific tag for the second part, and then updates the database. Finally, it checks that the
        database contains the expected notes with null and non-null tags.

        """
        self.create_tags()
        midpoint = len(self.notes) // 2
        top, bottom = self.notes[:midpoint], self.notes[midpoint:]
        for note in top:
            note.tag = None
        for note in bottom:
            note.tag = self.tags[0]
        Note.objects.bulk_update(self.notes, ["tag"])
        self.assertCountEqual(Note.objects.filter(tag__isnull=True), top)
        self.assertCountEqual(Note.objects.filter(tag__isnull=False), bottom)

    def test_functions(self):
        """

        Tests the bulk update functionality of note objects by setting all notes to 'TEST', 
        then converting them to lowercase and verifying the result against the expected output.

        Ensures that the bulk update operation successfully updates all note objects 
        and that the updated values are correctly persisted in the database.

        """
        Note.objects.update(note="TEST")
        for note in self.notes:
            note.note = Lower("note")
        Note.objects.bulk_update(self.notes, ["note"])
        self.assertEqual(set(Note.objects.values_list("note", flat=True)), {"test"})

    # Tests that use self.notes go here, otherwise put them in another class.


class BulkUpdateTests(TestCase):
    databases = {"default", "other"}

    def test_no_fields(self):
        """

        Tests that a ValueError is raised when no field names are provided to bulk_update.

        The test verifies that an error message is raised when attempting to bulk update 
        notes without specifying any fields, ensuring that the bulk_update method 
        correctly handles invalid input.

        """
        msg = "Field names must be given to bulk_update()."
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update([], fields=[])

    def test_invalid_batch_size(self):
        """

        Tests that bulk_update raises a ValueError when an invalid batch size is provided.

        The function checks that the bulk_update method fails with a ValueError when the batch size is set to a non-positive integer, 
        ensuring that only valid batch sizes are accepted for bulk updates.

        """
        msg = "Batch size must be a positive integer."
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update([], fields=["note"], batch_size=-1)
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update([], fields=["note"], batch_size=0)

    def test_nonexistent_field(self):
        with self.assertRaisesMessage(
            FieldDoesNotExist, "Note has no field named 'nonexistent'"
        ):
            Note.objects.bulk_update([], ["nonexistent"])

    pk_fields_error = "bulk_update() cannot be used with primary key fields."

    def test_update_primary_key(self):
        with self.assertRaisesMessage(ValueError, self.pk_fields_error):
            Note.objects.bulk_update([], ["id"])

    def test_update_custom_primary_key(self):
        """
        Test that bulk updating with an incorrect set of primary key fields raises a ValueError.

        This test ensures that attempting to update objects in the CustomPk model using a custom primary key that does not include all necessary fields results in an error with a clear message.

        :raises ValueError: If the set of primary key fields is invalid.
        """
        with self.assertRaisesMessage(ValueError, self.pk_fields_error):
            CustomPk.objects.bulk_update([], ["name"])

    def test_empty_objects(self):
        with self.assertNumQueries(0):
            rows_updated = Note.objects.bulk_update([], ["note"])
        self.assertEqual(rows_updated, 0)

    def test_large_batch(self):
        """

        Tests the bulk update functionality of the Note model with a large batch of data.

        This function creates a large batch of Note objects, saves them to the database using bulk creation, 
        retrieves all notes, and then updates them in bulk. The test asserts that the number of rows updated 
        matches the expected number, verifying the bulk update operation's correctness.

        The test case covers the performance and functionality of bulk updates with a significant amount of data.

        """
        Note.objects.bulk_create(
            [Note(note=str(i), misc=str(i)) for i in range(0, 2000)]
        )
        notes = list(Note.objects.all())
        rows_updated = Note.objects.bulk_update(notes, ["note"])
        self.assertEqual(rows_updated, 2000)

    def test_updated_rows_when_passing_duplicates(self):
        """

        Tests the behavior of bulk updating Note objects when passing duplicate instances.

        This test case verifies the number of rows updated when bulk updating Note objects with duplicate instances, 
        both with and without a specified batch size. It checks that the correct number of updates is made in each scenario.

        """
        note = Note.objects.create(note="test-note", misc="test")
        rows_updated = Note.objects.bulk_update([note, note], ["note"])
        self.assertEqual(rows_updated, 1)
        # Duplicates in different batches.
        rows_updated = Note.objects.bulk_update([note, note], ["note"], batch_size=1)
        self.assertEqual(rows_updated, 2)

    def test_only_concrete_fields_allowed(self):
        obj = Valid.objects.create(valid="test")
        detail = Detail.objects.create(data="test")
        paragraph = Paragraph.objects.create(text="test")
        Member.objects.create(name="test", details=detail)
        msg = "bulk_update() can only be used with concrete fields."
        with self.assertRaisesMessage(ValueError, msg):
            Detail.objects.bulk_update([detail], fields=["member"])
        with self.assertRaisesMessage(ValueError, msg):
            Paragraph.objects.bulk_update([paragraph], fields=["page"])
        with self.assertRaisesMessage(ValueError, msg):
            Valid.objects.bulk_update([obj], fields=["parent"])

    def test_custom_db_columns(self):
        """
        Tests the functionality of updating custom database columns.

        This test case verifies that a custom database column can be successfully updated using bulk update.
        It checks that the updated value is persisted in the database and that the model instance is correctly refreshed with the new value.

        The test covers the following scenarios:
            * Creating a new custom database column object
            * Updating the custom column value
            * Using bulk update to persist the changes
            * Refreshing the model instance from the database
            * Verifying that the updated value is correctly retrieved

        Ensures that the custom database column functionality is working as expected, providing a reliable way to update and retrieve custom column values.
        """
        model = CustomDbColumn.objects.create(custom_column=1)
        model.custom_column = 2
        CustomDbColumn.objects.bulk_update([model], fields=["custom_column"])
        model.refresh_from_db()
        self.assertEqual(model.custom_column, 2)

    def test_custom_pk(self):
        custom_pks = [
            CustomPk.objects.create(name="pk-%s" % i, extra="") for i in range(10)
        ]
        for model in custom_pks:
            model.extra = "extra-%s" % model.pk
        CustomPk.objects.bulk_update(custom_pks, ["extra"])
        self.assertCountEqual(
            CustomPk.objects.values_list("extra", flat=True),
            [cat.extra for cat in custom_pks],
        )

    def test_falsey_pk_value(self):
        """

        Tests the behavior of bulk updating an object with a falsey primary key value.

        This test case ensures that an object with a primary key value of 0 can be successfully
        updated using bulk update and that the changes are persisted in the database.

        It verifies that the object's attributes are updated correctly and that the object
        can be refreshed from the database after the update.

        """
        order = Order.objects.create(pk=0, name="test")
        order.name = "updated"
        Order.objects.bulk_update([order], ["name"])
        order.refresh_from_db()
        self.assertEqual(order.name, "updated")

    def test_inherited_fields(self):
        special_categories = [
            SpecialCategory.objects.create(name=str(i), special_name=str(i))
            for i in range(10)
        ]
        for category in special_categories:
            category.name = "test-%s" % category.id
            category.special_name = "special-test-%s" % category.special_name
        SpecialCategory.objects.bulk_update(
            special_categories, ["name", "special_name"]
        )
        self.assertCountEqual(
            SpecialCategory.objects.values_list("name", flat=True),
            [cat.name for cat in special_categories],
        )
        self.assertCountEqual(
            SpecialCategory.objects.values_list("special_name", flat=True),
            [cat.special_name for cat in special_categories],
        )

    def test_field_references(self):
        """
        Tests the ability to reference model fields within database queries using the F expression, 
         specifically in the context of bulk updates. It creates a set of numbered objects, increments 
         each number using an F expression, then bulk updates the objects. The test passes if the 
         updated objects all have the expected new value.
        """
        numbers = [Number.objects.create(num=0) for _ in range(10)]
        for number in numbers:
            number.num = F("num") + 1
        Number.objects.bulk_update(numbers, ["num"])
        self.assertCountEqual(Number.objects.filter(num=1), numbers)

    def test_f_expression(self):
        """
        Test the bulk update of notes using F expressions.

        This test creates a list of notes, sets the 'misc' field of each note to the value of its 'note' field using an F expression,
        and then performs a bulk update to persist these changes to the database.

        It validates that the update was successful by asserting that all notes with 'misc' equal to 'test_note'
        are the same as the original list of notes that were updated.

        This ensures the correct functionality of F expressions in bulk updates, allowing the database to perform
        self-referential updates efficiently and safely.
        """
        notes = [
            Note.objects.create(note="test_note", misc="test_misc") for _ in range(10)
        ]
        for note in notes:
            note.misc = F("note")
        Note.objects.bulk_update(notes, ["misc"])
        self.assertCountEqual(Note.objects.filter(misc="test_note"), notes)

    def test_booleanfield(self):
        individuals = [Individual.objects.create(alive=False) for _ in range(10)]
        for individual in individuals:
            individual.alive = True
        Individual.objects.bulk_update(individuals, ["alive"])
        self.assertCountEqual(Individual.objects.filter(alive=True), individuals)

    def test_ipaddressfield(self):
        """
        Tests the functionality of the ip_address field in the CustomDbColumn model.

            This test case checks whether the ip_address field correctly updates a list of model instances. 
            It creates a set of CustomDbColumn model instances with an initial ip_address, updates these instances with new IPv4 and IPv6 addresses, 
            and then verifies that the updated instances can be filtered by their new ip_address. 
            The test uses both IPv4 and IPv6 addresses to ensure compatibility.
        """
        for ip in ("2001::1", "1.2.3.4"):
            with self.subTest(ip=ip):
                models = [
                    CustomDbColumn.objects.create(ip_address="0.0.0.0")
                    for _ in range(10)
                ]
                for model in models:
                    model.ip_address = ip
                CustomDbColumn.objects.bulk_update(models, ["ip_address"])
                self.assertCountEqual(
                    CustomDbColumn.objects.filter(ip_address=ip), models
                )

    def test_datetime_field(self):
        """

        Test the functionality of the datetime field in the Article model.

        This test verifies that the created datetime field can be successfully updated 
        for multiple articles using bulk update and that the updated values are 
        accurately retrieved.

        The test case involves creating a set of articles, updating their creation 
        datetimes to a specific point in time, and then confirming that the updated 
        articles are correctly associated with that point in time.

        """
        articles = [
            Article.objects.create(name=str(i), created=datetime.datetime.today())
            for i in range(10)
        ]
        point_in_time = datetime.datetime(1991, 10, 31)
        for article in articles:
            article.created = point_in_time
        Article.objects.bulk_update(articles, ["created"])
        self.assertCountEqual(Article.objects.filter(created=point_in_time), articles)

    @skipUnlessDBFeature("supports_json_field")
    def test_json_field(self):
        JSONFieldNullable.objects.bulk_create(
            [JSONFieldNullable(json_field={"a": i}) for i in range(10)]
        )
        objs = JSONFieldNullable.objects.all()
        for obj in objs:
            obj.json_field = {"c": obj.json_field["a"] + 1}
        JSONFieldNullable.objects.bulk_update(objs, ["json_field"])
        self.assertCountEqual(
            JSONFieldNullable.objects.filter(json_field__has_key="c"), objs
        )

    def test_nullable_fk_after_related_save(self):
        """
        Tests the behavior of a nullable foreign key relationship after saving a related object.

         Verifies that the foreign key on the parent object is correctly updated after the related child object is saved.

         The test ensures data consistency by checking the foreign key value before and after refreshing the parent object from the database, 
         confirming that the relationship between the parent and child objects is maintained as expected.
        """
        parent = RelatedObject.objects.create()
        child = SingleObject()
        parent.single = child
        parent.single.save()
        RelatedObject.objects.bulk_update([parent], fields=["single"])
        self.assertEqual(parent.single_id, parent.single.pk)
        parent.refresh_from_db()
        self.assertEqual(parent.single, child)

    def test_unsaved_parent(self):
        """
        Tests that bulk_update on RelatedObject instances with unsaved related objects raises an error.

        Verifies that attempting to perform a bulk update on a collection of RelatedObject instances
        that have related objects which have not been saved to the database yet results in a ValueError.
        This ensures that data loss due to unsaved related objects is prevented.
        """
        parent = RelatedObject.objects.create()
        parent.single = SingleObject()
        msg = (
            "bulk_update() prohibited to prevent data loss due to unsaved "
            "related object 'single'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            RelatedObject.objects.bulk_update([parent], fields=["single"])

    def test_unspecified_unsaved_parent(self):
        """

        Tests the behavior of an unspecified and unsaved parent object in a related object scenario.

        Verifies that updating a parent object using bulk update does not affect the related object, 
        even if it was previously set. The test checks that the updated field is correctly saved 
        and the related object remains unset after the bulk update operation.

        """
        parent = RelatedObject.objects.create()
        parent.single = SingleObject()
        parent.f = 42
        RelatedObject.objects.bulk_update([parent], fields=["f"])
        parent.refresh_from_db()
        self.assertEqual(parent.f, 42)
        self.assertIsNone(parent.single)

    @override_settings(DATABASE_ROUTERS=[WriteToOtherRouter()])
    def test_database_routing(self):
        """

        Tests the database routing functionality by creating a note object, 
        updating its 'note' field, and then performing a bulk update on the object.
        The test verifies that the bulk update operation is routed to the 'other' database 
        and that it is executed in a single database query.

        This test case ensures that the WriteToOtherRouter configuration correctly routes 
        database operations to the intended database, allowing for efficient management 
        of data across multiple databases.

        """
        note = Note.objects.create(note="create")
        note.note = "bulk_update"
        with self.assertNumQueries(1, using="other"):
            Note.objects.bulk_update([note], fields=["note"])

    @override_settings(DATABASE_ROUTERS=[WriteToOtherRouter()])
    def test_database_routing_batch_atomicity(self):
        """

        Test database routing batch atomicity.

        This test case verifies that a bulk update operation using database routing
        is atomic, ensuring data consistency. It checks that when a bulk update fails
        due to an integrity error, the database remains in a consistent state and no
        partial updates are committed.

        The test scenario involves creating two food objects, updating their names to
        the same value (which would cause an integrity error), and then attempting a
        bulk update. The test asserts that the bulk update raises an IntegrityError
        and that no objects with the updated name are committed to the database.

        """
        f1 = Food.objects.create(name="Banana")
        f2 = Food.objects.create(name="Apple")
        f1.name = "Kiwi"
        f2.name = "Kiwi"
        with self.assertRaises(IntegrityError):
            Food.objects.bulk_update([f1, f2], fields=["name"], batch_size=1)
        self.assertIs(Food.objects.filter(name="Kiwi").exists(), False)
