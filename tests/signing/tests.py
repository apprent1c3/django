import datetime

from django.core import signing
from django.test import SimpleTestCase, override_settings
from django.test.utils import freeze_time
from django.utils.crypto import InvalidAlgorithm


class TestSigner(SimpleTestCase):
    def test_signature(self):
        """
        Tests the signature generation functionality of the Signer class, verifying that signatures are correctly calculated using the provided secret key and that different keys produce different signatures.
        """
        signer = signing.Signer(key="predictable-secret")
        signer2 = signing.Signer(key="predictable-secret2")
        for s in (
            b"hello",
            b"3098247:529:087:",
            "\u2019".encode(),
        ):
            self.assertEqual(
                signer.signature(s),
                signing.base64_hmac(
                    signer.salt + "signer",
                    s,
                    "predictable-secret",
                    algorithm=signer.algorithm,
                ),
            )
            self.assertNotEqual(signer.signature(s), signer2.signature(s))

    def test_signature_with_salt(self):
        signer = signing.Signer(key="predictable-secret", salt="extra-salt")
        self.assertEqual(
            signer.signature("hello"),
            signing.base64_hmac(
                "extra-salt" + "signer",
                "hello",
                "predictable-secret",
                algorithm=signer.algorithm,
            ),
        )
        self.assertNotEqual(
            signing.Signer(key="predictable-secret", salt="one").signature("hello"),
            signing.Signer(key="predictable-secret", salt="two").signature("hello"),
        )

    def test_custom_algorithm(self):
        signer = signing.Signer(key="predictable-secret", algorithm="sha512")
        self.assertEqual(
            signer.signature("hello"),
            "Usf3uVQOZ9m6uPfVonKR-EBXjPe7bjMbp3_Fq8MfsptgkkM1ojidN0BxYaT5HAEN1"
            "VzO9_jVu7R-VkqknHYNvw",
        )

    def test_invalid_algorithm(self):
        signer = signing.Signer(key="predictable-secret", algorithm="whatever")
        msg = "'whatever' is not an algorithm accepted by the hashlib module."
        with self.assertRaisesMessage(InvalidAlgorithm, msg):
            signer.sign("hello")

    def test_sign_unsign(self):
        """
        Verifies that the sign and unsign operations are reversible, ensuring data integrity by checking that the original input can be recovered after signing and then unsigning.
        """
        signer = signing.Signer(key="predictable-secret")
        examples = [
            "q;wjmbk;wkmb",
            "3098247529087",
            "3098247:529:087:",
            "jkw osanteuh ,rcuh nthu aou oauh ,ud du",
            "\u2019",
        ]
        for example in examples:
            signed = signer.sign(example)
            self.assertIsInstance(signed, str)
            self.assertNotEqual(example, signed)
            self.assertEqual(example, signer.unsign(signed))

    def test_sign_unsign_non_string(self):
        """

        Verifies that the Signer class can correctly sign and unsign non-string values.

        The test checks that signing various types of non-string values (e.g. integers, floats, booleans, dates) 
        produces a string signature, and that the original value can be recovered by unsigning this signature.

        """
        signer = signing.Signer(key="predictable-secret")
        values = [
            123,
            1.23,
            True,
            datetime.date.today(),
        ]
        for value in values:
            with self.subTest(value):
                signed = signer.sign(value)
                self.assertIsInstance(signed, str)
                self.assertNotEqual(signed, value)
                self.assertEqual(signer.unsign(signed), str(value))

    def test_unsign_detects_tampering(self):
        """
        Tests that the unsign function correctly detects and raises an exception when the signed value has been tampered with.
        """
        signer = signing.Signer(key="predictable-secret")
        value = "Another string"
        signed_value = signer.sign(value)
        transforms = (
            lambda s: s.upper(),
            lambda s: s + "a",
            lambda s: "a" + s[1:],
            lambda s: s.replace(":", ""),
        )
        self.assertEqual(value, signer.unsign(signed_value))
        for transform in transforms:
            with self.assertRaises(signing.BadSignature):
                signer.unsign(transform(signed_value))

    def test_sign_unsign_object(self):
        """

        Verifies the correct signing and un-signing of various object types using a signer.

        The function tests that signing an object produces a different result, 
        and that the original object can be recovered using the unsign method, 
        with and without compression.

        """
        signer = signing.Signer(key="predictable-secret")
        tests = [
            ["a", "list"],
            "a string \u2019",
            {"a": "dictionary"},
        ]
        for obj in tests:
            with self.subTest(obj=obj):
                signed_obj = signer.sign_object(obj)
                self.assertNotEqual(obj, signed_obj)
                self.assertEqual(obj, signer.unsign_object(signed_obj))
                signed_obj = signer.sign_object(obj, compress=True)
                self.assertNotEqual(obj, signed_obj)
                self.assertEqual(obj, signer.unsign_object(signed_obj))

    def test_dumps_loads(self):
        """
        Tests the reversibility of dumps and loads operations on JSON serializable objects, 
        ensuring that signing and loading the data results in the original object, 
        with and without compression.
        """
        objects = [
            ["a", "list"],
            "a string \u2019",
            {"a": "dictionary"},
        ]
        for o in objects:
            self.assertNotEqual(o, signing.dumps(o))
            self.assertEqual(o, signing.loads(signing.dumps(o)))
            self.assertNotEqual(o, signing.dumps(o, compress=True))
            self.assertEqual(o, signing.loads(signing.dumps(o, compress=True)))

    def test_decode_detects_tampering(self):
        """
        Tests that decoding with signing loads raises an exception when the encoded object has been tampered with.
        """
        transforms = (
            lambda s: s.upper(),
            lambda s: s + "a",
            lambda s: "a" + s[1:],
            lambda s: s.replace(":", ""),
        )
        value = {
            "foo": "bar",
            "baz": 1,
        }
        encoded = signing.dumps(value)
        self.assertEqual(value, signing.loads(encoded))
        for transform in transforms:
            with self.assertRaises(signing.BadSignature):
                signing.loads(transform(encoded))

    def test_works_with_non_ascii_keys(self):
        binary_key = b"\xe7"  # Set some binary (non-ASCII key)

        s = signing.Signer(key=binary_key)
        self.assertEqual(
            "foo:EE4qGC5MEKyQG5msxYA0sBohAxLC0BJf8uRhemh0BGU",
            s.sign("foo"),
        )

    def test_valid_sep(self):
        separators = ["/", "*sep*", ","]
        for sep in separators:
            signer = signing.Signer(key="predictable-secret", sep=sep)
            self.assertEqual(
                "foo%sjZQoX_FtSO70jX9HLRGg2A_2s4kdDBxz1QoO_OpEQb0" % sep,
                signer.sign("foo"),
            )

    def test_invalid_sep(self):
        """
        Tests that the Signer class raises a ValueError when initialized with an invalid separator, such as an empty string, a single hyphen, or a string containing only alphanumeric characters, hyphens, or underscores.
        """
        msg = (
            "Unsafe Signer separator: %r (cannot be empty or consist of only A-z0-9-_=)"
        )
        separators = ["", "-", "abc"]
        for sep in separators:
            with self.assertRaisesMessage(ValueError, msg % sep):
                signing.Signer(sep=sep)

    def test_verify_with_non_default_key(self):
        old_signer = signing.Signer(key="secret")
        new_signer = signing.Signer(
            key="newsecret", fallback_keys=["othersecret", "secret"]
        )
        signed = old_signer.sign("abc")
        self.assertEqual(new_signer.unsign(signed), "abc")

    def test_sign_unsign_multiple_keys(self):
        """The default key is a valid verification key."""
        signer = signing.Signer(key="secret", fallback_keys=["oldsecret"])
        signed = signer.sign("abc")
        self.assertEqual(signer.unsign(signed), "abc")

    @override_settings(
        SECRET_KEY="secret",
        SECRET_KEY_FALLBACKS=["oldsecret"],
    )
    def test_sign_unsign_ignore_secret_key_fallbacks(self):
        """
        Tests that signing and verifying ignores secret key fallbacks when explicitly disabled.

         Verifies that a signature created with an old secret key cannot be verified with a signer
         that has no fallback keys, resulting in a BadSignature exception.
        """
        old_signer = signing.Signer(key="oldsecret")
        signed = old_signer.sign("abc")
        signer = signing.Signer(fallback_keys=[])
        with self.assertRaises(signing.BadSignature):
            signer.unsign(signed)

    @override_settings(
        SECRET_KEY="secret",
        SECRET_KEY_FALLBACKS=["oldsecret"],
    )
    def test_default_keys_verification(self):
        old_signer = signing.Signer(key="oldsecret")
        signed = old_signer.sign("abc")
        signer = signing.Signer()
        self.assertEqual(signer.unsign(signed), "abc")


class TestTimestampSigner(SimpleTestCase):
    def test_timestamp_signer(self):
        """
        Tests the TimestampSigner class to ensure it correctly signs and unsigns values 
        with a timestamp, and handles signature expiration based on the max_age parameter.
        """
        value = "hello"
        with freeze_time(123456789):
            signer = signing.TimestampSigner(key="predictable-key")
            ts = signer.sign(value)
            self.assertNotEqual(ts, signing.Signer(key="predictable-key").sign(value))
            self.assertEqual(signer.unsign(ts), value)

        with freeze_time(123456800):
            self.assertEqual(signer.unsign(ts, max_age=12), value)
            # max_age parameter can also accept a datetime.timedelta object
            self.assertEqual(
                signer.unsign(ts, max_age=datetime.timedelta(seconds=11)), value
            )
            with self.assertRaises(signing.SignatureExpired):
                signer.unsign(ts, max_age=10)


class TestBase62(SimpleTestCase):
    def test_base62(self):
        tests = [-(10**10), 10**10, 1620378259, *range(-100, 100)]
        for i in tests:
            self.assertEqual(i, signing.b62_decode(signing.b62_encode(i)))
