from rest_framework import serializers


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


class OptionsSerializer(serializers.Serializer):
    auth = AuthOptionsSerializer()
    accounts = AccountsOptionsSerializer()
    workouts = WorkoutsOptionsSerializer()
    assessments = AssessmentsOptionsSerializer()
