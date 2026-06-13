import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower
from django.utils.text import slugify
from django.utils import timezone

from apps.accounts.models import Usuario


class CategoriaExercicio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "categoria_exercicio"
        ordering = ["ordem", "nome"]
        verbose_name = "categoria de exercicio"
        verbose_name_plural = "categorias de exercicios"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug(self.nome)
        super().save(*args, **kwargs)

    def generate_unique_slug(self, value):
        base_slug = slugify(value)[:80] or "categoria"
        candidate = base_slug
        suffix = 2
        while CategoriaExercicio.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base_slug}-{suffix}"[:100]
            suffix += 1
        return candidate


class Exercicio(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        APROVADO = "APROVADO", "Aprovado"
        REJEITADO = "REJEITADO", "Rejeitado"

    class Origem(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        WGER = "WGER", "wger"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    categoria = models.ForeignKey(
        CategoriaExercicio,
        on_delete=models.PROTECT,
        related_name="exercicios",
        null=True,
        blank=True,
    )
    grupo_muscular = models.CharField(max_length=80)
    url_animacao = models.URLField(blank=True)
    instrucoes_gerais = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APROVADO)
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.MANUAL)
    wger_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    wger_uuid = models.UUIDField(null=True, blank=True, unique=True)
    fonte_url = models.URLField(blank=True)
    licenca_nome = models.CharField(max_length=120, blank=True)
    licenca_url = models.URLField(blank=True)
    licenca_autor = models.CharField(max_length=160, blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exercicio"
        ordering = ["grupo_muscular", "nome"]
        verbose_name = "exercicio"
        verbose_name_plural = "exercicios"
        constraints = [
            models.UniqueConstraint(
                Lower("nome"),
                name="exercicio_nome_ci_unique",
            )
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug(self.nome)
        if self.categoria_id:
            self.grupo_muscular = self.categoria.nome
        super().save(*args, **kwargs)

    def generate_unique_slug(self, value):
        base_slug = slugify(value)[:120] or "exercicio"
        candidate = base_slug
        suffix = 2
        while Exercicio.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base_slug}-{suffix}"[:140]
            suffix += 1
        return candidate


class TreinoTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    personal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="treino_templates",
    )
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "treino_template"
        ordering = ["titulo"]
        verbose_name = "template de treino"
        verbose_name_plural = "templates de treino"

    def clean(self):
        if self.personal_id and self.personal.tipo != Usuario.Tipo.PERSONAL:
            raise ValidationError({"personal": "Template precisa pertencer a um personal."})

    @transaction.atomic
    def aplicar_para_aluno(
        self,
        aluno,
        titulo=None,
        dia_da_semana="",
        data_inicio=None,
        data_vencimento=None,
        ativo=True,
    ):
        if aluno.personal_id != self.personal_id:
            raise ValidationError({"aluno": "Aluno nao pertence ao personal do template."})

        treino = Treino.objects.create(
            aluno=aluno,
            template_origem=self,
            titulo=titulo or self.titulo,
            dia_da_semana=dia_da_semana,
            data_inicio=data_inicio or timezone.localdate(),
            data_vencimento=data_vencimento,
            ativo=ativo,
        )
        ItemTreino.objects.bulk_create(
            [
                ItemTreino(
                    treino=treino,
                    exercicio=item.exercicio,
                    series=item.series,
                    repeticoes=item.repeticoes,
                    descanso_segundos=item.descanso_segundos,
                    ordem_execucao=item.ordem_execucao,
                )
                for item in self.itens.order_by("ordem_execucao", "id")
            ]
        )
        return treino

    def __str__(self):
        return self.titulo


class ItemTreinoBase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exercicio = models.ForeignKey(
        Exercicio,
        on_delete=models.PROTECT,
    )
    series = models.PositiveSmallIntegerField()
    repeticoes = models.CharField(max_length=40)
    descanso_segundos = models.PositiveSmallIntegerField()
    ordem_execucao = models.PositiveSmallIntegerField()

    class Meta:
        abstract = True
        ordering = ["ordem_execucao", "id"]


class ItemTreinoTemplate(ItemTreinoBase):
    template = models.ForeignKey(
        TreinoTemplate,
        on_delete=models.CASCADE,
        related_name="itens",
    )

    class Meta(ItemTreinoBase.Meta):
        db_table = "item_treino_template"
        verbose_name = "item de template de treino"
        verbose_name_plural = "itens de template de treino"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "ordem_execucao"],
                name="item_treino_template_ordem_unique",
            )
        ]

    def __str__(self):
        return f"{self.ordem_execucao}. {self.exercicio}"


class Treino(models.Model):
    class DiaSemana(models.TextChoices):
        SEGUNDA = "SEGUNDA", "Segunda-feira"
        TERCA = "TERCA", "Terca-feira"
        QUARTA = "QUARTA", "Quarta-feira"
        QUINTA = "QUINTA", "Quinta-feira"
        SEXTA = "SEXTA", "Sexta-feira"
        SABADO = "SABADO", "Sabado"
        DOMINGO = "DOMINGO", "Domingo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aluno = models.ForeignKey(
        "accounts.Aluno",
        on_delete=models.CASCADE,
        related_name="treinos",
    )
    template_origem = models.ForeignKey(
        TreinoTemplate,
        on_delete=models.SET_NULL,
        related_name="treinos_aplicados",
        null=True,
        blank=True,
    )
    titulo = models.CharField(max_length=150)
    dia_da_semana = models.CharField(max_length=20, choices=DiaSemana.choices, blank=True)
    data_inicio = models.DateField()
    data_vencimento = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "treino"
        ordering = ["-ativo", "data_inicio", "titulo"]
        verbose_name = "treino"
        verbose_name_plural = "treinos"

    def clean(self):
        if self.template_origem_id and self.aluno_id:
            if self.template_origem.personal_id != self.aluno.personal_id:
                raise ValidationError(
                    {"template_origem": "Template precisa pertencer ao personal do aluno."}
                )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.ativo:
                Treino.objects.filter(aluno=self.aluno, ativo=True).exclude(pk=self.pk).update(
                    ativo=False
                )

    def __str__(self):
        return self.titulo


class ItemTreino(ItemTreinoBase):
    treino = models.ForeignKey(
        Treino,
        on_delete=models.CASCADE,
        related_name="itens",
    )

    class Meta(ItemTreinoBase.Meta):
        db_table = "item_treino"
        verbose_name = "item de treino"
        verbose_name_plural = "itens de treino"
        constraints = [
            models.UniqueConstraint(
                fields=["treino", "ordem_execucao"],
                name="item_treino_ordem_unique",
            )
        ]

    def __str__(self):
        return f"{self.ordem_execucao}. {self.exercicio}"
