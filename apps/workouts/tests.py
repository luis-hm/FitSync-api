from datetime import date
from io import StringIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Aluno
from apps.workouts.models import (
    CategoriaExercicio,
    Exercicio,
    ItemTreino,
    ItemTreinoTemplate,
    Treino,
    TreinoTemplate,
)


Usuario = get_user_model()


class WorkoutsDomainTests(TestCase):
    def setUp(self):
        self.personal = Usuario.objects.create_user(
            nome="Personal",
            email="personal.workouts@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        aluno_user = Usuario.objects.create_user(
            nome="Aluno",
            email="aluno.workouts@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.ALUNO,
        )
        self.aluno = Aluno.objects.create(
            usuario=aluno_user,
            personal=self.personal,
            data_nascimento="2000-01-01",
            sexo=Aluno.Sexo.MASCULINO,
        )
        self.exercicio = Exercicio.objects.create(
            nome="Supino Reto",
            grupo_muscular="Peito",
        )

    def test_template_application_copies_items_to_student_workout(self):
        template = TreinoTemplate.objects.create(
            personal=self.personal,
            titulo="Hipertrofia Iniciante",
        )
        ItemTreinoTemplate.objects.create(
            template=template,
            exercicio=self.exercicio,
            series=4,
            repeticoes="10 a 12",
            descanso_segundos=60,
            ordem_execucao=1,
        )

        treino = template.aplicar_para_aluno(self.aluno, data_inicio=date(2026, 1, 1))

        self.assertEqual(treino.template_origem, template)
        self.assertEqual(treino.itens.count(), 1)
        item = treino.itens.get()
        self.assertEqual(item.exercicio, self.exercicio)
        self.assertEqual(item.repeticoes, "10 a 12")

        ItemTreinoTemplate.objects.filter(template=template).update(repeticoes="8")
        item.refresh_from_db()
        self.assertEqual(item.repeticoes, "10 a 12")

    def test_only_one_active_workout_per_student(self):
        primeiro = Treino.objects.create(
            aluno=self.aluno,
            titulo="Treino A",
            data_inicio=date(2026, 1, 1),
            ativo=True,
        )
        segundo = Treino.objects.create(
            aluno=self.aluno,
            titulo="Treino B",
            data_inicio=date(2026, 2, 1),
            ativo=True,
        )

        primeiro.refresh_from_db()
        segundo.refresh_from_db()

        self.assertFalse(primeiro.ativo)
        self.assertTrue(segundo.ativo)


class WorkoutsAPITests(APITestCase):
    def setUp(self):
        self.personal = Usuario.objects.create_user(
            nome="Personal API",
            email="personal.workouts.api@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        aluno_user = Usuario.objects.create_user(
            nome="Aluno API",
            email="aluno.workouts.api@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.ALUNO,
        )
        self.aluno = Aluno.objects.create(
            usuario=aluno_user,
            personal=self.personal,
            data_nascimento="2000-01-01",
            sexo=Aluno.Sexo.MASCULINO,
        )
        self.categoria_peito = CategoriaExercicio.objects.create(nome="Peito", ordem=1)
        self.categoria_pernas = CategoriaExercicio.objects.create(nome="Pernas", ordem=2)
        self.client.force_authenticate(user=self.personal)

    def test_personal_cannot_manage_exercises_and_admin_can_curate(self):
        personal_response = self.client.post(
            "/api/workouts/exercicios/",
            {
                "nome": "Supino Reto",
                "grupo_muscular": "Peito",
                "instrucoes_gerais": "Controle a descida.",
            },
            format="json",
        )
        self.assertEqual(personal_response.status_code, 403)

        admin = Usuario.objects.create_superuser(
            nome="Admin Workouts",
            email="admin.workouts@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            "/api/workouts/exercicios/",
            {
                "nome": "Supino Reto",
                "categoria_id": str(self.categoria_peito.id),
                "url_animacao": "",
                "instrucoes_gerais": "Controle a descida.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Exercicio.Status.APROVADO)
        self.assertEqual(response.data["origem"], Exercicio.Origem.MANUAL)
        self.assertEqual(response.data["categoria_id"], str(self.categoria_peito.id))
        self.assertEqual(response.data["categoria_nome"], "Peito")
        self.assertEqual(response.data["grupo_muscular"], "Peito")

        duplicate_response = self.client.post(
            "/api/workouts/exercicios/",
            {"nome": "supino reto", "grupo_muscular": "Peito"},
            format="json",
        )
        self.assertEqual(duplicate_response.status_code, 400)

        pending = Exercicio.objects.create(
            nome="Afundo Alternado",
            categoria=self.categoria_pernas,
            grupo_muscular="Pernas",
            status=Exercicio.Status.PENDENTE,
            ativo=False,
        )
        admin_pending_response = self.client.get(
            "/api/workouts/exercicios/",
            {"status": Exercicio.Status.PENDENTE},
        )
        self.assertEqual(admin_pending_response.status_code, 200)
        self.assertEqual(admin_pending_response.data["count"], 1)

        approve_response = self.client.post(f"/api/workouts/exercicios/{pending.id}/aprovar/")
        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.data["status"], Exercicio.Status.APROVADO)
        self.assertTrue(approve_response.data["ativo"])

        archive_response = self.client.post(f"/api/workouts/exercicios/{response.data['id']}/arquivar/")
        self.assertEqual(archive_response.status_code, 200)
        self.assertFalse(archive_response.data["ativo"])

        self.client.force_authenticate(user=self.personal)
        list_response = self.client.get("/api/workouts/exercicios/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], str(pending.id))

    def test_categories_are_admin_managed_and_filter_exercises(self):
        admin = Usuario.objects.create_superuser(
            nome="Admin Categorias",
            email="admin.categorias@example.com",
            password="StrongPass123!",
        )
        self.client.force_authenticate(user=admin)

        create_response = self.client.post(
            "/api/workouts/categorias/",
            {"nome": "Costas", "ordem": 3},
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        categoria_id = create_response.data["id"]

        exercise = Exercicio.objects.create(
            nome="Remada Baixa",
            categoria_id=categoria_id,
            grupo_muscular="",
            status=Exercicio.Status.APROVADO,
            ativo=True,
        )
        exercise.refresh_from_db()
        self.assertEqual(exercise.grupo_muscular, "Costas")

        filtered_response = self.client.get(
            "/api/workouts/exercicios/",
            {"categoria_id": categoria_id, "status": Exercicio.Status.APROVADO},
        )
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(filtered_response.data["count"], 1)
        self.assertEqual(filtered_response.data["results"][0]["id"], str(exercise.id))

        archive_response = self.client.post(f"/api/workouts/categorias/{categoria_id}/arquivar/")
        self.assertEqual(archive_response.status_code, 200)
        self.assertFalse(archive_response.data["ativo"])

        self.client.force_authenticate(user=self.personal)
        personal_categories = self.client.get("/api/workouts/categorias/")
        self.assertEqual(personal_categories.status_code, 200)
        self.assertNotIn(categoria_id, [item["id"] for item in personal_categories.data["results"]])

    def test_template_with_nested_items_and_apply_copies_to_workout(self):
        exercicio = Exercicio.objects.create(nome="Agachamento Livre", grupo_muscular="Perna")
        template_response = self.client.post(
            "/api/workouts/templates/",
            {
                "titulo": "Treino Base",
                "descricao": "Template inicial",
                "itens": [
                    {
                        "exercicio_id": str(exercicio.id),
                        "series": 4,
                        "repeticoes": "10",
                        "descanso_segundos": 60,
                        "ordem_execucao": 1,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(template_response.status_code, 201)
        self.assertEqual(len(template_response.data["itens"]), 1)

        apply_response = self.client.post(
            f"/api/workouts/templates/{template_response.data['id']}/aplicar/",
            {
                "aluno_id": str(self.aluno.id),
                "dia_da_semana": Treino.DiaSemana.SEGUNDA,
                "data_inicio": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(apply_response.status_code, 201)
        self.assertEqual(apply_response.data["aluno_nome"], self.aluno.usuario.nome)
        self.assertEqual(len(apply_response.data["itens"]), 1)

        ItemTreinoTemplate.objects.filter(template_id=template_response.data["id"]).update(
            repeticoes="8"
        )
        item = ItemTreino.objects.get(treino_id=apply_response.data["id"])
        self.assertEqual(item.repeticoes, "10")

    def test_activate_workout_deactivates_previous_and_student_reads_own_workouts(self):
        exercicio = Exercicio.objects.create(nome="Remada Curvada", grupo_muscular="Costas")
        first = self.client.post(
            "/api/workouts/treinos/",
            {
                "aluno_id": str(self.aluno.id),
                "titulo": "Treino A",
                "dia_da_semana": Treino.DiaSemana.TERCA,
                "data_inicio": "2026-01-01",
                "ativo": True,
                "itens": [
                    {
                        "exercicio_id": str(exercicio.id),
                        "series": 3,
                        "repeticoes": "12",
                        "descanso_segundos": 45,
                        "ordem_execucao": 1,
                    }
                ],
            },
            format="json",
        )
        second = self.client.post(
            "/api/workouts/treinos/",
            {
                "aluno_id": str(self.aluno.id),
                "titulo": "Treino B",
                "dia_da_semana": Treino.DiaSemana.QUARTA,
                "data_inicio": "2026-01-02",
                "ativo": True,
            },
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        first_treino = Treino.objects.get(pk=first.data["id"])
        second_treino = Treino.objects.get(pk=second.data["id"])
        self.assertFalse(first_treino.ativo)
        self.assertTrue(second_treino.ativo)

        self.client.force_authenticate(user=self.aluno.usuario)
        list_response = self.client.get("/api/workouts/treinos/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], str(second_treino.id))


class FakeWgerResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ImportWgerCommandTests(TestCase):
    def test_import_wger_creates_pending_exercises_with_pt_and_english_fallback(self):
        payload = {
            "next": None,
            "results": [
                {
                    "id": 101,
                    "uuid": "11111111-1111-1111-1111-111111111111",
                    "category": {"id": 9, "name": "Legs"},
                    "images": [
                        {
                            "image": "https://wger.de/media/exercise-images/squat.png",
                            "is_main": True,
                        }
                    ],
                    "license": {
                        "short_name": "CC-BY-SA 4",
                        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    },
                    "license_author": "wger",
                    "translations": [
                        {
                            "language": 2,
                            "name": "Squat",
                            "description_source": "Lower your hips and stand up.",
                        },
                        {
                            "language": 7,
                            "name": "Agachamento Livre",
                            "description_source": "Flexione os joelhos e suba com controle.",
                        },
                    ],
                },
                {
                    "id": 102,
                    "uuid": "22222222-2222-2222-2222-222222222222",
                    "category": {"id": 11, "name": "Chest"},
                    "images": [
                        {
                            "image": "/media/exercise-images/push-up.png",
                            "is_main": True,
                        }
                    ],
                    "license": {"full_name": "Creative Commons"},
                    "license_author": "",
                    "translations": [
                        {
                            "language": 2,
                            "name": "Push-Up",
                            "description": "<ol><li>Keep your body aligned.</li></ol>",
                        }
                    ],
                },
            ],
        }

        with patch(
            "apps.workouts.management.commands.import_wger.urllib.request.urlopen",
            return_value=FakeWgerResponse(payload),
        ):
            call_command("import_wger", stdout=StringIO())
            call_command("import_wger", stdout=StringIO())

        self.assertEqual(Exercicio.objects.count(), 2)
        squat = Exercicio.objects.get(wger_id=101)
        self.assertEqual(squat.nome, "Agachamento Livre")
        self.assertEqual(squat.slug, "agachamento-livre")
        self.assertEqual(squat.grupo_muscular, "Pernas")
        self.assertEqual(squat.categoria.nome, "Pernas")
        self.assertEqual(squat.url_animacao, "https://wger.de/media/exercise-images/squat.png")
        self.assertEqual(squat.status, Exercicio.Status.PENDENTE)
        self.assertEqual(squat.origem, Exercicio.Origem.WGER)
        self.assertFalse(squat.ativo)

        fallback = Exercicio.objects.get(wger_id=102)
        self.assertEqual(fallback.nome, "Flexão")
        self.assertEqual(fallback.grupo_muscular, "Peito")
        self.assertEqual(fallback.url_animacao, "https://wger.de/media/exercise-images/push-up.png")
        self.assertIn("Keep your body aligned", fallback.instrucoes_gerais)
