from django.contrib import admin

from apps.workouts.models import (
    Exercicio,
    ItemTreino,
    ItemTreinoTemplate,
    Treino,
    TreinoTemplate,
)


class ItemTreinoTemplateInline(admin.TabularInline):
    model = ItemTreinoTemplate
    extra = 0
    autocomplete_fields = ("exercicio",)


class ItemTreinoInline(admin.TabularInline):
    model = ItemTreino
    extra = 0
    autocomplete_fields = ("exercicio",)


@admin.register(Exercicio)
class ExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome", "grupo_muscular", "data_criacao")
    list_filter = ("grupo_muscular",)
    search_fields = ("nome", "grupo_muscular")


@admin.register(TreinoTemplate)
class TreinoTemplateAdmin(admin.ModelAdmin):
    list_display = ("titulo", "personal", "ativo", "data_criacao")
    list_filter = ("ativo",)
    search_fields = ("titulo", "personal__nome", "personal__email")
    raw_id_fields = ("personal",)
    inlines = [ItemTreinoTemplateInline]


@admin.register(Treino)
class TreinoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "aluno", "ativo", "data_inicio", "data_vencimento")
    list_filter = ("ativo", "dia_da_semana")
    search_fields = ("titulo", "aluno__usuario__nome", "aluno__usuario__email")
    raw_id_fields = ("aluno", "template_origem")
    inlines = [ItemTreinoInline]
