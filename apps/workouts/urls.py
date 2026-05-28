from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.workouts.views import ExercicioViewSet, TreinoTemplateViewSet, TreinoViewSet


app_name = "workouts"

router = DefaultRouter()
router.register("exercicios", ExercicioViewSet, basename="exercicios")
router.register("templates", TreinoTemplateViewSet, basename="templates")
router.register("treinos", TreinoViewSet, basename="treinos")

urlpatterns = [
    path("", include(router.urls)),
]
