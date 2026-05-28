from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    AdminAlunosAPIView,
    AdminPersonaisAPIView,
    AdminUsuarioViewSet,
    AlunoMeAPIView,
    PersonalAlunoDetailAPIView,
    PersonalAlunosListAPIView,
)


app_name = "account_profiles"

router = DefaultRouter()
router.register("admin/usuarios", AdminUsuarioViewSet, basename="admin-usuarios")

urlpatterns = [
    path("admin/personais/", AdminPersonaisAPIView.as_view(), name="admin-personais"),
    path("admin/alunos/", AdminAlunosAPIView.as_view(), name="admin-alunos"),
    path("personal/alunos/", PersonalAlunosListAPIView.as_view(), name="personal-alunos"),
    path("personal/alunos/<uuid:pk>/", PersonalAlunoDetailAPIView.as_view(), name="personal-aluno-detail"),
    path("aluno/me/", AlunoMeAPIView.as_view(), name="aluno-me"),
    path("", include(router.urls)),
]
