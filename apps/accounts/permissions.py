from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.models import Usuario


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.tipo == Usuario.Tipo.ADMIN
        )


class IsPersonal(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.tipo == Usuario.Tipo.PERSONAL
        )


class IsAluno(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.tipo == Usuario.Tipo.ALUNO
        )


class IsPersonalOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.tipo == Usuario.Tipo.PERSONAL
        )
