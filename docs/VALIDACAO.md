# Validação — 11/09/2026

## Executado com sucesso

- Backend: **39 testes e 14 subtestes**. Inclui integração das camadas com transporte Gemini simulado, persistência, cache e expiração, RAG e reutilização do índice, isolamento, feedback, exclusões, extração de PDF, migrations, memória limitada, paginação de conversas e rejeição de envios concorrentes desatualizados.
- Navegador: **10 testes Playwright**, incluindo consulta, erro do provedor, histórico, layout móvel, documentos salvos, RAG/fontes, resposta completa, login/logout, continuidade e retomada do chat, destaque de trechos e abertura da página PDF.
- Build Angular de produção: concluído.
- Ruff e Prettier: código verificado e formatado.
- PostgreSQL configurado no `.env`: migrations aplicadas até `c83f0d52b714`; `alembic check` sem divergências.
- Migration em banco de teste: preservação de registro anterior e upgrade/downgrade verificados.
- SQLs PostgreSQL para banco novo e atualização: gerados em `db/`.
- Gemini real: consulta direta, cache, embeddings, recuperação de fontes e geração RAG validados com um documento sintético. Histórico, feedback e estatísticas conferidos no PostgreSQL real. Os registros do workspace temporário foram removidos pelo script.
- Chat real: pergunta de continuação respondida pelo Gemini, retomada da conversa e acesso autenticado ao documento conferidos; conversas de teste removidas ao terminar.
- Avaliador: exemplos gravados passaram; isso valida o mecanismo de avaliação, não representa uma medição ampla da qualidade do modelo.
- Docker Compose: configuração validada com os perfis `app` e `monitoring`.

## Limitações da validação

O daemon Docker não estava em execução. Portanto, imagens, inicialização dos containers e provisionamento real de Grafana/Prometheus não foram executados nesta máquina. A pipeline de CI foi criada, mas não foi executada em um serviço remoto.

O smoke test real cobre um documento sintético curto; não equivale a teste de carga nem a avaliação de qualidade em documentos reais do usuário. Os testes Python apresentam um aviso de depreciação na dependência Starlette/AnyIO, sem falha de teste.

Nenhuma chave Gemini ou senha existente no `.env` foi alterada. O acesso local continua conforme a configuração existente; habilitar usuários individuais requer preencher `API_TOKENS` como explicado no guia.
