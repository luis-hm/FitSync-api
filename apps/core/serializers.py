from rest_framework import serializers

from apps.core.models import PlatformSettings


class ChoiceOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class AuthOptionsSerializer(serializers.Serializer):
    tipos_cadastro = ChoiceOptionSerializer(many=True)


class AccountsOptionsSerializer(serializers.Serializer):
    sexos = ChoiceOptionSerializer(many=True)


class WorkoutsOptionsSerializer(serializers.Serializer):
    dias_semana = ChoiceOptionSerializer(many=True)


class AssessmentsOptionsSerializer(serializers.Serializer):
    metodos = ChoiceOptionSerializer(many=True)


class PlatformSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSettings
        fields = [
            "nome_plataforma",
            "suporte_email",
            "cadastro_publico_ativo",
            "data_atualizacao",
        ]
        read_only_fields = ["data_atualizacao"]


class OptionsSerializer(serializers.Serializer):
    auth = AuthOptionsSerializer()
    accounts = AccountsOptionsSerializer()
    workouts = WorkoutsOptionsSerializer()
    assessments = AssessmentsOptionsSerializer()
