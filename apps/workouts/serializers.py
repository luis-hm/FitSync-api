from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Aluno, Usuario
from apps.workouts.models import (
    Exercicio,
    ItemTreino,
    ItemTreinoTemplate,
    Treino,
    TreinoTemplate,
)


class ExercicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercicio
        fields = [
            "id",
            "nome",
            "grupo_muscular",
            "url_animacao",
            "instrucoes_gerais",
            "ativo",
            "data_criacao",
        ]
        read_only_fields = ["id", "data_criacao"]

    def validate_nome(self, value):
        queryset = Exercicio.objects.filter(nome__iexact=value.strip())
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ja existe um exercicio com este nome.")
        return value.strip()


class ItemTreinoTemplateSerializer(serializers.ModelSerializer):
    exercicio = ExercicioSerializer(read_only=True)
    exercicio_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercicio.objects.filter(ativo=True),
        source="exercicio",
        write_only=True,
    )

    class Meta:
        model = ItemTreinoTemplate
        fields = [
            "id",
            "exercicio",
            "exercicio_id",
            "series",
            "repeticoes",
            "descanso_segundos",
            "ordem_execucao",
        ]
        read_only_fields = ["id", "exercicio"]


class ItemTreinoSerializer(serializers.ModelSerializer):
    exercicio = ExercicioSerializer(read_only=True)
    exercicio_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercicio.objects.filter(ativo=True),
        source="exercicio",
        write_only=True,
    )

    class Meta:
        model = ItemTreino
        fields = [
            "id",
            "exercicio",
            "exercicio_id",
            "series",
            "repeticoes",
            "descanso_segundos",
            "ordem_execucao",
        ]
        read_only_fields = ["id", "exercicio"]


def validate_unique_ordem(items):
    ordens = [item["ordem_execucao"] for item in items]
    if len(ordens) != len(set(ordens)):
        raise serializers.ValidationError({"itens": "ordem_execucao nao pode repetir."})


class TreinoTemplateSerializer(serializers.ModelSerializer):
    personal_id = serializers.UUIDField(source="personal.id", read_only=True)
    personal_nome = serializers.CharField(source="personal.nome", read_only=True)
    itens = ItemTreinoTemplateSerializer(many=True, required=False)

    class Meta:
        model = TreinoTemplate
        fields = [
            "id",
            "personal_id",
            "personal_nome",
            "titulo",
            "descricao",
            "ativo",
            "data_criacao",
            "itens",
        ]
        read_only_fields = ["id", "personal_id", "personal_nome", "data_criacao"]

    def validate(self, attrs):
        itens = attrs.get("itens")
        if itens is not None:
            validate_unique_ordem(itens)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop("itens", [])
        template = TreinoTemplate.objects.create(
            personal=self.context["request"].user,
            **validated_data,
        )
        ItemTreinoTemplate.objects.bulk_create(
            [ItemTreinoTemplate(template=template, **item) for item in itens_data]
        )
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        itens_data = validated_data.pop("itens", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if itens_data is not None:
            instance.itens.all().delete()
            ItemTreinoTemplate.objects.bulk_create(
                [ItemTreinoTemplate(template=instance, **item) for item in itens_data]
            )
        return instance


class TreinoSerializer(serializers.ModelSerializer):
    aluno_id = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.select_related("usuario", "personal"),
        source="aluno",
        write_only=True,
    )
    aluno_nome = serializers.CharField(source="aluno.usuario.nome", read_only=True)
    template_origem_id = serializers.UUIDField(source="template_origem.id", read_only=True)
    itens = ItemTreinoSerializer(many=True, required=False)

    class Meta:
        model = Treino
        fields = [
            "id",
            "aluno_id",
            "aluno_nome",
            "template_origem_id",
            "titulo",
            "dia_da_semana",
            "data_inicio",
            "data_vencimento",
            "ativo",
            "data_criacao",
            "itens",
        ]
        read_only_fields = ["id", "aluno_nome", "template_origem_id", "data_criacao"]

    def validate(self, attrs):
        request = self.context["request"]
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)
        itens = attrs.get("itens")

        if self.instance and "aluno" in attrs:
            raise serializers.ValidationError({"aluno_id": "Aluno nao pode ser alterado."})

        if request.user.tipo == Usuario.Tipo.PERSONAL:
            if not aluno or aluno.personal_id != request.user.id:
                raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao personal."})
        elif request.user.tipo != Usuario.Tipo.ADMIN:
            raise serializers.ValidationError("Usuario nao pode salvar treinos.")

        if itens is not None:
            validate_unique_ordem(itens)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        itens_data = validated_data.pop("itens", [])
        treino = Treino.objects.create(**validated_data)
        ItemTreino.objects.bulk_create([ItemTreino(treino=treino, **item) for item in itens_data])
        return treino

    @transaction.atomic
    def update(self, instance, validated_data):
        itens_data = validated_data.pop("itens", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if itens_data is not None:
            instance.itens.all().delete()
            ItemTreino.objects.bulk_create([ItemTreino(treino=instance, **item) for item in itens_data])
        return instance


class AplicarTemplateSerializer(serializers.Serializer):
    aluno_id = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.select_related("usuario", "personal"),
        source="aluno",
    )
    titulo = serializers.CharField(max_length=150, required=False, allow_blank=True)
    dia_da_semana = serializers.ChoiceField(
        choices=Treino.DiaSemana.choices,
        required=False,
        allow_blank=True,
    )
    data_inicio = serializers.DateField(required=False)
    data_vencimento = serializers.DateField(required=False, allow_null=True)
    ativo = serializers.BooleanField(default=True)

    def validate(self, attrs):
        template = self.context["template"]
        aluno = attrs["aluno"]
        if aluno.personal_id != template.personal_id:
            raise serializers.ValidationError({"aluno_id": "Aluno nao pertence ao personal do template."})
        return attrs
