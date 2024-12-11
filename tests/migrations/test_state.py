from django.apps.registry import Apps
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.db.migrations.exceptions import InvalidBasesError
from django.db.migrations.operations import (
    AddField,
    AlterField,
    DeleteModel,
    RemoveField,
)
from django.db.migrations.state import (
    ModelState,
    ProjectState,
    get_related_models_recursive,
)
from django.test import SimpleTestCase, override_settings
from django.test.utils import isolate_apps

from .models import (
    FoodManager,
    FoodQuerySet,
    ModelWithCustomBase,
    NoMigrationFoodManager,
    UnicodeModel,
)


class StateTests(SimpleTestCase):
    """
    Tests state construction, rendering and modification by operations.
    """

    def test_create(self):
        """
        Tests making a ProjectState from an Apps
        """

        new_apps = Apps(["migrations"])

        class Author(models.Model):
            name = models.CharField(max_length=255)
            bio = models.TextField()
            age = models.IntegerField(blank=True, null=True)

            class Meta:
                app_label = "migrations"
                apps = new_apps
                unique_together = ["name", "bio"]

        class AuthorProxy(Author):
            class Meta:
                app_label = "migrations"
                apps = new_apps
                proxy = True
                ordering = ["name"]

        class SubAuthor(Author):
            width = models.FloatField(null=True)

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Book(models.Model):
            title = models.CharField(max_length=1000)
            author = models.ForeignKey(Author, models.CASCADE)
            contributors = models.ManyToManyField(Author)

            class Meta:
                app_label = "migrations"
                apps = new_apps
                verbose_name = "tome"
                db_table = "test_tome"
                indexes = [models.Index(fields=["title"])]

        class Food(models.Model):
            food_mgr = FoodManager("a", "b")
            food_qs = FoodQuerySet.as_manager()
            food_no_mgr = NoMigrationFoodManager("x", "y")

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class FoodNoManagers(models.Model):
            class Meta:
                app_label = "migrations"
                apps = new_apps

        class FoodNoDefaultManager(models.Model):
            food_no_mgr = NoMigrationFoodManager("x", "y")
            food_mgr = FoodManager("a", "b")
            food_qs = FoodQuerySet.as_manager()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        mgr1 = FoodManager("a", "b")
        mgr2 = FoodManager("x", "y", c=3, d=4)

        class FoodOrderedManagers(models.Model):
            # The managers on this model should be ordered by their creation
            # counter and not by the order in model body

            food_no_mgr = NoMigrationFoodManager("x", "y")
            food_mgr2 = mgr2
            food_mgr1 = mgr1

            class Meta:
                app_label = "migrations"
                apps = new_apps

        project_state = ProjectState.from_apps(new_apps)
        author_state = project_state.models["migrations", "author"]
        author_proxy_state = project_state.models["migrations", "authorproxy"]
        sub_author_state = project_state.models["migrations", "subauthor"]
        book_state = project_state.models["migrations", "book"]
        food_state = project_state.models["migrations", "food"]
        food_no_managers_state = project_state.models["migrations", "foodnomanagers"]
        food_no_default_manager_state = project_state.models[
            "migrations", "foodnodefaultmanager"
        ]
        food_order_manager_state = project_state.models[
            "migrations", "foodorderedmanagers"
        ]
        book_index = models.Index(fields=["title"])
        book_index.set_name_with_model(Book)

        self.assertEqual(author_state.app_label, "migrations")
        self.assertEqual(author_state.name, "Author")
        self.assertEqual(list(author_state.fields), ["id", "name", "bio", "age"])
        self.assertEqual(author_state.fields["name"].max_length, 255)
        self.assertIs(author_state.fields["bio"].null, False)
        self.assertIs(author_state.fields["age"].null, True)
        self.assertEqual(
            author_state.options,
            {
                "unique_together": {("name", "bio")},
                "indexes": [],
                "constraints": [],
            },
        )
        self.assertEqual(author_state.bases, (models.Model,))

        self.assertEqual(book_state.app_label, "migrations")
        self.assertEqual(book_state.name, "Book")
        self.assertEqual(
            list(book_state.fields), ["id", "title", "author", "contributors"]
        )
        self.assertEqual(book_state.fields["title"].max_length, 1000)
        self.assertIs(book_state.fields["author"].null, False)
        self.assertEqual(
            book_state.fields["contributors"].__class__.__name__, "ManyToManyField"
        )
        self.assertEqual(
            book_state.options,
            {
                "verbose_name": "tome",
                "db_table": "test_tome",
                "indexes": [book_index],
                "constraints": [],
            },
        )
        self.assertEqual(book_state.bases, (models.Model,))

        self.assertEqual(author_proxy_state.app_label, "migrations")
        self.assertEqual(author_proxy_state.name, "AuthorProxy")
        self.assertEqual(author_proxy_state.fields, {})
        self.assertEqual(
            author_proxy_state.options,
            {"proxy": True, "ordering": ["name"], "indexes": [], "constraints": []},
        )
        self.assertEqual(author_proxy_state.bases, ("migrations.author",))

        self.assertEqual(sub_author_state.app_label, "migrations")
        self.assertEqual(sub_author_state.name, "SubAuthor")
        self.assertEqual(len(sub_author_state.fields), 2)
        self.assertEqual(sub_author_state.bases, ("migrations.author",))

        # The default manager is used in migrations
        self.assertEqual([name for name, mgr in food_state.managers], ["food_mgr"])
        self.assertTrue(all(isinstance(name, str) for name, mgr in food_state.managers))
        self.assertEqual(food_state.managers[0][1].args, ("a", "b", 1, 2))

        # No explicit managers defined. Migrations will fall back to the default
        self.assertEqual(food_no_managers_state.managers, [])

        # food_mgr is used in migration but isn't the default mgr, hence add the
        # default
        self.assertEqual(
            [name for name, mgr in food_no_default_manager_state.managers],
            ["food_no_mgr", "food_mgr"],
        )
        self.assertTrue(
            all(
                isinstance(name, str)
                for name, mgr in food_no_default_manager_state.managers
            )
        )
        self.assertEqual(
            food_no_default_manager_state.managers[0][1].__class__, models.Manager
        )
        self.assertIsInstance(food_no_default_manager_state.managers[1][1], FoodManager)

        self.assertEqual(
            [name for name, mgr in food_order_manager_state.managers],
            ["food_mgr1", "food_mgr2"],
        )
        self.assertTrue(
            all(
                isinstance(name, str) for name, mgr in food_order_manager_state.managers
            )
        )
        self.assertEqual(
            [mgr.args for name, mgr in food_order_manager_state.managers],
            [("a", "b", 1, 2), ("x", "y", 3, 4)],
        )

    def test_custom_default_manager_added_to_the_model_state(self):
        """
        When the default manager of the model is a custom manager,
        it needs to be added to the model state.
        """
        new_apps = Apps(["migrations"])
        custom_manager = models.Manager()

        class Author(models.Model):
            objects = models.TextField()
            authors = custom_manager

            class Meta:
                app_label = "migrations"
                apps = new_apps

        project_state = ProjectState.from_apps(new_apps)
        author_state = project_state.models["migrations", "author"]
        self.assertEqual(author_state.managers, [("authors", custom_manager)])

    def test_custom_default_manager_named_objects_with_false_migration_flag(self):
        """
        When a manager is added with a name of 'objects' but it does not
        have `use_in_migrations = True`, no migration should be added to the
        model state (#26643).
        """
        new_apps = Apps(["migrations"])

        class Author(models.Model):
            objects = models.Manager()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        project_state = ProjectState.from_apps(new_apps)
        author_state = project_state.models["migrations", "author"]
        self.assertEqual(author_state.managers, [])

    def test_no_duplicate_managers(self):
        """
        When a manager is added with `use_in_migrations = True` and a parent
        model had a manager with the same name and `use_in_migrations = True`,
        the parent's manager shouldn't appear in the model state (#26881).
        """
        new_apps = Apps(["migrations"])

        class PersonManager(models.Manager):
            use_in_migrations = True

        class Person(models.Model):
            objects = PersonManager()

            class Meta:
                abstract = True

        class BossManager(PersonManager):
            use_in_migrations = True

        class Boss(Person):
            objects = BossManager()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        project_state = ProjectState.from_apps(new_apps)
        boss_state = project_state.models["migrations", "boss"]
        self.assertEqual(boss_state.managers, [("objects", Boss.objects)])

    def test_custom_default_manager(self):
        new_apps = Apps(["migrations"])

        class Author(models.Model):
            manager1 = models.Manager()
            manager2 = models.Manager()

            class Meta:
                app_label = "migrations"
                apps = new_apps
                default_manager_name = "manager2"

        project_state = ProjectState.from_apps(new_apps)
        author_state = project_state.models["migrations", "author"]
        self.assertEqual(author_state.options["default_manager_name"], "manager2")
        self.assertEqual(author_state.managers, [("manager2", Author.manager1)])

    def test_custom_base_manager(self):
        """
        '''
        Tests the functionality of setting a custom base manager for a model.

        This test case covers the scenario where a model has multiple managers defined,
        and a specific manager is designated as the base manager. The test verifies that
        the base manager name is correctly set in the model's metadata and that all
        managers are properly registered.

        The test includes two example models, Author and Author2, each with two managers:
        manager1 and manager2. The base manager name is set to 'manager2' for Author and
        'manager1' for Author2. The test then checks the model state to ensure that the
        base manager name and all managers are correctly configured.
        '''
        """
        new_apps = Apps(["migrations"])

        class Author(models.Model):
            manager1 = models.Manager()
            manager2 = models.Manager()

            class Meta:
                app_label = "migrations"
                apps = new_apps
                base_manager_name = "manager2"

        class Author2(models.Model):
            manager1 = models.Manager()
            manager2 = models.Manager()

            class Meta:
                app_label = "migrations"
                apps = new_apps
                base_manager_name = "manager1"

        project_state = ProjectState.from_apps(new_apps)

        author_state = project_state.models["migrations", "author"]
        self.assertEqual(author_state.options["base_manager_name"], "manager2")
        self.assertEqual(
            author_state.managers,
            [
                ("manager1", Author.manager1),
                ("manager2", Author.manager2),
            ],
        )

        author2_state = project_state.models["migrations", "author2"]
        self.assertEqual(author2_state.options["base_manager_name"], "manager1")
        self.assertEqual(
            author2_state.managers,
            [
                ("manager1", Author2.manager1),
            ],
        )

    def test_apps_bulk_update(self):
        """
        StateApps.bulk_update() should update apps.ready to False and reset
        the value afterward.
        """
        project_state = ProjectState()
        apps = project_state.apps
        with apps.bulk_update():
            self.assertFalse(apps.ready)
        self.assertTrue(apps.ready)
        with self.assertRaises(ValueError):
            with apps.bulk_update():
                self.assertFalse(apps.ready)
                raise ValueError()
        self.assertTrue(apps.ready)

    def test_render(self):
        """
        Tests rendering a ProjectState into an Apps.
        """
        project_state = ProjectState()
        project_state.add_model(
            ModelState(
                app_label="migrations",
                name="Tag",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("name", models.CharField(max_length=100)),
                    ("hidden", models.BooleanField()),
                ],
            )
        )
        project_state.add_model(
            ModelState(
                app_label="migrations",
                name="SubTag",
                fields=[
                    (
                        "tag_ptr",
                        models.OneToOneField(
                            "migrations.Tag",
                            models.CASCADE,
                            auto_created=True,
                            parent_link=True,
                            primary_key=True,
                            to_field="id",
                            serialize=False,
                        ),
                    ),
                    ("awesome", models.BooleanField()),
                ],
                bases=("migrations.Tag",),
            )
        )

        base_mgr = models.Manager()
        mgr1 = FoodManager("a", "b")
        mgr2 = FoodManager("x", "y", c=3, d=4)
        project_state.add_model(
            ModelState(
                app_label="migrations",
                name="Food",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                ],
                managers=[
                    # The ordering we really want is objects, mgr1, mgr2
                    ("default", base_mgr),
                    ("food_mgr2", mgr2),
                    ("food_mgr1", mgr1),
                ],
            )
        )

        new_apps = project_state.apps
        self.assertEqual(
            new_apps.get_model("migrations", "Tag")._meta.get_field("name").max_length,
            100,
        )
        self.assertIs(
            new_apps.get_model("migrations", "Tag")._meta.get_field("hidden").null,
            False,
        )

        self.assertEqual(
            len(new_apps.get_model("migrations", "SubTag")._meta.local_fields), 2
        )

        Food = new_apps.get_model("migrations", "Food")
        self.assertEqual(
            [mgr.name for mgr in Food._meta.managers],
            ["default", "food_mgr1", "food_mgr2"],
        )
        self.assertTrue(all(isinstance(mgr.name, str) for mgr in Food._meta.managers))
        self.assertEqual(
            [mgr.__class__ for mgr in Food._meta.managers],
            [models.Manager, FoodManager, FoodManager],
        )

    def test_render_model_inheritance(self):
        class Book(models.Model):
            title = models.CharField(max_length=1000)

            class Meta:
                app_label = "migrations"
                apps = Apps()

        class Novel(Book):
            class Meta:
                app_label = "migrations"
                apps = Apps()

        # First, test rendering individually
        apps = Apps(["migrations"])

        # We shouldn't be able to render yet
        ms = ModelState.from_model(Novel)
        with self.assertRaises(InvalidBasesError):
            ms.render(apps)

        # Once the parent model is in the app registry, it should be fine
        ModelState.from_model(Book).render(apps)
        ModelState.from_model(Novel).render(apps)

    def test_render_model_with_multiple_inheritance(self):
        """
        \\":Test to ensure that rendering models with multiple inheritance results in the expected base models.

            This test verifies the correct rendering of models that inherit from multiple base models, including 
            abstract models and models with multiple levels of inheritance. It checks that the `ModelState` 
            correctly identifies the base models for each model, handling cases where multiple inheritance 
            and abstract models are involved. The test also checks that an `InvalidBasesError` is raised when 
            attempting to render a model with an invalid base model configuration.\\"
        """
        class Foo(models.Model):
            class Meta:
                app_label = "migrations"
                apps = Apps()

        class Bar(models.Model):
            class Meta:
                app_label = "migrations"
                apps = Apps()

        class FooBar(Foo, Bar):
            class Meta:
                app_label = "migrations"
                apps = Apps()

        class AbstractSubFooBar(FooBar):
            class Meta:
                abstract = True
                apps = Apps()

        class SubFooBar(AbstractSubFooBar):
            class Meta:
                app_label = "migrations"
                apps = Apps()

        apps = Apps(["migrations"])

        # We shouldn't be able to render yet
        ms = ModelState.from_model(FooBar)
        with self.assertRaises(InvalidBasesError):
            ms.render(apps)

        # Once the parent models are in the app registry, it should be fine
        ModelState.from_model(Foo).render(apps)
        self.assertSequenceEqual(ModelState.from_model(Foo).bases, [models.Model])
        ModelState.from_model(Bar).render(apps)
        self.assertSequenceEqual(ModelState.from_model(Bar).bases, [models.Model])
        ModelState.from_model(FooBar).render(apps)
        self.assertSequenceEqual(
            ModelState.from_model(FooBar).bases, ["migrations.foo", "migrations.bar"]
        )
        ModelState.from_model(SubFooBar).render(apps)
        self.assertSequenceEqual(
            ModelState.from_model(SubFooBar).bases, ["migrations.foobar"]
        )

    def test_render_project_dependencies(self):
        """
        The ProjectState render method correctly renders models
        to account for inter-model base dependencies.
        """
        new_apps = Apps()

        class A(models.Model):
            class Meta:
                app_label = "migrations"
                apps = new_apps

        class B(A):
            class Meta:
                app_label = "migrations"
                apps = new_apps

        class C(B):
            class Meta:
                app_label = "migrations"
                apps = new_apps

        class D(A):
            class Meta:
                app_label = "migrations"
                apps = new_apps

        class E(B):
            class Meta:
                app_label = "migrations"
                apps = new_apps
                proxy = True

        class F(D):
            class Meta:
                app_label = "migrations"
                apps = new_apps
                proxy = True

        # Make a ProjectState and render it
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        project_state.add_model(ModelState.from_model(C))
        project_state.add_model(ModelState.from_model(D))
        project_state.add_model(ModelState.from_model(E))
        project_state.add_model(ModelState.from_model(F))
        final_apps = project_state.apps
        self.assertEqual(len(final_apps.get_models()), 6)

        # Now make an invalid ProjectState and make sure it fails
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        project_state.add_model(ModelState.from_model(C))
        project_state.add_model(ModelState.from_model(F))
        with self.assertRaises(InvalidBasesError):
            project_state.apps

    def test_render_unique_app_labels(self):
        """
        The ProjectState render method doesn't raise an
        ImproperlyConfigured exception about unique labels if two dotted app
        names have the same last part.
        """

        class A(models.Model):
            class Meta:
                app_label = "django.contrib.auth"

        class B(models.Model):
            class Meta:
                app_label = "vendor.auth"

        # Make a ProjectState and render it
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        self.assertEqual(len(project_state.apps.get_models()), 2)

    def test_reload_related_model_on_non_relational_fields(self):
        """
        The model is reloaded even on changes that are not involved in
        relations. Other models pointing to or from it are also reloaded.
        """
        project_state = ProjectState()
        project_state.apps  # Render project state.
        project_state.add_model(ModelState("migrations", "A", []))
        project_state.add_model(
            ModelState(
                "migrations",
                "B",
                [
                    ("a", models.ForeignKey("A", models.CASCADE)),
                ],
            )
        )
        project_state.add_model(
            ModelState(
                "migrations",
                "C",
                [
                    ("b", models.ForeignKey("B", models.CASCADE)),
                    ("name", models.TextField()),
                ],
            )
        )
        project_state.add_model(
            ModelState(
                "migrations",
                "D",
                [
                    ("a", models.ForeignKey("A", models.CASCADE)),
                ],
            )
        )
        operation = AlterField(
            model_name="C",
            name="name",
            field=models.TextField(blank=True),
        )
        operation.state_forwards("migrations", project_state)
        project_state.reload_model("migrations", "a", delay=True)
        A = project_state.apps.get_model("migrations.A")
        B = project_state.apps.get_model("migrations.B")
        D = project_state.apps.get_model("migrations.D")
        self.assertIs(B._meta.get_field("a").related_model, A)
        self.assertIs(D._meta.get_field("a").related_model, A)

    def test_reload_model_relationship_consistency(self):
        """
        Tests the consistency of model relationships after reloading a model.

        This test case creates a project state with three models, A, B, and C, where B has a foreign key to A, and C has a foreign key to B.
        It verifies that the related objects for each model are correctly set before and after reloading model A.
        The test ensures that the related objects for each model remain consistent, even after the model is reloaded, to prevent any potential inconsistencies or errors in the relationships between models.
        """
        project_state = ProjectState()
        project_state.add_model(ModelState("migrations", "A", []))
        project_state.add_model(
            ModelState(
                "migrations",
                "B",
                [
                    ("a", models.ForeignKey("A", models.CASCADE)),
                ],
            )
        )
        project_state.add_model(
            ModelState(
                "migrations",
                "C",
                [
                    ("b", models.ForeignKey("B", models.CASCADE)),
                ],
            )
        )
        A = project_state.apps.get_model("migrations.A")
        B = project_state.apps.get_model("migrations.B")
        C = project_state.apps.get_model("migrations.C")
        self.assertEqual([r.related_model for r in A._meta.related_objects], [B])
        self.assertEqual([r.related_model for r in B._meta.related_objects], [C])
        self.assertEqual([r.related_model for r in C._meta.related_objects], [])

        project_state.reload_model("migrations", "a", delay=True)
        A = project_state.apps.get_model("migrations.A")
        B = project_state.apps.get_model("migrations.B")
        C = project_state.apps.get_model("migrations.C")
        self.assertEqual([r.related_model for r in A._meta.related_objects], [B])
        self.assertEqual([r.related_model for r in B._meta.related_objects], [C])
        self.assertEqual([r.related_model for r in C._meta.related_objects], [])

    def test_add_relations(self):
        """
        #24573 - Adding relations to existing models should reload the
        referenced models too.
        """
        new_apps = Apps()

        class A(models.Model):
            class Meta:
                app_label = "something"
                apps = new_apps

        class B(A):
            class Meta:
                app_label = "something"
                apps = new_apps

        class C(models.Model):
            class Meta:
                app_label = "something"
                apps = new_apps

        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        project_state.add_model(ModelState.from_model(C))

        project_state.apps  # We need to work with rendered models

        old_state = project_state.clone()
        model_a_old = old_state.apps.get_model("something", "A")
        model_b_old = old_state.apps.get_model("something", "B")
        model_c_old = old_state.apps.get_model("something", "C")
        # The relations between the old models are correct
        self.assertIs(model_a_old._meta.get_field("b").related_model, model_b_old)
        self.assertIs(model_b_old._meta.get_field("a_ptr").related_model, model_a_old)

        operation = AddField(
            "c",
            "to_a",
            models.OneToOneField(
                "something.A",
                models.CASCADE,
                related_name="from_c",
            ),
        )
        operation.state_forwards("something", project_state)
        model_a_new = project_state.apps.get_model("something", "A")
        model_b_new = project_state.apps.get_model("something", "B")
        model_c_new = project_state.apps.get_model("something", "C")

        # All models have changed
        self.assertIsNot(model_a_old, model_a_new)
        self.assertIsNot(model_b_old, model_b_new)
        self.assertIsNot(model_c_old, model_c_new)
        # The relations between the old models still hold
        self.assertIs(model_a_old._meta.get_field("b").related_model, model_b_old)
        self.assertIs(model_b_old._meta.get_field("a_ptr").related_model, model_a_old)
        # The relations between the new models correct
        self.assertIs(model_a_new._meta.get_field("b").related_model, model_b_new)
        self.assertIs(model_b_new._meta.get_field("a_ptr").related_model, model_a_new)
        self.assertIs(model_a_new._meta.get_field("from_c").related_model, model_c_new)
        self.assertIs(model_c_new._meta.get_field("to_a").related_model, model_a_new)

    def test_remove_relations(self):
        """
        #24225 - Relations between models are updated while
        remaining the relations and references for models of an old state.
        """
        new_apps = Apps()

        class A(models.Model):
            class Meta:
                app_label = "something"
                apps = new_apps

        class B(models.Model):
            to_a = models.ForeignKey(A, models.CASCADE)

            class Meta:
                app_label = "something"
                apps = new_apps

        def get_model_a(state):
            return [
                mod for mod in state.apps.get_models() if mod._meta.model_name == "a"
            ][0]

        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        self.assertEqual(len(get_model_a(project_state)._meta.related_objects), 1)
        old_state = project_state.clone()

        operation = RemoveField("b", "to_a")
        operation.state_forwards("something", project_state)
        # Model from old_state still has the relation
        model_a_old = get_model_a(old_state)
        model_a_new = get_model_a(project_state)
        self.assertIsNot(model_a_old, model_a_new)
        self.assertEqual(len(model_a_old._meta.related_objects), 1)
        self.assertEqual(len(model_a_new._meta.related_objects), 0)

        # Same test for deleted model
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        project_state.add_model(ModelState.from_model(B))
        old_state = project_state.clone()

        operation = DeleteModel("b")
        operation.state_forwards("something", project_state)
        model_a_old = get_model_a(old_state)
        model_a_new = get_model_a(project_state)
        self.assertIsNot(model_a_old, model_a_new)
        self.assertEqual(len(model_a_old._meta.related_objects), 1)
        self.assertEqual(len(model_a_new._meta.related_objects), 0)

    def test_self_relation(self):
        """
        #24513 - Modifying an object pointing to itself would cause it to be
        rendered twice and thus breaking its related M2M through objects.
        """

        class A(models.Model):
            to_a = models.ManyToManyField("something.A", symmetrical=False)

            class Meta:
                app_label = "something"

        def get_model_a(state):
            return [
                mod for mod in state.apps.get_models() if mod._meta.model_name == "a"
            ][0]

        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(A))
        self.assertEqual(len(get_model_a(project_state)._meta.related_objects), 1)
        old_state = project_state.clone()

        operation = AlterField(
            model_name="a",
            name="to_a",
            field=models.ManyToManyField("something.A", symmetrical=False, blank=True),
        )
        # At this point the model would be rendered twice causing its related
        # M2M through objects to point to an old copy and thus breaking their
        # attribute lookup.
        operation.state_forwards("something", project_state)

        model_a_old = get_model_a(old_state)
        model_a_new = get_model_a(project_state)
        self.assertIsNot(model_a_old, model_a_new)

        # The old model's _meta is still consistent
        field_to_a_old = model_a_old._meta.get_field("to_a")
        self.assertEqual(field_to_a_old.m2m_field_name(), "from_a")
        self.assertEqual(field_to_a_old.m2m_reverse_field_name(), "to_a")
        self.assertIs(field_to_a_old.related_model, model_a_old)
        self.assertIs(
            field_to_a_old.remote_field.through._meta.get_field("to_a").related_model,
            model_a_old,
        )
        self.assertIs(
            field_to_a_old.remote_field.through._meta.get_field("from_a").related_model,
            model_a_old,
        )

        # The new model's _meta is still consistent
        field_to_a_new = model_a_new._meta.get_field("to_a")
        self.assertEqual(field_to_a_new.m2m_field_name(), "from_a")
        self.assertEqual(field_to_a_new.m2m_reverse_field_name(), "to_a")
        self.assertIs(field_to_a_new.related_model, model_a_new)
        self.assertIs(
            field_to_a_new.remote_field.through._meta.get_field("to_a").related_model,
            model_a_new,
        )
        self.assertIs(
            field_to_a_new.remote_field.through._meta.get_field("from_a").related_model,
            model_a_new,
        )

    def test_equality(self):
        """
        == and != are implemented correctly.
        """
        # Test two things that should be equal
        project_state = ProjectState()
        project_state.add_model(
            ModelState(
                "migrations",
                "Tag",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("name", models.CharField(max_length=100)),
                    ("hidden", models.BooleanField()),
                ],
                {},
                None,
            )
        )
        project_state.apps  # Fill the apps cached property
        other_state = project_state.clone()
        self.assertEqual(project_state, project_state)
        self.assertEqual(project_state, other_state)
        self.assertIs(project_state != project_state, False)
        self.assertIs(project_state != other_state, False)
        self.assertNotEqual(project_state.apps, other_state.apps)

        # Make a very small change (max_len 99) and see if that affects it
        project_state = ProjectState()
        project_state.add_model(
            ModelState(
                "migrations",
                "Tag",
                [
                    ("id", models.AutoField(primary_key=True)),
                    ("name", models.CharField(max_length=99)),
                    ("hidden", models.BooleanField()),
                ],
                {},
                None,
            )
        )
        self.assertNotEqual(project_state, other_state)
        self.assertIs(project_state == other_state, False)

    def test_dangling_references_throw_error(self):
        new_apps = Apps()

        class Author(models.Model):
            name = models.TextField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Publisher(models.Model):
            name = models.TextField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Book(models.Model):
            author = models.ForeignKey(Author, models.CASCADE)
            publisher = models.ForeignKey(Publisher, models.CASCADE)

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Magazine(models.Model):
            authors = models.ManyToManyField(Author)

            class Meta:
                app_label = "migrations"
                apps = new_apps

        # Make a valid ProjectState and render it
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(Author))
        project_state.add_model(ModelState.from_model(Publisher))
        project_state.add_model(ModelState.from_model(Book))
        project_state.add_model(ModelState.from_model(Magazine))
        self.assertEqual(len(project_state.apps.get_models()), 4)

        # now make an invalid one with a ForeignKey
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(Book))
        msg = (
            "The field migrations.Book.author was declared with a lazy reference "
            "to 'migrations.author', but app 'migrations' doesn't provide model "
            "'author'.\n"
            "The field migrations.Book.publisher was declared with a lazy reference "
            "to 'migrations.publisher', but app 'migrations' doesn't provide model "
            "'publisher'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            project_state.apps

        # And another with ManyToManyField.
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(Magazine))
        msg = (
            "The field migrations.Magazine.authors was declared with a lazy reference "
            "to 'migrations.author', but app 'migrations' doesn't provide model "
            "'author'.\n"
            "The field migrations.Magazine_authors.author was declared with a lazy "
            "reference to 'migrations.author', but app 'migrations' doesn't provide "
            "model 'author'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            project_state.apps

        # And now with multiple models and multiple fields.
        project_state.add_model(ModelState.from_model(Book))
        msg = (
            "The field migrations.Book.author was declared with a lazy reference "
            "to 'migrations.author', but app 'migrations' doesn't provide model "
            "'author'.\n"
            "The field migrations.Book.publisher was declared with a lazy reference "
            "to 'migrations.publisher', but app 'migrations' doesn't provide model "
            "'publisher'.\n"
            "The field migrations.Magazine.authors was declared with a lazy reference "
            "to 'migrations.author', but app 'migrations' doesn't provide model "
            "'author'.\n"
            "The field migrations.Magazine_authors.author was declared with a lazy "
            "reference to 'migrations.author', but app 'migrations' doesn't provide "
            "model 'author'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            project_state.apps

    def test_reference_mixed_case_app_label(self):
        new_apps = Apps()

        class Author(models.Model):
            class Meta:
                app_label = "MiXedCase_migrations"
                apps = new_apps

        class Book(models.Model):
            author = models.ForeignKey(Author, models.CASCADE)

            class Meta:
                app_label = "MiXedCase_migrations"
                apps = new_apps

        class Magazine(models.Model):
            authors = models.ManyToManyField(Author)

            class Meta:
                app_label = "MiXedCase_migrations"
                apps = new_apps

        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(Author))
        project_state.add_model(ModelState.from_model(Book))
        project_state.add_model(ModelState.from_model(Magazine))
        self.assertEqual(len(project_state.apps.get_models()), 3)

    def test_real_apps(self):
        """
        Including real apps can resolve dangling FK errors.
        This test relies on the fact that contenttypes is always loaded.
        """
        new_apps = Apps()

        class TestModel(models.Model):
            ct = models.ForeignKey("contenttypes.ContentType", models.CASCADE)

            class Meta:
                app_label = "migrations"
                apps = new_apps

        # If we just stick it into an empty state it should fail
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(TestModel))
        with self.assertRaises(ValueError):
            project_state.apps

        # If we include the real app it should succeed
        project_state = ProjectState(real_apps={"contenttypes"})
        project_state.add_model(ModelState.from_model(TestModel))
        rendered_state = project_state.apps
        self.assertEqual(
            len(
                [
                    x
                    for x in rendered_state.get_models()
                    if x._meta.app_label == "migrations"
                ]
            ),
            1,
        )

    def test_real_apps_non_set(self):
        """

        Tests that an AssertionError is raised when trying to create a ProjectState instance with real applications that are not sets.

        This test ensures that the ProjectState class correctly validates its input, specifically that the real_apps parameter must be a set of application names.

        :raises: AssertionError if the real_apps parameter is not a set.
        """
        with self.assertRaises(AssertionError):
            ProjectState(real_apps=["contenttypes"])

    def test_ignore_order_wrt(self):
        """
        Makes sure ProjectState doesn't include OrderWrt fields when
        making from existing models.
        """
        new_apps = Apps()

        class Author(models.Model):
            name = models.TextField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Book(models.Model):
            author = models.ForeignKey(Author, models.CASCADE)

            class Meta:
                app_label = "migrations"
                apps = new_apps
                order_with_respect_to = "author"

        # Make a valid ProjectState and render it
        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(Author))
        project_state.add_model(ModelState.from_model(Book))
        self.assertEqual(
            list(project_state.models["migrations", "book"].fields),
            ["id", "author"],
        )

    def test_modelstate_get_field_order_wrt(self):
        new_apps = Apps()

        class Author(models.Model):
            name = models.TextField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Book(models.Model):
            author = models.ForeignKey(Author, models.CASCADE)

            class Meta:
                app_label = "migrations"
                apps = new_apps
                order_with_respect_to = "author"

        model_state = ModelState.from_model(Book)
        order_wrt_field = model_state.get_field("_order")
        self.assertIsInstance(order_wrt_field, models.ForeignKey)
        self.assertEqual(order_wrt_field.related_model, "migrations.author")

    def test_modelstate_get_field_no_order_wrt_order_field(self):
        """

        Tests the ModelState's get_field method when retrieving a field that does not participate in an order_with_respect_to relationship.

        Verifies that the retrieved field is an instance of PositiveSmallIntegerField and does not have a related model.

        """
        new_apps = Apps()

        class HistoricalRecord(models.Model):
            _order = models.PositiveSmallIntegerField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        model_state = ModelState.from_model(HistoricalRecord)
        order_field = model_state.get_field("_order")
        self.assertIsNone(order_field.related_model)
        self.assertIsInstance(order_field, models.PositiveSmallIntegerField)

    def test_get_order_field_after_removed_order_with_respect_to_field(self):
        """
        Tests the behavior of the get_order_field method after an order_with_respect_to field has been removed.

        This test case verifies that the _order field is still correctly retrieved and that it no longer has a related model, as expected after the removal of the order_with_respect_to field.

        It ensures the timely update and correct functionality of the get_order_field method in the presence of changes to the model's ordering configuration, providing a robust test of the method's behavior under specific conditions.
        """
        new_apps = Apps()

        class HistoricalRecord(models.Model):
            _order = models.PositiveSmallIntegerField()

            class Meta:
                app_label = "migrations"
                apps = new_apps

        model_state = ModelState.from_model(HistoricalRecord)
        model_state.options["order_with_respect_to"] = None
        order_field = model_state.get_field("_order")
        self.assertIsNone(order_field.related_model)
        self.assertIsInstance(order_field, models.PositiveSmallIntegerField)

    def test_manager_refer_correct_model_version(self):
        """
        #24147 - Managers refer to the correct version of a
        historical model
        """
        project_state = ProjectState()
        project_state.add_model(
            ModelState(
                app_label="migrations",
                name="Tag",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("hidden", models.BooleanField()),
                ],
                managers=[
                    ("food_mgr", FoodManager("a", "b")),
                    ("food_qs", FoodQuerySet.as_manager()),
                ],
            )
        )

        old_model = project_state.apps.get_model("migrations", "tag")

        new_state = project_state.clone()
        operation = RemoveField("tag", "hidden")
        operation.state_forwards("migrations", new_state)

        new_model = new_state.apps.get_model("migrations", "tag")

        self.assertIsNot(old_model, new_model)
        self.assertIs(old_model, old_model.food_mgr.model)
        self.assertIs(old_model, old_model.food_qs.model)
        self.assertIs(new_model, new_model.food_mgr.model)
        self.assertIs(new_model, new_model.food_qs.model)
        self.assertIsNot(old_model.food_mgr, new_model.food_mgr)
        self.assertIsNot(old_model.food_qs, new_model.food_qs)
        self.assertIsNot(old_model.food_mgr.model, new_model.food_mgr.model)
        self.assertIsNot(old_model.food_qs.model, new_model.food_qs.model)

    def test_choices_iterator(self):
        """
        #24483 - ProjectState.from_apps should not destructively consume
        Field.choices iterators.
        """
        new_apps = Apps(["migrations"])
        choices = [("a", "A"), ("b", "B")]

        class Author(models.Model):
            name = models.CharField(max_length=255)
            choice = models.CharField(max_length=255, choices=iter(choices))

            class Meta:
                app_label = "migrations"
                apps = new_apps

        ProjectState.from_apps(new_apps)
        choices_field = Author._meta.get_field("choice")
        self.assertEqual(list(choices_field.choices), choices)


class StateRelationsTests(SimpleTestCase):
    def get_base_project_state(self):
        """
        Returns a :class:`ProjectState` object representing the base state of a project, including three models: User, Comment, and Post.
        The User model represents a user, the Comment model represents a comment with a foreign key to the User model and a many-to-many relationship to itself, and the Post model represents a post with a many-to-many relationship to the User model.
        This state can be used as a foundation for testing or comparison purposes.
        """
        new_apps = Apps()

        class User(models.Model):
            class Meta:
                app_label = "tests"
                apps = new_apps

        class Comment(models.Model):
            text = models.TextField()
            user = models.ForeignKey(User, models.CASCADE)
            comments = models.ManyToManyField("self")

            class Meta:
                app_label = "tests"
                apps = new_apps

        class Post(models.Model):
            text = models.TextField()
            authors = models.ManyToManyField(User)

            class Meta:
                app_label = "tests"
                apps = new_apps

        project_state = ProjectState()
        project_state.add_model(ModelState.from_model(User))
        project_state.add_model(ModelState.from_model(Comment))
        project_state.add_model(ModelState.from_model(Post))
        return project_state

    def test_relations_population(self):
        """

        Tests the population of relations in a project state for various model operations.

        Checks the relations are correctly updated after performing different operations
        such as adding/removing models, adding/removing fields, renaming models and fields,
        and altering fields. The operations tested include:
        - Adding a model
        - Removing a model
        - Renaming a model
        - Adding a field
        - Removing a field
        - Renaming a field
        - Altering a field

        For each operation, it verifies that the relations are initially empty and
        subsequently populated as expected.

        """
        tests = [
            (
                "add_model",
                [
                    ModelState(
                        app_label="migrations",
                        name="Tag",
                        fields=[("id", models.AutoField(primary_key=True))],
                    ),
                ],
            ),
            ("remove_model", ["tests", "comment"]),
            ("rename_model", ["tests", "comment", "opinion"]),
            (
                "add_field",
                [
                    "tests",
                    "post",
                    "next_post",
                    models.ForeignKey("self", models.CASCADE),
                    True,
                ],
            ),
            ("remove_field", ["tests", "post", "text"]),
            ("rename_field", ["tests", "comment", "user", "author"]),
            (
                "alter_field",
                [
                    "tests",
                    "comment",
                    "user",
                    models.IntegerField(),
                    True,
                ],
            ),
        ]
        for method, args in tests:
            with self.subTest(method=method):
                project_state = self.get_base_project_state()
                getattr(project_state, method)(*args)
                # ProjectState's `_relations` are populated on `relations` access.
                self.assertIsNone(project_state._relations)
                self.assertEqual(project_state.relations, project_state._relations)
                self.assertIsNotNone(project_state._relations)

    def test_add_model(self):
        """

        Tests that the model relations are correctly defined in the project state.

        This test case verifies the existence and accuracy of relationships between different models, 
        such as 'tests', 'user', 'comment', and 'post', in the project's state. It checks for 
        specific relationships and ensures that certain relationships do not exist.

        """
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "comment"]),
            [("tests", "comment")],
        )
        self.assertNotIn(("tests", "post"), project_state.relations)

    def test_add_model_no_relations(self):
        """
        Tests adding a model with no relations to the project state.

        Verifies that a model can be successfully added to the project state when it does not have any relationships defined.
        The test checks that the project state's relations dictionary remains empty after adding the model.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the project state's relations dictionary is not empty after adding the model.

        """
        project_state = ProjectState()
        project_state.add_model(
            ModelState(
                app_label="migrations",
                name="Tag",
                fields=[("id", models.AutoField(primary_key=True))],
            )
        )
        self.assertEqual(project_state.relations, {})

    def test_add_model_other_app(self):
        """
        Tests adding a model from another application affects the project state's relations.

        This test case verifies that when a new model with a foreign key to an existing model
        is added, the project state's relations are updated accordingly. It ensures that the
        relations between models are correctly tracked, even when the models belong to
        different applications.

        The test covers the scenario where a model from another application ('tests_other')
        has a foreign key to a model in the current application ('tests'), and checks that
        the project state's relations reflect this new relationship.
        """
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        project_state.add_model(
            ModelState(
                app_label="tests_other",
                name="comment",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("user", models.ForeignKey("tests.user", models.CASCADE)),
                ],
            )
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post"), ("tests_other", "comment")],
        )

    def test_remove_model(self):
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "comment"]),
            [("tests", "comment")],
        )

        project_state.remove_model("tests", "comment")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "post")],
        )
        self.assertNotIn(("tests", "comment"), project_state.relations)
        project_state.remove_model("tests", "post")
        self.assertEqual(project_state.relations, {})
        project_state.remove_model("tests", "user")
        self.assertEqual(project_state.relations, {})

    def test_rename_model(self):
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "comment"]),
            [("tests", "comment")],
        )

        related_field = project_state.relations["tests", "user"]["tests", "comment"]
        project_state.rename_model("tests", "comment", "opinion")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "post"), ("tests", "opinion")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "opinion"]),
            [("tests", "opinion")],
        )
        self.assertNotIn(("tests", "comment"), project_state.relations)
        self.assertEqual(
            project_state.relations["tests", "user"]["tests", "opinion"],
            related_field,
        )

        project_state.rename_model("tests", "user", "author")
        self.assertEqual(
            list(project_state.relations["tests", "author"]),
            [("tests", "post"), ("tests", "opinion")],
        )
        self.assertNotIn(("tests", "user"), project_state.relations)

    def test_rename_model_no_relations(self):
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        related_field = project_state.relations["tests", "user"]["tests", "post"]
        self.assertNotIn(("tests", "post"), project_state.relations)
        # Rename a model without relations.
        project_state.rename_model("tests", "post", "blog")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "blog")],
        )
        self.assertNotIn(("tests", "blog"), project_state.relations)
        self.assertEqual(
            related_field,
            project_state.relations["tests", "user"]["tests", "blog"],
        )

    def test_add_field(self):
        """
        Tests the addition of fields to a project state.

        This test case checks that fields can be successfully added to a project state,
        including foreign key relationships between models. It verifies that the added
        fields are correctly stored in the project state's relations dictionary and that
        the relationships between models are properly established.

        The test covers different scenarios, including adding a foreign key to the same
        model and adding a foreign key to a different model. It ensures that the
        preserve_default parameter is handled correctly, allowing default values to be
        preserved when adding new fields.

        The test validates the expected behavior of the add_field method by checking the
        project state's relations after adding fields and verifying that the relationships
        between models are correctly established.
        """
        project_state = self.get_base_project_state()
        self.assertNotIn(("tests", "post"), project_state.relations)
        # Add a self-referential foreign key.
        new_field = models.ForeignKey("self", models.CASCADE)
        project_state.add_field(
            "tests",
            "post",
            "next_post",
            new_field,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "post"]),
            [("tests", "post")],
        )
        self.assertEqual(
            project_state.relations["tests", "post"]["tests", "post"],
            {"next_post": new_field},
        )
        # Add a foreign key.
        new_field = models.ForeignKey("tests.post", models.CASCADE)
        project_state.add_field(
            "tests",
            "comment",
            "post",
            new_field,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "post"]),
            [("tests", "post"), ("tests", "comment")],
        )
        self.assertEqual(
            project_state.relations["tests", "post"]["tests", "comment"],
            {"post": new_field},
        )

    def test_add_field_m2m_with_through(self):
        project_state = self.get_base_project_state()
        project_state.add_model(
            ModelState(
                app_label="tests",
                name="Tag",
                fields=[("id", models.AutoField(primary_key=True))],
            )
        )
        project_state.add_model(
            ModelState(
                app_label="tests",
                name="PostTag",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("post", models.ForeignKey("tests.post", models.CASCADE)),
                    ("tag", models.ForeignKey("tests.tag", models.CASCADE)),
                ],
            )
        )
        self.assertEqual(
            list(project_state.relations["tests", "post"]),
            [("tests", "posttag")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "tag"]),
            [("tests", "posttag")],
        )
        # Add a many-to-many field with the through model.
        new_field = models.ManyToManyField("tests.tag", through="tests.posttag")
        project_state.add_field(
            "tests",
            "post",
            "tags",
            new_field,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "post"]),
            [("tests", "posttag")],
        )
        self.assertEqual(
            list(project_state.relations["tests", "tag"]),
            [("tests", "posttag"), ("tests", "post")],
        )
        self.assertEqual(
            project_state.relations["tests", "tag"]["tests", "post"],
            {"tags": new_field},
        )

    def test_remove_field(self):
        """

        Tests the removal of fields from a project state.

        Verifies that the remove_field method correctly updates relations between entities
        in the project state when a field is deleted. Specifically, it checks that:

        * The initial relations between entities are correctly identified
        * Removing a field from an entity updates the relations accordingly
        * Removing a second field from the same entity further updates the relations

        Ensures that the project state remains consistent after multiple field removals.

        """
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        # Remove a many-to-many field.
        project_state.remove_field("tests", "post", "authors")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment")],
        )
        # Remove a foreign key.
        project_state.remove_field("tests", "comment", "user")
        self.assertEqual(project_state.relations["tests", "user"], {})

    def test_remove_field_no_relations(self):
        """
        Tests the removal of a field from a project state that has no relations to other fields.

        This test case verifies that the removal of a field ('text') from a model ('post') in the 'tests' app does not affect the existing relations between 'tests' and 'user'. 

        It ensures that the `remove_field` method of the project state does not alter the relations when there are no direct dependencies between the field being removed and other related fields.

        The test relies on the initial project state established by `get_base_project_state`, which includes predefined relations between 'tests' and 'user' via 'comment' and 'post'.
        """
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        # Remove a non-relation field.
        project_state.remove_field("tests", "post", "text")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )

    def test_rename_field(self):
        project_state = self.get_base_project_state()
        field = project_state.models["tests", "comment"].fields["user"]
        self.assertEqual(
            project_state.relations["tests", "user"]["tests", "comment"],
            {"user": field},
        )

        project_state.rename_field("tests", "comment", "user", "author")
        renamed_field = project_state.models["tests", "comment"].fields["author"]
        self.assertEqual(
            project_state.relations["tests", "user"]["tests", "comment"],
            {"author": renamed_field},
        )
        self.assertEqual(field, renamed_field)

    def test_rename_field_no_relations(self):
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        # Rename a non-relation field.
        project_state.rename_field("tests", "post", "text", "description")
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )

    def test_alter_field(self):
        project_state = self.get_base_project_state()
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        # Alter a foreign key to a non-relation field.
        project_state.alter_field(
            "tests",
            "comment",
            "user",
            models.IntegerField(),
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "post")],
        )
        # Alter a non-relation field to a many-to-many field.
        m2m_field = models.ManyToManyField("tests.user")
        project_state.alter_field(
            "tests",
            "comment",
            "user",
            m2m_field,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "post"), ("tests", "comment")],
        )
        self.assertEqual(
            project_state.relations["tests", "user"]["tests", "comment"],
            {"user": m2m_field},
        )

    def test_alter_field_m2m_to_fk(self):
        """
        Tests the alteration of a many-to-many field to a foreign key.

         This test case verifies that the relations dictionary is updated correctly 
         when a many-to-many field is altered to a foreign key field, and ensures 
         that the default value is preserved during the alteration process.

         The test covers the successful removal of the many-to-many relation and 
         the establishment of a new foreign key relation between the models.

         The expected outcome is that the original many-to-many relation is removed 
         from the project state's relations and the new foreign key relation is added.

        """
        project_state = self.get_base_project_state()
        project_state.add_model(
            ModelState(
                app_label="tests_other",
                name="user_other",
                fields=[("id", models.AutoField(primary_key=True))],
            )
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        self.assertNotIn(("tests_other", "user_other"), project_state.relations)
        # Alter a many-to-many field to a foreign key.
        foreign_key = models.ForeignKey("tests_other.user_other", models.CASCADE)
        project_state.alter_field(
            "tests",
            "post",
            "authors",
            foreign_key,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment")],
        )
        self.assertEqual(
            list(project_state.relations["tests_other", "user_other"]),
            [("tests", "post")],
        )
        self.assertEqual(
            project_state.relations["tests_other", "user_other"]["tests", "post"],
            {"authors": foreign_key},
        )

    def test_many_relations_to_same_model(self):
        """

        Tests the handling of multiple relations from the same model.

        Verifies that the project state correctly manages multiple foreign key fields
        that point to the same model, including adding, renaming, and removing fields.
        Ensures that the relations are properly updated and maintained in the project state.

        Specifically, this test checks:

        * Adding a new field with a relation to an existing model
        * Verifying the correct number and names of relations
        * Renaming a field and checking that the relation is updated
        * Removing a field and checking that the relation is updated

        """
        project_state = self.get_base_project_state()
        new_field = models.ForeignKey("tests.user", models.CASCADE)
        project_state.add_field(
            "tests",
            "comment",
            "reviewer",
            new_field,
            preserve_default=True,
        )
        self.assertEqual(
            list(project_state.relations["tests", "user"]),
            [("tests", "comment"), ("tests", "post")],
        )
        comment_rels = project_state.relations["tests", "user"]["tests", "comment"]
        # Two foreign keys to the same model.
        self.assertEqual(len(comment_rels), 2)
        self.assertEqual(comment_rels["reviewer"], new_field)
        # Rename the second foreign key.
        project_state.rename_field("tests", "comment", "reviewer", "supervisor")
        self.assertEqual(len(comment_rels), 2)
        self.assertEqual(comment_rels["supervisor"], new_field)
        # Remove the first foreign key.
        project_state.remove_field("tests", "comment", "user")
        self.assertEqual(comment_rels, {"supervisor": new_field})


class ModelStateTests(SimpleTestCase):
    def test_custom_model_base(self):
        """
        Test that a custom model with a custom base class is correctly identified and its base classes are retrieved.

        This test case verifies that the from_model function in ModelState correctly handles 
        models that inherit from a custom base class, checking specifically that the 
        bases attribute of the resulting ModelState instance contains the expected base classes.

        The expected outcome is that the custom model's base classes are correctly identified 
        as the original Model base class from the models module, ensuring proper 
        functionality and inheritance in the model hierarchy. 
        """
        state = ModelState.from_model(ModelWithCustomBase)
        self.assertEqual(state.bases, (models.Model,))

    def test_bound_field_sanity_check(self):
        field = models.CharField(max_length=1)
        field.model = models.Model
        with self.assertRaisesMessage(
            ValueError, 'ModelState.fields cannot be bound to a model - "field" is.'
        ):
            ModelState("app", "Model", [("field", field)])

    def test_sanity_check_to(self):
        """
        Tests a sanity check for model state fields, ensuring that they do not directly reference a model class. Instead, they should use a string representation of the model, following the 'app.ModelName' format. This check prevents potential issues with model state fields and enforces consistency in model references. The test expects a ValueError to be raised with a specific error message when an invalid model field is provided.
        """
        field = models.ForeignKey(UnicodeModel, models.CASCADE)
        with self.assertRaisesMessage(
            ValueError,
            'Model fields in "ModelState.fields" cannot refer to a model class - '
            '"app.Model.field.to" does. Use a string reference instead.',
        ):
            ModelState("app", "Model", [("field", field)])

    def test_sanity_check_through(self):
        """
        Tests the sanity check for ManyToManyField through model references.

        This test case verifies that a ValueError is raised when the 'through' attribute
        of a ManyToManyField references a model class directly, rather than using a string
        reference. This is to prevent potential errors in ModelState fields.

        The test checks that the error message is correctly raised with a descriptive message,
        indicating that model fields cannot refer to a model class directly in the ModelState.fields.

        """
        field = models.ManyToManyField("UnicodeModel")
        field.remote_field.through = UnicodeModel
        with self.assertRaisesMessage(
            ValueError,
            'Model fields in "ModelState.fields" cannot refer to a model class - '
            '"app.Model.field.through" does. Use a string reference instead.',
        ):
            ModelState("app", "Model", [("field", field)])

    def test_sanity_index_name(self):
        field = models.IntegerField()
        options = {"indexes": [models.Index(fields=["field"])]}
        msg = (
            "Indexes passed to ModelState require a name attribute. <Index: "
            "fields=['field']> doesn't have one."
        )
        with self.assertRaisesMessage(ValueError, msg):
            ModelState("app", "Model", [("field", field)], options=options)

    def test_fields_immutability(self):
        """
        Rendering a model state doesn't alter its internal fields.
        """
        apps = Apps()
        field = models.CharField(max_length=1)
        state = ModelState("app", "Model", [("name", field)])
        Model = state.render(apps)
        self.assertNotEqual(Model._meta.get_field("name"), field)

    def test_repr(self):
        """

        Tests the representation of a ModelState object and ensures it properly handles invalid bases.

        This test case creates a ModelState object for a model with a single character field,
        then verifies that its string representation is correctly formatted.
        Additionally, it checks that attempting to resolve bases for a model with
        unresolvable bases raises an InvalidBasesError with the expected message.

        """
        field = models.CharField(max_length=1)
        state = ModelState(
            "app", "Model", [("name", field)], bases=["app.A", "app.B", "app.C"]
        )
        self.assertEqual(repr(state), "<ModelState: 'app.Model'>")

        project_state = ProjectState()
        project_state.add_model(state)
        with self.assertRaisesMessage(
            InvalidBasesError, "Cannot resolve bases for [<ModelState: 'app.Model'>]"
        ):
            project_state.apps

    def test_fields_ordering_equality(self):
        """
        Tests whether two ModelState instances with the same fields but in a different order are considered equal.

        This test case verifies that the equality check for ModelState instances is order-independent, meaning that the order in which fields are defined does not affect the comparison result. It ensures that ModelState instances with identical fields, regardless of their ordering, are treated as equal.
        """
        state = ModelState(
            "migrations",
            "Tag",
            [
                ("id", models.AutoField(primary_key=True)),
                ("name", models.CharField(max_length=100)),
                ("hidden", models.BooleanField()),
            ],
        )
        reordered_state = ModelState(
            "migrations",
            "Tag",
            [
                ("id", models.AutoField(primary_key=True)),
                # Purposely re-ordered.
                ("hidden", models.BooleanField()),
                ("name", models.CharField(max_length=100)),
            ],
        )
        self.assertEqual(state, reordered_state)

    @override_settings(TEST_SWAPPABLE_MODEL="migrations.SomeFakeModel")
    def test_create_swappable(self):
        """
        Tests making a ProjectState from an Apps with a swappable model
        """
        new_apps = Apps(["migrations"])

        class Author(models.Model):
            name = models.CharField(max_length=255)
            bio = models.TextField()
            age = models.IntegerField(blank=True, null=True)

            class Meta:
                app_label = "migrations"
                apps = new_apps
                swappable = "TEST_SWAPPABLE_MODEL"

        author_state = ModelState.from_model(Author)
        self.assertEqual(author_state.app_label, "migrations")
        self.assertEqual(author_state.name, "Author")
        self.assertEqual(list(author_state.fields), ["id", "name", "bio", "age"])
        self.assertEqual(author_state.fields["name"].max_length, 255)
        self.assertIs(author_state.fields["bio"].null, False)
        self.assertIs(author_state.fields["age"].null, True)
        self.assertEqual(
            author_state.options,
            {"swappable": "TEST_SWAPPABLE_MODEL", "indexes": [], "constraints": []},
        )
        self.assertEqual(author_state.bases, (models.Model,))
        self.assertEqual(author_state.managers, [])

    @override_settings(TEST_SWAPPABLE_MODEL="migrations.SomeFakeModel")
    def test_create_swappable_from_abstract(self):
        """
        A swappable model inheriting from a hierarchy:
        concrete -> abstract -> concrete.
        """
        new_apps = Apps(["migrations"])

        class SearchableLocation(models.Model):
            keywords = models.CharField(max_length=256)

            class Meta:
                app_label = "migrations"
                apps = new_apps

        class Station(SearchableLocation):
            name = models.CharField(max_length=128)

            class Meta:
                abstract = True

        class BusStation(Station):
            bus_routes = models.CharField(max_length=128)
            inbound = models.BooleanField(default=False)

            class Meta(Station.Meta):
                app_label = "migrations"
                apps = new_apps
                swappable = "TEST_SWAPPABLE_MODEL"

        station_state = ModelState.from_model(BusStation)
        self.assertEqual(station_state.app_label, "migrations")
        self.assertEqual(station_state.name, "BusStation")
        self.assertEqual(
            list(station_state.fields),
            ["searchablelocation_ptr", "name", "bus_routes", "inbound"],
        )
        self.assertEqual(station_state.fields["name"].max_length, 128)
        self.assertIs(station_state.fields["bus_routes"].null, False)
        self.assertEqual(
            station_state.options,
            {
                "abstract": False,
                "swappable": "TEST_SWAPPABLE_MODEL",
                "indexes": [],
                "constraints": [],
            },
        )
        self.assertEqual(station_state.bases, ("migrations.searchablelocation",))
        self.assertEqual(station_state.managers, [])

    @override_settings(TEST_SWAPPABLE_MODEL="migrations.SomeFakeModel")
    def test_custom_manager_swappable(self):
        """
        Tests making a ProjectState from unused models with custom managers
        """
        new_apps = Apps(["migrations"])

        class Food(models.Model):
            food_mgr = FoodManager("a", "b")
            food_qs = FoodQuerySet.as_manager()
            food_no_mgr = NoMigrationFoodManager("x", "y")

            class Meta:
                app_label = "migrations"
                apps = new_apps
                swappable = "TEST_SWAPPABLE_MODEL"

        food_state = ModelState.from_model(Food)

        # The default manager is used in migrations
        self.assertEqual([name for name, mgr in food_state.managers], ["food_mgr"])
        self.assertEqual(food_state.managers[0][1].args, ("a", "b", 1, 2))

    @isolate_apps("migrations", "django.contrib.contenttypes")
    def test_order_with_respect_to_private_field(self):
        class PrivateFieldModel(models.Model):
            content_type = models.ForeignKey("contenttypes.ContentType", models.CASCADE)
            object_id = models.PositiveIntegerField()
            private = GenericForeignKey()

            class Meta:
                order_with_respect_to = "private"

        state = ModelState.from_model(PrivateFieldModel)
        self.assertNotIn("order_with_respect_to", state.options)

    @isolate_apps("migrations")
    def test_abstract_model_children_inherit_indexes(self):
        class Abstract(models.Model):
            name = models.CharField(max_length=50)

            class Meta:
                app_label = "migrations"
                abstract = True
                indexes = [models.Index(fields=["name"])]

        class Child1(Abstract):
            pass

        class Child2(Abstract):
            pass

        abstract_state = ModelState.from_model(Abstract)
        child1_state = ModelState.from_model(Child1)
        child2_state = ModelState.from_model(Child2)
        index_names = [index.name for index in abstract_state.options["indexes"]]
        self.assertEqual(index_names, ["migrations__name_ae16a4_idx"])
        index_names = [index.name for index in child1_state.options["indexes"]]
        self.assertEqual(index_names, ["migrations__name_b0afd7_idx"])
        index_names = [index.name for index in child2_state.options["indexes"]]
        self.assertEqual(index_names, ["migrations__name_016466_idx"])

        # Modifying the state doesn't modify the index on the model.
        child1_state.options["indexes"][0].name = "bar"
        self.assertEqual(Child1._meta.indexes[0].name, "migrations__name_b0afd7_idx")

    @isolate_apps("migrations")
    def test_explicit_index_name(self):
        class TestModel(models.Model):
            name = models.CharField(max_length=50)

            class Meta:
                app_label = "migrations"
                indexes = [models.Index(fields=["name"], name="foo_idx")]

        model_state = ModelState.from_model(TestModel)
        index_names = [index.name for index in model_state.options["indexes"]]
        self.assertEqual(index_names, ["foo_idx"])

    @isolate_apps("migrations")
    def test_from_model_constraints(self):
        """
        Tests the transformation of model constraints from a Django model to a ModelState object.

        The model constraints tested here include a check constraint that ensures a field value is greater than a certain threshold.

        The test verifies that the original model constraints and the transformed state constraints are equal but not the same object, 
        and also checks that individual constraints within the lists are distinct objects.
        """
        class ModelWithConstraints(models.Model):
            size = models.IntegerField()

            class Meta:
                constraints = [
                    models.CheckConstraint(
                        condition=models.Q(size__gt=1), name="size_gt_1"
                    )
                ]

        state = ModelState.from_model(ModelWithConstraints)
        model_constraints = ModelWithConstraints._meta.constraints
        state_constraints = state.options["constraints"]
        self.assertEqual(model_constraints, state_constraints)
        self.assertIsNot(model_constraints, state_constraints)
        self.assertIsNot(model_constraints[0], state_constraints[0])


class RelatedModelsTests(SimpleTestCase):
    def setUp(self):
        self.apps = Apps(["migrations.related_models_app"])

    def create_model(
        self, name, foreign_keys=[], bases=(), abstract=False, proxy=False
    ):
        test_name = "related_models_app"
        assert not (abstract and proxy)
        meta_contents = {
            "abstract": abstract,
            "app_label": test_name,
            "apps": self.apps,
            "proxy": proxy,
        }
        meta = type("Meta", (), meta_contents)
        if not bases:
            bases = (models.Model,)
        body = {
            "Meta": meta,
            "__module__": "__fake__",
        }
        fname_base = fname = "%s_%%d" % name.lower()
        for i, fk in enumerate(foreign_keys, 1):
            fname = fname_base % i
            body[fname] = fk
        return type(name, bases, body)

    def assertRelated(self, model, needle):
        self.assertEqual(
            get_related_models_recursive(model),
            {(n._meta.app_label, n._meta.model_name) for n in needle},
        )

    def test_unrelated(self):
        A = self.create_model("A")
        B = self.create_model("B")
        self.assertRelated(A, [])
        self.assertRelated(B, [])

    def test_direct_fk(self):
        """
        /tests/test_direct_fk: Tests the functionality of direct foreign key relationships between two models.

            This test case verifies that a direct foreign key relationship is correctly established 
            between two models, 'A' and 'B', where 'A' has a foreign key referencing 'B'. It checks 
            that 'A' is related to 'B' and 'B' is related back to 'A', ensuring the relationship is 
            properly defined in both directions.
        """
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("B", models.CASCADE)]
        )
        B = self.create_model("B")
        self.assertRelated(A, [B])
        self.assertRelated(B, [A])

    def test_direct_hidden_fk(self):
        """

        Tests that a direct foreign key relationship is correctly established 
        between two models, even if the relationship is hidden on the related model.

        The test creates two models, A and B, where A has a foreign key to B. 
        The foreign key is defined with a related_name of '+', which hides the 
        relationship from the B model. The test then asserts that the relationship 
        is correctly established in both directions, i.e., that A is related to B 
        and B is related to A.

        """
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("B", models.CASCADE, related_name="+")]
        )
        B = self.create_model("B")
        self.assertRelated(A, [B])
        self.assertRelated(B, [A])

    def test_fk_through_proxy(self):
        A = self.create_model("A")
        B = self.create_model("B", bases=(A,), proxy=True)
        C = self.create_model("C", bases=(B,), proxy=True)
        D = self.create_model(
            "D", foreign_keys=[models.ForeignKey("C", models.CASCADE)]
        )
        self.assertRelated(A, [B, C, D])
        self.assertRelated(B, [A, C, D])
        self.assertRelated(C, [A, B, D])
        self.assertRelated(D, [A, B, C])

    def test_nested_fk(self):
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("B", models.CASCADE)]
        )
        B = self.create_model(
            "B", foreign_keys=[models.ForeignKey("C", models.CASCADE)]
        )
        C = self.create_model("C")
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [A, C])
        self.assertRelated(C, [A, B])

    def test_two_sided(self):
        """

        Tests the creation of two-sided relationships between two models.

        Verifies that when two models, A and B, reference each other through foreign keys,
        the relationships are correctly established in both directions. This test ensures
        that the models can be related to each other as expected, allowing for bidirectional
        navigation between instances of A and B.

        """
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("B", models.CASCADE)]
        )
        B = self.create_model(
            "B", foreign_keys=[models.ForeignKey("A", models.CASCADE)]
        )
        self.assertRelated(A, [B])
        self.assertRelated(B, [A])

    def test_circle(self):
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("B", models.CASCADE)]
        )
        B = self.create_model(
            "B", foreign_keys=[models.ForeignKey("C", models.CASCADE)]
        )
        C = self.create_model(
            "C", foreign_keys=[models.ForeignKey("A", models.CASCADE)]
        )
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [A, C])
        self.assertRelated(C, [A, B])

    def test_base(self):
        """

        Tests the basic relationship between a base model and its subclass.

        Verifies that a base model is correctly associated with its derived classes and
        that the derived classes are correctly associated with their base model.

        This test case ensures that the fundamental inheritance relationships are properly
        established and can be accurately retrieved.

        """
        A = self.create_model("A")
        B = self.create_model("B", bases=(A,))
        self.assertRelated(A, [B])
        self.assertRelated(B, [A])

    def test_nested_base(self):
        A = self.create_model("A")
        B = self.create_model("B", bases=(A,))
        C = self.create_model("C", bases=(B,))
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [A, C])
        self.assertRelated(C, [A, B])

    def test_multiple_bases(self):
        A = self.create_model("A")
        B = self.create_model("B")
        C = self.create_model(
            "C",
            bases=(
                A,
                B,
            ),
        )
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [A, C])
        self.assertRelated(C, [A, B])

    def test_multiple_nested_bases(self):
        """
        Tests whether the model inheritance relationships are correctly 
        resolved within a complex hierarchy of nested base classes.

        Checks the related models for each of the created models in a 
        scenarios with multiple levels of inheritance, ensuring that 
        all parent and child relationships are accurately identified and 
        returned. This includes verifying the relationships between models 
        at different levels of the hierarchy, such as great-grandparents 
        and great-grandchildren, as well as between models in separate 
        branches of the hierarchy.

        Models A through F are used to test relationships with multiple 
        nested base classes, while models Y and Z are used to verify 
        relationships in a simpler, separate hierarchy. The test asserts 
        that each model's related models are correctly identified, 
        covering various inheritance scenarios and confirming the 
        accurate resolution of complex relationships between models.
        """
        A = self.create_model("A")
        B = self.create_model("B")
        C = self.create_model(
            "C",
            bases=(
                A,
                B,
            ),
        )
        D = self.create_model("D")
        E = self.create_model("E", bases=(D,))
        F = self.create_model(
            "F",
            bases=(
                C,
                E,
            ),
        )
        Y = self.create_model("Y")
        Z = self.create_model("Z", bases=(Y,))
        self.assertRelated(A, [B, C, D, E, F])
        self.assertRelated(B, [A, C, D, E, F])
        self.assertRelated(C, [A, B, D, E, F])
        self.assertRelated(D, [A, B, C, E, F])
        self.assertRelated(E, [A, B, C, D, F])
        self.assertRelated(F, [A, B, C, D, E])
        self.assertRelated(Y, [Z])
        self.assertRelated(Z, [Y])

    def test_base_to_base_fk(self):
        """


        Tests the foreign key relationship between base models and their related instances.

        This test case checks the correctness of foreign key relationships 
        when a model inherits from another model with a foreign key.
        It verifies that the related objects are correctly resolved 
        between the base model, the inherited model, and their related instances.

        """
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("Y", models.CASCADE)]
        )
        B = self.create_model("B", bases=(A,))
        Y = self.create_model("Y")
        Z = self.create_model("Z", bases=(Y,))
        self.assertRelated(A, [B, Y, Z])
        self.assertRelated(B, [A, Y, Z])
        self.assertRelated(Y, [A, B, Z])
        self.assertRelated(Z, [A, B, Y])

    def test_base_to_subclass_fk(self):
        """

        Tests the foreign key relationship between a base model and its subclass, 
        and the relationships between the models and their parents or children.

        This test case verifies that the foreign key relationship is correctly 
        established between the base model and its subclass, and that the 
        relationships between the models are properly resolved.

        In this test, four models (A, B, Y, Z) are created with specific 
        inheritance relationships: model B inherits from model A, and model Z 
        inherits from model Y. Model A has a foreign key to model Z. The test 
        then checks that the relationships between these models are correctly 
        established, including the relationships between the base models and 
        their subclasses, as well as between the models and their parents or 
        children.

        """
        A = self.create_model(
            "A", foreign_keys=[models.ForeignKey("Z", models.CASCADE)]
        )
        B = self.create_model("B", bases=(A,))
        Y = self.create_model("Y")
        Z = self.create_model("Z", bases=(Y,))
        self.assertRelated(A, [B, Y, Z])
        self.assertRelated(B, [A, Y, Z])
        self.assertRelated(Y, [A, B, Z])
        self.assertRelated(Z, [A, B, Y])

    def test_direct_m2m(self):
        A = self.create_model("A", foreign_keys=[models.ManyToManyField("B")])
        B = self.create_model("B")
        self.assertRelated(A, [A.a_1.rel.through, B])
        self.assertRelated(B, [A, A.a_1.rel.through])

    def test_direct_m2m_self(self):
        """
        Tests direct many-to-many relationship with self-referential model.

        Verifies that a model with a many-to-many field referencing itself is correctly
        established and can be queried. This test ensures that the relationship is
        properly defined and the through model is correctly identified.
        """
        A = self.create_model("A", foreign_keys=[models.ManyToManyField("A")])
        self.assertRelated(A, [A.a_1.rel.through])

    def test_intermediate_m2m_self(self):
        """
        Tests the intermediate many-to-many relationship with self-referential models.

        This test case verifies the correct establishment of relationships between two models, 
        'A' and 'T', where 'A' has a many-to-many relationship with itself through the intermediate model 'T'. 
        It checks that model 'A' is related to model 'T' and vice versa, ensuring the expected associations 
        are correctly defined in the model definitions. The purpose is to validate the self-referential many-to-many 
        relationship in a model, ensuring proper relation setup and accessibility through the intermediate model 'T'.
        """
        A = self.create_model(
            "A", foreign_keys=[models.ManyToManyField("A", through="T")]
        )
        T = self.create_model(
            "T",
            foreign_keys=[
                models.ForeignKey("A", models.CASCADE),
                models.ForeignKey("A", models.CASCADE),
            ],
        )
        self.assertRelated(A, [T])
        self.assertRelated(T, [A])

    def test_intermediate_m2m(self):
        A = self.create_model(
            "A", foreign_keys=[models.ManyToManyField("B", through="T")]
        )
        B = self.create_model("B")
        T = self.create_model(
            "T",
            foreign_keys=[
                models.ForeignKey("A", models.CASCADE),
                models.ForeignKey("B", models.CASCADE),
            ],
        )
        self.assertRelated(A, [B, T])
        self.assertRelated(B, [A, T])
        self.assertRelated(T, [A, B])

    def test_intermediate_m2m_extern_fk(self):
        A = self.create_model(
            "A", foreign_keys=[models.ManyToManyField("B", through="T")]
        )
        B = self.create_model("B")
        Z = self.create_model("Z")
        T = self.create_model(
            "T",
            foreign_keys=[
                models.ForeignKey("A", models.CASCADE),
                models.ForeignKey("B", models.CASCADE),
                models.ForeignKey("Z", models.CASCADE),
            ],
        )
        self.assertRelated(A, [B, T, Z])
        self.assertRelated(B, [A, T, Z])
        self.assertRelated(T, [A, B, Z])
        self.assertRelated(Z, [A, B, T])

    def test_intermediate_m2m_base(self):
        A = self.create_model(
            "A", foreign_keys=[models.ManyToManyField("B", through="T")]
        )
        B = self.create_model("B")
        S = self.create_model("S")
        T = self.create_model(
            "T",
            foreign_keys=[
                models.ForeignKey("A", models.CASCADE),
                models.ForeignKey("B", models.CASCADE),
            ],
            bases=(S,),
        )
        self.assertRelated(A, [B, S, T])
        self.assertRelated(B, [A, S, T])
        self.assertRelated(S, [A, B, T])
        self.assertRelated(T, [A, B, S])

    def test_generic_fk(self):
        """
        Verifies the functionality of generic foreign keys in model relationships.

        This function tests the establishment of relationships between models using foreign keys, 
        specifically focusing on the interaction between a model with a generic foreign key and another model. 

        It checks if the relationships between models 'A' and 'B' are correctly established, 
        including the cascading effect on related models, by asserting that 'A' is related to 'B' and vice versa.

        This test ensures that the generic foreign key in model 'A' can correctly link to model 'B', 
        and that model 'B' can also be associated with model 'A' through its own foreign key, demonstrating a bidirectional relationship.
        """
        A = self.create_model(
            "A",
            foreign_keys=[
                models.ForeignKey("B", models.CASCADE),
                GenericForeignKey(),
            ],
        )
        B = self.create_model(
            "B",
            foreign_keys=[
                models.ForeignKey("C", models.CASCADE),
            ],
        )
        self.assertRelated(A, [B])
        self.assertRelated(B, [A])

    def test_abstract_base(self):
        A = self.create_model("A", abstract=True)
        B = self.create_model("B", bases=(A,))
        self.assertRelated(A, [B])
        self.assertRelated(B, [])

    def test_nested_abstract_base(self):
        A = self.create_model("A", abstract=True)
        B = self.create_model("B", bases=(A,), abstract=True)
        C = self.create_model("C", bases=(B,))
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [C])
        self.assertRelated(C, [])

    def test_proxy_base(self):
        """

        Tests the base class functionality of a proxy model.

        Verifies that a proxy model correctly establishes relationships with its base class.
        This includes checking that the base class recognizes the proxy model as a related object,
        and that the proxy model does not have any related objects of its own.

        Ensures that the proxy model is properly linked to its base class, and that this relationship
        is correctly reflected in the model's relationships.

        """
        A = self.create_model("A")
        B = self.create_model("B", bases=(A,), proxy=True)
        self.assertRelated(A, [B])
        self.assertRelated(B, [])

    def test_nested_proxy_base(self):
        """

        Tests the behavior of nested proxy models, verifying the relationships between base models and their proxies.

        This test case creates a hierarchical relationship between models A, B, and C, where B is a proxy model of A and C is a proxy model of B.
        It then asserts that the related models are correctly identified for each model in the hierarchy.

        """
        A = self.create_model("A")
        B = self.create_model("B", bases=(A,), proxy=True)
        C = self.create_model("C", bases=(B,), proxy=True)
        self.assertRelated(A, [B, C])
        self.assertRelated(B, [C])
        self.assertRelated(C, [])

    def test_multiple_mixed_bases(self):
        """

        Tests the relationships between models with multiple and mixed bases, 
        including abstract, proxy, and inherited models.

        This test case verifies that the relationships between the models are 
        correctly established, specifically testing the connections between 
        a model with multiple bases (including an abstract model, a normal model, 
        and a proxy model) and its related models.

        """
        A = self.create_model("A", abstract=True)
        M = self.create_model("M")
        P = self.create_model("P")
        Q = self.create_model("Q", bases=(P,), proxy=True)
        Z = self.create_model("Z", bases=(A, M, Q))
        # M has a pointer O2O field p_ptr to P
        self.assertRelated(A, [M, P, Q, Z])
        self.assertRelated(M, [P, Q, Z])
        self.assertRelated(P, [M, Q, Z])
        self.assertRelated(Q, [M, P, Z])
        self.assertRelated(Z, [M, P, Q])
