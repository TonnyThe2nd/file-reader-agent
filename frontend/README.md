# Frontend Documento

Interface Angular para consultar arquivos, reutilizar documentos, abrir respostas completas, avaliar consultas e acompanhar estatísticas.

## Executar

Com o backend na porta 8000:

```powershell
npm.cmd ci
npm.cmd start
```

Acesse http://localhost:4200. O proxy em `proxy.conf.cjs` encaminha `/api/*` ao FastAPI, removendo `/api`.

## Telas

- `/`: consulta direta ou por trechos, upload, cache, fontes e feedback imediato.
- `/documentos`: biblioteca, upload, reutilização e exclusão.
- `/historico`: busca, paginação, feedback e exclusão de consultas.
- `/historico/:id`: resposta completa com fontes, avaliação e consumo.
- `/estatisticas`: indicadores do workspace.
- Quando exigido pelo backend, a aplicação apresenta o formulário de chave de acesso antes das telas.

A chave da aplicação fica no `sessionStorage` da aba e é removida ao sair. Ela é diferente da chave Gemini, que nunca é enviada ao frontend.

## Organização

`core/api.ts` define contratos e operações HTTP. `shared/feedback.ts` concentra o componente reutilizável de avaliação. As páginas são carregadas sob demanda em `app.routes.ts`. O limite de upload e a exigência de autenticação vêm de `/config`; o indicador de conexão usa `/ready`.

## Qualidade e build

```powershell
npm.cmd run format
npm.cmd run format:check
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

O build fica em `dist/documento/browser`. Os testes simulam a API, sem enviar arquivos ao Gemini. O Dockerfile inclui Nginx com fallback das rotas Angular, limite de corpo HTTP e proxy para a API.

Veja [o guia da aplicação](../docs/APLICACAO.md) para banco, backend, autenticação, configurações, testes reais e decisões de arquitetura.
