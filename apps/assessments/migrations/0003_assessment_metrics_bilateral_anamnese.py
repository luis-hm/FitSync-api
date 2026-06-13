import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q


CENTESIMAL = Decimal("0.01")


def quantize(value):
    return Decimal(value).quantize(CENTESIMAL, rounding=ROUND_HALF_UP)


def calcular_imc(peso_kg, altura_cm):
    altura_m = Decimal(altura_cm) / Decimal("100")
    return quantize(Decimal(peso_kg) / (altura_m * altura_m))


def calcular_iac(quadril_cm, altura_cm):
    altura_m = Decimal(altura_cm) / Decimal("100")
    return quantize((Decimal(quadril_cm) / (altura_m * altura_m.sqrt())) - Decimal("18"))


def calcular_rcq(cintura_cm, quadril_cm):
    return quantize(Decimal(cintura_cm) / Decimal(quadril_cm))


def migrate_existing_assessments(apps, schema_editor):
    Avaliacao = apps.get_model("assessments", "Avaliacao")
    AvaliacaoCircunferencias = apps.get_model("assessments", "AvaliacaoCircunferencias")

    for avaliacao in Avaliacao.objects.all():
        update_fields = []
        if avaliacao.peso_kg and avaliacao.altura_cm:
            avaliacao.imc = calcular_imc(avaliacao.peso_kg, avaliacao.altura_cm)
            update_fields.append("imc")

        if not avaliacao.data_proxima_avaliacao and avaliacao.data_avaliacao:
            avaliacao.data_proxima_avaliacao = avaliacao.data_avaliacao + timedelta(days=90)
            update_fields.append("data_proxima_avaliacao")

        try:
            circ = AvaliacaoCircunferencias.objects.get(avaliacao_id=avaliacao.pk)
        except AvaliacaoCircunferencias.DoesNotExist:
            circ = None

        if circ:
            circ.braco_relaxado_esq_cm = circ.braco_relaxado_cm
            circ.braco_relaxado_dir_cm = circ.braco_relaxado_cm
            circ.braco_contraido_esq_cm = circ.braco_contraido_cm
            circ.braco_contraido_dir_cm = circ.braco_contraido_cm
            circ.antebraco_esq_cm = circ.antebraco_cm
            circ.antebraco_dir_cm = circ.antebraco_cm
            circ.coxa_esq_cm = circ.coxa_cm
            circ.coxa_dir_cm = circ.coxa_cm
            circ.panturrilha_esq_cm = circ.panturrilha_cm
            circ.panturrilha_dir_cm = circ.panturrilha_cm
            circ.save(
                update_fields=[
                    "braco_relaxado_esq_cm",
                    "braco_relaxado_dir_cm",
                    "braco_contraido_esq_cm",
                    "braco_contraido_dir_cm",
                    "antebraco_esq_cm",
                    "antebraco_dir_cm",
                    "coxa_esq_cm",
                    "coxa_dir_cm",
                    "panturrilha_esq_cm",
                    "panturrilha_dir_cm",
                ]
            )
            avaliacao.rcq = calcular_rcq(circ.cintura_cm, circ.quadril_cm)
            avaliacao.iac = calcular_iac(circ.quadril_cm, avaliacao.altura_cm)
            update_fields.extend(["rcq", "iac"])

        if update_fields:
            avaliacao.save(update_fields=sorted(set(update_fields)))


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0002_avaliacao_ativo"),
    ]

    operations = [
        migrations.AddField(
            model_name="avaliacao",
            name="data_atualizacao",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="avaliacao",
            name="data_proxima_avaliacao",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="avaliacao",
            name="iac",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacao",
            name="imc",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="antebraco_dir_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="antebraco_esq_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="braco_contraido_dir_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="braco_contraido_esq_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="braco_relaxado_dir_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="braco_relaxado_esq_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="coxa_dir_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="coxa_esq_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="panturrilha_dir_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="avaliacaocircunferencias",
            name="panturrilha_esq_cm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.RunPython(migrate_existing_assessments, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="avaliacaocircunferencias",
            name="antebraco_cm",
        ),
        migrations.RemoveField(
            model_name="avaliacaocircunferencias",
            name="braco_contraido_cm",
        ),
        migrations.RemoveField(
            model_name="avaliacaocircunferencias",
            name="braco_relaxado_cm",
        ),
        migrations.RemoveField(
            model_name="avaliacaocircunferencias",
            name="coxa_cm",
        ),
        migrations.RemoveField(
            model_name="avaliacaocircunferencias",
            name="panturrilha_cm",
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="antebraco_dir_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="antebraco_esq_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="braco_contraido_dir_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="braco_contraido_esq_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="braco_relaxado_dir_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="braco_relaxado_esq_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="coxa_dir_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="coxa_esq_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="panturrilha_dir_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.AlterField(
            model_name="avaliacaocircunferencias",
            name="panturrilha_esq_cm",
            field=models.DecimalField(decimal_places=2, max_digits=5),
        ),
        migrations.CreateModel(
            name="Anamnese",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("historico_familiar", models.TextField(blank=True)),
                ("doencas_preexistentes", models.TextField(blank=True)),
                ("lesoes", models.TextField(blank=True)),
                ("medicamentos", models.TextField(blank=True)),
                ("alergias", models.TextField(blank=True)),
                ("cirurgias", models.TextField(blank=True)),
                ("restricoes_exercicio", models.TextField(blank=True)),
                ("observacoes", models.TextField(blank=True)),
                ("ativo", models.BooleanField(default=True)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
                ("data_atualizacao", models.DateTimeField(auto_now=True)),
                (
                    "aluno",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anamneses",
                        to="accounts.aluno",
                    ),
                ),
            ],
            options={
                "verbose_name": "anamnese",
                "verbose_name_plural": "anamneses",
                "db_table": "anamnese",
                "ordering": ["-ativo", "-data_atualizacao"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=Q(("ativo", True)),
                        fields=("aluno",),
                        name="anamnese_aluno_ativo_unique",
                    )
                ],
            },
        ),
    ]
