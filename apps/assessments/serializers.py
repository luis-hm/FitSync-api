from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Aluno, Usuario
from apps.assessments.application.calculadora import calcular_por_dobras, massas_por_percentual, rcq
from apps.assessments.models import (
    Avaliacao,
    AvaliacaoBioimpedancia,
    AvaliacaoCircunferencias,
    AvaliacaoDobras,
)


class AvaliacaoDobrasSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvaliacaoDobras
        fields = [
            "peitoral_mm",
            "axilar_media_mm",
            "triceps_mm",
            "subescapular_mm",
            "abdominal_mm",
            "supra_iliaca_mm",
            "coxa_mm",
            "soma_7_dobras",
        ]
        read_only_fields = ["soma_7_dobras"]


class AvaliacaoBioimpedanciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvaliacaoBioimpedancia
        fields = [
            "percentual_gordura",
            "massa_gorda_kg",
            "massa_magra_kg",
            "massa_muscular_kg",
            "agua_corporal_percentual",
            "gordura_visceral",
            "taxa_metabolica_basal",
        ]


class AvaliacaoCircunferenciasSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvaliacaoCircunferencias
        fields = [
            "pescoco_cm",
            "torax_cm",
            "cintura_cm",
            "abdome_cm",
            "quadril_cm",
            "braco_relaxado_cm",
            "braco_contraido_cm",
            "antebraco_cm",
            "coxa_cm",
            "panturrilha_cm",
        ]


def soma_dobras(dobras_data):
    return sum(
        [
            dobras_data["peitoral_mm"],
            dobras_data["axilar_media_mm"],
            dobras_data["triceps_mm"],
            dobras_data["subescapular_mm"],
            dobras_data["abdominal_mm"],
            dobras_data["supra_iliaca_mm"],
            dobras_data["coxa_mm"],
        ],
        Decimal("0.00"),
    )


class AvaliacaoSerializer(serializers.ModelSerializer):
    aluno_id = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.select_related("usuario", "personal"),
        source="aluno",
        write_only=True,
    )
    aluno_nome = serializers.CharField(source="aluno.usuario.nome", read_only=True)
    personal_id = serializers.UUIDField(source="personal.id", read_only=True)
    personal_nome = serializers.CharField(source="personal.nome", read_only=True)
    dobras = AvaliacaoDobrasSerializer(required=False, allow_null=True)
    bioimpedancia = AvaliacaoBioimpedanciaSerializer(required=False, allow_null=True)
    circunferencias = AvaliacaoCircunferenciasSerializer(required=False, allow_null=True)

    class Meta:
        model = Avaliacao
        fields = [
            "id",
            "aluno_id",
            "aluno_nome",
            "personal_id",
            "personal_nome",
            "metodo",
            "data_avaliacao",
            "peso_kg",
            "altura_cm",
            "densidade_corporal",
            "percentual_gordura",
            "massa_gorda_kg",
            "massa_magra_kg",
            "rcq",
            "feedback_personal",
            "ativo",
            "data_criacao",
            "dobras",
            "bioimpedancia",
            "circunferencias",
        ]
        read_only_fields = [
            "id",
            "aluno_nome",
            "personal_id",
            "personal_nome",
            "densidade_corporal",
            "percentual_gordura",
            "massa_gorda_kg",
            "massa_magra_kg",
            "rcq",
            "data_criacao",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        metodo = attrs.get("metodo") or getattr(self.instance, "metodo", None)
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)

        dobras = attrs.get("dobras")
        bio = attrs.get("bioimpedancia")
        circ = attrs.get("circunferencias")

        if self.instance and not self.instance.ativo:
            raise serializers.ValidationError("Avaliacao arquivada nao pode ser alterada.")

        if self.instance and "aluno" in attrs:
            raise serializers.ValidationError({"aluno_id": "Aluno nao pode ser alterado."})

        if request.user.tipo == Usuario.Tipo.PERSONAL:
            if not aluno or aluno.personal_id != request.user.id:
                raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao personal."})
        elif request.method not in ["GET", "HEAD", "OPTIONS"]:
            raise serializers.ValidationError("Usuario nao pode salvar avaliacoes.")

        if metodo == Avaliacao.Metodo.DOBRAS and dobras is None and not getattr(self.instance, "dobras", None):
            raise serializers.ValidationError({"dobras": "Dobras sao obrigatorias para este metodo."})
        if metodo == Avaliacao.Metodo.BIOIMPEDANCIA and bio is None and not getattr(
            self.instance, "bioimpedancia", None
        ):
            raise serializers.ValidationError(
                {"bioimpedancia": "Bioimpedancia e obrigatoria para este metodo."}
            )
        if metodo == Avaliacao.Metodo.CIRCUNFERENCIAS and circ is None and not getattr(
            self.instance, "circunferencias", None
        ):
            raise serializers.ValidationError(
                {"circunferencias": "Circunferencias sao obrigatorias para este metodo."}
            )
        if metodo == Avaliacao.Metodo.COMBINADO:
            has_dobras = dobras is not None or getattr(self.instance, "dobras", None)
            has_circ = circ is not None or getattr(self.instance, "circunferencias", None)
            if not has_dobras or not has_circ:
                raise serializers.ValidationError(
                    {"metodo": "Combinado exige dobras e circunferencias."}
                )

        return attrs

    def compute_fields(self, avaliacao, dobras_data=None, bio_data=None, circ_data=None):
        if dobras_data:
            avaliacao.densidade_corporal = None
            avaliacao.percentual_gordura = None
            avaliacao.massa_gorda_kg = None
            avaliacao.massa_magra_kg = None
            computed = calcular_por_dobras(
                avaliacao.aluno,
                avaliacao.data_avaliacao,
                avaliacao.peso_kg,
                soma_dobras(dobras_data),
            )
            for field, value in computed.items():
                setattr(avaliacao, field, value)

        if bio_data:
            percentual = bio_data["percentual_gordura"]
            massa_gorda = bio_data.get("massa_gorda_kg")
            massa_magra = bio_data.get("massa_magra_kg")
            if massa_gorda is None or massa_magra is None:
                massa_gorda, massa_magra = massas_por_percentual(avaliacao.peso_kg, percentual)
                bio_data.setdefault("massa_gorda_kg", massa_gorda)
                bio_data.setdefault("massa_magra_kg", massa_magra)

            if not dobras_data:
                avaliacao.percentual_gordura = percentual
                avaliacao.massa_gorda_kg = massa_gorda
                avaliacao.massa_magra_kg = massa_magra

        if circ_data:
            avaliacao.rcq = rcq(circ_data["cintura_cm"], circ_data["quadril_cm"])

        avaliacao.save()

    def get_existing_dobras_data(self, instance):
        try:
            dobras = instance.dobras
        except AvaliacaoDobras.DoesNotExist:
            return None
        return {
            "peitoral_mm": dobras.peitoral_mm,
            "axilar_media_mm": dobras.axilar_media_mm,
            "triceps_mm": dobras.triceps_mm,
            "subescapular_mm": dobras.subescapular_mm,
            "abdominal_mm": dobras.abdominal_mm,
            "supra_iliaca_mm": dobras.supra_iliaca_mm,
            "coxa_mm": dobras.coxa_mm,
        }

    def get_existing_bio_data(self, instance):
        try:
            bio = instance.bioimpedancia
        except AvaliacaoBioimpedancia.DoesNotExist:
            return None
        return {
            "percentual_gordura": bio.percentual_gordura,
            "massa_gorda_kg": bio.massa_gorda_kg,
            "massa_magra_kg": bio.massa_magra_kg,
            "massa_muscular_kg": bio.massa_muscular_kg,
            "agua_corporal_percentual": bio.agua_corporal_percentual,
            "gordura_visceral": bio.gordura_visceral,
            "taxa_metabolica_basal": bio.taxa_metabolica_basal,
        }

    def get_existing_circ_data(self, instance):
        try:
            circ = instance.circunferencias
        except AvaliacaoCircunferencias.DoesNotExist:
            return None
        return {
            "pescoco_cm": circ.pescoco_cm,
            "torax_cm": circ.torax_cm,
            "cintura_cm": circ.cintura_cm,
            "abdome_cm": circ.abdome_cm,
            "quadril_cm": circ.quadril_cm,
            "braco_relaxado_cm": circ.braco_relaxado_cm,
            "braco_contraido_cm": circ.braco_contraido_cm,
            "antebraco_cm": circ.antebraco_cm,
            "coxa_cm": circ.coxa_cm,
            "panturrilha_cm": circ.panturrilha_cm,
        }

    @transaction.atomic
    def create(self, validated_data):
        dobras_data = validated_data.pop("dobras", None)
        bio_data = validated_data.pop("bioimpedancia", None)
        circ_data = validated_data.pop("circunferencias", None)
        avaliacao = Avaliacao.objects.create(
            personal=self.context["request"].user,
            **validated_data,
        )
        self.compute_fields(avaliacao, dobras_data, bio_data, circ_data)
        if dobras_data:
            AvaliacaoDobras.objects.create(avaliacao=avaliacao, **dobras_data)
        if bio_data:
            AvaliacaoBioimpedancia.objects.create(avaliacao=avaliacao, **bio_data)
        if circ_data:
            AvaliacaoCircunferencias.objects.create(avaliacao=avaliacao, **circ_data)
        return avaliacao

    @transaction.atomic
    def update(self, instance, validated_data):
        dobras_data = validated_data.pop("dobras", None)
        bio_data = validated_data.pop("bioimpedancia", None)
        circ_data = validated_data.pop("circunferencias", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        compute_dobras = dobras_data or self.get_existing_dobras_data(instance)
        compute_bio = bio_data or self.get_existing_bio_data(instance)
        compute_circ = circ_data or self.get_existing_circ_data(instance)
        self.compute_fields(instance, compute_dobras, compute_bio, compute_circ)

        if dobras_data:
            AvaliacaoDobras.objects.update_or_create(
                avaliacao=instance,
                defaults=dobras_data,
            )
        if bio_data:
            AvaliacaoBioimpedancia.objects.update_or_create(
                avaliacao=instance,
                defaults=bio_data,
            )
        if circ_data:
            AvaliacaoCircunferencias.objects.update_or_create(
                avaliacao=instance,
                defaults=circ_data,
            )

        return instance
