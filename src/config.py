"""Configuração central do projeto: caminhos, logging e variáveis de ambiente."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis do arquivo .env (se existir) para o ambiente do processo.
load_dotenv()

# --- Caminhos ---------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CLIENTES_CSV = DATA_DIR / "clientes.csv"
SCORE_LIMITE_CSV = DATA_DIR / "score_limite.csv"
SOLICITACOES_CSV = DATA_DIR / "solicitacoes_aumento_limite.csv"

# --- LLM --------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2") or "0.2")

# Modelos padrão por provedor (usados quando LLM_MODEL não é informado).
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "google": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
}

# --- Câmbio -----------------------------------------------------------------
EXCHANGE_API_URL = os.getenv(
    "EXCHANGE_API_URL", "https://economia.awesomeapi.com.br/last"
).rstrip("/")

# --- Regras de negócio ------------------------------------------------------
MAX_AUTH_ATTEMPTS = 3  # 1 tentativa inicial + 2 novas tentativas

# Limite de passos internos por turno do grafo. Dá folga para fluxos legítimos
# (autenticar -> transferir -> consultar -> responder, ~7-8 passos) mas corta
# cedo eventuais loops de transferência entre agentes, protegendo o orçamento
# de tokens do provedor.
RECURSION_LIMIT = 20


# --- Logging ----------------------------------------------------------------
def _build_logger() -> logging.Logger:
    """Configura um logger para registrar erros técnicos sem poluir a UI."""
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("banco_agil")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(logs_dir / "banco_agil.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger


logger = _build_logger()
