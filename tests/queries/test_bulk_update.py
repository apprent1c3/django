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
        """
        Tests the bulk update functionality by modifying note attributes and verifying the changes are persisted to the database efficiently.
        """
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
        Tests bulk update functionality for multiple fields of Note objects, 
        verifying that the update is performed efficiently in a single query and 
        that the updated values are correctly persisted in the database.
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
        with self.assertNumQueries(len(self.notes)):
            Note.objects.bulk_update(self.notes, fields=["note"], batch_size=1)

    def test_unsaved_models(self):
        objs = self.notes + [Note(note="test", misc="test")]
        msg = "All bulk_update() objects must have a primary key set."
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update(objs, fields=["note"])

    def test_foreign_keys_do_not_lookup(self):
        """
        Ensures that foreign key lookups are not performed when using bulk update with a single database query. Verifies that the bulk update operation correctly updates note objects with their associated tags without triggering unnecessary queries.
        """
        self.create_tags()
        for note, tag in zip(self.notes, self.tags):
            note.tag = tag
        with self.assertNumQueries(1):
            Note.objects.bulk_update(self.notes, ["tag"])
        self.assertSequenceEqual(Note.objects.filter(tag__isnull=False), self.notes)

    def test_set_field_to_null(self):
        """
        Tests that setting the 'tag' field of a note to null updates the database correctly. Verifies that the null assignment is persisted after bulk updating the notes.
        """
        self.create_tags()
        Note.objects.update(tag=self.tags[0])
        for note in self.notes:
            note.tag = None
        Note.objects.bulk_update(self.notes, ["tag"])
        self.assertCountEqual(Note.objects.filter(tag__isnull=True), self.notes)

    def test_set_mixed_fields_to_null(self):
        """
        Tests the bulk update functionality of notes with mixed fields, specifically setting tags to null, by splitting notes into two groups, updating their tags, and verifying the resulting database state.
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
        Updates all notes to have a lowercase 'test' value and verifies the change has been successfully applied to all notes in the database.
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
        msg = "Field names must be given to bulk_update()."
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.bulk_update([], fields=[])

    def test_invalid_batch_size(self):
        """
        Tests that a ValueError is raised when an invalid batch size is provided to bulk_update.\"\"\"

         or, a bit longer version:

        \"\"\"Verifies that bulk_update correctly handles invalid batch sizes by raising a ValueError when a non-positive integer is specified.
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
        with self.assertRaisesMessage(ValueError, self.pk_fields_error):
            CustomPk.objects.bulk_update([], ["name"])

    def test_empty_objects(self):
        with self.assertNumQueries(0):
            rows_updated = Note.objects.bulk_update([], ["note"])
        self.assertEqual(rows_updated, 0)

    def test_large_batch(self):
        Note.objects.bulk_create(
            [Note(note=str(i), misc=str(i)) for i in range(0, 2000)]
        )
        notes = list(Note.objects.all())
        rows_updated = Note.objects.bulk_update(notes, ["note"])
        self.assertEqual(rows_updated, 2000)

    def test_updated_rows_when_passing_duplicates(self):
        """
        Tests the behavior of bulk updating Note objects when passing duplicate entries, ensuring that the correct number of rows are updated in different batch size scenarios.
        """
        note = Note.objects.create(note="test-note", misc="test")
        rows_updated = Note.objects.bulk_update([note, note], ["note"])
        self.assertEqual(rows_updated, 1)
        # Duplicates in different batches.
        rows_updated = Note.objects.bulk_update([note, note], ["note"], batch_size=1)
        self.assertEqual(rows_updated, 2)

    def test_only_concrete_fields_allowed(self):
        """
        Tests that bulk_update can only be used with concrete fields, not with foreign key or relationship fields, raising a ValueError with a descriptive message when attempting to update non-concrete fields.
        """
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
        Tests the custom database column functionality, verifying that bulk updates correctly modify column values and changes are reflected after refreshing the model from the database.
        """
        model = CustomDbColumn.objects.create(custom_column=1)
        model.custom_column = 2
        CustomDbColumn.objects.bulk_update([model], fields=["custom_column"])
        model.refresh_from_db()
        self.assertEqual(model.custom_column, 2)

    def test_custom_pk(self):
        """
        Verifies that bulk update correctly updates the 'extra' field of CustomPk objects with custom primary keys.
        """
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
        Tests that a falsy primary key value does not prevent bulk updates and refresh from database operations.
        """
        order = Order.objects.create(pk=0, name="test")
        order.name = "updated"
        Order.objects.bulk_update([order], ["name"])
        order.refresh_from_db()
        self.assertEqual(order.name, "updated")

    def test_inherited_fields(self):
        """
        Tests that inherited fields are correctly updated in the database.

        Verifies that changes to 'name' and 'special_name' attributes of SpecialCategory objects
        are persisted after a bulk update, ensuring data consistency and integrity.
        """
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
        Tests that field references are correctly updated when using Django's F expressions in conjunction with bulk updates.
        """
        numbers = [Number.objects.create(num=0) for _ in range(10)]
        for number in numbers:
            number.num = F("num") + 1
        Number.objects.bulk_update(numbers, ["num"])
        self.assertCountEqual(Number.objects.filter(num=1), numbers)

    def test_f_expression(self):
        """
        Tests the update of model instances using F-expression, verifying that the 'misc' field is successfully updated to match the 'note' field for a batch of notes.
        """
        notes = [
            Note.objects.create(note="test_note", misc="test_misc") for _ in range(10)
        ]
        for note in notes:
            note.misc = F("note")
        Note.objects.bulk_update(notes, ["misc"])
        self.assertCountEqual(Note.objects.filter(misc="test_note"), notes)

    def test_booleanfield(self):
        """
        Tests the correct functionality of a boolean field in the Individual model, specifically when updating multiple instances using bulk update.
        """
        individuals = [Individual.objects.create(alive=False) for _ in range(10)]
        for individual in individuals:
            individual.alive = True
        Individual.objects.bulk_update(individuals, ["alive"])
        self.assertCountEqual(Individual.objects.filter(alive=True), individuals)

    def test_ipaddressfield(self):
        """
        Tests that the ip_address field of the CustomDbColumn model correctly stores and filters IPv4 and IPv6 addresses after bulk update.
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
        Tests the functionality of the 'created' datetime field in the Article model, ensuring it can be successfully updated and filtered.
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
        """
        Tests the database's support for JSON fields by creating, updating, and querying objects with JSON data.
        """
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
        Tests if a nullable foreign key on a related object remains consistent after saving and bulk updating the related object.
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
        Tests that attempting to perform a bulk update on a related object with an unsaved parent raises a ValueError, preventing potential data loss due to the unsaved relationship.
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
        Tests that an unsaved, unspecified related object is not persisted when 
        the parent object is updated using bulk update with only specified fields.
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
        note = Note.objects.create(note="create")
        note.note = "bulk_update"
        with self.assertNumQueries(1, using="other"):
            Note.objects.bulk_update([note], fields=["note"])

    @override_settings(DATABASE_ROUTERS=[WriteToOtherRouter()])
    def test_database_routing_batch_atomicity(self):
        """
        Tests that bulk updates with database routing are atomic, ensuring that if an update fails due to an integrity error, no changes are committed to the database.
        """
        f1 = Food.objects.create(name="Banana")
        f2 = Food.objects.create(name="Apple")
        f1.name = "Kiwi"
        f2.name = "Kiwi"
        with self.assertRaises(IntegrityError):
            Food.objects.bulk_update([f1, f2], fields=["name"], batch_size=1)
        self.assertIs(Food.objects.filter(name="Kiwi").exists(), False)
