# Guia de Apresentação — Banco Ágil

Material de apoio para a apresentação. Contém o pitch, o roteiro de demonstração
ao vivo (com valores calibrados), os pontos de fala sobre a arquitetura e as
perguntas mais prováveis da banca com respostas prontas.

---

## 1. Pitch (30 segundos)

> "O Banco Ágil é uma central de atendimento de um banco digital operada por
> vários agentes de IA especializados — triagem/autenticação, crédito, entrevista
> de crédito e câmbio. A sacada é que, para o cliente, existe **um único
> atendente**: as transferências entre os especialistas acontecem de forma
> invisível, sobre um mesmo histórico de conversa. Foi construído com LangGraph,
> LangChain e Streamlit, com as regras de negócio bancárias isoladas do LLM para
> garantir cálculo correto e auditável."

---

## 2. Roteiro de demonstração ao vivo

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

> **Plano B (se quiser mostrar rejeição persistente):** na entrevista, dê renda
> baixa (ex.: 2000) e despesas altas (ex.: 3000). O score sobe pouco e os
> R$ 8.000 continuam acima do teto — mostra que a regra de negócio manda, não o
> "bom humor" do modelo.

> **Se aparecer "limite de uso atingido":** é o teto de tokens/minuto do tier
> gratuito. Espere ~10 segundos e reenvie a última mensagem — a conversa continua
> do ponto em que estava (o estado é persistido por conversa). O modelo padrão
> (`llama-3.3-70b-versatile`) foi escolhido justamente para minimizar isso.

---

## 3. Pontos de fala sobre a arquitetura

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

## 4. Desafios técnicos resolvidos (para contar como "história")

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

## 5. Perguntas prováveis da banca (com respostas)

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

**"Por que trocou o modelo padrão?"**
O modelo antigo foi descontinuado na Groq. Avaliei os disponíveis com
tool-calling real e escolhi o `llama-3.3-70b-versatile` pela resposta limpa, bom
tool-calling e teto de tokens/minuto mais folgado — mais seguro para demo ao vivo.

---

## 6. Checklist pré-apresentação

- [ ] `.env` com `GROQ_API_KEY` válida e `LLM_MODEL=llama-3.3-70b-versatile`.
- [ ] `pip install -r requirements.txt` rodado no `.venv`.
- [ ] `streamlit run app.py` abre sem erro de configuração.
- [ ] `data/clientes.csv` com os scores originais (Bruno = 400).
- [ ] `data/solicitacoes_aumento_limite.csv` ausente ou vazio (começa limpo).
- [ ] Testado o Fluxo B uma vez antes para aquecer e confirmar a aprovação.
