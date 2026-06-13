import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.workouts.normalization import normalize_exercise_name, normalize_group_name
from apps.workouts.models import CategoriaExercicio, Exercicio


WGER_BASE_URL = "https://wger.de/api/v2"
PORTUGUESE_LANGUAGE_ID = 7
ENGLISH_LANGUAGE_ID = 2

CATEGORY_GROUPS = {
    "Abs": "Abdômen",
    "Arms": "Braços",
    "Back": "Costas",
    "Calves": "Panturrilhas",
    "Cardio": "Cardio",
    "Chest": "Peito",
    "Legs": "Pernas",
    "Shoulders": "Ombros",
}


class PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in {"li", "p", "br"}:
            self.parts.append("\n")


def html_to_text(value):
    parser = PlainTextParser()
    parser.feed(value or "")
    return "\n".join(part for part in parser.parts if part.strip()).strip()


def choose_translation(translations):
    for language_id in [PORTUGUESE_LANGUAGE_ID, ENGLISH_LANGUAGE_ID]:
        for translation in translations or []:
            if translation.get("language") == language_id and translation.get("name"):
                return translation
    for translation in translations or []:
        if translation.get("name"):
            return translation
    return None


def normalize_wger_media_url(value, base_url):
    image_url = (value or "").strip()
    if not image_url:
        return ""

    parsed = urllib.parse.urlsplit(image_url)
    if parsed.scheme and parsed.netloc:
        return image_url

    base = urllib.parse.urlsplit(base_url)
    base_origin = f"{base.scheme}://{base.netloc}" if base.scheme and base.netloc else base_url
    return urllib.parse.urljoin(f"{base_origin.rstrip('/')}/", image_url.lstrip("/"))


def choose_image(images, base_url):
    if not images:
        return ""
    main_image = next((image for image in images if image.get("is_main") and image.get("image")), None)
    selected = main_image or next((image for image in images if image.get("image")), None)
    return normalize_wger_media_url(selected.get("image", ""), base_url) if selected else ""


def group_from_category(category):
    name = (category or {}).get("name", "")
    return normalize_group_name(CATEGORY_GROUPS.get(name, name or "Outros"))


def get_or_create_category(group_name):
    name = (group_name or "Outros").strip() or "Outros"
    category = CategoriaExercicio.objects.filter(nome__iexact=name).first()
    if category:
        return category
    return CategoriaExercicio.objects.create(nome=name)


class Command(BaseCommand):
    help = "Importa exercicios do wger como pendentes para revisao do admin."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default=WGER_BASE_URL)
        parser.add_argument("--page-size", type=int, default=50)
        parser.add_argument("--max-pages", type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        base_url = options["base_url"].rstrip("/")
        page_size = options["page_size"]
        max_pages = options["max_pages"]
        dry_run = options["dry_run"]

        created = 0
        updated = 0
        skipped = 0
        page = 0
        next_url = self.build_url(base_url, page_size, 0)

        while next_url:
            page += 1
            payload = self.fetch_json(next_url)
            for item in payload.get("results", []):
                result = self.import_item(item, base_url, dry_run=dry_run)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1

            if max_pages and page >= max_pages:
                break
            next_url = payload.get("next")

        self.stdout.write(
            self.style.SUCCESS(
                f"Importacao wger finalizada: {created} criados, {updated} atualizados, {skipped} ignorados."
            )
        )

    def build_url(self, base_url, limit, offset):
        query = urllib.parse.urlencode({"limit": limit, "offset": offset})
        return f"{base_url}/exerciseinfo/?{query}"

    def fetch_json(self, url):
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def import_item(self, item, base_url, dry_run=False):
        translation = choose_translation(item.get("translations"))
        if not translation:
            return "skipped"

        name = normalize_exercise_name(translation["name"])
        exercise_slug = slugify(name)
        if not exercise_slug:
            return "skipped"

        existing = self.find_existing(item, exercise_slug)
        defaults = self.build_defaults(item, translation, name, exercise_slug, base_url)

        if dry_run:
            return "updated" if existing else "created"

        if existing:
            changed = False
            for field, value in defaults.items():
                if field in {"status", "ativo"}:
                    continue
                if value and not getattr(existing, field):
                    setattr(existing, field, value)
                    changed = True
            if changed:
                existing.save()
                return "updated"
            return "skipped"

        Exercicio.objects.create(**defaults)
        return "created"

    def find_existing(self, item, exercise_slug):
        filters = []
        if item.get("id"):
            filters.append({"wger_id": item["id"]})
        if item.get("uuid"):
            filters.append({"wger_uuid": item["uuid"]})
        filters.append({"slug": exercise_slug})

        for lookup in filters:
            existing = Exercicio.objects.filter(**lookup).first()
            if existing:
                return existing
        return None

    def build_defaults(self, item, translation, name, exercise_slug, base_url):
        license_data = item.get("license") or {}
        description = translation.get("description_source") or html_to_text(translation.get("description", ""))
        source_url = f"{base_url}/exerciseinfo/{item.get('id')}/" if item.get("id") else f"{base_url}/exerciseinfo/"
        group_name = group_from_category(item.get("category"))
        category = get_or_create_category(group_name)
        return {
            "nome": name,
            "slug": exercise_slug,
            "categoria": category,
            "grupo_muscular": category.nome,
            "url_animacao": choose_image(item.get("images"), base_url),
            "instrucoes_gerais": description.strip(),
            "status": Exercicio.Status.PENDENTE,
            "origem": Exercicio.Origem.WGER,
            "wger_id": item.get("id"),
            "wger_uuid": item.get("uuid") or None,
            "fonte_url": source_url,
            "licenca_nome": license_data.get("short_name") or license_data.get("full_name", ""),
            "licenca_url": license_data.get("url", ""),
            "licenca_autor": item.get("license_author") or translation.get("license_author") or "",
            "ativo": False,
        }
