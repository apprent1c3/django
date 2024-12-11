from django.core.exceptions import FieldError
from django.test import SimpleTestCase, TestCase

from .models import (
    Bookmark,
    Domain,
    Family,
    Genus,
    HybridSpecies,
    Kingdom,
    Klass,
    Order,
    Phylum,
    Pizza,
    Species,
    TaggedItem,
)


class SelectRelatedTests(TestCase):
    @classmethod
    def create_tree(cls, stringtree):
        """
        Helper to create a complete tree.
        """
        names = stringtree.split()
        models = [Domain, Kingdom, Phylum, Klass, Order, Family, Genus, Species]
        assert len(names) == len(models), (names, models)

        parent = None
        for name, model in zip(names, models):
            try:
                obj = model.objects.get(name=name)
            except model.DoesNotExist:
                obj = model(name=name)
            if parent:
                setattr(obj, parent.__class__.__name__.lower(), parent)
            obj.save()
            parent = obj

    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the class by creating a taxonomy tree for various organisms.

        This method creates a hierarchical structure for several species, including
        Drosophila melanogaster (fruit fly), Homo sapiens (human), Pisum sativum (pea),
        and Amanita muscaria (fly agaric mushroom), each with their respective kingdoms,
        phyla, classes, orders, families, and genera.

        """
        cls.create_tree(
            "Eukaryota Animalia Anthropoda Insecta Diptera Drosophilidae Drosophila "
            "melanogaster"
        )
        cls.create_tree(
            "Eukaryota Animalia Chordata Mammalia Primates Hominidae Homo sapiens"
        )
        cls.create_tree(
            "Eukaryota Plantae Magnoliophyta Magnoliopsida Fabales Fabaceae Pisum "
            "sativum"
        )
        cls.create_tree(
            "Eukaryota Fungi Basidiomycota Homobasidiomycatae Agaricales Amanitacae "
            "Amanita muscaria"
        )

    def test_access_fks_without_select_related(self):
        """
        Normally, accessing FKs doesn't fill in related objects
        """
        with self.assertNumQueries(8):
            fly = Species.objects.get(name="melanogaster")
            domain = fly.genus.family.order.klass.phylum.kingdom.domain
            self.assertEqual(domain.name, "Eukaryota")

    def test_access_fks_with_select_related(self):
        """
        A select_related() call will fill in those related objects without any
        extra queries
        """
        with self.assertNumQueries(1):
            person = Species.objects.select_related(
                "genus__family__order__klass__phylum__kingdom__domain"
            ).get(name="sapiens")
            domain = person.genus.family.order.klass.phylum.kingdom.domain
            self.assertEqual(domain.name, "Eukaryota")

    def test_list_without_select_related(self):
        """

        Tests the retrieval of related model instances from a queryset without using select_related.

        This test case verifies that the ORM issues the expected number of database queries when
        fetching related objects from a queryset. It retrieves a list of species, and then extracts
        the family names of the corresponding genera. The test asserts that the family names are
        as expected and that the query count is within the anticipated range.

        The expected query count of 9 reflects the initial query to retrieve the species, plus
        additional queries to fetch the related genus and family instances for each species.

        """
        with self.assertNumQueries(9):
            world = Species.objects.all()
            families = [o.genus.family.name for o in world]
            self.assertEqual(
                sorted(families),
                [
                    "Amanitacae",
                    "Drosophilidae",
                    "Fabaceae",
                    "Hominidae",
                ],
            )

    def test_list_with_select_related(self):
        """select_related() applies to entire lists, not just items."""
        with self.assertNumQueries(1):
            world = Species.objects.select_related()
            families = [o.genus.family.name for o in world]
            self.assertEqual(
                sorted(families),
                [
                    "Amanitacae",
                    "Drosophilidae",
                    "Fabaceae",
                    "Hominidae",
                ],
            )

    def test_list_with_depth(self):
        """
        Passing a relationship field lookup specifier to select_related() will
        stop the descent at a particular level. This can be used on lists as
        well.
        """
        with self.assertNumQueries(5):
            world = Species.objects.select_related("genus__family")
            orders = [o.genus.family.order.name for o in world]
            self.assertEqual(
                sorted(orders), ["Agaricales", "Diptera", "Fabales", "Primates"]
            )

    def test_select_related_with_extra(self):
        """

        Tests that the select_related queryset method functions correctly with extra select clauses.

        Verifies that extra select clauses are properly applied to the results of a select_related query,
        ensuring that the additional selected values are accurately calculated and returned in the query results.

        """
        s = (
            Species.objects.all()
            .select_related()
            .extra(select={"a": "select_related_species.id + 10"})[0]
        )
        self.assertEqual(s.id + 10, s.a)

    def test_certain_fields(self):
        """
        The optional fields passed to select_related() control which related
        models we pull in. This allows for smaller queries.

        In this case, we explicitly say to select the 'genus' and
        'genus.family' models, leading to the same number of queries as before.
        """
        with self.assertNumQueries(1):
            world = Species.objects.select_related("genus__family")
            families = [o.genus.family.name for o in world]
            self.assertEqual(
                sorted(families),
                ["Amanitacae", "Drosophilidae", "Fabaceae", "Hominidae"],
            )

    def test_more_certain_fields(self):
        """
        In this case, we explicitly say to select the 'genus' and
        'genus.family' models, leading to the same number of queries as before.
        """
        with self.assertNumQueries(2):
            world = Species.objects.filter(genus__name="Amanita").select_related(
                "genus__family"
            )
            orders = [o.genus.family.order.name for o in world]
            self.assertEqual(orders, ["Agaricales"])

    def test_field_traversal(self):
        """
        Tests the ability to traverse related fields in a single database query.

        Verifies that using select_related() to prefetch related objects allows the
        traversal of multiple levels of relationships without incurring additional
        database queries. Specifically, this test checks that traversing from a Species
        to its genus, family, and finally to the order name can be done with a single
        query. The test also validates that the order name is correctly retrieved as
        'Diptera'.
        """
        with self.assertNumQueries(1):
            s = (
                Species.objects.all()
                .select_related("genus__family__order")
                .order_by("id")[0:1]
                .get()
                .genus.family.order.name
            )
            self.assertEqual(s, "Diptera")

    def test_none_clears_list(self):
        """

        Tests that passing None to select_related clears the list of related objects to be retrieved with the main query.

        This ensures that when the select_related method is subsequently used, it will not attempt to fetch any related objects,
        resulting in a simple query without any joins. The test verifies this by checking the state of the queryset's select_related attribute.

        """
        queryset = Species.objects.select_related("genus").select_related(None)
        self.assertIs(queryset.query.select_related, False)

    def test_chaining(self):
        """
        Tests the efficient retrieval of related objects in a chained relationship.

        This test case validates the use of select_related to fetch related objects
        (parent species) in a hybrid species instance, ensuring that the data is 
        retrieved in a single database query, thus optimizing performance.

        Checks that the parent species instances are correctly retrieved and 
        associated with the hybrid species instance, confirming the chaining of 
        relationships works as expected.
        """
        parent_1, parent_2 = Species.objects.all()[:2]
        HybridSpecies.objects.create(
            name="hybrid", parent_1=parent_1, parent_2=parent_2
        )
        queryset = HybridSpecies.objects.select_related("parent_1").select_related(
            "parent_2"
        )
        with self.assertNumQueries(1):
            obj = queryset[0]
            self.assertEqual(obj.parent_1, parent_1)
            self.assertEqual(obj.parent_2, parent_2)

    def test_reverse_relation_caching(self):
        species = (
            Species.objects.select_related("genus").filter(name="melanogaster").first()
        )
        with self.assertNumQueries(0):
            self.assertEqual(species.genus.name, "Drosophila")
        # The species_set reverse relation isn't cached.
        self.assertEqual(species.genus._state.fields_cache, {})
        with self.assertNumQueries(1):
            self.assertEqual(species.genus.species_set.first().name, "melanogaster")

    def test_select_related_after_values(self):
        """
        Running select_related() after calling values() raises a TypeError
        """
        message = "Cannot call select_related() after .values() or .values_list()"
        with self.assertRaisesMessage(TypeError, message):
            list(Species.objects.values("name").select_related("genus"))

    def test_select_related_after_values_list(self):
        """
        Running select_related() after calling values_list() raises a TypeError
        """
        message = "Cannot call select_related() after .values() or .values_list()"
        with self.assertRaisesMessage(TypeError, message):
            list(Species.objects.values_list("name").select_related("genus"))


class SelectRelatedValidationTests(SimpleTestCase):
    """
    select_related() should thrown an error on fields that do not exist and
    non-relational fields.
    """

    non_relational_error = (
        "Non-relational field given in select_related: '%s'. Choices are: %s"
    )
    invalid_error = (
        "Invalid field name(s) given in select_related: '%s'. Choices are: %s"
    )

    def test_non_relational_field(self):
        """

        Tests the behavior of select_related when applied to non-relational fields.

        The function checks that using select_related with fields that do not support 
        relationships raises a FieldError with a meaningful error message. This ensures 
        that the ORM correctly handles and reports invalid usage of select_related.

        This test covers various scenarios, including attempting to select related 
        fields on a non-relational field, and selecting the non-relational field itself.

        """
        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("name", "genus")
        ):
            list(Species.objects.select_related("name__some_field"))

        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("name", "genus")
        ):
            list(Species.objects.select_related("name"))

        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("name", "(none)")
        ):
            list(Domain.objects.select_related("name"))

    def test_non_relational_field_nested(self):
        """
        Tests that attempting to use select_related on a non-relational field nested within a related field raises a FieldError.

        The function checks that Django correctly handles the case when trying to select a field that is not related, even when it is nested inside a related field. It verifies that the expected error message is raised, including the names of the fields involved in the error.

        This test case helps ensure that Django's ORM correctly handles and reports errors when attempting to use select_related with invalid field names, particularly in nested relationships.
        """
        with self.assertRaisesMessage(
            FieldError, self.non_relational_error % ("name", "family")
        ):
            list(Species.objects.select_related("genus__name"))

    def test_many_to_many_field(self):
        """

        Tests that attempting to use select_related on a many-to-many field raises a FieldError.

        This test case verifies that Django's ORM correctly handles many-to-many relationships
        and prevents the use of select_related on such fields, which are not supported by this method.

        The test expects a FieldError to be raised with a specific error message, indicating that
        select_related cannot be applied to the 'toppings' field on the Pizza model.

        """
        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("toppings", "(none)")
        ):
            list(Pizza.objects.select_related("toppings"))

    def test_reverse_relational_field(self):
        """
        Tests the behavior of the `select_related` method when attempting to select a relational field that does not exist.

        The test verifies that a `FieldError` exception is raised with an expected error message when trying to retrieve a list of `Species` objects that include the non-existent relationship `child_1` to `genus`. This ensures that the application correctly handles invalid relational field selections.
        """
        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("child_1", "genus")
        ):
            list(Species.objects.select_related("child_1"))

    def test_invalid_field(self):
        """
        Tests the behavior of the select_related method when an invalid field is specified.

        Verifies that a FieldError is raised when attempting to select a non-existent field, 
        either as a direct attribute or as a related field through a valid relationship. 
        The test covers various scenarios, including selecting an invalid field from different models, 
        such as Species and Domain, to ensure consistent error handling across the application.
        """
        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("invalid_field", "genus")
        ):
            list(Species.objects.select_related("invalid_field"))

        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("related_invalid_field", "family")
        ):
            list(Species.objects.select_related("genus__related_invalid_field"))

        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("invalid_field", "(none)")
        ):
            list(Domain.objects.select_related("invalid_field"))

    def test_generic_relations(self):
        """
        Tests that generic relations are handled correctly by Django's ORM.

        This test case checks that an error is raised when trying to use select_related on a generic foreign key field.
        It specifically tests two cases: selecting related 'tags' in Bookmark objects and selecting related 'content_object'
        in TaggedItem objects, without properly specifying the 'content_type' field for the generic relationship.

        The test verifies that the expected FieldError is raised with the correct error message, ensuring that the ORM
        correctly handles these generic relationships and raises informative errors when they are used incorrectly.
        """
        with self.assertRaisesMessage(FieldError, self.invalid_error % ("tags", "")):
            list(Bookmark.objects.select_related("tags"))

        with self.assertRaisesMessage(
            FieldError, self.invalid_error % ("content_object", "content_type")
        ):
            list(TaggedItem.objects.select_related("content_object"))
