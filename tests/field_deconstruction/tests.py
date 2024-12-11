from django.apps import apps
from django.db import models
from django.test import SimpleTestCase, override_settings
from django.test.utils import isolate_lru_cache
from django.utils.choices import normalize_choices


class FieldDeconstructionTests(SimpleTestCase):
    """
    Tests the deconstruct() method on all core fields.
    """

    def test_name(self):
        """
        Tests the outputting of the correct name if assigned one.
        """
        # First try using a "normal" field
        field = models.CharField(max_length=65)
        name, path, args, kwargs = field.deconstruct()
        self.assertIsNone(name)
        field.set_attributes_from_name("is_awesome_test")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(name, "is_awesome_test")
        # Now try with a ForeignKey
        field = models.ForeignKey("some_fake.ModelName", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertIsNone(name)
        field.set_attributes_from_name("author")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(name, "author")

    def test_db_tablespace(self):
        """
        Tests the functionality of the db_tablespace parameter on model fields.

        Verifies that the db_tablespace argument is correctly deconstructed from model fields,
        both when a default tablespace is specified in the settings and when it is explicitly 
        defined on the field. Ensures that the deconstructed arguments and keyword arguments 
        are as expected in various scenarios, including when no tablespace is specified, 
        when a default tablespace is set, and when a tablespace is explicitly set on the field.

        This test case covers the interaction between the model field's db_tablespace parameter 
        and the DEFAULT_DB_TABLESPACE setting, ensuring that the deconstruction process 
        accurately reflects the tablespace configuration in different situations.
        """
        field = models.Field()
        _, _, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        # With a DEFAULT_DB_TABLESPACE.
        with self.settings(DEFAULT_DB_TABLESPACE="foo"):
            _, _, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        # With a db_tablespace.
        field = models.Field(db_tablespace="foo")
        _, _, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"db_tablespace": "foo"})
        # With a db_tablespace equal to DEFAULT_DB_TABLESPACE.
        with self.settings(DEFAULT_DB_TABLESPACE="foo"):
            _, _, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"db_tablespace": "foo"})

    def test_auto_field(self):
        """

        Tests the deconstruction of an AutoField instance.

        Verifies that the deconstruction of an AutoField with primary_key=True
        correctly returns the field's path, arguments, and keyword arguments.

        """
        field = models.AutoField(primary_key=True)
        field.set_attributes_from_name("id")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.AutoField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"primary_key": True})

    def test_big_integer_field(self):
        field = models.BigIntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.BigIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_boolean_field(self):
        field = models.BooleanField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.BooleanField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.BooleanField(default=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.BooleanField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"default": True})

    def test_char_field(self):
        """
        Tests the deconstruction of a CharField instance into its constituent parts.

        This test ensures that the deconstruct method of CharField correctly returns the 
        field's name, path, positional arguments, and keyword arguments. It covers both 
        simple and complex field definitions, including those with null and blank attributes.

        The test verifies that the deconstructed path matches the expected 'django.db.models.CharField' 
        and that the keyword arguments match the field's specified parameters, such as max_length, null, and blank.
        """
        field = models.CharField(max_length=65)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.CharField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 65})
        field = models.CharField(max_length=65, null=True, blank=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.CharField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 65, "null": True, "blank": True})

    def test_char_field_choices(self):
        """
        Tests the deconstruction of a CharField with choices.

        Verifies that a CharField instance with specified choices can be correctly broken down into its constituent parts,
        including its path, positional arguments, and keyword arguments. Specifically, it checks that the path points to 
        the CharField class, that there are no positional arguments, and that the keyword arguments include the expected 
        choices and max_length parameters. This ensures that the field can be accurately reconstructed from its deconstructed 
        components.
        """
        field = models.CharField(max_length=1, choices=(("A", "One"), ("B", "Two")))
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.CharField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs, {"choices": [("A", "One"), ("B", "Two")], "max_length": 1}
        )

    def test_choices_iterator(self):
        """
        Tests the deconstruction of an IntegerField with choices into its constituent parts, 
        verifying that the field's path, arguments, and keyword arguments are correctly identified.

        The test checks that the field's path matches the expected model field path, 
        that no positional arguments are present, and that the keyword arguments contain 
        the expected choices as a list of tuples. This ensures that the field can be 
        accurately reconstructed from its deconstructed components.
        """
        field = models.IntegerField(choices=((i, str(i)) for i in range(3)))
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.IntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"choices": [(0, "0"), (1, "1"), (2, "2")]})

    def test_choices_iterable(self):
        # Pass an iterable (but not an iterator) to choices.
        """

        Tests that the deconstruction of an IntegerField with string choices results in the correct path and keyword arguments.

        The function verifies that the deconstructed path matches the expected Django model field path and that the keyword arguments contain the normalized choices.

        """
        field = models.IntegerField(choices="012345")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.IntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"choices": normalize_choices("012345")})

    def test_choices_callable(self):
        def get_choices():
            return [(i, str(i)) for i in range(3)]

        field = models.IntegerField(choices=get_choices)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.IntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"choices": get_choices})

    def test_csi_field(self):
        """
        Test the deconstruction of a CommaSeparatedIntegerField.

        This test case checks that a CommaSeparatedIntegerField can be properly deconstructed into its constituent parts, 
        including its path, arguments, and keyword arguments. It verifies that the path matches the expected string, 
        and that the arguments and keyword arguments match the values used when the field was created.
        """
        field = models.CommaSeparatedIntegerField(max_length=100)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.CommaSeparatedIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 100})

    def test_date_field(self):
        """
        Tests the deconstruction of a DateField in Django models. 

        This function verifies that a DateField can be correctly deconstructed into its constituent parts, 
        including its path, arguments, and keyword arguments. It checks the deconstruction of a basic DateField 
        and one with the auto_now parameter set to True, ensuring that the resulting path, arguments, and keyword 
        arguments match the expected values. The test asserts that the path is always 'django.db.models.DateField', 
        and that the arguments list remains empty, while the keyword arguments dictionary reflects any specified 
        parameters, such as 'auto_now'.
        """
        field = models.DateField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DateField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.DateField(auto_now=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DateField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"auto_now": True})

    def test_datetime_field(self):
        field = models.DateTimeField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DateTimeField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.DateTimeField(auto_now_add=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DateTimeField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"auto_now_add": True})
        # Bug #21785
        field = models.DateTimeField(auto_now=True, auto_now_add=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DateTimeField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"auto_now_add": True, "auto_now": True})

    def test_decimal_field(self):
        field = models.DecimalField(max_digits=5, decimal_places=2)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DecimalField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_digits": 5, "decimal_places": 2})

    def test_decimal_field_0_decimal_places(self):
        """
        A DecimalField with decimal_places=0 should work (#22272).
        """
        field = models.DecimalField(max_digits=5, decimal_places=0)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.DecimalField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_digits": 5, "decimal_places": 0})

    def test_email_field(self):
        field = models.EmailField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.EmailField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 254})
        field = models.EmailField(max_length=255)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.EmailField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 255})

    def test_file_field(self):
        field = models.FileField(upload_to="foo/bar")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.FileField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"upload_to": "foo/bar"})
        # Test max_length
        field = models.FileField(upload_to="foo/bar", max_length=200)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.FileField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"upload_to": "foo/bar", "max_length": 200})

    def test_file_path_field(self):
        field = models.FilePathField(match=r".*\.txt$")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.FilePathField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"match": r".*\.txt$"})
        field = models.FilePathField(recursive=True, allow_folders=True, max_length=123)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.FilePathField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs, {"recursive": True, "allow_folders": True, "max_length": 123}
        )

    def test_float_field(self):
        field = models.FloatField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.FloatField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_foreign_key(self):
        # Test basic pointing
        from django.contrib.auth.models import Permission

        field = models.ForeignKey("auth.Permission", models.CASCADE)
        field.remote_field.model = Permission
        field.remote_field.field_name = "id"
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "on_delete": models.CASCADE})
        self.assertFalse(hasattr(kwargs["to"], "setting_name"))
        # Test swap detection for swappable model
        field = models.ForeignKey("auth.User", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user", "on_delete": models.CASCADE})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")
        # Swap detection for lowercase swappable model.
        field = models.ForeignKey("auth.user", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user", "on_delete": models.CASCADE})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")
        # Test nonexistent (for now) model
        field = models.ForeignKey("something.Else", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "something.else", "on_delete": models.CASCADE})
        # Test on_delete
        field = models.ForeignKey("auth.User", models.SET_NULL)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user", "on_delete": models.SET_NULL})
        # Test to_field preservation
        field = models.ForeignKey("auth.Permission", models.CASCADE, to_field="foobar")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "to_field": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test related_name preservation
        field = models.ForeignKey(
            "auth.Permission", models.CASCADE, related_name="foobar"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "related_name": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test related_query_name
        field = models.ForeignKey(
            "auth.Permission", models.CASCADE, related_query_name="foobar"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "related_query_name": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test limit_choices_to
        field = models.ForeignKey(
            "auth.Permission", models.CASCADE, limit_choices_to={"foo": "bar"}
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "limit_choices_to": {"foo": "bar"},
                "on_delete": models.CASCADE,
            },
        )
        # Test unique
        field = models.ForeignKey("auth.Permission", models.CASCADE, unique=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {"to": "auth.permission", "unique": True, "on_delete": models.CASCADE},
        )

    @override_settings(AUTH_USER_MODEL="auth.Permission")
    def test_foreign_key_swapped(self):
        """

        Tests the behavior of a ForeignKey field with swappable settings.

        This test case verifies that a ForeignKey field correctly handles swappable settings,
        specifically when the related model is swapped using the AUTH_USER_MODEL setting.
        It checks that the field's deconstructed path, args, and kwargs are as expected,
        and that the 'to' attribute of the kwargs dictionary has the correct setting name.

        The test covers two scenarios: one where the related model is specified with a capitalize
        name ('auth.Permission') and another where it is specified with a lowercase name ('auth.permission').
        In both cases, it ensures that the field's behavior is consistent and correct.

        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            # It doesn't matter that we swapped out user for permission;
            # there's no validation. We just want to check the setting stuff works.
            field = models.ForeignKey("auth.Permission", models.CASCADE)
            name, path, args, kwargs = field.deconstruct()

        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "on_delete": models.CASCADE})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")

        # Model names are case-insensitive.
        with isolate_lru_cache(apps.get_swappable_settings_name):
            # It doesn't matter that we swapped out user for permission;
            # there's no validation. We just want to check the setting stuff
            # works.
            field = models.ForeignKey("auth.permission", models.CASCADE)
            name, path, args, kwargs = field.deconstruct()

        self.assertEqual(path, "django.db.models.ForeignKey")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "on_delete": models.CASCADE})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")

    def test_one_to_one(self):
        # Test basic pointing
        """
        Tests the deconstruction of a OneToOneField.

            The OneToOneField deconstruction process is verified to produce the correct
            name, path, arguments, and keyword arguments. The test checks various scenarios,
            including different related model names, on_delete actions, to_field, related_name,
            related_query_name, and limit_choices_to parameters.

            The test ensures that the deconstructed OneToOneField instance matches the expected
            values, which include the path to the OneToOneField class, empty argument list,
            and keyword arguments that correctly reflect the field's parameters.

        """
        from django.contrib.auth.models import Permission

        field = models.OneToOneField("auth.Permission", models.CASCADE)
        field.remote_field.model = Permission
        field.remote_field.field_name = "id"
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "on_delete": models.CASCADE})
        self.assertFalse(hasattr(kwargs["to"], "setting_name"))
        # Test swap detection for swappable model
        field = models.OneToOneField("auth.User", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user", "on_delete": models.CASCADE})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")
        # Test nonexistent (for now) model
        field = models.OneToOneField("something.Else", models.CASCADE)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "something.else", "on_delete": models.CASCADE})
        # Test on_delete
        field = models.OneToOneField("auth.User", models.SET_NULL)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user", "on_delete": models.SET_NULL})
        # Test to_field
        field = models.OneToOneField(
            "auth.Permission", models.CASCADE, to_field="foobar"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "to_field": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test related_name
        field = models.OneToOneField(
            "auth.Permission", models.CASCADE, related_name="foobar"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "related_name": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test related_query_name
        field = models.OneToOneField(
            "auth.Permission", models.CASCADE, related_query_name="foobar"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "related_query_name": "foobar",
                "on_delete": models.CASCADE,
            },
        )
        # Test limit_choices_to
        field = models.OneToOneField(
            "auth.Permission", models.CASCADE, limit_choices_to={"foo": "bar"}
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "auth.permission",
                "limit_choices_to": {"foo": "bar"},
                "on_delete": models.CASCADE,
            },
        )
        # Test unique
        field = models.OneToOneField("auth.Permission", models.CASCADE, unique=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.OneToOneField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "on_delete": models.CASCADE})

    def test_image_field(self):
        """
        Tests the deconstruction of an ImageField in a Django model.

        Verifies that the field correctly decomposes into its constituent parts,
        including the field path and keyword arguments. This ensures that the field
        can be properly reconstructed and used in a model.

        The test case checks the following:
        - The field path matches the expected Django ImageField path.
        - The positional arguments are empty.
        - The keyword arguments include the expected upload_to, width_field, and height_field settings.

        This test is crucial for ensuring the correct functionality of ImageFields in Django models,
        particularly when working with image uploads and processing.
        """
        field = models.ImageField(
            upload_to="foo/barness", width_field="width", height_field="height"
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ImageField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "upload_to": "foo/barness",
                "width_field": "width",
                "height_field": "height",
            },
        )

    def test_integer_field(self):
        """
        Tests that the IntegerField from django.db.models correctly deconstructs into its constituent parts, including its path, arguments, and keyword arguments, ensuring that they match the expected values.
        """
        field = models.IntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.IntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_ip_address_field(self):
        """
        Tests the deconstruction of an IPAddressField.

        Verifies that the field's deconstruction returns the correct path, arguments, and keyword arguments.
        The expected path is 'django.db.models.IPAddressField' with no arguments or keyword arguments.
        This test ensures that the IPAddressField can be properly recreated from its deconstructed components.
        """
        field = models.IPAddressField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.IPAddressField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_generic_ip_address_field(self):
        field = models.GenericIPAddressField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.GenericIPAddressField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.GenericIPAddressField(protocol="IPv6")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.GenericIPAddressField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"protocol": "IPv6"})

    def test_many_to_many_field(self):
        # Test normal
        """
        Tests the deconstruction of ManyToManyField instances.

        Verifies that the deconstruct method correctly returns the field name, path, 
        arguments, and keyword arguments for various ManyToManyField configurations, 
        including fields with and without through models, custom database tables, 
        related names, related query names, and limit choices to filters.

        Ensures that the returned path is always 'django.db.models.ManyToManyField' 
        and that the returned arguments are always an empty list. The keyword arguments 
        returned include the 'to' model, as well as any additional keyword arguments 
        passed to the field, such as 'through', 'db_table', 'related_name', 
        'related_query_name', and 'limit_choices_to'.

        Also checks that the 'to' model has a setting name when referring to 
         AUTH_USER_MODEL and does not have a setting name for other models.
        """
        field = models.ManyToManyField("auth.Permission")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission"})
        self.assertFalse(hasattr(kwargs["to"], "setting_name"))
        # Test swappable
        field = models.ManyToManyField("auth.User")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.user"})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")
        # Test through
        field = models.ManyToManyField("auth.Permission", through="auth.Group")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "through": "auth.Group"})
        # Test custom db_table
        field = models.ManyToManyField("auth.Permission", db_table="custom_table")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission", "db_table": "custom_table"})
        # Test related_name
        field = models.ManyToManyField("auth.Permission", related_name="custom_table")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs, {"to": "auth.permission", "related_name": "custom_table"}
        )
        # Test related_query_name
        field = models.ManyToManyField("auth.Permission", related_query_name="foobar")
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs, {"to": "auth.permission", "related_query_name": "foobar"}
        )
        # Test limit_choices_to
        field = models.ManyToManyField(
            "auth.Permission", limit_choices_to={"foo": "bar"}
        )
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs, {"to": "auth.permission", "limit_choices_to": {"foo": "bar"}}
        )

    @override_settings(AUTH_USER_MODEL="auth.Permission")
    def test_many_to_many_field_swapped(self):
        """

        Tests the deconstruction of a ManyToManyField when using swappable settings.

        This test case verifies that the ManyToManyField correctly identifies its path,
        arguments, and keyword arguments when the related model is specified as a string
        using the swappable settings. It checks that the deconstructed field's path
        matches the expected path, and that the arguments and keyword arguments are
        correctly determined.

        Specifically, it checks the following:

        * The path of the deconstructed field matches the expected path.
        * The arguments of the deconstructed field are empty.
        * The keyword arguments of the deconstructed field include the 'to' argument
          with the correct setting name.

        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            # It doesn't matter that we swapped out user for permission;
            # there's no validation. We just want to check the setting stuff works.
            field = models.ManyToManyField("auth.Permission")
            name, path, args, kwargs = field.deconstruct()

        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"to": "auth.permission"})
        self.assertEqual(kwargs["to"].setting_name, "AUTH_USER_MODEL")

    def test_many_to_many_field_related_name(self):
        class MyModel(models.Model):
            flag = models.BooleanField(default=True)
            m2m = models.ManyToManyField("self")
            m2m_related_name = models.ManyToManyField(
                "self",
                related_query_name="custom_query_name",
                limit_choices_to={"flag": True},
            )

        name, path, args, kwargs = MyModel.m2m.field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        # deconstruct() should not include attributes which were not passed to
        # the field during initialization.
        self.assertEqual(kwargs, {"to": "field_deconstruction.mymodel"})
        # Passed attributes.
        name, path, args, kwargs = MyModel.m2m_related_name.field.deconstruct()
        self.assertEqual(path, "django.db.models.ManyToManyField")
        self.assertEqual(args, [])
        self.assertEqual(
            kwargs,
            {
                "to": "field_deconstruction.mymodel",
                "related_query_name": "custom_query_name",
                "limit_choices_to": {"flag": True},
            },
        )

    def test_positive_integer_field(self):
        """

        Tests that a PositiveIntegerField can be correctly deconstructed.

        The deconstruction process involves breaking down the field into its constituent
        parts, including the field's path, arguments, and keyword arguments. This test
        ensures that the path is correctly identified as the PositiveIntegerField class
        from Django's database models module, and that the field does not contain any
        additional arguments or keyword arguments.

        The test validates the deconstruction of a PositiveIntegerField by verifying
        that the path, arguments, and keyword arguments are as expected.

        """
        field = models.PositiveIntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.PositiveIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_positive_small_integer_field(self):
        """
        Tests the deconstruction of a PositiveSmallIntegerField.

        Verifies that the deconstructed field returns the correct path, and that
        it does not include any arguments or keyword arguments.

        This test ensures that the PositiveSmallIntegerField behaves as expected
        when decomposed into its constituent parts, which is useful for tasks
        such as serialization and deserialization of model fields.
        """
        field = models.PositiveSmallIntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.PositiveSmallIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_positive_big_integer_field(self):
        """

        Tests the deconstruction of a PositiveBigIntegerField.

        This function verifies that a PositiveBigIntegerField can be successfully deconstructed
        into its constituent parts, including its path, arguments, and keyword arguments.
        It checks that the path matches the expected path for a PositiveBigIntegerField,
        and that no arguments or keyword arguments are present.

        """
        field = models.PositiveBigIntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.PositiveBigIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_slug_field(self):
        """
        Tests the deconstruction of a SlugField.

        Checks that the field can be successfully deconstructed into its constituent parts,
        including the field path, arguments, and keyword arguments. The test covers two
        scenarios: a SlugField with default parameters and one with custom parameters
        (db_index and max_length). The test verifies that the field path is correctly
        identified as 'django.db.models.SlugField', and that the arguments and keyword
        arguments are correctly extracted based on the field's configuration.
        """
        field = models.SlugField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.SlugField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.SlugField(db_index=False, max_length=231)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.SlugField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"db_index": False, "max_length": 231})

    def test_small_integer_field(self):
        field = models.SmallIntegerField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.SmallIntegerField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_text_field(self):
        field = models.TextField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.TextField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

    def test_time_field(self):
        field = models.TimeField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.TimeField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})

        field = models.TimeField(auto_now=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"auto_now": True})

        field = models.TimeField(auto_now_add=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"auto_now_add": True})

    def test_url_field(self):
        """
        Tests the deconstruction of a URLField.

        Checks that the deconstructed path, arguments, and keyword arguments
        are as expected for both a default URLField and one with a specified
        max_length. Verifies that the path correctly references the
        django.db.models.URLField class, and that optional arguments are
        accurately captured in the keyword arguments dictionary.
        """
        field = models.URLField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.URLField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.URLField(max_length=231)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.URLField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"max_length": 231})

    def test_binary_field(self):
        """
        Tests the deconstruction of BinaryField instances.

        Verifies that the deconstruction of BinaryField instances produces the expected
        path, arguments, and keyword arguments. This includes testing fields with and
        without the 'editable' attribute set.

        The test covers the following scenarios:

        * A BinaryField with no additional arguments or keyword arguments
        * A BinaryField with the 'editable' attribute set to True

        Ensures that the deconstructed field path always matches the expected path
        ('django.db.models.BinaryField') and that the arguments and keyword arguments
        are correctly represented in the deconstructed form.
        """
        field = models.BinaryField()
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, "django.db.models.BinaryField")
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {})
        field = models.BinaryField(editable=True)
        name, path, args, kwargs = field.deconstruct()
        self.assertEqual(args, [])
        self.assertEqual(kwargs, {"editable": True})
