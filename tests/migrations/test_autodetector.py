import copy
import functools
import re
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.validators import RegexValidator, validate_slug
from django.db import connection, migrations, models
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import MigrationQuestioner
from django.db.migrations.state import ModelState, ProjectState
from django.db.models.functions import Concat, Lower
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import isolate_lru_cache

from .models import FoodManager, FoodQuerySet


class DeconstructibleObject:
    """
    A custom deconstructible object.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def deconstruct(self):
        return (self.__module__ + "." + self.__class__.__name__, self.args, self.kwargs)


class BaseAutodetectorTests(TestCase):
    def repr_changes(self, changes, include_dependencies=False):
        """
        Returns a formatted string representation of the given changes, listing migrations for each app label, including operations and optional dependencies.
        """
        output = ""
        for app_label, migrations_ in sorted(changes.items()):
            output += "  %s:\n" % app_label
            for migration in migrations_:
                output += "    %s\n" % migration.name
                for operation in migration.operations:
                    output += "      %s\n" % operation
                if include_dependencies:
                    output += "      Dependencies:\n"
                    if migration.dependencies:
                        for dep in migration.dependencies:
                            output += "        %s\n" % (dep,)
                    else:
                        output += "        None\n"
        return output

    def assertNumberMigrations(self, changes, app_label, number):
        if len(changes.get(app_label, [])) != number:
            self.fail(
                "Incorrect number of migrations (%s) for %s (expected %s)\n%s"
                % (
                    len(changes.get(app_label, [])),
                    app_label,
                    number,
                    self.repr_changes(changes),
                )
            )

    def assertMigrationDependencies(self, changes, app_label, position, dependencies):
        """

        Verifies the dependencies of a specific migration in an application.

        Checks that the migration exists at the given position within the application's
        migration history and that its dependencies match the expected ones.

        """
        if not changes.get(app_label):
            self.fail(
                "No migrations found for %s\n%s"
                % (app_label, self.repr_changes(changes))
            )
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No migration at index %s for %s\n%s"
                % (position, app_label, self.repr_changes(changes))
            )
        migration = changes[app_label][position]
        if set(migration.dependencies) != set(dependencies):
            self.fail(
                "Migration dependencies mismatch for %s.%s (expected %s):\n%s"
                % (
                    app_label,
                    migration.name,
                    dependencies,
                    self.repr_changes(changes, include_dependencies=True),
                )
            )

    def assertOperationTypes(self, changes, app_label, position, types):
        """

        Verify that a migration operation at a specific position for a given application label has the expected types.

        This method checks if there are any migrations available for the specified application label, 
        if a migration is present at the given position, and if the operation types match the expected ones.

        :raises AssertionError: If no migrations are found for the application label, 
                                 if no migration is present at the specified position, 
                                 or if the operation types do not match the expected ones.
        :param changes: A dictionary of migrations
        :param app_label: The application label to check
        :param position: The position of the migration to check
        :param types: The expected operation types

        """
        if not changes.get(app_label):
            self.fail(
                "No migrations found for %s\n%s"
                % (app_label, self.repr_changes(changes))
            )
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No migration at index %s for %s\n%s"
                % (position, app_label, self.repr_changes(changes))
            )
        migration = changes[app_label][position]
        real_types = [
            operation.__class__.__name__ for operation in migration.operations
        ]
        if types != real_types:
            self.fail(
                "Operation type mismatch for %s.%s (expected %s):\n%s"
                % (
                    app_label,
                    migration.name,
                    types,
                    self.repr_changes(changes),
                )
            )

    def assertOperationAttributes(
        self, changes, app_label, position, operation_position, **attrs
    ):
        """
        Asserts the specified attributes of an operation in a migration.

        Checks that a migration exists at the specified position for the given app label, 
        and then verifies that the specified operation in that migration has the expected attributes.

        Raises an assertion failure if any of these conditions are not met, providing 
        detailed diagnostic information about the migration and operation in question.
        """
        if not changes.get(app_label):
            self.fail(
                "No migrations found for %s\n%s"
                % (app_label, self.repr_changes(changes))
            )
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No migration at index %s for %s\n%s"
                % (position, app_label, self.repr_changes(changes))
            )
        migration = changes[app_label][position]
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No operation at index %s for %s.%s\n%s"
                % (
                    operation_position,
                    app_label,
                    migration.name,
                    self.repr_changes(changes),
                )
            )
        operation = migration.operations[operation_position]
        for attr, value in attrs.items():
            if getattr(operation, attr, None) != value:
                self.fail(
                    "Attribute mismatch for %s.%s op #%s, %s (expected %r, got %r):\n%s"
                    % (
                        app_label,
                        migration.name,
                        operation_position,
                        attr,
                        value,
                        getattr(operation, attr, None),
                        self.repr_changes(changes),
                    )
                )

    def assertOperationFieldAttributes(
        self, changes, app_label, position, operation_position, **attrs
    ):
        """
        Verifies that the specified operation field attributes match the expected values.

        Checks for the presence of migrations and operations in the provided changes,
        then asserts that the attributes of the operation's field match the given values.

        :param changes: Dictionary of migrations changes.
        :param app_label: Application label to look up migrations.
        :param position: Index of the migration to check.
        :param operation_position: Index of the operation to check within the migration.
        :param attrs: Keyword arguments specifying the field attribute names and expected values.

        """
        if not changes.get(app_label):
            self.fail(
                "No migrations found for %s\n%s"
                % (app_label, self.repr_changes(changes))
            )
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No migration at index %s for %s\n%s"
                % (position, app_label, self.repr_changes(changes))
            )
        migration = changes[app_label][position]
        if len(changes[app_label]) < position + 1:
            self.fail(
                "No operation at index %s for %s.%s\n%s"
                % (
                    operation_position,
                    app_label,
                    migration.name,
                    self.repr_changes(changes),
                )
            )
        operation = migration.operations[operation_position]
        if not hasattr(operation, "field"):
            self.fail(
                "No field attribute for %s.%s op #%s."
                % (
                    app_label,
                    migration.name,
                    operation_position,
                )
            )
        field = operation.field
        for attr, value in attrs.items():
            if getattr(field, attr, None) != value:
                self.fail(
                    "Field attribute mismatch for %s.%s op #%s, field.%s (expected %r, "
                    "got %r):\n%s"
                    % (
                        app_label,
                        migration.name,
                        operation_position,
                        attr,
                        value,
                        getattr(field, attr, None),
                        self.repr_changes(changes),
                    )
                )

    def make_project_state(self, model_states):
        """
        Creates a ProjectState instance from a list of predefined model states.

         Returns a new ProjectState object containing cloned copies of the input model states.
        """
        project_state = ProjectState()
        for model_state in model_states:
            project_state.add_model(model_state.clone())
        return project_state

    def get_changes(self, before_states, after_states, questioner=None):
        """

        Detects changes between two project states.

        Given two project states (before and after) and an optional questioner,
        returns the detected changes. The project states can be provided either
        as ProjectState instances or as raw data, which will be converted to
        ProjectState instances automatically.

        :returns: Detected changes between the two project states

        """
        if not isinstance(before_states, ProjectState):
            before_states = self.make_project_state(before_states)
        if not isinstance(after_states, ProjectState):
            after_states = self.make_project_state(after_states)
        return MigrationAutodetector(
            before_states,
            after_states,
            questioner,
        )._detect_changes()


class AutodetectorTests(BaseAutodetectorTests):
    """
    Tests the migration autodetector.
    """

    author_empty = ModelState(
        "testapp", "Author", [("id", models.AutoField(primary_key=True))]
    )
    author_name = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
        ],
    )
    author_name_null = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, null=True)),
        ],
    )
    author_name_longer = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=400)),
        ],
    )
    author_name_renamed = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("names", models.CharField(max_length=200)),
        ],
    )
    author_name_default = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, default="Ada Lovelace")),
        ],
    )
    author_name_db_default = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, db_default="Ada Lovelace")),
        ],
    )
    author_name_check_constraint = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
        ],
        {
            "constraints": [
                models.CheckConstraint(
                    condition=models.Q(name__contains="Bob"), name="name_contains_bob"
                )
            ]
        },
    )
    author_dates_of_birth_auto_now = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("date_of_birth", models.DateField(auto_now=True)),
            ("date_time_of_birth", models.DateTimeField(auto_now=True)),
            ("time_of_birth", models.TimeField(auto_now=True)),
        ],
    )
    author_dates_of_birth_auto_now_add = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("date_of_birth", models.DateField(auto_now_add=True)),
            ("date_time_of_birth", models.DateTimeField(auto_now_add=True)),
            ("time_of_birth", models.TimeField(auto_now_add=True)),
        ],
    )
    author_name_deconstructible_1 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, default=DeconstructibleObject())),
        ],
    )
    author_name_deconstructible_2 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, default=DeconstructibleObject())),
        ],
    )
    author_name_deconstructible_3 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, default=models.IntegerField())),
        ],
    )
    author_name_deconstructible_4 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200, default=models.IntegerField())),
        ],
    )
    author_name_deconstructible_list_1 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=[DeconstructibleObject(), 123]
                ),
            ),
        ],
    )
    author_name_deconstructible_list_2 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=[DeconstructibleObject(), 123]
                ),
            ),
        ],
    )
    author_name_deconstructible_list_3 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=[DeconstructibleObject(), 999]
                ),
            ),
        ],
    )
    author_name_deconstructible_tuple_1 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=(DeconstructibleObject(), 123)
                ),
            ),
        ],
    )
    author_name_deconstructible_tuple_2 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=(DeconstructibleObject(), 123)
                ),
            ),
        ],
    )
    author_name_deconstructible_tuple_3 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200, default=(DeconstructibleObject(), 999)
                ),
            ),
        ],
    )
    author_name_deconstructible_dict_1 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default={"item": DeconstructibleObject(), "otheritem": 123},
                ),
            ),
        ],
    )
    author_name_deconstructible_dict_2 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default={"item": DeconstructibleObject(), "otheritem": 123},
                ),
            ),
        ],
    )
    author_name_deconstructible_dict_3 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default={"item": DeconstructibleObject(), "otheritem": 999},
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_1 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2"),
                        ),
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c")),
                    ),
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_2 = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2"),
                        ),
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c")),
                    ),
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_changed_arg = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2-changed"),
                        ),
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c")),
                    ),
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_extra_arg = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2"),
                        ),
                        None,
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c")),
                    ),
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_changed_kwarg = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2"),
                        ),
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c-changed")),
                    ),
                ),
            ),
        ],
    )
    author_name_nested_deconstructible_extra_kwarg = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "name",
                models.CharField(
                    max_length=200,
                    default=DeconstructibleObject(
                        DeconstructibleObject(1),
                        (
                            DeconstructibleObject("t1"),
                            DeconstructibleObject("t2"),
                        ),
                        a=DeconstructibleObject("A"),
                        b=DeconstructibleObject(B=DeconstructibleObject("c")),
                        c=None,
                    ),
                ),
            ),
        ],
    )
    author_custom_pk = ModelState(
        "testapp", "Author", [("pk_field", models.IntegerField(primary_key=True))]
    )
    author_with_biography_non_blank = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField()),
            ("biography", models.TextField()),
        ],
    )
    author_with_biography_blank = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(blank=True)),
            ("biography", models.TextField(blank=True)),
        ],
    )
    author_with_book = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
        ],
    )
    author_with_book_order_wrt = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
        ],
        options={"order_with_respect_to": "book"},
    )
    author_renamed_with_book = ModelState(
        "testapp",
        "Writer",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
        ],
    )
    author_with_publisher_string = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("publisher_name", models.CharField(max_length=200)),
        ],
    )
    author_with_publisher = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("publisher", models.ForeignKey("testapp.Publisher", models.CASCADE)),
        ],
    )
    author_with_user = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("user", models.ForeignKey("auth.User", models.CASCADE)),
        ],
    )
    author_with_custom_user = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=200)),
            ("user", models.ForeignKey("thirdapp.CustomUser", models.CASCADE)),
        ],
    )
    author_proxy = ModelState(
        "testapp", "AuthorProxy", [], {"proxy": True}, ("testapp.author",)
    )
    author_proxy_options = ModelState(
        "testapp",
        "AuthorProxy",
        [],
        {
            "proxy": True,
            "verbose_name": "Super Author",
        },
        ("testapp.author",),
    )
    author_proxy_notproxy = ModelState(
        "testapp", "AuthorProxy", [], {}, ("testapp.author",)
    )
    author_proxy_third = ModelState(
        "thirdapp", "AuthorProxy", [], {"proxy": True}, ("testapp.author",)
    )
    author_proxy_third_notproxy = ModelState(
        "thirdapp", "AuthorProxy", [], {}, ("testapp.author",)
    )
    author_proxy_proxy = ModelState(
        "testapp", "AAuthorProxyProxy", [], {"proxy": True}, ("testapp.authorproxy",)
    )
    author_unmanaged = ModelState(
        "testapp", "AuthorUnmanaged", [], {"managed": False}, ("testapp.author",)
    )
    author_unmanaged_managed = ModelState(
        "testapp", "AuthorUnmanaged", [], {}, ("testapp.author",)
    )
    author_unmanaged_default_pk = ModelState(
        "testapp", "Author", [("id", models.AutoField(primary_key=True))]
    )
    author_unmanaged_custom_pk = ModelState(
        "testapp",
        "Author",
        [
            ("pk_field", models.IntegerField(primary_key=True)),
        ],
    )
    author_with_m2m = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("publishers", models.ManyToManyField("testapp.Publisher")),
        ],
    )
    author_with_m2m_blank = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("publishers", models.ManyToManyField("testapp.Publisher", blank=True)),
        ],
    )
    author_with_m2m_through = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "publishers",
                models.ManyToManyField("testapp.Publisher", through="testapp.Contract"),
            ),
        ],
    )
    author_with_renamed_m2m_through = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "publishers",
                models.ManyToManyField("testapp.Publisher", through="testapp.Deal"),
            ),
        ],
    )
    author_with_former_m2m = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
            ("publishers", models.CharField(max_length=100)),
        ],
    )
    author_with_options = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {
            "permissions": [("can_hire", "Can hire")],
            "verbose_name": "Authi",
        },
    )
    author_with_db_table_comment = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {"db_table_comment": "Table comment"},
    )
    author_with_db_table_options = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {"db_table": "author_one"},
    )
    author_with_new_db_table_options = ModelState(
        "testapp",
        "Author",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {"db_table": "author_two"},
    )
    author_renamed_with_db_table_options = ModelState(
        "testapp",
        "NewAuthor",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {"db_table": "author_one"},
    )
    author_renamed_with_new_db_table_options = ModelState(
        "testapp",
        "NewAuthor",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        {"db_table": "author_three"},
    )
    contract = ModelState(
        "testapp",
        "Contract",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("publisher", models.ForeignKey("testapp.Publisher", models.CASCADE)),
        ],
    )
    contract_renamed = ModelState(
        "testapp",
        "Deal",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("publisher", models.ForeignKey("testapp.Publisher", models.CASCADE)),
        ],
    )
    publisher = ModelState(
        "testapp",
        "Publisher",
        [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=100)),
        ],
    )
    publisher_with_author = ModelState(
        "testapp",
        "Publisher",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("name", models.CharField(max_length=100)),
        ],
    )
    publisher_with_aardvark_author = ModelState(
        "testapp",
        "Publisher",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Aardvark", models.CASCADE)),
            ("name", models.CharField(max_length=100)),
        ],
    )
    publisher_with_book = ModelState(
        "testapp",
        "Publisher",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("otherapp.Book", models.CASCADE)),
            ("name", models.CharField(max_length=100)),
        ],
    )
    other_pony = ModelState(
        "otherapp",
        "Pony",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
    )
    other_pony_food = ModelState(
        "otherapp",
        "Pony",
        [
            ("id", models.AutoField(primary_key=True)),
        ],
        managers=[
            ("food_qs", FoodQuerySet.as_manager()),
            ("food_mgr", FoodManager("a", "b")),
            ("food_mgr_kwargs", FoodManager("x", "y", 3, 4)),
        ],
    )
    other_stable = ModelState(
        "otherapp", "Stable", [("id", models.AutoField(primary_key=True))]
    )
    third_thing = ModelState(
        "thirdapp", "Thing", [("id", models.AutoField(primary_key=True))]
    )
    book = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_proxy_fk = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("thirdapp.AuthorProxy", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_proxy_proxy_fk = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.AAuthorProxyProxy", models.CASCADE)),
        ],
    )
    book_migrations_fk = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("migrations.UnmigratedModel", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_no_author_fk = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.IntegerField()),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_no_author = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_author_renamed = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Writer", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_field_and_author_renamed = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("writer", models.ForeignKey("testapp.Writer", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_multiple_authors = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("authors", models.ManyToManyField("testapp.Author")),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_with_multiple_authors_through_attribution = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            (
                "authors",
                models.ManyToManyField(
                    "testapp.Author", through="otherapp.Attribution"
                ),
            ),
            ("title", models.CharField(max_length=200)),
        ],
    )
    book_indexes = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "indexes": [
                models.Index(fields=["author", "title"], name="book_title_author_idx")
            ],
        },
    )
    book_unordered_indexes = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "indexes": [
                models.Index(fields=["title", "author"], name="book_author_title_idx")
            ],
        },
    )
    book_unique_together = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "unique_together": {("author", "title")},
        },
    )
    book_unique_together_2 = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "unique_together": {("title", "author")},
        },
    )
    book_unique_together_3 = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("newfield", models.IntegerField()),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "unique_together": {("title", "newfield")},
        },
    )
    book_unique_together_4 = ModelState(
        "otherapp",
        "Book",
        [
            ("id", models.AutoField(primary_key=True)),
            ("newfield2", models.IntegerField()),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("title", models.CharField(max_length=200)),
        ],
        {
            "unique_together": {("title", "newfield2")},
        },
    )
    attribution = ModelState(
        "otherapp",
        "Attribution",
        [
            ("id", models.AutoField(primary_key=True)),
            ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
            ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
        ],
    )
    edition = ModelState(
        "thirdapp",
        "Edition",
        [
            ("id", models.AutoField(primary_key=True)),
            ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
        ],
    )
    custom_user = ModelState(
        "thirdapp",
        "CustomUser",
        [
            ("id", models.AutoField(primary_key=True)),
            ("username", models.CharField(max_length=255)),
        ],
        bases=(AbstractBaseUser,),
    )
    custom_user_no_inherit = ModelState(
        "thirdapp",
        "CustomUser",
        [
            ("id", models.AutoField(primary_key=True)),
            ("username", models.CharField(max_length=255)),
        ],
    )
    aardvark = ModelState(
        "thirdapp", "Aardvark", [("id", models.AutoField(primary_key=True))]
    )
    aardvark_testapp = ModelState(
        "testapp", "Aardvark", [("id", models.AutoField(primary_key=True))]
    )
    aardvark_based_on_author = ModelState(
        "testapp", "Aardvark", [], bases=("testapp.Author",)
    )
    aardvark_pk_fk_author = ModelState(
        "testapp",
        "Aardvark",
        [
            (
                "id",
                models.OneToOneField(
                    "testapp.Author", models.CASCADE, primary_key=True
                ),
            ),
        ],
    )
    knight = ModelState("eggs", "Knight", [("id", models.AutoField(primary_key=True))])
    rabbit = ModelState(
        "eggs",
        "Rabbit",
        [
            ("id", models.AutoField(primary_key=True)),
            ("knight", models.ForeignKey("eggs.Knight", models.CASCADE)),
            ("parent", models.ForeignKey("eggs.Rabbit", models.CASCADE)),
        ],
        {
            "unique_together": {("parent", "knight")},
            "indexes": [
                models.Index(
                    fields=["parent", "knight"], name="rabbit_circular_fk_index"
                )
            ],
        },
    )

    def test_arrange_for_graph(self):
        """
        Tests the ability of the migration autodetector to arrange and automatically name migrations for graph matching, ensuring that the resulting migrations have the correct names and dependencies.
        """
        # Make a fake graph
        graph = MigrationGraph()
        graph.add_node(("testapp", "0001_initial"), None)
        graph.add_node(("testapp", "0002_foobar"), None)
        graph.add_node(("otherapp", "0001_initial"), None)
        graph.add_dependency(
            "testapp.0002_foobar",
            ("testapp", "0002_foobar"),
            ("testapp", "0001_initial"),
        )
        graph.add_dependency(
            "testapp.0002_foobar",
            ("testapp", "0002_foobar"),
            ("otherapp", "0001_initial"),
        )
        # Use project state to make a new migration change set
        before = self.make_project_state([self.publisher, self.other_pony])
        after = self.make_project_state(
            [
                self.author_empty,
                self.publisher,
                self.other_pony,
                self.other_stable,
            ]
        )
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()
        # Run through arrange_for_graph
        changes = autodetector.arrange_for_graph(changes, graph)
        # Make sure there's a new name, deps match, etc.
        self.assertEqual(changes["testapp"][0].name, "0003_author")
        self.assertEqual(
            changes["testapp"][0].dependencies, [("testapp", "0002_foobar")]
        )
        self.assertEqual(changes["otherapp"][0].name, "0002_stable")
        self.assertEqual(
            changes["otherapp"][0].dependencies, [("otherapp", "0001_initial")]
        )

    def test_arrange_for_graph_with_multiple_initial(self):
        # Make a fake graph.
        """
        Verifies the arrangement of migration changes in a graph with multiple initial migrations.

         Tests that the MigrationAutodetector correctly orders and sets dependencies 
         between initial migrations across multiple apps in a project.
        """
        graph = MigrationGraph()
        # Use project state to make a new migration change set.
        before = self.make_project_state([])
        after = self.make_project_state(
            [self.author_with_book, self.book, self.attribution]
        )
        autodetector = MigrationAutodetector(
            before, after, MigrationQuestioner({"ask_initial": True})
        )
        changes = autodetector._detect_changes()
        changes = autodetector.arrange_for_graph(changes, graph)

        self.assertEqual(changes["otherapp"][0].name, "0001_initial")
        self.assertEqual(changes["otherapp"][0].dependencies, [])
        self.assertEqual(changes["otherapp"][1].name, "0002_initial")
        self.assertCountEqual(
            changes["otherapp"][1].dependencies,
            [("testapp", "0001_initial"), ("otherapp", "0001_initial")],
        )
        self.assertEqual(changes["testapp"][0].name, "0001_initial")
        self.assertEqual(
            changes["testapp"][0].dependencies, [("otherapp", "0001_initial")]
        )

    def test_trim_apps(self):
        """

        Tests the functionality of trimming migrations to only include the specified application and its dependencies.

        """
        # Use project state to make a new migration change set
        before = self.make_project_state([])
        after = self.make_project_state(
            [self.author_empty, self.other_pony, self.other_stable, self.third_thing]
        )
        autodetector = MigrationAutodetector(
            before, after, MigrationQuestioner({"ask_initial": True})
        )
        changes = autodetector._detect_changes()
        # Run through arrange_for_graph
        graph = MigrationGraph()
        changes = autodetector.arrange_for_graph(changes, graph)
        changes["testapp"][0].dependencies.append(("otherapp", "0001_initial"))
        changes = autodetector._trim_to_apps(changes, {"testapp"})
        # Make sure there's the right set of migrations
        self.assertEqual(changes["testapp"][0].name, "0001_initial")
        self.assertEqual(changes["otherapp"][0].name, "0001_initial")
        self.assertNotIn("thirdapp", changes)

    def test_custom_migration_name(self):
        """
        Tests whether migrations are correctly named using a custom naming scheme when generated for graph matching.
        """
        # Make a fake graph
        graph = MigrationGraph()
        graph.add_node(("testapp", "0001_initial"), None)
        graph.add_node(("testapp", "0002_foobar"), None)
        graph.add_node(("otherapp", "0001_initial"), None)
        graph.add_dependency(
            "testapp.0002_foobar",
            ("testapp", "0002_foobar"),
            ("testapp", "0001_initial"),
        )

        # Use project state to make a new migration change set
        before = self.make_project_state([])
        after = self.make_project_state(
            [self.author_empty, self.other_pony, self.other_stable]
        )
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes()

        # Run through arrange_for_graph
        migration_name = "custom_name"
        changes = autodetector.arrange_for_graph(changes, graph, migration_name)

        # Make sure there's a new name, deps match, etc.
        self.assertEqual(changes["testapp"][0].name, "0003_%s" % migration_name)
        self.assertEqual(
            changes["testapp"][0].dependencies, [("testapp", "0002_foobar")]
        )
        self.assertEqual(changes["otherapp"][0].name, "0002_%s" % migration_name)
        self.assertEqual(
            changes["otherapp"][0].dependencies, [("otherapp", "0001_initial")]
        )

    def test_new_model(self):
        """
        Tests whether the autodetection of new models in the application correctly generates a migration with a single 'CreateModel' operation.
        """
        changes = self.get_changes([], [self.other_pony_food])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Pony")
        self.assertEqual(
            [name for name, mgr in changes["otherapp"][0].operations[0].managers],
            ["food_qs", "food_mgr", "food_mgr_kwargs"],
        )

    def test_old_model(self):
        """

        Verifies the correct deletion of outdated models in the database schema.

        This test ensures that when a model is removed from the application code,
        the corresponding database table is properly deleted during the migration process.

        """
        changes = self.get_changes([self.author_empty], [])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["DeleteModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")

    def test_add_field(self):
        """
        Tests the autodetection of new fields by simulating adding a field to a model and verifying the generated migration operations.
        """
        changes = self.get_changes([self.author_empty], [self.author_name])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name")

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_add_not_null_field_with_db_default(self, mocked_ask_method):
        """
        Tests that adding a not-null field with a database default does not prompt for a default value, and generates the correct migration operation.
        """
        changes = self.get_changes([self.author_empty], [self.author_name_db_default])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=True
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 0, db_default="Ada Lovelace"
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_add_date_fields_with_auto_now_not_asking_for_default(
        self, mocked_ask_method
    ):
        """
        Tests that adding date fields with auto_now=True does not prompt for a default value when creating or modifying a database migration, as the current date and time should be automatically set.
        """
        changes = self.get_changes(
            [self.author_empty], [self.author_dates_of_birth_auto_now]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["AddField", "AddField", "AddField"]
        )
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, auto_now=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 1, auto_now=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 2, auto_now=True)

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_add_date_fields_with_auto_now_add_not_asking_for_null_addition(
        self, mocked_ask_method
    ):
        """
        Tests the addition of date fields with auto_now_add=True to an existing model, verifying that no prompt is issued for allowing null additions when generating migrations.
        """
        changes = self.get_changes(
            [self.author_empty], [self.author_dates_of_birth_auto_now_add]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["AddField", "AddField", "AddField"]
        )
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, auto_now_add=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 1, auto_now_add=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 2, auto_now_add=True)

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_auto_now_add_addition"
    )
    def test_add_date_fields_with_auto_now_add_asking_for_default(
        self, mocked_ask_method
    ):
        """
        Tests the creation of date fields with auto_now_add parameter in migrations, ensuring the correct operations are generated and the default value is requested as expected.
        """
        changes = self.get_changes(
            [self.author_empty], [self.author_dates_of_birth_auto_now_add]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["AddField", "AddField", "AddField"]
        )
        self.assertOperationFieldAttributes(changes, "testapp", 0, 0, auto_now_add=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 1, auto_now_add=True)
        self.assertOperationFieldAttributes(changes, "testapp", 0, 2, auto_now_add=True)
        self.assertEqual(mocked_ask_method.call_count, 3)

    def test_add_field_before_generated_field(self):
        """

        Tests adding a field before a generated field in a model state.

        Verifies that a single migration is created with two 'AddField' operations
        when adding a field before a generated field in the model.

        """
        initial_state = ModelState(
            "testapp",
            "Author",
            [
                ("name", models.CharField(max_length=20)),
            ],
        )
        updated_state = ModelState(
            "testapp",
            "Author",
            [
                ("name", models.CharField(max_length=20)),
                ("surname", models.CharField(max_length=20)),
                (
                    "lower_full_name",
                    models.GeneratedField(
                        expression=Concat(Lower("name"), Lower("surname")),
                        output_field=models.CharField(max_length=30),
                        db_persist=True,
                    ),
                ),
            ],
        )
        changes = self.get_changes([initial_state], [updated_state])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField", "AddField"])
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 1, expression=Concat(Lower("name"), Lower("surname"))
        )

    def test_add_fk_before_generated_field(self):
        """
        Tests adding a foreign key before a generated field in a model's state, verifying that the resulting migration operations are correct.
        """
        initial_state = ModelState(
            "testapp",
            "Author",
            [
                ("name", models.CharField(max_length=20)),
            ],
        )
        updated_state = [
            ModelState(
                "testapp",
                "Publisher",
                [
                    ("name", models.CharField(max_length=20)),
                ],
            ),
            ModelState(
                "testapp",
                "Author",
                [
                    ("name", models.CharField(max_length=20)),
                    (
                        "publisher",
                        models.ForeignKey("testapp.Publisher", models.CASCADE),
                    ),
                    (
                        "lower_full_name",
                        models.GeneratedField(
                            expression=Concat("name", "publisher_id"),
                            output_field=models.CharField(max_length=20),
                            db_persist=True,
                        ),
                    ),
                ],
            ),
        ]
        changes = self.get_changes([initial_state], updated_state)
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "AddField", "AddField"]
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 2, expression=Concat("name", "publisher_id")
        )

    def test_remove_field(self):
        """
        Verifies the autodetection of removed fields by comparing model changes and asserting the correct removal operation is generated.
        """
        changes = self.get_changes([self.author_name], [self.author_empty])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RemoveField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name")

    def test_alter_field(self):
        """
        Tests the autodetection of changes to a field, specifically verifying that an AlterField operation is generated when a model field is modified.
        """
        changes = self.get_changes([self.author_name], [self.author_name_longer])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=True
        )

    def test_supports_functools_partial(self):
        """
        Tests that changes to functools.partial calls in FileField upload_to arguments are correctly detected and migrated.
        """
        def _content_file_name(instance, filename, key, **kwargs):
            return "{}/{}".format(instance, filename)

        def content_file_name(key, **kwargs):
            return functools.partial(_content_file_name, key, **kwargs)

        # An unchanged partial reference.
        before = [
            ModelState(
                "testapp",
                "Author",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "file",
                        models.FileField(
                            max_length=200, upload_to=content_file_name("file")
                        ),
                    ),
                ],
            )
        ]
        after = [
            ModelState(
                "testapp",
                "Author",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "file",
                        models.FileField(
                            max_length=200, upload_to=content_file_name("file")
                        ),
                    ),
                ],
            )
        ]
        changes = self.get_changes(before, after)
        self.assertNumberMigrations(changes, "testapp", 0)

        # A changed partial reference.
        args_changed = [
            ModelState(
                "testapp",
                "Author",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "file",
                        models.FileField(
                            max_length=200, upload_to=content_file_name("other-file")
                        ),
                    ),
                ],
            )
        ]
        changes = self.get_changes(before, args_changed)
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        # Can't use assertOperationFieldAttributes because we need the
        # deconstructed version, i.e., the exploded func/args/keywords rather
        # than the partial: we don't care if it's not the same instance of the
        # partial, only if it's the same source function, args, and keywords.
        value = changes["testapp"][0].operations[0].field.upload_to
        self.assertEqual(
            (_content_file_name, ("other-file",), {}),
            (value.func, value.args, value.keywords),
        )

        kwargs_changed = [
            ModelState(
                "testapp",
                "Author",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "file",
                        models.FileField(
                            max_length=200,
                            upload_to=content_file_name("file", spam="eggs"),
                        ),
                    ),
                ],
            )
        ]
        changes = self.get_changes(before, kwargs_changed)
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        value = changes["testapp"][0].operations[0].field.upload_to
        self.assertEqual(
            (_content_file_name, ("file",), {"spam": "eggs"}),
            (value.func, value.args, value.keywords),
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_alteration",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_alter_field_to_not_null_with_default(self, mocked_ask_method):
        """
        Tests the autodetection of field alterations from nullable to non-nullable when a default value is provided, ensuring that no user prompt is triggered.
        """
        changes = self.get_changes([self.author_name_null], [self.author_name_default])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=True
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 0, default="Ada Lovelace"
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_alteration",
        side_effect=AssertionError("Should not have prompted for not null alteration"),
    )
    def test_alter_field_to_not_null_with_db_default(self, mocked_ask_method):
        """
        Tests the migration of a field to not null when a database default is provided, ensuring that no prompt for not null alteration is triggered. Verifies the resulting migration operation's type and attributes.
        """
        changes = self.get_changes(
            [self.author_name_null], [self.author_name_db_default]
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=True
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 0, db_default="Ada Lovelace"
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_alteration",
        return_value=models.NOT_PROVIDED,
    )
    def test_alter_field_to_not_null_without_default(self, mocked_ask_method):
        """

        Tests the autodetection of nullable to non-nullable alterations when altering a field to not null without a default value.

        """
        changes = self.get_changes([self.author_name_null], [self.author_name])
        self.assertEqual(mocked_ask_method.call_count, 1)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=True
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 0, default=models.NOT_PROVIDED
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_alteration",
        return_value="Some Name",
    )
    def test_alter_field_to_not_null_oneoff_default(self, mocked_ask_method):
        """
        Tests the autodetection of nullable to non-nullable field alterations, 
        specifically when the new default value is provided by user input.
        """
        changes = self.get_changes([self.author_name_null], [self.author_name])
        self.assertEqual(mocked_ask_method.call_count, 1)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="name", preserve_default=False
        )
        self.assertOperationFieldAttributes(
            changes, "testapp", 0, 0, default="Some Name"
        )

    def test_rename_field(self):
        """
        Tests the autodetection of renamed fields in migrations by verifying that a single RenameField operation is generated when a field name change is detected.
        """
        changes = self.get_changes(
            [self.author_name],
            [self.author_name_renamed],
            MigrationQuestioner({"ask_rename": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="name", new_name="names"
        )

    def test_rename_field_foreign_key_to_field(self):
        """
        Tests the renaming of a field referenced by a foreign key.

        Verifies that when a field is renamed, any foreign keys referencing it are updated
        correctly, and a single migration is generated with a RenameField operation.
        """
        before = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("field", models.IntegerField(unique=True)),
                ],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "foo",
                        models.ForeignKey("app.Foo", models.CASCADE, to_field="field"),
                    ),
                ],
            ),
        ]
        after = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("renamed_field", models.IntegerField(unique=True)),
                ],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "foo",
                        models.ForeignKey(
                            "app.Foo", models.CASCADE, to_field="renamed_field"
                        ),
                    ),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["RenameField"])
        self.assertOperationAttributes(
            changes, "app", 0, 0, old_name="field", new_name="renamed_field"
        )

    def test_foreign_object_from_to_fields_list(self):
        """
        Tests that model state changes are correctly detected for foreign object fields defined with from_fields and to_fields when the foreign object reference is not altered.
        """
        author_state = ModelState(
            "app",
            "Author",
            [("id", models.AutoField(primary_key=True))],
        )
        book_state = ModelState(
            "app",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField()),
                ("author_id", models.IntegerField()),
                (
                    "author",
                    models.ForeignObject(
                        "app.Author",
                        models.CASCADE,
                        from_fields=["author_id"],
                        to_fields=["id"],
                    ),
                ),
            ],
        )
        book_state_copy = copy.deepcopy(book_state)
        changes = self.get_changes(
            [author_state, book_state],
            [author_state, book_state_copy],
        )
        self.assertEqual(changes, {})

    def test_rename_foreign_object_fields(self):
        """
        Tests the renaming of fields in models that reference foreign objects.

        Verifies that changes to model fields are correctly detected and translated into 
        the appropriate database migration operations, including renaming fields and 
        updating foreign object references.
        """
        fields = ("first", "second")
        renamed_fields = ("first_renamed", "second_renamed")
        before = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first", models.IntegerField()),
                    ("second", models.IntegerField()),
                ],
                options={"unique_together": {fields}},
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first", models.IntegerField()),
                    ("second", models.IntegerField()),
                    (
                        "foo",
                        models.ForeignObject(
                            "app.Foo",
                            models.CASCADE,
                            from_fields=fields,
                            to_fields=fields,
                        ),
                    ),
                ],
            ),
        ]
        # Case 1: to_fields renames.
        after = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first_renamed", models.IntegerField()),
                    ("second_renamed", models.IntegerField()),
                ],
                options={"unique_together": {renamed_fields}},
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first", models.IntegerField()),
                    ("second", models.IntegerField()),
                    (
                        "foo",
                        models.ForeignObject(
                            "app.Foo",
                            models.CASCADE,
                            from_fields=fields,
                            to_fields=renamed_fields,
                        ),
                    ),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(
            changes, "app", 0, ["RenameField", "RenameField", "AlterUniqueTogether"]
        )
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            0,
            model_name="foo",
            old_name="first",
            new_name="first_renamed",
        )
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            1,
            model_name="foo",
            old_name="second",
            new_name="second_renamed",
        )
        # Case 2: from_fields renames.
        after = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first", models.IntegerField()),
                    ("second", models.IntegerField()),
                ],
                options={"unique_together": {fields}},
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("first_renamed", models.IntegerField()),
                    ("second_renamed", models.IntegerField()),
                    (
                        "foo",
                        models.ForeignObject(
                            "app.Foo",
                            models.CASCADE,
                            from_fields=renamed_fields,
                            to_fields=fields,
                        ),
                    ),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["RenameField", "RenameField"])
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            0,
            model_name="bar",
            old_name="first",
            new_name="first_renamed",
        )
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            1,
            model_name="bar",
            old_name="second",
            new_name="second_renamed",
        )

    def test_rename_referenced_primary_key(self):
        """
        Test the migration behavior when renaming a primary key field that is referenced by a foreign key in another model.
        """
        before = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.CharField(primary_key=True, serialize=False)),
                ],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("foo", models.ForeignKey("app.Foo", models.CASCADE)),
                ],
            ),
        ]
        after = [
            ModelState(
                "app",
                "Foo",
                [("renamed_id", models.CharField(primary_key=True, serialize=False))],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("foo", models.ForeignKey("app.Foo", models.CASCADE)),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["RenameField"])
        self.assertOperationAttributes(
            changes, "app", 0, 0, old_name="id", new_name="renamed_id"
        )

    def test_rename_field_preserved_db_column(self):
        """
        Tests that a RenameField operation is correctly generated when a field is 
        renamed and the db_column attribute is preserved, ensuring database column 
        names are updated accordingly.
        """
        before = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("field", models.IntegerField()),
                ],
            ),
        ]
        after = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("renamed_field", models.IntegerField(db_column="field")),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["AlterField", "RenameField"])
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            0,
            model_name="foo",
            name="field",
        )
        self.assertEqual(
            changes["app"][0].operations[0].field.deconstruct(),
            (
                "field",
                "django.db.models.IntegerField",
                [],
                {"db_column": "field"},
            ),
        )
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            1,
            model_name="foo",
            old_name="field",
            new_name="renamed_field",
        )

    def test_rename_related_field_preserved_db_column(self):
        """
        Tests that renaming a related field maintains its original database column name in the migration operations.
        """
        before = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("foo", models.ForeignKey("app.Foo", models.CASCADE)),
                ],
            ),
        ]
        after = [
            ModelState(
                "app",
                "Foo",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "app",
                "Bar",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "renamed_foo",
                        models.ForeignKey(
                            "app.Foo", models.CASCADE, db_column="foo_id"
                        ),
                    ),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename": True})
        )
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["AlterField", "RenameField"])
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            0,
            model_name="bar",
            name="foo",
        )
        self.assertEqual(
            changes["app"][0].operations[0].field.deconstruct(),
            (
                "foo",
                "django.db.models.ForeignKey",
                [],
                {"to": "app.foo", "on_delete": models.CASCADE, "db_column": "foo_id"},
            ),
        )
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            1,
            model_name="bar",
            old_name="foo",
            new_name="renamed_foo",
        )

    def test_rename_field_with_renamed_model(self):
        """
        Tests that a field is correctly renamed when its model is also renamed, ensuring that both the model and field name changes are properly captured in a migration.
        """
        changes = self.get_changes(
            [self.author_name],
            [
                ModelState(
                    "testapp",
                    "RenamedAuthor",
                    [
                        ("id", models.AutoField(primary_key=True)),
                        ("renamed_name", models.CharField(max_length=200)),
                    ],
                ),
            ],
            MigrationQuestioner({"ask_rename_model": True, "ask_rename": True}),
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel", "RenameField"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            old_name="Author",
            new_name="RenamedAuthor",
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            1,
            old_name="name",
            new_name="renamed_name",
        )

    def test_rename_model(self):
        """
        Tests whether the system correctly detects and handles renamed models, verifying that the changed model name is accurately reflected in the migration output.
        """
        changes = self.get_changes(
            [self.author_with_book, self.book],
            [self.author_renamed_with_book, self.book_with_author_renamed],
            MigrationQuestioner({"ask_rename_model": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="Author", new_name="Writer"
        )
        # Now that RenameModel handles related fields too, there should be
        # no AlterField for the related field.
        self.assertNumberMigrations(changes, "otherapp", 0)

    def test_rename_model_case(self):
        """
        Tests whether renaming a model by changing its case does not trigger any automatic migrations.
        """
        author_renamed = ModelState(
            "testapp",
            "author",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
        )
        changes = self.get_changes(
            [self.author_empty, self.book],
            [author_renamed, self.book],
            questioner=MigrationQuestioner({"ask_rename_model": True}),
        )
        self.assertNumberMigrations(changes, "testapp", 0)
        self.assertNumberMigrations(changes, "otherapp", 0)

    def test_renamed_referenced_m2m_model_case(self):
        publisher_renamed = ModelState(
            "testapp",
            "publisher",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=100)),
            ],
        )
        changes = self.get_changes(
            [self.publisher, self.author_with_m2m],
            [publisher_renamed, self.author_with_m2m],
            questioner=MigrationQuestioner({"ask_rename_model": True}),
        )
        self.assertNumberMigrations(changes, "testapp", 0)
        self.assertNumberMigrations(changes, "otherapp", 0)

    def test_rename_m2m_through_model(self):
        """
        Tests the autodetection of model renames used in many-to-many relationships as through models, ensuring the migration system correctly identifies and applies the rename operation.
        """
        changes = self.get_changes(
            [self.author_with_m2m_through, self.publisher, self.contract],
            [
                self.author_with_renamed_m2m_through,
                self.publisher,
                self.contract_renamed,
            ],
            MigrationQuestioner({"ask_rename_model": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="Contract", new_name="Deal"
        )

    def test_rename_model_with_renamed_rel_field(self):
        """
        Tests that model renaming is correctly autodetected when a related field is also renamed, verifying the generation of appropriate RenameModel and RenameField migrations.
        """
        changes = self.get_changes(
            [self.author_with_book, self.book],
            [self.author_renamed_with_book, self.book_with_field_and_author_renamed],
            MigrationQuestioner({"ask_rename": True, "ask_rename_model": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="Author", new_name="Writer"
        )
        # Right number/type of migrations for related field rename?
        # Alter is already taken care of.
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RenameField"])
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, old_name="author", new_name="writer"
        )

    def test_rename_model_with_fks_in_different_position(self):
        """
        Tests that the RenameModel detection is not influenced by the order of fields in a model, specifically with foreign keys in different positions.
        """
        before = [
            ModelState(
                "testapp",
                "EntityA",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "testapp",
                "EntityB",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("some_label", models.CharField(max_length=255)),
                    ("entity_a", models.ForeignKey("testapp.EntityA", models.CASCADE)),
                ],
            ),
        ]
        after = [
            ModelState(
                "testapp",
                "EntityA",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "testapp",
                "RenamedEntityB",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("entity_a", models.ForeignKey("testapp.EntityA", models.CASCADE)),
                    ("some_label", models.CharField(max_length=255)),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename_model": True})
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="EntityB", new_name="RenamedEntityB"
        )

    def test_rename_model_reverse_relation_dependencies(self):
        """
        Tests that a model renaming migration has the correct dependency on another app's migration when a foreign key points to the original model name, ensuring that the renaming migration runs after the foreign key is created.
        """
        before = [
            ModelState(
                "testapp",
                "EntityA",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "otherapp",
                "EntityB",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("entity_a", models.ForeignKey("testapp.EntityA", models.CASCADE)),
                ],
            ),
        ]
        after = [
            ModelState(
                "testapp",
                "RenamedEntityA",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "otherapp",
                "EntityB",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "entity_a",
                        models.ForeignKey("testapp.RenamedEntityA", models.CASCADE),
                    ),
                ],
            ),
        ]
        changes = self.get_changes(
            before, after, MigrationQuestioner({"ask_rename_model": True})
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertMigrationDependencies(
            changes, "testapp", 0, [("otherapp", "__first__")]
        )
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="EntityA", new_name="RenamedEntityA"
        )

    def test_fk_dependency(self):
        """
        Tests that having a ForeignKey in a model automatically adds a dependency between migrations of related models.
        """
        # Note that testapp (author) has no dependencies,
        # otherapp (book) depends on testapp (author),
        # thirdapp (edition) depends on otherapp (book)
        changes = self.get_changes([], [self.author_name, self.book, self.edition])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertMigrationDependencies(changes, "testapp", 0, [])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Book")
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("testapp", "auto_1")]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "thirdapp", 1)
        self.assertOperationTypes(changes, "thirdapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "thirdapp", 0, 0, name="Edition")
        self.assertMigrationDependencies(
            changes, "thirdapp", 0, [("otherapp", "auto_1")]
        )

    def test_proxy_fk_dependency(self):
        """
        Tests that foreign key dependencies are correctly applied to proxy models in database migrations.
        """
        # Note that testapp (author) has no dependencies,
        # otherapp (book) depends on testapp (authorproxy)
        changes = self.get_changes(
            [], [self.author_empty, self.author_proxy_third, self.book_proxy_fk]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertMigrationDependencies(changes, "testapp", 0, [])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Book")
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("thirdapp", "auto_1")]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "thirdapp", 1)
        self.assertOperationTypes(changes, "thirdapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "thirdapp", 0, 0, name="AuthorProxy")
        self.assertMigrationDependencies(
            changes, "thirdapp", 0, [("testapp", "auto_1")]
        )

    def test_same_app_no_fk_dependency(self):
        """
        Tests that a migration with a foreign key between two models of the same application does not create a self-referential dependency.
        """
        changes = self.get_changes([], [self.author_with_publisher, self.publisher])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Author")
        self.assertMigrationDependencies(changes, "testapp", 0, [])

    def test_circular_fk_dependency(self):
        """
        Tests the resolution of a circular ForeignKey dependency, verifying that the migration system correctly handles the situation by creating two migrations on one side and one on the other.
        """
        changes = self.get_changes(
            [], [self.author_with_book, self.book, self.publisher_with_book]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertMigrationDependencies(
            changes, "testapp", 0, [("otherapp", "auto_1")]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 2)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationTypes(changes, "otherapp", 1, ["AddField"])
        self.assertMigrationDependencies(changes, "otherapp", 0, [])
        self.assertMigrationDependencies(
            changes, "otherapp", 1, [("otherapp", "auto_1"), ("testapp", "auto_1")]
        )
        # both split migrations should be `initial`
        self.assertTrue(changes["otherapp"][0].initial)
        self.assertTrue(changes["otherapp"][1].initial)

    def test_same_app_circular_fk_dependency(self):
        """
        Verifies that Django migrations correctly handle foreign key dependencies between models within the same application, specifically checking for the absence of self-referential dependencies.
        """
        changes = self.get_changes(
            [], [self.author_with_publisher, self.publisher_with_author]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "CreateModel", "AddField"]
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="publisher")
        self.assertMigrationDependencies(changes, "testapp", 0, [])

    def test_same_app_circular_fk_dependency_with_unique_together_and_indexes(self):
        """
        Tests the handling of circular foreign key dependencies with unique_together constraints and indexes in migrations, ensuring that required fields are created before constraints and indexes.
        """
        changes = self.get_changes([], [self.knight, self.rabbit])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "eggs", 1)
        self.assertOperationTypes(
            changes,
            "eggs",
            0,
            ["CreateModel", "CreateModel"],
        )
        self.assertNotIn("unique_together", changes["eggs"][0].operations[0].options)
        self.assertMigrationDependencies(changes, "eggs", 0, [])

    def test_alter_db_table_add(self):
        """
        Tests the detection of adding a db_table option to a model and verifies that the correct AlterModelTable migration is generated.
        """
        changes = self.get_changes(
            [self.author_empty], [self.author_with_db_table_options]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTable"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", table="author_one"
        )

    def test_alter_db_table_change(self):
        """
        Tests the detection of changes to the db_table option in a model's Meta options, ensuring a successful migration operation is generated for the alteration of the database table name.
        """
        changes = self.get_changes(
            [self.author_with_db_table_options], [self.author_with_new_db_table_options]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTable"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", table="author_two"
        )

    def test_alter_db_table_remove(self):
        """
        Tests the detection of changes when the db_table option is removed from a model's Meta options, ensuring a correct AlterModelTable operation is generated in the migration.
        """
        changes = self.get_changes(
            [self.author_with_db_table_options], [self.author_empty]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTable"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", table=None
        )

    def test_alter_db_table_no_changes(self):
        """
        Alter_db_table doesn't generate a migration if no changes have been made.
        """
        changes = self.get_changes(
            [self.author_with_db_table_options], [self.author_with_db_table_options]
        )
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_keep_db_table_with_model_change(self):
        """
        Tests the autodetector's behavior when a model's name changes but its associated database table remains the same, ensuring that only one migration operation is generated.
        """
        changes = self.get_changes(
            [self.author_with_db_table_options],
            [self.author_renamed_with_db_table_options],
            MigrationQuestioner({"ask_rename_model": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RenameModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="Author", new_name="NewAuthor"
        )

    def test_alter_db_table_with_model_change(self):
        """
        Verifies that when a model's name and database table change, the autodetector correctly generates a migration with two operations: a RenameModel and an AlterModelTable.
        """
        changes = self.get_changes(
            [self.author_with_db_table_options],
            [self.author_renamed_with_new_db_table_options],
            MigrationQuestioner({"ask_rename_model": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["RenameModel", "AlterModelTable"]
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, old_name="Author", new_name="NewAuthor"
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, name="newauthor", table="author_three"
        )

    def test_alter_db_table_comment_add(self):
        changes = self.get_changes(
            [self.author_empty], [self.author_with_db_table_comment]
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTableComment"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", table_comment="Table comment"
        )

    def test_alter_db_table_comment_change(self):
        """
        Tests that a migration is correctly generated when the db_table_comment attribute of a model is changed.
        """
        author_with_new_db_table_comment = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
            {"db_table_comment": "New table comment"},
        )
        changes = self.get_changes(
            [self.author_with_db_table_comment],
            [author_with_new_db_table_comment],
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTableComment"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="author",
            table_comment="New table comment",
        )

    def test_alter_db_table_comment_remove(self):
        changes = self.get_changes(
            [self.author_with_db_table_comment],
            [self.author_empty],
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelTableComment"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", db_table_comment=None
        )

    def test_alter_db_table_comment_no_changes(self):
        changes = self.get_changes(
            [self.author_with_db_table_comment],
            [self.author_with_db_table_comment],
        )
        self.assertNumberMigrations(changes, "testapp", 0)

    def test_identical_regex_doesnt_alter(self):
        from_state = ModelState(
            "testapp",
            "model",
            [
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        validators=[
                            RegexValidator(
                                re.compile("^[-a-zA-Z0-9_]+\\Z"),
                                "Enter a valid “slug” consisting of letters, numbers, "
                                "underscores or hyphens.",
                                "invalid",
                            )
                        ],
                    ),
                )
            ],
        )
        to_state = ModelState(
            "testapp",
            "model",
            [("id", models.AutoField(primary_key=True, validators=[validate_slug]))],
        )
        changes = self.get_changes([from_state], [to_state])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 0)

    def test_different_regex_does_alter(self):
        """
        Tests that changing a model field's regex validator results in an AlterField operation in the generated migrations.
        """
        from_state = ModelState(
            "testapp",
            "model",
            [
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        validators=[
                            RegexValidator(
                                re.compile("^[a-z]+\\Z", 32),
                                "Enter a valid “slug” consisting of letters, numbers, "
                                "underscores or hyphens.",
                                "invalid",
                            )
                        ],
                    ),
                )
            ],
        )
        to_state = ModelState(
            "testapp",
            "model",
            [("id", models.AutoField(primary_key=True, validators=[validate_slug]))],
        )
        changes = self.get_changes([from_state], [to_state])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])

    def test_alter_regex_string_to_compiled_regex(self):
        """
        Tests the alteration of a model field's RegexValidator from a string to a compiled regular expression, verifying that the change generates the correct migration operations.
        """
        regex_string = "^[a-z]+$"
        from_state = ModelState(
            "testapp",
            "model",
            [
                (
                    "id",
                    models.AutoField(
                        primary_key=True, validators=[RegexValidator(regex_string)]
                    ),
                )
            ],
        )
        to_state = ModelState(
            "testapp",
            "model",
            [
                (
                    "id",
                    models.AutoField(
                        primary_key=True,
                        validators=[RegexValidator(re.compile(regex_string))],
                    ),
                )
            ],
        )
        changes = self.get_changes([from_state], [to_state])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])

    def test_empty_unique_together(self):
        """
        Tests that an empty unique_together constraint does not triggers a model migration.
        """
        # Explicitly testing for not specified, since this is the case after
        # a CreateModel operation w/o any definition on the original model
        model_state_not_specified = ModelState(
            "a", "model", [("id", models.AutoField(primary_key=True))]
        )
        # Explicitly testing for None, since this was the issue in #23452 after
        # an AlterUniqueTogether operation with e.g. () as value
        model_state_none = ModelState(
            "a",
            "model",
            [("id", models.AutoField(primary_key=True))],
            {
                "unique_together": None,
            },
        )
        # Explicitly testing for the empty set, since we now always have sets.
        # During removal (('col1', 'col2'),) --> () this becomes set([])
        model_state_empty = ModelState(
            "a",
            "model",
            [("id", models.AutoField(primary_key=True))],
            {
                "unique_together": set(),
            },
        )

        def test(from_state, to_state, msg):
            changes = self.get_changes([from_state], [to_state])
            if changes:
                ops = ", ".join(
                    o.__class__.__name__ for o in changes["a"][0].operations
                )
                self.fail("Created operation(s) %s from %s" % (ops, msg))

        tests = (
            (
                model_state_not_specified,
                model_state_not_specified,
                '"not specified" to "not specified"',
            ),
            (model_state_not_specified, model_state_none, '"not specified" to "None"'),
            (
                model_state_not_specified,
                model_state_empty,
                '"not specified" to "empty"',
            ),
            (model_state_none, model_state_not_specified, '"None" to "not specified"'),
            (model_state_none, model_state_none, '"None" to "None"'),
            (model_state_none, model_state_empty, '"None" to "empty"'),
            (
                model_state_empty,
                model_state_not_specified,
                '"empty" to "not specified"',
            ),
            (model_state_empty, model_state_none, '"empty" to "None"'),
            (model_state_empty, model_state_empty, '"empty" to "empty"'),
        )

        for t in tests:
            test(*t)

    def test_create_model_with_indexes(self):
        """
        Tests the creation of a new model that includes predefined indexes, verifying the resulting migration operation is correct and includes the defined indexes.
        """
        added_index = models.Index(
            fields=["name"], name="create_model_with_indexes_idx"
        )
        author = ModelState(
            "otherapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
            ],
            {
                "indexes": [added_index],
            },
        )
        changes = self.get_changes([], [author])
        # Right number of migrations?
        self.assertEqual(len(changes["otherapp"]), 1)
        # Right number of actions?
        migration = changes["otherapp"][0]
        self.assertEqual(len(migration.operations), 1)
        # Right actions order?
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Author")
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            name="Author",
            options={"indexes": [added_index]},
        )

    def test_add_indexes(self):
        """
        Tests that adding a new index is detected as a single 'AddIndex' operation in a migration.
        """
        changes = self.get_changes(
            [self.author_empty, self.book], [self.author_empty, self.book_indexes]
        )
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AddIndex"])
        added_index = models.Index(
            fields=["author", "title"], name="book_title_author_idx"
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, model_name="book", index=added_index
        )

    def test_remove_indexes(self):
        """
        Tests the detection of index removals in the database schema, verifying a single migration operation is generated with the correct RemoveIndex operation type and attributes.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_indexes], [self.author_empty, self.book]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RemoveIndex"])
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, model_name="book", name="book_title_author_idx"
        )

    def test_rename_indexes(self):
        """
        Tests that renaming an index on a model results in the correct RenameIndex operation in the generated migration.
        """
        book_renamed_indexes = ModelState(
            "otherapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("author", models.ForeignKey("testapp.Author", models.CASCADE)),
                ("title", models.CharField(max_length=200)),
            ],
            {
                "indexes": [
                    models.Index(
                        fields=["author", "title"], name="renamed_book_title_author_idx"
                    )
                ],
            },
        )
        changes = self.get_changes(
            [self.author_empty, self.book_indexes],
            [self.author_empty, book_renamed_indexes],
        )
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RenameIndex"])
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            model_name="book",
            new_name="renamed_book_title_author_idx",
            old_name="book_title_author_idx",
        )

    def test_order_fields_indexes(self):
        """
        Verifies that the system correctly detects changes when the order of fields in an index is rearranged.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_indexes],
            [self.author_empty, self.book_unordered_indexes],
        )
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["RemoveIndex", "AddIndex"])
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, model_name="book", name="book_title_author_idx"
        )
        added_index = models.Index(
            fields=["title", "author"], name="book_author_title_idx"
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 1, model_name="book", index=added_index
        )

    def test_create_model_with_check_constraint(self):
        """
        Verifies that a new model can be created with predefined check constraints, ensuring the constraint is properly applied during the migration process.
        """
        author = ModelState(
            "otherapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
            ],
            {
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(name__contains="Bob"),
                        name="name_contains_bob",
                    )
                ]
            },
        )
        changes = self.get_changes([], [author])
        constraint = models.CheckConstraint(
            condition=models.Q(name__contains="Bob"), name="name_contains_bob"
        )
        # Right number of migrations?
        self.assertEqual(len(changes["otherapp"]), 1)
        # Right number of actions?
        migration = changes["otherapp"][0]
        self.assertEqual(len(migration.operations), 1)
        # Right actions order?
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            name="Author",
            options={"constraints": [constraint]},
        )

    def test_add_constraints(self):
        """
        Verifies that the addition of new constraints to a model triggers the correct change detection and migration operations.
        """
        changes = self.get_changes(
            [self.author_name], [self.author_name_check_constraint]
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddConstraint"])
        added_constraint = models.CheckConstraint(
            condition=models.Q(name__contains="Bob"), name="name_contains_bob"
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, model_name="author", constraint=added_constraint
        )

    def test_add_constraints_with_new_model(self):
        book_with_unique_title_and_pony = ModelState(
            "otherapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("title", models.CharField(max_length=200)),
                ("pony", models.ForeignKey("otherapp.Pony", models.CASCADE)),
            ],
            {
                "constraints": [
                    models.UniqueConstraint(
                        fields=["title", "pony"],
                        name="unique_title_pony",
                    )
                ]
            },
        )
        changes = self.get_changes(
            [self.book_with_no_author],
            [book_with_unique_title_and_pony, self.other_pony],
        )

        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["CreateModel", "AddField", "AddConstraint"],
        )

    def test_add_constraints_with_dict_keys(self):
        """

        Verifies that check constraints using dictionary keys are properly resolved and added to the model state.

        Tests that the check constraint condition is evaluated and rewritten correctly when dictionary keys are used.

        """
        book_types = {"F": "Fantasy", "M": "Mystery"}
        book_with_type = ModelState(
            "testapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("type", models.CharField(max_length=1)),
            ],
            {
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(type__in=book_types.keys()),
                        name="book_type_check",
                    ),
                ],
            },
        )
        book_with_resolved_type = ModelState(
            "testapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("type", models.CharField(max_length=1)),
            ],
            {
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("type__in", tuple(book_types))),
                        name="book_type_check",
                    ),
                ],
            },
        )
        changes = self.get_changes([book_with_type], [book_with_resolved_type])
        self.assertEqual(len(changes), 0)

    def test_add_index_with_new_model(self):
        book_with_index_title_and_pony = ModelState(
            "otherapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("title", models.CharField(max_length=200)),
                ("pony", models.ForeignKey("otherapp.Pony", models.CASCADE)),
            ],
            {
                "indexes": [
                    models.Index(fields=["title", "pony"], name="index_title_pony"),
                ]
            },
        )
        changes = self.get_changes(
            [self.book_with_no_author],
            [book_with_index_title_and_pony, self.other_pony],
        )

        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["CreateModel", "AddField", "AddIndex"],
        )

    def test_remove_constraints(self):
        """
        Tests the detection of removed constraints by verifying the generation of a migration to remove a constraint from the database schema.
        """
        changes = self.get_changes(
            [self.author_name_check_constraint], [self.author_name]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RemoveConstraint"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, model_name="author", name="name_contains_bob"
        )

    def test_add_unique_together(self):
        """
        Tests the detection of unique_together constraints in models, verifying that the correct migration is generated when unique_together is added to a model.
        """
        changes = self.get_changes(
            [self.author_empty, self.book],
            [self.author_empty, self.book_unique_together],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether"])
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            name="book",
            unique_together={("author", "title")},
        )

    def test_remove_unique_together(self):
        """
        Verifies the detection and removal of unique_together constraints in database migrations.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together],
            [self.author_empty, self.book],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterUniqueTogether"])
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, name="book", unique_together=set()
        )

    def test_unique_together_remove_fk(self):
        """
        Tests the removal of a foreign key field in a model with unique_together constraints, ensuring the detection and correct ordering of changes in the migration process.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together],
            [self.author_empty, self.book_with_no_author],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["AlterUniqueTogether", "RemoveField"],
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, name="book", unique_together=set()
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 1, model_name="book", name="author"
        )

    def test_unique_together_no_changes(self):
        """
        unique_together doesn't generate a migration if no
        changes have been made.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together],
            [self.author_empty, self.book_unique_together],
        )
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_unique_together_ordering(self):
        """
        Tests that changes to ordering fields also trigger the unique_together constraint, ensuring data integrity when the order of unique fields is modified.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together],
            [self.author_empty, self.book_unique_together_2],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["AlterUniqueTogether"],
        )
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            name="book",
            unique_together={("title", "author")},
        )

    def test_add_field_and_unique_together(self):
        """
        Tests that when adding a new field to a model and simultaneously updating the unique_together constraint to include the new field, the field is created before the constraint is updated.
        """
        changes = self.get_changes(
            [self.author_empty, self.book],
            [self.author_empty, self.book_unique_together_3],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["AddField", "AlterUniqueTogether"],
        )
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            1,
            name="book",
            unique_together={("title", "newfield")},
        )

    def test_create_model_and_unique_together(self):
        """
        Tests the creation of a model and unique_together constraint in a migration.

        Verifies that the migration correctly creates the models and applies the unique_together constraint as expected.
        """
        author = ModelState(
            "otherapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
            ],
        )
        book_with_author = ModelState(
            "otherapp",
            "Book",
            [
                ("id", models.AutoField(primary_key=True)),
                ("author", models.ForeignKey("otherapp.Author", models.CASCADE)),
                ("title", models.CharField(max_length=200)),
            ],
            {
                "unique_together": {("title", "author")},
            },
        )
        changes = self.get_changes(
            [self.book_with_no_author], [author, book_with_author]
        )
        # Right number of migrations?
        self.assertEqual(len(changes["otherapp"]), 1)
        # Right number of actions?
        migration = changes["otherapp"][0]
        self.assertEqual(len(migration.operations), 3)
        # Right actions order?
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["CreateModel", "AddField", "AlterUniqueTogether"],
        )

    def test_remove_field_and_unique_together(self):
        """

        Tests the removal of fields and updates to unique_together constraints in a model.
        Verifies that the changes are correctly applied in the generated migration.

        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together_3],
            [self.author_empty, self.book_unique_together],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["AlterUniqueTogether", "RemoveField"],
        )
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            0,
            name="book",
            unique_together={("author", "title")},
        )
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            1,
            model_name="book",
            name="newfield",
        )

    def test_alter_field_and_unique_together(self):
        """
        Tests altering a field and updating unique_together constraints after changing the model's structure
        """
        initial_author = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("age", models.IntegerField(db_index=True)),
            ],
            {
                "unique_together": {("name",)},
            },
        )
        author_reversed_constraints = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200, unique=True)),
                ("age", models.IntegerField()),
            ],
            {
                "unique_together": {("age",)},
            },
        )
        changes = self.get_changes([initial_author], [author_reversed_constraints])

        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            [
                "AlterUniqueTogether",
                "AlterField",
                "AlterField",
                "AlterUniqueTogether",
            ],
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="author",
            unique_together=set(),
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            1,
            model_name="author",
            name="age",
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            2,
            model_name="author",
            name="name",
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            3,
            name="author",
            unique_together={("age",)},
        )

    def test_partly_alter_unique_together_increase(self):
        """

        Tests that altering unique_together constraints on a model results in the correct AlterUniqueTogether migration operation.

        Verifies that increasing the constraints by adding a new unique field will create the expected migration.

        """
        initial_author = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("age", models.IntegerField()),
            ],
            {
                "unique_together": {("name",)},
            },
        )
        author_new_constraints = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("age", models.IntegerField()),
            ],
            {
                "unique_together": {("name",), ("age",)},
            },
        )
        changes = self.get_changes([initial_author], [author_new_constraints])

        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            ["AlterUniqueTogether"],
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="author",
            unique_together={("name",), ("age",)},
        )

    def test_partly_alter_unique_together_decrease(self):
        """

        Test case for altering the 'unique_together' constraint on a model, specifically decreasing the number of unique fields.

        Verifies that the required migration to alter the unique constraint is correctly generated.

        """
        initial_author = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("age", models.IntegerField()),
            ],
            {
                "unique_together": {("name",), ("age",)},
            },
        )
        author_new_constraints = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("age", models.IntegerField()),
            ],
            {
                "unique_together": {("name",)},
            },
        )
        changes = self.get_changes([initial_author], [author_new_constraints])

        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            ["AlterUniqueTogether"],
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="author",
            unique_together={("name",)},
        )

    def test_rename_field_and_unique_together(self):
        """
        Tests the renaming of fields and its effect on unique_together constraints, ensuring that fields are properly renamed before updating unique_together constraints in a migration.
        """
        changes = self.get_changes(
            [self.author_empty, self.book_unique_together_3],
            [self.author_empty, self.book_unique_together_4],
            MigrationQuestioner({"ask_rename": True}),
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes,
            "otherapp",
            0,
            ["RenameField", "AlterUniqueTogether"],
        )
        self.assertOperationAttributes(
            changes,
            "otherapp",
            0,
            1,
            name="book",
            unique_together={("title", "newfield2")},
        )

    def test_proxy(self):
        """
        Tests the autodetector's handling of proxy models in migrations, verifying it correctly identifies changes 
        between model definitions with and without proxy options.
        """
        # First, we test adding a proxy model
        changes = self.get_changes(
            [self.author_empty], [self.author_empty, self.author_proxy]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="AuthorProxy",
            options={"proxy": True, "indexes": [], "constraints": []},
        )
        # Now, we test turning a proxy model into a non-proxy model
        # It should delete the proxy then make the real one
        changes = self.get_changes(
            [self.author_empty, self.author_proxy],
            [self.author_empty, self.author_proxy_notproxy],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["DeleteModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="AuthorProxy")
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, name="AuthorProxy", options={}
        )

    def test_proxy_non_model_parent(self):
        """
        Tests the creation of a proxy model with a non-model parent, ensuring a single migration is generated with the correct model attributes.
        """
        class Mixin:
            pass

        author_proxy_non_model_parent = ModelState(
            "testapp",
            "AuthorProxy",
            [],
            {"proxy": True},
            (Mixin, "testapp.author"),
        )
        changes = self.get_changes(
            [self.author_empty],
            [self.author_empty, author_proxy_non_model_parent],
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="AuthorProxy",
            options={"proxy": True, "indexes": [], "constraints": []},
            bases=(Mixin, "testapp.author"),
        )

    def test_proxy_custom_pk(self):
        """
        Tests the autodetector's ability to handle custom foreign keys on proxy models, ensuring correct resolution of custom primary keys.
        """
        # First, we test the default pk field name
        changes = self.get_changes(
            [], [self.author_empty, self.author_proxy_third, self.book_proxy_fk]
        )
        # The model the FK is pointing from and to.
        self.assertEqual(
            changes["otherapp"][0].operations[0].fields[2][1].remote_field.model,
            "thirdapp.AuthorProxy",
        )
        # Now, we test the custom pk field name
        changes = self.get_changes(
            [], [self.author_custom_pk, self.author_proxy_third, self.book_proxy_fk]
        )
        # The model the FK is pointing from and to.
        self.assertEqual(
            changes["otherapp"][0].operations[0].fields[2][1].remote_field.model,
            "thirdapp.AuthorProxy",
        )

    def test_proxy_to_mti_with_fk_to_proxy(self):
        # First, test the pk table and field name.
        """
        .. method:: test_proxy_to_mti_with_fk_to_proxy(self)

            Tests Django model migration functionality when proxied model with a foreign key
            changes from a proxied to a non-proxied model, ensuring the generated migrations
            correctly handle the model changes and dependencies between apps.
        """
        to_state = self.make_project_state(
            [self.author_empty, self.author_proxy_third, self.book_proxy_fk],
        )
        changes = self.get_changes([], to_state)
        fk_field = changes["otherapp"][0].operations[0].fields[2][1]
        self.assertEqual(
            to_state.get_concrete_model_key(fk_field.remote_field.model),
            ("testapp", "author"),
        )
        self.assertEqual(fk_field.remote_field.model, "thirdapp.AuthorProxy")

        # Change AuthorProxy to use MTI.
        from_state = to_state.clone()
        to_state = self.make_project_state(
            [self.author_empty, self.author_proxy_third_notproxy, self.book_proxy_fk],
        )
        changes = self.get_changes(from_state, to_state)
        # Right number/type of migrations for the AuthorProxy model?
        self.assertNumberMigrations(changes, "thirdapp", 1)
        self.assertOperationTypes(
            changes, "thirdapp", 0, ["DeleteModel", "CreateModel"]
        )
        # Right number/type of migrations for the Book model with a FK to
        # AuthorProxy?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterField"])
        # otherapp should depend on thirdapp.
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("thirdapp", "auto_1")]
        )
        # Now, test the pk table and field name.
        fk_field = changes["otherapp"][0].operations[0].field
        self.assertEqual(
            to_state.get_concrete_model_key(fk_field.remote_field.model),
            ("thirdapp", "authorproxy"),
        )
        self.assertEqual(fk_field.remote_field.model, "thirdapp.AuthorProxy")

    def test_proxy_to_mti_with_fk_to_proxy_proxy(self):
        # First, test the pk table and field name.
        """
        This function tests the handling of a proxy model with a foreign key to another proxy model, verifying that the migrations are correctly generated when the target model of the foreign key changes from a proxy model to a non-proxy model and that the foreign key is correctly updated.
        """
        to_state = self.make_project_state(
            [
                self.author_empty,
                self.author_proxy,
                self.author_proxy_proxy,
                self.book_proxy_proxy_fk,
            ]
        )
        changes = self.get_changes([], to_state)
        fk_field = changes["otherapp"][0].operations[0].fields[1][1]
        self.assertEqual(
            to_state.get_concrete_model_key(fk_field.remote_field.model),
            ("testapp", "author"),
        )
        self.assertEqual(fk_field.remote_field.model, "testapp.AAuthorProxyProxy")

        # Change AuthorProxy to use MTI. FK still points to AAuthorProxyProxy,
        # a proxy of AuthorProxy.
        from_state = to_state.clone()
        to_state = self.make_project_state(
            [
                self.author_empty,
                self.author_proxy_notproxy,
                self.author_proxy_proxy,
                self.book_proxy_proxy_fk,
            ]
        )
        changes = self.get_changes(from_state, to_state)
        # Right number/type of migrations for the AuthorProxy model?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["DeleteModel", "CreateModel"])
        # Right number/type of migrations for the Book model with a FK to
        # AAuthorProxyProxy?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterField"])
        # otherapp should depend on testapp.
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("testapp", "auto_1")]
        )
        # Now, test the pk table and field name.
        fk_field = changes["otherapp"][0].operations[0].field
        self.assertEqual(
            to_state.get_concrete_model_key(fk_field.remote_field.model),
            ("testapp", "authorproxy"),
        )
        self.assertEqual(fk_field.remote_field.model, "testapp.AAuthorProxyProxy")

    def test_unmanaged_create(self):
        """
        Tests that the autodetector correctly handles unmanaged model creation by verifying the generated migration operations.
        """
        # First, we test adding an unmanaged model
        changes = self.get_changes(
            [self.author_empty], [self.author_empty, self.author_unmanaged]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="AuthorUnmanaged", options={"managed": False}
        )

    def test_unmanaged_delete(self):
        changes = self.get_changes(
            [self.author_empty, self.author_unmanaged], [self.author_empty]
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["DeleteModel"])

    def test_unmanaged_to_managed(self):
        # Now, we test turning an unmanaged model into a managed model
        changes = self.get_changes(
            [self.author_empty, self.author_unmanaged],
            [self.author_empty, self.author_unmanaged_managed],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="authorunmanaged", options={}
        )

    def test_managed_to_unmanaged(self):
        # Now, we turn managed to unmanaged.
        changes = self.get_changes(
            [self.author_empty, self.author_unmanaged_managed],
            [self.author_empty, self.author_unmanaged],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="authorunmanaged", options={"managed": False}
        )

    def test_unmanaged_custom_pk(self):
        """
        Tests that the autodetector correctly handles custom foreign keys on unmanaged models.
        """
        # First, we test the default pk field name
        changes = self.get_changes([], [self.author_unmanaged_default_pk, self.book])
        # The model the FK on the book model points to.
        fk_field = changes["otherapp"][0].operations[0].fields[2][1]
        self.assertEqual(fk_field.remote_field.model, "testapp.Author")
        # Now, we test the custom pk field name
        changes = self.get_changes([], [self.author_unmanaged_custom_pk, self.book])
        # The model the FK on the book model points to.
        fk_field = changes["otherapp"][0].operations[0].fields[2][1]
        self.assertEqual(fk_field.remote_field.model, "testapp.Author")

    @override_settings(AUTH_USER_MODEL="thirdapp.CustomUser")
    def test_swappable(self):
        """
        Tests migration generation when using a custom user model, ensuring that dependencies and operations are correctly handled.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            changes = self.get_changes(
                [self.custom_user], [self.custom_user, self.author_with_custom_user]
            )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertMigrationDependencies(
            changes, "testapp", 0, [("__setting__", "AUTH_USER_MODEL")]
        )

    def test_swappable_lowercase(self):
        """
        Tests that model swappable settings are properly handled during model creation, specifically when the swappable model name is in lowercase.
        """
        model_state = ModelState(
            "testapp",
            "Document",
            [
                ("id", models.AutoField(primary_key=True)),
                (
                    "owner",
                    models.ForeignKey(
                        settings.AUTH_USER_MODEL.lower(),
                        models.CASCADE,
                    ),
                ),
            ],
        )
        with isolate_lru_cache(apps.get_swappable_settings_name):
            changes = self.get_changes([], [model_state])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Document")
        self.assertMigrationDependencies(
            changes,
            "testapp",
            0,
            [("__setting__", "AUTH_USER_MODEL")],
        )

    @override_settings(AUTH_USER_MODEL="thirdapp.CustomUser")
    def test_swappable_many_to_many_model_case(self):
        """
        Tests the swappable nature of a ManyToMany model field, ensuring that changes are not detected when the related model's name is case-insensitive.
        """
        document_lowercase = ModelState(
            "testapp",
            "Document",
            [
                ("id", models.AutoField(primary_key=True)),
                ("owners", models.ManyToManyField(settings.AUTH_USER_MODEL.lower())),
            ],
        )
        document = ModelState(
            "testapp",
            "Document",
            [
                ("id", models.AutoField(primary_key=True)),
                ("owners", models.ManyToManyField(settings.AUTH_USER_MODEL)),
            ],
        )
        with isolate_lru_cache(apps.get_swappable_settings_name):
            changes = self.get_changes(
                [self.custom_user, document_lowercase],
                [self.custom_user, document],
            )
        self.assertEqual(len(changes), 0)

    def test_swappable_changed(self):
        """
        Tests that a model's foreign key field is properly updated when the swappable user model is changed.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            before = self.make_project_state([self.custom_user, self.author_with_user])
            with override_settings(AUTH_USER_MODEL="thirdapp.CustomUser"):
                after = self.make_project_state(
                    [self.custom_user, self.author_with_custom_user]
                )
            autodetector = MigrationAutodetector(before, after)
            changes = autodetector._detect_changes()
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, model_name="author", name="user"
        )
        fk_field = changes["testapp"][0].operations[0].field
        self.assertEqual(fk_field.remote_field.model, "thirdapp.CustomUser")

    def test_add_field_with_default(self):
        """
        Tests that adding a field with a default value to a model creates the expected database migration.
        """
        changes = self.get_changes([self.author_empty], [self.author_name_default])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="name")

    def test_custom_deconstructible(self):
        """
        Two instances which deconstruct to the same value aren't considered a
        change.
        """
        changes = self.get_changes(
            [self.author_name_deconstructible_1], [self.author_name_deconstructible_2]
        )
        # Right number of migrations?
        self.assertEqual(len(changes), 0)

    def test_deconstruct_field_kwarg(self):
        """Field instances are handled correctly by nested deconstruction."""
        changes = self.get_changes(
            [self.author_name_deconstructible_3], [self.author_name_deconstructible_4]
        )
        self.assertEqual(changes, {})

    def test_deconstructible_list(self):
        """
        Tests whether the deconstruction process correctly handles lists by comparing the changes between different list configurations, verifying that changes are accurately detected when the list contents differ.
        """
        # When lists contain items that deconstruct to identical values, those lists
        # should be considered equal for the purpose of detecting state changes
        # (even if the original items are unequal).
        changes = self.get_changes(
            [self.author_name_deconstructible_list_1],
            [self.author_name_deconstructible_list_2],
        )
        self.assertEqual(changes, {})
        # Legitimate differences within the deconstructed lists should be reported
        # as a change
        changes = self.get_changes(
            [self.author_name_deconstructible_list_1],
            [self.author_name_deconstructible_list_3],
        )
        self.assertEqual(len(changes), 1)

    def test_deconstructible_tuple(self):
        """
        Tests whether tuple deconstruction works as expected by checking for changes when comparing different deconstructible tuples.
        """
        # When tuples contain items that deconstruct to identical values, those tuples
        # should be considered equal for the purpose of detecting state changes
        # (even if the original items are unequal).
        changes = self.get_changes(
            [self.author_name_deconstructible_tuple_1],
            [self.author_name_deconstructible_tuple_2],
        )
        self.assertEqual(changes, {})
        # Legitimate differences within the deconstructed tuples should be reported
        # as a change
        changes = self.get_changes(
            [self.author_name_deconstructible_tuple_1],
            [self.author_name_deconstructible_tuple_3],
        )
        self.assertEqual(len(changes), 1)

    def test_deconstructible_dict(self):
        """
        Tests that nested deconstruction correctly handles dictionary values, verifying that changes are detected and reported accurately when dictionary contents differ.
        """
        # When dicts contain items whose values deconstruct to identical values,
        # those dicts should be considered equal for the purpose of detecting
        # state changes (even if the original values are unequal).
        changes = self.get_changes(
            [self.author_name_deconstructible_dict_1],
            [self.author_name_deconstructible_dict_2],
        )
        self.assertEqual(changes, {})
        # Legitimate differences within the deconstructed dicts should be reported
        # as a change
        changes = self.get_changes(
            [self.author_name_deconstructible_dict_1],
            [self.author_name_deconstructible_dict_3],
        )
        self.assertEqual(len(changes), 1)

    def test_nested_deconstructible_objects(self):
        """
        Tests the recursive application of nested deconstruction to objects, verifying that changes are correctly detected in their arguments and keyword arguments.
        """
        # If the items within a deconstructed object's args/kwargs have the same
        # deconstructed values - whether or not the items themselves are different
        # instances - then the object as a whole is regarded as unchanged.
        changes = self.get_changes(
            [self.author_name_nested_deconstructible_1],
            [self.author_name_nested_deconstructible_2],
        )
        self.assertEqual(changes, {})
        # Differences that exist solely within the args list of a deconstructed object
        # should be reported as changes
        changes = self.get_changes(
            [self.author_name_nested_deconstructible_1],
            [self.author_name_nested_deconstructible_changed_arg],
        )
        self.assertEqual(len(changes), 1)
        # Additional args should also be reported as a change
        changes = self.get_changes(
            [self.author_name_nested_deconstructible_1],
            [self.author_name_nested_deconstructible_extra_arg],
        )
        self.assertEqual(len(changes), 1)
        # Differences that exist solely within the kwargs dict of a deconstructed object
        # should be reported as changes
        changes = self.get_changes(
            [self.author_name_nested_deconstructible_1],
            [self.author_name_nested_deconstructible_changed_kwarg],
        )
        self.assertEqual(len(changes), 1)
        # Additional kwargs should also be reported as a change
        changes = self.get_changes(
            [self.author_name_nested_deconstructible_1],
            [self.author_name_nested_deconstructible_extra_kwarg],
        )
        self.assertEqual(len(changes), 1)

    def test_deconstruct_type(self):
        """
        Tests that uninstantiated models with deconstruct method are correctly serialized during deep_deconstruct operation, ensuring proper migration generation.
        """
        author = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                (
                    "name",
                    models.CharField(
                        max_length=200,
                        # IntegerField intentionally not instantiated.
                        default=models.IntegerField,
                    ),
                ),
            ],
        )
        changes = self.get_changes([], [author])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])

    def test_replace_string_with_foreignkey(self):
        """
        Tests replacement of a string field with a foreign key field in a Django model migration, ensuring a smooth transition when removing a CharField and adding a ForeignKey in its place.
        """
        changes = self.get_changes(
            [self.author_with_publisher_string],
            [self.author_with_publisher, self.publisher],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "RemoveField", "AddField"]
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="publisher_name")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="publisher")

    def test_foreign_key_removed_before_target_model(self):
        """

        Tests that when a foreign key and its target model are removed in the same change,
        the foreign key field is deleted before the target model to maintain consistency.

        """
        changes = self.get_changes(
            [self.author_with_publisher, self.publisher], [self.author_name]
        )  # removes both the model and FK
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["RemoveField", "DeleteModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_add_many_to_many(self, mocked_ask_method):
        """
        Test that adding a ManyToManyField does not prompt for a default value, ensuring that the migration process runs smoothly without unnecessary user input.
        """
        changes = self.get_changes(
            [self.author_empty, self.publisher], [self.author_with_m2m, self.publisher]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="publishers")

    def test_alter_many_to_many(self):
        changes = self.get_changes(
            [self.author_with_m2m, self.publisher],
            [self.author_with_m2m_blank, self.publisher],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="publishers")

    def test_create_with_through_model(self):
        """

            Tests that adding a many-to-many field with a through model correctly orders 
            the creation of models and the addition of the many-to-many field.

        """
        changes = self.get_changes(
            [], [self.author_with_m2m_through, self.publisher, self.contract]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            [
                "CreateModel",
                "CreateModel",
                "CreateModel",
                "AddField",
            ],
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="Contract")
        self.assertOperationAttributes(
            changes, "testapp", 0, 3, model_name="author", name="publishers"
        )

    def test_create_with_through_model_separate_apps(self):
        """
        Tests the creation of a model with a ManyToManyField using a through model that is located in a separate application, ensuring the correct migrations are generated for all involved models.
        """
        author_with_m2m_through = ModelState(
            "authors",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                (
                    "publishers",
                    models.ManyToManyField(
                        "testapp.Publisher", through="contract.Contract"
                    ),
                ),
            ],
        )
        contract = ModelState(
            "contract",
            "Contract",
            [
                ("id", models.AutoField(primary_key=True)),
                ("author", models.ForeignKey("authors.Author", models.CASCADE)),
                ("publisher", models.ForeignKey("testapp.Publisher", models.CASCADE)),
            ],
        )
        changes = self.get_changes(
            [], [author_with_m2m_through, self.publisher, contract]
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertNumberMigrations(changes, "contract", 1)
        self.assertNumberMigrations(changes, "authors", 2)
        self.assertMigrationDependencies(
            changes,
            "authors",
            1,
            {("authors", "auto_1"), ("contract", "auto_1"), ("testapp", "auto_1")},
        )
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Publisher")
        self.assertOperationTypes(changes, "contract", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "contract", 0, 0, name="Contract")
        self.assertOperationTypes(changes, "authors", 0, ["CreateModel"])
        self.assertOperationTypes(changes, "authors", 1, ["AddField"])
        self.assertOperationAttributes(changes, "authors", 0, 0, name="Author")
        self.assertOperationAttributes(
            changes, "authors", 1, 0, model_name="author", name="publishers"
        )

    def test_many_to_many_removed_before_through_model(self):
        """
        Test that removing a ManyToManyField and its through model in the same change
        maintains consistency by removing the field before the model.
        """
        changes = self.get_changes(
            [
                self.book_with_multiple_authors_through_attribution,
                self.author_name,
                self.attribution,
            ],
            [self.book_with_no_author, self.author_name],
        )
        # Remove both the through model and ManyToMany
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes, "otherapp", 0, ["RemoveField", "DeleteModel"]
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, name="authors", model_name="book"
        )
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="Attribution")

    def test_many_to_many_removed_before_through_model_2(self):
        """
        Checks that a ManyToManyField is removed before its related model to maintain consistency when both are deleted in the same change.
        """
        changes = self.get_changes(
            [
                self.book_with_multiple_authors_through_attribution,
                self.author_name,
                self.attribution,
            ],
            [self.author_name],
        )
        # Remove both the through model and ManyToMany
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes, "otherapp", 0, ["RemoveField", "DeleteModel", "DeleteModel"]
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, name="authors", model_name="book"
        )
        self.assertOperationAttributes(changes, "otherapp", 0, 1, name="Attribution")
        self.assertOperationAttributes(changes, "otherapp", 0, 2, name="Book")

    def test_m2m_w_through_multistep_remove(self):
        """
        Tests the scenario where a model with a many-to-many field that uses a \"through\" model cannot be removed in the same migration as the \"through\" model, ensuring the autodetector generates multiple migrations to avoid an inconsistent schema state.
        """
        changes = self.get_changes(
            [self.author_with_m2m_through, self.publisher, self.contract],
            [self.publisher],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            ["RemoveField", "RemoveField", "DeleteModel", "DeleteModel"],
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", model_name="contract"
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, name="publisher", model_name="contract"
        )
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 3, name="Contract")

    def test_concrete_field_changed_to_many_to_many(self):
        """
        Tests database migration when changing a concrete field to a ManyToManyField, verifying that the concrete field is removed and the ManyToManyField is added correctly.
        """
        changes = self.get_changes(
            [self.author_with_former_m2m], [self.author_with_m2m, self.publisher]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "RemoveField", "AddField"]
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Publisher")
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, name="publishers", model_name="author"
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 2, name="publishers", model_name="author"
        )

    def test_many_to_many_changed_to_concrete_field(self):
        """

        Tests a database migration where a ManyToManyField is replaced with a concrete field.
        Verifies that the migration involves removing the m2m field and adding the new concrete field.

        """
        changes = self.get_changes(
            [self.author_with_m2m, self.publisher], [self.author_with_former_m2m]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["RemoveField", "DeleteModel", "AddField"]
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="publishers", model_name="author"
        )
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Publisher")
        self.assertOperationAttributes(
            changes, "testapp", 0, 2, name="publishers", model_name="author"
        )
        self.assertOperationFieldAttributes(changes, "testapp", 0, 2, max_length=100)

    def test_non_circular_foreignkey_dependency_removal(self):
        """
        Tests the correct removal of models with a circular ForeignKey dependency by the autodetector, ensuring that the models are deleted in the correct order to avoid dependency issues.
        """
        changes = self.get_changes(
            [self.author_with_publisher, self.publisher_with_author], []
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["RemoveField", "DeleteModel", "DeleteModel"]
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", model_name="publisher"
        )
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="Publisher")

    def test_alter_model_options(self):
        """

        Tests the behavior of altering model options.

        Verifies that changing a model's options generates the correct AlterModelOptions
        operation, and that the operation includes the expected options.

        """
        changes = self.get_changes([self.author_empty], [self.author_with_options])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            options={
                "permissions": [("can_hire", "Can hire")],
                "verbose_name": "Authi",
            },
        )

        # Changing them back to empty should also make a change
        changes = self.get_changes([self.author_with_options], [self.author_empty])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", options={}
        )

    def test_alter_model_options_proxy(self):
        """
        Tests that changing the options of a proxy model results in the expected migration, specifically an AlterModelOptions operation.
        """
        changes = self.get_changes(
            [self.author_proxy, self.author_empty],
            [self.author_proxy_options, self.author_empty],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="authorproxy",
            options={"verbose_name": "Super Author"},
        )

    def test_set_alter_order_with_respect_to(self):
        """
        Tests that setting the order_with_respect_to attribute on a model field creates an AlterOrderWithRespectTo migration.
        """
        changes = self.get_changes(
            [self.book, self.author_with_book],
            [self.book, self.author_with_book_order_wrt],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AlterOrderWithRespectTo"])
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", order_with_respect_to="book"
        )

    def test_add_alter_order_with_respect_to(self):
        """
        Tests the addition of a foreign key and ordering with respect to it, ensuring that database operations are executed in the correct order.
        """
        changes = self.get_changes(
            [self.author_name], [self.book, self.author_with_book_order_wrt]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["AddField", "AlterOrderWithRespectTo"]
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, model_name="author", name="book"
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, name="author", order_with_respect_to="book"
        )

    def test_remove_alter_order_with_respect_to(self):
        """

        Tests that removing an order_with_respect_to field is handled correctly when 
        removing the corresponding foreign key field, ensuring the operations are applied in the right order.

        """
        changes = self.get_changes(
            [self.book, self.author_with_book_order_wrt], [self.author_name]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["AlterOrderWithRespectTo", "RemoveField"]
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 0, name="author", order_with_respect_to=None
        )
        self.assertOperationAttributes(
            changes, "testapp", 0, 1, model_name="author", name="book"
        )

    def test_add_model_order_with_respect_to(self):
        """
        Checks that setting order_with_respect_to when adding a model results in the correct ordering of operations in migrations.
        """
        changes = self.get_changes([], [self.book, self.author_with_book_order_wrt])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="Author",
            options={"order_with_respect_to": "book"},
        )
        self.assertNotIn(
            "_order",
            [name for name, field in changes["testapp"][0].operations[0].fields],
        )

    def test_add_model_order_with_respect_to_unique_together(self):
        changes = self.get_changes(
            [],
            [
                self.book,
                ModelState(
                    "testapp",
                    "Author",
                    [
                        ("id", models.AutoField(primary_key=True)),
                        ("name", models.CharField(max_length=200)),
                        ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
                    ],
                    options={
                        "order_with_respect_to": "book",
                        "unique_together": {("id", "_order")},
                    },
                ),
            ],
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="Author",
            options={
                "order_with_respect_to": "book",
                "unique_together": {("id", "_order")},
            },
        )

    def test_add_model_order_with_respect_to_constraint(self):
        """
        Tests adding a model with an order_with_respect_to constraint, verifying the correct migration is generated when the constraint is applied to a related field.
        """
        after = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
            ],
            options={
                "order_with_respect_to": "book",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(_order__gt=1), name="book_order_gt_1"
                    ),
                ],
            },
        )
        changes = self.get_changes([], [self.book, after])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes,
            "testapp",
            0,
            ["CreateModel"],
        )
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="Author",
            options={
                "order_with_respect_to": "book",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(_order__gt=1), name="book_order_gt_1"
                    )
                ],
            },
        )

    def test_add_model_order_with_respect_to_index(self):
        """
        Tests the addition of a model with an order_with_respect_to field and a corresponding index, verifying that the correct migration is generated.
        """
        after = ModelState(
            "testapp",
            "Author",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=200)),
                ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
            ],
            options={
                "order_with_respect_to": "book",
                "indexes": [models.Index(fields=["_order"], name="book_order_idx")],
            },
        )
        changes = self.get_changes([], [self.book, after])
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "testapp",
            0,
            0,
            name="Author",
            options={
                "order_with_respect_to": "book",
                "indexes": [models.Index(fields=["_order"], name="book_order_idx")],
            },
        )

    def test_set_alter_order_with_respect_to_index_constraint_unique_together(self):
        """
        Tests altering the order of a model with respect to a related model, while also considering index and constraint changes, including adding indexes, constraints, and altering unique together constraints.
        """
        tests = [
            (
                "AddIndex",
                {
                    "indexes": [
                        models.Index(fields=["_order"], name="book_order_idx"),
                    ]
                },
            ),
            (
                "AddConstraint",
                {
                    "constraints": [
                        models.CheckConstraint(
                            condition=models.Q(_order__gt=1),
                            name="book_order_gt_1",
                        ),
                    ]
                },
            ),
            ("AlterUniqueTogether", {"unique_together": {("id", "_order")}}),
        ]
        for operation, extra_option in tests:
            with self.subTest(operation=operation):
                after = ModelState(
                    "testapp",
                    "Author",
                    [
                        ("id", models.AutoField(primary_key=True)),
                        ("name", models.CharField(max_length=200)),
                        ("book", models.ForeignKey("otherapp.Book", models.CASCADE)),
                    ],
                    options={
                        "order_with_respect_to": "book",
                        **extra_option,
                    },
                )
                changes = self.get_changes(
                    [self.book, self.author_with_book],
                    [self.book, after],
                )
                self.assertNumberMigrations(changes, "testapp", 1)
                self.assertOperationTypes(
                    changes,
                    "testapp",
                    0,
                    [
                        "AlterOrderWithRespectTo",
                        operation,
                    ],
                )

    def test_alter_model_managers(self):
        """
        Verifies that changing the model managers triggers the creation of an AlterModelManagers operation in the migration changes.
        """
        changes = self.get_changes([self.other_pony], [self.other_pony_food])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterModelManagers"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="pony")
        self.assertEqual(
            [name for name, mgr in changes["otherapp"][0].operations[0].managers],
            ["food_qs", "food_mgr", "food_mgr_kwargs"],
        )
        self.assertEqual(
            changes["otherapp"][0].operations[0].managers[1][1].args, ("a", "b", 1, 2)
        )
        self.assertEqual(
            changes["otherapp"][0].operations[0].managers[2][1].args, ("x", "y", 3, 4)
        )

    def test_swappable_first_inheritance(self):
        """
        Tests that swappable models correctly get their CreateModel operations ordered first in migrations, specifically when inheriting from a parent model.
        """
        changes = self.get_changes([], [self.custom_user, self.aardvark])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "thirdapp", 1)
        self.assertOperationTypes(
            changes, "thirdapp", 0, ["CreateModel", "CreateModel"]
        )
        self.assertOperationAttributes(changes, "thirdapp", 0, 0, name="CustomUser")
        self.assertOperationAttributes(changes, "thirdapp", 0, 1, name="Aardvark")

    def test_default_related_name_option(self):
        """
        Tests the default_related_name option for models to ensure correct migration creation and alteration.
        """
        model_state = ModelState(
            "app",
            "model",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
            options={"default_related_name": "related_name"},
        )
        changes = self.get_changes([], [model_state])
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["CreateModel"])
        self.assertOperationAttributes(
            changes,
            "app",
            0,
            0,
            name="model",
            options={"default_related_name": "related_name"},
        )
        altered_model_state = ModelState(
            "app",
            "Model",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
        )
        changes = self.get_changes([model_state], [altered_model_state])
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["AlterModelOptions"])
        self.assertOperationAttributes(changes, "app", 0, 0, name="model", options={})

    @override_settings(AUTH_USER_MODEL="thirdapp.CustomUser")
    def test_swappable_first_setting(self):
        """
        Tests that swappable models have their CreateModel operation applied first when generating migrations.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            changes = self.get_changes([], [self.custom_user_no_inherit, self.aardvark])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "thirdapp", 1)
        self.assertOperationTypes(
            changes, "thirdapp", 0, ["CreateModel", "CreateModel"]
        )
        self.assertOperationAttributes(changes, "thirdapp", 0, 0, name="CustomUser")
        self.assertOperationAttributes(changes, "thirdapp", 0, 1, name="Aardvark")

    def test_bases_first(self):
        """
        Tests that model bases are created before their derived models, ensuring the correct migration order.
        """
        changes = self.get_changes(
            [], [self.aardvark_based_on_author, self.author_name]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Aardvark")

    def test_bases_first_mixed_case_app_label(self):
        """
        Tests that model state changes are correctly serialized into database migrations when models are defined in an app with a mixed case label and one model inherits from another model in the same app.
        """
        app_label = "MiXedCaseApp"
        changes = self.get_changes(
            [],
            [
                ModelState(
                    app_label,
                    "owner",
                    [
                        ("id", models.AutoField(primary_key=True)),
                    ],
                ),
                ModelState(
                    app_label,
                    "place",
                    [
                        ("id", models.AutoField(primary_key=True)),
                        (
                            "owner",
                            models.ForeignKey("MiXedCaseApp.owner", models.CASCADE),
                        ),
                    ],
                ),
                ModelState(app_label, "restaurant", [], bases=("MiXedCaseApp.place",)),
            ],
        )
        self.assertNumberMigrations(changes, app_label, 1)
        self.assertOperationTypes(
            changes,
            app_label,
            0,
            [
                "CreateModel",
                "CreateModel",
                "CreateModel",
            ],
        )
        self.assertOperationAttributes(changes, app_label, 0, 0, name="owner")
        self.assertOperationAttributes(changes, app_label, 0, 1, name="place")
        self.assertOperationAttributes(changes, app_label, 0, 2, name="restaurant")

    def test_multiple_bases(self):
        """
        Tests model inheritance to ensure that fields from base models are not incorrectly moved into AddField operations when creating migrations. Verifies that models with multiple bases are created correctly.
        """
        A = ModelState("app", "A", [("a_id", models.AutoField(primary_key=True))])
        B = ModelState("app", "B", [("b_id", models.AutoField(primary_key=True))])
        C = ModelState("app", "C", [], bases=("app.A", "app.B"))
        D = ModelState("app", "D", [], bases=("app.A", "app.B"))
        E = ModelState("app", "E", [], bases=("app.A", "app.B"))
        changes = self.get_changes([], [A, B, C, D, E])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(
            changes,
            "app",
            0,
            ["CreateModel", "CreateModel", "CreateModel", "CreateModel", "CreateModel"],
        )
        self.assertOperationAttributes(changes, "app", 0, 0, name="A")
        self.assertOperationAttributes(changes, "app", 0, 1, name="B")
        self.assertOperationAttributes(changes, "app", 0, 2, name="C")
        self.assertOperationAttributes(changes, "app", 0, 3, name="D")
        self.assertOperationAttributes(changes, "app", 0, 4, name="E")

    def test_proxy_bases_first(self):
        """
        Tests that proxy models' bases are processed before their own definitions in migrations.
        """
        changes = self.get_changes(
            [], [self.author_empty, self.author_proxy, self.author_proxy_proxy]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "CreateModel", "CreateModel"]
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="AuthorProxy")
        self.assertOperationAttributes(
            changes, "testapp", 0, 2, name="AAuthorProxyProxy"
        )

    def test_pk_fk_included(self):
        """
        Tests that a primary key included in a foreign key relation is correctly included in the CreateModel operation when generating database migrations.
        """
        changes = self.get_changes([], [self.aardvark_pk_fk_author, self.author_name])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel", "CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Author")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="Aardvark")

    def test_first_dependency(self):
        """
        Tests dependency detection for an app with no migrations, ensuring it depends on __first__.
        """
        # Load graph
        loader = MigrationLoader(connection)
        before = self.make_project_state([])
        after = self.make_project_state([self.book_migrations_fk])
        after.real_apps = {"migrations"}
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes(graph=loader.graph)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Book")
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("migrations", "__first__")]
        )

    @override_settings(MIGRATION_MODULES={"migrations": "migrations.test_migrations"})
    def test_last_dependency(self):
        """
        Tests that a dependency to an app with existing migrations uses the last migration of that app.
        """
        # Load graph
        loader = MigrationLoader(connection)
        before = self.make_project_state([])
        after = self.make_project_state([self.book_migrations_fk])
        after.real_apps = {"migrations"}
        autodetector = MigrationAutodetector(before, after)
        changes = autodetector._detect_changes(graph=loader.graph)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "otherapp", 0, 0, name="Book")
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("migrations", "0002_second")]
        )

    def test_alter_fk_before_model_deletion(self):
        """
        Verifies the correct order of operations when deleting a model with foreign keys, ensuring that foreign key alterations occur before model deletion.
        """
        changes = self.get_changes(
            [self.author_name, self.publisher_with_author],
            [self.aardvark_testapp, self.publisher_with_aardvark_author],
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(
            changes, "testapp", 0, ["CreateModel", "AlterField", "DeleteModel"]
        )
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Aardvark")
        self.assertOperationAttributes(changes, "testapp", 0, 1, name="author")
        self.assertOperationAttributes(changes, "testapp", 0, 2, name="Author")

    def test_fk_dependency_other_app(self):
        """

        Tests that ForeignKeys correctly establish dependencies on models from other applications.

        """
        changes = self.get_changes(
            [self.author_name, self.book], [self.author_with_book, self.book]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="book")
        self.assertMigrationDependencies(
            changes, "testapp", 0, [("otherapp", "__first__")]
        )

    def test_alter_unique_together_fk_to_m2m(self):
        """
        Tests altering a unique together constraint with a foreign key to a many-to-many field, verifying the correct operations are applied in the resulting migration.
        """
        changes = self.get_changes(
            [self.author_name, self.book_unique_together],
            [
                self.author_name,
                ModelState(
                    "otherapp",
                    "Book",
                    [
                        ("id", models.AutoField(primary_key=True)),
                        ("author", models.ManyToManyField("testapp.Author")),
                        ("title", models.CharField(max_length=200)),
                    ],
                ),
            ],
        )
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(
            changes, "otherapp", 0, ["AlterUniqueTogether", "RemoveField", "AddField"]
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 0, name="book", unique_together=set()
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 1, model_name="book", name="author"
        )
        self.assertOperationAttributes(
            changes, "otherapp", 0, 2, model_name="book", name="author"
        )

    def test_alter_field_to_fk_dependency_other_app(self):
        changes = self.get_changes(
            [self.author_empty, self.book_with_no_author_fk],
            [self.author_empty, self.book],
        )
        self.assertNumberMigrations(changes, "otherapp", 1)
        self.assertOperationTypes(changes, "otherapp", 0, ["AlterField"])
        self.assertMigrationDependencies(
            changes, "otherapp", 0, [("testapp", "__first__")]
        )

    def test_circular_dependency_mixed_addcreate(self):
        """
        Tests the dependency resolver to ensure it correctly prioritizes create model operations before add field operations in the presence of circular dependencies involving mixed model creation and foreign key additions.
        """
        address = ModelState(
            "a",
            "Address",
            [
                ("id", models.AutoField(primary_key=True)),
                ("country", models.ForeignKey("b.DeliveryCountry", models.CASCADE)),
            ],
        )
        person = ModelState(
            "a",
            "Person",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
        )
        apackage = ModelState(
            "b",
            "APackage",
            [
                ("id", models.AutoField(primary_key=True)),
                ("person", models.ForeignKey("a.Person", models.CASCADE)),
            ],
        )
        country = ModelState(
            "b",
            "DeliveryCountry",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
        )
        changes = self.get_changes([], [address, person, apackage, country])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "a", 2)
        self.assertNumberMigrations(changes, "b", 1)
        self.assertOperationTypes(changes, "a", 0, ["CreateModel", "CreateModel"])
        self.assertOperationTypes(changes, "a", 1, ["AddField"])
        self.assertOperationTypes(changes, "b", 0, ["CreateModel", "CreateModel"])

    @override_settings(AUTH_USER_MODEL="a.Tenant")
    def test_circular_dependency_swappable(self):
        """
        Tests the handling of circular dependencies when using swappable models, ensuring that the dependency resolver can correctly resolve these models and generate the expected migrations.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            tenant = ModelState(
                "a",
                "Tenant",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("primary_address", models.ForeignKey("b.Address", models.CASCADE)),
                ],
                bases=(AbstractBaseUser,),
            )
            address = ModelState(
                "b",
                "Address",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "tenant",
                        models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE),
                    ),
                ],
            )
            changes = self.get_changes([], [address, tenant])

        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "a", 2)
        self.assertOperationTypes(changes, "a", 0, ["CreateModel"])
        self.assertOperationTypes(changes, "a", 1, ["AddField"])
        self.assertMigrationDependencies(changes, "a", 0, [])
        self.assertMigrationDependencies(
            changes, "a", 1, [("a", "auto_1"), ("b", "auto_1")]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "b", 1)
        self.assertOperationTypes(changes, "b", 0, ["CreateModel"])
        self.assertMigrationDependencies(
            changes, "b", 0, [("__setting__", "AUTH_USER_MODEL")]
        )

    @override_settings(AUTH_USER_MODEL="b.Tenant")
    def test_circular_dependency_swappable2(self):
        """
        Tests the dependency resolver's ability to handle circular dependencies involving swappable models, where the swappable model is not the first migrated model.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            address = ModelState(
                "a",
                "Address",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "tenant",
                        models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE),
                    ),
                ],
            )
            tenant = ModelState(
                "b",
                "Tenant",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("primary_address", models.ForeignKey("a.Address", models.CASCADE)),
                ],
                bases=(AbstractBaseUser,),
            )
            changes = self.get_changes([], [address, tenant])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "a", 2)
        self.assertOperationTypes(changes, "a", 0, ["CreateModel"])
        self.assertOperationTypes(changes, "a", 1, ["AddField"])
        self.assertMigrationDependencies(changes, "a", 0, [])
        self.assertMigrationDependencies(
            changes, "a", 1, [("__setting__", "AUTH_USER_MODEL"), ("a", "auto_1")]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "b", 1)
        self.assertOperationTypes(changes, "b", 0, ["CreateModel"])
        self.assertMigrationDependencies(changes, "b", 0, [("a", "auto_1")])

    @override_settings(AUTH_USER_MODEL="a.Person")
    def test_circular_dependency_swappable_self(self):
        """
        Tests the dependency resolver's ability to handle swappable models by creating a circular dependency between the AUTH_USER_MODEL and another model, verifying that a single migration is generated with a CreateModel operation and no dependencies.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            person = ModelState(
                "a",
                "Person",
                [
                    ("id", models.AutoField(primary_key=True)),
                    (
                        "parent1",
                        models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            models.CASCADE,
                            related_name="children",
                        ),
                    ),
                ],
            )
            changes = self.get_changes([], [person])
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "a", 1)
        self.assertOperationTypes(changes, "a", 0, ["CreateModel"])
        self.assertMigrationDependencies(changes, "a", 0, [])

    @override_settings(AUTH_USER_MODEL="a.User")
    def test_swappable_circular_multi_mti(self):
        """
        Tests the migration generation for a complex model setup involving swappable user models, 
        multitable inheritance, and circular model dependencies.
        """
        with isolate_lru_cache(apps.get_swappable_settings_name):
            parent = ModelState(
                "a",
                "Parent",
                [("user", models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE))],
            )
            child = ModelState("a", "Child", [], bases=("a.Parent",))
            user = ModelState("a", "User", [], bases=(AbstractBaseUser, "a.Child"))
            changes = self.get_changes([], [parent, child, user])
        self.assertNumberMigrations(changes, "a", 1)
        self.assertOperationTypes(
            changes, "a", 0, ["CreateModel", "CreateModel", "CreateModel", "AddField"]
        )

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition",
        side_effect=AssertionError("Should not have prompted for not null addition"),
    )
    def test_add_blank_textfield_and_charfield(self, mocked_ask_method):
        """

        Tests that adding a NOT NULL and blank CharField or TextField without default 
        does not prompt for a default value, according to Django issue #23405.

        """
        changes = self.get_changes(
            [self.author_empty], [self.author_with_biography_blank]
        )
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField", "AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0)

    @mock.patch(
        "django.db.migrations.questioner.MigrationQuestioner.ask_not_null_addition"
    )
    def test_add_non_blank_textfield_and_charfield(self, mocked_ask_method):
        """
        Tests that adding a NOT NULL and non-blank CharField or TextField without default triggers a prompt for a default value.
        """
        changes = self.get_changes(
            [self.author_empty], [self.author_with_biography_non_blank]
        )
        self.assertEqual(mocked_ask_method.call_count, 2)
        # Right number/type of migrations?
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["AddField", "AddField"])
        self.assertOperationAttributes(changes, "testapp", 0, 0)

    def test_mti_inheritance_model_removal(self):
        """

        Tests the removal of a model that inherits from another model using multi-table inheritance.

        """
        Animal = ModelState(
            "app",
            "Animal",
            [
                ("id", models.AutoField(primary_key=True)),
            ],
        )
        Dog = ModelState("app", "Dog", [], bases=("app.Animal",))
        changes = self.get_changes([Animal, Dog], [Animal])
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["DeleteModel"])
        self.assertOperationAttributes(changes, "app", 0, 0, name="Dog")

    def test_add_model_with_field_removed_from_base_model(self):
        """
        Tests that removing a field from the base model occurs before adding a new 
        inherited model with a field of the same name, ensuring correct migration behavior.
        """
        before = [
            ModelState(
                "app",
                "readable",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("title", models.CharField(max_length=200)),
                ],
            ),
        ]
        after = [
            ModelState(
                "app",
                "readable",
                [
                    ("id", models.AutoField(primary_key=True)),
                ],
            ),
            ModelState(
                "app",
                "book",
                [
                    ("title", models.CharField(max_length=200)),
                ],
                bases=("app.readable",),
            ),
        ]
        changes = self.get_changes(before, after)
        self.assertNumberMigrations(changes, "app", 1)
        self.assertOperationTypes(changes, "app", 0, ["RemoveField", "CreateModel"])
        self.assertOperationAttributes(
            changes, "app", 0, 0, name="title", model_name="readable"
        )
        self.assertOperationAttributes(changes, "app", 0, 1, name="book")

    def test_parse_number(self):
        tests = [
            ("no_number", None),
            ("0001_initial", 1),
            ("0002_model3", 2),
            ("0002_auto_20380101_1112", 2),
            ("0002_squashed_0003", 3),
            ("0002_model2_squashed_0003_other4", 3),
            ("0002_squashed_0003_squashed_0004", 4),
            ("0002_model2_squashed_0003_other4_squashed_0005_other6", 5),
            ("0002_custom_name_20380101_1112_squashed_0003_model", 3),
            ("2_squashed_4", 4),
        ]
        for migration_name, expected_number in tests:
            with self.subTest(migration_name=migration_name):
                self.assertEqual(
                    MigrationAutodetector.parse_number(migration_name),
                    expected_number,
                )

    def test_add_custom_fk_with_hardcoded_to(self):
        """
        Tests adding a custom foreign key with a hardcoded 'to' field.
        """
        class HardcodedForeignKey(models.ForeignKey):
            def __init__(self, *args, **kwargs):
                kwargs["to"] = "testapp.Author"
                super().__init__(*args, **kwargs)

            def deconstruct(self):
                name, path, args, kwargs = super().deconstruct()
                del kwargs["to"]
                return name, path, args, kwargs

        book_hardcoded_fk_to = ModelState(
            "testapp",
            "Book",
            [
                ("author", HardcodedForeignKey(on_delete=models.CASCADE)),
            ],
        )
        changes = self.get_changes(
            [self.author_empty],
            [self.author_empty, book_hardcoded_fk_to],
        )
        self.assertNumberMigrations(changes, "testapp", 1)
        self.assertOperationTypes(changes, "testapp", 0, ["CreateModel"])
        self.assertOperationAttributes(changes, "testapp", 0, 0, name="Book")


class MigrationSuggestNameTests(SimpleTestCase):
    def test_no_operations(self):
        class Migration(migrations.Migration):
            operations = []

        migration = Migration("some_migration", "test_app")
        self.assertIs(migration.suggest_name().startswith("auto_"), True)

    def test_no_operations_initial(self):
        """
        Tests that an initial migration with no operations suggests the name 'initial'.
        """
        class Migration(migrations.Migration):
            initial = True
            operations = []

        migration = Migration("some_migration", "test_app")
        self.assertEqual(migration.suggest_name(), "initial")

    def test_single_operation(self):
        """
        Tests the naming suggestion for a migration containing a single operation.

        Verifies that the suggested name is derived from the model name when creating
        or deleting a model.
        """
        class Migration(migrations.Migration):
            operations = [migrations.CreateModel("Person", fields=[])]

        migration = Migration("0001_initial", "test_app")
        self.assertEqual(migration.suggest_name(), "person")

        class Migration(migrations.Migration):
            operations = [migrations.DeleteModel("Person")]

        migration = Migration("0002_initial", "test_app")
        self.assertEqual(migration.suggest_name(), "delete_person")

    def test_single_operation_long_name(self):
        class Migration(migrations.Migration):
            operations = [migrations.CreateModel("A" * 53, fields=[])]

        migration = Migration("some_migration", "test_app")
        self.assertEqual(migration.suggest_name(), "a" * 53)

    def test_two_operations(self):
        class Migration(migrations.Migration):
            operations = [
                migrations.CreateModel("Person", fields=[]),
                migrations.DeleteModel("Animal"),
            ]

        migration = Migration("some_migration", "test_app")
        self.assertEqual(migration.suggest_name(), "person_delete_animal")

    def test_two_create_models(self):
        class Migration(migrations.Migration):
            operations = [
                migrations.CreateModel("Person", fields=[]),
                migrations.CreateModel("Animal", fields=[]),
            ]

        migration = Migration("0001_initial", "test_app")
        self.assertEqual(migration.suggest_name(), "person_animal")

    def test_two_create_models_with_initial_true(self):
        """
        Tests that the suggest_name method returns 'initial' for a migration with initial=True and multiple CreateModel operations.
        """
        class Migration(migrations.Migration):
            initial = True
            operations = [
                migrations.CreateModel("Person", fields=[]),
                migrations.CreateModel("Animal", fields=[]),
            ]

        migration = Migration("0001_initial", "test_app")
        self.assertEqual(migration.suggest_name(), "initial")

    def test_many_operations_suffix(self):
        class Migration(migrations.Migration):
            operations = [
                migrations.CreateModel("Person1", fields=[]),
                migrations.CreateModel("Person2", fields=[]),
                migrations.CreateModel("Person3", fields=[]),
                migrations.DeleteModel("Person4"),
                migrations.DeleteModel("Person5"),
            ]

        migration = Migration("some_migration", "test_app")
        self.assertEqual(
            migration.suggest_name(),
            "person1_person2_person3_delete_person4_and_more",
        )

    def test_operation_with_no_suggested_name(self):
        class Migration(migrations.Migration):
            operations = [
                migrations.CreateModel("Person", fields=[]),
                migrations.RunSQL("SELECT 1 FROM person;"),
            ]

        migration = Migration("some_migration", "test_app")
        self.assertIs(migration.suggest_name().startswith("auto_"), True)

    def test_operation_with_invalid_chars_in_suggested_name(self):
        class Migration(migrations.Migration):
            operations = [
                migrations.AddConstraint(
                    "Person",
                    models.UniqueConstraint(
                        fields=["name"], name="person.name-*~unique!"
                    ),
                ),
            ]

        migration = Migration("some_migration", "test_app")
        self.assertEqual(migration.suggest_name(), "person_person_name_unique_")

    def test_none_name(self):
        """
        Tests that a migration name is automatically generated when none is specified, prefixing it with 'auto_'
        """
        class Migration(migrations.Migration):
            operations = [migrations.RunSQL("SELECT 1 FROM person;")]

        migration = Migration("0001_initial", "test_app")
        suggest_name = migration.suggest_name()
        self.assertIs(suggest_name.startswith("auto_"), True)

    def test_none_name_with_initial_true(self):
        """
        Tests that the suggest_name method returns 'initial' when the migration is an initial migration with no name.
        """
        class Migration(migrations.Migration):
            initial = True
            operations = [migrations.RunSQL("SELECT 1 FROM person;")]

        migration = Migration("0001_initial", "test_app")
        self.assertEqual(migration.suggest_name(), "initial")

    def test_auto(self):
        migration = migrations.Migration("0001_initial", "test_app")
        suggest_name = migration.suggest_name()
        self.assertIs(suggest_name.startswith("auto_"), True)
