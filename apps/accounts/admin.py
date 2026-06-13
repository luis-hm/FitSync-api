from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from apps.accounts.models import Aluno, PersonalProfile, Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ("nome", "email", "tipo")


class UsuarioChangeForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    model = Usuario

    list_display = ("nome", "email", "tipo", "is_active", "is_staff", "data_criacao")
    list_filter = ("tipo", "is_active", "is_staff", "is_superuser")
    search_fields = ("nome", "email")
    ordering = ("nome", "email")
    readonly_fields = ("last_login", "data_criacao")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": ("nome", "tipo")}),
        ("Permissoes", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "data_criacao")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("nome", "email", "password1", "password2", "tipo", "is_staff"),
        }),
    )


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "personal", "sexo", "data_nascimento", "objetivo_principal")
    list_filter = ("sexo",)
    search_fields = ("usuario__nome", "usuario__email", "personal__nome", "personal__email")
    raw_id_fields = ("usuario", "personal")


@admin.register(PersonalProfile)
class PersonalProfileAdmin(admin.ModelAdmin):
    list_display = ("usuario", "especialidade", "data_atualizacao")
    search_fields = ("usuario__nome", "usuario__email", "especialidade")
    raw_id_fields = ("usuario",)
    readonly_fields = ("data_criacao", "data_atualizacao")
