# Consultas multiagente

O `/ask` aceita `mode=direct` (padrao), `mode=rag` e `mode=multiagent`.
O novo modo fica desabilitado ate configurar `MULTIAGENT_ENABLED=true` no
ambiente da API e reiniciar o processo. A interface consulta `/config` e
oferece a opcao quando habilitada. O contrato `AskResponse` e as fontes
continuam iguais, com `mode=multiagent` identificando a resposta e o historico.

## Configuracao

| Variavel | Padrao | Finalidade |
| --- | --- | --- |
| `MULTIAGENT_ENABLED` | `false` | Habilita o modo opcional |
| `MULTIAGENT_MODEL` | `OLLAMA_CHAT_MODEL` | Modelo das tres etapas; omitir para herdar |
| `MULTIAGENT_MAX_STEPS` | `3` | Teto de etapas, entre 3 e 10; o fluxo atual sempre executa 3 |
| `MULTIAGENT_TIMEOUT_SECONDS` | `300` | Prazo total incluindo recuperacao e geracoes |

Temperatura, limite de tokens, timeout HTTP e limite de contexto usam as
configuracoes Ollama existentes. O limite de tokens e por geracao; uma
consulta multiagente pode consumir ate tres geracoes, alem dos embeddings.
Nao ha novas dependencias ou servicos externos.

## Fluxo

1. `RAGService` valida dono do documento/conversa, carrega memoria e verifica cache.
2. `router` classifica a intencao em `lookup`, `summary` ou `comparison`.
3. `researcher` chama `retrieve()` com pergunta e contexto recente, reutilizando
   o indice PostgreSQL atual. A intencao orienta a avaliacao das evidencias.
   O modelo retorna somente suficiencia e IDs de trechos, validados estritamente.
4. `answerer` recebe pergunta, historico e os trechos originais selecionados,
   renumerados para corresponder as fontes retornadas. Deve citar [1], [2], etc.
5. `RAGService` verifica a versao da conversa e persiste a interacao normalmente.

`AgentService` executa etapas sequenciais limitadas e registra `AgentRun` em
memoria com nome, modelo, status, duracao e tokens. Os prompts de sistema
ficam em `PROMPTS`; entradas e saidas circulam apenas em memoria. Toda
chamada HTTP, inclusive as geracoes com prompt especifico, continua no
`OllamaService`. `generate()` preserva sua assinatura e comportamento.

Textos e PDFs com texto usam os mesmos limites de upload, chunks e top-k do
RAG. Imagens recebem 422, orientando consulta direta. A busca cobre trechos,
nao garante resumo exaustivo do documento. Sem trechos suficientes, as tres
etapas ainda executam, mas a resposta publica e uma mensagem deterministica
de evidencia insuficiente, com fontes vazias. Saida estruturada invalida ou
referencia inexistente falha com `OllamaServiceError`, sem continuar o fluxo.

Documento, historico e saidas dos agentes sao explicitamente tratados como
dados nao confiaveis nos prompts de sistema. O router nao recebe o arquivo;
o researcher nao pode criar fontes ou executar ferramentas arbitrarias.
A selecao usa IDs validados e o answerer recebe o texto original, nunca uma
reescrita de evidencias pelo researcher. Isso reduz a superficie de injecao,
mas a qualidade semantica da selecao e resposta ainda depende do modelo.

## Cache e persistencia

O cache inclui modo, dono, documento, historico e configuracoes existentes.
Para multiagente inclui tambem versao dos prompts, modelo efetivo, teto de
etapas, prazo total e limite de contexto. Uma resposta em cache nao executa
agentes e registra zero tokens, como nos modos anteriores. Desabilitar o
modo tambem bloqueia respostas multiagente previamente armazenadas no cache.

Nao e necessaria migration para este MVP: `Interaction.mode` ja comporta
`multiagent` (10 caracteres), e as colunas de duracao, modelo e tokens
armazenam os agregados das tres etapas. Nenhum prompt ou resultado
intermediario e persistido. Falhas nao criam interacoes nem avancam turnos,
seguindo o comportamento atual; uploads e indices ja salvos podem permanecer
para nova tentativa.

Os detalhes por etapa ficam em logs estruturados e metricas, inclusive para
fluxos interrompidos. Os logs contem somente nome, status, duracao, tokens e
categoria fixa de erro sanitizado. Nao incluem pergunta, documento, dono,
historico, prompt, resposta ou mensagens brutas do provedor. Modelo efetivo
fica em memoria e o modelo final no campo existente de `Interaction`.
Nao ha trilha duravel por agente vinculada a uma interacao no banco neste MVP.

## Observabilidade

- `multiagent_runs_total{status}`: fluxos executados com sucesso ou erro; exclui cache.
- `agent_failures_total{agent}`: falhas, incluindo cancelamento por timeout.
- `agent_duration_seconds{agent}`: duracao; researcher inclui recuperacao/indexacao.
- `agent_tokens_total{agent,kind}`: tokens de geracao reportados pelo Ollama.
- `generation_tokens_total{kind}`: inclui todas as geracoes multiagente, inclusive
  etapas concluidas antes de uma falha posterior, sem contar duas vezes.

Tokens de embeddings nao sao incluidos, seguindo a contabilizacao existente.
Os logs de etapas nao incluem erros brutos. Timeouts retornam 504 e falhas de
conexao 502, usando `OllamaServiceError` e o tratamento atual do endpoint.

## Validacao

Na raiz, com `.venv` ativado: `python.exe -m pytest -q`.
`tests/test_multiagent.py` usa mocks e `httpx.MockTransport`; nenhum teste
precisa de Ollama real. A integracao de persistencia usa SQLite, como a suite
existente. O teste Playwright verifica selecao, envio e identificacao da
resposta em desktop e mobile: `npm.cmd run test:e2e`, em `frontend`.
