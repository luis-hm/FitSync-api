from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Usuario
from apps.workouts.models import CategoriaExercicio, Exercicio, Treino, TreinoTemplate
from apps.workouts.serializers import (
    AplicarTemplateSerializer,
    BulkActionResponseSerializer,
    CategoriaExercicioSerializer,
    ExercicioBulkActionSerializer,
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


PAGE_PARAM = OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY)
SEARCH_PARAM = OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY)
ATIVO_PARAM = OpenApiParameter("ativo", OpenApiTypes.BOOL, OpenApiParameter.QUERY)
ALUNO_ID_PARAM = OpenApiParameter("aluno_id", OpenApiTypes.UUID, OpenApiParameter.QUERY)
STATUS_PARAM = OpenApiParameter("status", OpenApiTypes.STR, OpenApiParameter.QUERY)
ORIGEM_PARAM = OpenApiParameter("origem", OpenApiTypes.STR, OpenApiParameter.QUERY)
GRUPO_MUSCULAR_PARAM = OpenApiParameter("grupo_muscular", OpenApiTypes.STR, OpenApiParameter.QUERY)
CATEGORIA_ID_PARAM = OpenApiParameter("categoria_id", OpenApiTypes.UUID, OpenApiParameter.QUERY)


class CategoriaExercicioViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CategoriaExercicioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CategoriaExercicio.objects.none()

        queryset = CategoriaExercicio.objects.all()
        if self.request.user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.filter(ativo=True)
        else:
            ativo = self.request.query_params.get("ativo")
            if ativo is not None:
                queryset = queryset.filter(ativo=parse_bool(ativo))

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(nome__icontains=search)
        return queryset.order_by("ordem", "nome")

    @extend_schema(tags=["workouts"], parameters=[PAGE_PARAM, SEARCH_PARAM, ATIVO_PARAM])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN])
        serializer.save()

    def perform_update(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN])
        serializer.save()

    @extend_schema(tags=["workouts"], request=None, responses=CategoriaExercicioSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        categoria = self.get_object()
        categoria.ativo = False
        categoria.save(update_fields=["ativo"])
        return Response(self.get_serializer(categoria).data)


class ExercicioViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ExercicioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Exercicio.objects.none()

        user = self.request.user
        queryset = Exercicio.objects.select_related("categoria").all().order_by("grupo_muscular", "nome")

        if user.tipo != Usuario.Tipo.ADMIN:
            queryset = queryset.filter(ativo=True, status=Exercicio.Status.APROVADO)
        else:
            ativo = self.request.query_params.get("ativo")
            if ativo is not None:
                queryset = queryset.filter(ativo=parse_bool(ativo))

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(nome__icontains=search)
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
        origem = self.request.query_params.get("origem")
        if origem:
            queryset = queryset.filter(origem=origem)
        grupo_muscular = self.request.query_params.get("grupo_muscular")
        if grupo_muscular:
            queryset = queryset.filter(grupo_muscular__iexact=grupo_muscular)
        categoria_id = self.request.query_params.get("categoria_id")
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
        return queryset

    @extend_schema(
        tags=["workouts"],
        parameters=[
            PAGE_PARAM,
            SEARCH_PARAM,
            ATIVO_PARAM,
            STATUS_PARAM,
            ORIGEM_PARAM,
            GRUPO_MUSCULAR_PARAM,
            CATEGORIA_ID_PARAM,
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN])
        serializer.save(origem=Exercicio.Origem.MANUAL)

    def perform_update(self, serializer):
        require_role(self.request.user, [Usuario.Tipo.ADMIN])
        serializer.save()

    @extend_schema(tags=["workouts"], request=None, responses=ExercicioSerializer)
    @action(detail=True, methods=["post"])
    def arquivar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        exercicio = self.get_object()
        exercicio.ativo = False
        exercicio.save(update_fields=["ativo"])
        return Response(self.get_serializer(exercicio).data)

    @extend_schema(tags=["workouts"], request=None, responses=ExercicioSerializer)
    @action(detail=True, methods=["post"])
    def aprovar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        exercicio = self.get_object()
        exercicio.status = Exercicio.Status.APROVADO
        exercicio.ativo = True
        exercicio.save(update_fields=["status", "ativo"])
        return Response(self.get_serializer(exercicio).data)

    @extend_schema(tags=["workouts"], request=None, responses=ExercicioSerializer)
    @action(detail=True, methods=["post"])
    def rejeitar(self, request, pk=None):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        exercicio = self.get_object()
        exercicio.status = Exercicio.Status.REJEITADO
        exercicio.ativo = False
        exercicio.save(update_fields=["status", "ativo"])
        return Response(self.get_serializer(exercicio).data)

    @extend_schema(
        tags=["workouts"],
        request=ExercicioBulkActionSerializer,
        responses=BulkActionResponseSerializer,
    )
    @action(detail=False, methods=["post"], url_path="aprovar-lote")
    def aprovar_lote(self, request):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        serializer = ExercicioBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = Exercicio.objects.filter(id__in=serializer.validated_data["ids"]).update(
            status=Exercicio.Status.APROVADO,
            ativo=True,
        )
        return Response({"updated": updated})

    @extend_schema(
        tags=["workouts"],
        request=ExercicioBulkActionSerializer,
        responses=BulkActionResponseSerializer,
    )
    @action(detail=False, methods=["post"], url_path="rejeitar-lote")
    def rejeitar_lote(self, request):
        require_role(request.user, [Usuario.Tipo.ADMIN])
        serializer = ExercicioBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = Exercicio.objects.filter(id__in=serializer.validated_data["ids"]).update(
            status=Exercicio.Status.REJEITADO,
            ativo=False,
        )
        return Response({"updated": updated})


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

    @extend_schema(tags=["workouts"], parameters=[PAGE_PARAM, SEARCH_PARAM, ATIVO_PARAM])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

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

    @extend_schema(tags=["workouts"], parameters=[PAGE_PARAM, ATIVO_PARAM, ALUNO_ID_PARAM])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

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
