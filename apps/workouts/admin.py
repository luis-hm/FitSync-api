from django.contrib import admin

from apps.workouts.models import (
    CategoriaExercicio,
    Exercicio,
    ItemTreino,
    ItemTreinoTemplate,
    Treino,
    TreinoTemplate,
)


@admin.register(CategoriaExercicio)
class CategoriaExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "ordem", "data_criacao")
    list_filter = ("ativo",)
    search_fields = ("nome", "slug")
    readonly_fields = ("slug", "data_criacao")
    actions = ["ativar_categorias", "arquivar_categorias"]

    @admin.action(description="Ativar categorias selecionadas")
    def ativar_categorias(self, request, queryset):
        queryset.update(ativo=True)

    @admin.action(description="Arquivar categorias selecionadas")
    def arquivar_categorias(self, request, queryset):
        queryset.update(ativo=False)


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
    list_display = ("nome", "categoria", "grupo_muscular", "status", "origem", "ativo", "data_criacao")
    list_filter = ("categoria", "status", "origem", "ativo", "grupo_muscular")
    search_fields = ("nome", "slug", "categoria__nome", "grupo_muscular", "wger_id", "wger_uuid")
    autocomplete_fields = ("categoria",)
    readonly_fields = (
        "slug",
        "url_animacao",
        "origem",
        "wger_id",
        "wger_uuid",
        "fonte_url",
        "licenca_nome",
        "licenca_url",
        "licenca_autor",
        "data_criacao",
    )
    actions = ["aprovar_exercicios", "rejeitar_exercicios", "arquivar_exercicios"]

    @admin.action(description="Aprovar exercicios selecionados")
    def aprovar_exercicios(self, request, queryset):
        queryset.update(status=Exercicio.Status.APROVADO, ativo=True)

    @admin.action(description="Rejeitar exercicios selecionados")
    def rejeitar_exercicios(self, request, queryset):
        queryset.update(status=Exercicio.Status.REJEITADO, ativo=False)

    @admin.action(description="Arquivar exercicios selecionados")
    def arquivar_exercicios(self, request, queryset):
        queryset.update(ativo=False)


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
