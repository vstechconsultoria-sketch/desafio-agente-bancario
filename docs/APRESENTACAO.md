# Playbook de Apresentação — Banco Ágil

Guia completo para a apresentação técnica do desafio. A ordem abaixo já é a
sequência sugerida de fala. Cada seção diz **o que mostrar** e **o que falar**.

Índice:
1. Estrutura da apresentação (roteiro de ~15 min)
2. Pitch de abertura
3. Conformidade com a especificação (mapa requisito → implementação)
4. Passeio pelo código (o que abrir na tela)
5. Roteiro de demonstração ao vivo
6. Pontos de fala sobre a arquitetura
7. Desafios técnicos resolvidos
8. Perguntas prováveis da banca
9. Checklist pré-apresentação

---

## 1. Estrutura da apresentação (~15 min)

| Tempo | Bloco | O que fazer |
|------|-------|-------------|
| 1 min | **Abertura** | Diga o problema e o pitch (seção 2). Uma frase sobre a stack. |
| 3 min | **Arquitetura** | Mostre o diagrama do README. Explique o padrão swarm, os 4 agentes, o estado compartilhado e a separação IA / domínio / dados (seção 6). |
| 3 min | **Passeio pelo código** | Abra 4 arquivos-chave e ligue cada um a um requisito (seção 4). |
| 5 min | **Demo ao vivo** | Rode os fluxos conforme a especificação (seção 5). É o coração da apresentação. |
| 2 min | **Conformidade + qualidade** | Rode `pytest -q` (36 testes verdes) e passe o olho no mapa de conformidade (seção 3). Mencione o tratamento de erros. |
| 1 min | **Desafios + fecho** | Conte 1–2 desafios técnicos como história (seção 7) e abra para perguntas. |

Ideia-guia: **para cada requisito do enunciado, mostrar onde ele vive no código e
vê-lo funcionando na demo.** É isso que demonstra domínio.

---

## 2. Pitch de abertura (30 segundos)

> "O Banco Ágil é uma central de atendimento de um banco digital operada por
> vários agentes de IA especializados — triagem/autenticação, crédito, entrevista
> de crédito e câmbio. A sacada é que, para o cliente, existe **um único
> atendente**: as transferências entre os especialistas acontecem de forma
> invisível, sobre um mesmo histórico de conversa. Construído com LangGraph,
> LangChain e Streamlit, com as regras de negócio bancárias isoladas do LLM para
> garantir cálculo correto e auditável."

---

## 3. Conformidade com a especificação

O quadro abaixo mapeia **cada exigência do enunciado** ao ponto do código e à
forma de demonstrar. Serve tanto para você se orientar quanto para responder
"onde está X?" na hora.

### Agente de Triagem
| Requisito | Onde está | Como demonstrar |
|-----------|-----------|-----------------|
| Saudação inicial | `agents/prompts.py` (TRIAGEM_PROMPT) | Primeira mensagem do atendente |
| Coleta CPF e data | TRIAGEM_PROMPT (um dado por vez) | Demo Fluxo A/B |
| Autenticação vs `clientes.csv` | `tools/auth.py` + `data_manager.autenticar_cliente` | Autenticar Ana/Bruno |
| Só direciona após autenticar | TRIAGEM_PROMPT ("nunca prossiga sem autenticação") | Tentar pedir algo antes de autenticar |
| Identifica assunto e redireciona | TRIAGEM_PROMPT + ferramentas de handoff | Fluxo A (vai p/ câmbio), Fluxo B (vai p/ crédito) |
| Até 3 tentativas, encerra na 3ª falha | `config.MAX_AUTH_ATTEMPTS=3` + `tools/auth.py` | Errar a data 3× (opcional) |

### Agente de Crédito
| Requisito | Onde está | Como demonstrar |
|-----------|-----------|-----------------|
| Consulta de limite | `tools/credit.py::consultar_limite_credito` | Bruno: "qual meu limite?" |
| Cliente informa novo limite desejado | CREDITO_PROMPT | "quero aumentar para 8000" |
| Gera pedido em `solicitacoes_aumento_limite.csv` | `data_manager.registrar_solicitacao_aumento` | Abrir o CSV depois da demo |
| Colunas exatas: cpf, data_hora (ISO 8601), limite_atual, novo_limite, status | `_SOLICITACAO_CAMPOS` em `data_manager.py` | Mostrar o cabeçalho do CSV |
| Pedido nasce 'pendente' e caminha p/ 'aprovado'/'rejeitado' | `credit.py` (registra pendente → avalia → atualiza status) | `test_transicao_de_status...` |
| Checagem contra `score_limite.csv` | `domain.avaliar_aumento_limite` | Aprovação vs rejeição na demo |
| Se rejeitado, oferece entrevista; senão encerra/redireciona | CREDITO_PROMPT | Fluxo B |

### Agente de Entrevista de Crédito
| Requisito | Onde está | Como demonstrar |
|-----------|-----------|-----------------|
| Perguntas: renda, emprego, despesas, dependentes, dívidas | ENTREVISTA_PROMPT (uma por vez) | Fluxo B |
| Novo score de 0 a 1000 | `domain.calcular_score` (com clamp) | `test_score_limitado_a_1000` |
| Fórmula ponderada com os pesos do enunciado | `domain.py` (pesos idênticos) | Mostrar `domain.py` lado a lado com o enunciado |
| Atualiza score em `clientes.csv` | `data_manager.atualizar_score` | Fluxo B: score muda de 400 → 860 |
| Volta ao crédito para nova análise | `tools/interview.py` (`Command(goto="credito")`) | Fluxo B: reanálise automática |

### Agente de Câmbio
| Requisito | Onde está | Como demonstrar |
|-----------|-----------|-----------------|
| Cotação via API externa | `tools/exchange.py` (AwesomeAPI) | Fluxo A |
| Dólar por padrão, ou outra moeda | `_ALIASES` (dólar, euro, libra, bitcoin, peso) | "cotação do dólar", depois "e o euro?" |
| Apresenta a cotação | CAMBIO_PROMPT | Fluxo A |
| Encerra cordialmente | `tools/common.py::encerrar_atendimento` | "era só isso" |

### Regras gerais
| Requisito | Onde está |
|-----------|-----------|
| Encerramento a qualquer momento | `tools/common.py::encerrar_atendimento` (todos os agentes têm) |
| Tom respeitoso, sem repetição | `REGRAS_GERAIS` em `prompts.py` |
| Não atuar fora do escopo | Prompt de cada agente + conjunto restrito de ferramentas |
| Redirecionamentos implícitos | `tools/handoff.py` (`Command` de grafo, sem anúncio ao cliente) |
| Ferramentas para API/CSV/cálculo | `tools/` + `data_manager.py` + `domain.py` |
| Tratamento de erros (CSV, API, entrada) | `DataAccessError`, `ERRO_TECNICO`, timeout em `exchange.py`, `_mensagem_amigavel_erro` em `session.py`, log em `config.py` |

### Entrega e requisitos técnicos
| Requisito | Status |
|-----------|--------|
| Repositório GitHub | ✅ (lembrar de dar `push` antes da entrega) |
| README com as 6 seções obrigatórias | ✅ Visão geral, Arquitetura, Funcionalidades, Desafios, Escolhas técnicas, Tutorial |
| Estrutura modular por responsabilidade | ✅ `src/{config,llm,state,graph,session,data_manager,domain}` + `agents/` + `tools/` |
| UI Streamlit para teste completo | ✅ `app.py` (+ `cli.py` como bônus) |
| Stack sugerida (LangChain/LangGraph/Groq) | ✅ todas usadas |

> **Resumo honesto para a banca:** todos os requisitos funcionais e de entrega
> estão implementados. Um ponto de robustez conhecido: com só o CPF na primeira
> mensagem, o modelo pode consumir uma tentativa de autenticação antes de pedir a
> data (contorno: informar CPF e data juntos). Nada fora da especificação.

---

## 4. Passeio pelo código (o que abrir na tela)

Quatro arquivos contam a história inteira. Abra nesta ordem:

1. **`src/graph.py`** — a montagem. Mostra os 4 agentes ReAct, suas ferramentas e
   o roteador que envia cada turno ao agente ativo. "É aqui que o sistema vira um
   grafo de agentes."
2. **`src/tools/interview.py`** — a joia técnica. O `Command(goto="credito")`
   devolve o cliente ao crédito de forma **determinística** e preserva o contexto
   de sessão. "Foi assim que matei o loop de transferências."
3. **`src/domain.py`** — as regras puras. A fórmula de score e a política de
   limite, sem I/O e sem LLM. "O LLM conversa; a matemática do banco é código
   testado." Abra lado a lado com a fórmula do enunciado — os pesos são idênticos.
4. **`src/data_manager.py`** — a camada de dados. Escrita atômica (arquivo `.tmp`
   + replace) e lock. "Nenhum agente abre arquivo; e a base nunca corrompe."

Se sobrar tempo: `src/session.py` (sanitizador de saída + mensagens amigáveis de
erro) e `src/llm.py` (troca de provedor por variável de ambiente).

---

## 5. Roteiro de demonstração ao vivo

Antes de começar: `streamlit run app.py`, clicar em **Iniciar atendimento**.
A barra lateral já lista os clientes de teste.

> **Ritmo:** aguarde cada resposta aparecer antes de enviar a próxima mensagem.
> Além de parecer um atendimento real, isso evita picos de tokens por minuto.

> **Dica de autenticação:** informe **CPF e data de nascimento na mesma
> mensagem** (ex.: "Meu CPF é 555.666.777-88 e nasci em 02/11/1985"). Com os dois
> dados de uma vez, o atendente autentica direto. Se você mandar só o CPF
> primeiro, pode aparecer um "houve um problema na autenticação" inofensivo antes
> de ele pedir a data — recupera sozinho no turno seguinte, mas mandar junto
> deixa a demo mais limpa.

### Fluxo A — Câmbio (mostra auth + transferência invisível + API real)
1. Digite: **"Quero saber a cotação do dólar."**
   - Repare: o atendente pede autenticação **sem** dizer que "vai transferir".
2. Autentique como **Ana**: "Meu CPF é 111.222.333-44 e nasci em 15/05/1990."
3. Ele responde a cotação real do dólar (vinda da AwesomeAPI).
4. Pergunte: **"E o euro?"** — responde sem pedir dados de novo.
   - **Ponto a destacar:** trocamos de triagem para câmbio e o cliente nunca
     percebeu. É o mesmo atendente para ele.

### Fluxo B — Crédito + Entrevista + Reanálise (o fluxo mais rico)
Use o **Bruno** (score baixo, ótimo para mostrar o ciclo completo).
1. **"Bom dia, quero aumentar meu limite de crédito."**
2. Autentique como **Bruno**: "Meu CPF é 555.666.777-88 e nasci em 02/11/1985."
3. Ele informa o limite atual (R$ 3.000). Peça um aumento para **R$ 8.000**.
   - Com score 400, o teto é R$ 3.000 → **rejeitado**. Ele oferece a entrevista.
4. Aceite: **"Sim, quero fazer a entrevista."**
5. Responda as 5 perguntas **exatamente assim** (calibrado para aprovar):
   - Renda mensal: **12000**
   - Emprego: **formal**
   - Despesas fixas: **1000**
   - Dependentes: **0**
   - Dívidas: **não**
6. O score sobe para **~860**. O sistema devolve ao crédito **automaticamente**
   e refaz a análise dos R$ 8.000 → agora **aprovado**.
   - **Ponto a destacar:** o retorno da entrevista para o crédito é
     **determinístico** (código, não decisão do LLM) — foi assim que eliminei um
     loop de transferências que existia antes.
7. Encerre: **"Era só isso, obrigado."**
8. **Feche o loop visualmente:** abra `data/solicitacoes_aumento_limite.csv` e
   mostre as linhas geradas (pendente → rejeitado, depois aprovado) — prova o
   registro formal exigido pelo enunciado.

> **Plano B (se quiser mostrar rejeição persistente):** na entrevista, dê renda
> baixa (ex.: 2000) e despesas altas (ex.: 3000). O score sobe pouco e os
> R$ 8.000 continuam acima do teto — mostra que a regra de negócio manda, não o
> "bom humor" do modelo.

> **Se aparecer "limite de uso atingido":** é o teto de tokens/minuto do tier
> gratuito. Espere ~10 segundos e reenvie a última mensagem — a conversa continua
> do ponto em que estava (o estado é persistido por conversa). O modelo padrão
> (`llama-3.3-70b-versatile`) foi escolhido justamente para minimizar isso.

---

## 6. Pontos de fala sobre a arquitetura

Cinco ideias, uma frase-chave cada:

1. **Padrão "swarm" com handoffs implícitos.**
   Cada agente é um agente ReAct (LLM + ferramentas restritas + prompt de escopo),
   nós de um `StateGraph`. Um roteador de entrada manda cada novo turno para o
   agente ativo. As transferências são ferramentas que emitem um `Command` de
   grafo — o cliente vê um atendente só.

2. **Estado compartilhado e memória por conversa.**
   `BankState` guarda histórico, agente ativo, CPF, flag de autenticado e
   tentativas. Um checkpointer por `thread_id` dá as conversas multi-turno.

3. **Regras de negócio fora do LLM.**
   Cálculo de score e política de limite vivem em `domain.py` — código puro,
   testado, sem I/O e sem IA. Em banco, isso significa cálculo correto e
   auditável; o LLM só conversa e orquestra.

4. **Camada de dados isolada.**
   Nenhum agente abre arquivo. Tudo passa por `data_manager.py`, com escrita
   atômica e lock — daria para trocar CSV por um banco real sem tocar nos agentes.

5. **Agnóstico ao provedor.**
   Groq, Gemini ou OpenAI trocam por uma variável de ambiente. A fábrica de LLM
   (`llm.py`) concentra as diferenças (ex.: ocultar o raciocínio do qwen, retry
   contra rate-limit).

---

## 7. Desafios técnicos resolvidos (para contar como "história")

- **Contexto de autenticação sumindo na transferência.** Ao trocar de agente, só
  os campos explicitados no `Command` sobreviviam — CPF e "autenticado" se
  perdiam. Solução: a ferramenta de transferência relê o estado e reencaminha o
  contexto de sessão.
- **Loop de transferências (ping-pong).** Crédito ↔ entrevista trocavam controle
  até estourar a recursão. Solução: retorno **determinístico** da entrevista +
  regras de prompt (no máx. uma transferência por turno) + limite de recursão
  como rede de segurança.
- **Vazamento de sintaxe de ferramenta no texto.** Alguns modelos escrevem a
  chamada de função como texto. Um sanitizador remove isso antes de exibir.
- **Rate-limit em demo.** O tier gratuito tem teto de tokens/minuto. Retry com
  backoff absorve o 429 transitório sem expor erro; a mensagem de erro amigável é
  a última rede.

---

## 8. Perguntas prováveis da banca (com respostas)

**"Por que LangGraph e não só chamar o LLM em loop?"**
Porque o requisito é vários agentes com escopos distintos atuando como um só, com
transferências e memória. LangGraph modela isso como grafo de estado nativamente;
fazer na mão viraria uma máquina de estados caseira e frágil.

**"Como você garante que o cálculo do limite está certo?"**
Ele não passa pelo LLM. `domain.py` é código determinístico com testes unitários.
O LLM só coleta os dados e conversa; a decisão de aprovar/rejeitar é regra fixa.

**"E se a API de câmbio cair?"**
Há tratamento de timeout e indisponibilidade; o agente responde com uma mensagem
cordial de instabilidade e registra o erro técnico no log, sem expor detalhe.

**"Os dados dos clientes são reais?"**
Não, é uma base fictícia em CSV (`data/clientes.csv`). A camada de acesso é
isolada, então trocar por um banco real seria transparente para os agentes.

**"Como testou algo que depende de um LLM não-determinístico?"**
Separei as camadas: regras e dados têm testes unitários puros; o teste de
integração ponta-a-ponta roda só quando há chave configurada e valida o fluxo
real (autenticar → consultar limite).

**"Como funciona a transferência sem o cliente perceber?"**
A ferramenta de handoff emite um `Command` que muda o nó ativo no grafo sobre o
mesmo histórico. O prompt proíbe anunciar a transferência. Para o cliente, é o
mesmo atendente com outra habilidade.

**"A memória persiste se reiniciar o app?"**
Hoje uso um checkpointer em memória por `thread_id` — o enunciado pede um
atendimento funcional, não persistência entre reinícios. Trocar por um
checkpointer persistente (ex.: SQLite) seria só configurar, sem mudar os agentes.

**"Por que trocou o modelo padrão?"**
O modelo antigo foi descontinuado na Groq. Avaliei os disponíveis com
tool-calling real e escolhi o `llama-3.3-70b-versatile` pela resposta limpa, bom
tool-calling e teto de tokens/minuto mais folgado — mais seguro para demo ao vivo.

---

## 9. Checklist pré-apresentação

- [ ] `.env` com `GROQ_API_KEY` válida e `LLM_MODEL=llama-3.3-70b-versatile`.
- [ ] `pip install -r requirements.txt` rodado no `.venv`.
- [ ] `streamlit run app.py` abre sem erro de configuração.
- [ ] `data/clientes.csv` com os scores originais (Bruno = 400).
- [ ] `data/solicitacoes_aumento_limite.csv` ausente ou vazio (começa limpo).
- [ ] Testado o Fluxo B uma vez antes para aquecer e confirmar a aprovação.
- [ ] `pytest -q` verde (36 testes) para mostrar na parte de qualidade.
- [ ] Abas/arquivos do "passeio pelo código" já abertos no editor.
