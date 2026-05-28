from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.accounts.models import Aluno
from apps.core.logging_utils import log_security_event


Usuario = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nome", "email", "tipo", "data_criacao"]
        read_only_fields = ["id", "email", "tipo", "data_criacao"]


class AdminUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
    )
    personal_id = serializers.UUIDField(write_only=True, required=False)
    data_nascimento = serializers.DateField(write_only=True, required=False)
    sexo = serializers.ChoiceField(
        choices=Aluno.Sexo.choices,
        write_only=True,
        required=False,
    )
    objetivo_principal = serializers.CharField(write_only=True, required=False, allow_blank=True)
    observacoes_medicas = serializers.CharField(write_only=True, required=False, allow_blank=True)
    aluno = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = [
            "id",
            "nome",
            "email",
            "tipo",
            "is_active",
            "data_criacao",
            "password",
            "personal_id",
            "data_nascimento",
            "sexo",
            "objetivo_principal",
            "observacoes_medicas",
            "aluno",
        ]
        read_only_fields = ["id", "data_criacao", "aluno"]

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_aluno(self, obj):
        if obj.tipo != Usuario.Tipo.ALUNO:
            return None
        try:
            return AlunoSerializer(obj.aluno).data
        except Aluno.DoesNotExist:
            return None

    def validate_email(self, value):
        email = Usuario.objects.normalize_email(value).lower()
        queryset = Usuario.objects.filter(email__iexact=email)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ja existe um usuario com este email.")
        return email

    def validate_tipo(self, value):
        if value == Usuario.Tipo.ADMIN:
            raise serializers.ValidationError("Admin deve ser criado por createsuperuser.")
        return value

    def validate(self, attrs):
        if self.instance and "tipo" in attrs and attrs["tipo"] != self.instance.tipo:
            raise serializers.ValidationError({"tipo": "Tipo nao pode ser alterado."})

        tipo = attrs.get("tipo") or getattr(self.instance, "tipo", None)
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Senha temporaria e obrigatoria."})

        if not self.instance and tipo == Usuario.Tipo.ALUNO:
            required_fields = ["personal_id", "data_nascimento", "sexo"]
            missing = [field for field in required_fields if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError(
                    {field: "Este campo e obrigatorio para aluno." for field in missing}
                )
            try:
                attrs["personal"] = Usuario.objects.get(
                    id=attrs["personal_id"],
                    tipo=Usuario.Tipo.PERSONAL,
                    is_active=True,
                )
            except Usuario.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"personal_id": "Personal nao encontrado ou inativo."}
                ) from exc

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        personal = validated_data.pop("personal", None)
        validated_data.pop("personal_id", None)

        aluno_data = {
            "data_nascimento": validated_data.pop("data_nascimento", None),
            "sexo": validated_data.pop("sexo", ""),
            "objetivo_principal": validated_data.pop("objetivo_principal", ""),
            "observacoes_medicas": validated_data.pop("observacoes_medicas", ""),
        }

        user = Usuario.objects.create_user(password=password, **validated_data)
        if user.tipo == Usuario.Tipo.ALUNO:
            Aluno.objects.create(usuario=user, personal=personal, **aluno_data)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        validated_data.pop("personal_id", None)
        validated_data.pop("data_nascimento", None)
        validated_data.pop("sexo", None)
        validated_data.pop("objetivo_principal", None)
        validated_data.pop("observacoes_medicas", None)
        validated_data.pop("personal", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AlunoSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    personal_id = serializers.UUIDField(source="personal.id", read_only=True)
    personal_nome = serializers.CharField(source="personal.nome", read_only=True)

    class Meta:
        model = Aluno
        fields = [
            "id",
            "usuario",
            "personal_id",
            "personal_nome",
            "data_nascimento",
            "sexo",
            "objetivo_principal",
            "observacoes_medicas",
        ]
        read_only_fields = ["id", "usuario", "personal_id", "personal_nome"]


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class AuthRootResponseSerializer(serializers.Serializer):
    module = serializers.CharField()
    endpoints = serializers.DictField(child=serializers.CharField())


class RegisterResponseSerializer(serializers.Serializer):
    user = UsuarioSerializer()
    aluno = AlunoSerializer(allow_null=True)


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = UsuarioSerializer()


class AccessTokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


class RegisterSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    tipo = serializers.ChoiceField(
        choices=[
            Usuario.Tipo.PERSONAL,
            Usuario.Tipo.ALUNO,
        ],
        required=False,
        default=Usuario.Tipo.PERSONAL,
    )
    is_personal = serializers.BooleanField(required=False, write_only=True)
    personal_id = serializers.UUIDField(required=False)
    data_nascimento = serializers.DateField(required=False)
    sexo = serializers.ChoiceField(choices=Aluno.Sexo.choices, required=False)
    objetivo_principal = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
    )
    observacoes_medicas = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        email = Usuario.objects.normalize_email(value).lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Ja existe um usuario com este email.")
        return email

    def validate(self, attrs):
        legacy_is_personal = attrs.pop("is_personal", None)
        if legacy_is_personal is not None and "tipo" not in self.initial_data:
            attrs["tipo"] = (
                Usuario.Tipo.PERSONAL if legacy_is_personal else Usuario.Tipo.ALUNO
            )

        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas nao coincidem."})

        if attrs["tipo"] == Usuario.Tipo.ADMIN:
            raise serializers.ValidationError({"tipo": "Admin nao pode ser criado por cadastro publico."})

        if attrs["tipo"] == Usuario.Tipo.ALUNO:
            required_fields = ["personal_id", "data_nascimento", "sexo"]
            missing = [field for field in required_fields if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError(
                    {field: "Este campo e obrigatorio para cadastro de aluno." for field in missing}
                )

            try:
                personal = Usuario.objects.get(
                    id=attrs["personal_id"],
                    tipo=Usuario.Tipo.PERSONAL,
                    is_active=True,
                )
            except Usuario.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"personal_id": "Personal nao encontrado ou inativo."}
                ) from exc
            attrs["personal"] = personal

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")
        tipo = validated_data.pop("tipo")
        personal = validated_data.pop("personal", None)
        validated_data.pop("personal_id", None)

        aluno_data = {
            "data_nascimento": validated_data.pop("data_nascimento", None),
            "sexo": validated_data.pop("sexo", ""),
            "objetivo_principal": validated_data.pop("objetivo_principal", ""),
            "observacoes_medicas": validated_data.pop("observacoes_medicas", ""),
        }

        user = Usuario.objects.create_user(
            password=password,
            tipo=tipo,
            **validated_data,
        )

        aluno = None
        if tipo == Usuario.Tipo.ALUNO:
            aluno = Aluno.objects.create(usuario=user, personal=personal, **aluno_data)

        return {"user": user, "aluno": aluno}

    def to_representation(self, instance):
        return {
            "user": UsuarioSerializer(instance["user"]).data,
            "aluno": AlunoSerializer(instance["aluno"]).data if instance.get("aluno") else None,
        }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = Usuario.objects.normalize_email(attrs["email"]).lower()
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=email,
            password=attrs["password"],
        )
        if not user:
            inactive_user = Usuario.objects.filter(email__iexact=email, is_active=False).first()
            if inactive_user and inactive_user.check_password(attrs["password"]):
                log_security_event(
                    "login_inactive_user",
                    request=request,
                    context={"email": email, "user_id": str(inactive_user.id)},
                )
                raise serializers.ValidationError({"detail": "Usuario inativo."})

            log_security_event("login_failed", request=request, context={"email": email})
            raise serializers.ValidationError({"detail": "Email ou senha invalidos."})
        if not user.is_active:
            log_security_event(
                "login_inactive_user",
                request=request,
                context={"email": email, "user_id": str(user.id)},
            )
            raise serializers.ValidationError({"detail": "Usuario inativo."})

        attrs["user"] = user
        return attrs


class RefreshSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(required=False)

    def validate(self, attrs):
        refresh = attrs.get("refresh") or self.context["request"].COOKIES.get(
            settings.AUTH_COOKIE_REFRESH_NAME
        )
        if not refresh:
            raise serializers.ValidationError({"refresh": "Refresh token nao informado."})
        attrs["refresh"] = refresh
        return super().validate(attrs)


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["nome"]


class AlunoSelfSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source="usuario.nome", max_length=150)
    email = serializers.EmailField(source="usuario.email", read_only=True)
    tipo = serializers.CharField(source="usuario.tipo", read_only=True)
    personal_id = serializers.UUIDField(source="personal.id", read_only=True)
    personal_nome = serializers.CharField(source="personal.nome", read_only=True)

    class Meta:
        model = Aluno
        fields = [
            "id",
            "nome",
            "email",
            "tipo",
            "personal_id",
            "personal_nome",
            "data_nascimento",
            "sexo",
            "objetivo_principal",
            "observacoes_medicas",
        ]
        read_only_fields = ["id", "email", "tipo", "personal_id", "personal_nome"]

    def validate_sexo(self, value):
        if not self.instance or value == self.instance.sexo:
            return value

        try:
            from apps.assessments.models import Avaliacao
        except ImportError:
            return value

        if Avaliacao.objects.filter(aluno=self.instance).exists():
            raise serializers.ValidationError(
                "Sexo nao pode ser alterado apos o aluno possuir avaliacoes."
            )
        return value

    def update(self, instance, validated_data):
        usuario_data = validated_data.pop("usuario", {})
        nome = usuario_data.get("nome")
        if nome is not None:
            instance.usuario.nome = nome
            instance.usuario.save(update_fields=["nome"])

        return super().update(instance, validated_data)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = Usuario.objects.normalize_email(self.validated_data["email"]).lower()
        user = Usuario.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_path = settings.PASSWORD_RESET_FRONTEND_PATH
        if not reset_path.startswith("/"):
            reset_path = f"/{reset_path}"
        reset_url = (
            f"{settings.FRONTEND_URL}{reset_path}?"
            f"{urlencode({'uid': uid, 'token': token})}"
        )

        send_mail(
            subject="Recuperacao de senha FitSync",
            message=(
                "Use o link abaixo para redefinir sua senha.\n\n"
                f"link: {reset_url}\n\n"
                "Dados tecnicos para integracao manual:\n"
                f"uid: {uid}\n"
                f"token: {token}\n"
                "endpoint: /api/auth/password-reset/confirm/"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@fitsync.local"),
            recipient_list=[user.email],
            fail_silently=False,
        )


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "As senhas nao coincidem."})

        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = Usuario.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist) as exc:
            raise serializers.ValidationError({"uid": "Token de redefinicao invalido."}) from exc

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Token de redefinicao invalido."})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
