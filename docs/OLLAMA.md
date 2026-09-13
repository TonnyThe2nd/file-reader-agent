# Ollama local com Qwen

O backend usa `OllamaService` com `httpx.AsyncClient`, compartilhado pelo ciclo de vida da API. Geração e embeddings usam exclusivamente o Ollama. Não é necessário instalar o SDK OpenAI nem fornecer chave Gemini. O `.env` existente é preservado; variáveis antigas Gemini são ignoradas.

Adicione ao `.env` as variáveis `OLLAMA_*` de `.env.example`. O modelo padrão `qwen2.5:7b` preserva a escolha existente no código; configure `OLLAMA_CHAT_MODEL` com a tag exata instalada na sua máquina (`ollama list`).

```powershell
ollama pull qwen3.6:27b
ollama pull nomic-embed-text
ollama serve
```

Se o Ollama já estiver em execução, não inicie uma segunda instância. Reinicie a API depois de alterar o `.env`.

| Variável | Padrão / finalidade |
|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1`, incluindo `/v1` |
| `OLLAMA_CHAT_MODEL` | `qwen2.5:7b` |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` |
| `OLLAMA_EMBEDDING_DIMENSIONS` | `768`; deve corresponder à saída do modelo |
| `OLLAMA_TIMEOUT_SECONDS` | `300`, por chamada, incluindo carregamento do modelo |
| `OLLAMA_TEMPERATURE` | `0.2`; aceita zero |
| `OLLAMA_MAX_TOKENS` | `4096`; respostas truncadas são rejeitadas, sem salvar resposta parcial |
| `OLLAMA_MAX_CONTEXT_CHARS` | `24000`; limite do texto do arquivo em consulta direta e dos trechos enviados pelo RAG |

O limite em caracteres não mede tokens. Ajuste-o conforme a janela de contexto e a memória disponíveis no servidor, considerando também histórico, pergunta e resposta. Arquivos extensos devem usar RAG ou ser divididos.

Textos seguem em UTF-8. PDFs passam por extração local de texto (sem OCR); PDFs digitalizados, protegidos ou sem texto são rejeitados. Imagens são enviadas como `image_url` em base64 e exigem um modelo com visão. Um modelo apenas textual não passa a interpretar imagens por esta integração.

O RAG gera embeddings em lotes de 32, valida dimensão, ordem, valores finitos e vetores não nulos. Para Nomic, aplica `search_document:` e `search_query:`. Os novos índices possuem identificação própria e são criados na primeira consulta RAG, preservando os dados anteriores. O cache incorpora o novo provedor, modelo e parâmetros de geração. Conversas e histórico permanecem disponíveis.

No Docker Compose, a API acessa o Ollama do host por `http://host.docker.internal:11434/v1`. Para outro servidor, defina `OLLAMA_DOCKER_BASE_URL`. O Ollama precisa aceitar conexões da rede Docker; configure o bind e o firewall conforme sua implantação, mantendo o acesso restrito à rede necessária.

`/ready` verifica o banco e retorna `ollama_configured`; esse campo indica configuração presente, não disponibilidade real do servidor ou dos modelos. Erros de conexão, timeout e modelo ausente são apresentados ao consultar um documento.

Validação automática: `python -m pytest -q` usa transporte HTTP simulado e SQLite. Para validar o modelo real após instalá-lo, use `python scripts/smoke_live.py --live` com o banco migrado. Esse teste cria e remove um workspace temporário.

Referências: [protocolo compatível do Ollama](https://docs.ollama.com/api/openai-compatibility) e [prefixos do Nomic](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).
