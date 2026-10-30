"""
Serializers de autenticação para login e registro.
"""
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "username", "password", "password_confirm")

    def validate_username(self, value):
        if not value.isalnum():
            raise serializers.ValidationError(_("O nome de usuário deve conter apenas letras e números."))
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError({"password_confirm": _("As senhas não conferem.")})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


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
