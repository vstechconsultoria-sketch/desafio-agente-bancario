"""Interface Streamlit para simular um atendimento completo do Banco Ágil.

Execute com:  streamlit run app.py
"""
from __future__ import annotations

import uuid

import streamlit as st

from src import config
from src.llm import LLMConfigError
from src.session import enviar_mensagem, obter_historico, get_graph

st.set_page_config(page_title="Banco Ágil — Atendimento", page_icon="🏦")

MENSAGEM_ABERTURA = "Olá! Vim ao atendimento."


# --- Estado de sessão -------------------------------------------------------
def _reiniciar():
    st.session_state.thread_id = uuid.uuid4().hex
    st.session_state.encerrado = False
    st.session_state.iniciado = False


if "thread_id" not in st.session_state:
    _reiniciar()


# --- Barra lateral ----------------------------------------------------------
with st.sidebar:
    st.header("🏦 Banco Ágil")
    st.caption("Atendimento inteligente multi-agente")

    st.subheader("Configuração")
    st.write(f"**Provedor LLM:** `{config.LLM_PROVIDER}`")
    st.write(f"**Modelo:** `{config.LLM_MODEL or config.DEFAULT_MODELS.get(config.LLM_PROVIDER, '—')}`")

    st.subheader("Clientes para teste")
    st.caption("Use estes dados para autenticar (CPF · nascimento):")
    st.markdown(
        "- **Ana** · `111.222.333-44` · 15/05/1990 (score 650)\n"
        "- **Bruno** · `555.666.777-88` · 02/11/1985 (score 400)\n"
        "- **Carla** · `999.888.777-66` · 20/01/2000 (score 820)\n"
        "- **Diego** · `123.456.789-00` · 30/07/1995 (score 300)\n"
        "- **Eduarda** · `000.111.222-33` · 10/03/1978 (score 720)"
    )
    st.caption(
        "Dica: Bruno tem score baixo — peça um aumento alto para ver a rejeição "
        "e a entrevista de crédito."
    )

    if st.button("🔄 Reiniciar atendimento", use_container_width=True):
        _reiniciar()
        st.rerun()


st.title("🏦 Atendimento Banco Ágil")

# --- Verificação de configuração do LLM -------------------------------------
try:
    get_graph()
except LLMConfigError as exc:
    st.error(
        "⚙️ **Configuração pendente do LLM.**\n\n"
        f"{exc}\n\n"
        "Copie `.env.example` para `.env`, preencha a chave do provedor e "
        "reinicie o app."
    )
    st.stop()


# --- Início do atendimento (saudação do agente) -----------------------------
if not st.session_state.iniciado:
    st.info("Clique abaixo para iniciar a conversa com o atendente virtual.")
    if st.button("▶️ Iniciar atendimento", type="primary"):
        with st.spinner("Conectando ao atendimento..."):
            resultado = enviar_mensagem(st.session_state.thread_id, MENSAGEM_ABERTURA)
        st.session_state.iniciado = True
        st.session_state.encerrado = resultado["encerrado"]
        st.rerun()
    st.stop()


# --- Renderização do histórico ----------------------------------------------
for msg in obter_historico(st.session_state.thread_id):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --- Entrada do usuário -----------------------------------------------------
if st.session_state.encerrado:
    st.success("✅ Atendimento encerrado. Clique em **Reiniciar atendimento** para começar de novo.")
else:
    entrada = st.chat_input("Digite sua mensagem...")
    if entrada:
        with st.chat_message("user"):
            st.markdown(entrada)
        with st.chat_message("assistant"):
            with st.spinner("Digitando..."):
                resultado = enviar_mensagem(st.session_state.thread_id, entrada)
            st.markdown(resultado["resposta"])
        st.session_state.encerrado = resultado["encerrado"]
        st.rerun()
