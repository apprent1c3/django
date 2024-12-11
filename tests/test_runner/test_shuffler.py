from unittest import mock

from django.test import SimpleTestCase
from django.test.runner import Shuffler


class ShufflerTests(SimpleTestCase):
    def test_hash_text(self):
        actual = Shuffler._hash_text("abcd")
        self.assertEqual(actual, "e2fc714c4727ee9395f324cd2e7f331f")

    def test_hash_text_hash_algorithm(self):
        """

        Tests the consistency of the hash text algorithm used by the Shuffler class.

        Verifies that the hash text algorithm specified by the Shuffler class, in this case SHA-1,
        produces the expected hash value for a given input string.

        The test ensures that the resulting hash value matches the known hash value for the input string 'abcd',
        which is '81fe8bfe87576c3ecb22426f8e57847382917acf'.

        """
        class MyShuffler(Shuffler):
            hash_algorithm = "sha1"

        actual = MyShuffler._hash_text("abcd")
        self.assertEqual(actual, "81fe8bfe87576c3ecb22426f8e57847382917acf")

    def test_init(self):
        """
        Tests the initialization of the Shuffler class.

        Verifies that the Shuffler object is properly created with a given seed value,
        and that the seed and seed source are correctly set as attributes of the object.
        """
        shuffler = Shuffler(100)
        self.assertEqual(shuffler.seed, 100)
        self.assertEqual(shuffler.seed_source, "given")

    def test_init_none_seed(self):
        with mock.patch("random.randint", return_value=200):
            shuffler = Shuffler(None)
        self.assertEqual(shuffler.seed, 200)
        self.assertEqual(shuffler.seed_source, "generated")

    def test_init_no_seed_argument(self):
        """
        Tests that the Shuffler class initializes correctly when no seed argument is provided. 
         It verifies that a random seed is generated and assigned to the object, 
         and that the seed source is correctly identified as generated.
        """
        with mock.patch("random.randint", return_value=300):
            shuffler = Shuffler()
        self.assertEqual(shuffler.seed, 300)
        self.assertEqual(shuffler.seed_source, "generated")

    def test_seed_display(self):
        shuffler = Shuffler(100)
        shuffler.seed_source = "test"
        self.assertEqual(shuffler.seed_display, "100 (test)")

    def test_hash_item_seed(self):
        cases = [
            (1234, "64ad3fb166ddb41a2ca24f1803b8b722"),
            # Passing a string gives the same value.
            ("1234", "64ad3fb166ddb41a2ca24f1803b8b722"),
            (5678, "4dde450ad339b6ce45a0a2666e35b975"),
        ]
        for seed, expected in cases:
            with self.subTest(seed=seed):
                shuffler = Shuffler(seed=seed)
                actual = shuffler._hash_item("abc", lambda x: x)
                self.assertEqual(actual, expected)

    def test_hash_item_key(self):
        cases = [
            (lambda x: x, "64ad3fb166ddb41a2ca24f1803b8b722"),
            (lambda x: x.upper(), "ee22e8597bff91742affe4befbf4649a"),
        ]
        for key, expected in cases:
            with self.subTest(key=key):
                shuffler = Shuffler(seed=1234)
                actual = shuffler._hash_item("abc", key)
                self.assertEqual(actual, expected)

    def test_shuffle_key(self):
        cases = [
            (lambda x: x, ["a", "d", "b", "c"]),
            (lambda x: x.upper(), ["d", "c", "a", "b"]),
        ]
        for num, (key, expected) in enumerate(cases, start=1):
            with self.subTest(num=num):
                shuffler = Shuffler(seed=1234)
                actual = shuffler.shuffle(["a", "b", "c", "d"], key)
                self.assertEqual(actual, expected)

    def test_shuffle_consistency(self):
        """
        Tests the consistency of the shuffle operation performed by the Shuffler class.

        This test case verifies that the Shuffler class produces the expected shuffled sequence 
        for various input sequences and indices, using a fixed seed for reproducibility.

        The test checks the shuffle operation with and without removing elements at specific indices.
        It ensures that the shuffled sequence matches the expected output for each test case, 
        providing confidence in the correctness and consistency of the Shuffler class's shuffle method.
        """
        seq = [str(n) for n in range(5)]
        cases = [
            (None, ["3", "0", "2", "4", "1"]),
            (0, ["3", "2", "4", "1"]),
            (1, ["3", "0", "2", "4"]),
            (2, ["3", "0", "4", "1"]),
            (3, ["0", "2", "4", "1"]),
            (4, ["3", "0", "2", "1"]),
        ]
        shuffler = Shuffler(seed=1234)
        for index, expected in cases:
            with self.subTest(index=index):
                if index is None:
                    new_seq = seq
                else:
                    new_seq = seq.copy()
                    del new_seq[index]
                actual = shuffler.shuffle(new_seq, lambda x: x)
                self.assertEqual(actual, expected)

    def test_shuffle_same_hash(self):
        """

        Tests that the shuffle method raises an exception when it encounters items with the same hash value.

        This test case verifies that the shuffler correctly identifies and reports collisions between items 
        with different original values but identical hash values, ensuring data integrity during the shuffling process.

        """
        shuffler = Shuffler(seed=1234)
        msg = "item 'A' has same hash 'a56ce89262959e151ee2266552f1819c' as item 'a'"
        with self.assertRaisesMessage(RuntimeError, msg):
            shuffler.shuffle(["a", "b", "A"], lambda x: x.upper())
