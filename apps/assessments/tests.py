from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Aluno
from apps.assessments.models import (
    Avaliacao,
    AvaliacaoCircunferencias,
    AvaliacaoDobras,
)


Usuario = get_user_model()


class AssessmentsDomainTests(TestCase):
    def setUp(self):
        self.personal = Usuario.objects.create_user(
            nome="Personal",
            email="personal.assessments@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        aluno_user = Usuario.objects.create_user(
            nome="Aluno",
            email="aluno.assessments@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.ALUNO,
        )
        self.aluno = Aluno.objects.create(
            usuario=aluno_user,
            personal=self.personal,
            data_nascimento="2000-01-01",
            sexo=Aluno.Sexo.MASCULINO,
        )

    def create_avaliacao(self, metodo=Avaliacao.Metodo.COMBINADO):
        return Avaliacao.objects.create(
            aluno=self.aluno,
            personal=self.personal,
            metodo=metodo,
            data_avaliacao=date(2026, 1, 1),
            peso_kg=Decimal("80.00"),
            altura_cm=180,
        )

    def test_skinfolds_store_sum_of_seven_measurements(self):
        avaliacao = self.create_avaliacao(Avaliacao.Metodo.DOBRAS)

        dobras = AvaliacaoDobras.objects.create(
            avaliacao=avaliacao,
            peitoral_mm=Decimal("10.00"),
            axilar_media_mm=Decimal("11.00"),
            triceps_mm=Decimal("12.00"),
            subescapular_mm=Decimal("13.00"),
            abdominal_mm=Decimal("14.00"),
            supra_iliaca_mm=Decimal("15.00"),
            coxa_mm=Decimal("16.00"),
        )

        self.assertEqual(dobras.soma_7_dobras, Decimal("91.00"))

    def test_circumferences_update_assessment_rcq(self):
        avaliacao = self.create_avaliacao(Avaliacao.Metodo.CIRCUNFERENCIAS)

        AvaliacaoCircunferencias.objects.create(
            avaliacao=avaliacao,
            pescoco_cm=Decimal("38.00"),
            torax_cm=Decimal("100.00"),
            cintura_cm=Decimal("80.00"),
            abdome_cm=Decimal("85.00"),
            quadril_cm=Decimal("100.00"),
            braco_relaxado_cm=Decimal("32.00"),
            braco_contraido_cm=Decimal("36.00"),
            antebraco_cm=Decimal("28.00"),
            coxa_cm=Decimal("58.00"),
            panturrilha_cm=Decimal("38.00"),
        )

        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.rcq, Decimal("0.80"))


class AssessmentsAPITests(APITestCase):
    def setUp(self):
        self.personal = Usuario.objects.create_user(
            nome="Personal API",
            email="personal.assessments.api@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        aluno_user = Usuario.objects.create_user(
            nome="Aluno API",
            email="aluno.assessments.api@example.com",
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

    def bio_payload(self, percentual, data_avaliacao="2026-01-01"):
        return {
            "aluno_id": str(self.aluno.id),
            "metodo": Avaliacao.Metodo.BIOIMPEDANCIA,
            "data_avaliacao": data_avaliacao,
            "peso_kg": "80.00",
            "altura_cm": 180,
            "bioimpedancia": {"percentual_gordura": str(percentual)},
        }

    def circ_payload(self):
        return {
            "pescoco_cm": "38.00",
            "torax_cm": "100.00",
            "cintura_cm": "80.00",
            "abdome_cm": "85.00",
            "quadril_cm": "100.00",
            "braco_relaxado_cm": "32.00",
            "braco_contraido_cm": "36.00",
            "antebraco_cm": "28.00",
            "coxa_cm": "58.00",
            "panturrilha_cm": "38.00",
        }

    def dobras_payload(self):
        return {
            "peitoral_mm": "10.00",
            "axilar_media_mm": "11.00",
            "triceps_mm": "12.00",
            "subescapular_mm": "13.00",
            "abdominal_mm": "14.00",
            "supra_iliaca_mm": "15.00",
            "coxa_mm": "16.00",
        }

    def test_create_skinfold_assessment_calculates_body_composition(self):
        response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                "aluno_id": str(self.aluno.id),
                "metodo": Avaliacao.Metodo.DOBRAS,
                "data_avaliacao": "2026-01-01",
                "peso_kg": "80.00",
                "altura_cm": 180,
                "dobras": self.dobras_payload(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data["densidade_corporal"])
        self.assertIsNotNone(response.data["percentual_gordura"])
        self.assertIsNotNone(response.data["massa_gorda_kg"])
        self.assertEqual(response.data["dobras"]["soma_7_dobras"], "91.00")

    def test_assessment_requires_expected_block_for_method(self):
        response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                "aluno_id": str(self.aluno.id),
                "metodo": Avaliacao.Metodo.CIRCUNFERENCIAS,
                "data_avaliacao": "2026-01-01",
                "peso_kg": "80.00",
                "altura_cm": 180,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("circunferencias", response.data)

    def test_bioimpedance_patch_recomputes_masses_and_archive(self):
        create_response = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00"),
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)

        patch_response = self.client.patch(
            f"/api/assessments/avaliacoes/{create_response.data['id']}/",
            {"bioimpedancia": {"percentual_gordura": "25.00"}},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["percentual_gordura"], "25.00")
        self.assertEqual(patch_response.data["massa_gorda_kg"], "20.00")

        archive_response = self.client.post(
            f"/api/assessments/avaliacoes/{create_response.data['id']}/arquivar/"
        )
        self.assertEqual(archive_response.status_code, 200)
        self.assertFalse(archive_response.data["ativo"])

    def test_combined_assessment_requires_skinfolds_and_circumferences(self):
        response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                "aluno_id": str(self.aluno.id),
                "metodo": Avaliacao.Metodo.COMBINADO,
                "data_avaliacao": "2026-01-01",
                "peso_kg": "80.00",
                "altura_cm": 180,
                "dobras": self.dobras_payload(),
                "circunferencias": self.circ_payload(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["rcq"], "0.80")

    def test_student_reads_only_own_assessments(self):
        create_response = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00"),
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)

        self.client.force_authenticate(user=self.aluno.usuario)
        list_response = self.client.get("/api/assessments/avaliacoes/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], create_response.data["id"])

    def test_evolution_and_ranking_reports(self):
        first = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00", "2026-01-01"),
            format="json",
        )
        second = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("25.00", "2026-02-01"),
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        evolution = self.client.get(f"/api/assessments/alunos/{self.aluno.id}/evolucao/")
        ranking = self.client.get("/api/assessments/personal/ranking/")

        self.assertEqual(evolution.status_code, 200)
        self.assertEqual(len(evolution.data["results"]), 2)
        self.assertEqual(evolution.data["results"][1]["deltas"]["percentual_gordura"], Decimal("-5.00"))
        self.assertEqual(ranking.status_code, 200)
        self.assertEqual(ranking.data["results"][0]["variacao_percentual_gordura"], Decimal("-5.00"))
