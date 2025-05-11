from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.checks import Error
from django.core.exceptions import FieldDoesNotExist, FieldError
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


@isolate_apps("model_inheritance")
class AbstractInheritanceTests(SimpleTestCase):
    def test_single_parent(self):
        """
        Tests the behavior of model field inheritance in abstract base models, 
        verifying that field attributes are correctly overridden in descendant models.
        """
        class AbstractBase(models.Model):
            name = models.CharField(max_length=30)

            class Meta:
                abstract = True

        class AbstractDescendant(AbstractBase):
            name = models.CharField(max_length=50)

            class Meta:
                abstract = True

        class DerivedChild(AbstractBase):
            name = models.CharField(max_length=50)

        class DerivedGrandChild(AbstractDescendant):
            pass

        self.assertEqual(AbstractDescendant._meta.get_field("name").max_length, 50)
        self.assertEqual(DerivedChild._meta.get_field("name").max_length, 50)
        self.assertEqual(DerivedGrandChild._meta.get_field("name").max_length, 50)

    def test_multiple_inheritance_allows_inherited_field(self):
        """
        Tests that single layer multiple inheritance allows the inherited field to be derived from the first base class when there are conflicting field definitions.
        """

        class ParentA(models.Model):
            name = models.CharField(max_length=255)

            class Meta:
                abstract = True

        class ParentB(models.Model):
            name = models.IntegerField()

            class Meta:
                abstract = True

        class Child(ParentA, ParentB):
            pass

        self.assertEqual(Child.check(), [])
        inherited_field = Child._meta.get_field("name")
        self.assertIsInstance(inherited_field, models.CharField)
        self.assertEqual(inherited_field.max_length, 255)

    def test_diamond_shaped_multiple_inheritance_is_depth_first(self):
        """
        Tests that in cases of diamond-shaped multiple inheritance, field resolution follows a depth-first approach, ensuring that the base class's field is inherited rather than the one from the secondary parent class.
        """

        class Root(models.Model):
            name = models.CharField(max_length=255)

            class Meta:
                abstract = True

        class ParentA(Root):
            class Meta:
                abstract = True

        class ParentB(Root):
            name = models.IntegerField()

            class Meta:
                abstract = True

        class Child(ParentA, ParentB):
            pass

        self.assertEqual(Child.check(), [])
        inherited_field = Child._meta.get_field("name")
        self.assertIsInstance(inherited_field, models.CharField)
        self.assertEqual(inherited_field.max_length, 255)

    def test_target_field_may_be_pushed_down(self):
        """
        Tests that a target field can be pushed down in a model inheritance hierarchy by re-declaring it in the child model, allowing it to override an inherited field from a different base class.
        """

        class Root(models.Model):
            name = models.CharField(max_length=255)

            class Meta:
                abstract = True

        class ParentA(Root):
            class Meta:
                abstract = True

        class ParentB(Root):
            name = models.IntegerField()

            class Meta:
                abstract = True

        class Child(ParentA, ParentB):
            name = models.IntegerField()

        self.assertEqual(Child.check(), [])
        inherited_field = Child._meta.get_field("name")
        self.assertIsInstance(inherited_field, models.IntegerField)

    def test_multiple_inheritance_cannot_shadow_concrete_inherited_field(self):
        """

        Tests that Django correctly handles multiple inheritance where a concrete model's 
        field shadows a field from an abstract base class and vice versa.

        """
        class ConcreteParent(models.Model):
            name = models.CharField(max_length=255)

        class AbstractParent(models.Model):
            name = models.IntegerField()

            class Meta:
                abstract = True

        class FirstChild(ConcreteParent, AbstractParent):
            pass

        class AnotherChild(AbstractParent, ConcreteParent):
            pass

        self.assertIsInstance(FirstChild._meta.get_field("name"), models.CharField)
        self.assertEqual(
            AnotherChild.check(),
            [
                Error(
                    "The field 'name' clashes with the field 'name' "
                    "from model 'model_inheritance.concreteparent'.",
                    obj=AnotherChild._meta.get_field("name"),
                    id="models.E006",
                )
            ],
        )

    def test_virtual_field(self):
        """
        Tests the behavior of virtual fields in abstract models, specifically when a subclass overrides or extends a field from a parent class.
        """
        class RelationModel(models.Model):
            content_type = models.ForeignKey(ContentType, models.CASCADE)
            object_id = models.PositiveIntegerField()
            content_object = GenericForeignKey("content_type", "object_id")

        class RelatedModelAbstract(models.Model):
            field = GenericRelation(RelationModel)

            class Meta:
                abstract = True

        class ModelAbstract(models.Model):
            field = models.CharField(max_length=100)

            class Meta:
                abstract = True

        class OverrideRelatedModelAbstract(RelatedModelAbstract):
            field = models.CharField(max_length=100)

        class ExtendModelAbstract(ModelAbstract):
            field = GenericRelation(RelationModel)

        self.assertIsInstance(
            OverrideRelatedModelAbstract._meta.get_field("field"), models.CharField
        )
        self.assertIsInstance(
            ExtendModelAbstract._meta.get_field("field"), GenericRelation
        )

    def test_cannot_override_indirect_abstract_field(self):
        """
        Tests that Django prevents overriding an abstract model's field from an indirect base class.
        """
        class AbstractBase(models.Model):
            name = models.CharField(max_length=30)

            class Meta:
                abstract = True

        class ConcreteDescendant(AbstractBase):
            pass

        msg = (
            "Local field 'name' in class 'Descendant' clashes with field of "
            "the same name from base class 'ConcreteDescendant'."
        )
        with self.assertRaisesMessage(FieldError, msg):

            class Descendant(ConcreteDescendant):
                name = models.IntegerField()

    def test_override_field_with_attr(self):
        """
        Tests that a field in an abstract base model is correctly overridden by an attribute in a descendant model, effectively removing the field from the descendant's fields.
        """
        class AbstractBase(models.Model):
            first_name = models.CharField(max_length=50)
            last_name = models.CharField(max_length=50)
            middle_name = models.CharField(max_length=30)
            full_name = models.CharField(max_length=150)

            class Meta:
                abstract = True

        class Descendant(AbstractBase):
            middle_name = None

            def full_name(self):
                return self.first_name + self.last_name

        msg = "Descendant has no field named %r"
        with self.assertRaisesMessage(FieldDoesNotExist, msg % "middle_name"):
            Descendant._meta.get_field("middle_name")

        with self.assertRaisesMessage(FieldDoesNotExist, msg % "full_name"):
            Descendant._meta.get_field("full_name")

    def test_overriding_field_removed_by_concrete_model(self):
        """
        Tests that a field removed in an abstract model can be overridden by a concrete model.
        """
        class AbstractModel(models.Model):
            foo = models.CharField(max_length=30)

            class Meta:
                abstract = True

        class RemovedAbstractModelField(AbstractModel):
            foo = None

        class OverrideRemovedFieldByConcreteModel(RemovedAbstractModelField):
            foo = models.CharField(max_length=50)

        self.assertEqual(
            OverrideRemovedFieldByConcreteModel._meta.get_field("foo").max_length, 50
        )

    def test_shadowed_fkey_id(self):
        """
        Tests that a field name does not shadow a foreign key's automatically generated id field when inheriting from an abstract base model.
        """
        class Foo(models.Model):
            pass

        class AbstractBase(models.Model):
            foo = models.ForeignKey(Foo, models.CASCADE)

            class Meta:
                abstract = True

        class Descendant(AbstractBase):
            foo_id = models.IntegerField()

        self.assertEqual(
            Descendant.check(),
            [
                Error(
                    "The field 'foo_id' clashes with the field 'foo' "
                    "from model 'model_inheritance.descendant'.",
                    obj=Descendant._meta.get_field("foo_id"),
                    id="models.E006",
                )
            ],
        )

    def test_shadow_related_name_when_set_to_none(self):
        """

        Tests the behavior of related names when set to None in a model's ForeignKey field,
        verifying that no errors occur during model checking.

        """
        class AbstractBase(models.Model):
            bar = models.IntegerField()

            class Meta:
                abstract = True

        class Foo(AbstractBase):
            bar = None
            foo = models.IntegerField()

        class Bar(models.Model):
            bar = models.ForeignKey(Foo, models.CASCADE, related_name="bar")

        self.assertEqual(Bar.check(), [])

    def test_reverse_foreign_key(self):
        """
        Tests that a ForeignKey's reverse accessor name does not clash with an existing field name on the related model, specifically when there is model inheritance involved.
        """
        class AbstractBase(models.Model):
            foo = models.CharField(max_length=100)

            class Meta:
                abstract = True

        class Descendant(AbstractBase):
            pass

        class Foo(models.Model):
            foo = models.ForeignKey(Descendant, models.CASCADE, related_name="foo")

        self.assertEqual(
            Foo._meta.get_field("foo").check(),
            [
                Error(
                    "Reverse accessor 'Descendant.foo' for "
                    "'model_inheritance.Foo.foo' clashes with field name "
                    "'model_inheritance.Descendant.foo'.",
                    hint=(
                        "Rename field 'model_inheritance.Descendant.foo', or "
                        "add/change a related_name argument to the definition "
                        "for field 'model_inheritance.Foo.foo'."
                    ),
                    obj=Foo._meta.get_field("foo"),
                    id="fields.E302",
                ),
                Error(
                    "Reverse query name for 'model_inheritance.Foo.foo' "
                    "clashes with field name "
                    "'model_inheritance.Descendant.foo'.",
                    hint=(
                        "Rename field 'model_inheritance.Descendant.foo', or "
                        "add/change a related_name argument to the definition "
                        "for field 'model_inheritance.Foo.foo'."
                    ),
                    obj=Foo._meta.get_field("foo"),
                    id="fields.E303",
                ),
            ],
        )

    def test_multi_inheritance_field_clashes(self):
        """
        Tests handling of field clashes in models with multi-level inheritance, ensuring that duplicate field names are properly detected and reported as errors.
        """
        class AbstractBase(models.Model):
            name = models.CharField(max_length=30)

            class Meta:
                abstract = True

        class ConcreteBase(AbstractBase):
            pass

        class AbstractDescendant(ConcreteBase):
            class Meta:
                abstract = True

        class ConcreteDescendant(AbstractDescendant):
            name = models.CharField(max_length=100)

        self.assertEqual(
            ConcreteDescendant.check(),
            [
                Error(
                    "The field 'name' clashes with the field 'name' from "
                    "model 'model_inheritance.concretebase'.",
                    obj=ConcreteDescendant._meta.get_field("name"),
                    id="models.E006",
                )
            ],
        )

    def test_override_one2one_relation_auto_field_clashes(self):
        """
        Tests that attempting to override a one-to-one relation auto field with a clash raises a FieldError.

        This test ensures that when a subclass tries to define a field that conflicts with an auto-generated field
        used for a parent link, a FieldError is raised to prevent potential data inconsistencies.
        """
        class ConcreteParent(models.Model):
            name = models.CharField(max_length=255)

        class AbstractParent(models.Model):
            name = models.IntegerField()

            class Meta:
                abstract = True

        msg = (
            "Auto-generated field 'concreteparent_ptr' in class 'Descendant' "
            "for parent_link to base class 'ConcreteParent' clashes with "
            "declared field of the same name."
        )
        with self.assertRaisesMessage(FieldError, msg):

            class Descendant(ConcreteParent, AbstractParent):
                concreteparent_ptr = models.CharField(max_length=30)

    def test_abstract_model_with_regular_python_mixin_mro(self):
        """
        Tests the correct handling of abstract model inheritance with regular Python mixins, verifying that model fields are correctly resolved and that attribute overriding works as expected in various inheritance scenarios.
        """
        class AbstractModel(models.Model):
            name = models.CharField(max_length=255)
            age = models.IntegerField()

            class Meta:
                abstract = True

        class Mixin:
            age = None

        class Mixin2:
            age = 2

        class DescendantMixin(Mixin):
            pass

        class ConcreteModel(models.Model):
            foo = models.IntegerField()

        class ConcreteModel2(ConcreteModel):
            age = models.SmallIntegerField()

        def fields(model):
            if not hasattr(model, "_meta"):
                return []
            return [(f.name, f.__class__) for f in model._meta.get_fields()]

        model_dict = {"__module__": "model_inheritance"}
        model1 = type("Model1", (AbstractModel, Mixin), model_dict.copy())
        model2 = type("Model2", (Mixin2, AbstractModel), model_dict.copy())
        model3 = type("Model3", (DescendantMixin, AbstractModel), model_dict.copy())
        model4 = type("Model4", (Mixin2, Mixin, AbstractModel), model_dict.copy())
        model5 = type(
            "Model5", (Mixin2, ConcreteModel2, Mixin, AbstractModel), model_dict.copy()
        )

        self.assertEqual(
            fields(model1),
            [
                ("id", models.AutoField),
                ("name", models.CharField),
                ("age", models.IntegerField),
            ],
        )

        self.assertEqual(
            fields(model2), [("id", models.AutoField), ("name", models.CharField)]
        )
        self.assertEqual(getattr(model2, "age"), 2)

        self.assertEqual(
            fields(model3), [("id", models.AutoField), ("name", models.CharField)]
        )

        self.assertEqual(
            fields(model4), [("id", models.AutoField), ("name", models.CharField)]
        )
        self.assertEqual(getattr(model4, "age"), 2)

        self.assertEqual(
            fields(model5),
            [
                ("id", models.AutoField),
                ("foo", models.IntegerField),
                ("concretemodel_ptr", models.OneToOneField),
                ("age", models.SmallIntegerField),
                ("concretemodel2_ptr", models.OneToOneField),
                ("name", models.CharField),
            ],
        )
