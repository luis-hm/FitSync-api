from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.accounts.models import Aluno


CENTESIMAL = Decimal("0.01")
CORPORAL_DENSITY = Decimal("0.00001")
PERIODICIDADE_ALERTA_DIAS = 15


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
    elif sexo == Aluno.Sexo.FEMININO:
        densidade = (
            Decimal("1.097")
            - Decimal("0.00046971") * soma
            + Decimal("0.00000056") * soma * soma
            - Decimal("0.00012828") * idade_decimal
        )
    else:
        raise ValueError("Sexo invalido para calculo de dobras.")

    return quantize(densidade, CORPORAL_DENSITY)


def percentual_gordura_siri(densidade_corporal):
    return quantize((Decimal("495") / Decimal(densidade_corporal)) - Decimal("450"))


def massas_por_percentual(peso_kg, percentual_gordura):
    peso = Decimal(peso_kg)
    percentual = Decimal(percentual_gordura)
    massa_gorda = quantize(peso * percentual / Decimal("100"))
    return massa_gorda, quantize(peso - massa_gorda)


def imc(peso_kg, altura_cm):
    altura_m = Decimal(altura_cm) / Decimal("100")
    return quantize(Decimal(peso_kg) / (altura_m * altura_m))


def iac(quadril_cm, altura_cm):
    altura_m = Decimal(altura_cm) / Decimal("100")
    return quantize((Decimal(quadril_cm) / (altura_m * altura_m.sqrt())) - Decimal("18"))


def rcq(cintura_cm, quadril_cm):
    return quantize(Decimal(cintura_cm) / Decimal(quadril_cm))


def classificar_imc(valor_imc):
    if valor_imc is None:
        return None

    valor = Decimal(valor_imc)
    if valor < Decimal("18.50"):
        return "Abaixo do peso"
    if valor < Decimal("25.00"):
        return "Peso normal"
    if valor < Decimal("30.00"):
        return "Sobrepeso"
    if valor < Decimal("35.00"):
        return "Obesidade grau I"
    if valor < Decimal("40.00"):
        return "Obesidade grau II"
    return "Obesidade grau III"


def classificar_rcq(valor_rcq, sexo):
    if valor_rcq is None:
        return None

    valor = Decimal(valor_rcq)
    if sexo == Aluno.Sexo.MASCULINO:
        if valor < Decimal("0.90"):
            return "Risco baixo"
        if valor < Decimal("1.00"):
            return "Risco moderado"
        return "Risco alto"
    if sexo == Aluno.Sexo.FEMININO:
        if valor < Decimal("0.80"):
            return "Risco baixo"
        if valor < Decimal("0.85"):
            return "Risco moderado"
        return "Risco alto"
    raise ValueError("Sexo invalido para classificacao de RCQ.")


def classificar_percentual_gordura(percentual, sexo, idade):
    if percentual is None:
        return None

    valor = Decimal(percentual)
    if sexo == Aluno.Sexo.MASCULINO:
        if idade < 40:
            baixo, adequado, moderado = Decimal("8"), Decimal("20"), Decimal("26")
        elif idade < 60:
            baixo, adequado, moderado = Decimal("11"), Decimal("22"), Decimal("28")
        else:
            baixo, adequado, moderado = Decimal("13"), Decimal("25"), Decimal("30")
    elif sexo == Aluno.Sexo.FEMININO:
        if idade < 40:
            baixo, adequado, moderado = Decimal("21"), Decimal("33"), Decimal("39")
        elif idade < 60:
            baixo, adequado, moderado = Decimal("23"), Decimal("34"), Decimal("40")
        else:
            baixo, adequado, moderado = Decimal("24"), Decimal("36"), Decimal("42")
    else:
        raise ValueError("Sexo invalido para classificacao de percentual de gordura.")

    if valor < baixo:
        return "Baixo"
    if valor < adequado:
        return "Adequado"
    if valor < moderado:
        return "Moderadamente alto"
    return "Alto"


def classificar_iac(valor_iac, sexo, idade):
    return classificar_percentual_gordura(valor_iac, sexo, idade)


def status_periodicidade(data_proxima_avaliacao, data_referencia):
    if not data_proxima_avaliacao:
        return "SEM_DATA"
    if not isinstance(data_referencia, date):
        raise ValueError("data_referencia precisa ser uma date.")

    dias_restantes = (data_proxima_avaliacao - data_referencia).days
    if dias_restantes < 0:
        return "VENCIDA"
    if dias_restantes <= PERIODICIDADE_ALERTA_DIAS:
        return "VENCE_EM_BREVE"
    return "EM_DIA"


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
