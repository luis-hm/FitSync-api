from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Aluno
from apps.accounts.permissions import IsAdminRole, IsAluno, IsPersonal
from apps.accounts.serializers import (
    AccessTokenResponseSerializer,
    AdminAlunoUpdateSerializer,
    AdminDashboardSerializer,
    AdminPersonalSerializer,
    AdminUsuarioSerializer,
    AlunoSelfSerializer,
    AlunoSerializer,
    AuthRootResponseSerializer,
    DetailResponseSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    MeUpdateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PersonalAlunoCreateSerializer,
    PersonalAlunoUpdateSerializer,
    PersonalDashboardSerializer,
    RefreshSerializer,
    RegisterResponseSerializer,
    RegisterSerializer,
    UsuarioSerializer,
)
from apps.assessments.models import Avaliacao
from apps.core.logging_utils import log_app_event
from apps.core.models import PlatformSettings
from apps.workouts.models import Exercicio, Treino


Usuario = get_user_model()

PAGE_PARAM = OpenApiParameter("page", OpenApiTypes.INT, OpenApiParameter.QUERY)
SEARCH_PARAM = OpenApiParameter("search", OpenApiTypes.STR, OpenApiParameter.QUERY)
TIPO_PARAM = OpenApiParameter("tipo", OpenApiTypes.STR, OpenApiParameter.QUERY)
ATIVO_PARAM = OpenApiParameter("ativo", OpenApiTypes.BOOL, OpenApiParameter.QUERY)
PERSONAL_ID_PARAM = OpenApiParameter("personal_id", OpenApiTypes.UUID, OpenApiParameter.QUERY)


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        str(refresh_token),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def delete_refresh_cookie(response):
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


class AuthRootAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["auth"], responses=AuthRootResponseSerializer)
    def get(self, request):
        return Response(
            {
                "module": "auth",
                "endpoints": {
                    "register": "/api/auth/register/",
                    "login": "/api/auth/login/",
                    "refresh": "/api/auth/refresh/",
                    "logout": "/api/auth/logout/",
                    "me": "/api/auth/me/",
                    "password_reset": "/api/auth/password-reset/",
                    "password_reset_confirm": "/api/auth/password-reset/confirm/",
                    "accounts": "/api/accounts/",
                },
            }
        )


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["auth"],
        request=RegisterSerializer,
        responses={status.HTTP_201_CREATED: RegisterResponseSerializer},
    )
    def post(self, request):
        if not PlatformSettings.get_solo().cadastro_publico_ativo:
            raise PermissionDenied("Cadastro publico desativado.")

        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(serializer.to_representation(data), status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    @extend_schema(
        tags=["auth"],
        request=LoginSerializer,
        responses={status.HTTP_200_OK: LoginResponseSerializer},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "access": str(refresh.access_token),
                "user": UsuarioSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, refresh)
        return response


class RefreshAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"

    @extend_schema(
        tags=["auth"],
        request=RefreshSerializer,
        responses={status.HTTP_200_OK: AccessTokenResponseSerializer},
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        response = Response({"access": serializer.validated_data["access"]})
        if "refresh" in serializer.validated_data:
            set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class LogoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["auth"],
        request=None,
        responses={status.HTTP_200_OK: DetailResponseSerializer},
    )
    def post(self, request):
        refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME) or request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass

        response = Response({"detail": "Logout realizado."}, status=status.HTTP_200_OK)
        delete_refresh_cookie(response)
        log_app_event("logout", request=request, context={"had_refresh_cookie": bool(refresh)})
        return response


class MeAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["auth"], responses=UsuarioSerializer)
    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    @extend_schema(
        tags=["auth"],
        request=MeUpdateSerializer,
        responses=UsuarioSerializer,
    )
    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UsuarioSerializer(request.user).data)


class PasswordResetAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["auth"],
        request=PasswordResetRequestSerializer,
        responses={status.HTTP_200_OK: DetailResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Se o email existir, enviaremos as instrucoes de redefinicao."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["auth"],
        request=PasswordResetConfirmSerializer,
        responses={status.HTTP_200_OK: DetailResponseSerializer},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


def parse_bool(value):
    if value is None:
        return None
    return str(value).lower() in ["1", "true", "sim", "yes"]


def apply_usuario_filters(queryset, request):
    tipo = request.query_params.get("tipo")
    ativo = request.query_params.get("ativo")
    search = request.query_params.get("search")

    if tipo:
        queryset = queryset.filter(tipo=tipo)
    if ativo is not None:
        queryset = queryset.filter(is_active=parse_bool(ativo))
    if search:
        queryset = queryset.filter(Q(nome__icontains=search) | Q(email__icontains=search))
    return queryset


def personal_metrics_queryset(queryset):
    cutoff = timezone.localdate() - timedelta(days=30)
    return queryset.annotate(
        alunos_count=Count("alunos", distinct=True),
        treinos_count=Count("alunos__treinos", distinct=True),
        avaliacoes_count=Count("alunos__avaliacoes", distinct=True),
        avaliacoes_30d_count=Count(
            "alunos__avaliacoes",
            filter=Q(alunos__avaliacoes__data_avaliacao__gte=cutoff),
            distinct=True,
        ),
    )


class AdminUsuarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUsuarioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Usuario.objects.exclude(tipo=Usuario.Tipo.ADMIN).order_by("nome", "email")
        return apply_usuario_filters(queryset, self.request)

    @extend_schema(tags=["accounts"], parameters=[PAGE_PARAM, SEARCH_PARAM, TIPO_PARAM, ATIVO_PARAM])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=["accounts"], request=None, responses=AdminUsuarioSerializer)
    @action(detail=True, methods=["post"])
    def ativar(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)

    @extend_schema(tags=["accounts"], request=None, responses=AdminUsuarioSerializer)
    @action(detail=True, methods=["post"])
    def desativar(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)


def apply_student_filters(queryset, request):
    search = request.query_params.get("search")
    ativo = request.query_params.get("ativo")
    personal_id = request.query_params.get("personal_id")

    if search:
        queryset = queryset.filter(
            Q(usuario__nome__icontains=search)
            | Q(usuario__email__icontains=search)
            | Q(objetivo_principal__icontains=search)
            | Q(personal__nome__icontains=search)
        )
    if ativo is not None:
        queryset = queryset.filter(usuario__is_active=parse_bool(ativo))
    if personal_id:
        queryset = queryset.filter(personal_id=personal_id)
    return queryset


class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(tags=["accounts"], responses=AdminDashboardSerializer)
    def get(self, request):
        non_admin_users = Usuario.objects.exclude(tipo=Usuario.Tipo.ADMIN)
        users_active = non_admin_users.filter(is_active=True).count()
        users_inactive = non_admin_users.filter(is_active=False).count()

        personals = Usuario.objects.filter(tipo=Usuario.Tipo.PERSONAL)
        personals_active = personals.filter(is_active=True).count()
        personals_inactive = personals.filter(is_active=False).count()

        students = Aluno.objects.select_related("usuario")
        students_active = students.filter(usuario__is_active=True).count()
        students_inactive = students.filter(usuario__is_active=False).count()

        exercises = Exercicio.objects.all()
        exercises_active = exercises.filter(ativo=True).count()
        exercises_inactive = exercises.filter(ativo=False).count()

        cutoff = timezone.localdate() - timedelta(days=30)
        return Response(
            {
                "usuarios": {
                    "total": users_active + users_inactive,
                    "ativos": users_active,
                    "inativos": users_inactive,
                },
                "personais": {
                    "total": personals_active + personals_inactive,
                    "ativos": personals_active,
                    "inativos": personals_inactive,
                },
                "alunos": {
                    "total": students_active + students_inactive,
                    "ativos": students_active,
                    "inativos": students_inactive,
                },
                "exercicios": {
                    "total": exercises_active + exercises_inactive,
                    "ativos": exercises_active,
                    "inativos": exercises_inactive,
                },
                "treinos": {
                    "ativos": Treino.objects.filter(ativo=True).count(),
                    "total": Treino.objects.count(),
                },
                "avaliacoes": {
                    "ativas": Avaliacao.objects.filter(ativo=True).count(),
                    "recentes_30d": Avaliacao.objects.filter(
                        ativo=True,
                        data_avaliacao__gte=cutoff,
                    ).count(),
                },
            }
        )


class PersonalDashboardAPIView(APIView):
    permission_classes = [IsPersonal]

    @extend_schema(tags=["accounts"], responses=PersonalDashboardSerializer)
    def get(self, request):
        alunos = Aluno.objects.select_related("usuario").filter(personal=request.user)
        alunos_ativos = alunos.filter(usuario__is_active=True)
        treinos = Treino.objects.filter(aluno__personal=request.user)
        avaliacoes = Avaliacao.objects.filter(aluno__personal=request.user)
        cutoff = timezone.localdate() - timedelta(days=30)

        ranking = []
        for aluno in alunos_ativos:
            historico = avaliacoes.filter(
                aluno=aluno,
                ativo=True,
                percentual_gordura__isnull=False,
            ).order_by("data_avaliacao", "data_criacao")
            first = historico.first()
            last = historico.last()
            if not first or not last or first.id == last.id:
                continue
            ranking.append(
                {
                    "aluno_id": str(aluno.id),
                    "aluno_nome": aluno.usuario.nome,
                    "percentual_inicial": first.percentual_gordura,
                    "percentual_final": last.percentual_gordura,
                    "variacao_percentual_gordura": last.percentual_gordura
                    - first.percentual_gordura,
                }
            )

        ranking.sort(key=lambda item: item["variacao_percentual_gordura"])
        return Response(
            {
                "alunos": {
                    "total": alunos.count(),
                    "ativos": alunos_ativos.count(),
                    "inativos": alunos.filter(usuario__is_active=False).count(),
                },
                "treinos": {
                    "total": treinos.count(),
                    "ativos": treinos.filter(ativo=True).count(),
                },
                "avaliacoes": {
                    "total": avaliacoes.count(),
                    "ativas": avaliacoes.filter(ativo=True).count(),
                    "recentes_30d": avaliacoes.filter(
                        ativo=True,
                        data_avaliacao__gte=cutoff,
                    ).count(),
                },
                "ranking": ranking[:5],
            }
        )


class AdminPersonaisAPIView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminPersonalSerializer

    def get_queryset(self):
        queryset = Usuario.objects.filter(tipo=Usuario.Tipo.PERSONAL).select_related(
            "personal_profile"
        )
        queryset = apply_usuario_filters(queryset, self.request)
        return personal_metrics_queryset(queryset).order_by("nome", "email")

    @extend_schema(tags=["accounts"], parameters=[PAGE_PARAM, SEARCH_PARAM, ATIVO_PARAM])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminPersonalDetailAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminPersonalSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Usuario.objects.filter(tipo=Usuario.Tipo.PERSONAL).select_related(
            "personal_profile"
        )
        return personal_metrics_queryset(queryset)


class AdminAlunosAPIView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminAlunoUpdateSerializer

    def get_queryset(self):
        queryset = Aluno.objects.select_related("usuario", "personal").order_by(
            "usuario__nome",
            "usuario__email",
        )
        return apply_student_filters(queryset, self.request)

    @extend_schema(
        tags=["accounts"],
        parameters=[PAGE_PARAM, SEARCH_PARAM, ATIVO_PARAM, PERSONAL_ID_PARAM],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminAlunoDetailAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminAlunoUpdateSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Aluno.objects.select_related("usuario", "personal")


class PersonalAlunosListAPIView(ListCreateAPIView):
    permission_classes = [IsPersonal]
    serializer_class = AlunoSerializer

    def get_queryset(self):
        queryset = Aluno.objects.select_related("usuario", "personal").filter(
            personal=self.request.user,
            usuario__is_active=True,
        )
        queryset = apply_student_filters(queryset, self.request)
        return queryset.order_by("usuario__nome", "usuario__email")

    @extend_schema(tags=["accounts"], parameters=[PAGE_PARAM, SEARCH_PARAM])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["accounts"],
        request=PersonalAlunoCreateSerializer,
        responses={status.HTTP_201_CREATED: AlunoSerializer},
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PersonalAlunoCreateSerializer
        return AlunoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        aluno = serializer.save()
        return Response(AlunoSerializer(aluno).data, status=status.HTTP_201_CREATED)


class PersonalAlunoDetailAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsPersonal]
    serializer_class = PersonalAlunoUpdateSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Aluno.objects.select_related("usuario", "personal").filter(
            personal=self.request.user,
            usuario__is_active=True,
        )

    def get_serializer_class(self):
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return AlunoSerializer
        return PersonalAlunoUpdateSerializer


class AlunoMeAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAluno]
    serializer_class = AlunoSelfSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        try:
            return self.request.user.aluno
        except Aluno.DoesNotExist as exc:
            raise NotFound("Perfil de aluno nao encontrado.") from exc
