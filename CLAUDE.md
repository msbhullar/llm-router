# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A gateway that scores incoming query difficulty and routes each request to a
cheap or strong LLM tier (OpenAI) accordingly, instead of always calling the
most expensive model. See `README.md` for the full phase-by-phase build log,
design rationale, and dead ends (it's worth reading before making non-trivial
changes — several "obvious" approaches were tried and rejected, with the
reasoning documented there).

## Commands

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # full dev deps (includes `datasets`)
python3 -m spacy download en_core_web_sm
cp .env.example .env                     # fill in OPENAI_API_KEY
```

### Classifier (offline, `classifier/`)

```bash
python3 -m classifier.fetch_data     # downloads + labels training data into classifier/data/
python3 -m classifier.train          # extracts features, trains, evaluates, writes classifier/model.joblib
python3 -m classifier.sanity_check   # the only regression check in this repo — see "Testing" below
```

### Router service (online, `router_service/`)

```bash
uvicorn router_service.main:app --port 8000 --reload

curl -X POST http://127.0.0.1:8000/route -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'
curl http://127.0.0.1:8000/dashboard   # cost-savings dashboard, needs some /route traffic first
```

### Docker / Kubernetes

```bash
docker compose up -d --build                   # router + MongoDB together

minikube start --driver=docker
minikube addons enable metrics-server           # required for the HPA to report real metrics
minikube image load llmrouter-router:latest     # minikube has its own runtime, can't see host Docker images
kubectl apply -f k8s/mongo.yaml -f k8s/router-config.yaml -f k8s/router.yaml -f k8s/router-hpa.yaml
grep '^OPENAI_API_KEY=' .env | kubectl create secret generic router-secret --from-env-file=/dev/stdin
kubectl port-forward svc/router 8000:8000
```

### Testing

There is no automated test suite (no pytest). `classifier/sanity_check.py` is
the only regression check — it runs the trained model on hand-written,
out-of-distribution queries and prints the ranked difficulty scores for
manual eyeballing. Re-run it after every retrain. Held-out test-set accuracy
alone is not trusted in this repo (see "Architecture" below for why).

## Architecture

### Two independently-runnable components, joined at one seam

`classifier/` (offline training) and `router_service/` (online serving) are
deliberately kept separate — not just as folders, but as things that never
import application code from each other. The **one** intentional coupling
point is `classifier/features.py`: both `classifier/train.py` and
`router_service/difficulty.py` import `extract_features()` from it directly.
This is load-bearing, not incidental — if training-time and serving-time
feature computation ever diverge, the model silently gets garbage inputs in
production (train/serve skew). Any change to feature extraction must be made
in `classifier/features.py` and validated by re-running both
`classifier.train` and `classifier.sanity_check`.

`router_service/difficulty.py` loads `classifier/model.joblib` once at
**module import time** (not per-request). Retraining the classifier requires
restarting the router process — the new model is not picked up by a running
server.

### Request flow through `router_service/`

`main.py` orchestrates four separately-testable pieces in sequence:
`difficulty.py` (score 0–1) → `policy.py` (`choose_model()`, a single
threshold comparison) → `llm_client.py` (call the OpenAI Responses API) →
`logging_store.py` (fire-and-forget log write via FastAPI `BackgroundTasks`,
executed *after* the response is already sent — logging never adds latency
to the client-facing request).

`policy.py` is intentionally a single tiny function. The spec's optional
`max_cost`/`priority` request fields (not yet implemented) are meant to
extend `choose_model()` into a small rules engine without touching `main.py`
or anything upstream of it.

### Configuration

Everything tunable — model names, routing threshold, per-token cost rates,
Mongo connection — lives in `router_service/config.py`, read from environment
variables with defaults matching `.env.example`. Nothing downstream
hardcodes a model name or price; if you're changing a cost rate or model ID,
change it here (or via env var), not at the call site.

### One codebase, four deployment targets

The same `router_service` code runs unmodified as: a local `uvicorn`
process → `docker compose up` → a Minikube cluster → (documented, not
deployed — see README Phase 6) a real cloud cluster. The only thing that
changes between them is `MONGODB_URI`: `mongodb://localhost:27017` for local
dev, `mongodb://mongo:27017` for both Docker Compose and Kubernetes (both
resolve the hostname `mongo` via their own service discovery — Compose's
service name, k8s's Service object). This override lives in
`docker-compose.yml`'s `environment:` block and `k8s/router-config.yaml`,
never in `.env` itself.

Kubernetes-specific detail: `k8s/router.yaml` sets `imagePullPolicy: Never`
because the image is loaded into Minikube's own container runtime via
`minikube image load`, not pulled from a registry — Minikube does not share
the host machine's Docker daemon even though it runs via the Docker driver.
The `router-hpa.yaml` autoscaler requires `resources.requests.cpu` to be set
on the router container; without it there is no baseline to compute a CPU
percentage against, and the HPA cannot function.

### Dashboard

`router_service/dashboard.py` reads every logged document from MongoDB and
computes cost totals and latency percentiles **in Python**, not via a Mongo
aggregation pipeline — a deliberate choice at this data scale (hundreds, not
millions, of rows) favoring readability/debuggability over query
optimization. `compute_stats()` and `render_dashboard()` are separate
functions; the latter is a plain f-string HTML template with no templating
engine or JS charting library.

### A recurring class of bug worth knowing about

Multiple background processes in this project bind the same ports across
different environments (local `uvicorn`, Docker Compose's router container,
`kubectl port-forward` to the Minikube pod — all default to `localhost:8000`
or `:27017`). A stale process from an earlier session can silently shadow a
newer one on the same port, so a request appears to hit current code but
actually reaches old infrastructure. If a response doesn't match what the
code on disk should produce, check `ps aux | grep port-forward` and
`docker ps` for leftover processes before assuming the code is wrong.
