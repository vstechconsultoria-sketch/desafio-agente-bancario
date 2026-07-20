"""Fábrica de modelos de linguagem, agnóstica ao provedor.

Permite trocar entre Groq, Google Gemini e OpenAI apenas via variáveis de
ambiente, sem alterar o código dos agentes.
"""
from __future__ import annotations

from functools import lru_cache

from src import config
from src.config import logger


class LLMConfigError(RuntimeError):
    """Erro de configuração do provedor de LLM (ex.: chave ausente)."""


def _resolve_model() -> str:
    return config.LLM_MODEL or config.DEFAULT_MODELS.get(config.LLM_PROVIDER, "")


@lru_cache(maxsize=1)
def get_llm():
    """Instancia o chat model do provedor configurado.

    O resultado é memoizado para reutilizar a mesma conexão entre os agentes.
    Lança ``LLMConfigError`` com mensagem clara quando algo está mal configurado.
    """
    provider = config.LLM_PROVIDER
    model = _resolve_model()
    temperature = config.LLM_TEMPERATURE

    logger.info("Inicializando LLM provider=%s model=%s", provider, model)

    try:
        if provider == "groq":
            from langchain_groq import ChatGroq

            if not _has_env("GROQ_API_KEY"):
                raise LLMConfigError(
                    "GROQ_API_KEY não configurada. Defina-a no arquivo .env."
                )
            extra = {}
            # Modelos qwen3 raciocinam em voz alta e, sem isso, despejam blocos
            # <think> no conteúdo — inaceitável no chat visto pelo cliente.
            # "hidden" mantém o raciocínio interno e devolve só a resposta final.
            if model.startswith("qwen"):
                extra["reasoning_format"] = "hidden"
            # A camada gratuita da Groq tem um teto de tokens por minuto baixo.
            # Em turnos longos do multi-agente ele pode ser tocado; o cliente
            # devolve o cabeçalho "retry-after" (~poucos segundos), então
            # aumentamos as retentativas para absorver o 429 de forma invisível
            # em vez de expor uma falha ao cliente no meio da conversa.
            return ChatGroq(
                model=model,
                temperature=temperature,
                max_retries=6,
                **extra,
            )

        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI

            if not _has_env("GOOGLE_API_KEY"):
                raise LLMConfigError(
                    "GOOGLE_API_KEY não configurada. Defina-a no arquivo .env."
                )
            return ChatGoogleGenerativeAI(model=model, temperature=temperature)

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            if not _has_env("OPENAI_API_KEY"):
                raise LLMConfigError(
                    "OPENAI_API_KEY não configurada. Defina-a no arquivo .env."
                )
            return ChatOpenAI(model=model, temperature=temperature)

        raise LLMConfigError(
            f"Provedor de LLM desconhecido: '{provider}'. "
            "Use 'groq', 'google' ou 'openai'."
        )
    except ImportError as exc:  # pacote do provedor não instalado
        raise LLMConfigError(
            f"Dependência do provedor '{provider}' ausente: {exc}. "
            "Rode 'pip install -r requirements.txt'."
        ) from exc


def _has_env(name: str) -> bool:
    import os

    return bool(os.getenv(name, "").strip())
