"""Testes da ferramenta de autenticação (regra das 3 tentativas do enunciado).

O enunciado exige: validar CPF + data contra a base, informar falha e permitir
até 2 novas tentativas (3 no total), encerrando de forma cordial após a 3ª.
Estes testes exercitam a ferramenta diretamente (via ``.func``), sem LLM, para
travar esse comportamento — incluindo a blindagem que evita gastar uma tentativa
quando falta um dado ou a data vem malformada.
"""
from src.tools.auth import autenticar_cliente_tool

# A ferramenta declara parâmetros injetados (InjectedState/InjectedToolCallId);
# em produção o LangGraph os injeta. Nos testes chamamos a função crua por .func.
_auth = autenticar_cliente_tool.func


def _chamar(cpf, data, attempts=0):
    return _auth(cpf=cpf, data_nascimento=data, state={"auth_attempts": attempts}, tool_call_id="t")


# --- Blindagem: dado faltando NÃO consome tentativa -------------------------
def test_cpf_sem_data_nao_consome_tentativa():
    cmd = _chamar("11122233344", "")
    assert "auth_attempts" not in cmd.update  # nenhuma tentativa foi gasta
    assert "DADOS_INCOMPLETOS" in cmd.update["messages"][0].content


def test_data_malformada_nao_consome_tentativa():
    cmd = _chamar("11122233344", "ontem de manhã")
    assert "auth_attempts" not in cmd.update
    assert "DADOS_INCOMPLETOS" in cmd.update["messages"][0].content


def test_ambos_faltando_nao_consome_tentativa():
    cmd = _chamar("", "")
    assert "auth_attempts" not in cmd.update


# --- Autenticação de fato ---------------------------------------------------
def test_sucesso_autentica_e_guarda_contexto():
    cmd = _chamar("111.222.333-44", "15/05/1990")
    assert cmd.update["authenticated"] is True
    assert cmd.update["cpf"] == "11122233344"
    assert cmd.update["client_name"] == "Ana Souza"


def test_dados_validos_que_nao_batem_consomem_tentativa():
    # Data em formato válido, porém errada -> é uma tentativa legítima de auth.
    cmd = _chamar("11122233344", "01/01/2000")
    assert cmd.update["authenticated"] is False
    assert cmd.update["auth_attempts"] == 1


# --- Regra das 3 tentativas -------------------------------------------------
def test_falha_intermediaria_orienta_nova_tentativa():
    # 2ª falha (partindo de 1): ainda restam tentativas.
    cmd = _chamar("11122233344", "01/01/2000", attempts=1)
    conteudo = cmd.update["messages"][0].content.lower()
    assert cmd.update["auth_attempts"] == 2
    assert "restam" in conteudo or "tentativa" in conteudo
    assert "esgotad" not in conteudo


def test_terceira_falha_sinaliza_esgotamento_e_encerramento():
    # 3ª falha (partindo de 2): tentativas esgotadas -> orienta encerrar.
    cmd = _chamar("11122233344", "01/01/2000", attempts=2)
    conteudo = cmd.update["messages"][0].content.lower()
    assert cmd.update["auth_attempts"] == 3
    assert "esgotad" in conteudo
    assert "encerrar" in conteudo
