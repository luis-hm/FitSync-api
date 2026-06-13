from django.contrib import admin

from apps.core.models import PlatformSettings


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("nome_plataforma", "suporte_email", "cadastro_publico_ativo", "data_atualizacao")
    readonly_fields = ("data_atualizacao",)

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
