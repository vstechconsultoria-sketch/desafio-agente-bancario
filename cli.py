"""CLI simples para testar o atendimento no terminal (sem Streamlit).

Uso:  python cli.py
"""
from __future__ import annotations

import uuid

from src.llm import LLMConfigError
from src.session import enviar_mensagem, get_graph


def main() -> None:
    print("=" * 60)
    print(" Banco Ágil — Atendimento (CLI de teste)")
    print(" Digite 'sair' para encerrar manualmente.")
    print("=" * 60)

    try:
        get_graph()
    except LLMConfigError as exc:
        print(f"\n[ERRO DE CONFIGURAÇÃO] {exc}")
        print("Configure o arquivo .env e tente novamente.")
        return

    thread_id = uuid.uuid4().hex

    # Saudação inicial do agente.
    resultado = enviar_mensagem(thread_id, "Olá! Vim ao atendimento.")
    print(f"\nAtendente: {resultado['resposta']}\n")

    while not resultado["encerrado"]:
        try:
            entrada = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAtendimento interrompido.")
            break
        if not entrada:
            continue
        if entrada.lower() in {"sair", "exit", "quit"}:
            entrada = "Quero encerrar o atendimento, por favor."

        resultado = enviar_mensagem(thread_id, entrada)
        print(f"\nAtendente: {resultado['resposta']}\n")

    print("--- Atendimento encerrado. ---")


if __name__ == "__main__":
    main()
