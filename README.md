# Documento — consultas a arquivos com Ollama e Qwen

Angular + FastAPI + PostgreSQL com consulta direta e RAG, biblioteca de documentos, histórico persistente, feedback, estatísticas, autenticação por usuário e cache.

O [guia completo da aplicação](docs/APLICACAO.md) explica as funcionalidades, arquitetura, decisões, banco, autenticação, testes, operação e limitações.

## Estado atual

O MVP tem consulta direta, RAG e chat implementados com Ollama local. Isso não equivale à validação completa da instalação: é necessário ter banco migrado, os dois modelos instalados e executar o teste real. Consulte [os resultados e pendências](docs/VALIDACAO.md).

## Executar localmente

Preserve seu `.env` existente. Para uma instalação nova, use `.env.example` como referência e configure `DATABASE_URL` e as variáveis `OLLAMA_*` descritas em [Ollama local](docs/OLLAMA.md).

```powershell
# Com Ollama instalado e em execução:
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Apenas se precisar iniciar um banco pelo Docker:
docker compose up -d postgres
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Em outro terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd start
```

Interface: http://localhost:4200. Swagger: http://127.0.0.1:8000/docs.

Se já existe PostgreSQL na porta 5432, utilize-o com a URL correta ou defina `POSTGRES_PORT=5433` para o container e ajuste a URL local. Não remova volumes para resolver conflitos.

## Banco

A [migration incremental](alembic/versions/b72e9c41a603_documents_and_query_persistence.py) preserva o histórico existente no workspace `local`.

Prefira `alembic upgrade head`. Para execução manual, há [SQL para banco novo](db/migrate_fresh.sql) e [SQL para banco na revisão inicial](db/migrate_existing.sql). Não execute os SQLs depois de aplicar as mesmas mudanças com Alembic.

## Funcionalidades

O modo opcional `multiagent` executa router, researcher e answerer com o Ollama
existente. Consulte [configuracao, arquitetura e observabilidade](docs/MULTIAGENTE.md).

- PDF, TXT, MD, CSV, JSON e imagens, até 10 MiB.
- Consulta ao documento inteiro ou busca vetorial em trechos de texto/PDF.
- Biblioteca para reutilizar arquivos, com deduplicação por conteúdo e usuário.
- Histórico com busca, paginação, resposta completa e exclusão.
- Chat com memória, retomada de conversas e fontes clicáveis com visualizador.
- Feedback na resposta e no histórico; estatísticas por usuário.
- Cache com validade, fontes recuperadas e registro de tokens de geração.
- Chaves de acesso individuais, limites de requisições e CORS configurável.
- Migrations, testes, avaliação de referência, CI e configuração Prometheus/Grafana.

Sem `API_TOKENS`, somente `APP_ENV=development` permite o workspace compartilhado `local`. Para acesso individual, configure `API_TOKENS` conforme o guia. O Ollama local não exige chave de API.

## Validar

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m ruff check app tests evaluation
.\.venv\Scripts\python.exe -m evaluation.run
cd frontend
npm.cmd run format:check
npm.cmd run build
npm.cmd run test:e2e
```

Os testes Python simulam as chamadas ao Ollama. Com banco migrado e ambos os modelos instalados, execute na raiz `python scripts/smoke_live.py --live` usando o ambiente `.venv`. O teste valida consulta direta, cache, RAG, chat e persistência com dados sintéticos e processamento local. Os registros temporários são removidos ao terminar; isso não substitui avaliação de qualidade nem teste de carga.

## Containers

```powershell
docker compose --profile app up --build -d
docker compose --profile app --profile monitoring up --build -d
```

Interface na porta 8080, Grafana na 3000 e Prometheus na 9090, vinculados ao localhost. O serviço `migrate` aplica o schema antes da API. Para publicação externa, configure HTTPS, chaves individuais, senhas próprias e backup.

Selecione “Buscar trechos com fontes” na interface ou envie `mode=rag` ao `/ask`; o padrão da API é `direct`.

RAG usa busca exata sobre embeddings persistidos, limitada a um documento. A memória de conversa é limitada aos turnos recentes. Não há OCR local nem pesquisa em todo o acervo. Consulte o guia para limites de escala e segurança.
A migration [c83f0d52b714](alembic/versions/c83f0d52b714_conversations.py) adiciona conversas. Para bancos na revisão anterior, o SQL correspondente está em [db/migrate_chat.sql](db/migrate_chat.sql). Prefira `alembic upgrade head`.
