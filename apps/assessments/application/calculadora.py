from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.accounts.models import Aluno


CENTESIMAL = Decimal("0.01")
CORPORAL_DENSITY = Decimal("0.00001")


def quantize(value, precision=CENTESIMAL):
    return Decimal(value).quantize(precision, rounding=ROUND_HALF_UP)


def idade_em_anos(data_nascimento, data_referencia):
    if not isinstance(data_referencia, date):
        raise ValueError("data_referencia precisa ser uma date.")
    return (
        data_referencia.year
        - data_nascimento.year
        - ((data_referencia.month, data_referencia.day) < (data_nascimento.month, data_nascimento.day))
    )


def densidade_jackson_pollock_7(sexo, idade, soma_7_dobras):
    soma = Decimal(soma_7_dobras)
    idade_decimal = Decimal(idade)

    if sexo == Aluno.Sexo.MASCULINO:
        densidade = (
            Decimal("1.112")
            - Decimal("0.00043499") * soma
            + Decimal("0.00000055") * soma * soma
            - Decimal("0.00028826") * idade_decimal
        )
    else:
        densidade = (
            Decimal("1.097")
            - Decimal("0.00046971") * soma
            + Decimal("0.00000056") * soma * soma
            - Decimal("0.00012828") * idade_decimal
        )

    return quantize(densidade, CORPORAL_DENSITY)


def percentual_gordura_siri(densidade_corporal):
    return quantize((Decimal("495") / Decimal(densidade_corporal)) - Decimal("450"))


def massas_por_percentual(peso_kg, percentual_gordura):
    peso = Decimal(peso_kg)
    percentual = Decimal(percentual_gordura)
    massa_gorda = quantize(peso * percentual / Decimal("100"))
    return massa_gorda, quantize(peso - massa_gorda)


def rcq(cintura_cm, quadril_cm):
    return quantize(Decimal(cintura_cm) / Decimal(quadril_cm))


def calcular_por_dobras(aluno, data_avaliacao, peso_kg, soma_7_dobras):
    idade = idade_em_anos(aluno.data_nascimento, data_avaliacao)
    densidade = densidade_jackson_pollock_7(aluno.sexo, idade, soma_7_dobras)
    percentual_gordura = percentual_gordura_siri(densidade)
    massa_gorda, massa_magra = massas_por_percentual(peso_kg, percentual_gordura)
    return {
        "densidade_corporal": densidade,
        "percentual_gordura": percentual_gordura,
        "massa_gorda_kg": massa_gorda,
        "massa_magra_kg": massa_magra,
    }
