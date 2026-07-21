# Banco Ágil — Agente Bancário Inteligente

Sistema de atendimento ao cliente de um banco digital fictício, operado por um
conjunto de agentes de IA especializados que colaboram entre si de forma
transparente para o cliente. Para quem conversa, existe um único atendente
virtual com várias habilidades: triagem e autenticação, crédito, entrevista de
crédito e câmbio.

O projeto foi construído com LangGraph (orquestração dos agentes), LangChain
(integração com LLMs e ferramentas) e Streamlit (interface de teste).

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Funcionalidades Implementadas](#funcionalidades-implementadas)
4. [Desafios Enfrentados e Soluções](#desafios-enfrentados-e-soluções)
5. [Escolhas Técnicas e Justificativas](#escolhas-técnicas-e-justificativas)
6. [Tutorial de Execução e Testes](#tutorial-de-execução-e-testes)
7. [Estrutura do Código](#estrutura-do-código)

## Visão Geral

O Banco Ágil simula uma central de atendimento inteligente. O cliente inicia a
conversa, é autenticado e, conforme a necessidade, é conduzido — de forma
implícita — ao especialista adequado:

| Agente | Responsabilidade |
|--------|------------------|
| Triagem | Recepciona, coleta CPF e data de nascimento, autentica contra `clientes.csv` e direciona. |
| Crédito | Consulta o limite disponível e processa solicitações de aumento de limite. |
| Entrevista de Crédito | Conduz uma entrevista financeira e recalcula o score do cliente. |
| Câmbio | Consulta a cotação de moedas em tempo real por meio de uma API externa. |

O ponto central de experiência exigido pelo desafio — que o cliente não perceba
as transições entre agentes — foi atendido com um padrão de transferência
(handoff) silenciosa sobre um estado de conversa compartilhado.

## Arquitetura do Sistema

### Visão macro

```
                         +--------------------------------------------+
                         |            Interface (Streamlit)            |
                         |                app.py / cli.py              |
                         +----------------------+---------------------+
                                                | (thread_id + mensagem)
                         +----------------------v---------------------+
                         |             Camada de Sessão                |
                         |               src/session.py                |
                         |   (invoca o grafo, extrai histórico/estado) |
                         +----------------------+---------------------+
                                                |
        +----------------------------------------v-------------------------------+
        |                       Grafo LangGraph (src/graph.py)                   |
        |                                                                        |
        |   START -> [roteador de entrada: vai ao agente ativo do estado]        |
        |                                                                        |
        |     +----------+   handoff   +----------+   handoff   +----------+      |
        |     | Triagem  |------------>| Crédito  |------------>|Entrevista|      |
        |     | (auth)   |             |          |<------------|          |      |
        |     +----+-----+             +----+-----+   handoff   +----------+      |
        |          |  handoff               |  handoff                           |
        |          v                        v                                    |
        |     +----------+             +----------+                              |
        |     |  Câmbio  |             |  Câmbio  |   (todos podem encerrar)      |
        |     +----------+             +----------+                              |
        +-------------------------------+----------------------------------------+
                                        |  (estado persistido por conversa)
                         +--------------v---------------+
                         |    Estado compartilhado       |
                         |    BankState (src/state.py)   |
                         |    mensagens, agente ativo,    |
                         |    cpf, autenticado, ...       |
                         +--------------+----------------+
                                        |
        +-------------------------------v---------------------------------+
        |                 Camada de domínio e dados (sem LLM)              |
        |  data_manager.py (CSV) - domain.py (score/limites) - tools/*     |
        |        clientes.csv - score_limite.csv - solicitacoes_*.csv      |
        +-----------------------------------------------------------------+
```

### Os agentes e seus fluxos

Cada agente é um agente ReAct (um LLM equipado com um conjunto restrito de
ferramentas e um prompt de sistema que define seu escopo). Eles são nós de um
`StateGraph` que compartilham o mesmo estado de conversa.

Agente de Triagem — porta de entrada. Faz a saudação, coleta CPF e data de
nascimento, autentica com a ferramenta correspondente e, ao autenticar,
identifica a necessidade já expressa pelo cliente e transfere para o agente
certo. Permite até três tentativas de autenticação; esgotadas, encerra o
atendimento de forma cordial.

Agente de Crédito — consulta o limite e processa o aumento. Ao pedir aumento, a
solicitação é registrada em `solicitacoes_aumento_limite.csv`, avaliada contra a
tabela `score_limite.csv` e, se rejeitada, o agente oferece a entrevista de
crédito.

Agente de Entrevista de Crédito — conduz cinco perguntas (renda, tipo de
emprego, despesas fixas, dependentes e dívidas), recalcula o score por uma
fórmula ponderada, persiste o novo valor em `clientes.csv` e devolve o cliente
ao crédito para nova análise.

Agente de Câmbio — busca a cotação atual de uma moeda frente ao Real usando a
AwesomeAPI (pública, sem chave) e apresenta o valor ao cliente.

### Como os dados são manipulados

Toda a persistência é isolada na camada de dados; os agentes nunca abrem
arquivos diretamente:

- `src/data_manager.py` — leitura e escrita de CSV com tratamento de erros,
  normalização de CPF e datas, escrita atômica (arquivo temporário seguido de
  substituição) e lock para escritas concorrentes.
- `src/domain.py` — regras de negócio puras (cálculo de score e política de
  limites), sem I/O e sem LLM, portanto totalmente testáveis.
- `data/` — `clientes.csv` (base de clientes), `score_limite.csv` (política de
  limites por faixa de score) e `solicitacoes_aumento_limite.csv` (gerado em
  tempo de execução).

### Estado e memória da conversa

O `BankState` estende o estado padrão do LangGraph e carrega o histórico de
mensagens e o contexto de sessão (agente ativo, cpf, autenticado, número de
tentativas, nome do cliente e sinalizador de encerramento). Um checkpointer em
memória persiste esse estado por `thread_id`, o que permite conversas de
múltiplos turnos. O roteador de entrada sempre reencaminha o novo turno para o
agente ativo, garantindo continuidade após uma transferência.

### Fórmula de score (Entrevista de Crédito)

```
score = (renda_mensal / (despesas + 1)) * 30
        + peso_emprego[tipo_emprego]        # formal:300  autônomo:200  desempregado:0
        + peso_dependentes[num_dependentes] # 0:100  1:80  2:60  3+:30
        + peso_dividas[tem_dividas]         # sim:-100  não:+100
```

O resultado é limitado ao intervalo oficial de 0 a 1000.

## Funcionalidades Implementadas

- Triagem com autenticação (CPF e data de nascimento) contra `clientes.csv`.
- Controle de até três tentativas de autenticação, com encerramento cordial após
  a terceira falha.
- Consulta de limite de crédito e score do cliente autenticado.
- Solicitação de aumento de limite com registro formal em CSV: o pedido nasce
  como `pendente` e transiciona para `aprovado` ou `rejeitado` conforme a faixa
  de score.
- Atualização do limite na base quando o pedido é aprovado.
- Oferta de entrevista de crédito quando a solicitação é rejeitada.
- Entrevista de crédito conversacional, com recálculo e persistência do score.
- Retorno automático da entrevista para o crédito, para uma nova análise.
- Câmbio via API externa (AwesomeAPI), com suporte a diversas moedas.
- Transferências implícitas entre agentes: o cliente percebe um único atendente.
- Encerramento sob demanda a qualquer momento.
- Tratamento de erros esperados (CSV ausente, API indisponível, entrada
  inválida, limite de uso do provedor) com mensagem clara ao cliente e registro
  técnico em log.
- Interface Streamlit e um CLI para testes.
- Suíte de testes automatizados cobrindo regras de negócio, camada de dados,
  sanitização de saída e integração.
- Suporte a múltiplos provedores de LLM (Groq, Google Gemini e OpenAI),
  configurável por variável de ambiente.

## Desafios Enfrentados e Soluções

Transferência implícita preservando o contexto de autenticação. O padrão
multi-agente do LangGraph usa um comando de transferência para mudar o fluxo
entre nós. Percebi, ao inspecionar o estado final da conversa, que ao sair de um
subgrafo por esse comando apenas os campos incluídos explicitamente no comando
eram persistidos no estado principal — os dados gravados pela ferramenta de
autenticação (autenticado, cpf) se perdiam, quebrando os turnos seguintes. A
solução foi fazer a ferramenta de transferência ler o estado vigente e
reencaminhar o contexto de sessão, garantindo que ele sobrevivesse à transição.

Loop de transferência entre agentes. Em testes mais longos, os agentes entravam
em um ping-pong de transferências (por exemplo, crédito e entrevista trocando o
controle repetidamente), estourando o limite de recursão do grafo sem responder
ao cliente. Resolvi em duas frentes: regras de prompt que limitam as
transferências (no máximo uma por turno e nunca de volta ao agente anterior no
mesmo turno) e, principalmente, tornando o retorno da entrevista para o crédito
determinístico — disparado pela própria ferramenta de recálculo em vez de
depender de o modelo decidir transferir. Um limite de recursão conservador
funciona como rede de segurança.

Testar orquestração dependente de LLM. A lógica com LLM é não determinística.
Separei rigorosamente as regras de negócio e o acesso a dados da camada de IA,
tornando-as testáveis por testes unitários puros. O teste de integração ponta a
ponta roda apenas quando há chave de API configurada; caso contrário, é ignorado
automaticamente, para não quebrar a suíte em ambientes sem acesso ao provedor.

Vazamento de sintaxe de ferramenta no texto. Alguns modelos, ocasionalmente,
emitem a chamada de ferramenta como texto em vez de um evento de tool call.
Adicionei um sanitizador que remove qualquer sintaxe técnica antes de exibir a
resposta, garantindo que o cliente nunca veja detalhes internos.

Robustez de dados sob concorrência. Como a interface pode ter várias sessões,
usei escrita atômica (arquivo temporário e substituição) e um lock para
serializar as gravações no CSV, evitando corromper a base.

Câmbio sem dependência de serviço pago. Em vez de Tavily ou SerpAPI, que exigem
chave, usei a AwesomeAPI de cotações, pública e gratuita, com tratamento de
timeout e indisponibilidade. Isso elimina fricção de configuração para quem for
avaliar o projeto.

## Escolhas Técnicas e Justificativas

| Decisão | Justificativa |
|---------|---------------|
| LangGraph | Modela naturalmente múltiplos agentes como um grafo de estado, com transferências e memória por conversa. É o encaixe direto para o requisito de vários agentes atuando como um único atendente. |
| Transferência via comando de grafo | Permite trocar de agente sobre um histórico de mensagens único, exatamente o comportamento de transição implícita exigido. |
| Regras de negócio determinísticas | Cálculo de score e política de limite ficam em código testado, fora do LLM. Em contexto bancário isso significa ausência de erro de cálculo e auditabilidade. |
| Groq como provedor padrão | Camada gratuita e baixa latência para demonstração. O código é agnóstico ao provedor: Groq, Gemini ou OpenAI se trocam apenas por variável de ambiente. |
| Streamlit | Interface de chat funcional com pouco código, como sugerido no desafio. |
| AwesomeAPI para câmbio | Pública e sem chave, elimina fricção de configuração para avaliação. |
| CSV com camada de acesso dedicada | Fiel ao enunciado; a camada isolada permitiria trocar por um banco real sem alterar os agentes. |
| Separação em domínio, dados, ferramentas e agentes | Responsabilidades claras, alta testabilidade e baixo acoplamento. |

## Tutorial de Execução e Testes

### Pré-requisitos

- Python 3.10 ou superior (testado em 3.13).
- Uma chave de API de LLM gratuita. A recomendada é a do Groq
  (https://console.groq.com/keys).

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

Para usar Gemini: `LLM_PROVIDER=google` e `GOOGLE_API_KEY`.
Para usar OpenAI: `LLM_PROVIDER=openai` e `OPENAI_API_KEY`.

Observação sobre a camada gratuita do Groq: o modelo padrão é o
`llama-3.3-70b-versatile`, escolhido pelo bom tool-calling, resposta limpa e um
teto de tokens por minuto (TPM) folgado — o que reduz o risco de atingir o limite
de uso durante uma demonstração ao vivo. Se você fizer muitos ensaios e esbarrar
no limite **diário**, uma alternativa com cota diária maior é
`LLM_MODEL=qwen/qwen3.6-27b` (o raciocínio interno dele é ocultado
automaticamente). A camada de LLM já reenvia a requisição algumas vezes em caso
de 429 transitório, absorvendo os picos de TPM sem expor erro ao cliente.

### 3) Executar a interface

```bash
streamlit run app.py
```

Abra o endereço indicado no navegador, clique em Iniciar atendimento e converse.
A barra lateral traz clientes de teste prontos para autenticar.

Alternativa em terminal, sem interface gráfica:

```bash
python cli.py
```

### 4) Rodar os testes

```bash
pytest -q
```

Os testes unitários (regras de negócio e camada de dados) rodam sem chave. Os
testes de integração só executam se houver uma chave configurada no `.env`; caso
contrário, são ignorados.

### Roteiro de demonstração sugerido

1. Autentique-se como Bruno (`555.666.777-88`, 02/11/1985), score 400.
2. Peça para ver o limite e, em seguida, um aumento para R$ 8.000. Com o score
   400 (teto de R$ 3.000), a solicitação é rejeitada e a entrevista é oferecida.
3. Aceite a entrevista e responda: renda **R$ 12.000**, emprego **formal**,
   despesas fixas **R$ 1.000**, **0** dependentes, **sem** dívidas. Esses valores
   elevam o score para ~860 (teto de R$ 30.000). O cliente volta ao crédito
   automaticamente.
4. O agente refaz a análise do pedido de R$ 8.000 e agora **aprova**.
5. Consulte a cotação do dólar e depois diga "pode encerrar".

> Os números da entrevista acima são calibrados para uma aprovação limpa ao
> vivo. Se quiser mostrar o caminho de rejeição persistente, mantenha uma renda
> baixa ou despesas altas: o score sobe pouco e o pedido de R$ 8.000 continua
> acima do teto da faixa.

## Estrutura do Código

```
.
├── app.py                     # Interface Streamlit (chat)
├── cli.py                     # Interface de linha de comando (teste)
├── requirements.txt
├── .env.example               # Modelo de variáveis de ambiente
├── docs/
│   └── APRESENTACAO.md        # Playbook de apresentação (roteiro, conformidade)
├── data/
│   ├── clientes.csv           # Base de clientes (CPF, nascimento, limite, score)
│   ├── score_limite.csv       # Política: faixa de score -> limite máximo
│   └── solicitacoes_aumento_limite.csv   # Gerado em tempo de execução
├── src/
│   ├── config.py              # Caminhos, variáveis de ambiente, logging
│   ├── llm.py                 # Fábrica de LLM (Groq/Gemini/OpenAI)
│   ├── state.py               # BankState (estado compartilhado)
│   ├── graph.py               # Montagem do grafo multi-agente
│   ├── session.py             # Camada de sessão (API para UI e CLI)
│   ├── data_manager.py        # Acesso a CSV (I/O, normalização, erros)
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
    ├── test_auth_tool.py      # Ferramenta de autenticação (regra das 3 tentativas)
    ├── test_exchange.py       # Câmbio: cotação e tratamento de erros (API mockada)
    ├── test_session.py        # Sanitização de saída e mensagens de erro
    └── test_integration.py    # Fluxo ponta a ponta (requer chave; senão, ignorado)
```
