"""Ferramenta do Agente de Entrevista de Crédito."""
from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.config import logger
from src.data_manager import DataAccessError, atualizar_score
from src.domain import calcular_score


@tool("recalcular_score")
def recalcular_score(
    renda_mensal: float,
    tipo_emprego: str,
    despesas_fixas_mensais: float,
    numero_dependentes: int,
    tem_dividas_ativas: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Recalcula e atualiza o score de crédito com base na entrevista financeira.

    Chame APENAS após coletar todas as respostas do cliente:
    - renda_mensal (float, R$);
    - tipo_emprego: 'formal', 'autônomo' ou 'desempregado';
    - despesas_fixas_mensais (float, R$);
    - numero_dependentes (inteiro >= 0);
    - tem_dividas_ativas: 'sim' ou 'não'.
    Persiste o novo score na base e o retorna.
    """
    if not state.get("authenticated") or not state.get("cpf"):
        return "É necessário autenticar o cliente antes da entrevista de crédito."

    try:
        novo_score = calcular_score(
            renda_mensal=renda_mensal,
            tipo_emprego=tipo_emprego,
            despesas_fixas=despesas_fixas_mensais,
            num_dependentes=numero_dependentes,
            tem_dividas=tem_dividas_ativas,
        )
    except ValueError as exc:
        return f"ENTRADA_INVALIDA: {exc} Peça ao cliente para revisar a informação."

    try:
        atualizar_score(state["cpf"], novo_score)
    except DataAccessError as exc:
        return f"ERRO_TECNICO: {exc}"
    except Exception as exc:  # pragma: no cover - salvaguarda
        logger.exception("Erro inesperado ao atualizar score")
        return f"ERRO_TECNICO: falha ao salvar o novo score ({exc})."

    return (
        f"SCORE_ATUALIZADO para {novo_score}. Informe o novo score ao cliente e "
        "conduza-o de volta à análise de crédito para uma nova tentativa."
    )
