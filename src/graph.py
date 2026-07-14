"""Construção do grafo multi-agente (padrão swarm com handoffs implícitos).

Cada agente é um ReAct agent (LLM + ferramentas). Um roteador de entrada envia
cada novo turno do usuário para o agente atualmente ativo (persistido no estado
via checkpointer). As transferências entre agentes acontecem por ``Command``,
de forma invisível ao cliente.
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.state import BankState
from src.agents import prompts
from src.tools.auth import autenticar_cliente_tool
from src.tools.common import encerrar_atendimento
from src.tools.credit import consultar_limite_credito, solicitar_aumento_limite
from src.tools.exchange import consultar_cotacao
from src.tools.handoff import criar_handoff
from src.tools.interview import recalcular_score

# --- Ferramentas de transferência (descrições orientam QUANDO usar) ---------
_para_credito = criar_handoff(
    "credito",
    "Transfira para o atendimento de crédito quando o cliente falar de limite de "
    "crédito, aumento de limite ou análise de crédito.",
)
_para_entrevista = criar_handoff(
    "entrevista",
    "Transfira para a entrevista de crédito quando for necessário recalcular o "
    "score do cliente por meio de perguntas financeiras.",
)
_para_cambio = criar_handoff(
    "cambio",
    "Transfira para o atendimento de câmbio quando o cliente quiser consultar "
    "cotação de moedas (dólar, euro, etc.).",
)
_para_triagem = criar_handoff(
    "triagem",
    "Transfira de volta para a triagem caso seja necessário reautenticar ou "
    "reidentificar a necessidade do cliente.",
)


def _rotear_entrada(state: BankState) -> str:
    """Direciona o turno atual para o agente ativo (ou triagem por padrão)."""
    agente = state.get("active_agent") or "triagem"
    if state.get("ended"):
        return END
    return agente


def build_graph(checkpointer=None):
    """Compila e retorna o grafo de atendimento pronto para uso."""
    llm = get_llm()

    triagem = create_react_agent(
        llm,
        tools=[
            autenticar_cliente_tool,
            _para_credito,
            _para_cambio,
            _para_entrevista,
            encerrar_atendimento,
        ],
        prompt=prompts.TRIAGEM_PROMPT,
        state_schema=BankState,
        name="triagem",
    )

    credito = create_react_agent(
        llm,
        tools=[
            consultar_limite_credito,
            solicitar_aumento_limite,
            _para_entrevista,
            _para_cambio,
            encerrar_atendimento,
        ],
        prompt=prompts.CREDITO_PROMPT,
        state_schema=BankState,
        name="credito",
    )

    entrevista = create_react_agent(
        llm,
        tools=[recalcular_score, _para_credito, encerrar_atendimento],
        prompt=prompts.ENTREVISTA_PROMPT,
        state_schema=BankState,
        name="entrevista",
    )

    cambio = create_react_agent(
        llm,
        tools=[consultar_cotacao, _para_credito, encerrar_atendimento],
        prompt=prompts.CAMBIO_PROMPT,
        state_schema=BankState,
        name="cambio",
    )

    builder = StateGraph(BankState)
    builder.add_node("triagem", triagem)
    builder.add_node("credito", credito)
    builder.add_node("entrevista", entrevista)
    builder.add_node("cambio", cambio)

    # Cada novo turno começa no agente ativo.
    builder.add_conditional_edges(
        START,
        _rotear_entrada,
        {
            "triagem": "triagem",
            "credito": "credito",
            "entrevista": "entrevista",
            "cambio": "cambio",
            END: END,
        },
    )

    # Ao terminar sem handoff, o agente devolve o controle e aguarda o cliente.
    for no in ("triagem", "credito", "entrevista", "cambio"):
        builder.add_edge(no, END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
