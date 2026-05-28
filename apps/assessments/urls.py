from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.assessments.views import (
    AlunoEvolucaoAPIView,
    AvaliacaoViewSet,
    PersonalRankingAPIView,
)


app_name = "assessments"

router = DefaultRouter()
router.register("avaliacoes", AvaliacaoViewSet, basename="avaliacoes")

urlpatterns = [
    path("", include(router.urls)),
    path("alunos/<uuid:pk>/evolucao/", AlunoEvolucaoAPIView.as_view(), name="aluno-evolucao"),
    path("personal/ranking/", PersonalRankingAPIView.as_view(), name="personal-ranking"),
]
