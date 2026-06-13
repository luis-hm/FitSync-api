from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Aluno, Usuario
from apps.assessments.application.calculadora import (
    calcular_por_dobras,
    classificar_iac,
    classificar_imc,
    classificar_percentual_gordura,
    classificar_rcq,
    iac as calcular_iac,
    idade_em_anos,
    imc as calcular_imc,
    massas_por_percentual,
    rcq,
    status_periodicidade,
)
from apps.assessments.models import (
    Anamnese,
    Avaliacao,
    AvaliacaoBioimpedancia,
    AvaliacaoCircunferencias,
    AvaliacaoDobras,
)


DERIVED_FIELDS = {
    "imc",
    "iac",
    "classificacao_imc",
    "classificacao_iac",
    "classificacao_rcq",
    "classificacao_percentual_gordura",
    "status_periodicidade",
    "metodo_calculo",
}

DOBRAS_FIELDS = [
    "peitoral_mm",
    "axilar_media_mm",
    "triceps_mm",
    "subescapular_mm",
    "abdominal_mm",
    "supra_iliaca_mm",
    "coxa_mm",
]

CIRCUNFERENCIAS_FIELDS = [
    "pescoco_cm",
    "torax_cm",
    "cintura_cm",
    "abdome_cm",
    "quadril_cm",
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


def validate_range(attrs, fields, min_value, max_value, unit):
    errors = {}
    minimum = Decimal(str(min_value))
    maximum = Decimal(str(max_value))
    for field in fields:
        value = attrs.get(field)
        if value is None:
            continue
        if value < minimum or value > maximum:
            errors[field] = f"Valor deve estar entre {min_value} e {max_value} {unit}."
    if errors:
        raise serializers.ValidationError(errors)


def related_exists(instance, attr):
    if not instance:
        return False
    try:
        getattr(instance, attr)
    except ObjectDoesNotExist:
        return False
    return True


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

    def validate(self, attrs):
        validate_range(attrs, DOBRAS_FIELDS, 1, 100, "mm")
        return attrs


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

    def validate(self, attrs):
        percentual = attrs.get("percentual_gordura")
        if percentual is not None and (percentual < Decimal("0") or percentual > Decimal("100")):
            raise serializers.ValidationError(
                {"percentual_gordura": "Valor deve estar entre 0 e 100%."}
            )
        return attrs


class AvaliacaoCircunferenciasSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvaliacaoCircunferencias
        fields = CIRCUNFERENCIAS_FIELDS

    def validate(self, attrs):
        validate_range(attrs, CIRCUNFERENCIAS_FIELDS, 5, 200, "cm")
        quadril = attrs.get("quadril_cm")
        if quadril is not None and quadril <= Decimal("0"):
            raise serializers.ValidationError({"quadril_cm": "Quadril deve ser maior que zero."})
        return attrs


def soma_dobras(dobras_data):
    return sum([dobras_data[field] for field in DOBRAS_FIELDS], Decimal("0.00"))


class AvaliacaoSerializer(serializers.ModelSerializer):
    aluno_id = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.select_related("usuario", "personal"),
        source="aluno",
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )
    aluno_nome = serializers.CharField(source="aluno.usuario.nome", read_only=True)
    personal_id = serializers.UUIDField(source="personal.id", read_only=True)
    personal_nome = serializers.CharField(source="personal.nome", read_only=True)
    classificacao_imc = serializers.SerializerMethodField()
    classificacao_iac = serializers.SerializerMethodField()
    classificacao_rcq = serializers.SerializerMethodField()
    classificacao_percentual_gordura = serializers.SerializerMethodField()
    status_periodicidade = serializers.SerializerMethodField()
    metodo_calculo = serializers.SerializerMethodField()
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
            "data_proxima_avaliacao",
            "peso_kg",
            "altura_cm",
            "imc",
            "iac",
            "densidade_corporal",
            "percentual_gordura",
            "massa_gorda_kg",
            "massa_magra_kg",
            "rcq",
            "classificacao_imc",
            "classificacao_iac",
            "classificacao_rcq",
            "classificacao_percentual_gordura",
            "status_periodicidade",
            "metodo_calculo",
            "feedback_personal",
            "ativo",
            "data_criacao",
            "data_atualizacao",
            "dobras",
            "bioimpedancia",
            "circunferencias",
        ]
        read_only_fields = [
            "id",
            "aluno_nome",
            "personal_id",
            "personal_nome",
            "imc",
            "iac",
            "densidade_corporal",
            "percentual_gordura",
            "massa_gorda_kg",
            "massa_magra_kg",
            "rcq",
            "data_criacao",
            "data_atualizacao",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        metodo = attrs.get("metodo") or getattr(self.instance, "metodo", None)
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)
        data_avaliacao = attrs.get("data_avaliacao") or getattr(
            self.instance,
            "data_avaliacao",
            None,
        )

        dobras = attrs.get("dobras")
        bio = attrs.get("bioimpedancia")
        circ = attrs.get("circunferencias")

        sent_derived = sorted(set(getattr(self, "initial_data", {})) & DERIVED_FIELDS)
        if sent_derived:
            raise serializers.ValidationError(
                {field: "Campo derivado; nao envie este valor." for field in sent_derived}
            )

        if self.instance and not self.instance.ativo:
            raise serializers.ValidationError("Avaliacao arquivada nao pode ser alterada.")

        if self.instance and "aluno" in attrs:
            raise serializers.ValidationError({"aluno_id": "Aluno nao pode ser alterado."})

        if request.user.tipo == Usuario.Tipo.PERSONAL:
            if not aluno or aluno.personal_id != request.user.id:
                raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao personal."})
        elif request.method not in ["GET", "HEAD", "OPTIONS"]:
            raise serializers.ValidationError("Usuario nao pode salvar avaliacoes.")

        peso = attrs.get("peso_kg") or getattr(self.instance, "peso_kg", None)
        altura = attrs.get("altura_cm") or getattr(self.instance, "altura_cm", None)
        errors = {}
        if peso is not None and (peso < Decimal("1") or peso > Decimal("300")):
            errors["peso_kg"] = "Valor deve estar entre 1 e 300 kg."
        if altura is not None and (altura < 50 or altura > 250):
            errors["altura_cm"] = "Valor deve estar entre 50 e 250 cm."
        if errors:
            raise serializers.ValidationError(errors)

        data_proxima = attrs.get("data_proxima_avaliacao")
        if data_proxima and data_avaliacao and data_proxima < data_avaliacao:
            raise serializers.ValidationError(
                {"data_proxima_avaliacao": "Data nao pode ser anterior a data da avaliacao."}
            )

        if metodo == Avaliacao.Metodo.DOBRAS and dobras is None and not related_exists(
            self.instance,
            "dobras",
        ):
            raise serializers.ValidationError({"dobras": "Dobras sao obrigatorias para este metodo."})
        if metodo == Avaliacao.Metodo.BIOIMPEDANCIA and bio is None and not related_exists(
            self.instance,
            "bioimpedancia",
        ):
            raise serializers.ValidationError(
                {"bioimpedancia": "Bioimpedancia e obrigatoria para este metodo."}
            )
        if metodo == Avaliacao.Metodo.CIRCUNFERENCIAS and circ is None and not related_exists(
            self.instance,
            "circunferencias",
        ):
            raise serializers.ValidationError(
                {"circunferencias": "Circunferencias sao obrigatorias para este metodo."}
            )
        if metodo == Avaliacao.Metodo.COMBINADO:
            has_dobras = dobras is not None or related_exists(self.instance, "dobras")
            has_circ = circ is not None or related_exists(self.instance, "circunferencias")
            if not has_dobras or not has_circ:
                raise serializers.ValidationError(
                    {"metodo": "Combinado exige dobras e circunferencias."}
                )

        return attrs

    def get_idade(self, obj):
        return idade_em_anos(obj.aluno.data_nascimento, obj.data_avaliacao)

    @extend_schema_field(OpenApiTypes.STR)
    def get_classificacao_imc(self, obj):
        return classificar_imc(obj.imc)

    @extend_schema_field(OpenApiTypes.STR)
    def get_classificacao_iac(self, obj):
        return classificar_iac(obj.iac, obj.aluno.sexo, self.get_idade(obj)) if obj.iac else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_classificacao_rcq(self, obj):
        return classificar_rcq(obj.rcq, obj.aluno.sexo) if obj.rcq else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_classificacao_percentual_gordura(self, obj):
        if not obj.percentual_gordura:
            return None
        return classificar_percentual_gordura(
            obj.percentual_gordura,
            obj.aluno.sexo,
            self.get_idade(obj),
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_status_periodicidade(self, obj):
        return status_periodicidade(obj.data_proxima_avaliacao, timezone.localdate())

    @extend_schema_field(OpenApiTypes.STR)
    def get_metodo_calculo(self, obj):
        has_dobras = related_exists(obj, "dobras")
        has_bio = related_exists(obj, "bioimpedancia")
        has_circ = related_exists(obj, "circunferencias")
        if sum([has_dobras, has_bio, has_circ]) > 1:
            return "COMBINADO"
        if has_dobras:
            return "JACKSON_POLLOCK_7_SIRI"
        if has_bio:
            return "BIOIMPEDANCIA"
        if has_circ:
            return "CIRCUNFERENCIAS"
        return None

    def compute_fields(self, avaliacao, dobras_data=None, bio_data=None, circ_data=None):
        avaliacao.imc = calcular_imc(avaliacao.peso_kg, avaliacao.altura_cm)
        avaliacao.iac = None
        avaliacao.rcq = None

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
            avaliacao.iac = calcular_iac(circ_data["quadril_cm"], avaliacao.altura_cm)

        avaliacao.save()

    def get_existing_dobras_data(self, instance):
        try:
            dobras = instance.dobras
        except AvaliacaoDobras.DoesNotExist:
            return None
        return {field: getattr(dobras, field) for field in DOBRAS_FIELDS}

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
        return {field: getattr(circ, field) for field in CIRCUNFERENCIAS_FIELDS}

    @transaction.atomic
    def create(self, validated_data):
        dobras_data = validated_data.pop("dobras", None)
        bio_data = validated_data.pop("bioimpedancia", None)
        circ_data = validated_data.pop("circunferencias", None)
        validated_data.setdefault(
            "data_proxima_avaliacao",
            validated_data["data_avaliacao"] + timedelta(days=90),
        )
        avaliacao = Avaliacao.objects.create(
            personal=self.context["request"].user,
            **validated_data,
        )
        try:
            self.compute_fields(avaliacao, dobras_data, bio_data, circ_data)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
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

        compute_dobras = dobras_data if dobras_data is not None else self.get_existing_dobras_data(instance)
        compute_bio = bio_data if bio_data is not None else self.get_existing_bio_data(instance)
        compute_circ = circ_data if circ_data is not None else self.get_existing_circ_data(instance)
        try:
            self.compute_fields(instance, compute_dobras, compute_bio, compute_circ)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

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


class EvolucaoCircunferenciasSerializer(serializers.Serializer):
    for field in CIRCUNFERENCIAS_FIELDS:
        locals()[field] = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)


class EvolucaoDeltasSerializer(serializers.Serializer):
    peso_kg = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)
    imc = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    iac = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    percentual_gordura = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    massa_gorda_kg = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    massa_magra_kg = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    rcq = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    circunferencias = EvolucaoCircunferenciasSerializer()


class EvolucaoItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    data_avaliacao = serializers.DateField()
    data_proxima_avaliacao = serializers.DateField(allow_null=True)
    metodo = serializers.ChoiceField(choices=Avaliacao.Metodo.choices)
    metodo_calculo = serializers.CharField(allow_null=True)
    peso_kg = serializers.DecimalField(max_digits=5, decimal_places=2)
    imc = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    iac = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    percentual_gordura = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    massa_gorda_kg = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    massa_magra_kg = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    rcq = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    classificacao_imc = serializers.CharField(allow_null=True)
    classificacao_iac = serializers.CharField(allow_null=True)
    classificacao_rcq = serializers.CharField(allow_null=True)
    classificacao_percentual_gordura = serializers.CharField(allow_null=True)
    status_periodicidade = serializers.CharField()
    circunferencias = EvolucaoCircunferenciasSerializer()
    deltas = EvolucaoDeltasSerializer()


class AlunoEvolucaoResponseSerializer(serializers.Serializer):
    aluno_id = serializers.UUIDField()
    aluno_nome = serializers.CharField()
    results = EvolucaoItemSerializer(many=True)


class AvaliacaoResumoResponseSerializer(serializers.Serializer):
    aluno_id = serializers.UUIDField()
    aluno_nome = serializers.CharField()
    ultima_avaliacao = AvaliacaoSerializer(allow_null=True)


class AnamneseSerializer(serializers.ModelSerializer):
    aluno_id = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.select_related("usuario", "personal"),
        source="aluno",
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )
    aluno_nome = serializers.CharField(source="aluno.usuario.nome", read_only=True)

    class Meta:
        model = Anamnese
        fields = [
            "id",
            "aluno_id",
            "aluno_nome",
            "historico_familiar",
            "doencas_preexistentes",
            "lesoes",
            "medicamentos",
            "alergias",
            "cirurgias",
            "restricoes_exercicio",
            "observacoes",
            "ativo",
            "data_criacao",
            "data_atualizacao",
        ]
        read_only_fields = ["id", "aluno_nome", "data_criacao", "data_atualizacao"]

    def validate(self, attrs):
        request = self.context["request"]
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)

        if request.user.tipo != Usuario.Tipo.PERSONAL and request.method not in ["GET", "HEAD", "OPTIONS"]:
            raise serializers.ValidationError("Usuario nao pode salvar anamnese.")
        if request.user.tipo == Usuario.Tipo.PERSONAL:
            if not aluno or aluno.personal_id != request.user.id:
                raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao personal."})
        elif request.user.tipo == Usuario.Tipo.ALUNO:
            if not aluno or aluno.usuario_id != request.user.id:
                raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao usuario."})

        active = attrs.get("ativo", getattr(self.instance, "ativo", True))
        if active and aluno:
            queryset = Anamnese.objects.filter(aluno=aluno, ativo=True)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"aluno_id": "Aluno ja possui anamnese ativa."}
                )
        return attrs


class PersonalRankingItemSerializer(serializers.Serializer):
    aluno_id = serializers.UUIDField()
    aluno_nome = serializers.CharField()
    percentual_inicial = serializers.DecimalField(max_digits=5, decimal_places=2)
    percentual_final = serializers.DecimalField(max_digits=5, decimal_places=2)
    variacao_percentual_gordura = serializers.DecimalField(max_digits=5, decimal_places=2)


class PersonalRankingResponseSerializer(serializers.Serializer):
    results = PersonalRankingItemSerializer(many=True)
