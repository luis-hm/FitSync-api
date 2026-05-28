from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Aluno
from apps.workouts.models import Exercicio, ItemTreino, ItemTreinoTemplate, Treino, TreinoTemplate


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
        self.client.force_authenticate(user=self.personal)

    def test_exercicio_crud_blocks_duplicate_name_and_archives(self):
        response = self.client.post(
            "/api/workouts/exercicios/",
            {
                "nome": "Supino Reto",
                "grupo_muscular": "Peito",
                "url_animacao": "",
                "instrucoes_gerais": "Controle a descida.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        duplicate_response = self.client.post(
            "/api/workouts/exercicios/",
            {"nome": "supino reto", "grupo_muscular": "Peito"},
            format="json",
        )
        self.assertEqual(duplicate_response.status_code, 400)

        archive_response = self.client.post(
            f"/api/workouts/exercicios/{response.data['id']}/arquivar/"
        )
        self.assertEqual(archive_response.status_code, 200)
        self.assertFalse(archive_response.data["ativo"])

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
