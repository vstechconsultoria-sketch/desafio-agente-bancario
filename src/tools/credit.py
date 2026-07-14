"""Ferramentas do Agente de Crédito."""
from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.config import logger
from src.data_manager import (
    DataAccessError,
    buscar_cliente,
    ler_tabela_score_limite,
    atualizar_limite,
    registrar_solicitacao_aumento,
    atualizar_status_solicitacao,
)
from src.domain import avaliar_aumento_limite


def _cliente_autenticado(state: dict):
    """Retorna (cliente, None) se autenticado, ou (None, mensagem_erro)."""
    if not state.get("authenticated") or not state.get("cpf"):
        return None, (
            "É necessário autenticar o cliente antes de acessar dados de crédito."
        )
    cliente = buscar_cliente(state["cpf"])
    if cliente is None:
        return None, "Não localizei o cadastro do cliente autenticado."
    return cliente, None


@tool("consultar_limite_credito")
def consultar_limite_credito(state: Annotated[dict, InjectedState]) -> str:
    """Consulta o limite de crédito disponível e o score do cliente autenticado."""
    try:
        cliente, erro = _cliente_autenticado(state)
        if erro:
            return erro
        limite = float(cliente["limite_credito"])
        score = int(cliente["score"])
        return (
            f"Limite de crédito atual: R$ {limite:,.2f}. "
            f"Score de crédito: {score}."
        )
    except DataAccessError as exc:
        return f"ERRO_TECNICO: {exc}"


@tool("solicitar_aumento_limite")
def solicitar_aumento_limite(
    novo_limite_desejado: float,
    state: Annotated[dict, InjectedState],
) -> str:
    """Registra e avalia um pedido de aumento de limite de crédito.

    Gera o pedido formal em CSV, checa o score contra a tabela de política de
    limites e retorna o status ('aprovado' ou 'rejeitado'). Em caso de rejeição,
    oriente o cliente sobre a possibilidade da entrevista de crédito.
    """
    cliente, erro = _cliente_autenticado(state)
    if erro:
        return erro

    try:
        novo_limite = float(novo_limite_desejado)
    except (TypeError, ValueError):
        return "O novo limite informado é inválido. Peça um valor numérico."

    if novo_limite <= 0:
        return "O novo limite deve ser um valor positivo."

    try:
        limite_atual = float(cliente["limite_credito"])
        score = int(cliente["score"])

        if novo_limite <= limite_atual:
            return (
                f"O valor solicitado (R$ {novo_limite:,.2f}) não é maior que o "
                f"limite atual (R$ {limite_atual:,.2f}). Confirme o novo valor."
            )

        # 1) Gera o pedido formal em estado 'pendente' (trilha de auditoria).
        registro = registrar_solicitacao_aumento(
            cpf_cliente=state["cpf"],
            limite_atual=limite_atual,
            novo_limite_solicitado=novo_limite,
            status_pedido="pendente",
        )

        # 2) Com o pedido montado, checa o score contra a política de limites.
        tabela = ler_tabela_score_limite()
        status, limite_maximo = avaliar_aumento_limite(score, novo_limite, tabela)

        # 3) O pedido "caminha" do 'pendente' para o status final decidido.
        atualizar_status_solicitacao(
            cpf_cliente=state["cpf"],
            data_hora_solicitacao=registro["data_hora_solicitacao"],
            novo_status=status,
        )

        if status == "aprovado":
            atualizar_limite(state["cpf"], novo_limite)
            return (
                f"SOLICITACAO_APROVADA. O novo limite de R$ {novo_limite:,.2f} "
                "foi aprovado e já está disponível. Parabenize o cliente."
            )

        teto = (
            f"R$ {limite_maximo:,.2f}" if limite_maximo is not None else "indisponível"
        )
        return (
            f"SOLICITACAO_REJEITADA. Com o score atual ({score}), o limite máximo "
            f"permitido é {teto}, abaixo do valor pedido (R$ {novo_limite:,.2f}). "
            "Ofereça ao cliente uma entrevista de crédito para tentar reajustar o score."
        )
    except DataAccessError as exc:
        return f"ERRO_TECNICO: {exc}"
    except Exception as exc:  # pragma: no cover - salvaguarda
        logger.exception("Erro inesperado em solicitar_aumento_limite")
        return f"ERRO_TECNICO: falha ao processar a solicitação ({exc})."
