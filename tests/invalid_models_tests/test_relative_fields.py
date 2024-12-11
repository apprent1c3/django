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

        Tests that a valid foreign key without an accessor does not raise any errors.

        A foreign key is considered valid if it properly references the target model and
        has the correct settings. In this case, the foreign key references the Target model
        and uses the CASCADE action for on delete operations. The related name is set to '+'
        which indicates that the reverse relationship should not be created.

        The test checks that calling the check method on the field does not return any errors,
        indicating that the foreign key is correctly configured.

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
        Tests that the model ManyToManyField validation correctly identifies and warns about 
        useless options such as null, validators, and db_comment. Verifies that the function 
        issues the expected warnings when these options are specified for a ManyToManyField 
        in a model, as they do not apply to ManyToManyFields and are thus ignored by Django.
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

        Tests the behavior of a ManyToManyField with an ambiguous relationship model.

        This test case covers a scenario where a ManyToManyField is defined with a through model
        that has multiple foreign keys to the same model, causing ambiguity in the relationship.
        The test verifies that Django correctly raises an error when checking the field,
        indicating that the through_fields keyword argument is required to resolve the ambiguity.

        The test covers the following:
        - Definition of a ManyToManyField with an ambiguous through model
        - Verification of the error raised by Django when checking the field
        - The required use of the through_fields keyword argument to resolve the ambiguity

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

        Tests the validation of a ManyToManyField in a model where the intermediate model is missing a foreign key to one of the related models.

        Verifies that the model validation correctly identifies and reports the error when the intermediate model does not have foreign keys to both the source and target models of the ManyToManyField relationship.

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

        Tests that a ManyToManyField with a 'through' model that has not been installed correctly reports an error.

        This test case checks for the specific situation where a ManyToManyField 
        is defined with a 'through' model that does not exist or has not been 
        installed in the project. The test verifies that the field validation 
        correctly identifies this issue and raises an appropriate error message.

        The error is identified as a field error with the id 'fields.E331', 
        indicating that the specified many-to-many relation through model 
        could not be found among the installed models.

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
        Tests that a model check fails with an error when a many-to-many relationship is defined through a model that does not exist, i.e., the model specified in the \"through\" parameter of a ManyToManyField has not been installed. The error is raised to prevent potential issues that could arise from referencing a non-existent model in a many-to-many relationship. Verifies that the model check correctly identifies this problem and raises an appropriate error message.
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

        Tests that a self-referential ManyToManyField with an intermediary model fails validation when the intermediary model has more than two foreign keys to the self-referential model.

        This test case addresses the situation where the intermediary model in a self-referential ManyToManyField relationship has more foreign keys than expected, leading to ambiguity in establishing the relationship.

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

        Check that foreign keys referencing abstract models raise expected errors.

        This test ensures that when a model defines a foreign key to an abstract model,
        either by a string reference or by directly referencing the model class,
        the correct error is raised during field validation.

        The error is expected because abstract models cannot be instantiated and therefore
        cannot be used as targets for foreign key relationships.

        The test verifies that the error message is correctly generated for both types
        of foreign key definitions and that the error object is properly associated
        with the respective field.

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

        Tests Many-To-Many fields referencing an abstract model.

        Checks that a Many-To-Many relationship defined with either a string reference or a class reference to an abstract model raises the expected error.
        The error occurs because the abstract model cannot be used as a target for the relationship.

         verify that the :class:`~django.db.models.Field.check` method correctly identifies and reports the issue when checking the model's fields.

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

        Tests that a ManyToManyField with unique=True raises the appropriate validation error.

        This test case ensures that when a ManyToManyField is defined with the unique constraint,
        it correctly triggers a validation error, as ManyToManyFields cannot enforce uniqueness.

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
        Tests that creating a foreign key to a non-unique field in a model raises an error.

        This function checks that the Django model validation correctly identifies and reports
        a foreign key referencing a non-unique field in another model, as this can cause
        referential integrity issues. It verifies that the expected error message is raised,
        indicating that the referenced field should be unique or have a unique constraint
        defined in the model's Meta.constraints.

        The test scenario involves creating a foreign key in a model that points to a non-unique
        integer field in a target model. The function then checks the validation result of the
        foreign key field to ensure that it correctly reports the expected error. This ensures
        that the framework prevents potentially problematic database schema configurations
        that could lead to data inconsistencies or other issues. 
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

        Tests that a foreign key to a partially unique field raises an error.

        This test case verifies that a foreign key referencing a field that is not
        uniquely constrained for all rows in the target model raises a warning.
        In this scenario, the target model has a unique constraint on the referenced
        field, but this constraint only applies to a subset of rows, making it
        partially unique. The test checks that the foreign key field correctly reports
        this issue, providing a hint for resolution by either adding a unique constraint
        without conditions or setting unique=True on the referenced field.

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
        Tests that a foreign key referencing a unique field in another model, 
        which has a unique constraint defined in its Meta class, passes validation checks.

        Verifies that the foreign key relationship is correctly established and does not 
        report any errors when validating the field, ensuring data integrity and 
        consistency across related models.
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
        Tests that setting on_delete to SET_NULL on a non-nullable field raises an error, 
        as the field cannot be set to null when the referenced object is deleted. 
        This ensures that model fields are properly configured to handle deletions of related objects.
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
        Tests that a ForeignKey field with on_delete set to SET_DEFAULT raises an error if no default value is provided.

        The test verifies that the check method of the field returns an error when the on_delete rule is set to SET_DEFAULT but the field does not have a default value defined, as required by this rule. The test case ensures that the error message provides guidance on how to resolve the issue, either by setting a default value or changing the on_delete rule.
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

        Tests that a swappable model is not swapped when creating explicit and implicit foreign key and many-to-many fields.

        This test case covers the scenario where a swappable model is defined with the 'swappable' Meta option.
        It verifies that the model's fields are correctly validated when the swappable model is not swapped,
        ensuring that the fields' checks pass without errors.

        The test checks both explicit and implicit foreign key and many-to-many fields for proper validation.

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
        Tests that foreign key and many-to-many fields referencing a swappable model 
        raise an error when the model is swapped out.

        Verifies that both explicit and implicit field definitions correctly detect 
        when the referenced model has been swapped and returns the expected error 
        message with a hint to update the relation to point at the swapped model 
        defined in the settings.

        This test covers four cases: explicit foreign key, implicit foreign key, 
        explicit many-to-many field, and implicit many-to-many field. All cases 
        should raise a 'fields.E301' error with a hint to update the relation 
        when the referenced model is swapped out.
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
        Tests that related fields have valid related names.

        Checks that the related name for a foreign key field conforms to the required format.
        A related name must be a valid Python identifier or end with a '+' to avoid potential name clashes.
        Verifies that the model validation correctly identifies and reports invalid related names,
        including those that start or end with whitespace, digits, or special characters, or contain
        illegal characters. Ensures that the error message accurately describes the problem and provides a hint
        for correcting the issue. 
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
        Checks that a related field on a model instance has a valid related name.

        The function tests a set of related names for validity, including names with 
        lowercase and uppercase letters, digits, underscores, special characters, and 
        non-ASCII characters. It creates a model with a foreign key to a parent model 
        and assigns each related name to the foreign key, checking that no validation 
        errors are raised. 

        Args:
            None

        Returns:
            None 

        Raises:
            AssertionError: If any of the related names cause validation errors.
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

        Checks the validation of a foreign key field with from_fields and to_fields parameters.

        This test verifies that the field validation correctly reports errors when the 
        to_fields specified in a ForeignObject do not exist on the related model.

        It tests the case where the related model does not have fields matching those 
        specified in the to_fields parameter, ensuring that the check method returns 
        the expected errors.

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

        Tests that the `check` method on a foreign key field does not check the `to_fields` attribute 
        if the related model does not exist. 

        This ensures that the validation does not fail when the target model of a foreign key 
        relationship is not installed or is an abstract model. 

        The test validates the error code 'fields.E300' is raised when checking the field, 
        indicating that the related model could not be found.

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

        Test that the validation of invalid related query names raises the correct errors.

        This test checks two specific cases:

        * A related query name that contains double underscore (__).
        * A related query name that ends with an underscore.

        It verifies that the Model's check method returns the expected Error instances for each case, providing hints for fixing the issues.

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
        Tests for accessor clash in model fields.

        Checks that a reverse accessor on the target model does not clash with a field name
        on the related model. This ensures that Django can properly resolve relationships
        between models without ambiguity.

        Args:
            target (models.Model): The target model being referenced.
            relative (models.Field): The field on the Model class that references the target.

        Raises:
            AssertionError: If the check does not report an accessor clash error when expected.

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
        Tests that Django models raise the correct error when a foreign key and a many-to-many field in the same model both attempt to create a reverse accessor with the same name on the target model.

        The test checks for the specific case where a `ForeignKey` and a `ManyToManyField` both reference the same target model without specifying a unique `related_name`. It verifies that the resulting error messages provide a clear hint on how to resolve the issue by adding or modifying the `related_name` argument for one of the fields.
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

        Test that using a hidden related name '+' in ManyToManyField and ForeignKey
        does not cause naming clashes.

        This test verifies that using the '+' symbol as the related_name in a model's
        ManyToManyField and ForeignKey does not result in any errors when checked.
        The test ensures that the check method of the models returns an empty list,
        indicating no issues or conflicts were found.

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
        class Target(models.Model):
            class Meta:
                app_label = "invalid_models_tests"

        class Model(models.Model):
            m2m = models.ManyToManyField(Target, related_name="+")

            class Meta:
                app_label = "basic"

        def _test():
            # Define model with the same name.
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
        Tests for explicit related query name clash error in Django models.

        This method checks that a FieldError is raised when the reverse query name for a related field in a model clashes with a field name in a target model. It verifies that the error message and hint provide useful information to resolve the clash, such as renaming the conflicting field or adding a related_name argument to the field definition.
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
        """
        Tests that Django model validation correctly identifies and reports clashes between reverse accessors for ManyToMany fields. 

        This test case creates a model with two ManyToMany fields pointing to the same model, which results in a naming conflict for the reverse accessors, and verifies that the validation system raises the appropriate errors with useful hints for resolving the issue.
        """
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
        """
        Tests that a ManyToManyField with an explicit related_name clashes with a field name when running model checks.

        Verifies that model validation correctly raises errors when a ManyToManyField's reverse accessor name (defined by the related_name parameter) conflicts with an existing field name on the model.

        In the case of a clash, two errors are expected: one for the reverse accessor clashing with the field name and another for the reverse query name clashing with the field name. Both errors suggest resolving the conflict by renaming the field or modifying the related_name argument of the ManyToManyField to avoid the naming collision.
        """
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
        """

        Tests that a model with multiple ManyToMany fields to itself is valid.

        The model under test contains two ManyToMany fields, 'first' and 'second', 
        both referencing the model itself. This test checks that the model's 
        validation method does not return any errors for this configuration.

        It verifies that Django's model validation correctly handles 
        self-referential ManyToMany relationships with different related names.

        """
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
        """

        Tests that Django model accessor clash is correctly handled.

        The accessor clash occurs when the related name of a model field clashes with the field name itself.
        This test case ensures that the model validation correctly identifies and reports this clash.

        The expected error message includes a hint for resolving the issue by renaming the field or adding/adjusting the related_name argument.

        """
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
        """
        Tests that the model validation correctly identifies and reports clashes between field names and reverse accessors when an explicit related name is provided.

        The test case checks that the `check` method raises errors when a field name conflicts with the related name of a ForeignKey field, and that the error messages provide helpful hints for resolving the issue. The test covers two specific error cases: one for the general field name clash (E302), and another for the reverse query name clash (E303).
        """
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
        Tests the handling of complex field name clashes in Django model relationships.

        In this test, we define two models, `Target` and `Model`, with various field types (CharField, ForeignKey, ManyToManyField) and relationship names that intentionally cause naming conflicts.

        The test checks that the `check` method of the `Model` class correctly identifies and reports all the clashes between field names, reverse accessors, and reverse query names. The expected output is a list of error messages, each with a hint on how to resolve the conflict by renaming a field or adding/changing a related_name argument. 

        This test case covers a range of scenarios, including:

        * Clashes between a field name and a reverse accessor
        * Clashes between two reverse accessors
        * Clashes between a field name and a reverse query name
        * Clashes between two reverse query names

        By testing these complex clashes, this function ensures that the model checking mechanism is robust and provides helpful feedback to developers when there are naming conflicts in their Django models.
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
        ``` 
        Tests the error handling for a OneToOneField clash in a child model where the parent model is inherited.

        Checks if the class 'Child' correctly identifies accessor and query name clashes 
        between the automatically created 'parent_ptr' field and the manually defined 'other_parent' field.

        Verifies that the `check` method of the 'Child' model returns the expected list of errors,
        each error containing information about the conflicting fields and a suggestion for a solution.
        ```
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
        Checks that a ForeignObject field correctly identifies its superset when linked to a model via multiple fields, and not all of those fields are marked as unique together on the model.
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

        Tests the intersection of a foreign object with a model that has a unique constraint.

        Verifies that Sphinx correctly raises an error when a foreign object references 
        multiple fields on a model that does not have a corresponding unique constraint 
        or set of unique fields.

        It checks that the error message includes the required information about the 
        model and fields involved, along with a hint for how to resolve the issue by 
        adding a unique constraint or unique field.

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
