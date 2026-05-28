from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Aluno
from apps.accounts.permissions import IsAdminRole, IsAluno, IsPersonal
from apps.accounts.serializers import (
    AdminUsuarioSerializer,
    AlunoSelfSerializer,
    AlunoSerializer,
    AccessTokenResponseSerializer,
    AuthRootResponseSerializer,
    DetailResponseSerializer,
    LoginSerializer,
    LoginResponseSerializer,
    MeUpdateSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterResponseSerializer,
    RefreshSerializer,
    RegisterSerializer,
    UsuarioSerializer,
)
from apps.core.logging_utils import log_app_event


Usuario = get_user_model()


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


def apply_usuario_filters(queryset, request):
    tipo = request.query_params.get("tipo")
    ativo = request.query_params.get("ativo")
    search = request.query_params.get("search")

    if tipo:
        queryset = queryset.filter(tipo=tipo)
    if ativo is not None:
        queryset = queryset.filter(is_active=ativo.lower() in ["1", "true", "sim"])
    if search:
        queryset = queryset.filter(Q(nome__icontains=search) | Q(email__icontains=search))
    return queryset


class AdminUsuarioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUsuarioSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Usuario.objects.exclude(tipo=Usuario.Tipo.ADMIN).order_by("nome", "email")
        return apply_usuario_filters(queryset, self.request)

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


def apply_student_search(queryset, search):
    if not search:
        return queryset
    return queryset.filter(
        Q(usuario__nome__icontains=search)
        | Q(usuario__email__icontains=search)
        | Q(objetivo_principal__icontains=search)
    )


class AdminPersonaisAPIView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = UsuarioSerializer

    def get_queryset(self):
        return Usuario.objects.filter(tipo=Usuario.Tipo.PERSONAL).order_by("nome", "email")


class AdminAlunosAPIView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AlunoSerializer

    def get_queryset(self):
        queryset = Aluno.objects.select_related("usuario", "personal").order_by(
            "usuario__nome",
            "usuario__email",
        )
        return apply_student_search(queryset, self.request.query_params.get("search"))


class PersonalAlunosListAPIView(ListAPIView):
    permission_classes = [IsPersonal]
    serializer_class = AlunoSerializer

    def get_queryset(self):
        queryset = Aluno.objects.select_related("usuario", "personal").filter(
            personal=self.request.user,
            usuario__is_active=True,
        )
        queryset = apply_student_search(queryset, self.request.query_params.get("search"))
        return queryset.order_by("usuario__nome", "usuario__email")


class PersonalAlunoDetailAPIView(RetrieveAPIView):
    permission_classes = [IsPersonal]
    serializer_class = AlunoSerializer

    def get_queryset(self):
        return Aluno.objects.select_related("usuario", "personal").filter(
            personal=self.request.user,
            usuario__is_active=True,
        )


class AlunoMeAPIView(RetrieveUpdateAPIView):
    permission_classes = [IsAluno]
    serializer_class = AlunoSelfSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        try:
            return self.request.user.aluno
        except Aluno.DoesNotExist as exc:
            raise NotFound("Perfil de aluno nao encontrado.") from exc
