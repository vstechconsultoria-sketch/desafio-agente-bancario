"""Testes do sanitizador de saída (remoção de sintaxe de ferramenta vazada)."""
from src.session import _limpar_texto


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
