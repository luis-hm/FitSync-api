import logging
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.core.models import PlatformSettings


Usuario = get_user_model()


class LoggingConfigurationTests(TestCase):
    def test_logging_configuration_exists(self):
        self.assertIsInstance(settings.LOGGING, dict)

    def test_log_format_includes_fitsync_prefix(self):
        formatter_config = settings.LOGGING["formatters"]["observability"]
        self.assertIn("[FITSYNC]", formatter_config["format"])

    def test_application_loggers_are_configured(self):
        loggers = settings.LOGGING["loggers"]
        self.assertIn("apps", loggers)
        self.assertIn("apps.security", loggers)
        self.assertIn("apps.performance", loggers)


class LoggingBehaviorTests(APITestCase):
    def tearDown(self):
        cache.clear()
        super().tearDown()

    def capture_logger(self, logger_name, level):
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger(logger_name)
        previous_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(level)
        return logger, handler, log_capture, previous_level

    def release_logger(self, logger, handler, previous_level):
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    def test_failed_login_is_logged_without_password(self):
        Usuario.objects.create_user(
            nome="Personal Teste",
            email="personal.logging@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        logger, handler, log_capture, previous_level = self.capture_logger(
            "apps.security",
            logging.WARNING,
        )

        response = self.client.post(
            "/api/auth/login/",
            {"email": "personal.logging@example.com", "password": "WrongPass123!"},
            format="json",
        )

        self.release_logger(logger, handler, previous_level)
        log_contents = log_capture.getvalue()

        self.assertEqual(response.status_code, 400)
        self.assertIn("login_failed", log_contents)
        self.assertNotIn("WrongPass123!", log_contents)

    def test_unauthorized_request_is_logged(self):
        logger, handler, log_capture, previous_level = self.capture_logger(
            "apps.security",
            logging.WARNING,
        )

        response = self.client.get("/api/auth/me/")

        self.release_logger(logger, handler, previous_level)
        log_contents = log_capture.getvalue()

        self.assertEqual(response.status_code, 401)
        self.assertIn("StatusCode:401", log_contents)
        self.assertIn("Path:/api/auth/me/", log_contents)

    def test_api_health_request_logs_performance(self):
        logger, handler, log_capture, previous_level = self.capture_logger(
            "apps.performance",
            logging.INFO,
        )

        response = self.client.get("/api/health/")

        self.release_logger(logger, handler, previous_level)
        log_contents = log_capture.getvalue()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Method:GET", log_contents)
        self.assertIn("Path:/api/health/", log_contents)
        self.assertIn("Duration:", log_contents)


class DocumentationAPITests(APITestCase):
    def test_schema_docs_and_redoc_are_available(self):
        for path in ["/api/schema/", "/api/docs/", "/api/redoc/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_options_endpoint_returns_frontend_enums(self):
        response = self.client.get("/api/options/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["auth"]["tipos_cadastro"],
            [
                {"value": "PERSONAL", "label": "Personal"},
                {"value": "ALUNO", "label": "Aluno"},
            ],
        )
        self.assertEqual(
            response.data["accounts"]["sexos"],
            [
                {"value": "M", "label": "Masculino"},
                {"value": "F", "label": "Feminino"},
            ],
        )
        self.assertIn(
            {"value": "SEGUNDA", "label": "Segunda-feira"},
            response.data["workouts"]["dias_semana"],
        )
        self.assertIn(
            {"value": "DOBRAS", "label": "Dobras"},
            response.data["assessments"]["metodos"],
        )

    def test_admin_can_read_and_update_platform_settings(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.settings@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=admin)

        get_response = self.client.get("/api/settings/")
        patch_response = self.client.patch(
            "/api/settings/",
            {
                "nome_plataforma": "FitSync Admin",
                "suporte_email": "suporte@fitsync.local",
                "cadastro_publico_ativo": False,
            },
            format="json",
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["nome_plataforma"], "FitSync Admin")
        self.assertFalse(PlatformSettings.get_solo().cadastro_publico_ativo)

    def test_schema_generation_is_strictly_valid(self):
        output = StringIO()
        call_command("spectacular", fail_on_warn=True, stdout=output)

        self.assertIn("openapi:", output.getvalue())
