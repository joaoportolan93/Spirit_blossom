"""
Serializers de autenticação: login, registro, recuperação de senha e Google OAuth.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from core.models import UserProfile

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
        from core.services.auth import register_user

        birth_date = validated_data.get("birth_date")
        terms_accepted = validated_data.get("terms_accepted", True)
        user, _refresh = register_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            birth_date=birth_date,
            terms_accepted=terms_accepted,
            request=self.context.get("request"),
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )


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


class DeleteAccountSerializer(serializers.Serializer):
    """
    Serializer para DELETE /api/users/account/ (Onda 6 — LGPD).

    - Conta com senha: exige `current_password`.
    - Conta Google OAuth (`has_usable_password() == False`): exige `confirm_username`
      (o próprio @username) como confirmação explícita.
    """

    current_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
    )
    confirm_username = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        user = self.context["request"].user

        if user.has_usable_password():
            # Conta com senha: exige current_password
            pwd = attrs.get("current_password", "")
            if not pwd:
                raise serializers.ValidationError(
                    {"current_password": _("A senha atual é obrigatória para excluir a conta.")}
                )
            if not user.check_password(pwd):
                raise serializers.ValidationError(
                    {"current_password": _("Senha incorreta.")}
                )
        else:
            # Conta Google OAuth: exige confirm_username
            confirm = (attrs.get("confirm_username") or "").strip()
            if not confirm:
                raise serializers.ValidationError(
                    {
                        "confirm_username": _(
                            "Digite seu @username para confirmar a exclusão da conta."
                        )
                    }
                )
            if confirm.lstrip("@") != user.username:
                raise serializers.ValidationError(
                    {"confirm_username": _("O username informado não corresponde ao da sua conta.")}
                )
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer para POST /api/auth/change-password/ (Onda 5)."""

    current_password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True, min_length=8, required=True, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Senha atual incorreta."))
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": _("As novas senhas não coincidem.")}
            )
        return attrs


class CurrentUserSerializer(serializers.ModelSerializer):
    """Serializer para GET /api/auth/me/ (Onda 5)."""

    display_name = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    is_private = serializers.SerializerMethodField()
    show_likes_tab = serializers.SerializerMethodField()
    theme = serializers.SerializerMethodField()
    language = serializers.SerializerMethodField()
    notify_likes = serializers.SerializerMethodField()
    notify_comments = serializers.SerializerMethodField()
    notify_follows = serializers.SerializerMethodField()
    notify_mentions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "email",
            "bio",
            "avatar",
            "is_private",
            "show_likes_tab",
            "theme",
            "language",
            "notify_likes",
            "notify_comments",
            "notify_follows",
            "notify_mentions",
        )

    def get_display_name(self, obj):
        p = getattr(obj, "profile", None)
        return p.display_name if p else ""

    def get_bio(self, obj):
        p = getattr(obj, "profile", None)
        return p.bio if p else ""

    def get_avatar(self, obj):
        p = getattr(obj, "profile", None)
        return p.avatar.url if p and p.avatar else None

    def get_is_private(self, obj):
        p = getattr(obj, "profile", None)
        return p.is_private if p else False

    def get_show_likes_tab(self, obj):
        p = getattr(obj, "profile", None)
        return p.show_likes_tab if p else True

    def get_theme(self, obj):
        p = getattr(obj, "profile", None)
        return p.theme if p else UserProfile.Theme.LIGHT

    def get_language(self, obj):
        p = getattr(obj, "profile", None)
        return p.language if p else UserProfile.Language.PT_BR

    def get_notify_likes(self, obj):
        p = getattr(obj, "profile", None)
        return p.notify_likes if p else True

    def get_notify_comments(self, obj):
        p = getattr(obj, "profile", None)
        return p.notify_comments if p else True

    def get_notify_follows(self, obj):
        p = getattr(obj, "profile", None)
        return p.notify_follows if p else True

    def get_notify_mentions(self, obj):
        p = getattr(obj, "profile", None)
        return p.notify_mentions if p else True


class UserSettingsSerializer(serializers.ModelSerializer):
    """Representação serializada de configurações do usuário (Onda 5)."""

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            "username",
            "display_name",
            "email",
            "bio",
            "avatar",
            "is_private",
            "show_likes_tab",
            "notify_likes",
            "notify_comments",
            "notify_follows",
            "notify_mentions",
            "theme",
            "language",
        )

    def get_avatar(self, obj):
        return obj.avatar.url if obj.avatar else None


class UserSettingsUpdateSerializer(serializers.Serializer):
    """Serializer para PATCH /api/users/settings/ (Onda 5)."""

    username = serializers.CharField(max_length=30, required=False)
    display_name = serializers.CharField(max_length=60, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=160, required=False, allow_blank=True)
    avatar = serializers.FileField(required=False, allow_null=True)
    remove_avatar = serializers.BooleanField(required=False)
    is_private = serializers.BooleanField(required=False)
    show_likes_tab = serializers.BooleanField(required=False)
    notify_likes = serializers.BooleanField(required=False)
    notify_comments = serializers.BooleanField(required=False)
    notify_follows = serializers.BooleanField(required=False)
    notify_mentions = serializers.BooleanField(required=False)
    theme = serializers.ChoiceField(choices=UserProfile.Theme.choices, required=False)
    language = serializers.ChoiceField(choices=UserProfile.Language.choices, required=False)

    def validate_username(self, value):
        user = self.context["request"].user
        value = value.strip()
        if not value.isalnum():
            raise serializers.ValidationError(
                _("O nome de usuário deve conter apenas letras e números.")
            )
        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(_("Este nome de usuário já está em uso."))
        return value

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()
        else:
            data = dict(data)
        if "avatar" in data and data["avatar"] == "":
            data["avatar"] = None
            data["remove_avatar"] = True
        return super().to_internal_value(data)

    def validate_avatar(self, value):
        if not value:
            return value
        from django.core.exceptions import ValidationError as DjangoValidationError

        from core.utils.image_security import sanitize_avatar_image

        try:
            return sanitize_avatar_image(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def validate(self, attrs):
        if self.initial_data.get("avatar") == "":
            attrs["remove_avatar"] = True
        return attrs

    def update(self, instance: UserProfile, validated_data):
        from core.services.social import update_user_privacy
        from core.utils.image_security import delete_old_avatar

        user = instance.user

        # 1. Atualiza username se enviado
        if "username" in validated_data:
            new_username = validated_data["username"]
            if new_username != user.username:
                user.username = new_username
                user.save(update_fields=["username"])

        # 2. Atualiza display_name e bio
        if "display_name" in validated_data:
            instance.display_name = validated_data["display_name"].strip()

        if "bio" in validated_data:
            instance.bio = validated_data["bio"]

        # 3. Atualiza avatar
        if validated_data.get("remove_avatar") or (
            "avatar" in validated_data and validated_data["avatar"] is None
        ):
            delete_old_avatar(instance)
            instance.avatar = None
        elif validated_data.get("avatar"):
            delete_old_avatar(instance)
            instance.avatar = validated_data["avatar"]

        # 4. Atualiza privacidade (deleta pending se pública)
        if "is_private" in validated_data:
            new_private = validated_data["is_private"]
            if new_private != instance.is_private:
                update_user_privacy(user=user, is_private=new_private)
                instance.refresh_from_db(fields=["is_private"])

        # 5. Atualiza demais flags e escolhas
        for field in [
            "show_likes_tab",
            "notify_likes",
            "notify_comments",
            "notify_follows",
            "notify_mentions",
            "theme",
            "language",
        ]:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance
