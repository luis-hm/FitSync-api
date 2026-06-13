from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.assessments.views import (
    AlunoAnamneseAPIView,
    AlunoEvolucaoAPIView,
    AlunoMeAnamneseAPIView,
    AlunoMeEvolucaoAPIView,
    AlunoMeResumoAPIView,
    AlunoResumoAPIView,
    AnamneseViewSet,
    AvaliacaoViewSet,
    PersonalRankingAPIView,
)


app_name = "assessments"

router = DefaultRouter()
router.register("avaliacoes", AvaliacaoViewSet, basename="avaliacoes")
router.register("anamneses", AnamneseViewSet, basename="anamneses")

urlpatterns = [
    path("", include(router.urls)),
    path("me/anamnese/", AlunoMeAnamneseAPIView.as_view(), name="aluno-me-anamnese"),
    path("me/evolucao/", AlunoMeEvolucaoAPIView.as_view(), name="aluno-me-evolucao"),
    path("me/resumo/", AlunoMeResumoAPIView.as_view(), name="aluno-me-resumo"),
    path("alunos/<uuid:pk>/anamnese/", AlunoAnamneseAPIView.as_view(), name="aluno-anamnese"),
    path("alunos/<uuid:pk>/evolucao/", AlunoEvolucaoAPIView.as_view(), name="aluno-evolucao"),
    path("alunos/<uuid:pk>/resumo/", AlunoResumoAPIView.as_view(), name="aluno-resumo"),
    path("personal/ranking/", PersonalRankingAPIView.as_view(), name="personal-ranking"),
]
