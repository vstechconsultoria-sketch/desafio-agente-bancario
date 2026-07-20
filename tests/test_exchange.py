"""Testes da ferramenta de câmbio, com a API externa mockada.

Cobrem o caminho feliz (incluindo o mapeamento de nomes populares para o código
ISO) e os erros que o enunciado pede tratar de forma controlada: serviço
indisponível, timeout, moeda inexistente e resposta malformada. Sem rede.
"""
import requests

from src.tools import exchange

_cotacao = exchange.consultar_cotacao.func


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _mock_get(payload):
    def _get(url, timeout=None):
        return _FakeResp(payload)
    return _get


# --- Caminho feliz + mapeamento de moeda -----------------------------------
def test_cotacao_dolar_por_nome_popular(monkeypatch):
    # "dólar" deve virar USD e casar com a chave USDBRL da resposta.
    payload = {"USDBRL": {"bid": "5.2000", "pctChange": "0.43", "name": "Dólar/Real"}}
    monkeypatch.setattr(exchange.requests, "get", _mock_get(payload))
    saida = _cotacao("dólar")
    # Alias "dólar" -> USD casou com a chave USDBRL e a cotação foi extraída.
    assert "COTACAO" in saida
    assert "5.2000" in saida  # valor bruto da ferramenta (o LLM formata pt-BR)


def test_cotacao_codigo_iso_direto(monkeypatch):
    payload = {"EURBRL": {"bid": "6.10", "pctChange": "-0.12", "name": "Euro/Real"}}
    monkeypatch.setattr(exchange.requests, "get", _mock_get(payload))
    assert "COTACAO" in _cotacao("EUR")


# --- Erros tratados de forma controlada ------------------------------------
def test_moeda_inexistente_pede_confirmacao(monkeypatch):
    monkeypatch.setattr(exchange.requests, "get", _mock_get({}))  # sem a chave
    saida = _cotacao("XYZ")
    assert "não encontrei" in saida.lower()


def test_timeout_retorna_mensagem_amigavel(monkeypatch):
    def _raise(url, timeout=None):
        raise requests.Timeout()
    monkeypatch.setattr(exchange.requests, "get", _raise)
    saida = _cotacao("USD")
    assert "demorou" in saida.lower()


def test_api_indisponivel_retorna_mensagem_amigavel(monkeypatch):
    def _raise(url, timeout=None):
        raise requests.ConnectionError("sem rede")
    monkeypatch.setattr(exchange.requests, "get", _raise)
    saida = _cotacao("USD")
    assert "indisponível" in saida.lower()


def test_resposta_malformada_e_tratada(monkeypatch):
    # Tem a chave da moeda, mas falta o campo 'bid'.
    payload = {"USDBRL": {"pctChange": "0.1"}}
    monkeypatch.setattr(exchange.requests, "get", _mock_get(payload))
    saida = _cotacao("USD")
    assert "inesperada" in saida.lower()
