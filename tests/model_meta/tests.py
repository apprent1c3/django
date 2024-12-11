from django.apps import apps
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.core.exceptions import FieldDoesNotExist
from django.db.models import CharField, Field, ForeignObjectRel, ManyToManyField
from django.db.models.options import EMPTY_RELATION_TREE, IMMUTABLE_WARNING
from django.test import SimpleTestCase, override_settings

from .models import (
    AbstractPerson,
    BasePerson,
    Child,
    CommonAncestor,
    FirstParent,
    Person,
    ProxyPerson,
    Relating,
    Relation,
    SecondParent,
    Swappable,
)
from .results import TEST_RESULTS


class OptionsBaseTests(SimpleTestCase):
    def _map_related_query_names(self, res):
        return tuple((o.name, m) for o, m in res)

    def _map_names(self, res):
        return tuple((f.name, m) for f, m in res)

    def _model(self, current_model, field):
        model = field.model._meta.concrete_model
        return None if model == current_model else model

    def _details(self, current_model, relation):
        """
        Returns detailed information about a model relation.

        This method analyzes the given relation and the current model, providing insights into the relationship's nature and structure.
        It determines whether the relation is direct or indirect, the associated model (if any), and the type of field involved.
        The method returns a tuple containing the relation itself, the related model (or None if it's the current model), a boolean indicating directness, and another boolean indicating whether the field is a many-to-many field.
        """
        direct = isinstance(relation, (Field, GenericForeignKey))
        model = relation.model._meta.concrete_model
        if model == current_model:
            model = None

        field = relation if direct else relation.field
        return (
            relation,
            model,
            direct,
            bool(field.many_to_many),
        )  # many_to_many can be None


class GetFieldsTests(OptionsBaseTests):
    def test_get_fields_is_immutable(self):
        """
        Tests that the get_fields() method of the Person model's meta class returns an immutable sequence, by verifying that attempting to modify its result raises an AttributeError with the expected warning message.
        """
        msg = IMMUTABLE_WARNING % "get_fields()"
        for _ in range(2):
            # Running unit test twice to ensure both non-cached and cached result
            # are immutable.
            fields = Person._meta.get_fields()
            with self.assertRaisesMessage(AttributeError, msg):
                fields += ["errors"]


class LabelTests(OptionsBaseTests):
    def test_label(self):
        for model, expected_result in TEST_RESULTS["labels"].items():
            self.assertEqual(model._meta.label, expected_result)

    def test_label_lower(self):
        for model, expected_result in TEST_RESULTS["lower_labels"].items():
            self.assertEqual(model._meta.label_lower, expected_result)


class DataTests(OptionsBaseTests):
    def test_fields(self):
        """
        Tests that the fields defined in the model match the expected results.

        Currently, it iterates over a set of predefined test models and their corresponding expected field results. For each model, it retrieves the actual fields and compares their attribute names against the expected outcome, ensuring that the field definitions are correctly implemented. This validation is crucial to guarantee the consistency and accuracy of the model's structure.
        """
        for model, expected_result in TEST_RESULTS["fields"].items():
            fields = model._meta.fields
            self.assertEqual([f.attname for f in fields], expected_result)

    def test_local_fields(self):
        def is_data_field(f):
            return isinstance(f, Field) and not f.many_to_many

        for model, expected_result in TEST_RESULTS["local_fields"].items():
            fields = model._meta.local_fields
            self.assertEqual([f.attname for f in fields], expected_result)
            for f in fields:
                self.assertEqual(f.model, model)
                self.assertTrue(is_data_field(f))

    def test_local_concrete_fields(self):
        """
        Tests that local concrete fields for a model are correctly identified.

        This test iterates over a set of predefined test results, comparing the actual
        local concrete fields for each model against the expected results. It verifies
        that the field names of the local concrete fields match the expected field names,
        and that each field has a non-null column attribute.

        The purpose of this test is to ensure that the local concrete fields are properly
        detected and configured for each model, which is essential for maintaining data
        integrity and consistency in the database.

        :param None
        :returns: None
        :raises: AssertionError if the local concrete fields do not match the expected results
        """
        for model, expected_result in TEST_RESULTS["local_concrete_fields"].items():
            fields = model._meta.local_concrete_fields
            self.assertEqual([f.attname for f in fields], expected_result)
            for f in fields:
                self.assertIsNotNone(f.column)


class M2MTests(OptionsBaseTests):
    def test_many_to_many(self):
        """
        Tests the many-to-many fields in a model by comparing the actual field names with the expected results. 

        The function iterates over a set of predefined test models and their respective expected results. For each model, it retrieves the many-to-many fields and checks if their names match the expected values. Additionally, it verifies that each many-to-many field is correctly configured as a relation.
        """
        for model, expected_result in TEST_RESULTS["many_to_many"].items():
            fields = model._meta.many_to_many
            self.assertEqual([f.attname for f in fields], expected_result)
            for f in fields:
                self.assertTrue(f.many_to_many and f.is_relation)

    def test_many_to_many_with_model(self):
        for model, expected_result in TEST_RESULTS["many_to_many_with_model"].items():
            models = [self._model(model, field) for field in model._meta.many_to_many]
            self.assertEqual(models, expected_result)


class RelatedObjectsTests(OptionsBaseTests):
    def key_name(self, r):
        return r[0]

    def test_related_objects(self):
        result_key = "get_all_related_objects_with_model"
        for model, expected in TEST_RESULTS[result_key].items():
            objects = [
                (field, self._model(model, field))
                for field in model._meta.get_fields()
                if field.auto_created and not field.concrete
            ]
            self.assertEqual(
                sorted(self._map_related_query_names(objects), key=self.key_name),
                sorted(expected, key=self.key_name),
            )

    def test_related_objects_local(self):
        result_key = "get_all_related_objects_with_model_local"
        for model, expected in TEST_RESULTS[result_key].items():
            objects = [
                (field, self._model(model, field))
                for field in model._meta.get_fields(include_parents=False)
                if field.auto_created and not field.concrete
            ]
            self.assertEqual(
                sorted(self._map_related_query_names(objects), key=self.key_name),
                sorted(expected, key=self.key_name),
            )

    def test_related_objects_include_hidden(self):
        """

        Tests that the related objects of a model include hidden fields.

        This test case verifies that when retrieving all related objects for a given model, 
        the results include hidden fields that are auto-created and non-concrete. 
        The test iterates over a set of predefined test results and compares the 
        expected output with the actual related objects retrieved from the model.

        """
        result_key = "get_all_related_objects_with_model_hidden"
        for model, expected in TEST_RESULTS[result_key].items():
            objects = [
                (field, self._model(model, field))
                for field in model._meta.get_fields(include_hidden=True)
                if field.auto_created and not field.concrete
            ]
            self.assertEqual(
                sorted(self._map_names(objects), key=self.key_name),
                sorted(expected, key=self.key_name),
            )

    def test_related_objects_include_hidden_local_only(self):
        result_key = "get_all_related_objects_with_model_hidden_local"
        for model, expected in TEST_RESULTS[result_key].items():
            objects = [
                (field, self._model(model, field))
                for field in model._meta.get_fields(
                    include_hidden=True, include_parents=False
                )
                if field.auto_created and not field.concrete
            ]
            self.assertEqual(
                sorted(self._map_names(objects), key=self.key_name),
                sorted(expected, key=self.key_name),
            )


class PrivateFieldsTests(OptionsBaseTests):
    def test_private_fields(self):
        """
        Tests that the private fields of a model are correctly identified.

        Verifies that the private fields of each model match the expected names.
        The function iterates over a set of test results, comparing the actual private
        fields of each model with the expected field names. It asserts that the two sets
        of field names are equal, ensuring that the private fields are correctly defined
        and identified.

        This test is used to validate the accuracy of the model's metadata and ensure
        that the private fields are properly handled. The test results are predefined in
        the TEST_RESULTS dictionary, which maps each model to its expected private field
        names. 

        :param None
        :raises AssertionError: if the actual private fields do not match the expected
            field names for any model.
        :return: None
        """
        for model, expected_names in TEST_RESULTS["private_fields"].items():
            objects = model._meta.private_fields
            self.assertEqual(sorted(f.name for f in objects), sorted(expected_names))


class GetFieldByNameTests(OptionsBaseTests):
    def test_get_data_field(self):
        """

        Tests the retrieval of field information for the 'data_abstract' field in the Person model.

        Verifies that the field type is a CharField and checks the associated metadata, 
        including the base person type and permission settings for reading and writing.

        """
        field_info = self._details(Person, Person._meta.get_field("data_abstract"))
        self.assertEqual(field_info[1:], (BasePerson, True, False))
        self.assertIsInstance(field_info[0], CharField)

    def test_get_m2m_field(self):
        """

        Tests the retrieval of a many-to-many field from a model.

        Verifies that the correct field information is returned, including the field type,
        related model, and whether the field is auto-created and symmetrical.

        """
        field_info = self._details(Person, Person._meta.get_field("m2m_base"))
        self.assertEqual(field_info[1:], (BasePerson, True, True))
        self.assertIsInstance(field_info[0], ManyToManyField)

    def test_get_related_object(self):
        """
        Tests the retrieval of related object information for a given model field.

        Verifies that the field information returned contains the expected related model,
        and that the field's properties (e.g. whether it's a many-to-one relationship)
        match the expected values.

        Specifically, this test case checks the 'relating_baseperson' field of the Person model,
        confirming that it is associated with the BasePerson model and does not have certain flags set.
        """
        field_info = self._details(
            Person, Person._meta.get_field("relating_baseperson")
        )
        self.assertEqual(field_info[1:], (BasePerson, False, False))
        self.assertIsInstance(field_info[0], ForeignObjectRel)

    def test_get_related_m2m(self):
        """
        Tests the retrieval of related Many-To-Many fields.

        This test case verifies that the function correctly returns information about 
        a Many-To-Many relationship, specifically the 'relating_people' field of the 
        Person model. It checks that the field information matches the expected 
        values, including the relationship type and its attributes, and that the 
        related object type is correctly identified as a ForeignObjectRel instance.
        """
        field_info = self._details(Person, Person._meta.get_field("relating_people"))
        self.assertEqual(field_info[1:], (None, False, True))
        self.assertIsInstance(field_info[0], ForeignObjectRel)

    def test_get_generic_relation(self):
        field_info = self._details(
            Person, Person._meta.get_field("generic_relation_base")
        )
        self.assertEqual(field_info[1:], (None, True, False))
        self.assertIsInstance(field_info[0], GenericRelation)

    def test_get_fields_only_searches_forward_on_apps_not_ready(self):
        opts = Person._meta
        # If apps registry is not ready, get_field() searches over only
        # forward fields.
        opts.apps.models_ready = False
        try:
            # 'data_abstract' is a forward field, and therefore will be found
            self.assertTrue(opts.get_field("data_abstract"))
            msg = (
                "Person has no field named 'relating_baseperson'. The app "
                "cache isn't ready yet, so if this is an auto-created related "
                "field, it won't be available yet."
            )
            # 'data_abstract' is a reverse field, and will raise an exception
            with self.assertRaisesMessage(FieldDoesNotExist, msg):
                opts.get_field("relating_baseperson")
        finally:
            opts.apps.models_ready = True


class VerboseNameRawTests(SimpleTestCase):
    def test_string(self):
        # Clear cached property.
        """

        Tests the verbose name raw attribute of the Relation model.

        Verifies that the verbose name raw attribute is correctly set to 'relation'.
        This ensures that the model's verbose name is properly defined and can be used
        for display purposes in the application.

        """
        Relation._meta.__dict__.pop("verbose_name_raw", None)
        self.assertEqual(Relation._meta.verbose_name_raw, "relation")

    def test_gettext(self):
        """
        Tests that the verbose_name_raw attribute of the Person model is correctly set to 'Person' after removing any existing value from the model's metadata
        """
        Person._meta.__dict__.pop("verbose_name_raw", None)
        self.assertEqual(Person._meta.verbose_name_raw, "Person")


class SwappedTests(SimpleTestCase):
    def test_plain_model_none(self):
        self.assertIsNone(Relation._meta.swapped)

    def test_unset(self):
        self.assertIsNone(Swappable._meta.swapped)

    def test_set_and_unset(self):
        """

        Tests the swapping of Swappable model metadata.

        This test case verifies that the Swappable model's metadata can be swapped 
        with a different model (in this case, 'model_meta.Relation') and then 
        reverted back to its original state.

        It checks that the 'swapped' attribute of the Swappable model's metadata 
        is correctly set and unset during the swapping process.

        """
        with override_settings(MODEL_META_TESTS_SWAPPED="model_meta.Relation"):
            self.assertEqual(Swappable._meta.swapped, "model_meta.Relation")
        self.assertIsNone(Swappable._meta.swapped)

    def test_setting_none(self):
        """

        Tests that setting the MODEL_META_TESTS_SWAPPED setting to None correctly 
        sets the swapped attribute of the Swappable meta class to None.

        """
        with override_settings(MODEL_META_TESTS_SWAPPED=None):
            self.assertIsNone(Swappable._meta.swapped)

    def test_setting_non_label(self):
        with override_settings(MODEL_META_TESTS_SWAPPED="not-a-label"):
            self.assertEqual(Swappable._meta.swapped, "not-a-label")

    def test_setting_self(self):
        with override_settings(MODEL_META_TESTS_SWAPPED="model_meta.swappable"):
            self.assertIsNone(Swappable._meta.swapped)


class RelationTreeTests(SimpleTestCase):
    all_models = (Relation, AbstractPerson, BasePerson, Person, ProxyPerson, Relating)

    def setUp(self):
        apps.clear_cache()

    def test_clear_cache_clears_relation_tree(self):
        # The apps.clear_cache is setUp() should have deleted all trees.
        # Exclude abstract models that are not included in the Apps registry
        # and have no cache.
        """

        Tests that clearing the cache correctly removes the relation tree from all non-abstract models.

        This ensures that the cache is properly reset, which is crucial for maintaining data consistency and preventing stale data from being used.
        The test verifies that the '_relation_tree' attribute is removed from the meta dictionary of each model after the cache is cleared.

        """
        all_models_with_cache = (m for m in self.all_models if not m._meta.abstract)
        for m in all_models_with_cache:
            self.assertNotIn("_relation_tree", m._meta.__dict__)

    def test_first_relation_tree_access_populates_all(self):
        # On first access, relation tree should have populated cache.
        """

        Verifies that the relation tree is correctly populated for the first model.

        Tests that the relation tree attribute exists and is initialized for all models,
        excluding the AbstractPerson model which does not have relations. The test also
        confirms that the AbstractPerson model has an empty relation tree.

        This test case ensures that the _relation_tree attribute is successfully set up 
        for all applicable models during the initialization process, providing a 
        foundation for further relation-based operations.

        """
        self.assertTrue(self.all_models[0]._meta._relation_tree)

        # AbstractPerson does not have any relations, so relation_tree
        # should just return an EMPTY_RELATION_TREE.
        self.assertEqual(AbstractPerson._meta._relation_tree, EMPTY_RELATION_TREE)

        # All the other models should already have their relation tree
        # in the internal __dict__ .
        all_models_but_abstractperson = (
            m for m in self.all_models if m is not AbstractPerson
        )
        for m in all_models_but_abstractperson:
            self.assertIn("_relation_tree", m._meta.__dict__)

    def test_relations_related_objects(self):
        # Testing non hidden related objects
        """
        Tests the correct configuration of related objects for various model relations.

        This test method verifies that the relation tree for the Relation, BasePerson, and AbstractPerson models contain the expected related query names. It checks that the related query names for each model match the expected values, ensuring that the relationships between models are properly established.

        The test covers different types of relationships, including foreign keys and many-to-many fields, and verifies that the related query names are correctly generated for each type of relationship. The test also checks that hidden fields are correctly excluded from the relation tree.
        """
        self.assertEqual(
            sorted(
                field.related_query_name()
                for field in Relation._meta._relation_tree
                if not field.remote_field.field.remote_field.hidden
            ),
            sorted(
                [
                    "fk_abstract_rel",
                    "fk_base_rel",
                    "fk_concrete_rel",
                    "fo_abstract_rel",
                    "fo_base_rel",
                    "fo_concrete_rel",
                    "m2m_abstract_rel",
                    "m2m_base_rel",
                    "m2m_concrete_rel",
                ]
            ),
        )
        # Testing hidden related objects
        self.assertEqual(
            sorted(
                field.related_query_name() for field in BasePerson._meta._relation_tree
            ),
            sorted(
                [
                    "+",
                    "_model_meta_relating_basepeople_hidden_+",
                    "BasePerson_following_abstract+",
                    "BasePerson_following_abstract+",
                    "BasePerson_following_base+",
                    "BasePerson_following_base+",
                    "BasePerson_friends_abstract+",
                    "BasePerson_friends_abstract+",
                    "BasePerson_friends_base+",
                    "BasePerson_friends_base+",
                    "BasePerson_m2m_abstract+",
                    "BasePerson_m2m_base+",
                    "Relating_basepeople+",
                    "Relating_basepeople_hidden+",
                    "followers_abstract",
                    "followers_base",
                    "friends_abstract_rel_+",
                    "friends_base_rel_+",
                    "person",
                    "relating_basepeople",
                    "relating_baseperson",
                ]
            ),
        )
        self.assertEqual(
            [
                field.related_query_name()
                for field in AbstractPerson._meta._relation_tree
            ],
            [],
        )


class AllParentsTests(SimpleTestCase):
    def test_all_parents(self):
        """
        Tests that the all_parents attribute of the model meta class is correctly populated for each model in the inheritance hierarchy. 
        This includes models that inherit directly and indirectly, verifying that all parent models are properly accounted for in the all_parents tuple.
        """
        self.assertEqual(CommonAncestor._meta.all_parents, ())
        self.assertEqual(FirstParent._meta.all_parents, (CommonAncestor,))
        self.assertEqual(SecondParent._meta.all_parents, (CommonAncestor,))
        self.assertEqual(
            Child._meta.all_parents,
            (FirstParent, SecondParent, CommonAncestor),
        )

    def test_get_parent_list(self):
        self.assertEqual(Child._meta.get_parent_list(), list(Child._meta.all_parents))


class PropertyNamesTests(SimpleTestCase):
    def test_person(self):
        # Instance only descriptors don't appear in _property_names.
        """
        Tests behavior of instance-only descriptor and abstract model meta properties.

        Verifies that the instance-only descriptor can be accessed on instances of BasePerson,
        but raises an AttributeError when accessed on the AbstractPerson class itself.
        Additionally, checks that the AbstractPerson meta properties contain the expected attributes.
        """
        self.assertEqual(BasePerson().test_instance_only_descriptor, 1)
        with self.assertRaisesMessage(AttributeError, "Instance only"):
            AbstractPerson.test_instance_only_descriptor
        self.assertEqual(
            AbstractPerson._meta._property_names, frozenset(["pk", "test_property"])
        )


class ReturningFieldsTests(SimpleTestCase):
    def test_pk(self):
        self.assertEqual(Relation._meta.db_returning_fields, [Relation._meta.pk])


class AbstractModelTests(SimpleTestCase):
    def test_abstract_model_not_instantiated(self):
        """

        Tests that attempting to instantiate an abstract model raises a TypeError.

        Verifies that the AbstractPerson model, which is defined as an abstract base class, 
        cannot be directly instantiated as an object. This ensures that users must create 
        concrete subclasses of AbstractPerson in order to create instances.

        """
        msg = "Abstract models cannot be instantiated."
        with self.assertRaisesMessage(TypeError, msg):
            AbstractPerson()
