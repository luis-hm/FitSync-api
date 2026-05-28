from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Usuario
from apps.workouts.models import Exercicio, Treino, TreinoTemplate
from apps.workouts.serializers import (
    AplicarTemplateSerializer,
    ExercicioSerializer,
    TreinoSerializer,
    TreinoTemplateSerializer,
)


def parse_bool(value):
    if value is None:
        return None
    return str(value).lower() in ["1", "true", "sim", "yes"]


def filter_ativo(queryset, request):
    ativo = request.query_params.get("ativo")
    if ativo is None:
        return queryset.filter(ativo=True)
    return queryset.filter(ativo=parse_bool(ativo))


def require_role(user, allowed):
    if not user or not user.is_authenticated or user.tipo not in allowed:
        raise PermissionDenied("Usuario nao tem permissao para esta acao.")


class ExercicioViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExercicioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Exercicio.objects.none()

        queryset = Exercicio.objects.all().order_by("grupo_muscular", "nome")
        queryset = filter_ativo(queryset, self.request)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(nome__icontains=search)
        return queryset

    def perform_create(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN, Usuario.Tipo.PERSONAL])
        serializer.save()

    def perform_update(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN, Usuario.Tipo.PERSONAL])
        serializer.save()

    @extend_schema(tags=["workouts"], request=None, responses=ExercicioSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.ADMIN, Usuario.Tipo.PERSONAL])
        exercicio = self.get_object()
        exercicio.ativo = False
        exercicio.save(update_fields=["ativo"])
        return Response(self.get_serializer(exercicio).data)


class TreinoTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TreinoTemplateSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TreinoTemplate.objects.none()

        user = self.request.user
        queryset = TreinoTemplate.objects.select_related("personal").prefetch_related(
            "itens__exercicio"
        )

        if user.tipo == Usuario.Tipo.PERSONAL:
            queryset = queryset.filter(personal=user)
        elif user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.none()

        queryset = filter_ativo(queryset, self.request)
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(titulo__icontains=search)
        return queryset.order_by("titulo")

    def perform_create(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.PERSONAL])
        serializer.save()

    def perform_update(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.PERSONAL])
        serializer.save()

    @extend_schema(tags=["workouts"], request=None, responses=TreinoTemplateSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.PERSONAL])
        template = self.get_object()
        template.ativo = False
        template.save(update_fields=["ativo"])
        return Response(self.get_serializer(template).data)

    @extend_schema(
        tags=["workouts"],
        request=AplicarTemplateSerializer,
        responses={status.HTTP_201_CREATED: TreinoSerializer},
    )
    @action(detail=True, methods=["post"])
    def aplicar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.PERSONAL])
        template = self.get_object()
        serializer = AplicarTemplateSerializer(
            data=request.data,
            context={"template": template},
        )
        serializer.is_valid(raise_exception=True)
        treino = template.aplicar_para_aluno(**serializer.validated_data)
        return Response(TreinoSerializer(treino, context={"request": request}).data, status=status.HTTP_201_CREATED)


class TreinoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TreinoSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Treino.objects.none()

        user = self.request.user
        queryset = Treino.objects.select_related(
            "aluno__usuario",
            "aluno__personal",
            "template_origem",
        ).prefetch_related("itens__exercicio")

        if user.tipo == Usuario.Tipo.PERSONAL:
            queryset = queryset.filter(aluno__personal=user)
        elif user.tipo == Usuario.Tipo.ALUNO:
            queryset = queryset.filter(aluno__usuario=user)
        elif user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.none()

        aluno_id = self.request.query_params.get("aluno_id")
        if aluno_id:
            queryset = queryset.filter(aluno_id=aluno_id)

        queryset = filter_ativo(queryset, self.request)
        return queryset.order_by("-ativo", "data_inicio", "titulo")

    def perform_create(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.PERSONAL])
        serializer.save()

    def perform_update(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.PERSONAL])
        serializer.save()

    @extend_schema(tags=["workouts"], request=None, responses=TreinoSerializer)
    @action(detail=True, methods=["post"])
    def ativar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.PERSONAL])
        treino = self.get_object()
        treino.ativo = True
        treino.save(update_fields=["ativo"])
        return Response(self.get_serializer(treino).data)

    @extend_schema(tags=["workouts"], request=None, responses=TreinoSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.PERSONAL])
        treino = self.get_object()
        treino.ativo = False
        treino.save(update_fields=["ativo"])
        return Response(self.get_serializer(treino).data)
