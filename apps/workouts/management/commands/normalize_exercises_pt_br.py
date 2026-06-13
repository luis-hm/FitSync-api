from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.workouts.models import CategoriaExercicio, Exercicio
from apps.workouts.normalization import (
    normalize_exercise_name,
    normalize_group_name,
    normalize_instruction_text,
)


class Command(BaseCommand):
    help = "Normaliza categorias e exercicios para nomes em portugues do Brasil."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--sample-size", type=int, default=30)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        sample_size = options["sample_size"]

        category_changes = self.build_category_changes()
        exercise_changes = self.build_exercise_changes()

        self.write_summary(category_changes, exercise_changes, sample_size)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteracao foi salva."))
            return

        with transaction.atomic():
            for category, values in category_changes:
                category.nome = values["nome"]
                category.save(update_fields=["nome"])

            for exercise, values in exercise_changes:
                for field, value in values.items():
                    setattr(exercise, field, value)
                if exercise.categoria_id and "grupo_muscular" in values:
                    exercise.categoria.nome = values["grupo_muscular"]
                exercise.save(update_fields=list(values.keys()))

        self.stdout.write(
            self.style.SUCCESS(
                f"Normalizacao PT-BR finalizada: {len(category_changes)} categorias e "
                f"{len(exercise_changes)} exercicios atualizados."
            )
        )

    def build_category_changes(self):
        changes = []
        for category in CategoriaExercicio.objects.order_by("nome"):
            normalized_name = normalize_group_name(category.nome)
            if normalized_name != category.nome:
                changes.append((category, {"nome": normalized_name}))
        return changes

    def build_exercise_changes(self):
        exercises = list(Exercicio.objects.select_related("categoria").order_by("nome", "id"))
        used_names = {exercise.nome.casefold(): exercise.id for exercise in exercises}
        used_slugs = {exercise.slug: exercise.id for exercise in exercises if exercise.slug}
        changes = []

        for exercise in exercises:
            used_names.pop(exercise.nome.casefold(), None)
            if exercise.slug:
                used_slugs.pop(exercise.slug, None)

            values = {}
            normalized_name = self.unique_name(normalize_exercise_name(exercise.nome), exercise.id, used_names)
            used_names[normalized_name.casefold()] = exercise.id

            if normalized_name != exercise.nome:
                values["nome"] = normalized_name
                values["slug"] = self.unique_slug(slugify(normalized_name) or "exercicio", exercise.id, used_slugs)
                used_slugs[values["slug"]] = exercise.id
            elif exercise.slug:
                used_slugs[exercise.slug] = exercise.id

            normalized_group = normalize_group_name(exercise.categoria.nome if exercise.categoria_id else exercise.grupo_muscular)
            if normalized_group != exercise.grupo_muscular:
                values["grupo_muscular"] = normalized_group

            normalized_instructions = normalize_instruction_text(exercise.instrucoes_gerais)
            if normalized_instructions != exercise.instrucoes_gerais:
                values["instrucoes_gerais"] = normalized_instructions

            if values:
                changes.append((exercise, values))

        return changes

    def unique_name(self, base_name, exercise_id, used_names):
        candidate = base_name
        suffix = 2
        while used_names.get(candidate.casefold()) not in {None, exercise_id}:
            candidate = f"{base_name} {suffix}"
            suffix += 1
        return candidate

    def unique_slug(self, base_slug, exercise_id, used_slugs):
        candidate = base_slug[:140]
        suffix = 2
        while used_slugs.get(candidate) not in {None, exercise_id}:
            suffix_text = f"-{suffix}"
            candidate = f"{base_slug[:140 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        return candidate

    def write_summary(self, category_changes, exercise_changes, sample_size):
        self.stdout.write(f"Categorias a normalizar: {len(category_changes)}")
        for category, values in category_changes[:sample_size]:
            self.stdout.write(f"  - {category.nome} -> {values['nome']}")

        self.stdout.write(f"Exercicios a normalizar: {len(exercise_changes)}")
        for exercise, values in exercise_changes[:sample_size]:
            parts = []
            if "nome" in values:
                parts.append(f"nome: {exercise.nome} -> {values['nome']}")
            if "grupo_muscular" in values:
                parts.append(f"grupo: {exercise.grupo_muscular} -> {values['grupo_muscular']}")
            if "instrucoes_gerais" in values:
                parts.append("instrucoes: limpeza leve")
            self.stdout.write(f"  - {exercise.id}: " + "; ".join(parts))
