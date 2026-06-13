import uuid

import django.db.models.deletion
import django.utils.text
from django.db import migrations, models


def unique_slug(model, value):
    base_slug = django.utils.text.slugify(value)[:80] or "categoria"
    candidate = base_slug
    suffix = 2
    while model.objects.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"[:100]
        suffix += 1
    return candidate


def backfill_categories(apps, schema_editor):
    Exercicio = apps.get_model("workouts", "Exercicio")
    CategoriaExercicio = apps.get_model("workouts", "CategoriaExercicio")

    groups = (
        Exercicio.objects.exclude(grupo_muscular="")
        .values_list("grupo_muscular", flat=True)
        .distinct()
        .order_by("grupo_muscular")
    )

    categories_by_name = {}
    order = 1
    for group_name in groups:
        normalized_name = (group_name or "").strip()
        normalized_key = normalized_name.lower()
        if not normalized_name or normalized_key in categories_by_name:
            continue
        category, _ = CategoriaExercicio.objects.get_or_create(
            nome=normalized_name,
            defaults={
                "slug": unique_slug(CategoriaExercicio, normalized_name),
                "ordem": order,
                "ativo": True,
            },
        )
        categories_by_name[normalized_key] = category
        order += 1

    for exercise in Exercicio.objects.all():
        category = categories_by_name.get((exercise.grupo_muscular or "").strip().lower())
        if category:
            exercise.categoria_id = category.id
            exercise.save(update_fields=["categoria"])


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0003_exercicio_catalog_curation"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoriaExercicio",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("nome", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=100, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("ordem", models.PositiveSmallIntegerField(default=0)),
                ("data_criacao", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "categoria de exercicio",
                "verbose_name_plural": "categorias de exercicios",
                "db_table": "categoria_exercicio",
                "ordering": ["ordem", "nome"],
            },
        ),
        migrations.AddField(
            model_name="exercicio",
            name="categoria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="exercicios",
                to="workouts.categoriaexercicio",
            ),
        ),
        migrations.RunPython(backfill_categories, migrations.RunPython.noop),
    ]
