from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Aluno
from apps.assessments.application.calculadora import (
    classificar_imc,
    densidade_jackson_pollock_7,
    iac,
    imc,
    status_periodicidade,
)
from apps.assessments.models import (
    Anamnese,
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

    def test_circumferences_update_assessment_rcq_and_iac(self):
        avaliacao = self.create_avaliacao(Avaliacao.Metodo.CIRCUNFERENCIAS)

        AvaliacaoCircunferencias.objects.create(
            avaliacao=avaliacao,
            **self.circ_payload_decimal(),
        )

        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.rcq, Decimal("0.80"))
        self.assertEqual(avaliacao.iac, Decimal("23.41"))

    def test_calculator_uses_sex_specific_equations_and_rejects_invalid_sex(self):
        male_density = densidade_jackson_pollock_7(Aluno.Sexo.MASCULINO, 26, Decimal("91.00"))
        female_density = densidade_jackson_pollock_7(Aluno.Sexo.FEMININO, 26, Decimal("91.00"))

        self.assertNotEqual(male_density, female_density)
        with self.assertRaises(ValueError):
            densidade_jackson_pollock_7("X", 26, Decimal("91.00"))

    def test_imc_iac_and_status_helpers(self):
        today = timezone.localdate()

        self.assertEqual(imc(Decimal("80.00"), 180), Decimal("24.69"))
        self.assertEqual(classificar_imc(Decimal("24.69")), "Peso normal")
        self.assertEqual(iac(Decimal("100.00"), 180), Decimal("23.41"))
        self.assertEqual(status_periodicidade(today - timedelta(days=1), today), "VENCIDA")
        self.assertEqual(status_periodicidade(today + timedelta(days=10), today), "VENCE_EM_BREVE")
        self.assertEqual(status_periodicidade(today + timedelta(days=30), today), "EM_DIA")
        self.assertEqual(status_periodicidade(None, today), "SEM_DATA")

    def circ_payload_decimal(self):
        return {
            "pescoco_cm": Decimal("38.00"),
            "torax_cm": Decimal("100.00"),
            "cintura_cm": Decimal("80.00"),
            "abdome_cm": Decimal("85.00"),
            "quadril_cm": Decimal("100.00"),
            "braco_relaxado_esq_cm": Decimal("32.00"),
            "braco_relaxado_dir_cm": Decimal("33.00"),
            "braco_contraido_esq_cm": Decimal("36.00"),
            "braco_contraido_dir_cm": Decimal("37.00"),
            "antebraco_esq_cm": Decimal("28.00"),
            "antebraco_dir_cm": Decimal("29.00"),
            "coxa_esq_cm": Decimal("58.00"),
            "coxa_dir_cm": Decimal("59.00"),
            "panturrilha_esq_cm": Decimal("38.00"),
            "panturrilha_dir_cm": Decimal("39.00"),
        }


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
        self.other_personal = Usuario.objects.create_user(
            nome="Outro Personal",
            email="outro.personal.assessments@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.PERSONAL,
        )
        other_aluno_user = Usuario.objects.create_user(
            nome="Outro Aluno",
            email="outro.aluno.assessments@example.com",
            password="StrongPass123!",
            tipo=Usuario.Tipo.ALUNO,
        )
        self.other_aluno = Aluno.objects.create(
            usuario=other_aluno_user,
            personal=self.other_personal,
            data_nascimento="1998-01-01",
            sexo=Aluno.Sexo.FEMININO,
        )
        self.client.force_authenticate(user=self.personal)

    def bio_payload(self, percentual, data_avaliacao="2026-01-01", peso="80.00"):
        return {
            "aluno_id": str(self.aluno.id),
            "metodo": Avaliacao.Metodo.BIOIMPEDANCIA,
            "data_avaliacao": data_avaliacao,
            "peso_kg": peso,
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
            "braco_relaxado_esq_cm": "32.00",
            "braco_relaxado_dir_cm": "33.00",
            "braco_contraido_esq_cm": "36.00",
            "braco_contraido_dir_cm": "37.00",
            "antebraco_esq_cm": "28.00",
            "antebraco_dir_cm": "29.00",
            "coxa_esq_cm": "58.00",
            "coxa_dir_cm": "59.00",
            "panturrilha_esq_cm": "38.00",
            "panturrilha_dir_cm": "39.00",
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

    def test_create_skinfold_assessment_calculates_metrics_and_periodicity(self):
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
        self.assertEqual(response.data["imc"], "24.69")
        self.assertEqual(response.data["classificacao_imc"], "Peso normal")
        self.assertEqual(response.data["data_proxima_avaliacao"], "2026-04-01")
        self.assertEqual(response.data["metodo_calculo"], "JACKSON_POLLOCK_7_SIRI")
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

    def test_combined_assessment_calculates_iac_and_bilateral_circumferences(self):
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
        self.assertEqual(response.data["iac"], "23.41")
        self.assertEqual(response.data["metodo_calculo"], "COMBINADO")
        self.assertEqual(response.data["circunferencias"]["coxa_dir_cm"], "59.00")

    def test_rejects_derived_fields_and_invalid_physical_values(self):
        derived_response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                **self.bio_payload("30.00"),
                "imc": "10.00",
                "metodo_calculo": "BIOIMPEDANCIA",
            },
            format="json",
        )
        invalid_response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                **self.bio_payload("30.00"),
                "peso_kg": "400.00",
                "altura_cm": 40,
            },
            format="json",
        )

        self.assertEqual(derived_response.status_code, 400)
        self.assertIn("imc", derived_response.data)
        self.assertIn("metodo_calculo", derived_response.data)
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("peso_kg", invalid_response.data)
        self.assertIn("altura_cm", invalid_response.data)

    def test_custom_next_assessment_date_and_periodicity_status(self):
        today = timezone.localdate()
        response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                **self.bio_payload("25.00", str(today)),
                "data_proxima_avaliacao": str(today + timedelta(days=10)),
            },
            format="json",
        )
        invalid_response = self.client.post(
            "/api/assessments/avaliacoes/",
            {
                **self.bio_payload("25.00", "2026-02-01"),
                "data_proxima_avaliacao": "2026-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status_periodicidade"], "VENCE_EM_BREVE")
        self.assertEqual(invalid_response.status_code, 400)
        self.assertIn("data_proxima_avaliacao", invalid_response.data)

    def test_student_reads_only_own_assessments(self):
        create_response = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00"),
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)

        self.client.force_authenticate(user=self.aluno.usuario)
        list_response = self.client.get("/api/assessments/avaliacoes/")
        create_as_student = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("20.00"),
            format="json",
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["id"], create_response.data["id"])
        self.assertEqual(create_as_student.status_code, 403)

    def test_evolution_ranking_and_summary_reports(self):
        first = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00", "2026-01-01", "80.00"),
            format="json",
        )
        second = self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("25.00", "2026-02-01", "82.00"),
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        evolution = self.client.get(f"/api/assessments/alunos/{self.aluno.id}/evolucao/")
        ranking = self.client.get("/api/assessments/personal/ranking/")
        summary = self.client.get(f"/api/assessments/alunos/{self.aluno.id}/resumo/")

        self.assertEqual(evolution.status_code, 200)
        self.assertEqual(len(evolution.data["results"]), 2)
        self.assertEqual(evolution.data["results"][1]["deltas"]["percentual_gordura"], Decimal("-5.00"))
        self.assertEqual(evolution.data["results"][1]["deltas"]["imc"], Decimal("0.62"))
        self.assertEqual(evolution.data["results"][1]["metodo_calculo"], "BIOIMPEDANCIA")
        self.assertEqual(ranking.status_code, 200)
        self.assertEqual(ranking.data["results"][0]["variacao_percentual_gordura"], Decimal("-5.00"))
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["ultima_avaliacao"]["id"], second.data["id"])
        self.assertEqual(summary.data["ultima_avaliacao"]["metodo_calculo"], "BIOIMPEDANCIA")

    def test_other_personal_cannot_access_summary_or_evolution(self):
        self.client.post(
            "/api/assessments/avaliacoes/",
            self.bio_payload("30.00"),
            format="json",
        )
        self.client.force_authenticate(user=self.other_personal)

        summary = self.client.get(f"/api/assessments/alunos/{self.aluno.id}/resumo/")
        evolution = self.client.get(f"/api/assessments/alunos/{self.aluno.id}/evolucao/")

        self.assertEqual(summary.status_code, 403)
        self.assertEqual(evolution.status_code, 403)

    def test_anamnese_create_update_duplicate_and_student_read(self):
        create_response = self.client.post(
            "/api/assessments/anamneses/",
            {
                "aluno_id": str(self.aluno.id),
                "historico_familiar": "Hipertensao familiar.",
                "lesoes": "Lesao antiga no joelho.",
            },
            format="json",
        )
        duplicate_response = self.client.post(
            "/api/assessments/anamneses/",
            {
                "aluno_id": str(self.aluno.id),
                "historico_familiar": "Duplicada.",
            },
            format="json",
        )
        patch_response = self.client.patch(
            f"/api/assessments/alunos/{self.aluno.id}/anamnese/",
            {"medicamentos": "Nenhum."},
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["medicamentos"], "Nenhum.")
        self.assertEqual(Anamnese.objects.filter(aluno=self.aluno, ativo=True).count(), 1)

        self.client.force_authenticate(user=self.aluno.usuario)
        own_response = self.client.get("/api/assessments/me/anamnese/")
        forbidden_patch = self.client.patch(
            "/api/assessments/me/anamnese/",
            {"medicamentos": "Aluno editando."},
            format="json",
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response.data["historico_familiar"], "Hipertensao familiar.")
        self.assertEqual(forbidden_patch.status_code, 403)

    def test_other_personal_cannot_manage_anamnese(self):
        self.client.force_authenticate(user=self.other_personal)
        response = self.client.post(
            "/api/assessments/anamneses/",
            {
                "aluno_id": str(self.aluno.id),
                "historico_familiar": "Sem acesso.",
            },
            format="json",
        )
        patch_response = self.client.patch(
            f"/api/assessments/alunos/{self.aluno.id}/anamnese/",
            {"historico_familiar": "Sem acesso."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(patch_response.status_code, 403)
