from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Aluno, Usuario
from apps.assessments.models import Avaliacao
from apps.assessments.serializers import AvaliacaoSerializer


def parse_bool(value):
    if value is None:
        return None
    return str(value).lower() in ["1", "true", "sim", "yes"]


def filter_dates(queryset, request):
    data_inicio = request.query_params.get("data_inicio")
    data_fim = request.query_params.get("data_fim")
    if data_inicio:
        queryset = queryset.filter(data_avaliacao__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_avaliacao__lte=data_fim)
    return queryset


def ensure_can_access_aluno(user, aluno):
    if user.tipo == Usuario.Tipo.ADMIN:
        return
    if user.tipo == Usuario.Tipo.PERSONAL and aluno.personal_id == user.id:
        return
    if user.tipo == Usuario.Tipo.ALUNO and aluno.usuario_id == user.id:
        return
    raise PermissionDenied("Usuario nao tem acesso a este aluno.")


class AvaliacaoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvaliacaoSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Avaliacao.objects.none()

        user = self.request.user
        queryset = Avaliacao.objects.select_related(
            "aluno__usuario",
            "aluno__personal",
            "personal",
        ).prefetch_related("dobras", "bioimpedancia", "circunferencias")

        if user.tipo == Usuario.Tipo.PERSONAL:
            queryset = queryset.filter(aluno__personal=user)
        elif user.tipo == Usuario.Tipo.ALUNO:
            queryset = queryset.filter(aluno__usuario=user)
        elif user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.none()

        ativo = self.request.query_params.get("ativo")
        queryset = queryset.filter(ativo=True if ativo is None else parse_bool(ativo))

        aluno_id = self.request.query_params.get("aluno_id")
        metodo = self.request.query_params.get("metodo")
        if aluno_id:
            queryset = queryset.filter(aluno_id=aluno_id)
        if metodo:
            queryset = queryset.filter(metodo=metodo)
        return filter_dates(queryset, self.request).order_by("-data_avaliacao", "-data_criacao")

    def perform_create(self, serializer):
        if self.request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal registra avaliacoes.")
        serializer.save()

    def perform_update(self, serializer):
        if self.request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal corrige avaliacoes.")
        serializer.save()

    @extend_schema(tags=["assessments"], request=None, responses=AvaliacaoSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal arquiva avaliacoes.")
        avaliacao = self.get_object()
        avaliacao.ativo = False
        avaliacao.save(update_fields=["ativo"])
        return Response(self.get_serializer(avaliacao).data)


def serialize_evolution(avaliacoes):
    previous = None
    result = []
    for avaliacao in avaliacoes:
        circ = getattr(avaliacao, "circunferencias", None)
        current = {
            "id": str(avaliacao.id),
            "data_avaliacao": avaliacao.data_avaliacao,
            "metodo": avaliacao.metodo,
            "peso_kg": avaliacao.peso_kg,
            "percentual_gordura": avaliacao.percentual_gordura,
            "massa_gorda_kg": avaliacao.massa_gorda_kg,
            "massa_magra_kg": avaliacao.massa_magra_kg,
            "rcq": avaliacao.rcq,
            "circunferencias": {
                "cintura_cm": circ.cintura_cm if circ else None,
                "abdome_cm": circ.abdome_cm if circ else None,
                "quadril_cm": circ.quadril_cm if circ else None,
                "coxa_cm": circ.coxa_cm if circ else None,
                "braco_contraido_cm": circ.braco_contraido_cm if circ else None,
            },
            "deltas": {},
        }

        if previous:
            for field in ["peso_kg", "percentual_gordura", "massa_gorda_kg", "massa_magra_kg", "rcq"]:
                current_value = current[field]
                previous_value = previous[field]
                current["deltas"][field] = (
                    current_value - previous_value
                    if current_value is not None and previous_value is not None
                    else None
                )
        else:
            current["deltas"] = {
                "peso_kg": None,
                "percentual_gordura": None,
                "massa_gorda_kg": None,
                "massa_magra_kg": None,
                "rcq": None,
            }

        result.append(current)
        previous = current
    return result


class AlunoEvolucaoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["assessments"],
        parameters=[
            OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY),
        ],
        responses=inline_serializer(
            name="AlunoEvolucaoResponse",
            fields={
                "aluno_id": serializers.UUIDField(),
                "aluno_nome": serializers.CharField(),
                "results": serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request, pk):
        try:
            aluno = Aluno.objects.select_related("usuario", "personal").get(pk=pk)
        except Aluno.DoesNotExist as exc:
            raise NotFound("Aluno nao encontrado.") from exc

        ensure_can_access_aluno(request.user, aluno)
        avaliacoes = Avaliacao.objects.filter(aluno=aluno, ativo=True).select_related(
            "aluno__usuario",
            "personal",
        ).prefetch_related("circunferencias")
        avaliacoes = filter_dates(avaliacoes, request).order_by("data_avaliacao", "data_criacao")

        return Response(
            {
                "aluno_id": str(aluno.id),
                "aluno_nome": aluno.usuario.nome,
                "results": serialize_evolution(avaliacoes),
            }
        )


class PersonalRankingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["assessments"],
        parameters=[
            OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY),
            OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY),
        ],
        responses=inline_serializer(
            name="PersonalRankingResponse",
            fields={"results": serializers.ListField(child=serializers.DictField())},
        ),
    )
    def get(self, request):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal acessa ranking.")

        alunos = Aluno.objects.select_related("usuario").filter(personal=request.user)
        ranking = []
        for aluno in alunos:
            avaliacoes = Avaliacao.objects.filter(
                aluno=aluno,
                ativo=True,
                percentual_gordura__isnull=False,
            )
            avaliacoes = filter_dates(avaliacoes, request).order_by("data_avaliacao", "data_criacao")
            first = avaliacoes.first()
            last = avaliacoes.last()
            if not first or not last or first.id == last.id:
                continue
            ranking.append(
                {
                    "aluno_id": str(aluno.id),
                    "aluno_nome": aluno.usuario.nome,
                    "percentual_inicial": first.percentual_gordura,
                    "percentual_final": last.percentual_gordura,
                    "variacao_percentual_gordura": last.percentual_gordura - first.percentual_gordura,
                }
            )

        ranking.sort(key=lambda item: item["variacao_percentual_gordura"])
        return Response({"results": ranking})
