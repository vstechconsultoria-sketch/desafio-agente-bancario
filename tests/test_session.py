"""Testes do sanitizador de saída e das mensagens amigáveis de erro."""
from src.session import _limpar_texto, _mensagem_amigavel_erro


def test_remove_function_tag_fechada():
    texto = "Posso encerrar o atendimento.\n<function=encerrar_atendimento>{}</function>"
    assert _limpar_texto(texto) == "Posso encerrar o atendimento."


def test_remove_tool_call_tag():
    texto = "Certo!\n<tool_call>{\"name\": \"x\"}</tool_call>"
    assert _limpar_texto(texto) == "Certo!"


def test_remove_fragmento_nao_fechado():
    texto = "Vou verificar. <function=consultar_cotacao>{"
    assert _limpar_texto(texto) == "Vou verificar."


def test_texto_normal_intacto():
    texto = "Seu limite é de R$ 5.000,00. Posso ajudar em mais algo?"
    assert _limpar_texto(texto) == texto


def test_texto_vazio():
    assert _limpar_texto("") == ""


# --- Mensagens amigáveis de erro -------------------------------------------
def test_mensagem_rate_limit():
    class RateLimitError(Exception):
        pass

    msg = _mensagem_amigavel_erro(RateLimitError("Error code: 429 rate_limit_exceeded"))
    assert "limite de uso" in msg.lower()


def test_mensagem_recursion():
    class GraphRecursionError(Exception):
        pass

    msg = _mensagem_amigavel_erro(GraphRecursionError("Recursion limit of 20 reached"))
    assert "reformular" in msg.lower()


def test_mensagem_generica():
    msg = _mensagem_amigavel_erro(ValueError("algo inesperado"))
    assert "instabilidade" in msg.lower()
