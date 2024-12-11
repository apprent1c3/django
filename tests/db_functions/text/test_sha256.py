from django.db import connection
from django.db.models import CharField
from django.db.models.functions import SHA256
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class SHA256Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Author.objects.bulk_create(
            [
                Author(alias="John Smith"),
                Author(alias="Jordan Élena"),
                Author(alias="皇帝"),
                Author(alias=""),
                Author(alias=None),
            ]
        )

    def test_basic(self):
        """

        Tests the basic functionality of annotating authors with a SHA256 hash of their alias.

        Verifies that the resulting sequence of hashes matches the expected values, 
        ordered by the primary key of the authors. The test covers different database 
        behaviors regarding empty strings, ensuring consistency across various platforms.

        """
        authors = (
            Author.objects.annotate(
                sha256_alias=SHA256("alias"),
            )
            .values_list("sha256_alias", flat=True)
            .order_by("pk")
        )
        self.assertSequenceEqual(
            authors,
            [
                "ef61a579c907bbed674c0dbcbcf7f7af8f851538eef7b8e58c5bee0b8cfdac4a",
                "6e4cce20cd83fc7c202f21a8b2452a68509cf24d1c272a045b5e0cfc43f0d94e",
                "3ad2039e3ec0c88973ae1c0fce5a3dbafdd5a1627da0a92312c54ebfcf43988e",
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                (
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    if connection.features.interprets_empty_strings_as_nulls
                    else None
                ),
            ],
        )

    def test_transform(self):
        """
        Tests the transformation of a hashed value to its original form.

        This test case verifies that the SHA256 hash function can correctly transform 
        a hashed value back to its original string, in this case, an author's alias. 
        It checks if the provided hash value corresponds to a specific author and 
        ensures that the transformed value matches the expected output.

        The test registers a lookup for SHA256 with the CharField, allowing the filter 
        operation to find the author with the matching hashed alias. The result is then 
        compared to the expected value to confirm the correctness of the transformation.
        """
        with register_lookup(CharField, SHA256):
            authors = Author.objects.filter(
                alias__sha256=(
                    "ef61a579c907bbed674c0dbcbcf7f7af8f851538eef7b8e58c5bee0b8cfdac4a"
                ),
            ).values_list("alias", flat=True)
            self.assertSequenceEqual(authors, ["John Smith"])
