from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import User


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'base_currency', 'timezone')
        read_only_fields = fields


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(write_only=True, trim_whitespace=False)
    base_currency = serializers.RegexField(r'\A[A-Z]{3}\Z', max_length=3, trim_whitespace=False)
    timezone = serializers.CharField(required=False, max_length=64)

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirmation']:
            raise serializers.ValidationError({'password_confirmation': ['Passwords do not match.']})
        user = User(**{key: value for key, value in attrs.items()
                       if key not in ('password', 'password_confirmation')})
        try:
            user.full_clean(exclude=['password'])
            validate_password(attrs['password'], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, 'message_dict') else {'password': error.messages}
            ) from None
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirmation')
        try:
            with transaction.atomic():
                return User.objects.create_user(**validated_data)
        except IntegrityError:
            # A competing registration can win after serializer validation.
            raise serializers.ValidationError({'email': ['An account with this email already exists.']}) from None
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(request=self.context['request'],
                            email=User.objects.normalize_email(attrs['email']),
                            password=attrs['password'])
        if user is None:
            raise serializers.ValidationError({'detail': 'Invalid email or password.'})
        attrs['user'] = user
        return attrs
