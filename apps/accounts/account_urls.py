from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    AdminAlunoDetailAPIView,
    AdminAlunosAPIView,
    AdminDashboardAPIView,
    AdminPersonalDetailAPIView,
    AdminPersonaisAPIView,
    AdminUsuarioViewSet,
    AlunoMeAPIView,
    PersonalDashboardAPIView,
    PersonalAlunoDetailAPIView,
    PersonalAlunosListAPIView,
)


app_name = "account_profiles"

router = DefaultRouter()
router.register("admin/usuarios", AdminUsuarioViewSet, basename="admin-usuarios")

urlpatterns = [
    path("admin/dashboard/", AdminDashboardAPIView.as_view(), name="admin-dashboard"),
    path("admin/personais/", AdminPersonaisAPIView.as_view(), name="admin-personais"),
    path("admin/personais/<uuid:pk>/", AdminPersonalDetailAPIView.as_view(), name="admin-personal-detail"),
    path("admin/alunos/", AdminAlunosAPIView.as_view(), name="admin-alunos"),
    path("admin/alunos/<uuid:pk>/", AdminAlunoDetailAPIView.as_view(), name="admin-aluno-detail"),
    path("personal/dashboard/", PersonalDashboardAPIView.as_view(), name="personal-dashboard"),
    path("personal/alunos/", PersonalAlunosListAPIView.as_view(), name="personal-alunos"),
    path("personal/alunos/<uuid:pk>/", PersonalAlunoDetailAPIView.as_view(), name="personal-aluno-detail"),
    path("aluno/me/", AlunoMeAPIView.as_view(), name="aluno-me"),
    path("", include(router.urls)),
]
