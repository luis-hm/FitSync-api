from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Aluno, Usuario
from apps.assessments.application.calculadora import (
    classificar_iac,
    classificar_imc,
    classificar_percentual_gordura,
    classificar_rcq,
    idade_em_anos,
    status_periodicidade,
)
from apps.assessments.models import Anamnese, Avaliacao
from apps.assessments.serializers import (
    AlunoEvolucaoResponseSerializer,
    AnamneseSerializer,
    AvaliacaoResumoResponseSerializer,
    AvaliacaoSerializer,
    CIRCUNFERENCIAS_FIELDS,
    PersonalRankingResponseSerializer,
)


PAGE_PARAM = OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY)
ATIVO_PARAM = OpenApiParameter("ativo", OpenApiTypes.BOOL, OpenApiParameter.QUERY)
ALUNO_ID_PARAM = OpenApiParameter("aluno_id", OpenApiTypes.UUID, OpenApiParameter.QUERY)
METODO_PARAM = OpenApiParameter("metodo", OpenApiTypes.STR, OpenApiParameter.QUERY)
DATA_INICIO_PARAM = OpenApiParameter("data_inicio", OpenApiTypes.DATE, OpenApiParameter.QUERY)
DATA_FIM_PARAM = OpenApiParameter("data_fim", OpenApiTypes.DATE, OpenApiParameter.QUERY)


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


def related_exists(instance, attr):
    try:
        getattr(instance, attr)
    except ObjectDoesNotExist:
        return False
    return True


def assessment_metodo_calculo(avaliacao):
    has_dobras = related_exists(avaliacao, "dobras")
    has_bio = related_exists(avaliacao, "bioimpedancia")
    has_circ = related_exists(avaliacao, "circunferencias")
    if sum([has_dobras, has_bio, has_circ]) > 1:
        return "COMBINADO"
    if has_dobras:
        return "JACKSON_POLLOCK_7_SIRI"
    if has_bio:
        return "BIOIMPEDANCIA"
    if has_circ:
        return "CIRCUNFERENCIAS"
    return None


def assessment_classificacoes(avaliacao):
    idade = idade_em_anos(avaliacao.aluno.data_nascimento, avaliacao.data_avaliacao)
    return {
        "classificacao_imc": classificar_imc(avaliacao.imc),
        "classificacao_iac": (
            classificar_iac(avaliacao.iac, avaliacao.aluno.sexo, idade) if avaliacao.iac else None
        ),
        "classificacao_rcq": (
            classificar_rcq(avaliacao.rcq, avaliacao.aluno.sexo) if avaliacao.rcq else None
        ),
        "classificacao_percentual_gordura": (
            classificar_percentual_gordura(
                avaliacao.percentual_gordura,
                avaliacao.aluno.sexo,
                idade,
            )
            if avaliacao.percentual_gordura
            else None
        ),
    }


def empty_circunferencias():
    return {field: None for field in CIRCUNFERENCIAS_FIELDS}


def circunferencias_payload(avaliacao):
    try:
        circ = avaliacao.circunferencias
    except ObjectDoesNotExist:
        return empty_circunferencias()
    return {field: getattr(circ, field) for field in CIRCUNFERENCIAS_FIELDS}


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

    @extend_schema(
        tags=["assessments"],
        parameters=[
            PAGE_PARAM,
            ATIVO_PARAM,
            ALUNO_ID_PARAM,
            METODO_PARAM,
            DATA_INICIO_PARAM,
            DATA_FIM_PARAM,
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal registra avaliacoes.")
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal corrige avaliacoes.")
        return super().partial_update(request, *args, **kwargs)

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


class AnamneseViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AnamneseSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Anamnese.objects.none()

        user = self.request.user
        queryset = Anamnese.objects.select_related("aluno__usuario", "aluno__personal")
        if user.tipo == Usuario.Tipo.PERSONAL:
            queryset = queryset.filter(aluno__personal=user)
        elif user.tipo == Usuario.Tipo.ALUNO:
            queryset = queryset.filter(aluno__usuario=user)
        elif user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.none()

        aluno_id = self.request.query_params.get("aluno_id")
        if aluno_id:
            queryset = queryset.filter(aluno_id=aluno_id)
        return queryset.order_by("-ativo", "-data_atualizacao")

    @extend_schema(tags=["assessments"], parameters=[PAGE_PARAM, ALUNO_ID_PARAM])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal registra anamnese.")
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal corrige anamnese.")
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        if self.request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal registra anamnese.")
        serializer.save()

    def perform_update(self, serializer):
        if self.request.user.tipo != Usuario.Tipo.PERSONAL:
            raise PermissionDenied("Somente personal corrige anamnese.")
        serializer.save()


def serialize_evolution(avaliacoes):
    previous = None
    result = []
    numeric_fields = ["peso_kg", "imc", "iac", "percentual_gordura", "massa_gorda_kg", "massa_magra_kg", "rcq"]

    for avaliacao in avaliacoes:
        current = {
            "id": str(avaliacao.id),
            "data_avaliacao": avaliacao.data_avaliacao,
            "data_proxima_avaliacao": avaliacao.data_proxima_avaliacao,
            "metodo": avaliacao.metodo,
            "metodo_calculo": assessment_metodo_calculo(avaliacao),
            "peso_kg": avaliacao.peso_kg,
            "imc": avaliacao.imc,
            "iac": avaliacao.iac,
            "percentual_gordura": avaliacao.percentual_gordura,
            "massa_gorda_kg": avaliacao.massa_gorda_kg,
            "massa_magra_kg": avaliacao.massa_magra_kg,
            "rcq": avaliacao.rcq,
            "status_periodicidade": status_periodicidade(
                avaliacao.data_proxima_avaliacao,
                timezone.localdate(),
            ),
            "circunferencias": circunferencias_payload(avaliacao),
            "deltas": {},
        }
        current.update(assessment_classificacoes(avaliacao))

        current["deltas"] = {
            field: (
                current[field] - previous[field]
                if previous and current[field] is not None and previous[field] is not None
                else None
            )
            for field in numeric_fields
        }
        current["deltas"]["circunferencias"] = {
            field: (
                current["circunferencias"][field] - previous["circunferencias"][field]
                if previous
                and current["circunferencias"][field] is not None
                and previous["circunferencias"][field] is not None
                else None
            )
            for field in CIRCUNFERENCIAS_FIELDS
        }

        result.append(current)
        previous = current
    return result


def get_aluno_or_404(pk):
    try:
        return Aluno.objects.select_related("usuario", "personal").get(pk=pk)
    except Aluno.DoesNotExist as exc:
        raise NotFound("Aluno nao encontrado.") from exc


def get_active_assessments(aluno):
    return Avaliacao.objects.filter(aluno=aluno, ativo=True).select_related(
        "aluno__usuario",
        "aluno__personal",
        "personal",
    ).prefetch_related("dobras", "bioimpedancia", "circunferencias")


def latest_assessment(aluno):
    return get_active_assessments(aluno).order_by("-data_avaliacao", "-data_criacao").first()


class AlunoEvolucaoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["assessments"],
        parameters=[DATA_INICIO_PARAM, DATA_FIM_PARAM],
        responses=AlunoEvolucaoResponseSerializer,
    )
    def get(self, request, pk):
        aluno = get_aluno_or_404(pk)
        ensure_can_access_aluno(request.user, aluno)
        avaliacoes = filter_dates(get_active_assessments(aluno), request).order_by(
            "data_avaliacao",
            "data_criacao",
        )

        return Response(
            {
                "aluno_id": str(aluno.id),
                "aluno_nome": aluno.usuario.nome,
                "results": serialize_evolution(avaliacoes),
            }
        )


class AlunoMeEvolucaoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["assessments"],
        parameters=[DATA_INICIO_PARAM, DATA_FIM_PARAM],
        responses=AlunoEvolucaoResponseSerializer,
    )
    def get(self, request):
        if request.user.tipo != Usuario.Tipo.ALUNO:
            raise PermissionDenied("Somente aluno acessa a propria evolucao por esta rota.")

        try:
            aluno = request.user.aluno
        except Aluno.DoesNotExist as exc:
            raise NotFound("Perfil de aluno nao encontrado.") from exc

        avaliacoes = filter_dates(get_active_assessments(aluno), request).order_by(
            "data_avaliacao",
            "data_criacao",
        )

        return Response(
            {
                "aluno_id": str(aluno.id),
                "aluno_nome": aluno.usuario.nome,
                "results": serialize_evolution(avaliacoes),
            }
        )


class AlunoResumoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["assessments"], responses=AvaliacaoResumoResponseSerializer)
    def get(self, request, pk):
        aluno = get_aluno_or_404(pk)
        ensure_can_access_aluno(request.user, aluno)
        avaliacao = latest_assessment(aluno)
        return Response(
            {
                "aluno_id": str(aluno.id),
                "aluno_nome": aluno.usuario.nome,
                "ultima_avaliacao": (
                    AvaliacaoSerializer(avaliacao, context={"request": request}).data
                    if avaliacao
                    else None
                ),
            }
        )


class AlunoMeResumoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["assessments"], responses=AvaliacaoResumoResponseSerializer)
    def get(self, request):
        if request.user.tipo != Usuario.Tipo.ALUNO:
            raise PermissionDenied("Somente aluno acessa o proprio resumo por esta rota.")

        try:
            aluno = request.user.aluno
        except Aluno.DoesNotExist as exc:
            raise NotFound("Perfil de aluno nao encontrado.") from exc

        avaliacao = latest_assessment(aluno)
        return Response(
            {
                "aluno_id": str(aluno.id),
                "aluno_nome": aluno.usuario.nome,
                "ultima_avaliacao": (
                    AvaliacaoSerializer(avaliacao, context={"request": request}).data
                    if avaliacao
                    else None
                ),
            }
        )


def get_active_anamnese(aluno):
    return Anamnese.objects.select_related("aluno__usuario", "aluno__personal").filter(
        aluno=aluno,
        ativo=True,
    ).first()


class AlunoAnamneseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["assessments"], responses=AnamneseSerializer)
    def get(self, request, pk):
        aluno = get_aluno_or_404(pk)
        ensure_can_access_aluno(request.user, aluno)
        anamnese = get_active_anamnese(aluno)
        if not anamnese:
            raise NotFound("Anamnese nao encontrada.")
        return Response(AnamneseSerializer(anamnese, context={"request": request}).data)

    @extend_schema(tags=["assessments"], request=AnamneseSerializer, responses=AnamneseSerializer)
    def patch(self, request, pk):
        aluno = get_aluno_or_404(pk)
        if request.user.tipo != Usuario.Tipo.PERSONAL or aluno.personal_id != request.user.id:
            raise PermissionDenied("Somente personal edita anamnese dos proprios alunos.")
        anamnese = get_active_anamnese(aluno)
        data = request.data.copy()
        data["aluno_id"] = str(aluno.id)
        serializer = AnamneseSerializer(
            anamnese,
            data=data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class AlunoMeAnamneseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["assessments"], responses=AnamneseSerializer)
    def get(self, request):
        if request.user.tipo != Usuario.Tipo.ALUNO:
            raise PermissionDenied("Somente aluno acessa a propria anamnese por esta rota.")
        try:
            aluno = request.user.aluno
        except Aluno.DoesNotExist as exc:
            raise NotFound("Perfil de aluno nao encontrado.") from exc
        anamnese = get_active_anamnese(aluno)
        if not anamnese:
            raise NotFound("Anamnese nao encontrada.")
        return Response(AnamneseSerializer(anamnese, context={"request": request}).data)

    @extend_schema(tags=["assessments"], request=AnamneseSerializer, responses=AnamneseSerializer)
    def patch(self, request):
        raise PermissionDenied("Aluno nao edita anamnese nesta fase.")


class PersonalRankingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["assessments"],
        parameters=[DATA_INICIO_PARAM, DATA_FIM_PARAM],
        responses=PersonalRankingResponseSerializer,
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
