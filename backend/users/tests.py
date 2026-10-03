from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .admin import CustomUserCreationForm
from .models import User


class UserModelTests(TestCase):
    def test_custom_model_and_email_identity(self):
        self.assertIs(get_user_model(), User)
        user = User.objects.create_user("  Owner@EXAMPLE.COM  ", "secret-password", base_currency="USD")
        user.refresh_from_db()
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertEqual(str(user), user.email)
        self.assertTrue(user.check_password("secret-password"))
        self.assertNotEqual(user.password, "secret-password")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_preferences_default_and_persist(self):
        user = User.objects.create_user("default@example.com", base_currency="GBP")
        self.assertEqual(user.base_currency, "GBP")
        self.assertEqual(user.timezone, "Africa/Lagos")
        self.assertFalse(user.has_usable_password())
        user.base_currency = "USD"
        user.timezone = "America/New_York"
        user.full_clean()
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.base_currency, "USD")
        self.assertEqual(user.timezone, "America/New_York")

    def test_invalid_email_and_preferences(self):
        for email in (None, "", "   "):
            with self.subTest(email=email), self.assertRaises(ValueError):
                User.objects.create_user(email)
        for fields in ({"email": "invalid"}, {"base_currency": "usd"},
                       {"base_currency": "US"}, {"base_currency": "USDD"},
                       {"base_currency": "USD\n"}, {"timezone": "Unknown/Place"},
                       {"timezone": "../UTC"}, {"timezone": ""}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                User.objects.create_user(**({"email": "valid@example.com", "base_currency": "USD"} | fields))

    def test_duplicate_email_validation(self):
        User.objects.create_user("owner@example.com", base_currency="USD")
        for email in ("owner@example.com", "OWNER@EXAMPLE.COM"):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                User.objects.create_user(email, base_currency="USD")

    def test_database_enforces_case_insensitive_uniqueness(self):
        User.objects.create_user("owner@example.com", base_currency="USD")
        for email in ("owner@example.com", "OWNER@EXAMPLE.COM"):
            with self.subTest(email=email), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    User.objects.bulk_create([User(email=email, base_currency="USD")])

    def test_superuser_flags(self):
        user = User.objects.create_superuser("admin@example.com", "secret-password", base_currency="USD")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        for flags in ({"is_staff": False}, {"is_superuser": False}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                User.objects.create_superuser("other@example.com", **flags)

    def test_admin_creation_form(self):
        form = CustomUserCreationForm(data={
            "email": "New@Example.com", "base_currency": "GBP", "timezone": "Europe/London",
            "password1": "Strong-test-password-913!", "password2": "Strong-test-password-913!",
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("Strong-test-password-913!"))
        self.assertEqual(user.base_currency, "GBP")
        self.assertEqual(user.timezone, "Europe/London")

    def test_admin_registered_and_pages_render(self):
        self.assertIn(User, admin.site._registry)
        user = User.objects.create_superuser("admin@example.com", "secret-password", base_currency="USD")
        self.client.force_login(user)
        for name, args in (("admin:users_user_changelist", []),
                           ("admin:users_user_add", []),
                           ("admin:users_user_change", [user.pk])):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_currency_has_no_default_and_requires_explicit_selection(self):
        self.assertFalse(User._meta.get_field("base_currency").has_default())
        user = User(email="unselected@example.com")
        self.assertEqual(user.base_currency, "")
        with self.assertRaises(ValidationError) as error:
            user.full_clean()
        self.assertIn("base_currency", error.exception.message_dict)
        for fields in ({}, {"base_currency": ""}, {"base_currency": None}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                User.objects.create_user("unselected@example.com", **fields)
        self.assertFalse(User.objects.filter(email="unselected@example.com").exists())

    def test_superuser_requires_currency_and_command_accepts_it(self):
        self.assertIn("base_currency", User.REQUIRED_FIELDS)
        with self.assertRaises(ValidationError):
            User.objects.create_superuser("missing@example.com", "secret-password")
        call_command("createsuperuser", email="command@example.com", base_currency="EUR", interactive=False, verbosity=0)
        user = User.objects.get(email="command@example.com")
        self.assertEqual(user.base_currency, "EUR")
        self.assertTrue(user.is_superuser)

    def test_admin_requires_currency_without_initial_selection(self):
        form = CustomUserCreationForm()
        self.assertTrue(form.fields["base_currency"].required)
        self.assertIsNone(form.fields["base_currency"].initial)
        form = CustomUserCreationForm(data={
            "email": "missing@example.com", "timezone": "Africa/Lagos",
            "password1": "Strong-test-password-913!", "password2": "Strong-test-password-913!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("base_currency", form.errors)

    def test_currency_designation_can_change_repeatedly(self):
        user = User.objects.create_user("change@example.com", base_currency="NGN")
        for currency in ("USD", "EUR", "NGN"):
            user.base_currency = currency
            user.full_clean()
            user.save(update_fields=["base_currency"])
            user.refresh_from_db()
            self.assertEqual(user.base_currency, currency)
