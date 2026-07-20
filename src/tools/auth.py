"""Ferramenta de autenticação usada pelo Agente de Triagem."""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src import config
from src.data_manager import (
    DataAccessError,
    autenticar_cliente,
    normalizar_cpf,
    normalizar_data,
)


@tool("autenticar_cliente")
def autenticar_cliente_tool(
    cpf: str,
    data_nascimento: str,
    state: Annotated[dict, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Valida o CPF e a data de nascimento do cliente contra a base de dados.

    Chame esta ferramenta APENAS quando já tiver coletado os dois dados.
    A data pode vir como DD/MM/AAAA ou AAAA-MM-DD.
    Retorna o resultado da autenticação e controla o número de tentativas.
    """
    cpf_limpo = str(cpf or "").strip()
    data_limpa = str(data_nascimento or "").strip()

    # Blindagem: não consome uma tentativa quando falta um dado essencial. O
    # modelo pode chamar a ferramenta cedo demais (por exemplo, só com o CPF) ou
    # a data pode vir num formato irreconhecível. Nesses casos pedimos o dado de
    # novo, sem penalizar o cliente com uma das (poucas) tentativas de autenticação.
    if not cpf_limpo or not data_limpa or normalizar_data(data_limpa) is None:
        if not cpf_limpo and not data_limpa:
            faltando = "o CPF e a data de nascimento"
        elif not cpf_limpo:
            faltando = "o CPF"
        elif not data_limpa:
            faltando = "a data de nascimento (dd/mm/aaaa)"
        else:  # data presente, porém em formato não reconhecido
            faltando = "a data de nascimento num formato válido (dd/mm/aaaa)"
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=(
                            f"DADOS_INCOMPLETOS: ainda falta {faltando}. Peça esse "
                            "dado ao cliente de forma cordial. Isto NÃO conta como "
                            "tentativa de autenticação."
                        ),
                        tool_call_id=tool_call_id,
                        name="autenticar_cliente",
                    )
                ]
            }
        )

    tentativas = int(state.get("auth_attempts", 0)) + 1

    try:
        cliente = autenticar_cliente(cpf_limpo, data_limpa)
    except DataAccessError as exc:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"ERRO_TECNICO: {exc}",
                        tool_call_id=tool_call_id,
                        name="autenticar_cliente",
                    )
                ]
            }
        )

    if cliente is not None:
        return Command(
            update={
                "authenticated": True,
                "cpf": normalizar_cpf(cpf),
                "client_name": cliente.get("nome"),
                "auth_attempts": tentativas,
                "messages": [
                    ToolMessage(
                        content=(
                            "AUTENTICADO com sucesso. "
                            f"Cliente: {cliente.get('nome')}. "
                            "Agora identifique a necessidade e direcione o atendimento."
                        ),
                        tool_call_id=tool_call_id,
                        name="autenticar_cliente",
                    )
                ],
            }
        )

    # Falha de autenticação (dados não conferem).
    restantes = config.MAX_AUTH_ATTEMPTS - tentativas
    if restantes > 0:
        conteudo = (
            f"FALHA na autenticação (tentativa {tentativas} de "
            f"{config.MAX_AUTH_ATTEMPTS}). Restam {restantes} tentativa(s). "
            "Peça gentilmente que o cliente confirme CPF e data de nascimento."
        )
    else:
        conteudo = (
            "FALHA na autenticação e LIMITE DE TENTATIVAS esgotado. "
            "Informe de forma cordial que não foi possível autenticar e use a "
            "ferramenta 'encerrar_atendimento' para finalizar."
        )

    return Command(
        update={
            "authenticated": False,
            "auth_attempts": tentativas,
            "messages": [
                ToolMessage(
                    content=conteudo,
                    tool_call_id=tool_call_id,
                    name="autenticar_cliente",
                )
            ],
        }
    )
