from django.db import migrations, models
import django.utils.text


def populate_slugs(apps, schema_editor):
    Exercicio = apps.get_model("workouts", "Exercicio")
    used_slugs = set()
    for exercicio in Exercicio.objects.order_by("data_criacao", "id"):
        base_slug = django.utils.text.slugify(exercicio.nome)[:120] or "exercicio"
        candidate = base_slug
        suffix = 2
        while candidate in used_slugs or Exercicio.objects.filter(slug=candidate).exclude(pk=exercicio.pk).exists():
            candidate = f"{base_slug}-{suffix}"[:140]
            suffix += 1
        exercicio.slug = candidate
        exercicio.save(update_fields=["slug"])
        used_slugs.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0002_exercicio_ativo_alter_treino_dia_da_semana_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercicio",
            name="fonte_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="licenca_autor",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="licenca_nome",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="licenca_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="origem",
            field=models.CharField(
                choices=[("MANUAL", "Manual"), ("WGER", "wger")],
                default="MANUAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="slug",
            field=models.SlugField(blank=True, max_length=140, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDENTE", "Pendente"),
                    ("APROVADO", "Aprovado"),
                    ("REJEITADO", "Rejeitado"),
                ],
                default="APROVADO",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="wger_id",
            field=models.PositiveIntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="exercicio",
            name="wger_uuid",
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="exercicio",
            name="slug",
            field=models.SlugField(blank=True, max_length=140, unique=True),
        ),
    ]
