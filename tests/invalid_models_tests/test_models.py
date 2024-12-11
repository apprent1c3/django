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

    Returns the maximum allowed length for a column name and the database alias where this limit applies.

    This function iterates over available database connections, retrieves the maximum allowed name length for each,
    and returns the shortest length that is not subject to truncation, along with the corresponding database alias.

    The returned values can be used to ensure that column names are compatible with the most restrictive database connection.

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
        Tests that the unique_together Meta attribute in a model must be a list or tuple.

        Verifies that a ValueError is raised when the unique_together attribute is not a list or tuple, ensuring data integrity by enforcing proper configuration of the model's metadata.

        :raises: AssertionError if the check does not raise the expected Error.
        :raises: Error if the 'unique_together' attribute is not a valid list or tuple.

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
        Tests that a model with a unique_together constraint is considered valid if no duplicate combinations exist.

            This test ensures that the model validation checks correctly identify the absence of duplicate combinations of fields
            specified in the unique_together meta option, and returns an empty list in such cases.

            :return: None

        """
        class Model(models.Model):
            one = models.IntegerField()
            two = models.IntegerField()

            class Meta:
                # unique_together can be a simple tuple
                unique_together = ("one", "two")

        self.assertEqual(Model.check(), [])

    def test_pointing_to_missing_field(self):
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

        Tests that a ManyToManyField cannot be used in the unique_together model Meta option.

        This check ensures that the model's unique_together constraint does not reference a ManyToManyField, 
        as this is not a valid configuration according to Django's model validation rules. 
        A ManyToManyField is not allowed in unique_together because it does not represent a field on the model itself, 
        but rather a relationship between models.

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
        Tests that the model validation correctly identifies an index referencing a non-existent field in the model. 

        This test case covers the scenario where a model's Meta class defines an index on a field that does not exist in the model. The expected outcome is a validation error indicating that the 'indexes' attribute refers to a non-existent field.
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

        Tests that a model with a ManyToManyField cannot be indexed.

        Checks that attempting to create an index on a ManyToManyField results in an error.
        Verifies that the error is correctly reported and references the problematic field and model.

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

        Checks that a model does not reference non-local fields in its index definitions.

        This test case verifies that an error is raised when a model attempts to create an index
        that includes a field inherited from a parent model. The test ensures that the error
        message provides a clear indication of the issue and suggests possible causes, such as
        multi-table inheritance.

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
        Checks the validity of index names defined on a model, ensuring that they do not start with an underscore or a number, in accordance with database naming conventions. The function verifies that the model's indexing is correctly configured and returns an error if any index name is invalid.
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
        Checks if a model with a conditional index can be validated, ensuring that the database backend supports partial indexes.

        The function tests that the model's `check` method does not return any errors when the model has a conditional index and the `required_db_features` Meta option is set to `{'supports_partial_indexes'}`. This allows the model to specify that a partial index should only be created if the database supports this feature.
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

        Checks that an IndexError is raised when creating an index that includes a ManyToManyField.

        This test verifies that Django's model index validation correctly identifies
        and prevents the creation of indexes that include ManyToManyFields. The test
        case ensures that the check raises the expected error when an index includes
        a ManyToManyField, providing a specific error message and object reference.

        The validation process is performed on a model containing a ManyToManyField
        and an index that attempts to include this field, demonstrating the expected
        behavior and error handling for such a scenario.

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
        Tests that the check function correctly handles indexes with included columns 
        that point to foreign keys, ensuring that the system does not raise any errors.

        The test case verifies the index validation logic for the given model structure,
        where the index includes foreign key references, helping to maintain data integrity.

        The test skips if the database does not support covering indexes, as this feature 
        is required for the test scenario to be applicable. 

        :raises AssertionError: If the check function returns any errors for the test model.

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

        Tests the indexing functionality of a database model.

        This test case creates a model with a custom index defined on an expression (in this case, the lowercase version of a field).
        It then checks if the database backend supports indexing on expressions and verifies that the model validation
        behaves as expected, either creating the index or raising a warning if the database does not support it.

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

        Checks if the required database features are correctly specified for a model with an index.

        This test case verifies that when a model defines an index that relies on a specific database feature,
        such as expression indexes, the model's required database features are properly identified and reported.

        The test asserts that the model's check method returns an empty list, indicating no issues,
        when the required database features are correctly specified.

        """
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                indexes = [models.Index(Lower("name"), name="index_lower_name")]
                required_db_features = {"supports_expression_indexes"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_func_index_complex_expression_custom_lookup(self):
        """
        Tests the support for complex expressions in index definitions, including the ability to use a custom lookup for absolute value calculations, and verifies that the model's index is correctly validated.
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
        Tests that a model validation error is raised when an index points to a field that does not exist on the model. The validation error checks if all fields referenced in an index are present in the model, ensuring data integrity and preventing potential database errors.
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

        Tests that an index on a model cannot point to a ManyToManyField.

        Verifies that attempting to create an index on a ManyToManyField raises an error.
        This check ensures that models are correctly configured and indexes are properly defined.

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
        Test that index pointing to a foreign key is correctly created.

        This test case verifies that an index created on a foreign key field and 
        another field in the same model is properly validated. The index includes 
        the 'id' field of the related model, and the test checks that no errors 
        are raised during the validation process.

        The test involves two models, Foo and Bar, with Bar having foreign key 
        relationships to Foo. An index is defined on Bar with the 'id' field of 
        the Foo foreign key and another field in Bar. The test checks that the 
        index creation does not result in any errors. 

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the index creation results in any errors.
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
        #13711 -- Model check for long M2M column names when database has
        column name length limits.
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
        #13711 -- Model check for long column names
        when database does not support long names.
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
        """
        Checks for column name clashes in a Django model's database fields.

        This test case verifies that when two fields in a model are assigned the same column name in the database, a suitable error is raised to prevent potential data inconsistencies.

        The function specifically tests whether the ORM can correctly identify and report field column name clashes, ensuring that each field is uniquely mapped to a database column.

        Returns an error when a column name is reused across multiple fields in the model, providing a hint to specify a unique 'db_column' for the offending field.
        """
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

        Tests that a field name clash is detected when a field in a child model 
        has the same name as a field in its parent model, but through a many-to-many 
        relationship. This ensures that the model validation correctly identifies 
        potential naming conflicts.

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
        Tests that Django model inheritance correctly detects field name clashes between parent and child models.

        This test case checks for a specific error (models.E006) that occurs when a field in a child model has the same name as a field in its parent model. The test verifies that the error is correctly raised when a ForeignKey field in the child model clashes with a field in the parent model.

        The test involves creating a parent model and a child model that inherits from it, and then checking the error messages generated by the child model's validation.

        The expected output is an error message indicating that the field 'f' in the child model clashes with the field 'f_id' from the parent model, with the error ID 'models.E006'.
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

        Tests model field clash detection in a multigeneration inheritance scenario.

        Verifies that when a model field name clashes with a field from a grandparent model,
        the check function correctly identifies and reports the error.

        In this test case, the field 'clash' is defined in both the GrandParent and GrandChild models,
        which should trigger an error due to the inheritance relationship between them.

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

        Tests that a Multi-Table Inheritance (MTI) model with a common parent class raises an error when checking for validity.

        The test creates a hierarchy of models with a grandparent, parent, and child, and then defines a new model that inherits from both the child and the grandparent. It then checks that the expected error is raised, indicating that the field 'grandparent_ptr' clashes with the field 'grandparent_ptr' from the parent model.

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

        Checks that the 'ordering' Meta option in a model is correctly set to a tuple or list.

        This test ensures that the 'ordering' attribute, which specifies the default ordering of query results, 
        is properly defined as a collection (even if ordering by a single field) to prevent potential errors.

        The test verifies that an Error is raised when 'ordering' is not a tuple or list, providing a clear error message.

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
        Tests that a model with a single PositiveIntegerField and ordering by that field has no errors when checked.

        This test case verifies that the model's `Meta.ordering` attribute is correctly set to order instances by the 'order' field, 
        and that this ordering does not introduce any errors. The test confirms that the model is valid and can be used as expected.
        """
        class Model(models.Model):
            order = models.PositiveIntegerField()

            class Meta:
                ordering = ["order"]

        self.assertEqual(Model.check(), [])

    def test_just_order_with_respect_to_no_errors(self):
        """
        Tests that a model with a foreign key and order_with_respect_to meta option does not produce any errors when checked.

        This test case verifies that the model Answer, which has a foreign key to the Question model and is ordered with respect to the Question model, passes the model check without raising any errors.

        The test is successful when the check method of the Answer model returns an empty list, indicating that no errors were found in the model's definitions.
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
        Tests that using both 'ordering' and 'order_with_respect_to' in a model's Meta options raises an error.

        This test case checks the validation of model options to ensure they are correctly configured. 
        It verifies that when 'ordering' is specified, using 'order_with_respect_to' is not allowed, as these two options are mutually exclusive.

        The test creates two models, Question and Answer, where Answer has a foreign key to Question and an 'order' field. 
        The Answer model's Meta options are then set to use both 'order_with_respect_to' and 'ordering', which should trigger an error.

        The expected error, 'models.E021', is asserted to be raised, indicating that the validation correctly identifies the incompatible model options.
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

        Tests that a model with a ManyToManyField specified in the 'ordering' Meta option
        raises the correct error when the field is not a valid choice for ordering.

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
        Tests whether the model validation correctly identifies and raises an error when the model's Meta class specifies an ordering that references a field that does not exist in the model. This ensures that the validation process catches and reports invalid ordering configurations, helping to prevent potential runtime errors.
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
        Checks if the ordering meta option references a field that does not exist on the model, specifically a foreign key field that is being referenced with the incorrect suffix '_id'. 

        This test case verifies that an error is raised when the model's 'ordering' Meta option is set to a field name that does not exist on the model, in this case 'missing_fk_field_id'. The expected error is a models.E015 error, indicating that the 'ordering' option references a nonexistent field, related field, or lookup.
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
        Tests that Django model validation correctly identifies and reports an error when the model's 'ordering' Meta attribute references a related field that does not exist on the model.
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

        Tests that a ValidationError is raised when the 'ordering' Meta option references 
        a related field that does not exist.

        The test case involves three models: Parent2, Parent1, and Child. The Child model 
        has a foreign key to Parent1, which in turn has a foreign key to Parent2. The 
        'ordering' option in the Child model's Meta class references a non-existent field 
        ('missing_field') on the related Parent2 model. The test verifies that the 
        expected error is raised when checking the model.

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
        Tests the behavior of the ordering meta attribute when referencing multiple related fields.

        This test case checks if the ORM correctly raises an error when an ordering is defined 
        on a field that points to a related field which does not exist or is not a valid lookup. 
        In this specific case, it attempts to order by 'parent__field1__field2', 
        which refers to a nonexistent or invalid related field 'field2' in 'field1'. 

        The expected outcome is that the check method should return a list containing a single Error object, 
        indicating that the 'ordering' refers to a nonexistent field, related field, or lookup. 

        The purpose of this test is to ensure the model validation is correctly enforced 
        when using related fields in the ordering attribute of the Meta class.
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
        Tests that model ordering allows registered lookups on CharField.

        This test case checks if a model that uses a custom lookup in its ordering
        can be successfully validated. The custom lookup is registered for
        CharField, making it available for use in model meta options, such as
        ordering. The test passes if no errors are raised during validation.

        :raises AssertionError: If the model validation fails.

        """
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__lower",)

        with register_lookup(models.CharField, Lower):
            self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_lookup_not_transform(self):
        """

        Tests that model validation does not fail when an ordering is set on a field
        that points to a lookup type 'isnull', ensuring that the model's Meta class
        can correctly handle this type of ordering without raising any errors.

        """
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__isnull",)

        self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_related_model_pk(self):
        """
        Test that the ordering specification points to the primary key of a related model.

        This test case verifies that the ordering attribute in the Child model's Meta class
        correctly references the primary key of the Parent model, ensuring that the Child
        instances are ordered as expected.

        The test checks the ordering specification without any errors or warnings, 
        indicating that the relationship between the Child and Parent models is correctly 
        configured for ordering purposes.

        Returns:
            An empty list if the ordering is correctly specified, indicating no errors.

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
        Tests that a model's Meta ordering attribute cannot point to a ForeignKey field.

        Checks that an InvalidOrderingError is raised when the ordering attribute
        is set to a field that is a ForeignKey, as this can lead to ambiguous and
        potentially incorrect query results. Verifies that the check method returns
        False when this invalid condition is detected, ensuring data consistency and
        preventing potential database errors.
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
        class Cheese:
            @property
            def filling_id(self):
                pass

        class Sandwich(Cheese, models.Model):
            filling = models.ForeignKey("self", models.CASCADE)

        self.assertEqual(Sandwich.check(), [])

    def test_single_primary_key(self):
        """
        Tests that a model definition with multiple fields marked as primary keys raises the correct error. 

        The test verifies that the model validation correctly identifies and reports the error when more than one field is defined with 'primary_key=True'.
        """
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
        .Tests an error checking method to ensure that a model does not define two many-to-many relationships 
        through the same intermediate model, which is an unsupported database configuration.

        The test creates a model structure where a Group model has two many-to-many relationships with a Person 
        model through the same Membership intermediate model, triggering the expected error. 

        This test case verifies that the model validation correctly identifies and reports this kind of 
        modeling error, providing an informative error message with the model object and error identifier.
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

        Tests that Many-To-Many fields with the same intermediate model but different through fields are correctly validated.

        This test case ensures that Django's model validation correctly handles cases where two Many-To-Many fields in a model use the same intermediate model (`ShippingMethodPrice`) but specify different through fields (`to_countries` and `from_countries`).

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
        Tests the functionality of a one-to-one relationship between two models, specifically when one model is a parent of the other, to ensure there are no errors or issues. The test creates a parent model \"Place\" and a child model \"ParkingLot\" that inherits from \"Place\", with a one-to-one relationship to another \"Place\" instance. The test checks that the validation of this relationship does not return any errors.
        """
        class Place(models.Model):
            pass

        class ParkingLot(Place):
            other_place = models.OneToOneField(
                Place, models.CASCADE, related_name="other_parking"
            )

        self.assertEqual(ParkingLot.check(), [])

    def test_onetoone_with_explicit_parent_link_parent_model(self):
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
        Tester for Many-To-Many field table name clash.

        This test checks if a Many-To-Many field's intermediary table name conflicts with an existing model's table name. The test verifies that an error is raised when a model's Many-To-Many field uses the same database table name as another model, which could lead to data corruption or incorrect query results. The test uses a mock model setup to simulate this scenario and asserts that the expected error is reported by the model's validation mechanism.
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
        Tests that ManyToManyField table name clashes are correctly identified and reported.

        In this test case, two ManyToManyFields from different models reference the same intermediary table name, which should raise an error.

        The test ensures that the validation checks correctly detect the table name clash and return the expected error messages, specifying the conflicting fields and their models.

        This test helps to ensure that the database table names generated for ManyToManyFields do not conflict with other model's table names, preventing potential database errors and inconsistencies.
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

        Test that ManyToManyField table name clashes are detected when using database routers.

        This test checks for instances where two ManyToManyFields define the same intermediary table name,
        and that the expected warnings are raised when these tables are defined with database routers installed.

        It verifies that the warnings provide accurate information about the clashing models and suggest a potential solution.

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

        Tests that a Many-To-Many relationship's automatically generated table name does not clash with an existing table name.

        Verifies that the check method of the model raises an error when the intermediary table name
        generated for a Many-To-Many field matches the table name of another model in the database.

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
        Tests that a Many-To-Many field with an autogenerated intermediary table correctly raises a warning when its table name clashes with an existing model's table name, considering the presence of database routers.

        This test case verifies that the check method on the model detects the naming conflict and returns the appropriate warning, suggesting that the table of the conflicting model should be routed to a separate database to avoid the clash.

        Specifically, it checks for the issuance of a W344 warning, indicating a field's intermediary table name conflict, when database routers are installed and configured in the settings.

        The test expects the warning to contain information about the clashing table name and a hint to verify the correct routing of the conflicting model's table to a separate database.
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

        Tests that many-to-many fields can use both concrete and proxy through models.

        This test case verifies that Django's model validation allows many-to-many fields 
        to be defined with both a concrete through model and a proxy through model.
        The test models define a simple many-to-many relationship between models A and C, 
        with both a concrete Through model and a proxy ThroughProxy model.
        The test checks that the model validation does not raise any errors when using 
        both the concrete and proxy through models in many-to-many fields.

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

        Tests the functionality of setting comments on database tables for models.

        This test verifies that when a model has a db_table_comment set, the expected warnings or lack thereof are generated.
        It checks for the presence of a specific warning when the database backend does not support table comments.
        The test ensures compatibility and adherence to expected behavior across different database systems.

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
        Tests the :func:`check` method for a model that has a database table comment and requires the database to support comments.

        This test ensures that the model validation succeeds when the required database feature 'supports_comments' is available.

        :raises AssertionError: If the model validation fails or reports any errors.
        """
        class Model(models.Model):
            class Meta:
                db_table_comment = "Table comment"
                required_db_features = {"supports_comments"}

        self.assertEqual(Model.check(databases=self.databases), [])


class MultipleAutoFieldsTests(TestCase):
    def test_multiple_autofields(self):
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
        class Model(models.Model):
            field = models.JSONField()

            class Meta:
                ordering = ["field__value"]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_check_jsonfield(self):
        """
        Tests the model validation for a model containing a JSONField, verifying that the check method returns the expected errors based on the database backend's support for JSON fields. If the database supports JSON fields, the check method should return an empty list, otherwise it should return an error indicating that the field is not supported.
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

        Checks that the JSONField in a model is correctly validated against the required database features.

        The function tests that a model with a JSONField and a Meta option specifying 'supports_json_field' as a required database feature
        correctly passes the database feature checks when run against the configured databases.

        Returns:
            None

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
        Tests whether the :class:`~models.Model` class correctly checks for constraints 
        on supported databases. Specifically, it checks the behavior for a CheckConstraint 
        that verifies whether an integer field 'age' is greater than or equal to 18. 

        The test covers the case when the database supports table check constraints and 
        when it does not, ensuring the expected warnings are raised. 

        The outcome of the test is a list of errors or warnings that should match the 
        expected output, depending on the database's capabilities. 

        Note: 
            This test does not directly create the model or apply the constraints to the 
            database, but rather checks the model's internal consistency and 
            compatibility with different database backends. 

        Returns:
            None
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
        Tests the behavior of check constraints in models when referencing a reverse foreign key.

        Checks that the ORM correctly identifies and raises an error when a check constraint
        is defined with a condition that references a nonexistent field, in this case, a reverse
        foreign key that doesn't exist due to the nature of the model's relationships.

        Verifies the error is correctly reported and includes the expected error message,
        indicating the specific problem and the model and field involved in the error.

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

        Checks the functionality of a check constraint referencing the reverse One-To-One field in a model.

        This test validates that Django's ORM correctly raises an error when a model's check constraint references a field that does not exist in the model.

        The expected behavior is that the validation of the model's check constraints returns an error indicating that the referenced field does not exist.

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

        Tests that a CheckConstraint on a model cannot refer to a ManyToManyField.

        This test case verifies that Django correctly prevents the creation of check constraints
        that reference ManyToManyFields, as these are not supported.

        The test attempts to define a model with a check constraint on a ManyToManyField and
        then checks that the expected error is raised when validating the model.

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

        Tests that a CheckConstraint cannot reference joined fields.

        This test case covers various scenarios where CheckConstraints are defined with
        conditions that involve joined fields. It verifies that the model validation
        correctly raises an error when a CheckConstraint points to a joined field,
        either through a ForeignKey, OneToOneField, or nested joined fields.

        The test creates a model with multiple CheckConstraints that reference joined
        fields and then checks that the expected validation errors are raised.

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
        Tests that a CheckConstraint on a model cannot reference joined fields.

        This test case creates a model with a self-referential foreign key and a complex
        CheckConstraint that references the joined fields of the parent instance.
        It then verifies that the expected errors are raised when checking the model's constraints.

        The test covers a scenario where the CheckConstraint condition involves a mix of
        logical operators and comparisons between fields, including joined fields.
        The expected outcome is that an error is raised for each joined field referenced
        in the CheckConstraint, as this is not supported by the database backend.

        The test ensures that the model validation correctly identifies and reports the
        invalid constraint, providing informative error messages that specify the
        problematic joined fields.
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
        Tests the creation of a unique constraint with a condition in a model to ensure it behaves as expected across different databases.

        The test checks if a model with a unique constraint on the 'age' field, conditioned on 'age' being greater than or equal to 100, can be created without raising any errors.
        It verifies that the correct warnings are raised if the database does not support unique constraints with conditions.
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

        Tests the behavior of a model's unique constraint with a condition when the database feature 'supports_partial_indexes' is required.

        Verifies that the model validation returns no errors when using a unique constraint with a condition that requires partial index support.

        The test checks if the model's constraints are correctly validated against the specified database features.

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
        Tests that a UniqueConstraint with a condition referencing a missing field in the model raises a validation error if the database supports partial indexes, and no error otherwise.
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

        Tests that UniqueConstraint with a condition referencing a joined field raises an error.

        This checks if the model validation correctly identifies the joined field reference
        in the UniqueConstraint condition and reports it as an error. The test covers
        both cases where the database supports partial indexes and where it does not.

        The UniqueConstraint in question refers to a joined field ('parent__age__lt') in its
        condition, which is not allowed. The expected error is raised when the model is
        validated, provided the database supports the required features.

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

        Tests if a model with a deferrable unique constraint is successfully checked when the database features required for deferrable unique constraints are specified.

        This test case ensures that the model validation passes when the database supports deferrable unique constraints and the corresponding required database feature is defined in the model's Meta options.

        The test verifies that no errors are raised during model checking, indicating that the model's unique constraint is properly validated against the database's capabilities.

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
        Tests the behavior of Django's model validation when a unique constraint is defined on a field that does not exist in the model.

        The function checks that the correct error is raised when the model's constraints are validated against a set of databases. Specifically, it verifies that an error is reported when a unique constraint points to a missing field in the model.

         Args:
            self: The test case instance.

         Returns:
            None: The test does not return a value, but instead asserts that the model validation returns the expected error. 

         Raises:
            AssertionError: If the model validation does not return the expected error. 

         Note:
            This test case is used to ensure that Django's model validation correctly handles unique constraints that reference non-existent fields.
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

        Tests that a unique constraint cannot include a ManyToManyField.

        Verifies that attempting to create a unique constraint that includes a ManyToManyField
        results in an error, as ManyToManyFields are not permitted in constraints.

        The test covers the case where a model defines a unique constraint with the 'include'
        parameter referencing a ManyToManyField, and checks that the expected error is raised.

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
        Tests that a unique constraint with an included field referencing a non-local field raises an error.

        This test case covers the scenario where a model with multi-table inheritance attempts to define a unique constraint
        that includes a field from a parent model. The expected outcome is an error indicating that the included field is not
        local to the model, providing a hint about the potential cause being related to multi-table inheritance.

        Verifies that the model checking mechanism correctly identifies and reports this specific issue, ensuring data integrity
        and consistency in the database schema.
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

        Tests the functionality of a unique constraint that includes fields pointing to foreign keys.

        This test case verifies that a unique constraint can be successfully defined on a model,
        including fields that reference foreign keys. The test model has two foreign key fields
        and a unique constraint that includes both of these fields, in addition to the model's primary key.
        The test checks that the model's validation does not raise any errors when the constraint is applied.

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

        Tests the unique constraint on a model field with database expression.

        This test case checks that a model with a unique constraint defined on a database
        expression (in this case, the lowercase of a character field) is validated
        correctly. The test verifies that the model validation returns the expected
        warnings or errors based on the capabilities of the underlying database.

        If the database supports expression indexes, no warnings are expected. However,
        if the database does not support expression indexes, a warning is expected to be
        raised, indicating that the unique constraint on the expression will not be
        created.

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
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                constraints = [
                    models.UniqueConstraint(Lower("name"), name="lower_name_unq"),
                ]
                required_db_features = {"supports_expression_indexes"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_unique_constraint_nulls_distinct(self):
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

        Tests the functionality of a unique constraint with a custom lookup expression.

        The test case covers a scenario where a model has a unique constraint defined 
        on an expression involving an absolute value custom lookup. The constraint is 
        verified to work correctly by checking if the model's checks pass without any 
        errors.

        This test is only executed if the database being used supports expression indexes.

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
        Tests that a unique constraint pointing to a missing field raises an error.

        This test case checks the validation of a model's unique constraints when
        one of the fields referenced in the constraint does not exist in the model.
        It verifies that the expected error is raised, indicating that the constraint
        refers to a nonexistent field.

        The test covers the scenario where the constraint uses a database function
        (Lower) and is ordered in descending order, adding a layer of complexity to
        the validation process. The expected error message includes the name of the
        model, the id of the error, and a descriptive message indicating the issue.

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
        Tests the handling of unique constraints in models that reference missing fields, specifically when the constraint expression is nested and involves an absolute value function. 
        The test verifies that the model validation correctly identifies and reports an error when the referenced field does not exist in the model.
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

        Tests that a unique constraint cannot be applied to a Many-To-Many field.

        This test checks that attempting to create a model with a unique constraint 
        on a Many-To-Many field raises a check error. The constraint is defined 
        using the model's Meta.constraints attribute, which is not permitted to 
        reference Many-To-Many fields. The test verifies that the correct error 
        message is returned when the model is checked.

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

        Tests if a UniqueConstraint on a model can reference a field from a parent model.

        This test case verifies the behavior of the `UniqueConstraint` when used with 
        model inheritance, specifically when the constraint points to a field that is 
        defined on a parent model, rather than a field local to the current model. 

        It checks if the model validation correctly identifies and reports an error 
        when a non-local field is referenced in a UniqueConstraint, providing an 
        informative error message and hint about the potential cause of the issue, 
        such as multi-table inheritance. 

        The test ultimately checks that the model check returns the expected error 
        regarding the non-local field reference in the UniqueConstraint.

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

        Tests the creation of a unique constraint that references a foreign key field.

        This test case verifies that a model can define a unique constraint that points to
        a foreign key field, ensuring data integrity by preventing duplicate combinations
        of values. The constraint is case-insensitive, as it uses the Lower function to
        normalize the values. The test checks that the model's check method returns no
        errors when the constraint is properly defined.

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
