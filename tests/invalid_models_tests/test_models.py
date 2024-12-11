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
        """

        Checks if all elements in the 'unique_together' Meta option of a model are lists or tuples.

        This test ensures that the 'unique_together' option in a model's Meta class is correctly formatted, 
        containing only lists or tuples. If any element is a non-iterable (in this case, an integer), 
        it raises an error with a specific message and identifier.

        The test verifies that the model validation correctly identifies and reports this formatting issue, 
        returning a list of errors with the appropriate error message and object reference.

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
        Test that a model with multiple foreign keys to the same model defines correct related object names.

        This test ensures that the model's related object names are properly set when there are multiple foreign keys to the same model. 
        It verifies that the model validation does not raise any errors when the related names are correctly defined.
        The test specifically checks for a model with two foreign keys to another model, where both foreign keys have distinct related names and one of them is used in a model index.

        The test passes if no errors are raised during model validation, indicating that the related object names are correctly defined and the model is properly configured.
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

        Tests that an error is raised when a model uses a covering index that includes a field 
        from a parent model, which is not local to the model. This checks for correct handling 
        of multi-table inheritance in model indexes.

        The test verifies that the model validation correctly identifies and reports the error 
        when the 'include' parameter of an index references a field from a parent model, 
        which is not accessible as a local field of the child model.

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
        class Model(models.Model):
            name = models.CharField(max_length=10)

            class Meta:
                indexes = [models.Index(Lower("name"), name="index_lower_name")]
                required_db_features = {"supports_expression_indexes"}

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_func_index_complex_expression_custom_lookup(self):
        """

        Tests the functionality of creating a complex database index on a model field
        using a custom lookup expression.

        The test verifies that a model with a custom index defined using a complex
        expression involving absolute value and arithmetic operations can be
        successfully created without raising any errors.

        The index is defined on the 'height' field of the model, using the absolute
        value of the 'weight' field and an additional constant value. The test case
        ensures that this custom index is valid and can be used without issues.

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

        Checks if an index in a subclass model points to a field that is not local to the model.

        This test case verifies that when using multi-table inheritance in Django models,
        the model validation correctly identifies and reports an error if an index defined
        in a subclass model references a field that is not defined within that model itself,
        but rather in one of its parent models.

        The model validation process raises an error with a specific error message and hint,
        indicating the potential cause of the issue and providing guidance on how to resolve it.

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
        """

        Tests that model field names do not end with an underscore, as this is not allowed in Django.

        This test checks that the `check` method of the model correctly identifies and reports field names that end with an underscore, and that it raises the corresponding error messages for both regular fields and many-to-many fields.

        The expected output includes error messages with id 'fields.E001' for each field that ends with an underscore.

        """
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
        Checks if a field in a child model has the same name as an accessor method generated for a field in its parent model, which would cause a naming conflict.
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
        Tests that a field name clash is detected between a model field and a field inherited from a parent model through a many-to-many relationship.

        The function checks for a specific error (E006) that occurs when a model field has the same name as a field from a related model, which can cause ambiguity and conflicts in the database schema.

        It verifies that the `check` method of the model correctly identifies and reports this field name clash, ensuring that the model's fields can be properly validated and used without errors. 
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
        Tests that a child model correctly identifies field clashes when inheriting from multiple parent models.

        This test case validates the error handling for multi-inheritance conflicts.
        It covers scenarios where fields with the same name are defined in multiple parent models,
        including automatically generated fields like the primary key 'id' and user-defined fields like 'clash'.
        The expected output is a list of Errors, each detailing a specific field clash and its origin in the model inheritance hierarchy.
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
        class Model(models.Model):
            order = models.PositiveIntegerField()

            class Meta:
                ordering = ["order"]

        self.assertEqual(Model.check(), [])

    def test_just_order_with_respect_to_no_errors(self):
        class Question(models.Model):
            pass

        class Answer(models.Model):
            question = models.ForeignKey(Question, models.CASCADE)

            class Meta:
                order_with_respect_to = "question"

        self.assertEqual(Answer.check(), [])

    def test_ordering_with_order_with_respect_to(self):
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
        Tests that a model with a ManyToManyField in its ordering Meta option 
        raises an error if the field is not valid for ordering.

        The test checks that the model's check method returns an error when 
        the ManyToManyField 'relation' is used in the 'ordering' option, 
        as it is not a valid field for ordering due to its nature of 
        representing a relationship rather than a direct field value.
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
        Tests that the model's Meta.ordering attribute raises an error when referencing a field on a related model that does not exist, specifically when traversing multiple relationships. Verifies that the check for valid ordering fields correctly identifies and reports the error in this scenario.
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
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__lower",)

        with register_lookup(models.CharField, Lower):
            self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_lookup_not_transform(self):
        """
        Tests that a model with an ordering pointing to a lookup, specifically 'isnull', does not result in any transformation issues when checked. This ensures that models can be correctly ordered based on null values without encountering any errors.
        """
        class Model(models.Model):
            test = models.CharField(max_length=100)

            class Meta:
                ordering = ("test__isnull",)

        self.assertEqual(Model.check(), [])

    def test_ordering_pointing_to_related_model_pk(self):
        class Parent(models.Model):
            pass

        class Child(models.Model):
            parent = models.ForeignKey(Parent, models.CASCADE)

            class Meta:
                ordering = ("parent__pk",)

        self.assertEqual(Child.check(), [])

    def test_ordering_pointing_to_foreignkey_field(self):
        """

        Tests that a model does not allow ordering on a field that points to a foreign key.

        This case checks for a specific model configuration where a foreign key is used
        in the model's Meta ordering. The test verifies that the check method correctly
        identifies and prevents this configuration, ensuring that the model does not
        attempt to order instances based on the foreign key.

        The scenario involves a parent-child relationship where the child model has a
        foreign key referencing the parent model, and the child model's Meta class
        specifies an ordering based on the foreign key field.

        The expected outcome is that the check method returns False, indicating that the
        model's configuration is invalid due to the ordering on the foreign key field.

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
        """
        Tests that a model name containing double underscores raises a validation error.

        The function checks that the model validation correctly identifies and reports model names
        that contain double underscores, which conflict with the query lookup syntax, ensuring that
        the validation returns the expected error message and object reference.

        The error is classified as 'models.E024' and includes a descriptive message and the offending
        model object, providing clear information for diagnosis and correction. 
        """
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
        Tests the one-to-one relationship between two models, where one model is a subclass of the other.

        This test case verifies that a one-to-one field in a subclassed model does not introduce any errors or inconsistencies.
        It checks the relationship between a parent model and its subclass, ensuring that the one-to-one field is correctly established.

        The test specifically looks for any issues that may arise from the relationship between the parent and child models, and asserts that no errors are encountered.

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

        Tests the handling of Many-To-Many field table name clashes when database routers are installed.

        Verifies that the check for intermediate table name clashes raises the correct warnings
        when multiple models attempt to use the same database table for their Many-To-Many relationships.

        This test case covers the scenario where multiple models have a Many-To-Many field with the same
        database table name, and the project has database routers configured.
        The expected output is a list of warnings indicating the table name clashes and suggesting verification
        of the database routing configuration.

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
        Tests that a Many-To-Many relationship does not clash with an existing table name.

        This test case verifies that Django raises an error when the automatically generated
        table name for a Many-To-Many relationship conflicts with the name of an existing table.
        The test checks that the `check` method on the model returns the expected error message
        when the table name clash occurs, ensuring that the model's validity can be properly verified.

        The test scenario involves two models, `Foo` and `Bar`, where `Bar` has a Many-To-Many
        relationship with `Foo`. The table name for `Foo` is explicitly set to 'bar_foos', which
        conflicts with the automatically generated table name for the Many-To-Many relationship.
        The test asserts that the `check` method correctly identifies and reports this clash as an error.

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
        Test that a ManyToManyField's auto-generated intermediary table does not clash with an existing table name when DATABASE_ROUTERS are installed.

        This test case checks for potential naming conflicts between the auto-generated table name for a ManyToManyField and an existing model's table name when database routers are being used. It verifies that a warning is raised when the intermediary table name matches an existing model's table name, and provides a hint to check the database routing configuration to ensure the models are correctly routed to separate databases.

        The warning is raised to prevent potential data corruption or inconsistencies that could arise from the naming conflict, and the test ensures that the warning is correctly generated and reported.

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
        Tests that unmanaged shadow models in many-to-many relationships are not checked for consistency.

        This test ensures that when using intermediate models in many-to-many relationships
        between managed and unmanaged models, the validation check does not fail even if the 
        intermediate table's name is the same as the automatic many-to-many table name that 
        Django would generate.

        It verifies that no errors are raised when checking the consistency of both managed and 
        unmanaged models, even when the unmanaged model uses a shadow relationship with the 
        same table name as an existing managed model's many-to-many relationship.

        The test cases cover scenarios with both managed and unmanaged models, ensuring that the 
        validation check handles these cases correctly without reporting any errors.
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

        Checks that Django's lazy model references are correctly validated.

        Performs a series of operations that trigger lazy model references, including:
        - Creating a model with a foreign key to a non-existent model
        - Defining a function and connecting it to a signal with a non-existent sender
        - Creating an instance of a class and connecting it to a signal with a non-existent sender
        - Connecting a bound method to a signal with a non-existent sender
        - Using lazy model operations with non-existent apps and models

        Verifies that the expected errors are raised for each operation, including:
        - Errors for non-existent models and apps
        - Errors for signals with non-existent senders
        - Errors for foreign keys to non-existent models

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
        class Model(models.Model):
            class Meta:
                db_table_comment = "Table comment"
                required_db_features = {"supports_comments"}

        self.assertEqual(Model.check(databases=self.databases), [])


class MultipleAutoFieldsTests(TestCase):
    def test_multiple_autofields(self):
        """

        Tests that a model cannot have multiple auto-generated fields.

        This test case verifies that attempting to define a model with more than one
        auto-field (i.e., fields using ``AutoField`` with ``primary_key=True``) raises
        a ``ValueError`` exception.

        The error message expected to be raised indicates that the model
        ``invalid_models_tests.MultipleAutoFields`` is invalid due to having more than
        one auto-generated field.

        This ensures that the framework enforces the rule that a model can have at most
        one auto-generated field, maintaining data integrity and preventing potential
        ambiguities in the database schema.

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
        class Model(models.Model):
            field = models.JSONField()

            class Meta:
                ordering = ["field__value"]

        self.assertEqual(Model.check(databases=self.databases), [])

    def test_check_jsonfield(self):
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
        Checks if the database features required by a model's JSONField are met.

        This test case ensures that a model with a JSONField explicitly requiring 
        database support for JSON fields can successfully check its requirements.

        The test covers the scenario where a model specifies 'supports_json_field' 
        in its Meta options as a required database feature, verifying that the 
        model's check method returns an empty list when run against the test 
        databases, indicating that all required features are supported.
        """
        class Model(models.Model):
            field = models.JSONField()

            class Meta:
                required_db_features = {"supports_json_field"}

        self.assertEqual(Model.check(databases=self.databases), [])


@isolate_apps("invalid_models_tests")
class ConstraintsTests(TestCase):
    def test_check_constraints(self):
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
        Check if a model with required database features and constraints can pass the model validation.

        The function tests the behavior of a model that includes a check constraint, which is a feature that may not be supported by all databases.
        It defines a model with an age field and a constraint that enforces the age to be greater than or equal to 18, simulating a realistic use case where such a constraint would be useful.
        The test ensures that the model validation process correctly handles the required database feature and the check constraint, and that no errors are raised when the model is checked against the specified databases.
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

        Tests whether the database correctly handles a check constraint in a model
        that references a reverse foreign key relationship. This test case verifies
        that the ORM raises an error when a check constraint attempts to reference
        a nonexistent field, specifically a reverse foreign key named 'parents'.

        The test aims to ensure that the model validation checks correctly identify
        and report this type of error, providing a meaningful error message.

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
        Tests the validation of check constraints defined using raw SQL.

        Verifies that the model's check constraints are properly validated during the 
        full clean operation, handling cases where raw SQL expressions are used.

        Specifically, it checks for warnings raised when raw SQL is used in check 
        constraints, ensuring that the model does not attempt to validate these 
        constraints during the full clean process. The test covers both simple and 
        nested raw SQL expressions within check constraints.

        This test case ensures correct behavior when working with check constraints 
        that use raw SQL, providing assurance that the model validation process 
        functions as expected in these scenarios.
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
        Tests the behavior of model validation when a unique constraint with a condition is defined and the required database features are specified.

        This test verifies that the model validation process correctly handles the case where a unique constraint is applied to a model field with a condition, such as a conditional unique constraint on a field. The required database features are also checked to ensure compatibility.

        The test covers a scenario where the unique constraint is defined with a condition, and the model is checked for any errors or warnings against the specified databases.

        Args:
            self: The test instance

        Returns:
            None
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
        """
        Tests whether a unique constraint raises an error when the include parameter points to a field that does not exist on the model.

        This test case ensures that Django correctly identifies and reports an invalid constraint definition, specifically when a UniqueConstraint specifies a field in its include parameter that is not a field on the model.

        The expected outcome is a validation error indicating that the 'constraints' Meta option refers to a nonexistent field. 

        The test covers the scenario where a model defines a unique constraint with an include parameter referencing a missing field, and verifies that the model check correctly identifies and reports this error. 
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
        Checks whether a Django model with a unique constraint on an expression is properly validated.
        The function tests if the model's unique constraint on a lower case field name is supported by the database backend.
        It verifies that a warning is raised when the database does not support unique constraints on expressions, and no warning is raised when it does. 
        The test ensures that the model's validation behaves as expected across different database backends.
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
        Tests the application of a unique constraint to a model using a custom lookup expression.

        The function verifies that a model with an integer field and a unique constraint
        defined by a custom expression can be successfully checked for database consistency.
        The constraint expression involves a calculation combining the 'height' and 'weight' fields.
        Ensures that the model validation process handles the custom lookup correctly, 
        returning an empty list to indicate no errors when the constraint is valid for the given databases.
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
        Tests the database's handling of unique constraints that reference a missing field within a nested expression.

        Specifically, this test case checks that an error is raised when a unique constraint is defined using an aggregate function (in this case, Abs and Round) that references a field that does not exist in the model.

        The expected outcome is that the database validation will catch this error and return a list containing a single Error object, which indicates that the 'constraints' attribute refers to a nonexistent field.

        This test ensures that the database correctly handles and reports errors in unique constraints, even when they involve complex expressions and nested references to missing fields.
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
