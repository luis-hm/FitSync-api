from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Aluno, PersonalProfile
from apps.core.models import PlatformSettings


Usuario = get_user_model()


class AccountsAuthAPITests(APITestCase):
    def tearDown(self):
        cache.clear()
        super().tearDown()

    def create_personal(self, email="personal@example.com", password="StrongPass123!"):
        return Usuario.objects.create_user(
            nome="Personal Teste",
            email=email,
            password=password,
            tipo=Usuario.Tipo.PERSONAL,
        )

    def create_student(self, personal, email="aluno@example.com", password="StrongPass123!"):
        user = Usuario.objects.create_user(
            nome="Aluno Teste",
            email=email,
            password=password,
            tipo=Usuario.Tipo.ALUNO,
        )
        return Aluno.objects.create(
            usuario=user,
            personal=personal,
            data_nascimento="2000-01-01",
            sexo=Aluno.Sexo.MASCULINO,
        )

    def test_manager_creates_superuser(self):
        user = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin@example.com",
            password="StrongPass123!",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.tipo, Usuario.Tipo.ADMIN)
        self.assertFalse(user.is_personal)

    def test_register_personal(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "nome": "Personal Novo",
                "email": "personal.novo@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "tipo": Usuario.Tipo.PERSONAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["email"], "personal.novo@example.com")
        self.assertEqual(response.data["user"]["tipo"], Usuario.Tipo.PERSONAL)
        self.assertIsNone(response.data["aluno"])

    def test_register_does_not_allow_admin(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "nome": "Admin Publico",
                "email": "admin.publico@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "tipo": Usuario.Tipo.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tipo", response.data)

    def test_register_student_requires_personal(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "nome": "Aluno Sem Personal",
                "email": "aluno.sem.personal@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "tipo": Usuario.Tipo.ALUNO,
                "data_nascimento": "2000-01-01",
                "sexo": "M",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("personal_id", response.data)

    def test_register_student_with_personal(self):
        personal = self.create_personal()

        response = self.client.post(
            "/api/auth/register/",
            {
                "nome": "Aluno Novo",
                "email": "aluno.novo@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "tipo": Usuario.Tipo.ALUNO,
                "personal_id": str(personal.id),
                "data_nascimento": "2000-01-01",
                "sexo": "F",
                "objetivo_principal": "Hipertrofia",
                "observacoes_medicas": "Sem observacoes",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"]["tipo"], Usuario.Tipo.ALUNO)
        self.assertIsNotNone(response.data["aluno"])
        self.assertEqual(Aluno.objects.count(), 1)
        self.assertEqual(Aluno.objects.get().personal, personal)

    def test_login_refresh_logout_and_me(self):
        user = self.create_personal()

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)
        self.assertEqual(login_response.data["user"]["tipo"], Usuario.Tipo.PERSONAL)
        self.assertIn(settings.AUTH_COOKIE_REFRESH_NAME, login_response.cookies)

        access = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["email"], user.email)

        patch_response = self.client.patch(
            "/api/auth/me/",
            {"nome": "Personal Atualizado"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["nome"], "Personal Atualizado")

        refresh_response = self.client.post("/api/auth/refresh/", {}, format="json")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

        logout_response = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout_response.status_code, 200)

    def test_password_reset_confirm(self):
        user = self.create_personal()
        reset_response = self.client.post(
            "/api/auth/password-reset/",
            {"email": user.email},
            format="json",
        )
        self.assertEqual(reset_response.status_code, 200)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        confirm_response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass123!",
                "confirm_password": "NewStrongPass123!",
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="http://localhost:3000",
        PASSWORD_RESET_FRONTEND_PATH="/reset-password",
    )
    def test_password_reset_email_uses_frontend_url(self):
        user = self.create_personal(email="reset.front@example.com")

        response = self.client.post(
            "/api/auth/password-reset/",
            {"email": user.email},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://localhost:3000/reset-password?uid=", mail.outbox[0].body)
        self.assertIn("token=", mail.outbox[0].body)
        self.assertIn("endpoint: /api/auth/password-reset/confirm/", mail.outbox[0].body)

    def test_login_throttle_blocks_after_configured_limit(self):
        cache.clear()

        for _ in range(5):
            response = self.client.post(
                "/api/auth/login/",
                {"email": "missing@example.com", "password": "WrongPass123!"},
                format="json",
            )
            self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/auth/login/",
            {"email": "missing@example.com", "password": "WrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 429)

    def test_admin_lists_personals_and_students(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.lista@example.com",
            password="StrongPass123!",
        )
        personal = self.create_personal()
        self.create_student(personal)

        self.client.force_authenticate(user=admin)

        personais_response = self.client.get("/api/accounts/admin/personais/")
        alunos_response = self.client.get("/api/accounts/admin/alunos/")

        self.assertEqual(personais_response.status_code, 200)
        self.assertEqual(alunos_response.status_code, 200)
        self.assertEqual(personais_response.data["results"][0]["tipo"], Usuario.Tipo.PERSONAL)
        self.assertEqual(alunos_response.data["results"][0]["personal_id"], str(personal.id))

    def test_admin_user_crud_and_activation(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.crud@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=admin)

        create_response = self.client.post(
            "/api/accounts/admin/usuarios/",
            {
                "nome": "Personal API",
                "email": "personal.api@example.com",
                "password": "StrongPass123!",
                "tipo": Usuario.Tipo.PERSONAL,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.data["tipo"], Usuario.Tipo.PERSONAL)

        user_id = create_response.data["id"]
        patch_response = self.client.patch(
            f"/api/accounts/admin/usuarios/{user_id}/",
            {"nome": "Personal API Atualizado"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["nome"], "Personal API Atualizado")

        deactivate_response = self.client.post(f"/api/accounts/admin/usuarios/{user_id}/desativar/")
        self.assertEqual(deactivate_response.status_code, 200)
        self.assertFalse(deactivate_response.data["is_active"])

        activate_response = self.client.post(f"/api/accounts/admin/usuarios/{user_id}/ativar/")
        self.assertEqual(activate_response.status_code, 200)
        self.assertTrue(activate_response.data["is_active"])

    def test_admin_user_crud_does_not_allow_type_change(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.tipo@example.com",
            password="StrongPass123!",
        )
        personal = self.create_personal(email="personal.tipo@example.com")
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            f"/api/accounts/admin/usuarios/{personal.id}/",
            {"tipo": Usuario.Tipo.ALUNO},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tipo", response.data)

    def test_admin_updates_student_extended_profile(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.aluno.detail@example.com",
            password="StrongPass123!",
        )
        personal = self.create_personal()
        other_personal = self.create_personal(email="novo.personal@example.com")
        student = self.create_student(personal)
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            f"/api/accounts/admin/alunos/{student.id}/",
            {
                "nome": "Aluno Admin",
                "email": "aluno.admin@example.com",
                "personal_id": str(other_personal.id),
                "objetivo_principal": "Emagrecimento",
                "observacoes_medicas": "Acompanhamento semanal",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        student.usuario.refresh_from_db()
        self.assertEqual(student.usuario.nome, "Aluno Admin")
        self.assertEqual(student.usuario.email, "aluno.admin@example.com")
        self.assertEqual(student.personal_id, other_personal.id)
        self.assertEqual(student.objetivo_principal, "Emagrecimento")

    def test_admin_lists_personal_metrics_and_updates_profile(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.personal.metrics@example.com",
            password="StrongPass123!",
        )
        personal = self.create_personal()
        self.create_student(personal)
        self.client.force_authenticate(user=admin)

        list_response = self.client.get("/api/accounts/admin/personais/")
        detail_response = self.client.patch(
            f"/api/accounts/admin/personais/{personal.id}/",
            {
                "especialidade": "Musculacao",
                "bio": "Atendimento para hipertrofia.",
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["results"][0]["alunos_count"], 1)
        self.assertIn("avaliacoes_30d_count", list_response.data["results"][0])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["especialidade"], "Musculacao")
        self.assertTrue(PersonalProfile.objects.filter(usuario=personal).exists())

    def test_admin_dashboard_returns_counts(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin",
            email="admin.dashboard@example.com",
            password="StrongPass123!",
        )
        personal = self.create_personal()
        self.create_student(personal)
        self.client.force_authenticate(user=admin)

        response = self.client.get("/api/accounts/admin/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["personais"]["total"], 1)
        self.assertEqual(response.data["alunos"]["total"], 1)
        self.assertIn("exercicios", response.data)

    def test_register_is_blocked_when_public_signup_is_disabled(self):
        PlatformSettings.get_solo()
        PlatformSettings.objects.update(cadastro_publico_ativo=False)

        response = self.client.post(
            "/api/auth/register/",
            {
                "nome": "Personal Bloqueado",
                "email": "personal.bloqueado@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "tipo": Usuario.Tipo.PERSONAL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_personal_lists_only_own_students(self):
        personal = self.create_personal()
        other_personal = self.create_personal(email="outro.personal@example.com")
        own_student = self.create_student(personal, email="aluno.proprio@example.com")
        other_student = self.create_student(other_personal, email="aluno.outro@example.com")

        self.client.force_authenticate(user=personal)

        list_response = self.client.get("/api/accounts/personal/alunos/")
        own_detail_response = self.client.get(f"/api/accounts/personal/alunos/{own_student.id}/")
        other_detail_response = self.client.get(f"/api/accounts/personal/alunos/{other_student.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], str(own_student.id))
        self.assertEqual(own_detail_response.status_code, 200)
        self.assertEqual(other_detail_response.status_code, 404)

    def test_student_updates_own_extended_profile(self):
        personal = self.create_personal()
        student = self.create_student(personal)

        self.client.force_authenticate(user=student.usuario)

        response = self.client.patch(
            "/api/accounts/aluno/me/",
            {
                "nome": "Aluno Atualizado",
                "objetivo_principal": "Condicionamento",
                "observacoes_medicas": "Sem restricoes",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        student.usuario.refresh_from_db()
        self.assertEqual(student.usuario.nome, "Aluno Atualizado")
        self.assertEqual(student.objetivo_principal, "Condicionamento")
        self.assertEqual(response.data["tipo"], Usuario.Tipo.ALUNO)
