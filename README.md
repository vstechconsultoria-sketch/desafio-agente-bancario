# 🏦 Banco Ágil — Agente Bancário Inteligente

Sistema de atendimento ao cliente de um banco digital fictício, operado por um
conjunto de **agentes de IA especializados** que colaboram entre si de forma
**transparente para o cliente**: para quem conversa, existe um único atendente
virtual com múltiplas habilidades (triagem/autenticação, crédito, entrevista de
crédito e câmbio).

Construído com **LangGraph** (orquestração multi-agente), **LangChain** (LLMs e
ferramentas) e **Streamlit** (interface de teste).

---

## 📑 Índice
1. [Visão Geral](#-visão-geral)
2. [Arquitetura do Sistema](#-arquitetura-do-sistema)
3. [Funcionalidades Implementadas](#-funcionalidades-implementadas)
4. [Desafios Enfrentados e Soluções](#-desafios-enfrentados-e-soluções)
5. [Escolhas Técnicas e Justificativas](#-escolhas-técnicas-e-justificativas)
6. [Tutorial de Execução e Testes](#-tutorial-de-execução-e-testes)
7. [Estrutura do Código](#-estrutura-do-código)

---

## 🎯 Visão Geral

O **Banco Ágil** simula uma central de atendimento inteligente. O cliente inicia
a conversa, é autenticado e, conforme a necessidade, é conduzido — de forma
**implícita** — ao especialista adequado:

| Agente | Responsabilidade |
|--------|------------------|
| 🤖 **Triagem** | Recepciona, coleta CPF e data de nascimento, autentica contra `clientes.csv` e direciona. |
| 💳 **Crédito** | Consulta limite disponível e processa solicitações de aumento de limite. |
| 🗣️ **Entrevista de Crédito** | Conduz uma entrevista financeira e recalcula o score do cliente. |
| 💱 **Câmbio** | Consulta a cotação de moedas em tempo real via API externa. |

O grande diferencial de UX exigido pelo desafio — que o cliente **não perceba**
as transições entre agentes — é atendido por um padrão de *handoff* silencioso
sobre um estado de conversa compartilhado.

---

## 🏗️ Arquitetura do Sistema

### Visão macro

```
                         ┌──────────────────────────────────────────┐
                         │              Interface (Streamlit)        │
                         │                  app.py / cli.py          │
                         └───────────────────┬──────────────────────┘
                                             │ (thread_id + mensagem)
                         ┌───────────────────▼──────────────────────┐
                         │            Camada de Sessão                │
                         │              src/session.py                │
                         │  (invoca o grafo, extrai histórico/estado) │
                         └───────────────────┬──────────────────────┘
                                             │
        ┌────────────────────────────────────▼─────────────────────────────────┐
        │                      Grafo LangGraph (src/graph.py)                    │
        │                                                                        │
        │   START ──▶ [roteador de entrada: vai ao agente ativo do estado]       │
        │                                                                        │
        │     ┌──────────┐   handoff   ┌──────────┐   handoff   ┌──────────┐      │
        │     │ Triagem  │────────────▶│ Crédito  │────────────▶│Entrevista│      │
        │     │ (auth)   │             │          │◀────────────│          │      │
        │     └────┬─────┘             └────┬─────┘   handoff   └──────────┘      │
        │          │  handoff               │  handoff                           │
        │          ▼                        ▼                                    │
        │     ┌──────────┐             ┌──────────┐                              │
        │     │  Câmbio  │◀────────────│  Câmbio  │   (todos podem encerrar)      │
        │     └──────────┘             └──────────┘                              │
        └──────────────────────────────┬─────────────────────────────────────────┘
                                        │  (estado persistido por thread)
                         ┌──────────────▼───────────────┐
                         │   Estado compartilhado         │
                         │   BankState (src/state.py)     │
                         │   msgs, active_agent, cpf,     │
                         │   authenticated, ...           │
                         └──────────────┬────────────────┘
                                        │
        ┌───────────────────────────────▼────────────────────────────────┐
        │                 Camada de dados / regras (sem LLM)               │
        │  data_manager.py (CSV) · domain.py (score/limites) · tools/*     │
        │        clientes.csv · score_limite.csv · solicitacoes_*.csv      │
        └─────────────────────────────────────────────────────────────────┘
```

### Os agentes e seus fluxos

Cada agente é um **ReAct agent** (`create_react_agent`) — um LLM equipado com um
conjunto restrito de **ferramentas** e um **prompt de sistema** que define seu
escopo. Eles são nós de um `StateGraph` que compartilham o mesmo estado.

**1. Agente de Triagem** — porta de entrada. Fluxo obrigatório:
saudação → coleta CPF → coleta data de nascimento → `autenticar_cliente` →
se autenticado, identifica o assunto e **transfere** para o agente certo; se
falhar, permite até **3 tentativas** no total e, esgotadas, encerra com cordialidade.

**2. Agente de Crédito** — `consultar_limite_credito` e `solicitar_aumento_limite`.
A solicitação de aumento segue exatamente o fluxo do enunciado:
1. registra um **pedido formal** em `solicitacoes_aumento_limite.csv`
   (`cpf_cliente`, `data_hora_solicitacao` ISO 8601, `limite_atual`,
   `novo_limite_solicitado`, `status_pedido`) inicialmente como **`pendente`**;
2. com o pedido montado, checa o valor contra o teto da faixa de score do cliente
   (tabela `score_limite.csv`);
3. o pedido **"caminha"** do `pendente` para o status final — **`aprovado`** se o
   score permite, **`rejeitado`** caso contrário — atualizando a mesma linha do CSV;
4. se aprovado, atualiza o limite do cliente; se rejeitado, **oferece a entrevista
   de crédito**.

**3. Agente de Entrevista de Crédito** — conduz 5 perguntas (renda, tipo de
emprego, despesas fixas, dependentes, dívidas), calcula um novo score pela
fórmula ponderada, persiste em `clientes.csv` e **conduz o cliente de volta**
ao crédito para nova análise.

**4. Agente de Câmbio** — `consultar_cotacao` busca a cotação atual de uma moeda
frente ao Real na **AwesomeAPI** (pública, sem chave) e apresenta o valor.

### Como os dados são manipulados

Toda a persistência é isolada na **camada de dados** — os agentes nunca abrem
arquivos diretamente:

- **`src/data_manager.py`** — leitura/escrita de CSV com tratamento de erros,
  normalização de CPF/datas, escrita **atômica** (arquivo temporário + `replace`)
  e **lock** para escritas concorrentes.
- **`src/domain.py`** — regras de negócio **puras** (cálculo de score e política
  de limites), sem I/O e sem LLM, portanto 100% testáveis.
- **`data/`** — `clientes.csv` (base de clientes), `score_limite.csv` (política
  de limites por faixa de score) e `solicitacoes_aumento_limite.csv` (gerado em
  runtime).

### Estado e memória da conversa

O `BankState` (estende o `AgentState` do LangGraph) carrega o histórico de
mensagens **e** o contexto de sessão (`active_agent`, `cpf`, `authenticated`,
`auth_attempts`, `client_name`, `ended`). Um **checkpointer** (`MemorySaver`)
persiste esse estado por `thread_id`, permitindo conversas multi-turno. O
roteador de entrada sempre reencaminha o novo turno para o `active_agent`,
garantindo continuidade após um handoff.

### Fórmula de score (Entrevista de Crédito)

```
score = (renda_mensal / (despesas + 1)) * 30
        + peso_emprego[tipo_emprego]        # formal:300 · autônomo:200 · desempregado:0
        + peso_dependentes[num_dependentes] # 0:100 · 1:80 · 2:60 · 3+:30
        + peso_dividas[tem_dividas]         # sim:-100 · não:+100
```
O resultado é limitado (clamp) ao intervalo oficial **[0, 1000]**.

---

## ✅ Funcionalidades Implementadas

- [x] **Triagem com autenticação** (CPF + data de nascimento) contra `clientes.csv`.
- [x] **Controle de tentativas** — até 3 tentativas; encerramento cordial após falha.
- [x] **Consulta de limite** de crédito e score do cliente autenticado.
- [x] **Solicitação de aumento de limite** com registro formal em CSV (nasce
      `pendente` e transiciona para `aprovado`/`rejeitado`) por faixa de score.
- [x] **Atualização do limite** na base quando aprovado.
- [x] **Oferta de entrevista** quando a solicitação é rejeitada.
- [x] **Entrevista de crédito** conversacional com recálculo e persistência do score.
- [x] **Retorno automático** da entrevista para o crédito (nova análise).
- [x] **Câmbio** via API externa (AwesomeAPI), com suporte a USD, EUR, GBP, etc.
- [x] **Handoffs implícitos** — o cliente percebe um único atendente.
- [x] **Encerramento sob demanda** — ferramenta `encerrar_atendimento` a qualquer momento.
- [x] **Tratamento de erros** — CSV ausente, API indisponível/timeout, entradas
      inválidas — sempre com mensagem amigável e log técnico para análise posterior.
- [x] **UI Streamlit** + **CLI** para testes.
- [x] **Suíte de testes** (33 testes; lógica de negócio, dados, sanitização e integração).
- [x] **Multi-provedor de LLM** — Groq (padrão), Google Gemini ou OpenAI, via `.env`.

---

## 🧩 Desafios Enfrentados e Soluções

**1. Handoff implícito preservando o contexto de autenticação.**
O padrão de multi-agente do LangGraph usa `Command(goto=..., graph=PARENT)` para
transferir o fluxo. Descobri (via um teste de fumaça com um LLM "scriptado") que,
ao sair de um subgrafo por esse comando, **apenas os campos incluídos no `update`
do comando são persistidos no estado pai** — os campos gravados localmente pela
ferramenta de autenticação (`authenticated`, `cpf`) se perdiam, quebrando os
turnos seguintes. **Solução:** a ferramenta de handoff lê o estado vigente
(`InjectedState`) e **reencaminha explicitamente** o contexto de sessão no
`update`, garantindo que ele sobreviva à transição e ao checkpoint. Esse bug foi
encontrado justamente porque validei o estado final, e não apenas a resposta.

**2. Testar orquestração dependente de LLM sem gastar chamadas/credenciais.**
A lógica com LLM é não-determinística. **Solução:** separei rigorosamente as
regras de negócio (`domain.py`) e o acesso a dados (`data_manager.py`) da camada
de IA, tornando-as testáveis por *unit tests* puros; e criei um **modelo
scriptado** (um `BaseChatModel` falso que emite tool-calls pré-definidos) para
validar o mecanismo de handoff ponta a ponta, sem rede. O teste de integração
real fica disponível, porém é **pulado automaticamente** quando não há chave.

**3. Manter cada agente dentro do seu escopo.**
Prompts restritos por agente + conjuntos de ferramentas mínimos por nó. Um agente
só consegue fazer aquilo para o qual tem ferramenta; qualquer assunto fora do
escopo vira um handoff.

**4. Robustez de dados (concorrência e escrita segura).**
A UI pode ter múltiplas sessões. **Solução:** escrita **atômica** (tmp + replace)
e um `Lock` para serializar gravações no CSV, evitando corromper a base.

**5. Câmbio sem depender de chave paga.**
Em vez de Tavily/SerpAPI (que exigem chave), usei a **AwesomeAPI** de cotações,
pública e gratuita, com tratamento de *timeout* e indisponibilidade.

---

## 🛠️ Escolhas Técnicas e Justificativas

| Decisão | Justificativa |
|---------|---------------|
| **LangGraph** | Modela naturalmente múltiplos agentes como um grafo de estado, com *handoffs* e memória por thread (*checkpointer*). É o encaixe direto para "vários agentes, um atendente". |
| **Padrão *swarm* (handoff via `Command`)** | Permite transferências implícitas sobre um histórico de mensagens único — exatamente o requisito de UX. |
| **Ferramentas determinísticas** | Regras de negócio (score, limites, CSV) ficam em código testável; o LLM apenas conversa e decide *quando* chamar cada ferramenta. Reduz alucinação e facilita auditoria. |
| **Groq como LLM padrão** | *Free tier* generoso e latência baixa (bom para demo). O código é **agnóstico ao provedor** — troca-se Groq/Gemini/OpenAI apenas no `.env`. |
| **Streamlit** | UI de chat funcional com pouquíssimo código, como sugerido no desafio. |
| **AwesomeAPI (câmbio)** | Pública e sem chave, elimina fricção de setup para quem for avaliar. |
| **CSV + camada de acesso dedicada** | Fiel ao enunciado, e a camada isolada permitiria trocar por um banco real sem tocar nos agentes. |
| **Separação `domain` / `data_manager` / `tools` / `agents`** | Responsabilidades claras, alta testabilidade e baixo acoplamento. |

---

## 🚀 Tutorial de Execução e Testes

### Pré-requisitos
- Python 3.10+ (testado em 3.13).
- Uma chave de API de LLM gratuita (recomendado: **Groq** — https://console.groq.com/keys).

### 1) Clonar e criar o ambiente

```bash
git clone <url-do-repositorio>
cd <repositorio>

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2) Configurar as credenciais

```bash
cp .env.example .env      # no Windows: copy .env.example .env
```
Edite o `.env` e preencha a chave do provedor escolhido, por exemplo:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=sua_chave_aqui
```
> Para usar Gemini: `LLM_PROVIDER=google` + `GOOGLE_API_KEY`.
> Para usar OpenAI: `LLM_PROVIDER=openai` + `OPENAI_API_KEY`.

### 3) Executar a interface

```bash
streamlit run app.py
```
Abra o navegador no endereço indicado, clique em **Iniciar atendimento** e
converse. A barra lateral traz **clientes de teste** prontos para autenticar.

Alternativa em terminal (sem UI):
```bash
python cli.py
```

### 4) Rodar os testes

```bash
pytest -q
```
- **Testes unitários** (regras de negócio e camada de dados) rodam sem chave.
- **Testes de integração** (fluxo real com LLM) são executados apenas se houver
  uma chave configurada no `.env`; caso contrário, são pulados.

### Roteiro de demonstração sugerido
1. Autentique-se como **Bruno** (`555.666.777-88`, 02/11/1985) — score 400.
2. Peça para **ver seu limite** e depois um **aumento para R$ 8.000**.
   → A solicitação é **rejeitada** (score insuficiente) e a **entrevista** é oferecida.
3. **Aceite a entrevista**, informe uma renda alta e emprego formal.
   → O **score é recalculado** e você volta ao crédito.
4. Peça o aumento novamente → agora pode ser **aprovado**.
5. Peça a **cotação do dólar** e depois diga **"pode encerrar"**.

---

## 📂 Estrutura do Código

```
.
├── app.py                     # Interface Streamlit (chat)
├── cli.py                     # Interface de linha de comando (teste)
├── requirements.txt
├── .env.example               # Modelo de variáveis de ambiente
├── data/
│   ├── clientes.csv           # Base de clientes (CPF, nascimento, limite, score)
│   ├── score_limite.csv       # Política: faixa de score -> limite máximo
│   └── solicitacoes_aumento_limite.csv   # Gerado em runtime
├── src/
│   ├── config.py              # Caminhos, env, logging
│   ├── llm.py                 # Fábrica de LLM (Groq/Gemini/OpenAI)
│   ├── state.py               # BankState (estado compartilhado)
│   ├── graph.py               # Montagem do grafo multi-agente
│   ├── session.py             # Camada de sessão (API para UI/CLI)
│   ├── data_manager.py        # Acesso a CSV (I/O + normalização + erros)
│   ├── domain.py              # Regras puras (score e limites)
│   ├── agents/
│   │   └── prompts.py         # Prompts de sistema de cada agente
│   └── tools/
│       ├── auth.py            # Autenticação (triagem)
│       ├── credit.py          # Consulta e aumento de limite
│       ├── interview.py       # Recálculo de score
│       ├── exchange.py        # Cotação de moedas (API externa)
│       ├── handoff.py         # Transferências implícitas entre agentes
│       └── common.py          # Encerramento do atendimento
└── tests/
    ├── test_domain.py         # Score e política de limites
    ├── test_data_manager.py   # Autenticação e escrita em CSV
    └── test_integration.py    # Fluxo ponta a ponta (requer chave; senão, pulado)
```

---

<p align="center"><i>Desenvolvido como desafio técnico — Banco Ágil.</i></p>
