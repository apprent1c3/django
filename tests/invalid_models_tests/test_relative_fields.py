from unittest import mock

from django.core.checks import Error
from django.core.checks import Warning as DjangoWarning
from django.db import connection, models
from django.test.testcases import SimpleTestCase
from django.test.utils import isolate_apps, modify_settings, override_settings


@isolate_apps("invalid_models_tests")
class RelativeFieldTests(SimpleTestCase):
    def test_valid_foreign_key_without_accessor(self):
        """
        Tests that a foreign key without an accessor is valid, ensuring no errors are raised during field validation.
        """
        class Target(models.Model):
            # There would be a clash if Model.field installed an accessor.
            model = models.IntegerField()

        class Model(models.Model):
            field = models.ForeignKey(Target, models.CASCADE, related_name="+")

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])

    def test_foreign_key_to_missing_model(self):
        # Model names are resolved when a model is being created, so we cannot
        # test relative fields in isolation and we need to attach them to a
        # model.
        class Model(models.Model):
            foreign_key = models.ForeignKey("Rel1", models.CASCADE)

        field = Model._meta.get_field("foreign_key")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "Field defines a relation with model 'Rel1', "
                    "which is either not installed, or is abstract.",
                    obj=field,
                    id="fields.E300",
                ),
            ],
        )

    @isolate_apps("invalid_models_tests")
    def test_foreign_key_to_isolate_apps_model(self):
        """
        #25723 - Referenced model registration lookup should be run against the
        field's model registry.
        """

        class OtherModel(models.Model):
            pass

        class Model(models.Model):
            foreign_key = models.ForeignKey("OtherModel", models.CASCADE)

        field = Model._meta.get_field("foreign_key")
        self.assertEqual(field.check(from_model=Model), [])

    def test_many_to_many_to_missing_model(self):
        class Model(models.Model):
            m2m = models.ManyToManyField("Rel2")

        field = Model._meta.get_field("m2m")
        self.assertEqual(
            field.check(from_model=Model),
            [
                Error(
                    "Field defines a relation with model 'Rel2', "
                    "which is either not installed, or is abstract.",
                    obj=field,
                    id="fields.E300",
                ),
            ],
        )

    @isolate_apps("invalid_models_tests")
    def test_many_to_many_to_isolate_apps_model(self):
        """
        #25723 - Referenced model registration lookup should be run against the
        field's model registry.
        """

        class OtherModel(models.Model):
            pass

        class Model(models.Model):
            m2m = models.ManyToManyField("OtherModel")

        field = Model._meta.get_field("m2m")
        self.assertEqual(field.check(from_model=Model), [])

    @isolate_apps("invalid_models_tests")
    def test_auto_created_through_model(self):
        """
        Tests the auto-creation of a model's fields to ensure that an One-To-One field referencing a Many-To-Many field does not raise any errors during validation.
        """
        class OtherModel(models.Model):
            pass

        class M2MModel(models.Model):
            many_to_many_rel = models.ManyToManyField(OtherModel)

        class O2OModel(models.Model):
            one_to_one_rel = models.OneToOneField(
                "invalid_models_tests.M2MModel_many_to_many_rel",
                on_delete=models.CASCADE,
            )

        field = O2OModel._meta.get_field("one_to_one_rel")
        self.assertEqual(field.check(from_model=O2OModel), [])

    def test_many_to_many_with_useless_options(self):
        """
        Tests that Django correctly issues warnings for ManyToManyField when provided with options that have no effect, specifically 'null', 'validators', and 'db_comment'.
        """
        class Model(models.Model):
            name = models.CharField(max_length=20)

        class ModelM2M(models.Model):
            m2m = models.ManyToManyField(
                Model, null=True, validators=[lambda x: x], db_comment="Column comment"
            )

        field = ModelM2M._meta.get_field("m2m")
        self.assertEqual(
            ModelM2M.check(),
            [
                DjangoWarning(
                    "null has no effect on ManyToManyField.",
                    obj=field,
                    id="fields.W340",
                ),
                DjangoWarning(
                    "ManyToManyField does not support validators.",
                    obj=field,
                    id="fields.W341",
                ),
                DjangoWarning(
                    "db_comment has no effect on ManyToManyField.",
                    obj=field,
                    id="fields.W346",
                ),
            ],
        )

    def test_many_to_many_with_useless_related_name(self):
        class ModelM2M(models.Model):
            m2m = models.ManyToManyField("self", related_name="children")

        field = ModelM2M._meta.get_field("m2m")
        self.assertEqual(
            ModelM2M.check(),
            [
                DjangoWarning(
                    "related_name has no effect on ManyToManyField with "
                    'a symmetrical relationship, e.g. to "self".',
                    obj=field,
                    id="fields.W345",
                ),
            ],
        )

    def test_ambiguous_relationship_model_from(self):
        """
        Tests the error handling for an ambiguous relationship model in a ManyToManyField with a through model that has multiple foreign keys to the same model. Verifies that Django raises an error due to the ambiguity.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            field = models.ManyToManyField("Person", through="AmbiguousRelationship")

        class AmbiguousRelationship(models.Model):
            person = models.ForeignKey(Person, models.CASCADE)
            first_group = models.ForeignKey(Group, models.CASCADE, related_name="first")
            second_group = models.ForeignKey(
                Group, models.CASCADE, related_name="second"
            )

        field = Group._meta.get_field("field")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "The model is used as an intermediate model by "
                    "'invalid_models_tests.Group.field', but it has more than one "
                    "foreign key from 'Group', which is ambiguous. You must "
                    "specify which foreign key Django should use via the "
                    "through_fields keyword argument.",
                    hint=(
                        "If you want to create a recursive relationship, use "
                        'ManyToManyField("self", through="AmbiguousRelationship").'
                    ),
                    obj=field,
                    id="fields.E334",
                ),
            ],
        )

    def test_ambiguous_relationship_model_to(self):
        """
        Tests the behavior of the ManyToManyField when its intermediate model has multiple foreign keys to the same model, causing an ambiguous relationship. This check ensures Django raises the appropriate error when model ambiguity occurs.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            field = models.ManyToManyField(
                "Person", through="AmbiguousRelationship", related_name="tertiary"
            )

        class AmbiguousRelationship(models.Model):
            # Too much foreign keys to Person.
            first_person = models.ForeignKey(
                Person, models.CASCADE, related_name="first"
            )
            second_person = models.ForeignKey(
                Person, models.CASCADE, related_name="second"
            )
            second_model = models.ForeignKey(Group, models.CASCADE)

        field = Group._meta.get_field("field")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "The model is used as an intermediate model by "
                    "'invalid_models_tests.Group.field', but it has more than one "
                    "foreign key to 'Person', which is ambiguous. You must specify "
                    "which foreign key Django should use via the through_fields "
                    "keyword argument.",
                    hint=(
                        "If you want to create a recursive relationship, use "
                        'ManyToManyField("self", through="AmbiguousRelationship").'
                    ),
                    obj=field,
                    id="fields.E335",
                ),
            ],
        )

    def test_relationship_model_with_foreign_key_to_wrong_model(self):
        """
        Tests that a ManyToManyField raises an error when its through model has a ForeignKey to the wrong model.
        """
        class WrongModel(models.Model):
            pass

        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField("Person", through="InvalidRelationship")

        class InvalidRelationship(models.Model):
            person = models.ForeignKey(Person, models.CASCADE)
            wrong_foreign_key = models.ForeignKey(WrongModel, models.CASCADE)
            # The last foreign key should point to Group model.

        field = Group._meta.get_field("members")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "The model is used as an intermediate model by "
                    "'invalid_models_tests.Group.members', but it does not "
                    "have a foreign key to 'Group' or 'Person'.",
                    obj=InvalidRelationship,
                    id="fields.E336",
                ),
            ],
        )

    def test_relationship_model_missing_foreign_key(self):
        """
        Tests that a ManyToManyField relationship raises an error when the through model is missing a foreign key to one of the related models.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField("Person", through="InvalidRelationship")

        class InvalidRelationship(models.Model):
            group = models.ForeignKey(Group, models.CASCADE)
            # No foreign key to Person

        field = Group._meta.get_field("members")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "The model is used as an intermediate model by "
                    "'invalid_models_tests.Group.members', but it does not have "
                    "a foreign key to 'Group' or 'Person'.",
                    obj=InvalidRelationship,
                    id="fields.E336",
                ),
            ],
        )

    def test_missing_relationship_model(self):
        """
        Tests that a ManyToManyField raises an error when its 'through' model is missing.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField("Person", through="MissingM2MModel")

        field = Group._meta.get_field("members")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "Field specifies a many-to-many relation through model "
                    "'MissingM2MModel', which has not been installed.",
                    obj=field,
                    id="fields.E331",
                ),
            ],
        )

    def test_missing_relationship_model_on_model_check(self):
        """
        Tests that model check raises an error when a many-to-many relationship is defined with a missing through model.
        """
        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField("Person", through="MissingM2MModel")

        self.assertEqual(
            Group.check(),
            [
                Error(
                    "Field specifies a many-to-many relation through model "
                    "'MissingM2MModel', which has not been installed.",
                    obj=Group._meta.get_field("members"),
                    id="fields.E331",
                ),
            ],
        )

    @isolate_apps("invalid_models_tests")
    def test_many_to_many_through_isolate_apps_model(self):
        """
        #25723 - Through model registration lookup should be run against the
        field's model registry.
        """

        class GroupMember(models.Model):
            person = models.ForeignKey("Person", models.CASCADE)
            group = models.ForeignKey("Group", models.CASCADE)

        class Person(models.Model):
            pass

        class Group(models.Model):
            members = models.ManyToManyField("Person", through="GroupMember")

        field = Group._meta.get_field("members")
        self.assertEqual(field.check(from_model=Group), [])

    def test_too_many_foreign_keys_in_self_referential_model(self):
        """
        Tests that Django correctly raises an error when a self-referential ManyToManyField has an intermediate model with more than two foreign keys to the same model, which creates an ambiguity.
        """
        class Person(models.Model):
            friends = models.ManyToManyField(
                "self", through="InvalidRelationship", symmetrical=False
            )

        class InvalidRelationship(models.Model):
            first = models.ForeignKey(
                Person, models.CASCADE, related_name="rel_from_set_2"
            )
            second = models.ForeignKey(
                Person, models.CASCADE, related_name="rel_to_set_2"
            )
            third = models.ForeignKey(
                Person, models.CASCADE, related_name="too_many_by_far"
            )

        field = Person._meta.get_field("friends")
        self.assertEqual(
            field.check(from_model=Person),
            [
                Error(
                    "The model is used as an intermediate model by "
                    "'invalid_models_tests.Person.friends', but it has more than two "
                    "foreign keys to 'Person', which is ambiguous. You must specify "
                    "which two foreign keys Django should use via the through_fields "
                    "keyword argument.",
                    hint=(
                        "Use through_fields to specify which two foreign keys Django "
                        "should use."
                    ),
                    obj=InvalidRelationship,
                    id="fields.E333",
                ),
            ],
        )

    def test_foreign_key_to_abstract_model(self):
        """
        Tests the validation of foreign key fields referencing an abstract model, ensuring an error is raised when using either a string or class reference to the abstract model.
        """
        class AbstractModel(models.Model):
            class Meta:
                abstract = True

        class Model(models.Model):
            rel_string_foreign_key = models.ForeignKey("AbstractModel", models.CASCADE)
            rel_class_foreign_key = models.ForeignKey(AbstractModel, models.CASCADE)

        fields = [
            Model._meta.get_field("rel_string_foreign_key"),
            Model._meta.get_field("rel_class_foreign_key"),
        ]
        expected_error = Error(
            "Field defines a relation with model 'AbstractModel', "
            "which is either not installed, or is abstract.",
            id="fields.E300",
        )
        for field in fields:
            expected_error.obj = field
            self.assertEqual(field.check(), [expected_error])

    def test_m2m_to_abstract_model(self):
        """
        Tests that Django's ManyToManyField validation raises an error when referencing an abstract base model.
        """
        class AbstractModel(models.Model):
            class Meta:
                abstract = True

        class Model(models.Model):
            rel_string_m2m = models.ManyToManyField("AbstractModel")
            rel_class_m2m = models.ManyToManyField(AbstractModel)

        fields = [
            Model._meta.get_field("rel_string_m2m"),
            Model._meta.get_field("rel_class_m2m"),
        ]
        expected_error = Error(
            "Field defines a relation with model 'AbstractModel', "
            "which is either not installed, or is abstract.",
            id="fields.E300",
        )
        for field in fields:
            expected_error.obj = field
            self.assertEqual(field.check(from_model=Model), [expected_error])

    def test_unique_m2m(self):
        """
        Checks that ManyToManyFields with unique=True are correctly validated and raises an error, as ManyToManyFields cannot enforce uniqueness due to their underlying implementation as separate tables.
        """
        class Person(models.Model):
            name = models.CharField(max_length=5)

        class Group(models.Model):
            members = models.ManyToManyField("Person", unique=True)

        field = Group._meta.get_field("members")
        self.assertEqual(
            field.check(from_model=Group),
            [
                Error(
                    "ManyToManyFields cannot be unique.",
                    obj=field,
                    id="fields.E330",
                ),
            ],
        )

    def test_foreign_key_to_non_unique_field(self):
        """
        Tests that a foreign key referencing a non-unique field on the target model raises an error, indicating the need for a unique constraint on the referenced field.
        """
        class Target(models.Model):
            bad = models.IntegerField()  # No unique=True

        class Model(models.Model):
            foreign_key = models.ForeignKey("Target", models.CASCADE, to_field="bad")

        field = Model._meta.get_field("foreign_key")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'Target.bad' must be unique because it is referenced by a foreign "
                    "key.",
                    hint=(
                        "Add unique=True to this field or add a UniqueConstraint "
                        "(without condition) in the model Meta.constraints."
                    ),
                    obj=field,
                    id="fields.E311",
                ),
            ],
        )

    def test_foreign_key_to_non_unique_field_under_explicit_model(self):
        """
        Tests that a foreign key referencing a non-unique field raises an error, as it should be unique to enable proper foreign key functionality.
        """
        class Target(models.Model):
            bad = models.IntegerField()

        class Model(models.Model):
            field = models.ForeignKey(Target, models.CASCADE, to_field="bad")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'Target.bad' must be unique because it is referenced by a foreign "
                    "key.",
                    hint=(
                        "Add unique=True to this field or add a UniqueConstraint "
                        "(without condition) in the model Meta.constraints."
                    ),
                    obj=field,
                    id="fields.E311",
                ),
            ],
        )

    def test_foreign_key_to_partially_unique_field(self):
        """
        Tests that a foreign key to a partially unique field raises an error, as the referenced field must be unique when referenced by a foreign key, unless a UniqueConstraint without condition is defined in the model Meta.constraints.
        """
        class Target(models.Model):
            source = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["source"],
                        name="tfktpuf_partial_unique",
                        condition=models.Q(pk__gt=2),
                    ),
                ]

        class Model(models.Model):
            field = models.ForeignKey(Target, models.CASCADE, to_field="source")

        field = Model._meta.get_field("field")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "'Target.source' must be unique because it is referenced by a "
                    "foreign key.",
                    hint=(
                        "Add unique=True to this field or add a UniqueConstraint "
                        "(without condition) in the model Meta.constraints."
                    ),
                    obj=field,
                    id="fields.E311",
                ),
            ],
        )

    def test_foreign_key_to_unique_field_with_meta_constraint(self):
        """
        Tests that a foreign key to a unique field with a meta constraint is created without any errors or warnings. Verifies the correctness of the foreign key relationship and its integrity checks.
        """
        class Target(models.Model):
            source = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["source"],
                        name="tfktufwmc_unique",
                    ),
                ]

        class Model(models.Model):
            field = models.ForeignKey(Target, models.CASCADE, to_field="source")

        field = Model._meta.get_field("field")
        self.assertEqual(field.check(), [])

    def test_foreign_object_to_non_unique_fields(self):
        """
        Tests that a ForeignObject to non-unique fields on a related model raises an error.

        The test case checks that Django correctly identifies and reports the issue when trying to create a foreign object relationship 
        without a unique constraint on the related model's fields. This ensures data consistency by preventing ambiguous references.
        """
        class Person(models.Model):
            # Note that both fields are not unique.
            country_id = models.IntegerField()
            city_id = models.IntegerField()

        class MMembership(models.Model):
            person_country_id = models.IntegerField()
            person_city_id = models.IntegerField()

            person = models.ForeignObject(
                Person,
                on_delete=models.CASCADE,
                from_fields=["person_country_id", "person_city_id"],
                to_fields=["country_id", "city_id"],
            )

        field = MMembership._meta.get_field("person")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "No subset of the fields 'country_id', 'city_id' on model 'Person' "
                    "is unique.",
                    hint=(
                        "Mark a single field as unique=True or add a set of "
                        "fields to a unique constraint (via unique_together or a "
                        "UniqueConstraint (without condition) in the model "
                        "Meta.constraints)."
                    ),
                    obj=field,
                    id="fields.E310",
                )
            ],
        )

    def test_foreign_object_to_partially_unique_field(self):
        """
        Tests that a ForeignObject to a partially unique field raises an error, as Django requires a unique subset of fields for the relation to work correctly.
        """
        class Person(models.Model):
            country_id = models.IntegerField()
            city_id = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["country_id", "city_id"],
                        name="tfotpuf_partial_unique",
                        condition=models.Q(pk__gt=2),
                    ),
                ]

        class MMembership(models.Model):
            person_country_id = models.IntegerField()
            person_city_id = models.IntegerField()
            person = models.ForeignObject(
                Person,
                on_delete=models.CASCADE,
                from_fields=["person_country_id", "person_city_id"],
                to_fields=["country_id", "city_id"],
            )

        field = MMembership._meta.get_field("person")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "No subset of the fields 'country_id', 'city_id' on model "
                    "'Person' is unique.",
                    hint=(
                        "Mark a single field as unique=True or add a set of "
                        "fields to a unique constraint (via unique_together or a "
                        "UniqueConstraint (without condition) in the model "
                        "Meta.constraints)."
                    ),
                    obj=field,
                    id="fields.E310",
                ),
            ],
        )

    def test_foreign_object_to_unique_field_with_meta_constraint(self):
        """
        Tests that a foreign object referencing a model with a unique constraint on multiple fields works correctly, ensuring data integrity by verifying that no validation errors are raised.
        """
        class Person(models.Model):
            country_id = models.IntegerField()
            city_id = models.IntegerField()

            class Meta:
                constraints = [
                    models.UniqueConstraint(
                        fields=["country_id", "city_id"],
                        name="tfotpuf_unique",
                    ),
                ]

        class MMembership(models.Model):
            person_country_id = models.IntegerField()
            person_city_id = models.IntegerField()
            person = models.ForeignObject(
                Person,
                on_delete=models.CASCADE,
                from_fields=["person_country_id", "person_city_id"],
                to_fields=["country_id", "city_id"],
            )

        field = MMembership._meta.get_field("person")
        self.assertEqual(field.check(), [])

    def test_on_delete_set_null_on_non_nullable_field(self):
        """
        Tests that setting on_delete to SET_NULL on a non-nullable ForeignKey field raises an error, ensuring data integrity by preventing null values in such fields.
        """
        class Person(models.Model):
            pass

        class Model(models.Model):
            foreign_key = models.ForeignKey("Person", models.SET_NULL)

        field = Model._meta.get_field("foreign_key")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "Field specifies on_delete=SET_NULL, but cannot be null.",
                    hint=(
                        "Set null=True argument on the field, or change the on_delete "
                        "rule."
                    ),
                    obj=field,
                    id="fields.E320",
                ),
            ],
        )

    def test_on_delete_set_default_without_default_value(self):
        """
        Tests that a ForeignKey field with on_delete set to SET_DEFAULT raises an error when no default value is provided.
        """
        class Person(models.Model):
            pass

        class Model(models.Model):
            foreign_key = models.ForeignKey("Person", models.SET_DEFAULT)

        field = Model._meta.get_field("foreign_key")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "Field specifies on_delete=SET_DEFAULT, but has no default value.",
                    hint="Set a default value, or change the on_delete rule.",
                    obj=field,
                    id="fields.E321",
                ),
            ],
        )

    def test_nullable_primary_key(self):
        """
        Tests that setting a primary key field to be nullable raises a validation error.
        """
        class Model(models.Model):
            field = models.IntegerField(primary_key=True, null=True)

        field = Model._meta.get_field("field")
        with mock.patch.object(
            connection.features, "interprets_empty_strings_as_nulls", False
        ):
            results = field.check()
        self.assertEqual(
            results,
            [
                Error(
                    "Primary keys must not have null=True.",
                    hint=(
                        "Set null=False on the field, or remove primary_key=True "
                        "argument."
                    ),
                    obj=field,
                    id="fields.E007",
                ),
            ],
        )

    def test_not_swapped_model(self):
        """
        Tests that field checks on swappable models do not trigger errors when the swappable model is not swapped.
        """
        class SwappableModel(models.Model):
            # A model that can be, but isn't swapped out. References to this
            # model should *not* raise any validation error.
            class Meta:
                swappable = "TEST_SWAPPABLE_MODEL"

        class Model(models.Model):
            explicit_fk = models.ForeignKey(
                SwappableModel,
                models.CASCADE,
                related_name="explicit_fk",
            )
            implicit_fk = models.ForeignKey(
                "invalid_models_tests.SwappableModel",
                models.CASCADE,
                related_name="implicit_fk",
            )
            explicit_m2m = models.ManyToManyField(
                SwappableModel, related_name="explicit_m2m"
            )
            implicit_m2m = models.ManyToManyField(
                "invalid_models_tests.SwappableModel",
                related_name="implicit_m2m",
            )

        explicit_fk = Model._meta.get_field("explicit_fk")
        self.assertEqual(explicit_fk.check(), [])

        implicit_fk = Model._meta.get_field("implicit_fk")
        self.assertEqual(implicit_fk.check(), [])

        explicit_m2m = Model._meta.get_field("explicit_m2m")
        self.assertEqual(explicit_m2m.check(from_model=Model), [])

        implicit_m2m = Model._meta.get_field("implicit_m2m")
        self.assertEqual(implicit_m2m.check(from_model=Model), [])

    @override_settings(TEST_SWAPPED_MODEL="invalid_models_tests.Replacement")
    def test_referencing_to_swapped_model(self):
        """
        Tests that referencing a model that has been swapped out results in the correct validation error.
        """
        class Replacement(models.Model):
            pass

        class SwappedModel(models.Model):
            class Meta:
                swappable = "TEST_SWAPPED_MODEL"

        class Model(models.Model):
            explicit_fk = models.ForeignKey(
                SwappedModel,
                models.CASCADE,
                related_name="explicit_fk",
            )
            implicit_fk = models.ForeignKey(
                "invalid_models_tests.SwappedModel",
                models.CASCADE,
                related_name="implicit_fk",
            )
            explicit_m2m = models.ManyToManyField(
                SwappedModel, related_name="explicit_m2m"
            )
            implicit_m2m = models.ManyToManyField(
                "invalid_models_tests.SwappedModel",
                related_name="implicit_m2m",
            )

        fields = [
            Model._meta.get_field("explicit_fk"),
            Model._meta.get_field("implicit_fk"),
            Model._meta.get_field("explicit_m2m"),
            Model._meta.get_field("implicit_m2m"),
        ]

        expected_error = Error(
            (
                "Field defines a relation with the model "
                "'invalid_models_tests.SwappedModel', which has been swapped out."
            ),
            hint="Update the relation to point at 'settings.TEST_SWAPPED_MODEL'.",
            id="fields.E301",
        )

        for field in fields:
            expected_error.obj = field
            self.assertEqual(field.check(from_model=Model), [expected_error])

    def test_related_field_has_invalid_related_name(self):
        """
        Checks that the related_name of a foreign key field is a valid Python identifier or ends with a '+'.
        """
        digit = 0
        illegal_non_alphanumeric = "!"
        whitespace = "\t"

        invalid_related_names = [
            "%s_begins_with_digit" % digit,
            "%s_begins_with_illegal_non_alphanumeric" % illegal_non_alphanumeric,
            "%s_begins_with_whitespace" % whitespace,
            "contains_%s_illegal_non_alphanumeric" % illegal_non_alphanumeric,
            "contains_%s_whitespace" % whitespace,
            "ends_with_with_illegal_non_alphanumeric_%s" % illegal_non_alphanumeric,
            "ends_with_whitespace_%s" % whitespace,
            "with",  # a Python keyword
            "related_name\n",
            "",
            "，",  # non-ASCII
        ]

        class Parent(models.Model):
            pass

        for invalid_related_name in invalid_related_names:
            Child = type(
                "Child%s" % invalid_related_name,
                (models.Model,),
                {
                    "parent": models.ForeignKey(
                        "Parent", models.CASCADE, related_name=invalid_related_name
                    ),
                    "__module__": Parent.__module__,
                },
            )

            field = Child._meta.get_field("parent")
            self.assertEqual(
                Child.check(),
                [
                    Error(
                        "The name '%s' is invalid related_name for field Child%s.parent"
                        % (invalid_related_name, invalid_related_name),
                        hint=(
                            "Related name must be a valid Python identifier or end "
                            "with a '+'"
                        ),
                        obj=field,
                        id="fields.E306",
                    ),
                ],
            )

    def test_related_field_has_valid_related_name(self):
        """
        Checks that a model's related field name is valid according to Django's naming conventions, ensuring it doesn't raise any errors when used in the model. The test covers a variety of related name formats, including names starting with uppercase or lowercase letters, digits, underscores, and special characters, as well as names containing invalid characters.
        """
        lowercase = "a"
        uppercase = "A"
        digit = 0

        related_names = [
            "%s_starts_with_lowercase" % lowercase,
            "%s_tarts_with_uppercase" % uppercase,
            "_starts_with_underscore",
            "contains_%s_digit" % digit,
            "ends_with_plus+",
            "_+",
            "+",
            "試",
            "試驗+",
        ]

        class Parent(models.Model):
            pass

        for related_name in related_names:
            Child = type(
                "Child%s" % related_name,
                (models.Model,),
                {
                    "parent": models.ForeignKey(
                        "Parent", models.CASCADE, related_name=related_name
                    ),
                    "__module__": Parent.__module__,
                },
            )
            self.assertEqual(Child.check(), [])

    def test_to_fields_exist(self):
        """
        Tests that a ForeignObject field with from_fields and to_fields correctly identifies missing fields on the related model.
        """
        class Parent(models.Model):
            pass

        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            parent = models.ForeignObject(
                Parent,
                on_delete=models.SET_NULL,
                from_fields=("a", "b"),
                to_fields=("a", "b"),
            )

        field = Child._meta.get_field("parent")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "The to_field 'a' doesn't exist on the related model "
                    "'invalid_models_tests.Parent'.",
                    obj=field,
                    id="fields.E312",
                ),
                Error(
                    "The to_field 'b' doesn't exist on the related model "
                    "'invalid_models_tests.Parent'.",
                    obj=field,
                    id="fields.E312",
                ),
            ],
        )

    def test_to_fields_not_checked_if_related_model_doesnt_exist(self):
        """
        Tests that 'to_fields' are not checked if the related model does not exist, 
        resulting in a specific validation error being raised.
        """
        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            parent = models.ForeignObject(
                "invalid_models_tests.Parent",
                on_delete=models.SET_NULL,
                from_fields=("a", "b"),
                to_fields=("a", "b"),
            )

        field = Child._meta.get_field("parent")
        self.assertEqual(
            field.check(),
            [
                Error(
                    "Field defines a relation with model "
                    "'invalid_models_tests.Parent', which is either not installed, or "
                    "is abstract.",
                    id="fields.E300",
                    obj=field,
                ),
            ],
        )

    def test_invalid_related_query_name(self):
        """
        Tests that a model with foreign key fields having invalid related query names raises the expected errors. The function checks for related names containing double underscores and related query names ending with an underscore, ensuring they conform to the required naming conventions.
        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            first = models.ForeignKey(
                Target, models.CASCADE, related_name="contains__double"
            )
            second = models.ForeignKey(
                Target, models.CASCADE, related_query_name="ends_underscore_"
            )

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse query name 'contains__double' must not contain '__'.",
                    hint=(
                        "Add or change a related_name or related_query_name "
                        "argument for this field."
                    ),
                    obj=Model._meta.get_field("first"),
                    id="fields.E309",
                ),
                Error(
                    "Reverse query name 'ends_underscore_' must not end with an "
                    "underscore.",
                    hint=(
                        "Add or change a related_name or related_query_name "
                        "argument for this field."
                    ),
                    obj=Model._meta.get_field("second"),
                    id="fields.E308",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class AccessorClashTests(SimpleTestCase):
    def test_fk_to_integer(self):
        self._test_accessor_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_fk_to_fk(self):
        self._test_accessor_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_fk_to_m2m(self):
        self._test_accessor_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_m2m_to_integer(self):
        self._test_accessor_clash(
            target=models.IntegerField(), relative=models.ManyToManyField("Target")
        )

    def test_m2m_to_fk(self):
        self._test_accessor_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ManyToManyField("Target"),
        )

    def test_m2m_to_m2m(self):
        self._test_accessor_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ManyToManyField("Target"),
        )

    def _test_accessor_clash(self, target, relative):
        """
        Tests for the case when the reverse accessor for a relationship field clashes with an existing field name on the related model, ensuring that the correct error is raised and provides a meaningful hint for resolution.
        """
        class Another(models.Model):
            pass

        class Target(models.Model):
            model_set = target

        class Model(models.Model):
            rel = relative

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Target.model_set' for "
                    "'invalid_models_tests.Model.rel' clashes with field name "
                    "'invalid_models_tests.Target.model_set'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.model_set', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.rel'."
                    ),
                    obj=Model._meta.get_field("rel"),
                    id="fields.E302",
                ),
            ],
        )

    def test_clash_between_accessors(self):
        """

        Tests that the model validation correctly identifies clashes between reverse accessors
        for foreign key and many-to-many fields.

        """
        class Target(models.Model):
            pass

        class Model(models.Model):
            foreign = models.ForeignKey(Target, models.CASCADE)
            m2m = models.ManyToManyField(Target)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Target.model_set' for "
                    "'invalid_models_tests.Model.foreign' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.m2m'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.foreign' or "
                        "'invalid_models_tests.Model.m2m'."
                    ),
                    obj=Model._meta.get_field("foreign"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse accessor 'Target.model_set' for "
                    "'invalid_models_tests.Model.m2m' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.foreign'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.m2m' or "
                        "'invalid_models_tests.Model.foreign'."
                    ),
                    obj=Model._meta.get_field("m2m"),
                    id="fields.E304",
                ),
            ],
        )

    def test_m2m_to_m2m_with_inheritance(self):
        """Ref #22047."""

        class Target(models.Model):
            pass

        class Model(models.Model):
            children = models.ManyToManyField(
                "Child", related_name="m2m_clash", related_query_name="no_clash"
            )

        class Parent(models.Model):
            m2m_clash = models.ManyToManyField("Target")

        class Child(Parent):
            pass

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Child.m2m_clash' for "
                    "'invalid_models_tests.Model.children' clashes with field "
                    "name 'invalid_models_tests.Child.m2m_clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Child.m2m_clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.children'."
                    ),
                    obj=Model._meta.get_field("children"),
                    id="fields.E302",
                )
            ],
        )

    def test_no_clash_for_hidden_related_name(self):
        """
        Verifies that using a '+' related name in ManyToManyField and ForeignKey fields does not cause conflicts when model checking is performed.
        """
        class Stub(models.Model):
            pass

        class ManyToManyRel(models.Model):
            thing1 = models.ManyToManyField(Stub, related_name="+")
            thing2 = models.ManyToManyField(Stub, related_name="+")

        class FKRel(models.Model):
            thing1 = models.ForeignKey(Stub, models.CASCADE, related_name="+")
            thing2 = models.ForeignKey(Stub, models.CASCADE, related_name="+")

        self.assertEqual(ManyToManyRel.check(), [])
        self.assertEqual(FKRel.check(), [])


@isolate_apps("invalid_models_tests")
class ReverseQueryNameClashTests(SimpleTestCase):
    def test_fk_to_integer(self):
        self._test_reverse_query_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_fk_to_fk(self):
        self._test_reverse_query_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_fk_to_m2m(self):
        self._test_reverse_query_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ForeignKey("Target", models.CASCADE),
        )

    def test_m2m_to_integer(self):
        self._test_reverse_query_name_clash(
            target=models.IntegerField(), relative=models.ManyToManyField("Target")
        )

    def test_m2m_to_fk(self):
        self._test_reverse_query_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ManyToManyField("Target"),
        )

    def test_m2m_to_m2m(self):
        self._test_reverse_query_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ManyToManyField("Target"),
        )

    def _test_reverse_query_name_clash(self, target, relative):
        """
        Tests that Django raises an error when a reverse query name clashes with a field name on a related model.
        """
        class Another(models.Model):
            pass

        class Target(models.Model):
            model = target

        class Model(models.Model):
            rel = relative

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.rel' "
                    "clashes with field name 'invalid_models_tests.Target.model'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.model', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.rel'."
                    ),
                    obj=Model._meta.get_field("rel"),
                    id="fields.E303",
                ),
            ],
        )

    @modify_settings(INSTALLED_APPS={"append": "basic"})
    @isolate_apps("basic", "invalid_models_tests")
    def test_no_clash_across_apps_without_accessor(self):
        """
        Tests that there are no naming clashes for ManyToMany fields across Django applications when no related_name accessor is provided.
        """
        class Target(models.Model):
            class Meta:
                app_label = "invalid_models_tests"

        class Model(models.Model):
            m2m = models.ManyToManyField(Target, related_name="+")

            class Meta:
                app_label = "basic"

        def _test():
            # Define model with the same name.
            """
            Internal test function to verify that a model with a many-to-many field has no validation errors.
            """
            class Model(models.Model):
                m2m = models.ManyToManyField(Target, related_name="+")

                class Meta:
                    app_label = "invalid_models_tests"

            self.assertEqual(Model.check(), [])

        _test()
        self.assertEqual(Model.check(), [])


@isolate_apps("invalid_models_tests")
class ExplicitRelatedNameClashTests(SimpleTestCase):
    def test_fk_to_integer(self):
        self._test_explicit_related_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey("Target", models.CASCADE, related_name="clash"),
        )

    def test_fk_to_fk(self):
        self._test_explicit_related_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ForeignKey("Target", models.CASCADE, related_name="clash"),
        )

    def test_fk_to_m2m(self):
        self._test_explicit_related_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ForeignKey("Target", models.CASCADE, related_name="clash"),
        )

    def test_m2m_to_integer(self):
        self._test_explicit_related_name_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField("Target", related_name="clash"),
        )

    def test_m2m_to_fk(self):
        self._test_explicit_related_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ManyToManyField("Target", related_name="clash"),
        )

    def test_m2m_to_m2m(self):
        self._test_explicit_related_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ManyToManyField("Target", related_name="clash"),
        )

    def _test_explicit_related_name_clash(self, target, relative):
        """
        Tests that Django correctly identifies and reports a field name clash that occurs when a related field's reverse accessor conflicts with an existing field name on the related model.
        """
        class Another(models.Model):
            pass

        class Target(models.Model):
            clash = target

        class Model(models.Model):
            rel = relative

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Target.clash' for "
                    "'invalid_models_tests.Model.rel' clashes with field name "
                    "'invalid_models_tests.Target.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.rel'."
                    ),
                    obj=Model._meta.get_field("rel"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.rel' "
                    "clashes with field name 'invalid_models_tests.Target.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.rel'."
                    ),
                    obj=Model._meta.get_field("rel"),
                    id="fields.E303",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class ExplicitRelatedQueryNameClashTests(SimpleTestCase):
    def test_fk_to_integer(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.IntegerField(),
            relative=models.ForeignKey(
                "Target",
                models.CASCADE,
                related_name=related_name,
                related_query_name="clash",
            ),
        )

    def test_hidden_fk_to_integer(self, related_name=None):
        self.test_fk_to_integer(related_name="+")

    def test_fk_to_fk(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ForeignKey(
                "Target",
                models.CASCADE,
                related_name=related_name,
                related_query_name="clash",
            ),
        )

    def test_hidden_fk_to_fk(self):
        self.test_fk_to_fk(related_name="+")

    def test_fk_to_m2m(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ForeignKey(
                "Target",
                models.CASCADE,
                related_name=related_name,
                related_query_name="clash",
            ),
        )

    def test_hidden_fk_to_m2m(self):
        self.test_fk_to_m2m(related_name="+")

    def test_m2m_to_integer(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.IntegerField(),
            relative=models.ManyToManyField(
                "Target", related_name=related_name, related_query_name="clash"
            ),
        )

    def test_hidden_m2m_to_integer(self):
        self.test_m2m_to_integer(related_name="+")

    def test_m2m_to_fk(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.ForeignKey("Another", models.CASCADE),
            relative=models.ManyToManyField(
                "Target", related_name=related_name, related_query_name="clash"
            ),
        )

    def test_hidden_m2m_to_fk(self):
        self.test_m2m_to_fk(related_name="+")

    def test_m2m_to_m2m(self, related_name=None):
        self._test_explicit_related_query_name_clash(
            target=models.ManyToManyField("Another"),
            relative=models.ManyToManyField(
                "Target",
                related_name=related_name,
                related_query_name="clash",
            ),
        )

    def test_hidden_m2m_to_m2m(self):
        self.test_m2m_to_m2m(related_name="+")

    def _test_explicit_related_query_name_clash(self, target, relative):
        """
        Tests a case where the reverse query name of a related field clashes with an existing field name on the target model, verifying that a corresponding error is raised with a helpful error message and hint for resolution.
        """
        class Another(models.Model):
            pass

        class Target(models.Model):
            clash = target

        class Model(models.Model):
            rel = relative

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.rel' "
                    "clashes with field name 'invalid_models_tests.Target.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.rel'."
                    ),
                    obj=Model._meta.get_field("rel"),
                    id="fields.E303",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class SelfReferentialM2MClashTests(SimpleTestCase):
    def test_clash_between_accessors(self):
        class Model(models.Model):
            first_m2m = models.ManyToManyField("self", symmetrical=False)
            second_m2m = models.ManyToManyField("self", symmetrical=False)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Model.model_set' for "
                    "'invalid_models_tests.Model.first_m2m' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.second_m2m'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.first_m2m' or "
                        "'invalid_models_tests.Model.second_m2m'."
                    ),
                    obj=Model._meta.get_field("first_m2m"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse accessor 'Model.model_set' for "
                    "'invalid_models_tests.Model.second_m2m' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.first_m2m'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.second_m2m' or "
                        "'invalid_models_tests.Model.first_m2m'."
                    ),
                    obj=Model._meta.get_field("second_m2m"),
                    id="fields.E304",
                ),
            ],
        )

    def test_accessor_clash(self):
        class Model(models.Model):
            model_set = models.ManyToManyField("self", symmetrical=False)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Model.model_set' for "
                    "'invalid_models_tests.Model.model_set' clashes with field "
                    "name 'invalid_models_tests.Model.model_set'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.model_set', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.model_set'."
                    ),
                    obj=Model._meta.get_field("model_set"),
                    id="fields.E302",
                ),
            ],
        )

    def test_reverse_query_name_clash(self):
        class Model(models.Model):
            model = models.ManyToManyField("self", symmetrical=False)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.model' "
                    "clashes with field name 'invalid_models_tests.Model.model'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.model', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.model'."
                    ),
                    obj=Model._meta.get_field("model"),
                    id="fields.E303",
                ),
            ],
        )

    def test_clash_under_explicit_related_name(self):
        class Model(models.Model):
            clash = models.IntegerField()
            m2m = models.ManyToManyField(
                "self", symmetrical=False, related_name="clash"
            )

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Model.clash' for "
                    "'invalid_models_tests.Model.m2m' clashes with field name "
                    "'invalid_models_tests.Model.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.m2m'."
                    ),
                    obj=Model._meta.get_field("m2m"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.m2m' "
                    "clashes with field name 'invalid_models_tests.Model.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.m2m'."
                    ),
                    obj=Model._meta.get_field("m2m"),
                    id="fields.E303",
                ),
            ],
        )

    def test_valid_model(self):
        class Model(models.Model):
            first = models.ManyToManyField(
                "self", symmetrical=False, related_name="first_accessor"
            )
            second = models.ManyToManyField(
                "self", symmetrical=False, related_name="second_accessor"
            )

        self.assertEqual(Model.check(), [])


@isolate_apps("invalid_models_tests")
class SelfReferentialFKClashTests(SimpleTestCase):
    def test_accessor_clash(self):
        class Model(models.Model):
            model_set = models.ForeignKey("Model", models.CASCADE)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Model.model_set' for "
                    "'invalid_models_tests.Model.model_set' clashes with field "
                    "name 'invalid_models_tests.Model.model_set'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.model_set', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.model_set'."
                    ),
                    obj=Model._meta.get_field("model_set"),
                    id="fields.E302",
                ),
            ],
        )

    def test_reverse_query_name_clash(self):
        class Model(models.Model):
            model = models.ForeignKey("Model", models.CASCADE)

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.model' "
                    "clashes with field name 'invalid_models_tests.Model.model'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.model', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.model'."
                    ),
                    obj=Model._meta.get_field("model"),
                    id="fields.E303",
                ),
            ],
        )

    def test_clash_under_explicit_related_name(self):
        class Model(models.Model):
            clash = models.CharField(max_length=10)
            foreign = models.ForeignKey("Model", models.CASCADE, related_name="clash")

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Model.clash' for "
                    "'invalid_models_tests.Model.foreign' clashes with field name "
                    "'invalid_models_tests.Model.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.foreign'."
                    ),
                    obj=Model._meta.get_field("foreign"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.foreign' "
                    "clashes with field name 'invalid_models_tests.Model.clash'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Model.clash', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.foreign'."
                    ),
                    obj=Model._meta.get_field("foreign"),
                    id="fields.E303",
                ),
            ],
        )


@isolate_apps("invalid_models_tests")
class ComplexClashTests(SimpleTestCase):
    # New tests should not be included here, because this is a single,
    # self-contained sanity check, not a test of everything.
    def test_complex_clash(self):
        """
        Tests a complex scenario of field and reverse accessor naming clashes in Django models, helping ensure that related_name arguments are correctly set for foreign key and many-to-many fields to avoid conflicts with field names and other reverse accessors.
        """
        class Target(models.Model):
            tgt_safe = models.CharField(max_length=10)
            clash = models.CharField(max_length=10)
            model = models.CharField(max_length=10)

            clash1_set = models.CharField(max_length=10)

        class Model(models.Model):
            src_safe = models.CharField(max_length=10)

            foreign_1 = models.ForeignKey(Target, models.CASCADE, related_name="id")
            foreign_2 = models.ForeignKey(
                Target, models.CASCADE, related_name="src_safe"
            )

            m2m_1 = models.ManyToManyField(Target, related_name="id")
            m2m_2 = models.ManyToManyField(Target, related_name="src_safe")

        self.assertEqual(
            Model.check(),
            [
                Error(
                    "Reverse accessor 'Target.id' for "
                    "'invalid_models_tests.Model.foreign_1' clashes with field "
                    "name 'invalid_models_tests.Target.id'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.id', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.foreign_1'."
                    ),
                    obj=Model._meta.get_field("foreign_1"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.foreign_1' "
                    "clashes with field name 'invalid_models_tests.Target.id'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.id', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.foreign_1'."
                    ),
                    obj=Model._meta.get_field("foreign_1"),
                    id="fields.E303",
                ),
                Error(
                    "Reverse accessor 'Target.id' for "
                    "'invalid_models_tests.Model.foreign_1' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.m2m_1'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.foreign_1' or "
                        "'invalid_models_tests.Model.m2m_1'."
                    ),
                    obj=Model._meta.get_field("foreign_1"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.foreign_1' "
                    "clashes with reverse query name for "
                    "'invalid_models_tests.Model.m2m_1'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.foreign_1' or "
                        "'invalid_models_tests.Model.m2m_1'."
                    ),
                    obj=Model._meta.get_field("foreign_1"),
                    id="fields.E305",
                ),
                Error(
                    "Reverse accessor 'Target.src_safe' for "
                    "'invalid_models_tests.Model.foreign_2' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.m2m_2'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.foreign_2' or "
                        "'invalid_models_tests.Model.m2m_2'."
                    ),
                    obj=Model._meta.get_field("foreign_2"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.foreign_2' "
                    "clashes with reverse query name for "
                    "'invalid_models_tests.Model.m2m_2'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.foreign_2' or "
                        "'invalid_models_tests.Model.m2m_2'."
                    ),
                    obj=Model._meta.get_field("foreign_2"),
                    id="fields.E305",
                ),
                Error(
                    "Reverse accessor 'Target.id' for "
                    "'invalid_models_tests.Model.m2m_1' clashes with field name "
                    "'invalid_models_tests.Target.id'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.id', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.m2m_1'."
                    ),
                    obj=Model._meta.get_field("m2m_1"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.m2m_1' "
                    "clashes with field name 'invalid_models_tests.Target.id'.",
                    hint=(
                        "Rename field 'invalid_models_tests.Target.id', or "
                        "add/change a related_name argument to the definition for "
                        "field 'invalid_models_tests.Model.m2m_1'."
                    ),
                    obj=Model._meta.get_field("m2m_1"),
                    id="fields.E303",
                ),
                Error(
                    "Reverse accessor 'Target.id' for "
                    "'invalid_models_tests.Model.m2m_1' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.foreign_1'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.m2m_1' or "
                        "'invalid_models_tests.Model.foreign_1'."
                    ),
                    obj=Model._meta.get_field("m2m_1"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.m2m_1' "
                    "clashes with reverse query name for "
                    "'invalid_models_tests.Model.foreign_1'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.m2m_1' or "
                        "'invalid_models_tests.Model.foreign_1'."
                    ),
                    obj=Model._meta.get_field("m2m_1"),
                    id="fields.E305",
                ),
                Error(
                    "Reverse accessor 'Target.src_safe' for "
                    "'invalid_models_tests.Model.m2m_2' clashes with reverse "
                    "accessor for 'invalid_models_tests.Model.foreign_2'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.m2m_2' or "
                        "'invalid_models_tests.Model.foreign_2'."
                    ),
                    obj=Model._meta.get_field("m2m_2"),
                    id="fields.E304",
                ),
                Error(
                    "Reverse query name for 'invalid_models_tests.Model.m2m_2' "
                    "clashes with reverse query name for "
                    "'invalid_models_tests.Model.foreign_2'.",
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Model.m2m_2' or "
                        "'invalid_models_tests.Model.foreign_2'."
                    ),
                    obj=Model._meta.get_field("m2m_2"),
                    id="fields.E305",
                ),
            ],
        )

    def test_clash_parent_link(self):
        """
        Tests that a model's reverse accessor names do not clash with other fields or the primary key.
        """
        class Parent(models.Model):
            pass

        class Child(Parent):
            other_parent = models.OneToOneField(Parent, models.CASCADE)

        errors = [
            (
                "fields.E304",
                "accessor",
                " 'Parent.child'",
                "parent_ptr",
                "other_parent",
            ),
            ("fields.E305", "query name", "", "parent_ptr", "other_parent"),
            (
                "fields.E304",
                "accessor",
                " 'Parent.child'",
                "other_parent",
                "parent_ptr",
            ),
            ("fields.E305", "query name", "", "other_parent", "parent_ptr"),
        ]
        self.assertEqual(
            Child.check(),
            [
                Error(
                    "Reverse %s%s for 'invalid_models_tests.Child.%s' clashes with "
                    "reverse %s for 'invalid_models_tests.Child.%s'."
                    % (attr, rel_name, field_name, attr, clash_name),
                    hint=(
                        "Add or change a related_name argument to the definition "
                        "for 'invalid_models_tests.Child.%s' or "
                        "'invalid_models_tests.Child.%s'." % (field_name, clash_name)
                    ),
                    obj=Child._meta.get_field(field_name),
                    id=error_id,
                )
                for error_id, attr, rel_name, field_name, clash_name in errors
            ],
        )


@isolate_apps("invalid_models_tests")
class M2mThroughFieldsTests(SimpleTestCase):
    def test_m2m_field_argument_validation(self):
        """
        ManyToManyField accepts the ``through_fields`` kwarg
        only if an intermediary table is specified.
        """

        class Fan(models.Model):
            pass

        with self.assertRaisesMessage(
            ValueError, "Cannot specify through_fields without a through model"
        ):
            models.ManyToManyField(Fan, through_fields=("f1", "f2"))

    def test_invalid_order(self):
        """
        Mixing up the order of link fields to ManyToManyField.through_fields
        triggers validation errors.
        """

        class Fan(models.Model):
            pass

        class Event(models.Model):
            invitees = models.ManyToManyField(
                Fan, through="Invitation", through_fields=("invitee", "event")
            )

        class Invitation(models.Model):
            event = models.ForeignKey(Event, models.CASCADE)
            invitee = models.ForeignKey(Fan, models.CASCADE)
            inviter = models.ForeignKey(Fan, models.CASCADE, related_name="+")

        field = Event._meta.get_field("invitees")
        self.assertEqual(
            field.check(from_model=Event),
            [
                Error(
                    "'Invitation.invitee' is not a foreign key to 'Event'.",
                    hint=(
                        "Did you mean one of the following foreign keys to 'Event': "
                        "event?"
                    ),
                    obj=field,
                    id="fields.E339",
                ),
                Error(
                    "'Invitation.event' is not a foreign key to 'Fan'.",
                    hint=(
                        "Did you mean one of the following foreign keys to 'Fan': "
                        "invitee, inviter?"
                    ),
                    obj=field,
                    id="fields.E339",
                ),
            ],
        )

    def test_invalid_field(self):
        """
        Providing invalid field names to ManyToManyField.through_fields
        triggers validation errors.
        """

        class Fan(models.Model):
            pass

        class Event(models.Model):
            invitees = models.ManyToManyField(
                Fan,
                through="Invitation",
                through_fields=("invalid_field_1", "invalid_field_2"),
            )

        class Invitation(models.Model):
            event = models.ForeignKey(Event, models.CASCADE)
            invitee = models.ForeignKey(Fan, models.CASCADE)
            inviter = models.ForeignKey(Fan, models.CASCADE, related_name="+")

        field = Event._meta.get_field("invitees")
        self.assertEqual(
            field.check(from_model=Event),
            [
                Error(
                    "The intermediary model 'invalid_models_tests.Invitation' has no "
                    "field 'invalid_field_1'.",
                    hint=(
                        "Did you mean one of the following foreign keys to 'Event': "
                        "event?"
                    ),
                    obj=field,
                    id="fields.E338",
                ),
                Error(
                    "The intermediary model 'invalid_models_tests.Invitation' has no "
                    "field 'invalid_field_2'.",
                    hint=(
                        "Did you mean one of the following foreign keys to 'Fan': "
                        "invitee, inviter?"
                    ),
                    obj=field,
                    id="fields.E338",
                ),
            ],
        )

    def test_explicit_field_names(self):
        """
        If ``through_fields`` kwarg is given, it must specify both
        link fields of the intermediary table.
        """

        class Fan(models.Model):
            pass

        class Event(models.Model):
            invitees = models.ManyToManyField(
                Fan, through="Invitation", through_fields=(None, "invitee")
            )

        class Invitation(models.Model):
            event = models.ForeignKey(Event, models.CASCADE)
            invitee = models.ForeignKey(Fan, models.CASCADE)
            inviter = models.ForeignKey(Fan, models.CASCADE, related_name="+")

        field = Event._meta.get_field("invitees")
        self.assertEqual(
            field.check(from_model=Event),
            [
                Error(
                    "Field specifies 'through_fields' but does not provide the names "
                    "of the two link fields that should be used for the relation "
                    "through model 'invalid_models_tests.Invitation'.",
                    hint=(
                        "Make sure you specify 'through_fields' as "
                        "through_fields=('field1', 'field2')"
                    ),
                    obj=field,
                    id="fields.E337",
                ),
            ],
        )

    def test_superset_foreign_object(self):
        """
        Tests that a ForeignObject field without a superset of its parents unique_together constraint correctly reports a validation error.
        """
        class Parent(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            c = models.PositiveIntegerField()

            class Meta:
                unique_together = (("a", "b", "c"),)

        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            value = models.CharField(max_length=255)
            parent = models.ForeignObject(
                Parent,
                on_delete=models.SET_NULL,
                from_fields=("a", "b"),
                to_fields=("a", "b"),
                related_name="children",
            )

        field = Child._meta.get_field("parent")
        self.assertEqual(
            field.check(from_model=Child),
            [
                Error(
                    "No subset of the fields 'a', 'b' on model 'Parent' is unique.",
                    hint=(
                        "Mark a single field as unique=True or add a set of "
                        "fields to a unique constraint (via unique_together or a "
                        "UniqueConstraint (without condition) in the model "
                        "Meta.constraints)."
                    ),
                    obj=field,
                    id="fields.E310",
                ),
            ],
        )

    def test_intersection_foreign_object(self):
        """
        Tests that Django's ForeignObject field validation correctly identifies a missing unique constraint on the related model when establishing a foreign key relationship with a non-unique subset of fields on the target model.
        """
        class Parent(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            c = models.PositiveIntegerField()
            d = models.PositiveIntegerField()

            class Meta:
                unique_together = (("a", "b", "c"),)

        class Child(models.Model):
            a = models.PositiveIntegerField()
            b = models.PositiveIntegerField()
            d = models.PositiveIntegerField()
            value = models.CharField(max_length=255)
            parent = models.ForeignObject(
                Parent,
                on_delete=models.SET_NULL,
                from_fields=("a", "b", "d"),
                to_fields=("a", "b", "d"),
                related_name="children",
            )

        field = Child._meta.get_field("parent")
        self.assertEqual(
            field.check(from_model=Child),
            [
                Error(
                    "No subset of the fields 'a', 'b', 'd' on model 'Parent' is "
                    "unique.",
                    hint=(
                        "Mark a single field as unique=True or add a set of "
                        "fields to a unique constraint (via unique_together or a "
                        "UniqueConstraint (without condition) in the model "
                        "Meta.constraints)."
                    ),
                    obj=field,
                    id="fields.E310",
                ),
            ],
        )
