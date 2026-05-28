from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.models import Aluno, Usuario
from apps.assessments.models import Avaliacao
from apps.core.serializers import OptionsSerializer
from apps.workouts.models import Treino


def choice_options(choices):
    return [{"value": value, "label": label} for value, label in choices]


@extend_schema(
    tags=["core"],
    responses=inline_serializer(
        name="HealthCheckResponse",
        fields={
            "status": serializers.CharField(),
            "service": serializers.CharField(),
        },
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok", "service": "fitsync-api"})


@extend_schema(
    tags=["core"],
    responses=inline_serializer(
        name="ApiRootResponse",
        fields={
            "service": serializers.CharField(),
            "modules": serializers.DictField(child=serializers.CharField()),
            "health": serializers.CharField(),
            "options": serializers.CharField(),
            "docs": serializers.CharField(),
        },
    ),
)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response(
        {
            "service": "fitsync-api",
            "modules": {
                "auth": "/api/auth/",
                "accounts": "/api/accounts/",
                "workouts": "/api/workouts/",
                "assessments": "/api/assessments/",
            },
            "health": "/api/health/",
            "options": "/api/options/",
            "docs": "/api/docs/",
        }
    )


@extend_schema(tags=["core"], responses=OptionsSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def api_options(request):
    return Response(
        {
            "auth": {
                "tipos_cadastro": choice_options(
                    [
                        (Usuario.Tipo.PERSONAL, Usuario.Tipo.PERSONAL.label),
                        (Usuario.Tipo.ALUNO, Usuario.Tipo.ALUNO.label),
                    ]
                )
            },
            "accounts": {"sexos": choice_options(Aluno.Sexo.choices)},
            "workouts": {"dias_semana": choice_options(Treino.DiaSemana.choices)},
            "assessments": {"metodos": choice_options(Avaliacao.Metodo.choices)},
        }
    )
