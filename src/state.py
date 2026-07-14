"""Estado compartilhado entre todos os agentes do grafo.

Estende ``MessagesState`` (que já contém o histórico de mensagens) com o
contexto de sessão: agente ativo, dados de autenticação e flag de encerramento.
Esse estado é único por thread/sessão e persiste entre os turnos da conversa.
"""
from __future__ import annotations

from typing import Optional

from langgraph.prebuilt.chat_agent_executor import AgentState


class BankState(AgentState):
    # Herda 'messages' e 'remaining_steps' de AgentState (exigidos pelo
    # create_react_agent) e acrescenta o contexto de sessão do Banco Ágil.
    # Nome do agente que deve receber o próximo turno do usuário.
    active_agent: str
    # Contexto de autenticação preenchido pelo Agente de Triagem.
    cpf: Optional[str]
    authenticated: bool
    auth_attempts: int
    client_name: Optional[str]
    # Sinaliza que o cliente pediu (ou o fluxo levou ao) encerramento.
    ended: bool


def estado_inicial() -> dict:
    """Retorna o dicionário de estado inicial de uma nova sessão."""
    return {
        "messages": [],
        "active_agent": "triagem",
        "cpf": None,
        "authenticated": False,
        "auth_attempts": 0,
        "client_name": None,
        "ended": False,
    }
