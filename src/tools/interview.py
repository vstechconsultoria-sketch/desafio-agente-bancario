"""Ferramenta do Agente de Entrevista de Crédito."""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.config import logger
from src.data_manager import DataAccessError, atualizar_score
from src.domain import calcular_score

# Campos de sessão preservados ao devolver o cliente ao Agente de Crédito.
_CAMPOS_SESSAO = ("authenticated", "cpf", "client_name", "auth_attempts", "ended")


@tool("recalcular_score")
def recalcular_score(
    renda_mensal: float,
    tipo_emprego: str,
    despesas_fixas_mensais: float,
    numero_dependentes: int,
    tem_dividas_ativas: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Recalcula e atualiza o score de crédito com base na entrevista financeira.

    Chame APENAS após coletar todas as respostas do cliente:
    - renda_mensal (float, R$);
    - tipo_emprego: 'formal', 'autônomo' ou 'desempregado';
    - despesas_fixas_mensais (float, R$);
    - numero_dependentes (inteiro >= 0);
    - tem_dividas_ativas: 'sim' ou 'não'.
    Persiste o novo score na base e, em caso de sucesso, devolve automaticamente
    o cliente ao atendimento de crédito para nova análise.
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

    # Sucesso: devolve o cliente ao Agente de Crédito de forma DETERMINÍSTICA
    # (não depende do LLM decidir transferir), preservando o contexto de sessão.
    mensagem = ToolMessage(
        content=(
            f"SCORE_ATUALIZADO para {novo_score}. Você agora está no atendimento de "
            "crédito: informe o novo score ao cliente e refaça a análise do aumento "
            "de limite que ele havia pedido."
        ),
        tool_call_id=tool_call_id,
        name="recalcular_score",
    )
    update = {"active_agent": "credito", "messages": [mensagem]}
    for campo in _CAMPOS_SESSAO:
        if campo in state and state.get(campo) is not None:
            update[campo] = state.get(campo)

    return Command(goto="credito", graph=Command.PARENT, update=update)
