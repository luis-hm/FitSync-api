from django.urls import path

from apps.core.views import api_options, api_root, health_check, platform_settings


app_name = "core"

urlpatterns = [
    path("", api_root, name="api-root"),
    path("health/", health_check, name="health"),
    path("options/", api_options, name="api-options"),
    path("settings/", platform_settings, name="platform-settings"),
]
