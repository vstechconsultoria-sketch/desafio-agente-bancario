"""Camada de sessão: encapsula a interação com o grafo por thread/conversa.

Fornece uma API simples (enviar mensagem, obter histórico, verificar
encerramento) usada tanto pela UI Streamlit quanto pelo CLI de teste.
"""
from __future__ import annotations

import re
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage

from src.config import logger
from src.graph import build_graph

# Alguns modelos (ex.: Llama via Groq) ocasionalmente "vazam" a sintaxe da
# chamada de ferramenta como texto em vez de emitir um tool_call de verdade.
# Estes padrões limpam esse ruído para que o cliente nunca veja detalhes técnicos.
_PADROES_RUIDO = [
    re.compile(r"<function=.*?</function>", re.DOTALL),
    re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL),
    re.compile(r"<function=[^>]*>\s*\{[^}]*\}?", re.DOTALL),
    re.compile(r"<function=[^\n]*$", re.DOTALL),  # fragmento não fechado no fim
]


def _limpar_texto(texto: str) -> str:
    """Remove sintaxe de chamada de ferramenta eventualmente vazada no texto."""
    if not texto:
        return texto
    limpo = texto
    for padrao in _PADROES_RUIDO:
        limpo = padrao.sub("", limpo)
    limpo = re.sub(r"\n{3,}", "\n\n", limpo)
    return limpo.strip()


@lru_cache(maxsize=1)
def get_graph():
    """Compila o grafo uma única vez por processo (memoizado)."""
    return build_graph()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def enviar_mensagem(thread_id: str, texto: str) -> dict:
    """Envia a mensagem do usuário ao grafo e retorna o estado resultante.

    Retorna um dict com ``resposta`` (texto do atendente), ``encerrado`` (bool)
    e ``erro`` (str | None) para tratamento amigável na UI.
    """
    graph = get_graph()
    config = _config(thread_id)
    try:
        estado = graph.invoke({"messages": [HumanMessage(content=texto)]}, config)
    except Exception as exc:  # falha inesperada do LLM/infra
        logger.exception("Falha ao processar turno da conversa")
        return {
            "resposta": (
                "Desculpe, tive uma instabilidade no atendimento agora. "
                "Pode tentar novamente em instantes?"
            ),
            "encerrado": False,
            "erro": str(exc),
        }

    resposta = _ultima_resposta(estado.get("messages", []))
    return {
        "resposta": resposta,
        "encerrado": bool(estado.get("ended")),
        "erro": None,
    }


def obter_historico(thread_id: str) -> list[dict]:
    """Retorna o histórico visível da conversa (usuário + atendente)."""
    graph = get_graph()
    snapshot = graph.get_state(_config(thread_id))
    mensagens = snapshot.values.get("messages", []) if snapshot else []
    return _formatar_para_ui(mensagens)


def _formatar_para_ui(mensagens: list) -> list[dict]:
    historico = []
    for msg in mensagens:
        if isinstance(msg, HumanMessage):
            historico.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            conteudo = _limpar_texto(msg.content or "")
            if conteudo:  # ignora AIMessages que são apenas chamadas de ferramenta
                historico.append({"role": "assistant", "content": conteudo})
    return historico


def _ultima_resposta(mensagens: list) -> str:
    for msg in reversed(mensagens):
        if isinstance(msg, AIMessage):
            conteudo = _limpar_texto(msg.content or "")
            if conteudo:
                return conteudo
    return ""
