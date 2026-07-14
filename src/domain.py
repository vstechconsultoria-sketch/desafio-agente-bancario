"""Regras de negócio puras (sem I/O e sem LLM), portanto 100% testáveis.

Contém:
- o cálculo do score de crédito da entrevista financeira;
- a decisão de aprovação/rejeição de aumento de limite com base na tabela
  score x limite.
"""
from __future__ import annotations

from typing import Optional

# --- Pesos da fórmula de score ---------------------------------------------
PESO_RENDA = 30

PESO_EMPREGO = {
    "formal": 300,
    "autonomo": 200,
    "autônomo": 200,  # aceita com e sem acento
    "desempregado": 0,
}

PESO_DEPENDENTES = {
    0: 100,
    1: 80,
    2: 60,
    "3+": 30,
}

PESO_DIVIDAS = {
    "sim": -100,
    "nao": 100,
    "não": 100,
    True: -100,
    False: 100,
}

SCORE_MIN = 0
SCORE_MAX = 1000


def _normaliza_emprego(tipo_emprego: str) -> str:
    return str(tipo_emprego).strip().lower()


def _normaliza_dividas(tem_dividas) -> str:
    if isinstance(tem_dividas, bool):
        return "sim" if tem_dividas else "nao"
    valor = str(tem_dividas).strip().lower()
    return "sim" if valor in ("sim", "s", "true", "1") else "nao"


def calcular_score(
    renda_mensal: float,
    tipo_emprego: str,
    despesas_fixas: float,
    num_dependentes: int,
    tem_dividas,
) -> int:
    """Calcula o novo score de crédito (0 a 1000) pela fórmula ponderada.

    A pontuação bruta é limitada (clamp) ao intervalo [0, 1000].
    Lança ``ValueError`` para entradas fora do domínio esperado.
    """
    renda_mensal = float(renda_mensal)
    despesas_fixas = float(despesas_fixas)
    num_dependentes = int(num_dependentes)

    if renda_mensal < 0 or despesas_fixas < 0 or num_dependentes < 0:
        raise ValueError("Valores financeiros não podem ser negativos.")

    emprego = _normaliza_emprego(tipo_emprego)
    if emprego not in PESO_EMPREGO:
        raise ValueError(
            "Tipo de emprego inválido. Use 'formal', 'autônomo' ou 'desempregado'."
        )

    chave_dep = num_dependentes if num_dependentes in (0, 1, 2) else "3+"
    dividas = _normaliza_dividas(tem_dividas)

    score = (
        (renda_mensal / (despesas_fixas + 1)) * PESO_RENDA
        + PESO_EMPREGO[emprego]
        + PESO_DEPENDENTES[chave_dep]
        + PESO_DIVIDAS[dividas]
    )

    # Mantém o score dentro da faixa oficial [0, 1000].
    score = max(SCORE_MIN, min(SCORE_MAX, score))
    return int(round(score))


def limite_maximo_por_score(score: int, tabela: list[dict]) -> Optional[float]:
    """Dado o score do cliente, retorna o limite máximo permitido pela tabela.

    ``tabela`` é a lista de dicts vinda de ``data_manager.ler_tabela_score_limite``.
    Retorna ``None`` se nenhuma faixa cobrir o score informado.
    """
    score = int(score)
    for faixa in tabela:
        try:
            smin = int(faixa["score_min"])
            smax = int(faixa["score_max"])
            limite = float(faixa["limite_maximo"])
        except (KeyError, ValueError):
            continue
        if smin <= score <= smax:
            return limite
    return None


def avaliar_aumento_limite(
    score: int,
    novo_limite_solicitado: float,
    tabela: list[dict],
) -> tuple[str, Optional[float]]:
    """Decide o status de uma solicitação de aumento de limite.

    Retorna uma tupla ``(status, limite_maximo)`` onde status é
    'aprovado' ou 'rejeitado'. ``limite_maximo`` é o teto da faixa do cliente
    (ou ``None`` se a tabela não cobrir o score).
    """
    limite_maximo = limite_maximo_por_score(score, tabela)
    if limite_maximo is None:
        return "rejeitado", None

    if float(novo_limite_solicitado) <= limite_maximo:
        return "aprovado", limite_maximo
    return "rejeitado", limite_maximo
