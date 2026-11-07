"""
Serializers de autenticação: login, registro, recuperação de senha e Google OAuth.
"""

from datetime import date

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import UserProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    birth_date = serializers.DateField(required=True)
    terms_accepted = serializers.BooleanField(required=True, write_only=True)

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "password",
            "password_confirm",
            "birth_date",
            "terms_accepted",
        )

    def validate_username(self, value):
        if not value.isalnum():
            raise serializers.ValidationError(
                _("O nome de usuário deve conter apenas letras e números.")
            )
        return value.lower()

    def validate_birth_date(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError(
                _("É necessário ter pelo menos 18 anos para se cadastrar.")
            )
        return value

    def validate(self, attrs):
        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError(
                {
                    "terms_accepted": _(
                        "Você deve aceitar os Termos de Uso e Política de Privacidade."
                    )
                }
            )
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": _("As senhas não conferem.")})
        return attrs

    def create(self, validated_data):
        birth_date = validated_data.pop("birth_date")
        validated_data.pop("terms_accepted")
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "birth_date": birth_date,
                "terms_accepted_at": timezone.now(),
            },
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError(_("E-mail ou senha inválidos."))
        if not user.is_active or user.status != user.Status.ACTIVE:
            raise serializers.ValidationError(_("Conta inativa ou suspensa."))
        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        min_length=8,
        write_only=True,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs.pop("new_password_confirm"):
            raise serializers.ValidationError(
                {"new_password_confirm": _("As senhas não conferem.")}
            )
        return attrs


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)


class GoogleCompleteSignupSerializer(serializers.Serializer):
    onboarding_token = serializers.CharField(required=True)
    username = serializers.CharField(min_length=3, max_length=30, required=True)
    birth_date = serializers.DateField(required=True)
    terms_accepted = serializers.BooleanField(required=True)

    def validate_username(self, value):
        if not value.isalnum():
            raise serializers.ValidationError(
                _("O nome de usuário deve conter apenas letras e números.")
            )
        value = value.lower()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("Este nome de usuário já está em uso."))
        return value

    def validate_birth_date(self, value):
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise serializers.ValidationError(
                _("É necessário ter pelo menos 18 anos para se cadastrar.")
            )
        return value

    def validate(self, attrs):
        if not attrs.get("terms_accepted"):
            raise serializers.ValidationError(
                {
                    "terms_accepted": _(
                        "Você deve aceitar os Termos de Uso e Política de Privacidade."
                    )
                }
            )
        return attrs
