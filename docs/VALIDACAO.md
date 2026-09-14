# Validação — Ollama local

## Evolução de 14/09/2026

- Backend: **99 testes e 14 subtestes aprovados**, com 6 testes de integração ignorados localmente.
- As integrações ignoradas são quatro cenários de concorrência em PostgreSQL (`POSTGRES_TEST_URL`) e dois cenários nativos de OCR (Tesseract e dependências opcionais). A CI foi configurada para executá-los.
- Navegador: **16 testes Playwright aprovados**, incluindo regressão do fluxo anterior, múltiplos documentos, fontes corretas, streaming, exportação Markdown e comparação.
- Build Angular e lint/formatação do backend aprovados. A avaliação com respostas gravadas passou; ela não mede a qualidade atual do Ollama.
- Migrações foram verificadas com preservação de registros anteriores e comparação do schema em SQLite; SQL PostgreSQL atualizado foi exportado. Migrações não foram aplicadas ao banco pessoal.
- O Docker não respondeu neste ambiente e Tesseract não estava disponível; inferência real com Ollama e execução nativa de OCR/PostgreSQL permanecem como validação da instalação de destino.
- O teste do padrão multiagente foi alinhado à configuração local já ativada; a escolha existente foi preservada.

Consulte [EVOLUCAO.md](EVOLUCAO.md) para arquitetura, ativação do worker/OCR, permissões, retenção, limites e próximos passos.

## Verificação de 13/09/2026 (registro anterior)

- Backend: **46 testes e 14 subtestes passaram**, executados com `python -m pytest -q` no ambiente `.venv`. As chamadas HTTP ao Ollama são simuladas e a persistência usa banco de teste; isso não comprova inferência real.
- A integração ativa usa `OllamaService` para geração e embeddings.
- O endpoint local `/v1/models` respondeu HTTP 200 e listou apenas `qwen2.5:7b`.
- A configuração carregada apontava para `localhost`, com `qwen2.5:7b` para geração e `nomic-embed-text` para embeddings.
- `nomic-embed-text` não apareceu na lista de modelos: sua instalação era uma pendência para executar RAG nessa verificação.
- A suíte apresentou um aviso de depreciação Starlette/AnyIO, sem falhas.

Esses resultados registram o estado observado nessa data. A disponibilidade do endpoint e a presença do modelo não confirmam a geração de respostas nem o fluxo completo com PostgreSQL.

## Pendências para validar a instalação local

1. Instalar os modelos configurados e manter o Ollama em execução:

   ```powershell
   ollama pull qwen2.5:7b
   ollama pull nomic-embed-text
   ollama list
   ```

2. Com o PostgreSQL disponível e `DATABASE_URL` configurada, aplicar e conferir o schema. Execute os comandos abaixo na raiz, com o ambiente `.venv` ativado:

   ```powershell
   python -m alembic upgrade head
   python -m alembic check
   ```

3. Executar o teste com Ollama real no mesmo ambiente:

   ```powershell
   python scripts/smoke_live.py --live
   ```

O script verifica consulta direta, cache, embeddings, recuperação de fontes, geração RAG, histórico, feedback, estatísticas, continuidade do chat e acesso ao documento. Cria um workspace temporário e remove seus registros ao terminar. Usa recursos locais de inferência; não depende de cota Gemini.

O teste real com Ollama e a situação atual do PostgreSQL ainda não foram confirmados nesta verificação. `/ready` verifica o schema e indica configuração do provedor, mas não testa conexão ao Ollama nem presença dos modelos.

## Registro anterior — 11/09/2026

A documentação anterior registrava 39 testes e 14 subtestes, 10 testes Playwright, build Angular, Ruff/Prettier, migrations até `c83f0d52b714`, `alembic check`, SQLs exportados, avaliação com respostas gravadas e configuração do Compose.

Também registrava consulta direta, RAG e chat com **Gemini**, o provedor daquela versão. Esses resultados são históricos e não validam a execução real após a migração para Ollama. Os checks de frontend, banco e infraestrutura não foram repetidos na verificação de 13/09.

## Limites da evidência

- O teste sintético não substitui avaliação em documentos reais nem teste de carga.
- A avaliação com respostas gravadas verifica o avaliador, não a qualidade atual do modelo.
- No registro anterior, o daemon Docker estava parado; inicialização dos containers e provisionamento real de Grafana/Prometheus não foram validados.
- A execução remota da pipeline de CI não está confirmada.
- O MVP está implementado, mas a instalação local ainda precisa concluir as pendências acima antes de ser considerada validada de ponta a ponta.
