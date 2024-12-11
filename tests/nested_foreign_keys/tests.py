from django.test import TestCase

from .models import (
    Event,
    Movie,
    Package,
    PackageNullFK,
    Person,
    Screening,
    ScreeningNullFK,
)


# These are tests for #16715. The basic scheme is always the same: 3 models with
# 2 relations. The first relation may be null, while the second is non-nullable.
# In some cases, Django would pick the wrong join type for the second relation,
# resulting in missing objects in the queryset.
#
#   Model A
#   | (Relation A/B : nullable)
#   Model B
#   | (Relation B/C : non-nullable)
#   Model C
#
# Because of the possibility of NULL rows resulting from the LEFT OUTER JOIN
# between Model A and Model B (i.e. instances of A without reference to B),
# the second join must also be LEFT OUTER JOIN, so that we do not ignore
# instances of A that do not reference B.
#
# Relation A/B can either be an explicit foreign key or an implicit reverse
# relation such as introduced by one-to-one relations (through multi-table
# inheritance).
class NestedForeignKeysTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = Person.objects.create(name="Terry Gilliam / Terry Jones")
        cls.movie = Movie.objects.create(
            title="Monty Python and the Holy Grail", director=cls.director
        )

    # This test failed in #16715 because in some cases INNER JOIN was selected
    # for the second foreign key relation instead of LEFT OUTER JOIN.
    def test_inheritance(self):
        """

        Test the inheritance behavior of the Event model.

        Verify that the Event model properly inherits and relates to the Screening and Movie models.
        This includes testing various query methods such as select_related, values, filter, and exclude,
        to ensure that the model's relationships are correctly established and queried.

        """
        Event.objects.create()
        Screening.objects.create(movie=self.movie)

        self.assertEqual(len(Event.objects.all()), 2)
        self.assertEqual(len(Event.objects.select_related("screening")), 2)
        # This failed.
        self.assertEqual(len(Event.objects.select_related("screening__movie")), 2)

        self.assertEqual(len(Event.objects.values()), 2)
        self.assertEqual(len(Event.objects.values("screening__pk")), 2)
        self.assertEqual(len(Event.objects.values("screening__movie__pk")), 2)
        self.assertEqual(len(Event.objects.values("screening__movie__title")), 2)
        # This failed.
        self.assertEqual(
            len(
                Event.objects.values("screening__movie__pk", "screening__movie__title")
            ),
            2,
        )

        # Simple filter/exclude queries for good measure.
        self.assertEqual(Event.objects.filter(screening__movie=self.movie).count(), 1)
        self.assertEqual(Event.objects.exclude(screening__movie=self.movie).count(), 1)

    # These all work because the second foreign key in the chain has null=True.
    def test_inheritance_null_FK(self):
        Event.objects.create()
        ScreeningNullFK.objects.create(movie=None)
        ScreeningNullFK.objects.create(movie=self.movie)

        self.assertEqual(len(Event.objects.all()), 3)
        self.assertEqual(len(Event.objects.select_related("screeningnullfk")), 3)
        self.assertEqual(len(Event.objects.select_related("screeningnullfk__movie")), 3)

        self.assertEqual(len(Event.objects.values()), 3)
        self.assertEqual(len(Event.objects.values("screeningnullfk__pk")), 3)
        self.assertEqual(len(Event.objects.values("screeningnullfk__movie__pk")), 3)
        self.assertEqual(len(Event.objects.values("screeningnullfk__movie__title")), 3)
        self.assertEqual(
            len(
                Event.objects.values(
                    "screeningnullfk__movie__pk", "screeningnullfk__movie__title"
                )
            ),
            3,
        )

        self.assertEqual(
            Event.objects.filter(screeningnullfk__movie=self.movie).count(), 1
        )
        self.assertEqual(
            Event.objects.exclude(screeningnullfk__movie=self.movie).count(), 2
        )

    def test_null_exclude(self):
        """
        Test that the exclude method correctly filters out objects based on the 'movie' foreign key.

        This test verifies that when excluding objects with a specific 'movie' id, it returns the correct ScreeningNullFK instance where the 'movie' is null, while excluding the instance where the 'movie' matches the specified id.

        Checks the behavior of the exclude method on the 'movie' foreign key field, ensuring it properly handles null values and distinct object filtering.
        """
        screening = ScreeningNullFK.objects.create(movie=None)
        ScreeningNullFK.objects.create(movie=self.movie)
        self.assertEqual(
            list(ScreeningNullFK.objects.exclude(movie__id=self.movie.pk)), [screening]
        )

    # This test failed in #16715 because in some cases INNER JOIN was selected
    # for the second foreign key relation instead of LEFT OUTER JOIN.
    def test_explicit_ForeignKey(self):
        """

        Tests the usage of explicit ForeignKey relationships in Package objects.

        This test case verifies the correct functioning of ForeignKey fields in Package objects, specifically when related to Screening and Movie objects.
        It covers various scenarios, including:
        - Creating Package objects with and without a Screening relationship
        - Using select_related to fetch related objects in a single query
        - Using values and values_list to retrieve specific fields from related objects
        - Filtering and excluding Package objects based on conditions applied to related Screening and Movie objects

        The test ensures that the expected number of Package objects is returned in each scenario, validating the integrity of the ForeignKey relationships.

        """
        Package.objects.create()
        screening = Screening.objects.create(movie=self.movie)
        Package.objects.create(screening=screening)

        self.assertEqual(len(Package.objects.all()), 2)
        self.assertEqual(len(Package.objects.select_related("screening")), 2)
        self.assertEqual(len(Package.objects.select_related("screening__movie")), 2)

        self.assertEqual(len(Package.objects.values()), 2)
        self.assertEqual(len(Package.objects.values("screening__pk")), 2)
        self.assertEqual(len(Package.objects.values("screening__movie__pk")), 2)
        self.assertEqual(len(Package.objects.values("screening__movie__title")), 2)
        # This failed.
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__pk", "screening__movie__title"
                )
            ),
            2,
        )

        self.assertEqual(Package.objects.filter(screening__movie=self.movie).count(), 1)
        self.assertEqual(
            Package.objects.exclude(screening__movie=self.movie).count(), 1
        )

    # These all work because the second foreign key in the chain has null=True.
    def test_explicit_ForeignKey_NullFK(self):
        PackageNullFK.objects.create()
        screening = ScreeningNullFK.objects.create(movie=None)
        screening_with_movie = ScreeningNullFK.objects.create(movie=self.movie)
        PackageNullFK.objects.create(screening=screening)
        PackageNullFK.objects.create(screening=screening_with_movie)

        self.assertEqual(len(PackageNullFK.objects.all()), 3)
        self.assertEqual(len(PackageNullFK.objects.select_related("screening")), 3)
        self.assertEqual(
            len(PackageNullFK.objects.select_related("screening__movie")), 3
        )

        self.assertEqual(len(PackageNullFK.objects.values()), 3)
        self.assertEqual(len(PackageNullFK.objects.values("screening__pk")), 3)
        self.assertEqual(len(PackageNullFK.objects.values("screening__movie__pk")), 3)
        self.assertEqual(
            len(PackageNullFK.objects.values("screening__movie__title")), 3
        )
        self.assertEqual(
            len(
                PackageNullFK.objects.values(
                    "screening__movie__pk", "screening__movie__title"
                )
            ),
            3,
        )

        self.assertEqual(
            PackageNullFK.objects.filter(screening__movie=self.movie).count(), 1
        )
        self.assertEqual(
            PackageNullFK.objects.exclude(screening__movie=self.movie).count(), 2
        )


# Some additional tests for #16715. The only difference is the depth of the
# nesting as we now use 4 models instead of 3 (and thus 3 relations). This
# checks if promotion of join types works for deeper nesting too.
class DeeplyNestedForeignKeysTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating a basic movie object with a director.

         This method creates a single Person object representing the movie director and a Movie object referencing this director.

         :return: None
         :rtype: None
        """
        cls.director = Person.objects.create(name="Terry Gilliam / Terry Jones")
        cls.movie = Movie.objects.create(
            title="Monty Python and the Holy Grail", director=cls.director
        )

    def test_inheritance(self):
        """

        Tests the proper inheritance and relationship queries between Events, Screenings, Movies, and Directors.

        This function creates an Event and a Screening instance related to a Movie, 
        then asserts that various database queries using Django's ORM correctly 
        retrieves or filters related objects through foreign key relationships. 
        It checks for correct counts of objects retrieved using select_related, 
        values, filter, and exclude queries. 
        The test ensures that the relationships between models are properly established 
        and that queries can traverse these relationships to retrieve related data.

        """
        Event.objects.create()
        Screening.objects.create(movie=self.movie)

        self.assertEqual(len(Event.objects.all()), 2)
        self.assertEqual(
            len(Event.objects.select_related("screening__movie__director")), 2
        )

        self.assertEqual(len(Event.objects.values()), 2)
        self.assertEqual(len(Event.objects.values("screening__movie__director__pk")), 2)
        self.assertEqual(
            len(Event.objects.values("screening__movie__director__name")), 2
        )
        self.assertEqual(
            len(
                Event.objects.values(
                    "screening__movie__director__pk", "screening__movie__director__name"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Event.objects.values(
                    "screening__movie__pk", "screening__movie__director__pk"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Event.objects.values(
                    "screening__movie__pk", "screening__movie__director__name"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Event.objects.values(
                    "screening__movie__title", "screening__movie__director__pk"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Event.objects.values(
                    "screening__movie__title", "screening__movie__director__name"
                )
            ),
            2,
        )

        self.assertEqual(
            Event.objects.filter(screening__movie__director=self.director).count(), 1
        )
        self.assertEqual(
            Event.objects.exclude(screening__movie__director=self.director).count(), 1
        )

    def test_explicit_ForeignKey(self):
        Package.objects.create()
        screening = Screening.objects.create(movie=self.movie)
        Package.objects.create(screening=screening)

        self.assertEqual(len(Package.objects.all()), 2)
        self.assertEqual(
            len(Package.objects.select_related("screening__movie__director")), 2
        )

        self.assertEqual(len(Package.objects.values()), 2)
        self.assertEqual(
            len(Package.objects.values("screening__movie__director__pk")), 2
        )
        self.assertEqual(
            len(Package.objects.values("screening__movie__director__name")), 2
        )
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__director__pk", "screening__movie__director__name"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__pk", "screening__movie__director__pk"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__pk", "screening__movie__director__name"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__title", "screening__movie__director__pk"
                )
            ),
            2,
        )
        self.assertEqual(
            len(
                Package.objects.values(
                    "screening__movie__title", "screening__movie__director__name"
                )
            ),
            2,
        )

        self.assertEqual(
            Package.objects.filter(screening__movie__director=self.director).count(), 1
        )
        self.assertEqual(
            Package.objects.exclude(screening__movie__director=self.director).count(), 1
        )
