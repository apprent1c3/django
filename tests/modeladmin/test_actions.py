from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from .models import Band


class AdminActionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="super", password="secret", email="super@example.com"
        )
        content_type = ContentType.objects.get_for_model(Band)
        Permission.objects.create(
            name="custom", codename="custom_band", content_type=content_type
        )
        for user_type in ("view", "add", "change", "delete", "custom"):
            username = "%suser" % user_type
            user = User.objects.create_user(
                username=username, password="secret", is_staff=True
            )
            permission = Permission.objects.get(
                codename="%s_band" % user_type, content_type=content_type
            )
            user.user_permissions.add(permission)
            setattr(cls, username, user)

    def test_get_actions_respects_permissions(self):
        """
        Tests that the get_actions method of a ModelAdmin respects custom permissions.

        The test ensures that the actions returned by get_actions are filtered based on the 
        permissions of the requesting user. This includes both built-in actions like 
        'delete_selected' and custom actions registered with the @admin.action decorator.

        The test covers various scenarios, including different types of permissions 
        ('add', 'change', 'delete', 'view', 'custom') and different types of users 
        (superuser, viewuser, adduser, changeuser, deleteuser, customuser).
        """
        class MockRequest:
            pass

        class BandAdmin(admin.ModelAdmin):
            actions = ["custom_action"]

            @admin.action
            def custom_action(modeladmin, request, queryset):
                pass

            def has_custom_permission(self, request):
                return request.user.has_perm("%s.custom_band" % self.opts.app_label)

        ma = BandAdmin(Band, admin.AdminSite())
        mock_request = MockRequest()
        mock_request.GET = {}
        cases = [
            (None, self.viewuser, ["custom_action"]),
            ("view", self.superuser, ["delete_selected", "custom_action"]),
            ("view", self.viewuser, ["custom_action"]),
            ("add", self.adduser, ["custom_action"]),
            ("change", self.changeuser, ["custom_action"]),
            ("delete", self.deleteuser, ["delete_selected", "custom_action"]),
            ("custom", self.customuser, ["custom_action"]),
        ]
        for permission, user, expected in cases:
            with self.subTest(permission=permission, user=user):
                if permission is None:
                    if hasattr(BandAdmin.custom_action, "allowed_permissions"):
                        del BandAdmin.custom_action.allowed_permissions
                else:
                    BandAdmin.custom_action.allowed_permissions = (permission,)
                mock_request.user = user
                actions = ma.get_actions(mock_request)
                self.assertEqual(list(actions.keys()), expected)

    def test_actions_inheritance(self):
        """

        Tests the inheritance of actions in Django admin classes.

        This test case checks how actions defined in a base admin class are inherited
        by its subclasses. It verifies that actions are properly inherited when the
        subclass does not override the actions attribute, and that they are not
        inherited when the subclass explicitly sets actions to None.

        """
        class AdminBase(admin.ModelAdmin):
            actions = ["custom_action"]

            @admin.action
            def custom_action(modeladmin, request, queryset):
                pass

        class AdminA(AdminBase):
            pass

        class AdminB(AdminBase):
            actions = None

        ma1 = AdminA(Band, admin.AdminSite())
        action_names = [name for _, name, _ in ma1._get_base_actions()]
        self.assertEqual(action_names, ["delete_selected", "custom_action"])
        # `actions = None` removes actions from superclasses.
        ma2 = AdminB(Band, admin.AdminSite())
        action_names = [name for _, name, _ in ma2._get_base_actions()]
        self.assertEqual(action_names, ["delete_selected"])

    def test_global_actions_description(self):
        @admin.action(description="Site-wide admin action 1.")
        """
        Tests the description of global actions in the admin interface.

        This test verifies that global actions added to an AdminSite are correctly displayed
        in the admin interface, including their descriptions. It checks that actions with
        explicit descriptions are displayed as specified, and that actions without explicit
        descriptions are displayed with a default description.

        The test covers the following scenarios:

        * Global actions with explicit descriptions
        * Global actions without explicit descriptions
        * Actions added to a custom AdminSite instance

        It ensures that the descriptions of global actions are correctly retrieved and
        displayed in the admin interface, allowing administrators to understand the purpose
        of each action.
        """
        def global_action_1(modeladmin, request, queryset):
            pass

        @admin.action
        def global_action_2(modeladmin, request, queryset):
            pass

        admin_site = admin.AdminSite()
        admin_site.add_action(global_action_1)
        admin_site.add_action(global_action_2)

        class BandAdmin(admin.ModelAdmin):
            pass

        ma = BandAdmin(Band, admin_site)
        self.assertEqual(
            [description for _, _, description in ma._get_base_actions()],
            [
                "Delete selected %(verbose_name_plural)s",
                "Site-wide admin action 1.",
                "Global action 2",
            ],
        )

    def test_actions_replace_global_action(self):
        @admin.action(description="Site-wide admin action 1.")
        def global_action_1(modeladmin, request, queryset):
            pass

        @admin.action(description="Site-wide admin action 2.")
        def global_action_2(modeladmin, request, queryset):
            pass

        admin.site.add_action(global_action_1, name="custom_action_1")
        admin.site.add_action(global_action_2, name="custom_action_2")

        @admin.action(description="Local admin action 1.")
        def custom_action_1(modeladmin, request, queryset):
            pass

        class BandAdmin(admin.ModelAdmin):
            actions = [custom_action_1, "custom_action_2"]

            @admin.action(description="Local admin action 2.")
            def custom_action_2(self, request, queryset):
                pass

        ma = BandAdmin(Band, admin.site)
        self.assertEqual(ma.check(), [])
        self.assertEqual(
            [
                desc
                for _, name, desc in ma._get_base_actions()
                if name.startswith("custom_action")
            ],
            [
                "Local admin action 1.",
                "Local admin action 2.",
            ],
        )
