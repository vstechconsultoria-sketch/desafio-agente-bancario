"""Ferramentas comuns a todos os agentes."""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.types import Command


@tool("encerrar_atendimento")
def encerrar_atendimento(
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Encerra o atendimento e finaliza o loop de execução.

    Use esta ferramenta sempre que o cliente sinalizar que deseja terminar a
    conversa (ex.: 'tchau', 'obrigado, era só isso', 'pode encerrar') ou quando
    o fluxo chegar naturalmente ao fim.
    """
    return Command(
        update={
            "ended": True,
            "messages": [
                ToolMessage(
                    content="Atendimento encerrado a pedido do cliente.",
                    tool_call_id=tool_call_id,
                    name="encerrar_atendimento",
                )
            ],
        }
    )
