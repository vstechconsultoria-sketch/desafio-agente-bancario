"""Ferramenta do Agente de Câmbio (consulta de cotações)."""
from __future__ import annotations

import requests

from langchain_core.tools import tool

from src import config
from src.config import logger

# Aliases comuns -> código ISO da moeda.
_ALIASES = {
    "DOLAR": "USD",
    "DÓLAR": "USD",
    "DOLLAR": "USD",
    "USD": "USD",
    "EURO": "EUR",
    "EUR": "EUR",
    "LIBRA": "GBP",
    "GBP": "GBP",
    "BITCOIN": "BTC",
    "BTC": "BTC",
    "PESO": "ARS",
    "ARS": "ARS",
}


@tool("consultar_cotacao")
def consultar_cotacao(moeda: str = "USD") -> str:
    """Consulta a cotação atual de uma moeda em relação ao Real (BRL).

    ``moeda`` pode ser o código ISO (USD, EUR, GBP...) ou o nome popular
    (dólar, euro, libra). O padrão é o dólar (USD).
    """
    entrada = str(moeda).strip().upper()
    codigo = _ALIASES.get(entrada, entrada)

    par = f"{codigo}-BRL"
    url = f"{config.EXCHANGE_API_URL}/{par}"

    try:
        resposta = requests.get(url, timeout=8)
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.Timeout:
        logger.warning("Timeout ao consultar cotação de %s", codigo)
        return (
            "O serviço de cotação demorou a responder. Peça desculpas e sugira "
            "tentar novamente em instantes."
        )
    except requests.RequestException as exc:
        logger.error("Falha na API de câmbio (%s): %s", codigo, exc)
        return (
            "Não consegui obter a cotação agora (serviço indisponível). "
            "Informe o cliente de forma cordial e ofereça tentar mais tarde."
        )

    chave = f"{codigo}BRL"
    if chave not in dados:
        return (
            f"Não encontrei cotação para '{moeda}'. Confirme o código da moeda "
            "(ex.: USD, EUR, GBP)."
        )

    info = dados[chave]
    try:
        compra = float(info["bid"])
        variacao = float(info.get("pctChange", 0.0))
        nome = info.get("name", par)
    except (KeyError, ValueError) as exc:
        logger.error("Resposta inesperada da API de câmbio: %s", exc)
        return "Recebi uma resposta inesperada do serviço de cotação. Tente novamente."

    return (
        f"COTACAO {nome}: R$ {compra:,.4f} "
        f"(variação de {variacao:+.2f}% no dia). "
        "Apresente o valor ao cliente de forma clara."
    )
