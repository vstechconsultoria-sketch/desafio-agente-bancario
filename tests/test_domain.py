"""Testes da lógica de negócio pura (score e política de limites)."""
import pytest

from src.domain import (
    avaliar_aumento_limite,
    calcular_score,
    limite_maximo_por_score,
)

TABELA = [
    {"score_min": "0", "score_max": "299", "limite_maximo": "1000.00"},
    {"score_min": "300", "score_max": "499", "limite_maximo": "3000.00"},
    {"score_min": "500", "score_max": "699", "limite_maximo": "7000.00"},
    {"score_min": "700", "score_max": "849", "limite_maximo": "15000.00"},
    {"score_min": "850", "score_max": "1000", "limite_maximo": "30000.00"},
]


# --- calcular_score ---------------------------------------------------------
def test_score_cliente_formal_saudavel():
    # (5000/2001)*30 + 300 + 100 + 100 = 574.96 -> 575
    score = calcular_score(5000, "formal", 2000, 0, "não")
    assert score == 575


def test_score_com_acento_no_emprego():
    assert calcular_score(3000, "autônomo", 1000, 1, "não") == calcular_score(
        3000, "autonomo", 1000, 1, "não"
    )


def test_score_nunca_negativo_faz_clamp():
    # desempregado, sem renda, com dívidas -> resultado bruto negativo -> 0
    assert calcular_score(0, "desempregado", 0, 3, "sim") == 0


def test_score_limitado_a_1000():
    # renda altíssima e despesas baixas explodiriam o score, mas é limitado a 1000
    assert calcular_score(1_000_000, "formal", 0, 0, "não") == 1000


def test_dependentes_3_ou_mais_usam_faixa_3mais():
    s3 = calcular_score(4000, "formal", 1000, 3, "não")
    s5 = calcular_score(4000, "formal", 1000, 5, "não")
    assert s3 == s5  # ambos caem na faixa "3+"


def test_emprego_invalido_levanta_erro():
    with pytest.raises(ValueError):
        calcular_score(3000, "estagiario", 1000, 0, "não")


def test_valores_negativos_levantam_erro():
    with pytest.raises(ValueError):
        calcular_score(-100, "formal", 1000, 0, "não")


# --- política de limites ----------------------------------------------------
def test_limite_maximo_por_faixa():
    assert limite_maximo_por_score(400, TABELA) == 3000.00
    assert limite_maximo_por_score(820, TABELA) == 15000.00
    assert limite_maximo_por_score(900, TABELA) == 30000.00


def test_score_fora_da_tabela_retorna_none():
    assert limite_maximo_por_score(1500, TABELA) is None


def test_aumento_aprovado_quando_dentro_do_teto():
    status, teto = avaliar_aumento_limite(650, 6000, TABELA)
    assert status == "aprovado"
    assert teto == 7000.00


def test_aumento_rejeitado_quando_acima_do_teto():
    status, teto = avaliar_aumento_limite(400, 5000, TABELA)
    assert status == "rejeitado"
    assert teto == 3000.00


def test_aumento_no_limite_exato_e_aprovado():
    status, _ = avaliar_aumento_limite(400, 3000, TABELA)
    assert status == "aprovado"
