import unittest

from django.core.checks import Error, Warning
from django.core.checks.model_checks import _check_lazy_references
from django.db import connection, connections, models
from django.db.models.functions import Abs, Lower, Round
from django.db.models.signals import post_init
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import isolate_apps, override_settings, register_lookup


class EmptyRouter:
    pass


def get_max_column_name_length():
    """
    Determines the maximum allowed column name length across multiple databases.

    Returns a tuple containing the maximum allowed length and the database alias where this length was found. The calculation takes into account the database connection features, ignoring databases that truncate names and selecting the shortest allowed length among the remaining ones.
    """
    allowed_len = None
    db_alias = None

    for db in ("default", "other"):
        connection = connections[db]
        max_name_length = connection.ops.max_name_length()
        if max_name_length is not None and not connection.features.truncates_names:
            if allowed_len is None or max_name_length < allowed_len:
                allowed_len = max_name_length
                db_alias = db

    return (allowed_len, db_alias)


@isolate_apps("invalid_models_tests")
class UniqueTogetherTests(SimpleTestCase):
    def test_non_iterable(self):
        """
        Tests that models with invalid unique_together Meta option raise the correct error.
        """
        class Model(models.Model):
            class Meta:
                unique_together = 42

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'unique_together' must be a list or tuple.",
                    obj=Model,
                    id="models.E010",
                ),
            ],
        )

    def test_list_containing_non_iterable(self):
        """
        Tests a model validation check to ensure that all elements in the 'unique_together' Meta option are either lists or tuples, rejecting non-iterable values.
        """
        class Model(models.Model):
            one = models.IntegerField()
            two = models.IntegerField()

            class Meta:
                unique_together = [("a", "b"), 42]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "All 'unique_together' elements must be lists or tuples.",
                    obj=Model,
                    id="models.E011",
                ),
            ],
        )

    def test_non_list(self):
        """
        Checks that the 'unique_together' constraint in a model's Meta class is properly defined as a list or tuple, and raises an error if it is not.
        """
        class Model(models.Model):
            class Meta:
                unique_together = "not-a-list"

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'unique_together' must be a list or tuple.",
                    obj=Model,
                    id="models.E010",
                ),
            ],
        )

    def test_valid_model(self):
        """
        Checks if a model with a unique_together constraint is valid. Verifies that no duplicate combinations of the specified fields exist.
        """
        class Model(models.Model):
            one = models.IntegerField()
            two = models.IntegerField()

            class Meta:
                # unique_together can be a simple tuple
                unique_together = ("one", "two")

        self.assertEqual(Model.check(), [])

    def test_pointing_to_missing_field(self):
        """
        Tests that the model validation correctly identifies 'unique_together' constraints referencing missing fields.
        """
        class Model(models.Model):
            class Meta:
                unique_together = [["missing_field"]]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'unique_together' refers to the nonexistent field "
                    "'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    def test_pointing_to_m2m(self):
        """
        Tests that ManyToManyFields raise an error when used in unique_together constraints in a model's Meta options.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                unique_together = [["m2m"]]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'unique_together' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'unique_together'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    def test_pointing_to_fk(self):
        """
        Tests that a model with multiple foreign keys to the same model can correctly implement unique constraints on the related fields, ensuring data integrity and preventing duplicate relationships between instances.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foo_1 = models.ForeignKey(
                Foo, on_delete=models.CASCADE, related_name="bar_1"
            )
            foo_2 = models.ForeignKey(
                Foo, on_delete=models.CASCADE, related_name="bar_2"
            )

            class Meta:
                unique_together = [["foo_1_id", "foo_2"]]

        self.assertEqual(Bar.check(), [])


@isolate_apps("invalid_models_tests")
class IndexesTests(TestCase):
    def test_pointing_to_missing_field(self):
        """
        Tests that a model with an index referencing a missing field correctly raises an error.
        """
        class Model(models.Model):
            class Meta:
                indexes = [models.Index(fields=["missing_field"], name="name")]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'indexes' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    def test_pointing_to_m2m_field(self):
        """
        Tests that a model raises an error when its Meta.indexes attribute references a ManyToManyField, which is not permitted.\"\"\"

        However, since this is an internal test and likely used only for validation in a specific context, a slightly modified version could be:

        \"\"\"Verifies that ManyToManyFields are not allowed in model indexes, as per database constraints.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                indexes = [models.Index(fields=["m2m"], name="name")]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'indexes' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'indexes'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    def test_pointing_to_non_local_field(self):
        """
        Tests that a model's index cannot point to a field inherited from its non-local parent model, enforcing the requirement that indexes only reference local fields or fields with a clear inheritance path.
        """
        class Foo(models.Model):
            field1 = models.IntegerField()

        class Bar(Foo):
            field2 = models.IntegerField()

            class Meta:
                indexes = [models.Index(fields=["field2", "field1"], name="name")]

        self.assertEqual(
            Bar.check(),
            [
                Error(
                    "'indexes' refers to field 'field1' which is not local to "
                    "model 'Bar'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Bar,
                    id="models.E016",
                ),
            ],
        )

    def test_pointing_to_fk(self):
        """

        Tests that a model's foreign key fields are correctly indexed when related_name is used.

        Verifies the model validation does not raise any errors when a composite index
        is created with a ForeignKey field that has a related_name and a field of another model.

        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foo_1 = models.ForeignKey(
                Foo, on_delete=models.CASCADE, related_name="bar_1"
            )
            foo_2 = models.ForeignKey(
                Foo, on_delete=models.CASCADE, related_name="bar_2"
            )

            class Meta:
                indexes = [
                    models.Index(fields=["foo_1_id", "foo_2"], name="index_name")
                ]

        self.assertEqual(Bar.check(), [])

    def test_name_constraints(self):
        """

        Tests that index names in a Django model's Meta indexes do not start with an underscore or a number.

        """
        class Model(models.Model):
            class Meta:
                indexes = [
                    models.Index(fields=["id"], name="_index_name"),
                    models.Index(fields=["id"], name="5index_name"),
                ]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "The index name '%sindex_name' cannot start with an "
                    "underscore or a number." % prefix,
                    obj=Model,
                    id="models.E033",
                )
                for prefix in ("_", "5")
            ],
        )

    def test_max_name_length(self):
        """
        Tests that Django models raise a validation error when an index name exceeds the maximum allowed length of 30 characters.
        """
        index_name = "x" * 31

        class Model(models.Model):
            class Meta:
                indexes = [models.Index(fields=["id"], name=index_name)]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "The index name '%s' cannot be longer than 30 characters."
                    % index_name,
                    obj=Model,
                    id="models.E034",
                ),
            ],
        )

    def test_index_with_condition(self):
        """
        Tests the creation of an index with a condition on a model field, verifying that the database supports partial indexes or correctly reports a warning if it does not.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                indexes = [
                    models.Index(
                        fields=["age"],
                        name="index_age_gte_10",
                        condition=models.Q(age__gte=10),
                    ),
                ]

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_partial_indexes
            else [
                Warning(
                    "%s does not support indexes with conditions."
                    % connection.display_name,
                    hint=(
                        "Conditions will be ignored. Silence this warning if you "
                        "don't care about it."
                    ),
                    obj=Model,
                    id="models.W037",
                )
            ]
        )
        self.assertEqual(errors, expected)

    def test_index_with_condition_required_db_features(self):
        """
        Tests that a model with a conditionally required database feature is valid when the feature is supported, using an example model that defines an index with a condition.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_partial_indexes"}
                indexes = [
                    models.Index(
                        fields=["age"],
                        name="index_age_gte_10",
                        condition=models.Q(age__gte=10),
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_index_with_include(self):
        """
        Checks if the database supports indexes with non-key columns (covering indexes) for a model with a defined index that includes non-key columns.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                indexes = [
                    models.Index(
                        fields=["age"],
                        name="index_age_include_id",
                        include=["id"],
                    ),
                ]

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_covering_indexes
            else [
                Warning(
                    "%s does not support indexes with non-key columns."
                    % connection.display_name,
                    hint=(
                        "Non-key columns will be ignored. Silence this warning if "
                        "you don't care about it."
                    ),
                    obj=Model,
                    id="models.W040",
                )
            ]
        )
        self.assertEqual(errors, expected)

    def test_index_with_include_required_db_features(self):
        """
        Tests whether a model with a covering index that includes a field is valid when the required database feature 'supports_covering_indexes' is specified.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_covering_indexes"}
                indexes = [
                    models.Index(
                        fields=["age"],
                        name="index_age_include_id",
                        include=["id"],
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_index_include_pointing_to_missing_field(self):
        """
        Tests that an Index with an include referencing a missing field raises an error.
        """
        class Model(models.Model):
            class Meta:
                indexes = [
                    models.Index(fields=["id"], include=["missing_field"], name="name"),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'indexes' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_index_include_pointing_to_m2m_field(self):
        """
        Tests that an error is raised when a model's indexing configuration includes a ManyToManyField, which is not permitted.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                indexes = [models.Index(fields=["id"], include=["m2m"], name="name")]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'indexes' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'indexes'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_index_include_pointing_to_non_local_field(self):
        """
        Tests that an error is raised when a model's index includes a non-local field obtained through multi-table inheritance.
        """
        class Parent(models.Model):
            field1 = models.IntegerField()

        class Child(Parent):
            field2 = models.IntegerField()

            class Meta:
                indexes = [
                    models.Index(fields=["field2"], include=["field1"], name="name"),
                ]

        self.assertEqual(
            Child.check(databases=self.databases),
            [
                Error(
                    "'indexes' refers to field 'field1' which is not local to "
                    "model 'Child'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Child,
                    id="models.E016",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_index_include_pointing_to_fk(self):
        """
        Tests that the database validation process correctly handles covering indexes with included columns referencing foreign key fields.
        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            fk_1 = models.ForeignKey(Target, models.CASCADE, related_name="target_1")
            fk_2 = models.ForeignKey(Target, models.CASCADE, related_name="target_2")

            class Meta:
                indexes = [
                    models.Index(
                        fields=["id"],
                        include=["fk_1_id", "fk_2"],
                        name="name",
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_func_index(self):
        """
        Tests the checking of model indexes on a database, specifically when an index is defined on an expression, verifying that a warning is raised if the database backend does not support expression indexes.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                indexes = [models.Index(Lower("name"), name="index_lower_name")]

        warn = Warning(
            "%s does not support indexes on expressions." % connection.display_name,
            hint=(
                "An index won't be created. Silence this warning if you don't "
                "care about it."
            ),
            obj=Model,
            id="models.W043",
        )
        expected = [] if connection.features.supports_expression_indexes else [warn]
        self.assertEqual(Model.check(databases=self.databases), expected)

    def test_func_index_required_db_features(self):
        """
        Tests that a model with required database features is valid when those features are supported.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                indexes = [models.Index(Lower("name"), name="index_lower_name")]
                required_db_features = {"supports_expression_indexes"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_func_index_complex_expression_custom_lookup(self):
        """
        Tests a custom lookup 'Abs' used within an index with a complex expression.

         Verifies that a model's check method returns no errors when the 'Abs' lookup is 
         correctly registered and used in an index of a model field, preventing potential 
         division by zero issues with a custom expression involving absolute value calculation.
        """
        class Model(models.Model):
            height = models.IntegerField()
            weight = models.IntegerField()

            class Meta:
                indexes = [
                    models.Index(
                        models.F("height")
                        / (models.F("weight__abs") + models.Value(5)),
                        name="name",
                    ),
                ]

        with register_lookup(models.IntegerField, Abs):
            self.assertEqual(Model.check(), [])

    def test_func_index_pointing_to_missing_field(self):
        """
        Tests that a model with an index pointing to a missing field correctly reports the error.
        """
        class Model(models.Model):
            class Meta:
                indexes = [models.Index(Lower("missing_field").desc(), name="name")]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'indexes' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    def test_func_index_pointing_to_missing_field_nested(self):
        """
        Checks that a model's index pointing to a missing field in a nested expression raises the correct error.
        """
        class Model(models.Model):
            class Meta:
                indexes = [
                    models.Index(Abs(Round("missing_field")), name="name"),
                ]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'indexes' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    def test_func_index_pointing_to_m2m_field(self):
        """

        Tests that an error is raised when an index is defined on a ManyToManyField.

        The function checks that Django model checks correctly identify and prevent the creation of indexes on ManyToManyFields.

        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                indexes = [models.Index(Lower("m2m"), name="name")]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'indexes' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'indexes'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    def test_func_index_pointing_to_non_local_field(self):
        """
        Tests that an index on a non-local field inherited from a parent model raises an error.
        """
        class Foo(models.Model):
            field1 = models.CharField(max_length=15)

        class Bar(Foo):
            class Meta:
                indexes = [models.Index(Lower("field1"), name="name")]

        self.assertEqual(
            Bar.check(),
            [
                Error(
                    "'indexes' refers to field 'field1' which is not local to "
                    "model 'Bar'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Bar,
                    id="models.E016",
                ),
            ],
        )

    def test_func_index_pointing_to_fk(self):
        """
        Checks that a model's index pointing to a foreign key column is correctly defined, ensuring proper casing of the referenced field names.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foo_1 = models.ForeignKey(Foo, models.CASCADE, related_name="bar_1")
            foo_2 = models.ForeignKey(Foo, models.CASCADE, related_name="bar_2")

            class Meta:
                indexes = [
                    models.Index(Lower("foo_1_id"), Lower("foo_2"), name="index_name"),
                ]

        self.assertEqual(Bar.check(), [])


@isolate_apps("invalid_models_tests")
class FieldNamesTests(TestCase):
    databases = {"default", "other"}

    def test_ending_with_underscore(self):
        class Model(models.Model):
            field_ = models.CharField(max_length=10)
            m2m_ = models.ManyToManyField("self")

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Field names must not end with an underscore.",
                    obj=Model._meta.get_field("field_"),
                    id="fields.E001",
                ),
                Error(
                    "Field names must not end with an underscore.",
                    obj=Model._meta.get_field("m2m_"),
                    id="fields.E001",
                ),
            ],
        )

    max_column_name_length, column_limit_db_alias = get_max_column_name_length()

    @unittest.skipIf(
        max_column_name_length is None,
        "The database doesn't have a column name length limit.",
    )
    def test_M2M_long_column_name(self):
        """
        Tests the model validation for ManyToManyField column names that exceed the 
        database's column name length limit, ensuring appropriate errors are raised when 
        the model is checked for issues.
        """

        # A model with very long name which will be used to set relations to.
        class VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz(
            models.Model
        ):
            title = models.CharField(max_length=11)

        # Main model for which checks will be performed.
        class ModelWithLongField(models.Model):
            m2m_field = models.ManyToManyField(
                VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
                related_name="rn1",
            )
            m2m_field2 = models.ManyToManyField(
                VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
                related_name="rn2",
                through="m2msimple",
            )
            m2m_field3 = models.ManyToManyField(
                VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
                related_name="rn3",
                through="m2mcomplex",
            )
            fk = models.ForeignKey(
                VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
                models.CASCADE,
                related_name="rn4",
            )

        # Models used for setting `through` in M2M field.
        class m2msimple(models.Model):
            id2 = models.ForeignKey(ModelWithLongField, models.CASCADE)

        class m2mcomplex(models.Model):
            id2 = models.ForeignKey(ModelWithLongField, models.CASCADE)

        long_field_name = "a" * (self.max_column_name_length + 1)
        models.ForeignKey(
            VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
            models.CASCADE,
        ).contribute_to_class(m2msimple, long_field_name)

        models.ForeignKey(
            VeryLongModelNamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz,
            models.CASCADE,
            db_column=long_field_name,
        ).contribute_to_class(m2mcomplex, long_field_name)

        errors = ModelWithLongField.check(databases=("default", "other"))

        # First error because of M2M field set on the model with long name.
        m2m_long_name = (
            "verylongmodelnamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz_id"
        )
        if self.max_column_name_length > len(m2m_long_name):
            # Some databases support names longer than the test name.
            expected = []
        else:
            expected = [
                Error(
                    'Autogenerated column name too long for M2M field "%s". '
                    'Maximum length is "%s" for database "%s".'
                    % (
                        m2m_long_name,
                        self.max_column_name_length,
                        self.column_limit_db_alias,
                    ),
                    hint="Use 'through' to create a separate model for "
                    "M2M and then set column_name using 'db_column'.",
                    obj=ModelWithLongField,
                    id="models.E019",
                )
            ]

        # Second error because the FK specified in the `through` model
        # `m2msimple` has auto-generated name longer than allowed.
        # There will be no check errors in the other M2M because it
        # specifies db_column for the FK in `through` model even if the actual
        # name is longer than the limits of the database.
        expected.append(
            Error(
                'Autogenerated column name too long for M2M field "%s_id". '
                'Maximum length is "%s" for database "%s".'
                % (
                    long_field_name,
                    self.max_column_name_length,
                    self.column_limit_db_alias,
                ),
                hint="Use 'through' to create a separate model for "
                "M2M and then set column_name using 'db_column'.",
                obj=ModelWithLongField,
                id="models.E019",
            )
        )

        self.assertEqual(errors, expected)
        # Check for long column names is called only for specified database
        # aliases.
        self.assertEqual(ModelWithLongField.check(databases=None), [])

    @unittest.skipIf(
        max_column_name_length is None,
        "The database doesn't have a column name length limit.",
    )
    def test_local_field_long_column_name(self):
        """
        Tests that a model validation error is raised when a field's automatically generated column name exceeds the database's maximum allowed length, and verifies that setting a manual column name resolves the issue.
        """

        class ModelWithLongField(models.Model):
            title = models.CharField(max_length=11)

        long_field_name = "a" * (self.max_column_name_length + 1)
        long_field_name2 = "b" * (self.max_column_name_length + 1)
        models.CharField(max_length=11).contribute_to_class(
            ModelWithLongField, long_field_name
        )
        models.CharField(max_length=11, db_column="vlmn").contribute_to_class(
            ModelWithLongField, long_field_name2
        )
        self.assertEqual(
            ModelWithLongField.check(databases=("default", "other")),
            [
                Error(
                    'Autogenerated column name too long for field "%s". '
                    'Maximum length is "%s" for database "%s".'
                    % (
                        long_field_name,
                        self.max_column_name_length,
                        self.column_limit_db_alias,
                    ),
                    hint="Set the column name manually using 'db_column'.",
                    obj=ModelWithLongField,
                    id="models.E018",
                )
            ],
        )
        # Check for long column names is called only for specified database
        # aliases.
        self.assertEqual(ModelWithLongField.check(databases=None), [])

    def test_including_separator(self):
        class Model(models.Model):
            some__field = models.IntegerField()

        self.assertEqual(
            Model.check(),
            [
                Error(
                    'Field names must not contain "__".',
                    obj=Model._meta.get_field("some__field"),
                    id="fields.E002",
                )
            ],
        )

    def test_pk(self):
        class Model(models.Model):
            pk = models.IntegerField()

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'pk' is a reserved word that cannot be used as a field name.",
                    obj=Model._meta.get_field("pk"),
                    id="fields.E003",
                )
            ],
        )

    def test_db_column_clash(self):
        class Model(models.Model):
            foo = models.IntegerField()
            bar = models.IntegerField(db_column="foo")

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Field 'bar' has column name 'foo' that is used by "
                    "another field.",
                    hint="Specify a 'db_column' for the field.",
                    obj=Model,
                    id="models.E007",
                )
            ],
        )


@isolate_apps("invalid_models_tests")
class ShadowingFieldsTests(SimpleTestCase):
    def test_field_name_clash_with_child_accessor(self):
        """
        Tests that a field name in a child model that clashes with an accessor automatically created by a parent's field raises an error.
        """
        class Parent(models.Model):
            pass

        class Child(Parent):
            child = models.CharField(max_length=100)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "The field 'child' clashes with the field "
                    "'child' from model 'invalid_models_tests.parent'.",
                    obj=Child._meta.get_field("child"),
                    id="models.E006",
                )
            ],
        )

    def test_field_name_clash_with_m2m_through(self):
        """
        Tests the error handling for aMany-To-Many field name clash with the 'through' model when the field name in the model overlaps with a field name in a parent model.
        """
        class Parent(models.Model):
            clash_id = models.IntegerField()

        class Child(Parent):
            clash = models.ForeignKey("Child", models.CASCADE)

        class Model(models.Model):
            parents = models.ManyToManyField(
                to=Parent,
                through="Through",
                through_fields=["parent", "model"],
            )

        class Through(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)
            model = models.ForeignKey(Model, models.CASCADE)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "The field 'clash' clashes with the field 'clash_id' from "
                    "model 'invalid_models_tests.parent'.",
                    obj=Child._meta.get_field("clash"),
                    id="models.E006",
                )
            ],
        )

    def test_multiinheritance_clash(self):
        """

        Tests that multiple inheritance clashes between two parent models are correctly identified.

        Verifies that checks for field clashes, including both the auto-generated 'id' field and explicitly defined fields, are handled properly when a child model inherits from multiple parents with conflicting fields.

        """
        class Mother(models.Model):
            clash = models.IntegerField()

        class Father(models.Model):
            clash = models.IntegerField()

        class Child(Mother, Father):
            # Here we have two clashed: id (automatic field) and clash, because
            # both parents define these fields.
            pass

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "The field 'id' from parent model "
                    "'invalid_models_tests.mother' clashes with the field 'id' "
                    "from parent model 'invalid_models_tests.father'.",
                    obj=Child,
                    id="models.E005",
                ),
                Error(
                    "The field 'clash' from parent model "
                    "'invalid_models_tests.mother' clashes with the field 'clash' "
                    "from parent model 'invalid_models_tests.father'.",
                    obj=Child,
                    id="models.E005",
                ),
            ],
        )

    def test_inheritance_clash(self):
        """
        Checks for inheritance model field clashes, ensuring that foreign key fields do not conflict with fields inherited from parent models.
        """
        class Parent(models.Model):
            f_id = models.IntegerField()

        class Target(models.Model):
            # This field doesn't result in a clash.
            f_id = models.IntegerField()

        class Child(Parent):
            # This field clashes with parent "f_id" field.
            f = models.ForeignKey(Target, models.CASCADE)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "The field 'f' clashes with the field 'f_id' "
                    "from model 'invalid_models_tests.parent'.",
                    obj=Child._meta.get_field("f"),
                    id="models.E006",
                )
            ],
        )

    def test_multigeneration_inheritance(self):
        """
        Tests multigeneration inheritance in model fields to ensure field name clashes are detected across hierarchical model relationships.
        """
        class GrandParent(models.Model):
            clash = models.IntegerField()

        class Parent(GrandParent):
            pass

        class Child(Parent):
            pass

        class GrandChild(Child):
            clash = models.IntegerField()

        self.assertEqual(
            GrandChild.check(),
            [
                Error(
                    "The field 'clash' clashes with the field 'clash' "
                    "from model 'invalid_models_tests.grandparent'.",
                    obj=GrandChild._meta.get_field("clash"),
                    id="models.E006",
                )
            ],
        )

    def test_diamond_mti_common_parent(self):
        """

        Tests that Multi-Table Inheritance (MTI) model validation correctly identifies 
        clashing fields when a model has a common parent with one of its base classes.

        """
        class GrandParent(models.Model):
            pass

        class Parent(GrandParent):
            pass

        class Child(Parent):
            pass

        class MTICommonParentModel(Child, GrandParent):
            pass

        self.assertEqual(
            MTICommonParentModel.check(),
            [
                Error(
                    "The field 'grandparent_ptr' clashes with the field "
                    "'grandparent_ptr' from model 'invalid_models_tests.parent'.",
                    obj=MTICommonParentModel,
                    id="models.E006",
                )
            ],
        )

    def test_id_clash(self):
        """
        Tests for id clash error between a foreign key and an integer field in a model, verifying that Django correctly raises an error when a model contains both a foreign key to another model and an integer field with a name that could be mistaken for the foreign key's id.
        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            fk = models.ForeignKey(Target, models.CASCADE)
            fk_id = models.IntegerField()

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "The field 'fk_id' clashes with the field 'fk' from model "
                    "'invalid_models_tests.model'.",
                    obj=Model._meta.get_field("fk_id"),
                    id="models.E006",
                )
            ],
        )


@isolate_apps("invalid_models_tests")
class OtherModelTests(SimpleTestCase):
    def test_unique_primary_key(self):
        """
        Tests that a primary key field in a model must be named 'id' and have primary_key=True.
        """
        invalid_id = models.IntegerField(primary_key=False)

        class Model(models.Model):
            id = invalid_id

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'id' can only be used as a field name if the field also sets "
                    "'primary_key=True'.",
                    obj=Model,
                    id="models.E004",
                ),
            ],
        )

    def test_ordering_non_iterable(self):
        """
        Tests that the model's Meta.ordering attribute raises an error when set to a non-iterable value, such as a string, instead of the expected tuple or list.
        """
        class Model(models.Model):
            class Meta:
                ordering = "missing_field"

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'ordering' must be a tuple or list "
                    "(even if you want to order by only one field).",
                    obj=Model,
                    id="models.E014",
                ),
            ],
        )

    def test_just_ordering_no_errors(self):
        """
        Tests that a model with a PositiveIntegerField specified as the ordering field does not raise any errors when checked.
        """
        class Model(models.Model):
            order = models.PositiveIntegerField()

            class Meta:
                ordering = ["order"]

        self.assertEqual(Model.check(), [])

    def test_just_order_with_respect_to_no_errors(self):
        """

        Tests that the Answer model, which has an order_with_respect_to field, 
        checks for errors correctly when no errors are present, specifically 
        when ordering is done with respect to its question foreign key field.

        """
        class Question(models.Model):
            pass

        class Answer(models.Model):
            question = models.ForeignKey(Question, models.CASCADE)

            class Meta:
                order_with_respect_to = "question"

        self.assertEqual(Answer.check(), [])

    def test_ordering_with_order_with_respect_to(self):
        """
        Tests that using 'ordering' and 'order_with_respect_to' together in a model's Meta raises an error, as these two settings are mutually exclusive.
        """
        class Question(models.Model):
            pass

        class Answer(models.Model):
            question = models.ForeignKey(Question, models.CASCADE)
            order = models.IntegerField()

            class Meta:
                order_with_respect_to = "question"
                ordering = ["order"]

        self.assertEqual(
            Answer.check(),
            [
                Error(
                    "'ordering' and 'order_with_respect_to' cannot be used together.",
                    obj=Answer,
                    id="models.E021",
                ),
            ],
        )

    def test_non_valid(self):
        """

        Verifies that the check method correctly identifies a non-existent 'ordering' field with a ManyToManyField relation.

        """
        class RelationModel(models.Model):
            pass

        class Model(models.Model):
            relation = models.ManyToManyField(RelationModel)

            class Meta:
                ordering = ["relation"]

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'relation'.",
                    obj=Model,
                    id="models.E015",
                ),
            ],
        )

    def test_ordering_pointing_to_missing_field(self):
        """
        Tests that a model's Meta.ordering attribute raises an error when referencing a field that does not exist in the model.
        """
        class Model(models.Model):
            class Meta:
                ordering = ("missing_field",)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'missing_field'.",
                    obj=Model,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_to_missing_foreignkey_field(self):
        """
        Tests a model's ordering attribute when pointing to a missing foreign key field, ensuring a correct error is raised when the field does not exist.
        """
        class Model(models.Model):
            missing_fk_field = models.IntegerField()

            class Meta:
                ordering = ("missing_fk_field_id",)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'missing_fk_field_id'.",
                    obj=Model,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_to_missing_related_field(self):
        """
        Tests that a model with an ordering specification that points to a missing related field is detected and reported as an error by the model's check method.
        """
        class Model(models.Model):
            test = models.IntegerField()

            class Meta:
                ordering = ("missing_related__id",)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'missing_related__id'.",
                    obj=Model,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_to_missing_related_model_field(self):
        """

        Tests that the model validation correctly identifies ordering fields that reference
        missing related model fields.

        """
        class Parent(models.Model):
            pass

        class Child(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)

            class Meta:
                ordering = ("parent__missing_field",)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'parent__missing_field'.",
                    obj=Child,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_to_non_related_field(self):
        """
        Tests the validation of model ordering when referencing a non-existent field through a non-related field, ensuring the check method returns the expected error when attempting to order by a field that does not exist.
        """
        class Child(models.Model):
            parent = models.IntegerField()

            class Meta:
                ordering = ("parent__missing_field",)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'parent__missing_field'.",
                    obj=Child,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_to_two_related_model_field(self):
        """
        Tests that the model checker correctly identifies and reports an error when the 'ordering' Meta option references a related field that does not exist.
        """
        class Parent2(models.Model):
            pass

        class Parent1(models.Model):
            parent2 = models.ForeignKey(Parent2, models.CASCADE)

        class Child(models.Model):
            parent1 = models.ForeignKey(Parent1, models.CASCADE)

            class Meta:
                ordering = ("parent1__parent2__missing_field",)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'parent1__parent2__missing_field'.",
                    obj=Child,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_pointing_multiple_times_to_model_fields(self):
        """
        Tests that a model's Meta.ordering attribute correctly handles references to nonexistent fields in a related model, specifically when attempting to order by a field that is multiple relationships deep but does not exist.
        """
        class Parent(models.Model):
            field1 = models.CharField(max_length=100)
            field2 = models.CharField(max_length=100)

        class Child(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)

            class Meta:
                ordering = ("parent__field1__field2",)

        self.assertEqual(
            Child.check(),
            [
                Error(
                    "'ordering' refers to the nonexistent field, related field, "
                    "or lookup 'parent__field1__field2'.",
                    obj=Child,
                    id="models.E015",
                )
            ],
        )

    def test_ordering_allows_registered_lookups(self):
        """
        Tests that model ordering allows registered lookup functions, specifically Lower case, to be used in the Meta ordering definition without raising errors.
        """
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__lower",)

        with register_lookup(models.CharField, Lower):
            self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_lookup_not_transform(self):
        """
        Verifies that a model with an `ordering` Meta attribute pointing to a lookup (like 'isnull') does not incorrectly trigger any model checks, ensuring expected model validation behavior.
        """
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__isnull",)

        self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_related_model_pk(self):
        """
        Tests whether the Child model's foreign key to the Parent model can be used for ordering, verifying that no errors are raised when checking the model's ordering definition.
        """
        class Parent(models.Model):
            pass

        class Child(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)

            class Meta:
                ordering = ("parent__pk",)

        self.assertEqual(Child.check(), [])

    def test_ordering_pointing_to_foreignkey_field(self):
        """
        Tests that Django models do not allow ordering to be specified via a field that references a foreign key directly.
        """
        class Parent(models.Model):
            pass

        class Child(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)

            class Meta:
                ordering = ("parent_id",)

        self.assertFalse(Child.check())

    def test_name_beginning_with_underscore(self):
        class _Model(models.Model):
            pass

        self.assertEqual(
            _Model.check(),
            [
                Error(
                    "The model name '_Model' cannot start or end with an underscore "
                    "as it collides with the query lookup syntax.",
                    obj=_Model,
                    id="models.E023",
                )
            ],
        )

    def test_name_ending_with_underscore(self):
        class Model_(models.Model):
            pass

        self.assertEqual(
            Model_.check(),
            [
                Error(
                    "The model name 'Model_' cannot start or end with an underscore "
                    "as it collides with the query lookup syntax.",
                    obj=Model_,
                    id="models.E023",
                )
            ],
        )

    def test_name_contains_double_underscores(self):
        class Test__Model(models.Model):
            pass

        self.assertEqual(
            Test__Model.check(),
            [
                Error(
                    "The model name 'Test__Model' cannot contain double underscores "
                    "as it collides with the query lookup syntax.",
                    obj=Test__Model,
                    id="models.E024",
                )
            ],
        )

    def test_property_and_related_field_accessor_clash(self):
        class Model(models.Model):
            fk = models.ForeignKey("self", models.CASCADE)

        # Override related field accessor.
        Model.fk_id = property(lambda self: "ERROR")

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "The property 'fk_id' clashes with a related field accessor.",
                    obj=Model,
                    id="models.E025",
                )
            ],
        )

    def test_inherited_overriden_property_no_clash(self):
        """
        ..: 
            Tests that a model inheriting a property from a parent class does not clash with an attribute of the same name, 
            when the property is overridden in the child class.
        """
        class Cheese:
            @property
            def filling_id(self):
                pass

        class Sandwich(Cheese, models.Model):
            filling = models.ForeignKey("self", models.CASCADE)

        self.assertEqual(Sandwich.check(), [])

    def test_single_primary_key(self):
        class Model(models.Model):
            foo = models.IntegerField(primary_key=True)
            bar = models.IntegerField(primary_key=True)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "The model cannot have more than one field with "
                    "'primary_key=True'.",
                    obj=Model,
                    id="models.E026",
                )
            ],
        )

    @override_settings(TEST_SWAPPED_MODEL_BAD_VALUE="not-a-model")
    def test_swappable_missing_app_name(self):
        """
        Tests that the swappable model validation raises an error when the provided value is missing the app name.
        """
        class Model(models.Model):
            class Meta:
                swappable = "TEST_SWAPPED_MODEL_BAD_VALUE"

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'TEST_SWAPPED_MODEL_BAD_VALUE' is not of the form "
                    "'app_label.app_name'.",
                    id="models.E001",
                ),
            ],
        )

    @override_settings(TEST_SWAPPED_MODEL_BAD_MODEL="not_an_app.Target")
    def test_swappable_missing_app(self):
        """
        Tests the error handling of a swappable model when the referenced app is missing.
        """
        class Model(models.Model):
            class Meta:
                swappable = "TEST_SWAPPED_MODEL_BAD_MODEL"

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "'TEST_SWAPPED_MODEL_BAD_MODEL' references 'not_an_app.Target', "
                    "which has not been installed, or is abstract.",
                    id="models.E002",
                ),
            ],
        )

    def test_two_m2m_through_same_relationship(self):
        """
        Tests that a model validation error is raised when two many-to-many fields 
        use the same intermediate model through the same relationship.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            primary = models.ManyToManyField(
                Person, through="Membership", related_name="primary"
            )
            secondary = models.ManyToManyField(
                Person, through="Membership", related_name="secondary"
            )

        class Membership(models.Model):
            person = models.ForeignKey(Person, models.CASCADE)
            group = models.ForeignKey(Group, models.CASCADE)

        self.assertEqual(
            Group.check(),
            [
                Error(
                    "The model has two identical many-to-many relations through "
                    "the intermediate model 'invalid_models_tests.Membership'.",
                    obj=Group,
                    id="models.E003",
                )
            ],
        )

    def test_two_m2m_through_same_model_with_different_through_fields(self):
        """
        Tests that two Many-To-Many fields in the same model can use the same intermediate model with different through fields, without causing conflicts or errors. Verifies the correctness of the ShippingMethod model's relationships with Country through ShippingMethodPrice.
        """
        class Country(models.Model):
            pass

        class ShippingMethod(models.Model):
            to_countries = models.ManyToManyField(
                Country,
                through="ShippingMethodPrice",
                through_fields=("method", "to_country"),
            )
            from_countries = models.ManyToManyField(
                Country,
                through="ShippingMethodPrice",
                through_fields=("method", "from_country"),
                related_name="+",
            )

        class ShippingMethodPrice(models.Model):
            method = models.ForeignKey(ShippingMethod, models.CASCADE)
            to_country = models.ForeignKey(Country, models.CASCADE)
            from_country = models.ForeignKey(Country, models.CASCADE)

        self.assertEqual(ShippingMethod.check(), [])

    def test_onetoone_with_parent_model(self):
        """
        Tests a one-to-one relationship between two models, specifically when one model is a subclass of the other, to ensure that the validation check does not return any errors.
        """
        class Place(models.Model):
            pass

        class ParkingLot(Place):
            other_place = models.OneToOneField(
                Place, models.CASCADE, related_name="other_parking"
            )

        self.assertEqual(ParkingLot.check(), [])

    def test_onetoone_with_explicit_parent_link_parent_model(self):
        """
        Tests that a one-to-one relationship with an explicit parent link on the parent model is correctly validated.
        """
        class Place(models.Model):
            pass

        class ParkingLot(Place):
            place = models.OneToOneField(
                Place, models.CASCADE, parent_link=True, primary_key=True
            )
            other_place = models.OneToOneField(
                Place, models.CASCADE, related_name="other_parking"
            )

        self.assertEqual(ParkingLot.check(), [])

    def test_m2m_table_name_clash(self):
        """

        Tests that a ManyToMany field raises an error when its intermediary table name clashes with another model's table name.

        """
        class Foo(models.Model):
            bar = models.ManyToManyField("Bar", db_table="myapp_bar")

            class Meta:
                db_table = "myapp_foo"

        class Bar(models.Model):
            class Meta:
                db_table = "myapp_bar"

        self.assertEqual(
            Foo.check(),
            [
                Error(
                    "The field's intermediary table 'myapp_bar' clashes with the "
                    "table name of 'invalid_models_tests.Bar'.",
                    obj=Foo._meta.get_field("bar"),
                    id="fields.E340",
                )
            ],
        )

    @override_settings(
        DATABASE_ROUTERS=["invalid_models_tests.test_models.EmptyRouter"]
    )
    def test_m2m_table_name_clash_database_routers_installed(self):
        """
        Tests for field warnings when a many-to-many field's intermediary table name clashes 
        with an existing model table name, specifically when database routers are installed.
        """
        class Foo(models.Model):
            bar = models.ManyToManyField("Bar", db_table="myapp_bar")

            class Meta:
                db_table = "myapp_foo"

        class Bar(models.Model):
            class Meta:
                db_table = "myapp_bar"

        self.assertEqual(
            Foo.check(),
            [
                Warning(
                    "The field's intermediary table 'myapp_bar' clashes with the "
                    "table name of 'invalid_models_tests.Bar'.",
                    obj=Foo._meta.get_field("bar"),
                    hint=(
                        "You have configured settings.DATABASE_ROUTERS. Verify "
                        "that the table of 'invalid_models_tests.Bar' is "
                        "correctly routed to a separate database."
                    ),
                    id="fields.W344",
                ),
            ],
        )

    def test_m2m_field_table_name_clash(self):
        """
        Tests that Many-to-Many fields with identical table names generate a clash error, ensuring Django's model validation catches and reports table naming conflicts between different models.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foos = models.ManyToManyField(Foo, db_table="clash")

        class Baz(models.Model):
            foos = models.ManyToManyField(Foo, db_table="clash")

        self.assertEqual(
            Bar.check() + Baz.check(),
            [
                Error(
                    "The field's intermediary table 'clash' clashes with the "
                    "table name of 'invalid_models_tests.Baz.foos'.",
                    obj=Bar._meta.get_field("foos"),
                    id="fields.E340",
                ),
                Error(
                    "The field's intermediary table 'clash' clashes with the "
                    "table name of 'invalid_models_tests.Bar.foos'.",
                    obj=Baz._meta.get_field("foos"),
                    id="fields.E340",
                ),
            ],
        )

    @override_settings(
        DATABASE_ROUTERS=["invalid_models_tests.test_models.EmptyRouter"]
    )
    def test_m2m_field_table_name_clash_database_routers_installed(self):
        """
        Tests the clash of ManyToMany field table names between models when database routers are installed.

        Verifies that the model validation correctly identifies and warns about table name clashes
        in the presence of custom database routing configuration, ensuring proper database separation.
        """
        class Foo(models.Model):
            pass

        class Bar(models.Model):
            foos = models.ManyToManyField(Foo, db_table="clash")

        class Baz(models.Model):
            foos = models.ManyToManyField(Foo, db_table="clash")

        self.assertEqual(
            Bar.check() + Baz.check(),
            [
                Warning(
                    "The field's intermediary table 'clash' clashes with the "
                    "table name of 'invalid_models_tests.%s.foos'." % clashing_model,
                    obj=model_cls._meta.get_field("foos"),
                    hint=(
                        "You have configured settings.DATABASE_ROUTERS. Verify "
                        "that the table of 'invalid_models_tests.%s.foos' is "
                        "correctly routed to a separate database." % clashing_model
                    ),
                    id="fields.W344",
                )
                for model_cls, clashing_model in [(Bar, "Baz"), (Baz, "Bar")]
            ],
        )

    def test_m2m_autogenerated_table_name_clash(self):
        """
        Tests that an error is raised when a many-to-many field's 
        intermediary table name clashes with an existing model's table name.
        """
        class Foo(models.Model):
            class Meta:
                db_table = "bar_foos"

        class Bar(models.Model):
            # The autogenerated `db_table` will be bar_foos.
            foos = models.ManyToManyField(Foo)

            class Meta:
                db_table = "bar"

        self.assertEqual(
            Bar.check(),
            [
                Error(
                    "The field's intermediary table 'bar_foos' clashes with the "
                    "table name of 'invalid_models_tests.Foo'.",
                    obj=Bar._meta.get_field("foos"),
                    id="fields.E340",
                )
            ],
        )

    @override_settings(
        DATABASE_ROUTERS=["invalid_models_tests.test_models.EmptyRouter"]
    )
    def test_m2m_autogenerated_table_name_clash_database_routers_installed(self):
        """

        Tests the automatic table name generation for many-to-many fields to detect clashes 
        when using database routers, ensuring the system correctly identifies potential errors.

        """
        class Foo(models.Model):
            class Meta:
                db_table = "bar_foos"

        class Bar(models.Model):
            # The autogenerated db_table is bar_foos.
            foos = models.ManyToManyField(Foo)

            class Meta:
                db_table = "bar"

        self.assertEqual(
            Bar.check(),
            [
                Warning(
                    "The field's intermediary table 'bar_foos' clashes with the "
                    "table name of 'invalid_models_tests.Foo'.",
                    obj=Bar._meta.get_field("foos"),
                    hint=(
                        "You have configured settings.DATABASE_ROUTERS. Verify "
                        "that the table of 'invalid_models_tests.Foo' is "
                        "correctly routed to a separate database."
                    ),
                    id="fields.W344",
                ),
            ],
        )

    def test_m2m_unmanaged_shadow_models_not_checked(self):
        """
        Tests that unmanaged ManyToManyField models with a custom through model do not trigger validation checks.
        """
        class A1(models.Model):
            pass

        class C1(models.Model):
            mm_a = models.ManyToManyField(A1, db_table="d1")

        # Unmanaged models that shadow the above models. Reused table names
        # shouldn't be flagged by any checks.
        class A2(models.Model):
            class Meta:
                managed = False

        class C2(models.Model):
            mm_a = models.ManyToManyField(A2, through="Intermediate")

            class Meta:
                managed = False

        class Intermediate(models.Model):
            a2 = models.ForeignKey(A2, models.CASCADE, db_column="a1_id")
            c2 = models.ForeignKey(C2, models.CASCADE, db_column="c1_id")

            class Meta:
                db_table = "d1"
                managed = False

        self.assertEqual(C1.check(), [])
        self.assertEqual(C2.check(), [])

    def test_m2m_to_concrete_and_proxy_allowed(self):
        """
        Tests that many-to-many relationships are correctly established when using both a concrete model and a proxy model as intermediates. Verifies that the relationship checks pass without raising any errors.
        """
        class A(models.Model):
            pass

        class Through(models.Model):
            a = models.ForeignKey("A", models.CASCADE)
            c = models.ForeignKey("C", models.CASCADE)

        class ThroughProxy(Through):
            class Meta:
                proxy = True

        class C(models.Model):
            mm_a = models.ManyToManyField(A, through=Through)
            mm_aproxy = models.ManyToManyField(
                A, through=ThroughProxy, related_name="proxied_m2m"
            )

        self.assertEqual(C.check(), [])

    @isolate_apps("django.contrib.auth", kwarg_name="apps")
    def test_lazy_reference_checks(self, apps):
        """
        Tests the check for lazy references in models and signals, ensuring that the application correctly identifies and reports references to non-existent models and apps.
        """
        class DummyModel(models.Model):
            author = models.ForeignKey("Author", models.CASCADE)

            class Meta:
                app_label = "invalid_models_tests"

        class DummyClass:
            def __call__(self, **kwargs):
                pass

            def dummy_method(self):
                pass

        def dummy_function(*args, **kwargs):
            pass

        apps.lazy_model_operation(dummy_function, ("auth", "imaginarymodel"))
        apps.lazy_model_operation(dummy_function, ("fanciful_app", "imaginarymodel"))

        post_init.connect(dummy_function, sender="missing-app.Model", apps=apps)
        post_init.connect(DummyClass(), sender="missing-app.Model", apps=apps)
        post_init.connect(
            DummyClass().dummy_method, sender="missing-app.Model", apps=apps
        )

        self.assertEqual(
            _check_lazy_references(apps),
            [
                Error(
                    "%r contains a lazy reference to auth.imaginarymodel, "
                    "but app 'auth' doesn't provide model 'imaginarymodel'."
                    % dummy_function,
                    obj=dummy_function,
                    id="models.E022",
                ),
                Error(
                    "%r contains a lazy reference to fanciful_app.imaginarymodel, "
                    "but app 'fanciful_app' isn't installed." % dummy_function,
                    obj=dummy_function,
                    id="models.E022",
                ),
                Error(
                    "An instance of class 'DummyClass' was connected to "
                    "the 'post_init' signal with a lazy reference to the sender "
                    "'missing-app.model', but app 'missing-app' isn't installed.",
                    hint=None,
                    obj="invalid_models_tests.test_models",
                    id="signals.E001",
                ),
                Error(
                    "Bound method 'DummyClass.dummy_method' was connected to the "
                    "'post_init' signal with a lazy reference to the sender "
                    "'missing-app.model', but app 'missing-app' isn't installed.",
                    hint=None,
                    obj="invalid_models_tests.test_models",
                    id="signals.E001",
                ),
                Error(
                    "The field invalid_models_tests.DummyModel.author was declared "
                    "with a lazy reference to 'invalid_models_tests.author', but app "
                    "'invalid_models_tests' isn't installed.",
                    hint=None,
                    obj=DummyModel.author.field,
                    id="fields.E307",
                ),
                Error(
                    "The function 'dummy_function' was connected to the 'post_init' "
                    "signal with a lazy reference to the sender "
                    "'missing-app.model', but app 'missing-app' isn't installed.",
                    hint=None,
                    obj="invalid_models_tests.test_models",
                    id="signals.E001",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class DbTableCommentTests(TestCase):
    def test_db_table_comment(self):
        """
        Tests the database table comment functionality by checking if a warning is raised when the database does not support comments on tables.
        """
        class Model(models.Model):
            class Meta:
                db_table_comment = "Table comment"

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_comments
            else [
                Warning(
                    f"{connection.display_name} does not support comments on tables "
                    f"(db_table_comment).",
                    obj=Model,
                    id="models.W046",
                ),
            ]
        )
        self.assertEqual(errors, expected)

    def test_db_table_comment_required_db_features(self):
        """
        Verifies that a model's table comment is correctly validated against required database features.
        """
        class Model(models.Model):
            class Meta:
                db_table_comment = "Table comment"
                required_db_features = {"supports_comments"}

        self.assertEqual(Model.check(databases=self.databases), [])


class MultipleAutoFieldsTests(TestCase):
    def test_multiple_autofields(self):
        """
        Tests that a model cannot have multiple auto-generated fields, ensuring data integrity by preventing incorrect model definitions.
        """
        msg = (
            "Model invalid_models_tests.MultipleAutoFields can't have more "
            "than one auto-generated field."
        )
        with self.assertRaisesMessage(ValueError, msg):

            class MultipleAutoFields(models.Model):
                auto1 = models.AutoField(primary_key=True)
                auto2 = models.AutoField(primary_key=True)


@isolate_apps("invalid_models_tests")
class JSONFieldTests(TestCase):
    @skipUnlessDBFeature("supports_json_field")
    def test_ordering_pointing_to_json_field_value(self):
        """

        Tests that a model can be ordered by a value within a JSONField.

        This test ensures that the ORM can correctly handle ordering based on a JSON field's value.

        """
        class Model(models.Model):
            field = models.JSONField()

            class Meta:
                ordering = ["field__value"]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_check_jsonfield(self):
        """

        Checks if a model with a JSONField can be validated by the database.

        If the database does not support JSONFields, a list containing a validation error is expected.
        Otherwise, an empty list is returned.

        """
        class Model(models.Model):
            field = models.JSONField()

        error = Error(
            "%s does not support JSONFields." % connection.display_name,
            obj=Model,
            id="fields.E180",
        )
        expected = [] if connection.features.supports_json_field else [error]
        self.assertEqual(Model.check(databases=self.databases), expected)

    def test_check_jsonfield_required_db_features(self):
        """
        Checks if models with JSONFields validate the required database features for storing JSON data, ensuring compatibility with the underlying database system.
        """
        class Model(models.Model):
            field = models.JSONField()

            class Meta:
                required_db_features = {"supports_json_field"}

        self.assertEqual(Model.check(databases=self.databases), [])


@isolate_apps("invalid_models_tests")
class ConstraintsTests(TestCase):
    def test_check_constraints(self):
        """
        Tests the model's check constraints for integrity, specifically the ability to enforce a minimum age requirement, and verifies the correct handling of database backends with and without check constraint support.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        condition=models.Q(age__gte=18), name="is_adult"
                    )
                ]

        errors = Model.check(databases=self.databases)
        warn = Warning(
            "%s does not support check constraints." % connection.display_name,
            hint=(
                "A constraint won't be created. Silence this warning if you "
                "don't care about it."
            ),
            obj=Model,
            id="models.W027",
        )
        expected = (
            [] if connection.features.supports_table_check_constraints else [warn]
        )
        self.assertCountEqual(errors, expected)

    def test_check_constraints_required_db_features(self):
        """
        Verifies that the check_constraints_required_db_features validation works correctly.

        Tests that a model with required database features and a check constraint raises no errors when validated against the available databases if the required feature is supported.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_table_check_constraints"}
                constraints = [
                    models.CheckConstraint(
                        condition=models.Q(age__gte=18), name="is_adult"
                    )
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_check_constraint_pointing_to_missing_field(self):
        """

        Checks that creating a model with a check constraint referencing a missing field raises an error.

        Validates that the check constraint validation detects and reports a nonexistent field reference when the database supports table check constraints.

        """
        class Model(models.Model):
            class Meta:
                required_db_features = {"supports_table_check_constraints"}
                constraints = [
                    models.CheckConstraint(
                        name="name",
                        condition=models.Q(missing_field=2),
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            (
                [
                    Error(
                        "'constraints' refers to the nonexistent field "
                        "'missing_field'.",
                        obj=Model,
                        id="models.E012",
                    ),
                ]
                if connection.features.supports_table_check_constraints
                else []
            ),
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_reverse_fk(self):
        """

        Tests that a check constraint referencing a reverse foreign key raises a validation error.

        """
        class Model(models.Model):
            parent = models.ForeignKey("self", models.CASCADE, related_name="parents")

            class Meta:
                constraints = [
                    models.CheckConstraint(name="name", condition=models.Q(parents=3)),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'parents'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_reverse_o2o(self):
        """
        Tests that a check constraint in a model pointing to a reverse one-to-one field raises the correct error, as Django does not support this type of constraint.
        """
        class Model(models.Model):
            parent = models.OneToOneField("self", models.CASCADE)

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        name="name",
                        condition=models.Q(model__isnull=True),
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'model'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_m2m_field(self):
        """
        Tests that using a ManyToManyField in a CheckConstraint raises a validation error.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                constraints = [
                    models.CheckConstraint(name="name", condition=models.Q(m2m=2)),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'constraints'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_fk(self):
        """
        Tests that check constraints referencing foreign keys are properly validated.\"\"\"

        \"\"\"Verifies that the model's check constraint condition pointing to a foreign key is handled correctly.
        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            fk_1 = models.ForeignKey(Target, models.CASCADE, related_name="target_1")
            fk_2 = models.ForeignKey(Target, models.CASCADE, related_name="target_2")

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        name="name",
                        condition=models.Q(fk_1_id=2) | models.Q(fk_2=2),
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_pk(self):
        """
        Tests that a check constraint pointing to the primary key is correctly evaluated.
        """
        class Model(models.Model):
            age = models.SmallIntegerField()

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        name="name",
                        condition=models.Q(pk__gt=5) & models.Q(age__gt=models.F("pk")),
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_non_local_field(self):
        """
        Tests that a CheckConstraint on a model with multi-table inheritance correctly raises an error when referencing a non-local field.
        """
        class Parent(models.Model):
            field1 = models.IntegerField()

        class Child(Parent):
            pass

            class Meta:
                constraints = [
                    models.CheckConstraint(name="name", condition=models.Q(field1=1)),
                ]

        self.assertEqual(
            Child.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to field 'field1' which is not local to "
                    "model 'Child'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Child,
                    id="models.E016",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_joined_fields(self):
        """
        Tests Django's validation of check constraints that reference joined fields across models, ensuring that the framework correctly raises errors when these constraints are defined.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)
            field1 = models.PositiveSmallIntegerField()
            field2 = models.PositiveSmallIntegerField()
            field3 = models.PositiveSmallIntegerField()
            parent = models.ForeignKey("self", models.CASCADE)
            previous = models.OneToOneField("self", models.CASCADE, related_name="next")

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        name="name1",
                        condition=models.Q(
                            field1__lt=models.F("parent__field1")
                            + models.F("parent__field2")
                        ),
                    ),
                    models.CheckConstraint(
                        name="name2", condition=models.Q(name=Lower("parent__name"))
                    ),
                    models.CheckConstraint(
                        name="name3",
                        condition=models.Q(parent__field3=models.F("field1")),
                    ),
                    models.CheckConstraint(
                        name="name4",
                        condition=models.Q(name=Lower("previous__name")),
                    ),
                ]

        joined_fields = [
            "parent__field1",
            "parent__field2",
            "parent__field3",
            "parent__name",
            "previous__name",
        ]
        errors = Model.check(databases=self.databases)
        expected_errors = [
            Error(
                "'constraints' refers to the joined field '%s'." % field_name,
                obj=Model,
                id="models.E041",
            )
            for field_name in joined_fields
        ]
        self.assertCountEqual(errors, expected_errors)

    @skipUnlessDBFeature("supports_table_check_constraints")
    def test_check_constraint_pointing_to_joined_fields_complex_check(self):
        """

        Tests that a CheckConstraint which references joined fields raises the expected validation error.

        """
        class Model(models.Model):
            name = models.PositiveSmallIntegerField()
            field1 = models.PositiveSmallIntegerField()
            field2 = models.PositiveSmallIntegerField()
            parent = models.ForeignKey("self", models.CASCADE)

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        name="name",
                        condition=models.Q(
                            (
                                models.Q(name="test")
                                & models.Q(field1__lt=models.F("parent__field1"))
                            )
                            | (
                                models.Q(name__startswith=Lower("parent__name"))
                                & models.Q(
                                    field1__gte=(
                                        models.F("parent__field1")
                                        + models.F("parent__field2")
                                    )
                                )
                            )
                        )
                        | (models.Q(name="test1")),
                    ),
                ]

        joined_fields = ["parent__field1", "parent__field2", "parent__name"]
        errors = Model.check(databases=self.databases)
        expected_errors = [
            Error(
                "'constraints' refers to the joined field '%s'." % field_name,
                obj=Model,
                id="models.E041",
            )
            for field_name in joined_fields
        ]
        self.assertCountEqual(errors, expected_errors)

    def test_check_constraint_raw_sql_check(self):
        """
        Tests that check constraints with raw SQL conditions raise the expected warnings when validating the model.
        """
        class Model(models.Model):
            class Meta:
                required_db_features = {"supports_table_check_constraints"}
                constraints = [
                    models.CheckConstraint(
                        condition=models.Q(id__gt=0), name="q_check"
                    ),
                    models.CheckConstraint(
                        condition=models.ExpressionWrapper(
                            models.Q(price__gt=20),
                            output_field=models.BooleanField(),
                        ),
                        name="expression_wrapper_check",
                    ),
                    models.CheckConstraint(
                        condition=models.expressions.RawSQL(
                            "id = 0",
                            params=(),
                            output_field=models.BooleanField(),
                        ),
                        name="raw_sql_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.ExpressionWrapper(
                                models.Q(
                                    models.expressions.RawSQL(
                                        "id = 0",
                                        params=(),
                                        output_field=models.BooleanField(),
                                    )
                                ),
                                output_field=models.BooleanField(),
                            )
                        ),
                        name="nested_raw_sql_check",
                    ),
                ]

        expected_warnings = (
            [
                Warning(
                    "Check constraint 'raw_sql_check' contains RawSQL() expression and "
                    "won't be validated during the model full_clean().",
                    hint="Silence this warning if you don't care about it.",
                    obj=Model,
                    id="models.W045",
                ),
                Warning(
                    "Check constraint 'nested_raw_sql_check' contains RawSQL() "
                    "expression and won't be validated during the model full_clean().",
                    hint="Silence this warning if you don't care about it.",
                    obj=Model,
                    id="models.W045",
                ),
            ]
            if connection.features.supports_table_check_constraints
            else []
        )
        self.assertEqual(Model.check(databases=self.databases), expected_warnings)

    def test_unique_constraint_with_condition(self):
        """
        Tests the unique constraint on a model field with a condition, verifying the database backend supports it and checking for expected warnings.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_gte_100",
                        condition=models.Q(age__gte=100),
                    ),
                ]

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_partial_indexes
            else [
                Warning(
                    "%s does not support unique constraints with conditions."
                    % connection.display_name,
                    hint=(
                        "A constraint won't be created. Silence this warning if "
                        "you don't care about it."
                    ),
                    obj=Model,
                    id="models.W036",
                ),
            ]
        )
        self.assertEqual(errors, expected)

    def test_unique_constraint_with_condition_required_db_features(self):
        """
        Tests that a model with a unique constraint and a condition using required_db_features performs validation correctly.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_partial_indexes"}
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_gte_100",
                        condition=models.Q(age__gte=100),
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_unique_constraint_condition_pointing_to_missing_field(self):
        """
        Checks if a :class:`~django.db.models.UniqueConstraint` with a condition referencing a non-existent field generates the expected error message.
        """
        class Model(models.Model):
            age = models.SmallIntegerField()

            class Meta:
                required_db_features = {"supports_partial_indexes"}
                constraints = [
                    models.UniqueConstraint(
                        name="name",
                        fields=["age"],
                        condition=models.Q(missing_field=2),
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            (
                [
                    Error(
                        "'constraints' refers to the nonexistent field "
                        "'missing_field'.",
                        obj=Model,
                        id="models.E012",
                    ),
                ]
                if connection.features.supports_partial_indexes
                else []
            ),
        )

    def test_unique_constraint_condition_pointing_to_joined_fields(self):
        """
        Checks the UniqueConstraint condition pointing to joined fields on a model, verifying that it raises an error if the condition references a joined field.
        """
        class Model(models.Model):
            age = models.SmallIntegerField()
            parent = models.ForeignKey("self", models.CASCADE)

            class Meta:
                required_db_features = {"supports_partial_indexes"}
                constraints = [
                    models.UniqueConstraint(
                        name="name",
                        fields=["age"],
                        condition=models.Q(parent__age__lt=2),
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            (
                [
                    Error(
                        "'constraints' refers to the joined field 'parent__age__lt'.",
                        obj=Model,
                        id="models.E041",
                    )
                ]
                if connection.features.supports_partial_indexes
                else []
            ),
        )

    def test_unique_constraint_pointing_to_reverse_o2o(self):
        """

        Tests that Django correctly raises an error when a UniqueConstraint on a OneToOneField 
        in a model refers to a nonexistent field in the related object.

        """
        class Model(models.Model):
            parent = models.OneToOneField("self", models.CASCADE)

            class Meta:
                required_db_features = {"supports_partial_indexes"}
                constraints = [
                    models.UniqueConstraint(
                        fields=["parent"],
                        name="name",
                        condition=models.Q(model__isnull=True),
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            (
                [
                    Error(
                        "'constraints' refers to the nonexistent field 'model'.",
                        obj=Model,
                        id="models.E012",
                    ),
                ]
                if connection.features.supports_partial_indexes
                else []
            ),
        )

    def test_deferrable_unique_constraint(self):
        """
        Tests whether a database backend supports deferrable unique constraints, checking for warnings if the feature is not available.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_deferrable",
                        deferrable=models.Deferrable.DEFERRED,
                    ),
                ]

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_deferrable_unique_constraints
            else [
                Warning(
                    "%s does not support deferrable unique constraints."
                    % connection.display_name,
                    hint=(
                        "A constraint won't be created. Silence this warning if "
                        "you don't care about it."
                    ),
                    obj=Model,
                    id="models.W038",
                ),
            ]
        )
        self.assertEqual(errors, expected)

    def test_deferrable_unique_constraint_required_db_features(self):
        """
        Tests if a model with a deferrable unique constraint correctly specifies required database features for immediate deferral behavior.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_deferrable_unique_constraints"}
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_deferrable",
                        deferrable=models.Deferrable.IMMEDIATE,
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_unique_constraint_pointing_to_missing_field(self):
        """
        Checks that a model with a unique constraint referencing a missing field raises an error during model checking.
        """
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.UniqueConstraint(fields=["missing_field"], name="name")
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    def test_unique_constraint_pointing_to_m2m_field(self):
        """
        Tests that a UniqueConstraint cannot be applied to a ManyToManyField.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                constraints = [models.UniqueConstraint(fields=["m2m"], name="name")]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'constraints'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    def test_unique_constraint_pointing_to_non_local_field(self):
        """
        Tests that a UniqueConstraint in a child model referencing a field from a parent model using multi-table inheritance raises the appropriate error.
        """
        class Parent(models.Model):
            field1 = models.IntegerField()

        class Child(Parent):
            field2 = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(fields=["field2", "field1"], name="name"),
                ]

        self.assertEqual(
            Child.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to field 'field1' which is not local to "
                    "model 'Child'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Child,
                    id="models.E016",
                ),
            ],
        )

    def test_unique_constraint_pointing_to_fk(self):
        """
        Tests the enforcement of a unique constraint on a model where the constraint involves two foreign keys, verifying that the model's validation correctly identifies and reports any unsatisfied constraints.
        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            fk_1 = models.ForeignKey(Target, models.CASCADE, related_name="target_1")
            fk_2 = models.ForeignKey(Target, models.CASCADE, related_name="target_2")

            class Meta:
                constraints = [
                    models.UniqueConstraint(fields=["fk_1_id", "fk_2"], name="name"),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_unique_constraint_with_include(self):
        """
        Verifies that a model with a unique constraint including a non-key column behaves as expected, checking for support of covering indexes in the underlying database.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_include_id",
                        include=["id"],
                    ),
                ]

        errors = Model.check(databases=self.databases)
        expected = (
            []
            if connection.features.supports_covering_indexes
            else [
                Warning(
                    "%s does not support unique constraints with non-key columns."
                    % connection.display_name,
                    hint=(
                        "A constraint won't be created. Silence this warning if "
                        "you don't care about it."
                    ),
                    obj=Model,
                    id="models.W039",
                ),
            ]
        )
        self.assertEqual(errors, expected)

    def test_unique_constraint_with_include_required_db_features(self):
        """
        Tests the functionality of a unique constraint with the include parameter, ensuring it works with databases that support covering indexes.
        """
        class Model(models.Model):
            age = models.IntegerField()

            class Meta:
                required_db_features = {"supports_covering_indexes"}
                constraints = [
                    models.UniqueConstraint(
                        fields=["age"],
                        name="unique_age_include_id",
                        include=["id"],
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_unique_constraint_include_pointing_to_missing_field(self):
        """
        Tests that a UniqueConstraint with an include pointing to a missing field raises an error.
        """
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["id"],
                        include=["missing_field"],
                        name="name",
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_unique_constraint_include_pointing_to_m2m_field(self):
        """
        Tests that a UniqueConstraint cannot include a ManyToManyField, verifying that an error is raised when trying to create such a constraint.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["id"],
                        include=["m2m"],
                        name="name",
                    ),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'constraints'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_unique_constraint_include_pointing_to_non_local_field(self):
        """
        Tests the behavior of unique constraints with included fields when using multi-table inheritance.

        Verifies that an error is raised when a unique constraint's included field is not local to the model, but rather inherited from a parent model.
        """
        class Parent(models.Model):
            field1 = models.IntegerField()

        class Child(Parent):
            field2 = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["field2"],
                        include=["field1"],
                        name="name",
                    ),
                ]

        self.assertEqual(
            Child.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to field 'field1' which is not local to "
                    "model 'Child'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Child,
                    id="models.E016",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_covering_indexes")
    def test_unique_constraint_include_pointing_to_fk(self):
        """

        Tests that a unique constraint with an include clause pointing to a foreign key is correctly validated.

        The test case verifies that the check method does not report any errors for a model with a unique constraint
        defined on the primary key and including foreign key fields.

        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            fk_1 = models.ForeignKey(Target, models.CASCADE, related_name="target_1")
            fk_2 = models.ForeignKey(Target, models.CASCADE, related_name="target_2")

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["id"],
                        include=["fk_1_id", "fk_2"],
                        name="name",
                    ),
                ]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_func_unique_constraint(self):
        """
        Tests the model validation behavior when a unique constraint is defined on an expression field, verifying that a warning is raised if the database backend does not support expression indexes.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                constraints = [
                    models.UniqueConstraint(Lower("name"), name="lower_name_uq"),
                ]

        warn = Warning(
            "%s does not support unique constraints on expressions."
            % connection.display_name,
            hint=(
                "A constraint won't be created. Silence this warning if you "
                "don't care about it."
            ),
            obj=Model,
            id="models.W044",
        )
        expected = [] if connection.features.supports_expression_indexes else [warn]
        self.assertEqual(Model.check(databases=self.databases), expected)

    def test_func_unique_constraint_required_db_features(self):
        """
        Checks if a model with a unique constraint and required database features can be validated without errors.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                constraints = [
                    models.UniqueConstraint(Lower("name"), name="lower_name_unq"),
                ]
                required_db_features = {"supports_expression_indexes"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_unique_constraint_nulls_distinct(self):
        """
        Tests that UniqueConstraints with nulls_distinct flag function correctly, 
        including checking for database support and emitting warnings when necessary.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["name"],
                        name="name_uq_distinct_null",
                        nulls_distinct=True,
                    ),
                ]

        warn = Warning(
            f"{connection.display_name} does not support unique constraints with nulls "
            "distinct.",
            hint=(
                "A constraint won't be created. Silence this warning if you don't care "
                "about it."
            ),
            obj=Model,
            id="models.W047",
        )
        expected = (
            []
            if connection.features.supports_nulls_distinct_unique_constraints
            else [warn]
        )
        self.assertEqual(Model.check(databases=self.databases), expected)

    def test_unique_constraint_nulls_distinct_required_db_features(self):
        """
        Checks the creation of a unique constraint that treats NULL values as distinct, verifying that the corresponding database features are properly required.
        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["name"],
                        name="name_uq_distinct_null",
                        nulls_distinct=True,
                    ),
                ]
                required_db_features = {"supports_nulls_distinct_unique_constraints"}

        self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_expression_custom_lookup(self):
        """
        Tests the support for custom lookup types in unique constraints using expressions.
        """
        class Model(models.Model):
            height = models.IntegerField()
            weight = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        models.F("height")
                        / (models.F("weight__abs") + models.Value(5)),
                        name="name",
                    ),
                ]

        with register_lookup(models.IntegerField, Abs):
            self.assertEqual(Model.check(databases=self.databases), [])

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_pointing_to_missing_field(self):
        """
        Tests that a unique constraint raising an error when pointing to a missing field on a model.

        Checks that Django correctly identifies and reports the error when a unique constraint
        refers to a field that does not exist in the model, in a database that supports expression indexes.

        """
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.UniqueConstraint(Lower("missing_field").desc(), name="name"),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_pointing_to_missing_field_nested(self):
        """
        Tests that a unique constraint referencing a missing field within a nested database function raises the correct error when checking the model.
        """
        class Model(models.Model):
            class Meta:
                constraints = [
                    models.UniqueConstraint(Abs(Round("missing_field")), name="name"),
                ]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to the nonexistent field 'missing_field'.",
                    obj=Model,
                    id="models.E012",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_pointing_to_m2m_field(self):
        """
        Tests that a UniqueConstraint referencing a ManyToManyField raises a validation error, as such constraints are not supported.
        """
        class Model(models.Model):
            m2m = models.ManyToManyField("self")

            class Meta:
                constraints = [models.UniqueConstraint(Lower("m2m"), name="name")]

        self.assertEqual(
            Model.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to a ManyToManyField 'm2m', but "
                    "ManyToManyFields are not permitted in 'constraints'.",
                    obj=Model,
                    id="models.E013",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_pointing_to_non_local_field(self):
        """
        Tests the validation of a UniqueConstraint referencing a non-local field in a model with multi-table inheritance.
        """
        class Foo(models.Model):
            field1 = models.CharField(max_length=15)

        class Bar(Foo):
            class Meta:
                constraints = [models.UniqueConstraint(Lower("field1"), name="name")]

        self.assertEqual(
            Bar.check(databases=self.databases),
            [
                Error(
                    "'constraints' refers to field 'field1' which is not local to "
                    "model 'Bar'.",
                    hint="This issue may be caused by multi-table inheritance.",
                    obj=Bar,
                    id="models.E016",
                ),
            ],
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_pointing_to_fk(self):
        """

        Tests the creation of a unique constraint on a model field pointing to a foreign key,
        ensuring that the constraint is correctly applied when using a database expression.

        """
        class Foo(models.Model):
            id = models.CharField(primary_key=True, max_length=255)

        class Bar(models.Model):
            foo_1 = models.ForeignKey(Foo, models.CASCADE, related_name="bar_1")
            foo_2 = models.ForeignKey(Foo, models.CASCADE, related_name="bar_2")

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        Lower("foo_1_id"),
                        Lower("foo_2"),
                        name="name",
                    ),
                ]

        self.assertEqual(Bar.check(databases=self.databases), [])
