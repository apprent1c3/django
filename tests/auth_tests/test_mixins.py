from unittest import mock

from django.contrib.auth import models
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.views.generic import View


class AlwaysTrueMixin(UserPassesTestMixin):
    def test_func(self):
        """
        This is a comment
        """
        return True


class AlwaysFalseMixin(UserPassesTestMixin):
    def test_func(self):
        """
        This is a comment
        """
        return False


class EmptyResponseView(View):
    def get(self, request, *args, **kwargs):
        """
        This is a comment
        """
        return HttpResponse()


class AlwaysTrueView(AlwaysTrueMixin, EmptyResponseView):
    pass


class AlwaysFalseView(AlwaysFalseMixin, EmptyResponseView):
    pass


class StackedMixinsView1(
    LoginRequiredMixin, PermissionRequiredMixin, EmptyResponseView
):
    permission_required = ["auth_tests.add_customuser", "auth_tests.change_customuser"]
    raise_exception = True


class StackedMixinsView2(
    PermissionRequiredMixin, LoginRequiredMixin, EmptyResponseView
):
    permission_required = ["auth_tests.add_customuser", "auth_tests.change_customuser"]
    raise_exception = True


class AccessMixinTests(TestCase):
    factory = RequestFactory()

    def test_stacked_mixins_success(self):
        """
        This is a comment
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)

        view = StackedMixinsView2.as_view()
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_stacked_mixins_missing_permission(self):
        """
        This is a comment
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(codename__in=("add_customuser",))
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

        view = StackedMixinsView2.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_access_mixin_permission_denied_response(self):
        """
        This is a comment
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        # Authenticated users receive PermissionDenied.
        request = self.factory.get("/rand")
        request.user = user
        view = AlwaysFalseView.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)
        # Anonymous users are redirected to the login page.
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/rand")

    def test_access_mixin_permission_denied_remote_login_url(self):
        """
        This is a comment
        """
        class AView(AlwaysFalseView):
            login_url = "https://www.remote.example.com/login"

        view = AView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            "https://www.remote.example.com/login?next=http%3A//testserver/rand",
        )

    @mock.patch.object(models.User, "is_authenticated", False)
    def test_stacked_mixins_not_logged_in(self):
        """
        This is a comment
        """
        user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        user.user_permissions.add(*perms)
        request = self.factory.get("/rand")
        request.user = user

        view = StackedMixinsView1.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)

        view = StackedMixinsView2.as_view()
        with self.assertRaises(PermissionDenied):
            view(request)


class UserPassesTestTests(SimpleTestCase):
    factory = RequestFactory()

    def _test_redirect(self, view=None, url="/accounts/login/?next=/rand"):
        """
        This is a comment
        """
        if not view:
            view = AlwaysFalseView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, url)

    def test_default(self):
        """
        This is a comment
        """
        self._test_redirect()

    def test_custom_redirect_url(self):
        """
        This is a comment
        """
        class AView(AlwaysFalseView):
            login_url = "/login/"

        self._test_redirect(AView.as_view(), "/login/?next=/rand")

    def test_custom_redirect_parameter(self):
        """
        This is a comment
        """
        class AView(AlwaysFalseView):
            redirect_field_name = "goto"

        self._test_redirect(AView.as_view(), "/accounts/login/?goto=/rand")

    def test_no_redirect_parameter(self):
        """
        This is a comment
        """
        class AView(AlwaysFalseView):
            redirect_field_name = None

        self._test_redirect(AView.as_view(), "/accounts/login/")

    def test_raise_exception(self):
        """
        This is a comment
        """
        class AView(AlwaysFalseView):
            raise_exception = True

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)

    def test_raise_exception_custom_message(self):
        """
        This is a comment
        """
        msg = "You don't have access here"

        class AView(AlwaysFalseView):
            raise_exception = True
            permission_denied_message = msg

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        view = AView.as_view()
        with self.assertRaisesMessage(PermissionDenied, msg):
            view(request)

    def test_raise_exception_custom_message_function(self):
        """
        This is a comment
        """
        msg = "You don't have access here"

        class AView(AlwaysFalseView):
            raise_exception = True

            def get_permission_denied_message(self):
                """
                This is a comment
                """
                return msg

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        view = AView.as_view()
        with self.assertRaisesMessage(PermissionDenied, msg):
            view(request)

    def test_user_passes(self):
        """
        This is a comment
        """
        view = AlwaysTrueView.as_view()
        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 200)


class LoginRequiredMixinTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.user = models.User.objects.create(username="joe", password="qwerty")

    def test_login_required(self):
        """
        This is a comment
        """

        class AView(LoginRequiredMixin, EmptyResponseView):
            pass

        view = AView.as_view()

        request = self.factory.get("/rand")
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/accounts/login/?next=/rand", response.url)
        request = self.factory.get("/rand")
        request.user = self.user
        response = view(request)
        self.assertEqual(response.status_code, 200)


class PermissionsRequiredMixinTests(TestCase):
    factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.user = models.User.objects.create(username="joe", password="qwerty")
        perms = models.Permission.objects.filter(
            codename__in=("add_customuser", "change_customuser")
        )
        cls.user.user_permissions.add(*perms)

    def test_many_permissions_pass(self):
        """
        This is a comment
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
            ]

        request = self.factory.get("/rand")
        request.user = self.user
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

    def test_single_permission_pass(self):
        """
        This is a comment
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = "auth_tests.add_customuser"

        request = self.factory.get("/rand")
        request.user = self.user
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

    def test_permissioned_denied_redirect(self):
        """
        This is a comment
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]

        # Authenticated users receive PermissionDenied.
        request = self.factory.get("/rand")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)
        # Anonymous users are redirected to the login page.
        request.user = AnonymousUser()
        resp = AView.as_view()(request)
        self.assertEqual(resp.status_code, 302)

    def test_permissioned_denied_exception_raised(self):
        """
        This is a comment
        """
        class AView(PermissionRequiredMixin, EmptyResponseView):
            permission_required = [
                "auth_tests.add_customuser",
                "auth_tests.change_customuser",
                "nonexistent-permission",
            ]
            raise_exception = True

        request = self.factory.get("/rand")
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            AView.as_view()(request)
