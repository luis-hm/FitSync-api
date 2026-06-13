from django.contrib import admin

from apps.assessments.models import (
    Anamnese,
    Avaliacao,
    AvaliacaoBioimpedancia,
    AvaliacaoCircunferencias,
    AvaliacaoDobras,
)


class AvaliacaoDobrasInline(admin.StackedInline):
    model = AvaliacaoDobras
    extra = 0


class AvaliacaoBioimpedanciaInline(admin.StackedInline):
    model = AvaliacaoBioimpedancia
    extra = 0


class AvaliacaoCircunferenciasInline(admin.StackedInline):
    model = AvaliacaoCircunferencias
    extra = 0


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = (
        "aluno",
        "personal",
        "metodo",
        "data_avaliacao",
        "data_proxima_avaliacao",
        "peso_kg",
        "imc",
        "percentual_gordura",
        "ativo",
    )
    list_filter = ("metodo", "ativo", "data_avaliacao")
    search_fields = ("aluno__usuario__nome", "aluno__usuario__email", "personal__nome", "personal__email")
    raw_id_fields = ("aluno", "personal")
    inlines = [
        AvaliacaoDobrasInline,
        AvaliacaoBioimpedanciaInline,
        AvaliacaoCircunferenciasInline,
    ]


@admin.register(Anamnese)
class AnamneseAdmin(admin.ModelAdmin):
    list_display = ("aluno", "ativo", "data_atualizacao")
    list_filter = ("ativo",)
    search_fields = ("aluno__usuario__nome", "aluno__usuario__email")
    raw_id_fields = ("aluno",)
