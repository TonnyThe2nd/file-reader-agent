from prometheus_client import Counter, Histogram

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
