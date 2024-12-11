from django.db.models import FilteredRelation
from django.test import TestCase

from .models import Organiser, Pool, PoolStyle, Tournament


class ExistingRelatedInstancesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
         Sets up test data for the class, including tournaments, organisers, pools, and pool styles.

            Creates two tournaments, two organisers, four pools across the tournaments, and three pool styles.
            The test data is designed to provide a diverse set of scenarios for testing, including multiple pools
            within a tournament, shared organisers, and associations between pools through pool styles. 

            The test data is set as class attributes, making it accessible to all methods within the class for 
            testing purposes. 
        """
        cls.t1 = Tournament.objects.create(name="Tourney 1")
        cls.t2 = Tournament.objects.create(name="Tourney 2")
        cls.o1 = Organiser.objects.create(name="Organiser 1")
        cls.p1 = Pool.objects.create(
            name="T1 Pool 1", tournament=cls.t1, organiser=cls.o1
        )
        cls.p2 = Pool.objects.create(
            name="T1 Pool 2", tournament=cls.t1, organiser=cls.o1
        )
        cls.p3 = Pool.objects.create(
            name="T2 Pool 1", tournament=cls.t2, organiser=cls.o1
        )
        cls.p4 = Pool.objects.create(
            name="T2 Pool 2", tournament=cls.t2, organiser=cls.o1
        )
        cls.ps1 = PoolStyle.objects.create(name="T1 Pool 2 Style", pool=cls.p2)
        cls.ps2 = PoolStyle.objects.create(name="T2 Pool 1 Style", pool=cls.p3)
        cls.ps3 = PoolStyle.objects.create(
            name="T1 Pool 1/3 Style", pool=cls.p1, another_pool=cls.p3
        )

    def test_foreign_key(self):
        """
        Tests the foreign key relationship between Tournament and Pool models.

        Verifies that a pool instance is correctly associated with its corresponding tournament instance, 
        ensuring data consistency and validating the expected link between these models.

        The test checks for the correct number of database queries executed during the operation, 
        ensuring efficient data retrieval and minimizing potential performance issues.
        """
        with self.assertNumQueries(2):
            tournament = Tournament.objects.get(pk=self.t1.pk)
            pool = tournament.pool_set.all()[0]
            self.assertIs(tournament, pool.tournament)

    def test_foreign_key_prefetch_related(self):
        """
        Tests that prefetching related objects for a Tournament instance correctly retrieves 
        its associated Pool objects and establishes the foreign key relationship between them.

        Verifies that the tournament and pool objects are correctly linked via the foreign key, 
        and that the related objects can be accessed without triggering additional database queries.

        Preconditions: A Tournament instance with associated Pool objects must exist in the database.
        Asserts: The foreign key relationship between the Tournament and Pool objects is correctly established.
        """
        with self.assertNumQueries(2):
            tournament = Tournament.objects.prefetch_related("pool_set").get(
                pk=self.t1.pk
            )
            pool = tournament.pool_set.all()[0]
            self.assertIs(tournament, pool.tournament)

    def test_foreign_key_multiple_prefetch(self):
        with self.assertNumQueries(2):
            tournaments = list(
                Tournament.objects.prefetch_related("pool_set").order_by("pk")
            )
            pool1 = tournaments[0].pool_set.all()[0]
            self.assertIs(tournaments[0], pool1.tournament)
            pool2 = tournaments[1].pool_set.all()[0]
            self.assertIs(tournaments[1], pool2.tournament)

    def test_queryset_or(self):
        """
        Tests the QuerySet OR operation to retrieve pools from multiple tournaments.

        This test verifies that the QuerySet OR operation correctly combines pools from 
        multiple tournaments into a single QuerySet, and that the related tournament objects 
        are as expected.

        The test case checks that the QuerySet OR operation is executed in a single database 
        query, and that the resulting set of related tournament objects matches the set of 
        tournaments used to retrieve the pools.

        """
        tournament_1 = self.t1
        tournament_2 = self.t2
        with self.assertNumQueries(1):
            pools = tournament_1.pool_set.all() | tournament_2.pool_set.all()
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})

    def test_queryset_or_different_cached_items(self):
        tournament = self.t1
        organiser = self.o1
        with self.assertNumQueries(1):
            pools = tournament.pool_set.all() | organiser.pool_set.all()
            first = pools.filter(pk=self.p1.pk)[0]
            self.assertIs(first.tournament, tournament)
            self.assertIs(first.organiser, organiser)

    def test_queryset_or_only_one_with_precache(self):
        tournament_1 = self.t1
        tournament_2 = self.t2
        # 2 queries here as pool 3 has tournament 2, which is not cached
        with self.assertNumQueries(2):
            pools = tournament_1.pool_set.all() | Pool.objects.filter(pk=self.p3.pk)
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})
        # and the other direction
        with self.assertNumQueries(2):
            pools = Pool.objects.filter(pk=self.p3.pk) | tournament_1.pool_set.all()
            related_objects = {pool.tournament for pool in pools}
            self.assertEqual(related_objects, {tournament_1, tournament_2})

    def test_queryset_and(self):
        tournament = self.t1
        organiser = self.o1
        with self.assertNumQueries(1):
            pools = tournament.pool_set.all() & organiser.pool_set.all()
            first = pools.filter(pk=self.p1.pk)[0]
            self.assertIs(first.tournament, tournament)
            self.assertIs(first.organiser, organiser)

    def test_one_to_one(self):
        """

        Tests the one-to-one relationship between PoolStyle and Pool objects.

        Verifies that retrieving a PoolStyle object and then fetching its associated Pool
        object, and subsequently checking the Pool object's poolstyle attribute, results
        in the same PoolStyle object being returned, confirming the correct functioning
        of the one-to-one relationship. The test also ensures that this operation is
        performed within the expected number of database queries.

        """
        with self.assertNumQueries(2):
            style = PoolStyle.objects.get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_select_related(self):
        """
        Tests the one-to-one relationship between PoolStyle and Pool using select_related.

        This test case verifies that the relationship between PoolStyle and Pool is correctly
        established when using select_related, resulting in a reduction of database queries.
        It checks that the Pool instance associated with the PoolStyle instance can be accessed
        without triggering an additional database query, and that the reverse relationship is also valid.
        """
        with self.assertNumQueries(1):
            style = PoolStyle.objects.select_related("pool").get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_multi_select_related(self):
        with self.assertNumQueries(1):
            poolstyles = list(PoolStyle.objects.select_related("pool").order_by("pk"))
            self.assertIs(poolstyles[0], poolstyles[0].pool.poolstyle)
            self.assertIs(poolstyles[1], poolstyles[1].pool.poolstyle)

    def test_one_to_one_prefetch_related(self):
        with self.assertNumQueries(2):
            style = PoolStyle.objects.prefetch_related("pool").get(pk=self.ps1.pk)
            pool = style.pool
            self.assertIs(style, pool.poolstyle)

    def test_one_to_one_multi_prefetch_related(self):
        with self.assertNumQueries(2):
            poolstyles = list(PoolStyle.objects.prefetch_related("pool").order_by("pk"))
            self.assertIs(poolstyles[0], poolstyles[0].pool.poolstyle)
            self.assertIs(poolstyles[1], poolstyles[1].pool.poolstyle)

    def test_reverse_one_to_one(self):
        """

        Tests the one-to-one relationship between a Pool object and its associated PoolStyle object.
        Verifies that reversing the relationship, i.e., accessing the Pool object from its PoolStyle,
        returns the original Pool object, ensuring consistency in the relationship.
        The test also checks that the database query count is as expected, ensuring efficient data retrieval.

        """
        with self.assertNumQueries(2):
            pool = Pool.objects.get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_select_related(self):
        with self.assertNumQueries(1):
            pool = Pool.objects.select_related("poolstyle").get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_prefetch_related(self):
        """
        Tests the reverse one-to-one relationship when prefetching related objects.

        Verifies that when a Pool object is retrieved with prefetching of its related
        PoolStyle object, the reverse relationship from PoolStyle back to Pool is
        correctly established, ensuring that no additional database queries are
        issued.

        This test case ensures data consistency and efficient query execution by
        validating the one-to-one relationship between Pool and PoolStyle, which is
        essential for reliable operation of the application.

        The test checks that exactly two database queries are executed during this
        operation, confirming that the related object is indeed prefetched and
        not retrieved in a separate query. It also asserts that the PoolStyle object
        properly references its related Pool object, demonstrating a correct
        reverse one-to-one relationship.
        """
        with self.assertNumQueries(2):
            pool = Pool.objects.prefetch_related("poolstyle").get(pk=self.p2.pk)
            style = pool.poolstyle
            self.assertIs(pool, style.pool)

    def test_reverse_one_to_one_multi_select_related(self):
        """
        Tests the reverse one-to-one relationship between Pool and PoolStyle models.

        Verifies that the relationship is correctly established when using select_related
        to retrieve related objects in a single database query. The test checks that the
        Pool instance is correctly linked to its corresponding PoolStyle instance, and
        vice versa, for multiple Pool instances.

        Ensures that the query is executed efficiently, with only one database query
        being performed to retrieve the required data. 
        """
        with self.assertNumQueries(1):
            pools = list(Pool.objects.select_related("poolstyle").order_by("pk"))
            self.assertIs(pools[1], pools[1].poolstyle.pool)
            self.assertIs(pools[2], pools[2].poolstyle.pool)

    def test_reverse_one_to_one_multi_prefetch_related(self):
        """

        Tests the reverse one-to-one relationship between models with multi-prefetch related fields.

        Verifies that when fetching multiple objects using prefetch_related, the related objects are properly
        associated with their parent objects. Specifically, this test checks that the 'poolstyle' attribute of
        each 'Pool' object is correctly linked to its corresponding 'Pool' object, demonstrating a valid
        reverse one-to-one relationship.

        The test also asserts that the database query count is within the expected limit, ensuring efficient
        data retrieval.

        """
        with self.assertNumQueries(2):
            pools = list(Pool.objects.prefetch_related("poolstyle").order_by("pk"))
            self.assertIs(pools[1], pools[1].poolstyle.pool)
            self.assertIs(pools[2], pools[2].poolstyle.pool)

    def test_reverse_fk_select_related_multiple(self):
        """

        Tests the ability to select related objects in a single query using FilteredRelation 
        and select_related, specifically when dealing with multiple foreign key relationships 
        in reverse. Verifies that the selected related objects are correctly associated 
        with the primary object and that the query is executed efficiently with a single 
        database query.

        """
        with self.assertNumQueries(1):
            ps = list(
                PoolStyle.objects.annotate(
                    pool_1=FilteredRelation("pool"),
                    pool_2=FilteredRelation("another_pool"),
                )
                .select_related("pool_1", "pool_2")
                .order_by("-pk")
            )
            self.assertIs(ps[0], ps[0].pool_1.poolstyle)
            self.assertIs(ps[0], ps[0].pool_2.another_style)

    def test_multilevel_reverse_fk_cyclic_select_related(self):
        """
        Test that multilevel reverse foreign key cyclic select_related queries are executed efficiently.

        This function verifies that a specific ORM query using select_related and annotate with FilteredRelation is executed within the expected number of database queries.
        It checks that the relationship between PoolStyle, TournamentPool and Tournament is correctly established and can be accessed without additional database queries.
        The assertion ensures that the tournament instance obtained through the reverse foreign key is the same as the one obtained directly from the pool.
        """
        with self.assertNumQueries(3):
            p = list(
                PoolStyle.objects.annotate(
                    tournament_pool=FilteredRelation("pool__tournament__pool"),
                ).select_related("tournament_pool", "tournament_pool__tournament")
            )
            self.assertEqual(p[0].tournament_pool.tournament, p[0].pool.tournament)

    def test_multilevel_reverse_fk_select_related(self):
        with self.assertNumQueries(2):
            p = list(
                Tournament.objects.filter(id=self.t2.id)
                .annotate(
                    style=FilteredRelation("pool__another_style"),
                )
                .select_related("style")
            )
            self.assertEqual(p[0].style.another_pool, self.p3)
