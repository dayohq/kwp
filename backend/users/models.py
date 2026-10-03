from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Enter a valid IANA time zone.", code="invalid_timezone")


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        if not email or not email.strip():
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    base_currency = models.CharField(
        max_length=3,
        validators=[RegexValidator(r"\A[A-Z]{3}\Z", "Use a three-letter uppercase currency code.")],
    )
    timezone = models.CharField(max_length=64, default="Africa/Lagos", validators=[validate_timezone])

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["base_currency"]
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="users_user_email_ci_unique")]

    def clean(self):
        super().clean()
        self.email = type(self).objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.email = type(self).objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
