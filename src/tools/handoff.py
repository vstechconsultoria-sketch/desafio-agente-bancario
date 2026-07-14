"""Ferramentas de transferência (handoff) entre agentes.

A transferência é feita de forma implícita: para o cliente, a conversa segue
com "um único atendente". Internamente, o handoff emite um ``Command`` que
redireciona o fluxo do grafo para outro nó (agente), atualizando ``active_agent``
para que o próximo turno também comece no agente correto.

Detalhe importante de arquitetura: cada agente é um subgrafo (create_react_agent)
com o mesmo schema de estado. Quando o subgrafo sai via ``Command(graph=PARENT)``,
APENAS o que estiver no ``update`` do comando é persistido no estado pai. Por
isso o handoff precisa reencaminhar explicitamente o contexto de sessão
(autenticação, CPF, etc.) para que ele sobreviva à transição e aos próximos turnos.
"""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

# Campos de sessão que devem ser preservados ao trocar de agente.
_CAMPOS_SESSAO = ("authenticated", "cpf", "client_name", "auth_attempts", "ended")


def criar_handoff(destino: str, descricao: str):
    """Cria uma tool de transferência para o agente ``destino``.

    O nome da tool é ``transferir_para_<destino>``; a ``descricao`` orienta o
    LLM sobre QUANDO usá-la.
    """

    @tool(f"transferir_para_{destino}", description=descricao)
    def _handoff(
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        mensagem = ToolMessage(
            content=f"Transferência interna concluída para o agente '{destino}'.",
            tool_call_id=tool_call_id,
            name=f"transferir_para_{destino}",
        )
        # Reencaminha o contexto de sessão vigente para o estado pai.
        update = {"active_agent": destino, "messages": [mensagem]}
        for campo in _CAMPOS_SESSAO:
            if campo in state and state.get(campo) is not None:
                update[campo] = state.get(campo)

        return Command(goto=destino, graph=Command.PARENT, update=update)

    return _handoff
