import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.accounts.models import Usuario
from apps.assessments.application.calculadora import iac as calcular_iac
from apps.assessments.application.calculadora import rcq as calcular_rcq


class Avaliacao(models.Model):
    class Metodo(models.TextChoices):
        DOBRAS = "DOBRAS", "Dobras"
        BIOIMPEDANCIA = "BIOIMPEDANCIA", "Bioimpedancia"
        CIRCUNFERENCIAS = "CIRCUNFERENCIAS", "Circunferencias"
        COMBINADO = "COMBINADO", "Combinado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aluno = models.ForeignKey(
        "accounts.Aluno",
        on_delete=models.PROTECT,
        related_name="avaliacoes",
    )
    personal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="avaliacoes_registradas",
    )
    metodo = models.CharField(max_length=30, choices=Metodo.choices)
    data_avaliacao = models.DateField()
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2)
    altura_cm = models.PositiveSmallIntegerField()
    densidade_corporal = models.DecimalField(max_digits=6, decimal_places=5, null=True, blank=True)
    percentual_gordura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    massa_gorda_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    massa_magra_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    imc = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    iac = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rcq = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    data_proxima_avaliacao = models.DateField(null=True, blank=True)
    feedback_personal = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "avaliacao"
        ordering = ["-data_avaliacao", "-data_criacao"]
        verbose_name = "avaliacao"
        verbose_name_plural = "avaliacoes"

    def clean(self):
        if self.personal_id and self.personal.tipo != Usuario.Tipo.PERSONAL:
            raise ValidationError({"personal": "Avaliacao precisa ser registrada por um personal."})
        if self.aluno_id and self.personal_id and self.aluno.personal_id != self.personal_id:
            raise ValidationError({"aluno": "Aluno nao pertence ao personal informado."})

    def __str__(self):
        return f"{self.aluno} - {self.data_avaliacao} ({self.metodo})"


class AvaliacaoMetodoMixin(models.Model):
    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.avaliacao_id and self.avaliacao.metodo not in self.metodos_permitidos:
            raise ValidationError(
                {"avaliacao": "Dados informados nao correspondem ao metodo da avaliacao."}
            )


class AvaliacaoDobras(AvaliacaoMetodoMixin):
    metodos_permitidos = [Avaliacao.Metodo.DOBRAS, Avaliacao.Metodo.COMBINADO]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avaliacao = models.OneToOneField(
        Avaliacao,
        on_delete=models.CASCADE,
        related_name="dobras",
    )
    peitoral_mm = models.DecimalField(max_digits=5, decimal_places=2)
    axilar_media_mm = models.DecimalField(max_digits=5, decimal_places=2)
    triceps_mm = models.DecimalField(max_digits=5, decimal_places=2)
    subescapular_mm = models.DecimalField(max_digits=5, decimal_places=2)
    abdominal_mm = models.DecimalField(max_digits=5, decimal_places=2)
    supra_iliaca_mm = models.DecimalField(max_digits=5, decimal_places=2)
    coxa_mm = models.DecimalField(max_digits=5, decimal_places=2)
    soma_7_dobras = models.DecimalField(max_digits=6, decimal_places=2, editable=False)

    class Meta:
        db_table = "avaliacao_dobras"
        verbose_name = "dobras de avaliacao"
        verbose_name_plural = "dobras de avaliacao"

    def save(self, *args, **kwargs):
        self.soma_7_dobras = sum(
            [
                self.peitoral_mm,
                self.axilar_media_mm,
                self.triceps_mm,
                self.subescapular_mm,
                self.abdominal_mm,
                self.supra_iliaca_mm,
                self.coxa_mm,
            ],
            Decimal("0.00"),
        )
        super().save(*args, **kwargs)


class AvaliacaoBioimpedancia(AvaliacaoMetodoMixin):
    metodos_permitidos = [Avaliacao.Metodo.BIOIMPEDANCIA, Avaliacao.Metodo.COMBINADO]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avaliacao = models.OneToOneField(
        Avaliacao,
        on_delete=models.CASCADE,
        related_name="bioimpedancia",
    )
    percentual_gordura = models.DecimalField(max_digits=5, decimal_places=2)
    massa_gorda_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    massa_magra_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    massa_muscular_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    agua_corporal_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    gordura_visceral = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    taxa_metabolica_basal = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "avaliacao_bioimpedancia"
        verbose_name = "bioimpedancia de avaliacao"
        verbose_name_plural = "bioimpedancias de avaliacao"


class AvaliacaoCircunferencias(AvaliacaoMetodoMixin):
    metodos_permitidos = [
        Avaliacao.Metodo.CIRCUNFERENCIAS,
        Avaliacao.Metodo.COMBINADO,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avaliacao = models.OneToOneField(
        Avaliacao,
        on_delete=models.CASCADE,
        related_name="circunferencias",
    )
    pescoco_cm = models.DecimalField(max_digits=5, decimal_places=2)
    torax_cm = models.DecimalField(max_digits=5, decimal_places=2)
    cintura_cm = models.DecimalField(max_digits=5, decimal_places=2)
    abdome_cm = models.DecimalField(max_digits=5, decimal_places=2)
    quadril_cm = models.DecimalField(max_digits=5, decimal_places=2)
    braco_relaxado_esq_cm = models.DecimalField(max_digits=5, decimal_places=2)
    braco_relaxado_dir_cm = models.DecimalField(max_digits=5, decimal_places=2)
    braco_contraido_esq_cm = models.DecimalField(max_digits=5, decimal_places=2)
    braco_contraido_dir_cm = models.DecimalField(max_digits=5, decimal_places=2)
    antebraco_esq_cm = models.DecimalField(max_digits=5, decimal_places=2)
    antebraco_dir_cm = models.DecimalField(max_digits=5, decimal_places=2)
    coxa_esq_cm = models.DecimalField(max_digits=5, decimal_places=2)
    coxa_dir_cm = models.DecimalField(max_digits=5, decimal_places=2)
    panturrilha_esq_cm = models.DecimalField(max_digits=5, decimal_places=2)
    panturrilha_dir_cm = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        db_table = "avaliacao_circunferencias"
        verbose_name = "circunferencias de avaliacao"
        verbose_name_plural = "circunferencias de avaliacao"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.quadril_cm:
            Avaliacao.objects.filter(pk=self.avaliacao_id).update(
                rcq=calcular_rcq(self.cintura_cm, self.quadril_cm),
                iac=calcular_iac(self.quadril_cm, self.avaliacao.altura_cm),
            )


class Anamnese(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aluno = models.ForeignKey(
        "accounts.Aluno",
        on_delete=models.CASCADE,
        related_name="anamneses",
    )
    historico_familiar = models.TextField(blank=True)
    doencas_preexistentes = models.TextField(blank=True)
    lesoes = models.TextField(blank=True)
    medicamentos = models.TextField(blank=True)
    alergias = models.TextField(blank=True)
    cirurgias = models.TextField(blank=True)
    restricoes_exercicio = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "anamnese"
        ordering = ["-ativo", "-data_atualizacao"]
        verbose_name = "anamnese"
        verbose_name_plural = "anamneses"
        constraints = [
            models.UniqueConstraint(
                fields=["aluno"],
                condition=Q(ativo=True),
                name="anamnese_aluno_ativo_unique",
            )
        ]

    def clean(self):
        if self.aluno_id and self.aluno.personal.tipo != Usuario.Tipo.PERSONAL:
            raise ValidationError({"aluno": "Aluno precisa estar vinculado a um personal."})

    def __str__(self):
        return f"Anamnese de {self.aluno}"
