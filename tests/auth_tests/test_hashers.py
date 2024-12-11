from unittest import mock, skipUnless

from django.conf.global_settings import PASSWORD_HASHERS
from django.contrib.auth.hashers import (
    UNUSABLE_PASSWORD_PREFIX,
    UNUSABLE_PASSWORD_SUFFIX_LENGTH,
    BasePasswordHasher,
    BCryptPasswordHasher,
    BCryptSHA256PasswordHasher,
    MD5PasswordHasher,
    PBKDF2PasswordHasher,
    PBKDF2SHA1PasswordHasher,
    ScryptPasswordHasher,
    acheck_password,
    check_password,
    get_hasher,
    identify_hasher,
    is_password_usable,
    make_password,
)
from django.test import SimpleTestCase
from django.test.utils import override_settings

try:
    import bcrypt
except ImportError:
    bcrypt = None

try:
    import argon2
except ImportError:
    argon2 = None

# scrypt requires OpenSSL 1.1+
try:
    import hashlib

    scrypt = hashlib.scrypt
except ImportError:
    scrypt = None


class PBKDF2SingleIterationHasher(PBKDF2PasswordHasher):
    iterations = 1


@override_settings(PASSWORD_HASHERS=PASSWORD_HASHERS)
class TestUtilsHashPass(SimpleTestCase):
    def test_simple(self):
        """
        Tests the functionality of password creation and verification.

        This test case covers the creation of passwords using the make_password function,
        verifies that the generated passwords are in the correct format and usable,
        and checks that the check_password function correctly validates passwords.

        It also tests edge cases such as empty passwords to ensure the password
        management system behaves as expected.

        The test covers the following scenarios:
        - Password creation with a non-empty string
        - Password creation with an empty string
        - Verification of valid and invalid passwords against the created passwords
        """
        encoded = make_password("lètmein")
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        # Blank passwords
        blank_encoded = make_password("")
        self.assertTrue(blank_encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))

    async def test_acheck_password(self):
        """

        Checks the functionality of asynchronous password verification.

        This test function verifies that the acheck_password function correctly validates 
        user-provided passwords against their stored encrypted versions. It checks the 
        following scenarios:

        - Valid password matching the stored encoded password
        - Invalid password not matching the stored encoded password
        - Empty password matching the stored encoded empty password
        - Non-empty password not matching the stored encoded empty password

        Ensures that the acheck_password function behaves as expected in various cases.

        """
        encoded = make_password("lètmein")
        self.assertIs(await acheck_password("lètmein", encoded), True)
        self.assertIs(await acheck_password("lètmeinz", encoded), False)
        # Blank passwords.
        blank_encoded = make_password("")
        self.assertIs(await acheck_password("", blank_encoded), True)
        self.assertIs(await acheck_password(" ", blank_encoded), False)

    def test_bytes(self):
        """
        Tests the functionality of password creation and verification when using bytes as input.

        This test case covers the following scenarios:
        - Password encoding: Verifies that a password encoded from bytes input starts with the expected prefix.
        - Password usability: Checks if the encoded password is usable.
        - Password verification: Confirms that the original bytes password matches the encoded password.

        Ensures that the password management system correctly handles bytes input and produces the expected results for encoded password verification and usability checks.
        """
        encoded = make_password(b"bytes_password")
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertIs(is_password_usable(encoded), True)
        self.assertIs(check_password(b"bytes_password", encoded), True)

    def test_invalid_password(self):
        msg = "Password must be a string or bytes, got int."
        with self.assertRaisesMessage(TypeError, msg):
            make_password(1)

    def test_pbkdf2(self):
        """

        Test the functionality of the PBKDF2 password hashing algorithm.

        This test case verifies the correctness of the PBKDF2 password hashing algorithm 
        by checking the following scenarios:

        - Encoding a password with a given salt and algorithm
        - Verifying the usability of the encoded password
        - Checking the correctness of password verification
        - Identifying the hashing algorithm used for a given encoded password
        - Handling of empty passwords and different salts

        The test also checks the 'must_update' method of the password hasher to ensure 
        that weak salts are correctly identified and updated to stronger ones.

        """
        encoded = make_password("lètmein", "seasalt", "pbkdf2_sha256")
        self.assertEqual(
            encoded,
            "pbkdf2_sha256$1000000$"
            "seasalt$r1uLUxoxpP2Ued/qxvmje7UH9PUJBkRrvf9gGPL7Cps=",
        )
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "pbkdf2_sha256")
        # Blank passwords
        blank_encoded = make_password("", "seasalt", "pbkdf2_sha256")
        self.assertTrue(blank_encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))
        # Salt entropy check.
        hasher = get_hasher("pbkdf2_sha256")
        encoded_weak_salt = make_password("lètmein", "iodizedsalt", "pbkdf2_sha256")
        encoded_strong_salt = make_password("lètmein", hasher.salt(), "pbkdf2_sha256")
        self.assertIs(hasher.must_update(encoded_weak_salt), True)
        self.assertIs(hasher.must_update(encoded_strong_salt), False)

    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
    )
    def test_md5(self):
        """

        Tests the functionality of the MD5 password hasher.

        This test case ensures that the MD5 password hasher correctly encodes and verifies passwords.
        It checks the following:

        * Passwords are encoded correctly with the MD5 algorithm and a provided salt.
        * Encoded passwords can be verified using the correct password.
        * Incorrect passwords are rejected.
        * The MD5 algorithm is correctly identified from an encoded password.
        * Blank passwords are handled correctly and can be verified.
        * Passwords with weak salts are flagged for update.
        * Passwords with strong salts are not flagged for update.

        The test uses various helper functions, including `make_password`, `is_password_usable`, `check_password`, `identify_hasher`, and `get_hasher`, to verify the correctness of the MD5 password hasher.

        """
        encoded = make_password("lètmein", "seasalt", "md5")
        self.assertEqual(encoded, "md5$seasalt$3f86d0d3d465b7b458c231bf3555c0e3")
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "md5")
        # Blank passwords
        blank_encoded = make_password("", "seasalt", "md5")
        self.assertTrue(blank_encoded.startswith("md5$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))
        # Salt entropy check.
        hasher = get_hasher("md5")
        encoded_weak_salt = make_password("lètmein", "iodizedsalt", "md5")
        encoded_strong_salt = make_password("lètmein", hasher.salt(), "md5")
        self.assertIs(hasher.must_update(encoded_weak_salt), True)
        self.assertIs(hasher.must_update(encoded_strong_salt), False)

    @skipUnless(bcrypt, "bcrypt not installed")
    def test_bcrypt_sha256(self):
        """
        Tests the bcrypt_sha256 password hashing algorithm.

        This test suite verifies the functionality of the bcrypt_sha256 hasher, including
        password encoding, usability checking, and authentication. It ensures that the 
        hasher produces the expected output format and can correctly validate passwords.

        The tests cover various scenarios, such as:
        - Encoding and checking passwords with special characters
        - Verifying that the encoded password starts with the expected prefix
        - Checking that the correct hashing algorithm is identified
        - Authenticating passwords of varying lengths
        - Handling empty passwords

        These tests provide confidence that the bcrypt_sha256 hasher is working as expected
        and can be relied upon for secure password storage and verification.
        """
        encoded = make_password("lètmein", hasher="bcrypt_sha256")
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(encoded.startswith("bcrypt_sha256$"))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "bcrypt_sha256")

        # password truncation no longer works
        password = (
            "VSK0UYV6FFQVZ0KG88DYN9WADAADZO1CTSIVDJUNZSUML6IBX7LN7ZS3R5"
            "JGB3RGZ7VI7G7DJQ9NI8BQFSRPTG6UWTTVESA5ZPUN"
        )
        encoded = make_password(password, hasher="bcrypt_sha256")
        self.assertTrue(check_password(password, encoded))
        self.assertFalse(check_password(password[:72], encoded))
        # Blank passwords
        blank_encoded = make_password("", hasher="bcrypt_sha256")
        self.assertTrue(blank_encoded.startswith("bcrypt_sha256$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))

    @skipUnless(bcrypt, "bcrypt not installed")
    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.BCryptPasswordHasher"]
    )
    def test_bcrypt(self):
        encoded = make_password("lètmein", hasher="bcrypt")
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(encoded.startswith("bcrypt$"))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "bcrypt")
        # Blank passwords
        blank_encoded = make_password("", hasher="bcrypt")
        self.assertTrue(blank_encoded.startswith("bcrypt$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))

    @skipUnless(bcrypt, "bcrypt not installed")
    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.BCryptPasswordHasher"]
    )
    def test_bcrypt_upgrade(self):
        hasher = get_hasher("bcrypt")
        self.assertEqual("bcrypt", hasher.algorithm)
        self.assertNotEqual(hasher.rounds, 4)

        old_rounds = hasher.rounds
        try:
            # Generate a password with 4 rounds.
            hasher.rounds = 4
            encoded = make_password("letmein", hasher="bcrypt")
            rounds = hasher.safe_summary(encoded)["work factor"]
            self.assertEqual(rounds, 4)

            state = {"upgraded": False}

            def setter(password):
                state["upgraded"] = True

            # No upgrade is triggered.
            self.assertTrue(check_password("letmein", encoded, setter, "bcrypt"))
            self.assertFalse(state["upgraded"])

            # Revert to the old rounds count and ...
            hasher.rounds = old_rounds

            # ... check if the password would get updated to the new count.
            self.assertTrue(check_password("letmein", encoded, setter, "bcrypt"))
            self.assertTrue(state["upgraded"])
        finally:
            hasher.rounds = old_rounds

    @skipUnless(bcrypt, "bcrypt not installed")
    @override_settings(
        PASSWORD_HASHERS=["django.contrib.auth.hashers.BCryptPasswordHasher"]
    )
    def test_bcrypt_harden_runtime(self):
        hasher = get_hasher("bcrypt")
        self.assertEqual("bcrypt", hasher.algorithm)

        with mock.patch.object(hasher, "rounds", 4):
            encoded = make_password("letmein", hasher="bcrypt")

        with (
            mock.patch.object(hasher, "rounds", 6),
            mock.patch.object(hasher, "encode", side_effect=hasher.encode),
        ):
            hasher.harden_runtime("wrong_password", encoded)

            # Increasing rounds from 4 to 6 means an increase of 4 in workload,
            # therefore hardening should run 3 times to make the timing the
            # same (the original encode() call already ran once).
            self.assertEqual(hasher.encode.call_count, 3)

            # Get the original salt (includes the original workload factor)
            algorithm, data = encoded.split("$", 1)
            expected_call = (("wrong_password", data[:29].encode()),)
            self.assertEqual(hasher.encode.call_args_list, [expected_call] * 3)

    def test_unusable(self):
        encoded = make_password(None)
        self.assertEqual(
            len(encoded),
            len(UNUSABLE_PASSWORD_PREFIX) + UNUSABLE_PASSWORD_SUFFIX_LENGTH,
        )
        self.assertFalse(is_password_usable(encoded))
        self.assertFalse(check_password(None, encoded))
        self.assertFalse(check_password(encoded, encoded))
        self.assertFalse(check_password(UNUSABLE_PASSWORD_PREFIX, encoded))
        self.assertFalse(check_password("", encoded))
        self.assertFalse(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        with self.assertRaisesMessage(ValueError, "Unknown password hashing algorithm"):
            identify_hasher(encoded)
        # Assert that the unusable passwords actually contain a random part.
        # This might fail one day due to a hash collision.
        self.assertNotEqual(encoded, make_password(None), "Random password collision?")

    def test_unspecified_password(self):
        """
        Makes sure specifying no plain password with a valid encoded password
        returns `False`.
        """
        self.assertFalse(check_password(None, make_password("lètmein")))

    def test_bad_algorithm(self):
        """
        Tests that specifying an unknown password hashing algorithm raises a ValueError.

        This test covers two scenarios: 
        1. When attempting to create a password using an unknown hashing algorithm via the 'make_password' function.
        2. When attempting to identify the hashing algorithm used in a given password string via the 'identify_hasher' function.

        In both cases, the test expects a ValueError to be raised with a message indicating that the specified algorithm is unknown and instructing the user to check the PASSWORD_HASHERS setting.
        """
        msg = (
            "Unknown password hashing algorithm '%s'. Did you specify it in "
            "the PASSWORD_HASHERS setting?"
        )
        with self.assertRaisesMessage(ValueError, msg % "lolcat"):
            make_password("lètmein", hasher="lolcat")
        with self.assertRaisesMessage(ValueError, msg % "lolcat"):
            identify_hasher("lolcat$salt$hash")

    def test_is_password_usable(self):
        passwords = ("lètmein_badencoded", "", None)
        for password in passwords:
            with self.subTest(password=password):
                self.assertIs(is_password_usable(password), True)

    def test_low_level_pbkdf2(self):
        hasher = PBKDF2PasswordHasher()
        encoded = hasher.encode("lètmein", "seasalt2")
        self.assertEqual(
            encoded,
            "pbkdf2_sha256$1000000$"
            "seasalt2$egbhFghgsJVDo5Tpg/k9ZnfbySKQ1UQnBYXhR97a7sk=",
        )
        self.assertTrue(hasher.verify("lètmein", encoded))

    def test_low_level_pbkdf2_sha1(self):
        hasher = PBKDF2SHA1PasswordHasher()
        encoded = hasher.encode("lètmein", "seasalt2")
        self.assertEqual(
            encoded, "pbkdf2_sha1$1000000$seasalt2$3R9hvSAiAy5ARspAFy5GJ/2rjXo="
        )
        self.assertTrue(hasher.verify("lètmein", encoded))

    @skipUnless(bcrypt, "bcrypt not installed")
    def test_bcrypt_salt_check(self):
        hasher = BCryptPasswordHasher()
        encoded = hasher.encode("lètmein", hasher.salt())
        self.assertIs(hasher.must_update(encoded), False)

    @skipUnless(bcrypt, "bcrypt not installed")
    def test_bcryptsha256_salt_check(self):
        """
        Tests the correctness of the BCryptSHA256PasswordHasher's salt generation functionality.

        This test checks whether the BCryptSHA256PasswordHasher correctly determines if a password needs to be updated after being encoded with a generated salt.

        The test case verifies that the encoded password does not require an immediate update by the hasher.
        """
        hasher = BCryptSHA256PasswordHasher()
        encoded = hasher.encode("lètmein", hasher.salt())
        self.assertIs(hasher.must_update(encoded), False)

    @override_settings(
        PASSWORD_HASHERS=[
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
            "django.contrib.auth.hashers.MD5PasswordHasher",
        ],
    )
    def test_upgrade(self):
        self.assertEqual("pbkdf2_sha256", get_hasher("default").algorithm)
        for algo in ("pbkdf2_sha1", "md5"):
            with self.subTest(algo=algo):
                encoded = make_password("lètmein", hasher=algo)
                state = {"upgraded": False}

                def setter(password):
                    state["upgraded"] = True

                self.assertTrue(check_password("lètmein", encoded, setter))
                self.assertTrue(state["upgraded"])

    def test_no_upgrade(self):
        encoded = make_password("lètmein")
        state = {"upgraded": False}

        def setter():
            state["upgraded"] = True

        self.assertFalse(check_password("WRONG", encoded, setter))
        self.assertFalse(state["upgraded"])

    @override_settings(
        PASSWORD_HASHERS=[
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
            "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
            "django.contrib.auth.hashers.MD5PasswordHasher",
        ],
    )
    def test_no_upgrade_on_incorrect_pass(self):
        self.assertEqual("pbkdf2_sha256", get_hasher("default").algorithm)
        for algo in ("pbkdf2_sha1", "md5"):
            with self.subTest(algo=algo):
                encoded = make_password("lètmein", hasher=algo)
                state = {"upgraded": False}

                def setter():
                    state["upgraded"] = True

                self.assertFalse(check_password("WRONG", encoded, setter))
                self.assertFalse(state["upgraded"])

    def test_pbkdf2_upgrade(self):
        hasher = get_hasher("default")
        self.assertEqual("pbkdf2_sha256", hasher.algorithm)
        self.assertNotEqual(hasher.iterations, 1)

        old_iterations = hasher.iterations
        try:
            # Generate a password with 1 iteration.
            hasher.iterations = 1
            encoded = make_password("letmein")
            algo, iterations, salt, hash = encoded.split("$", 3)
            self.assertEqual(iterations, "1")

            state = {"upgraded": False}

            def setter(password):
                state["upgraded"] = True

            # No upgrade is triggered
            self.assertTrue(check_password("letmein", encoded, setter))
            self.assertFalse(state["upgraded"])

            # Revert to the old iteration count and ...
            hasher.iterations = old_iterations

            # ... check if the password would get updated to the new iteration count.
            self.assertTrue(check_password("letmein", encoded, setter))
            self.assertTrue(state["upgraded"])
        finally:
            hasher.iterations = old_iterations

    def test_pbkdf2_harden_runtime(self):
        hasher = get_hasher("default")
        self.assertEqual("pbkdf2_sha256", hasher.algorithm)

        with mock.patch.object(hasher, "iterations", 1):
            encoded = make_password("letmein")

        with (
            mock.patch.object(hasher, "iterations", 6),
            mock.patch.object(hasher, "encode", side_effect=hasher.encode),
        ):
            hasher.harden_runtime("wrong_password", encoded)

            # Encode should get called once ...
            self.assertEqual(hasher.encode.call_count, 1)

            # ... with the original salt and 5 iterations.
            algorithm, iterations, salt, hash = encoded.split("$", 3)
            expected_call = (("wrong_password", salt, 5),)
            self.assertEqual(hasher.encode.call_args, expected_call)

    def test_pbkdf2_upgrade_new_hasher(self):
        hasher = get_hasher("default")
        self.assertEqual("pbkdf2_sha256", hasher.algorithm)
        self.assertNotEqual(hasher.iterations, 1)

        state = {"upgraded": False}

        def setter(password):
            state["upgraded"] = True

        with self.settings(
            PASSWORD_HASHERS=["auth_tests.test_hashers.PBKDF2SingleIterationHasher"]
        ):
            encoded = make_password("letmein")
            algo, iterations, salt, hash = encoded.split("$", 3)
            self.assertEqual(iterations, "1")

            # No upgrade is triggered
            self.assertTrue(check_password("letmein", encoded, setter))
            self.assertFalse(state["upgraded"])

        # Revert to the old iteration count and check if the password would get
        # updated to the new iteration count.
        with self.settings(
            PASSWORD_HASHERS=[
                "django.contrib.auth.hashers.PBKDF2PasswordHasher",
                "auth_tests.test_hashers.PBKDF2SingleIterationHasher",
            ]
        ):
            self.assertTrue(check_password("letmein", encoded, setter))
            self.assertTrue(state["upgraded"])

    def test_check_password_calls_harden_runtime(self):
        hasher = get_hasher("default")
        encoded = make_password("letmein")

        with (
            mock.patch.object(hasher, "harden_runtime"),
            mock.patch.object(hasher, "must_update", return_value=True),
        ):
            # Correct password supplied, no hardening needed
            check_password("letmein", encoded)
            self.assertEqual(hasher.harden_runtime.call_count, 0)

            # Wrong password supplied, hardening needed
            check_password("wrong_password", encoded)
            self.assertEqual(hasher.harden_runtime.call_count, 1)

    def test_check_password_calls_make_password_to_fake_runtime(self):
        hasher = get_hasher("default")
        cases = [
            (None, None, None),  # no plain text password provided
            ("foo", make_password(password=None), None),  # unusable encoded
            ("letmein", make_password(password="letmein"), ValueError),  # valid encoded
        ]
        for password, encoded, hasher_side_effect in cases:
            with (
                self.subTest(encoded=encoded),
                mock.patch(
                    "django.contrib.auth.hashers.identify_hasher",
                    side_effect=hasher_side_effect,
                ) as mock_identify_hasher,
                mock.patch(
                    "django.contrib.auth.hashers.make_password"
                ) as mock_make_password,
                mock.patch(
                    "django.contrib.auth.hashers.get_random_string",
                    side_effect=lambda size: "x" * size,
                ),
                mock.patch.object(hasher, "verify"),
            ):
                # Ensure make_password is called to standardize timing.
                check_password(password, encoded)
                self.assertEqual(hasher.verify.call_count, 0)
                self.assertEqual(mock_identify_hasher.mock_calls, [mock.call(encoded)])
                self.assertEqual(
                    mock_make_password.mock_calls,
                    [mock.call("x" * UNUSABLE_PASSWORD_SUFFIX_LENGTH)],
                )

    def test_encode_invalid_salt(self):
        hasher_classes = [
            MD5PasswordHasher,
            PBKDF2PasswordHasher,
            PBKDF2SHA1PasswordHasher,
            ScryptPasswordHasher,
        ]
        msg = "salt must be provided and cannot contain $."
        for hasher_class in hasher_classes:
            hasher = hasher_class()
            for salt in [None, "", "sea$salt"]:
                with self.subTest(hasher_class.__name__, salt=salt):
                    with self.assertRaisesMessage(ValueError, msg):
                        hasher.encode("password", salt)

    def test_encode_password_required(self):
        hasher_classes = [
            MD5PasswordHasher,
            PBKDF2PasswordHasher,
            PBKDF2SHA1PasswordHasher,
            ScryptPasswordHasher,
        ]
        msg = "password must be provided."
        for hasher_class in hasher_classes:
            hasher = hasher_class()
            with self.subTest(hasher_class.__name__):
                with self.assertRaisesMessage(TypeError, msg):
                    hasher.encode(None, "seasalt")


class BasePasswordHasherTests(SimpleTestCase):
    not_implemented_msg = "subclasses of BasePasswordHasher must provide %s() method"

    def setUp(self):
        self.hasher = BasePasswordHasher()

    def test_load_library_no_algorithm(self):
        msg = "Hasher 'BasePasswordHasher' doesn't specify a library attribute"
        with self.assertRaisesMessage(ValueError, msg):
            self.hasher._load_library()

    def test_load_library_importerror(self):
        """
        Tests that a ValueError is raised with a meaningful message when the library for a password hashing algorithm cannot be loaded.

        This test case specifically targets the situation where the algorithm's library is not a valid Python module, resulting in an Import Error.

        The expected error message includes the name of the algorithm and the reason for the failure, providing helpful feedback for users and developers.

        """
        PlainHasher = type(
            "PlainHasher",
            (BasePasswordHasher,),
            {"algorithm": "plain", "library": "plain"},
        )
        msg = "Couldn't load 'PlainHasher' algorithm library: No module named 'plain'"
        with self.assertRaisesMessage(ValueError, msg):
            PlainHasher()._load_library()

    def test_attributes(self):
        self.assertIsNone(self.hasher.algorithm)
        self.assertIsNone(self.hasher.library)

    def test_encode(self):
        msg = self.not_implemented_msg % "an encode"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.hasher.encode("password", "salt")

    def test_decode(self):
        msg = self.not_implemented_msg % "a decode"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.hasher.decode("encoded")

    def test_harden_runtime(self):
        msg = (
            "subclasses of BasePasswordHasher should provide a harden_runtime() method"
        )
        with self.assertWarnsMessage(Warning, msg):
            self.hasher.harden_runtime("password", "encoded")

    def test_must_update(self):
        self.assertIs(self.hasher.must_update("encoded"), False)

    def test_safe_summary(self):
        msg = self.not_implemented_msg % "a safe_summary"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.hasher.safe_summary("encoded")

    def test_verify(self):
        msg = self.not_implemented_msg % "a verify"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.hasher.verify("password", "encoded")


@skipUnless(argon2, "argon2-cffi not installed")
@override_settings(PASSWORD_HASHERS=PASSWORD_HASHERS)
class TestUtilsHashPassArgon2(SimpleTestCase):
    def test_argon2(self):
        """

        Tests the functionality of the Argon2 password hasher.

        The Argon2 hasher is a secure password hashing algorithm that is designed to be
        resistant to GPU-based attacks and other forms of brute force attacks. This test
        ensures that the Argon2 hasher is working correctly by checking the following:

        * That passwords can be hashed and verified correctly
        * That the hashed password starts with the expected prefix
        * That the password verification function returns the correct result
        * That the password identification function can correctly identify the hashing algorithm used
        * That the password hasher can handle blank passwords and passwords with special characters
        * That the password hasher can correctly update passwords with weak salts

        """
        encoded = make_password("lètmein", hasher="argon2")
        self.assertTrue(is_password_usable(encoded))
        self.assertTrue(encoded.startswith("argon2$argon2id$"))
        self.assertTrue(check_password("lètmein", encoded))
        self.assertFalse(check_password("lètmeinz", encoded))
        self.assertEqual(identify_hasher(encoded).algorithm, "argon2")
        # Blank passwords
        blank_encoded = make_password("", hasher="argon2")
        self.assertTrue(blank_encoded.startswith("argon2$argon2id$"))
        self.assertTrue(is_password_usable(blank_encoded))
        self.assertTrue(check_password("", blank_encoded))
        self.assertFalse(check_password(" ", blank_encoded))
        # Old hashes without version attribute
        encoded = (
            "argon2$argon2i$m=8,t=1,p=1$c29tZXNhbHQ$gwQOXSNhxiOxPOA0+PY10P9QFO"
            "4NAYysnqRt1GSQLE55m+2GYDt9FEjPMHhP2Cuf0nOEXXMocVrsJAtNSsKyfg"
        )
        self.assertTrue(check_password("secret", encoded))
        self.assertFalse(check_password("wrong", encoded))
        # Old hashes with version attribute.
        encoded = "argon2$argon2i$v=19$m=8,t=1,p=1$c2FsdHNhbHQ$YC9+jJCrQhs5R6db7LlN8Q"
        self.assertIs(check_password("secret", encoded), True)
        self.assertIs(check_password("wrong", encoded), False)
        # Salt entropy check.
        hasher = get_hasher("argon2")
        encoded_weak_salt = make_password("lètmein", "iodizedsalt", "argon2")
        encoded_strong_salt = make_password("lètmein", hasher.salt(), "argon2")
        self.assertIs(hasher.must_update(encoded_weak_salt), True)
        self.assertIs(hasher.must_update(encoded_strong_salt), False)

    def test_argon2_decode(self):
        salt = "abcdefghijk"
        encoded = make_password("lètmein", salt=salt, hasher="argon2")
        hasher = get_hasher("argon2")
        decoded = hasher.decode(encoded)
        self.assertEqual(decoded["memory_cost"], hasher.memory_cost)
        self.assertEqual(decoded["parallelism"], hasher.parallelism)
        self.assertEqual(decoded["salt"], salt)
        self.assertEqual(decoded["time_cost"], hasher.time_cost)

    def test_argon2_upgrade(self):
        self._test_argon2_upgrade("time_cost", "time cost", 1)
        self._test_argon2_upgrade("memory_cost", "memory cost", 64)
        self._test_argon2_upgrade("parallelism", "parallelism", 1)

    def test_argon2_version_upgrade(self):
        hasher = get_hasher("argon2")
        state = {"upgraded": False}
        encoded = (
            "argon2$argon2id$v=19$m=102400,t=2,p=8$Y041dExhNkljRUUy$TMa6A8fPJh"
            "CAUXRhJXCXdw"
        )

        def setter(password):
            state["upgraded"] = True

        old_m = hasher.memory_cost
        old_t = hasher.time_cost
        old_p = hasher.parallelism
        try:
            hasher.memory_cost = 8
            hasher.time_cost = 1
            hasher.parallelism = 1
            self.assertTrue(check_password("secret", encoded, setter, "argon2"))
            self.assertTrue(state["upgraded"])
        finally:
            hasher.memory_cost = old_m
            hasher.time_cost = old_t
            hasher.parallelism = old_p

    def _test_argon2_upgrade(self, attr, summary_key, new_value):
        hasher = get_hasher("argon2")
        self.assertEqual("argon2", hasher.algorithm)
        self.assertNotEqual(getattr(hasher, attr), new_value)

        old_value = getattr(hasher, attr)
        try:
            # Generate hash with attr set to 1
            setattr(hasher, attr, new_value)
            encoded = make_password("letmein", hasher="argon2")
            attr_value = hasher.safe_summary(encoded)[summary_key]
            self.assertEqual(attr_value, new_value)

            state = {"upgraded": False}

            def setter(password):
                state["upgraded"] = True

            # No upgrade is triggered.
            self.assertTrue(check_password("letmein", encoded, setter, "argon2"))
            self.assertFalse(state["upgraded"])

            # Revert to the old rounds count and ...
            setattr(hasher, attr, old_value)

            # ... check if the password would get updated to the new count.
            self.assertTrue(check_password("letmein", encoded, setter, "argon2"))
            self.assertTrue(state["upgraded"])
        finally:
            setattr(hasher, attr, old_value)


@skipUnless(scrypt, "scrypt not available")
@override_settings(PASSWORD_HASHERS=PASSWORD_HASHERS)
class TestUtilsHashPassScrypt(SimpleTestCase):
    def test_scrypt(self):
        """
        Tests the functionality of the scrypt password hashing algorithm.

        This test case verifies that passwords can be successfully hashed and verified using the scrypt algorithm.
        It checks the following scenarios:

        * Hashing and verifying a non-empty password
        * Hashing and verifying an empty password
        * Identifying the hashing algorithm used for a given password

        The test ensures that the scrypt algorithm correctly handles password hashing, verification, and identification,
        including edge cases such as empty passwords. It validates the correctness of the hashed password format and
        the ability to check passwords against the hashed value.
        """
        encoded = make_password("lètmein", "seasalt", "scrypt")
        self.assertEqual(
            encoded,
            "scrypt$16384$seasalt$8$5$ECMIUp+LMxMSK8xB/IVyba+KYGTI7FTnet025q/1f"
            "/vBAVnnP3hdYqJuRi+mJn6ji6ze3Fbb7JEFPKGpuEf5vw==",
        )
        self.assertIs(is_password_usable(encoded), True)
        self.assertIs(check_password("lètmein", encoded), True)
        self.assertIs(check_password("lètmeinz", encoded), False)
        self.assertEqual(identify_hasher(encoded).algorithm, "scrypt")
        # Blank passwords.
        blank_encoded = make_password("", "seasalt", "scrypt")
        self.assertIs(blank_encoded.startswith("scrypt$"), True)
        self.assertIs(is_password_usable(blank_encoded), True)
        self.assertIs(check_password("", blank_encoded), True)
        self.assertIs(check_password(" ", blank_encoded), False)

    def test_scrypt_decode(self):
        encoded = make_password("lètmein", "seasalt", "scrypt")
        hasher = get_hasher("scrypt")
        decoded = hasher.decode(encoded)
        tests = [
            ("block_size", hasher.block_size),
            ("parallelism", hasher.parallelism),
            ("salt", "seasalt"),
            ("work_factor", hasher.work_factor),
        ]
        for key, excepted in tests:
            with self.subTest(key=key):
                self.assertEqual(decoded[key], excepted)

    def _test_scrypt_upgrade(self, attr, summary_key, new_value):
        hasher = get_hasher("scrypt")
        self.assertEqual(hasher.algorithm, "scrypt")
        self.assertNotEqual(getattr(hasher, attr), new_value)

        old_value = getattr(hasher, attr)
        try:
            # Generate hash with attr set to the new value.
            setattr(hasher, attr, new_value)
            encoded = make_password("lètmein", "seasalt", "scrypt")
            attr_value = hasher.safe_summary(encoded)[summary_key]
            self.assertEqual(attr_value, new_value)

            state = {"upgraded": False}

            def setter(password):
                state["upgraded"] = True

            # No update is triggered.
            self.assertIs(check_password("lètmein", encoded, setter, "scrypt"), True)
            self.assertIs(state["upgraded"], False)
            # Revert to the old value.
            setattr(hasher, attr, old_value)
            # Password is updated.
            self.assertIs(check_password("lètmein", encoded, setter, "scrypt"), True)
            self.assertIs(state["upgraded"], True)
        finally:
            setattr(hasher, attr, old_value)

    def test_scrypt_upgrade(self):
        tests = [
            ("work_factor", "work factor", 2**11),
            ("block_size", "block size", 10),
            ("parallelism", "parallelism", 2),
        ]
        for attr, summary_key, new_value in tests:
            with self.subTest(attr=attr):
                self._test_scrypt_upgrade(attr, summary_key, new_value)
