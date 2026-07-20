"""Teste de fumaça de integração (requer chave de API real do provedor).

É pulado automaticamente quando nenhuma credencial está configurada, para não
quebrar a suíte em ambientes sem acesso ao LLM. Rode com uma chave válida no
.env para validar o fluxo ponta a ponta.
"""
import os
import uuid

import pytest
from dotenv import load_dotenv

# Carrega o .env aqui também: rodado isoladamente (pytest tests/test_integration.py),
# nenhum outro módulo dispara o load_dotenv de src.config antes desta verificação,
# o que faria o teste pular mesmo com a chave presente no .env.
load_dotenv()

_TEM_CHAVE = any(
    os.getenv(k)
    for k in ("GROQ_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY")
)

pytestmark = pytest.mark.skipif(
    not _TEM_CHAVE,
    reason="Nenhuma chave de LLM configurada; teste de integração pulado.",
)


def _pular_se_sem_cota(resultado):
    """Um rate-limit do provedor é condição de ambiente, não defeito de código.

    Nesses casos pulamos o teste em vez de falhar, para a suíte não ficar
    vermelha só porque a cota (por minuto ou diária) da camada gratuita acabou.
    """
    erro = (resultado.get("erro") or "").lower()
    if "429" in erro or "rate_limit" in erro or "rate limit" in erro:
        pytest.skip("Provedor de LLM sem cota (rate limit) no momento; fluxo real pulado.")


def test_saudacao_inicial_gera_resposta():
    from src.session import enviar_mensagem

    thread = uuid.uuid4().hex
    resultado = enviar_mensagem(thread, "Olá! Vim ao atendimento.")
    _pular_se_sem_cota(resultado)
    assert isinstance(resultado["resposta"], str)
    assert resultado["resposta"].strip() != ""
    assert resultado["erro"] is None


def test_fluxo_autenticacao_valida():
    """Autentica a Ana e pede o limite; espera que o valor apareça na conversa."""
    from src.session import enviar_mensagem

    thread = uuid.uuid4().hex
    for msg in (
        "Olá, quero consultar meu limite de crédito.",
        "Meu CPF é 111.222.333-44",
        "Nasci em 15/05/1990",
    ):
        _pular_se_sem_cota(enviar_mensagem(thread, msg))
    # Após autenticar, ao pedir o limite, a resposta deve mencionar valor/limite.
    resultado = enviar_mensagem(thread, "Qual é o meu limite disponível?")
    _pular_se_sem_cota(resultado)
    assert resultado["erro"] is None
    assert "5.000" in resultado["resposta"] or "limite" in resultado["resposta"].lower()
