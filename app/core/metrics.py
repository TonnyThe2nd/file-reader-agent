from prometheus_client import Counter, Histogram

MULTIAGENT_RUNS_TOTAL = Counter(
    "multiagent_runs_total", "Fluxos multiagente executados", ["status"]
)
AGENT_FAILURES_TOTAL = Counter("agent_failures_total", "Falhas por agente", ["agent"])
AGENT_DURATION_SECONDS = Histogram(
    "agent_duration_seconds",
    "Duracao por agente",
    ["agent"],
    buckets=[0.1, 1, 5, 10, 30, 60, 120, 300, 900],
)
AGENT_TOKENS_TOTAL = Counter(
    "agent_tokens_total", "Tokens de geracao por agente", ["agent", "kind"]
)

CACHE_HITS_TOTAL = Counter("ask_cache_hits_total", "Consultas atendidas pelo cache")
GENERATION_TOKENS_TOTAL = Counter(
    "generation_tokens_total", "Tokens informados pelo provedor", ["kind"]
)

ASK_REQUESTS_TOTAL = Counter(
    "ask_requests_total",
    "Total de requisições ao endpoint /ask",
    ["status"],
)

ASK_LATENCY_SECONDS = Histogram(
    "ask_latency_seconds",
    "Latência do endpoint /ask em segundos",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 900.0],
)

FEEDBACK_TOTAL = Counter(
    "feedback_total",
    "Total de feedbacks recebidos",
    ["rating"],
)
