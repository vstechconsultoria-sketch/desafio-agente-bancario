"""Camada de acesso a dados (CSV).

Centraliza toda a leitura e escrita de arquivos CSV para que os agentes/tools
não manipulem arquivos diretamente. Cada função trata erros esperados (arquivo
ausente, dado malformado) e registra falhas técnicas no log, propagando um
``DataAccessError`` com mensagem amigável.
"""
from __future__ import annotations

import csv
import threading
from datetime import datetime, timezone
from typing import Optional

from src import config
from src.config import logger

# Serializa escritas concorrentes (a UI Streamlit pode ter múltiplas sessões).
_write_lock = threading.Lock()


class DataAccessError(RuntimeError):
    """Falha ao ler/gravar dados. Mensagem já é amigável ao cliente."""


# --- Normalização de entrada ------------------------------------------------
def normalizar_cpf(cpf: str) -> str:
    """Remove máscara do CPF, mantendo apenas dígitos."""
    return "".join(ch for ch in str(cpf) if ch.isdigit())


def normalizar_data(data: str) -> Optional[str]:
    """Converte diferentes formatos de data para ISO (YYYY-MM-DD).

    Aceita DD/MM/AAAA, DD-MM-AAAA e AAAA-MM-DD. Retorna ``None`` se não
    reconhecer o formato (entrada inválida do usuário).
    """
    data = str(data).strip()
    formatos = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y")
    for fmt in formatos:
        try:
            return datetime.strptime(data, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# --- Clientes ---------------------------------------------------------------
def _ler_clientes() -> list[dict]:
    try:
        with open(config.CLIENTES_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError as exc:
        logger.error("Base de clientes não encontrada: %s", exc)
        raise DataAccessError(
            "Não consegui acessar a base de clientes no momento. "
            "Por favor, tente novamente em instantes."
        ) from exc


def buscar_cliente(cpf: str) -> Optional[dict]:
    """Retorna o registro do cliente pelo CPF, ou ``None`` se não existir."""
    cpf_norm = normalizar_cpf(cpf)
    for linha in _ler_clientes():
        if normalizar_cpf(linha.get("cpf", "")) == cpf_norm:
            return linha
    return None


def autenticar_cliente(cpf: str, data_nascimento: str) -> Optional[dict]:
    """Valida CPF + data de nascimento contra a base.

    Retorna o registro do cliente em caso de sucesso, ou ``None`` se os dados
    não conferem.
    """
    data_norm = normalizar_data(data_nascimento)
    if data_norm is None:
        return None

    cliente = buscar_cliente(cpf)
    if cliente is None:
        return None

    if normalizar_data(cliente.get("data_nascimento", "")) == data_norm:
        return cliente
    return None


def atualizar_score(cpf: str, novo_score: int) -> None:
    """Atualiza o score de um cliente na base, reescrevendo o CSV com segurança."""
    cpf_norm = normalizar_cpf(cpf)
    with _write_lock:
        linhas = _ler_clientes()
        encontrado = False
        for linha in linhas:
            if normalizar_cpf(linha.get("cpf", "")) == cpf_norm:
                linha["score"] = str(int(novo_score))
                encontrado = True
                break
        if not encontrado:
            raise DataAccessError("Cliente não encontrado para atualização de score.")
        _reescrever_clientes(linhas)
    logger.info("Score atualizado cpf=%s novo_score=%s", cpf_norm, novo_score)


def atualizar_limite(cpf: str, novo_limite: float) -> None:
    """Atualiza o limite de crédito de um cliente na base."""
    cpf_norm = normalizar_cpf(cpf)
    with _write_lock:
        linhas = _ler_clientes()
        for linha in linhas:
            if normalizar_cpf(linha.get("cpf", "")) == cpf_norm:
                linha["limite_credito"] = f"{float(novo_limite):.2f}"
                _reescrever_clientes(linhas)
                logger.info(
                    "Limite atualizado cpf=%s novo_limite=%.2f", cpf_norm, novo_limite
                )
                return
        raise DataAccessError("Cliente não encontrado para atualização de limite.")


def _reescrever_clientes(linhas: list[dict]) -> None:
    campos = ["cpf", "data_nascimento", "nome", "limite_credito", "score"]
    tmp = config.CLIENTES_CSV.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(linhas)
    tmp.replace(config.CLIENTES_CSV)  # escrita atômica


# --- Tabela score x limite --------------------------------------------------
def ler_tabela_score_limite() -> list[dict]:
    try:
        with open(config.SCORE_LIMITE_CSV, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError as exc:
        logger.error("Tabela score_limite não encontrada: %s", exc)
        raise DataAccessError(
            "Não consegui consultar a política de limites agora. "
            "Tente novamente em instantes."
        ) from exc


# --- Solicitações de aumento de limite --------------------------------------
_SOLICITACAO_CAMPOS = [
    "cpf_cliente",
    "data_hora_solicitacao",
    "limite_atual",
    "novo_limite_solicitado",
    "status_pedido",
]


def registrar_solicitacao_aumento(
    cpf_cliente: str,
    limite_atual: float,
    novo_limite_solicitado: float,
    status_pedido: str = "pendente",
) -> dict:
    """Anexa uma solicitação formal de aumento de limite ao CSV de solicitações.

    Cria o arquivo com cabeçalho caso ainda não exista. Retorna o registro
    gravado (incluindo o timestamp ISO 8601).
    """
    registro = {
        "cpf_cliente": normalizar_cpf(cpf_cliente),
        "data_hora_solicitacao": datetime.now(timezone.utc).isoformat(),
        "limite_atual": f"{float(limite_atual):.2f}",
        "novo_limite_solicitado": f"{float(novo_limite_solicitado):.2f}",
        "status_pedido": status_pedido,
    }

    with _write_lock:
        existe = config.SOLICITACOES_CSV.exists()
        try:
            with open(
                config.SOLICITACOES_CSV, "a", newline="", encoding="utf-8"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=_SOLICITACAO_CAMPOS)
                if not existe:
                    writer.writeheader()
                writer.writerow(registro)
        except OSError as exc:
            logger.error("Falha ao registrar solicitação: %s", exc)
            raise DataAccessError(
                "Não consegui registrar sua solicitação agora. "
                "Tente novamente em instantes."
            ) from exc

    logger.info(
        "Solicitação registrada cpf=%s novo_limite=%.2f status=%s",
        registro["cpf_cliente"],
        novo_limite_solicitado,
        status_pedido,
    )
    return registro


def _ler_solicitacoes() -> list[dict]:
    if not config.SOLICITACOES_CSV.exists():
        return []
    with open(config.SOLICITACOES_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def atualizar_status_solicitacao(
    cpf_cliente: str,
    data_hora_solicitacao: str,
    novo_status: str,
) -> None:
    """Atualiza o ``status_pedido`` de uma solicitação já registrada.

    Localiza a linha pelo par (cpf_cliente, data_hora_solicitacao), que é único,
    e a reescreve com o novo status. Usado para levar um pedido de 'pendente'
    para 'aprovado' ou 'rejeitado', preservando a trilha de auditoria.
    """
    cpf_norm = normalizar_cpf(cpf_cliente)
    with _write_lock:
        linhas = _ler_solicitacoes()
        encontrado = False
        for linha in linhas:
            if (
                linha.get("cpf_cliente") == cpf_norm
                and linha.get("data_hora_solicitacao") == data_hora_solicitacao
            ):
                linha["status_pedido"] = novo_status
                encontrado = True
                break
        if not encontrado:
            raise DataAccessError("Solicitação não encontrada para atualização de status.")

        tmp = config.SOLICITACOES_CSV.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_SOLICITACAO_CAMPOS)
            writer.writeheader()
            writer.writerows(linhas)
        tmp.replace(config.SOLICITACOES_CSV)  # escrita atômica

    logger.info(
        "Status da solicitação atualizado cpf=%s data=%s status=%s",
        cpf_norm,
        data_hora_solicitacao,
        novo_status,
    )
