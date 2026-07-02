# ─────────────────────────────────────────────────────────────────────────────
# Process2Diagram — Dockerfile
# Target: FastAPI API (api.py) on Google Cloud Run
# ─────────────────────────────────────────────────────────────────────────────
#
# Build:  docker build -t p2d-api .
# Run:    docker run -p 8080:8080 --env-file .env p2d-api
#
# Isolamento de estado (ENGINEERING_MANIFESTO §3):
#   - WORKERS=1 por instância — Cloud Run escala horizontalmente
#   - Nenhum st.session_state acessado fora do contexto Streamlit
#   - _JOBS dict em memória: volátil por design (migrar para Supabase na Fase 2)
#   - threading.Lock: válido dentro de 1 instância (migrar para Cloud Tasks na Fase 2)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ──────────────────────────────────────────────────────────
# Instala deps Python e baixa modelo spaCy. build-essential fica SOMENTE aqui.
FROM python:3.13-slim AS builder

WORKDIR /build

# libgomp1: dependência de runtime do spaCy (OpenMP)
# build-essential: compila extensões C de algumas deps (ex: lxml, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.api.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.api.txt

# Bake modelo spaCy na imagem — elimina download no cold start do Cloud Run.
# pt_core_news_lg (~560 MB) alinhado com CLAUDE.md.
# Para imagens menores: substituir por pt_core_news_sm (acurácia reduzida).
RUN python -m spacy download pt_core_news_lg

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
# Imagem final sem build tools — apenas o necessário para executar.
FROM python:3.13-slim AS runtime

# Apenas deps de runtime (sem build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copia packages instalados do builder (inclui modelo spaCy e todas as deps)
COPY --from=builder /usr/local/lib/python3.13/site-packages \
                    /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# ── Código da aplicação (superfície API — sem pages/, tests/, static/) ────────
COPY agents/   agents/
COPY core/     core/
COPY modules/  modules/
COPY services/ services/
COPY skills/   skills/
COPY api.py    api.py

# Usuário não-root — boas práticas de segurança do Cloud Run
RUN useradd -m -u 1001 p2d && chown -R p2d:p2d /app
USER p2d

# ── Configuração de runtime ───────────────────────────────────────────────────
# PORT: Cloud Run injeta automaticamente (padrão 8080).
# WORKERS=1: isolamento de estado por instância; escala horizontal via Cloud Run.
# PYTHONUNBUFFERED=1: logs em tempo real no Cloud Logging (sem buffer de stdout).
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Probe de liveness — Cloud Run chama /health a cada 30s
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
        || exit 1

# Shell form para expandir $PORT em runtime
CMD uvicorn api:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info \
    --timeout-graceful-shutdown 30
