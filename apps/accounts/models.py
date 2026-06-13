import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O email e obrigatorio.")

        email = self.normalize_email(email).lower()
        tipo = extra_fields.get("tipo")
        if tipo == Usuario.Tipo.ADMIN and not extra_fields.get("is_superuser"):
            raise ValueError("Usuario admin deve ser criado como superuser.")

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        if user.tipo == Usuario.Tipo.PERSONAL:
            PersonalProfile.objects.get_or_create(usuario=user)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("tipo", Usuario.Tipo.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("tipo") != Usuario.Tipo.ADMIN:
            raise ValueError("Superuser precisa ter tipo=ADMIN.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa ter is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa ter is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    class Tipo(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        PERSONAL = "PERSONAL", "Personal"
        ALUNO = "ALUNO", "Aluno"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.PERSONAL,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        db_table = "usuario"
        ordering = ["nome", "email"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="usuario_email_ci_unique",
            ),
        ]

    @property
    def is_personal(self):
        return self.tipo == self.Tipo.PERSONAL

    @property
    def is_aluno(self):
        return self.tipo == self.Tipo.ALUNO

    @property
    def is_admin_role(self):
        return self.tipo == self.Tipo.ADMIN

    def clean(self):
        if self.tipo == self.Tipo.ADMIN and not (self.is_staff and self.is_superuser):
            raise ValidationError({"tipo": "Admin precisa ter is_staff e is_superuser."})

    def __str__(self):
        return f"{self.nome} <{self.email}>"


class PersonalProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="personal_profile",
    )
    especialidade = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "personal_profile"
        verbose_name = "perfil de personal"
        verbose_name_plural = "perfis de personal"

    def clean(self):
        if self.usuario_id and self.usuario.tipo != self.usuario.Tipo.PERSONAL:
            raise ValidationError({"usuario": "Perfil precisa estar vinculado a um personal."})

    def __str__(self):
        return f"Perfil de {self.usuario.nome}"


class Aluno(models.Model):
    class Sexo(models.TextChoices):
        MASCULINO = "M", "Masculino"
        FEMININO = "F", "Feminino"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="aluno",
    )
    personal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="alunos",
    )
    data_nascimento = models.DateField()
    sexo = models.CharField(max_length=1, choices=Sexo.choices)
    objetivo_principal = models.CharField(max_length=120, blank=True)
    observacoes_medicas = models.TextField(blank=True)

    class Meta:
        db_table = "aluno"
        ordering = ["usuario__nome"]
        verbose_name = "aluno"
        verbose_name_plural = "alunos"

    def clean(self):
        if self.usuario_id and self.usuario.tipo != self.usuario.Tipo.ALUNO:
            raise ValidationError({"usuario": "Aluno precisa estar vinculado a um usuario aluno."})
        if self.personal_id and self.personal.tipo != self.personal.Tipo.PERSONAL:
            raise ValidationError({"personal": "O responsavel precisa ser um personal."})

    def __str__(self):
        return self.usuario.nome
