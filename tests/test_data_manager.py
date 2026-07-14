"""Testes da camada de acesso a dados (autenticação e escrita em CSV)."""
import csv

import pytest

from src import config, data_manager
from src.data_manager import (
    autenticar_cliente,
    buscar_cliente,
    normalizar_cpf,
    normalizar_data,
    registrar_solicitacao_aumento,
    atualizar_status_solicitacao,
    atualizar_score,
    atualizar_limite,
)


# --- Normalização -----------------------------------------------------------
def test_normalizar_cpf_remove_mascara():
    assert normalizar_cpf("111.222.333-44") == "11122233344"


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("15/05/1990", "1990-05-15"),
        ("1990-05-15", "1990-05-15"),
        ("15-05-1990", "1990-05-15"),
    ],
)
def test_normalizar_data_formatos(entrada, esperado):
    assert normalizar_data(entrada) == esperado


def test_normalizar_data_invalida():
    assert normalizar_data("data qualquer") is None


# --- Autenticação (lê a base real, somente leitura) -------------------------
def test_autenticacao_sucesso_com_mascara():
    cliente = autenticar_cliente("111.222.333-44", "15/05/1990")
    assert cliente is not None
    assert cliente["nome"] == "Ana Souza"


def test_autenticacao_falha_data_errada():
    assert autenticar_cliente("11122233344", "01/01/2000") is None


def test_autenticacao_falha_cpf_inexistente():
    assert autenticar_cliente("00000000000", "15/05/1990") is None


def test_buscar_cliente_inexistente():
    assert buscar_cliente("00000000000") is None


# --- Escrita em CSV (usa cópias temporárias via monkeypatch) ----------------
@pytest.fixture
def base_temporaria(tmp_path, monkeypatch):
    """Cria cópias isoláveis dos CSVs para não afetar os arquivos reais."""
    clientes = tmp_path / "clientes.csv"
    with open(clientes, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cpf", "data_nascimento", "nome", "limite_credito", "score"])
        writer.writerow(["11122233344", "1990-05-15", "Ana Souza", "5000.00", "650"])

    solicitacoes = tmp_path / "solicitacoes.csv"

    monkeypatch.setattr(config, "CLIENTES_CSV", clientes)
    monkeypatch.setattr(config, "SOLICITACOES_CSV", solicitacoes)
    return {"clientes": clientes, "solicitacoes": solicitacoes}


def test_registrar_solicitacao_cria_arquivo_com_cabecalho(base_temporaria):
    registro = registrar_solicitacao_aumento("11122233344", 5000, 8000, "pendente")
    assert registro["status_pedido"] == "pendente"
    assert "T" in registro["data_hora_solicitacao"]  # ISO 8601

    with open(base_temporaria["solicitacoes"], encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 1
    assert linhas[0]["cpf_cliente"] == "11122233344"
    assert linhas[0]["novo_limite_solicitado"] == "8000.00"


def test_transicao_de_status_pendente_para_final(base_temporaria):
    # Reproduz o fluxo do enunciado: pedido nasce 'pendente' e caminha para o final.
    registro = registrar_solicitacao_aumento("11122233344", 5000, 6000, "pendente")
    assert registro["status_pedido"] == "pendente"

    atualizar_status_solicitacao(
        "11122233344", registro["data_hora_solicitacao"], "aprovado"
    )

    with open(base_temporaria["solicitacoes"], encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 1  # a linha foi atualizada, não duplicada
    assert linhas[0]["status_pedido"] == "aprovado"


def test_atualizar_status_solicitacao_inexistente_levanta_erro(base_temporaria):
    from src.data_manager import DataAccessError

    registrar_solicitacao_aumento("11122233344", 5000, 6000, "pendente")
    with pytest.raises(DataAccessError):
        atualizar_status_solicitacao("11122233344", "timestamp-inexistente", "aprovado")


def test_atualizar_score_persiste(base_temporaria):
    atualizar_score("11122233344", 720)
    assert buscar_cliente("11122233344")["score"] == "720"


def test_atualizar_limite_persiste(base_temporaria):
    atualizar_limite("11122233344", 9000)
    assert buscar_cliente("11122233344")["limite_credito"] == "9000.00"
