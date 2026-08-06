# Intelligent LLM Router & Cost-Optimization Gateway

A gateway that classifies each incoming query for difficulty and routes it to the
cheapest LLM tier capable of answering it correctly, instead of sending every
request to the most expensive model.

## Architecture

```
┌─────────────┐      ┌──────────────────────────────────────┐      ┌──────────────────┐
│   Client    │─────▶│            Router Service             │─────▶│  Cheap LLM tier   │
│ (curl, etc.)│      │  1. Score query difficulty (Phase 1)  │      │  (gpt-5.6-luna)   │
└─────────────┘      │  2. Apply threshold routing policy    │      └──────────────────┘
                      │  3. Call the selected LLM             │
                      │  4. Return the answer to the client   │      ┌──────────────────┐
                      │  5. Log the decision (background task)│─────▶│  Strong LLM tier  │
                      └────────────────────┬───────────────────┘      │  (gpt-5.6-sol)    │
                                           │                          └──────────────────┘
                                           ▼
                                ┌─────────────────────┐
                                │       MongoDB         │
                                │  routing_decisions     │
                                └──────────┬─────────────┘
                                           │
                                           ▼
                                ┌─────────────────────┐
                                │    GET /dashboard      │
                                │  cost savings, model    │
                                │  distribution, latency   │
                                └─────────────────────┘
```

Deployable as: a local Python process (Phase 2) → `docker compose up` (Phase 4) →
a local Kubernetes cluster with self-healing + autoscaling (Phase 5) → the same
manifests, unchanged, against a real cloud cluster (Phase 6, documented).

## Results

From a live test batch of 9 requests (small, manual, illustrative — not a
large-scale benchmark; see `GET /dashboard` for current live numbers):

| Metric | Value |
|---|---|
| Total cost savings vs. always using the strong model | $0.0026 (7.9%) |
| Queries routed to cheap tier | 6 of 9 (67%) |
| Queries routed to strong tier | 3 of 9 (33%) |
| p50 / p95 latency, cheap tier | 2,489 ms / 3,304 ms |
| p50 / p95 latency, strong tier | 2,579 ms / 16,305 ms |

The mechanism is what matters here, not the absolute dollar figure — at this
tiny scale a few cents saved is illustrative, but the same 60–70% cheap-tier
routing rate applied to real production traffic (thousands of queries/day) is
where this pattern actually pays for itself. The strong tier's much higher p95
latency is also expected and worth noting: harder queries get longer, more
deliberate responses from a larger model — the latency difference is a
consequence of the routing decision working as intended, not a performance bug.

## Status

- [x] Phase 1 — Data & Model (difficulty classifier)
- [x] Phase 2 — Router Service (local)
- [x] Phase 3 — Logging (MongoDB)
- [x] Phase 4 — Containerization
- [x] Phase 5 — Kubernetes (Minikube)
- [x] Phase 6 — Cloud deployment (documented, not deployed — see below)
- [x] Phase 7 — Dashboard & writeup

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_sm
cp .env.example .env   # fill in your real OPENAI_API_KEY — do not commit this file
```

## Phase 1: Difficulty Classifier

### What it does

`classifier/` trains a binary logistic regression classifier that scores a raw
text query from 0 (easy) to 1 (hard). The router (Phase 2) will use this score
with a threshold policy to decide which LLM tier handles a given query.

### How to run it

```bash
python3 -m classifier.fetch_data     # downloads and labels training data
python3 -m classifier.train          # extracts features, trains, evaluates, saves model.joblib
python3 -m classifier.sanity_check   # runs the model on hand-written queries as a smoke test
```

### Files

| File | Purpose |
|---|---|
| `fetch_data.py` | Downloads and labels training data into `data/raw_labeled.csv` |
| `features.py` | Shared feature extraction — imported by both training and (later) the live router, so features are computed identically in both places and avoid train/serve skew |
| `train.py` | Builds the feature matrix, trains the model, evaluates on a held-out test set, saves `model.joblib` |
| `sanity_check.py` | Standing regression check on hand-written, out-of-distribution queries — run after every retrain |

### Features (6, all fast/deterministic, no LLM calls)

`word_count`, `reasoning_keyword_count` (compare/explain why/step by step/etc.),
`question_mark_count`, `conjunction_count`, `entity_count` (spaCy NER),
`avg_word_length`, `rare_word_ratio` (fraction of words below a word-frequency
threshold, via `wordfreq` — a proxy for "technical/jargon density").

A deferred feature from the original spec: **embedding similarity to a labeled
set** ("historical difficulty of similar queries"). Skipped for v1 — it requires
standing up an embedding model + vector lookup for one feature. Noted as a
stretch goal.

### Training data

Difficulty labels come from four public benchmark datasets, combined so that
**both classes contain entity-rich and entity-sparse examples** (see "Key
decisions" below for why this matters):

- Easy (0): ARC-Easy (short science questions) + a 5,000-question sample of SQuAD
  (Wikipedia reading comprehension)
- Hard (1): GSM8K (multi-step math word problems) + ARC-Challenge (harder
  science reasoning)

~21,500 labeled queries total.

### Results

Logistic regression (`class_weight="balanced"`, features standardized via
`StandardScaler`), 80/20 train/test split:

- **87% accuracy** on held-out test set
- Precision/recall: easy 0.83/0.93, hard 0.93/0.83

### Key decisions & things that went wrong (worth reading before extending this)

1. **First attempt (ARC-Easy vs. ARC-Challenge only) scored 57% accuracy** —
   barely above a naive baseline. Root cause: ARC's difficulty split is about
   scientific-knowledge depth, which isn't visible in surface-level text
   features like length or keywords. Switching the model (logistic regression
   → gradient boosting) didn't help, confirming the bottleneck was the labels/
   features, not model capacity.

2. **Second attempt (ARC-Easy vs. GSM8K) scored 96% accuracy — and was
   wrong.** Manual testing on hand-written queries (not from either dataset)
   showed the model called *everything* "easy," including genuinely complex
   queries, while a bare "hi" scored higher than a real comparison question.
   Inspecting the logistic regression coefficients showed `entity_count` had
   ~4x the weight of any other feature — the model had learned "does this
   look like a GSM8K story problem" (which mention people/quantities → many
   named entities), not "is this hard." A high test-set score doesn't
   guarantee real generalization if the two classes differ systematically in
   writing style, not just difficulty — this needs a check against realistic
   out-of-distribution examples.

3. **Fix:** blend multiple genres into *both* classes (SQuAD added to easy,
   ARC-Challenge added to hard) so entity-density and length no longer
   perfectly predict the label. Accuracy dropped to 87% — expected and
   healthier, since the shortcut is gone. `entity_count`'s coefficient
   dropped from 4x-dominant to roughly in line with `word_count`, and manual
   sanity-check queries now rank in a sensible order (a REST-vs-GraphQL
   comparison scores higher than "hi").

4. **Known limitation:** this is still a proxy for difficulty, not ground
   truth, and the training data leans toward science/math/trivia domains. A
   production version would want broader domain coverage (code, creative
   writing, business reasoning, etc.).

5. **Design note:** the classifier outputs a continuous 0–1 score, not a
   binary label. The cheap/expensive routing decision is a *separate* policy
   (a threshold) applied in the router service — so adding a third model tier
   later just means adding a second threshold, not retraining anything.

## Phase 2: Router Service

### What it does

`router_service/` is a FastAPI app exposing `POST /route`. It scores the
incoming query with the Phase 1 classifier, picks a model tier via a
threshold policy, calls the LLM, and returns the answer plus routing
metadata (which model was used, the difficulty score, an estimated cost,
and latency).

### How to run it

```bash
cp .env.example .env   # fill in your real API key — do not commit this file
uvicorn router_service.main:app --port 8000 --reload
```

```bash
curl -X POST http://127.0.0.1:8000/route \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the capital of Japan?"}'
```

### Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app; `POST /route` ties the pieces below together and computes latency/cost |
| `config.py` | All tunables (API key, model names, routing threshold, cost rates) read from environment variables — nothing hardcoded, per spec section 8.4 |
| `difficulty.py` | Loads the trained classifier once at startup; imports `classifier.features` directly so scoring uses the exact same feature logic as training |
| `policy.py` | The threshold routing decision, isolated in its own function so it can grow into a richer rules engine later without touching the endpoint |
| `llm_client.py` | Thin wrapper around the LLM provider's API |

### LLM provider: OpenAI (switched from Anthropic)

The original plan was Claude (Haiku as the cheap tier, Sonnet as the strong
tier) — the classifier and routing logic are provider-agnostic, so this was
just a `llm_client.py` + `config.py` swap. The switch happened because the
Anthropic Console's "buy credits" button was stuck in a disabled state during
setup, and the developer already had a funded OpenAI account. Both providers
require a **separate paid API account** — distinct from any consumer chat
subscription — so this wasn't a way of avoiding that step, just a case where
one provider's billing was already in place.

- Cheap tier: `gpt-5.6-luna` ($0.20 / $1.20 per 1M input/output tokens)
- Strong tier: `gpt-5.6-sol` ($5.00 / $30.00 per 1M input/output tokens)
- Uses OpenAI's Responses API (`client.responses.create`, not the older Chat
  Completions API)

### Manual test results

| Query | Routed to | Difficulty score | Est. cost |
|---|---|---|---|
| "What is the capital of Japan?" | `gpt-5.6-luna` (cheap) | 0.193 | $0.000018 |
| "A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?" | `gpt-5.6-sol` (strong) | 0.553 | $0.001055 |

Both answered correctly, and both routed to the tier the difficulty score
implies (threshold = 0.3) — meeting the spec's Phase 2 acceptance criteria.

### Deferred from the spec

- **`max_cost` / `priority` optional request fields** (spec section 4.2) —
  the core `query`-only flow was built and verified first; these are policy
  variations that can layer on top of the same `choose_model()` function
  later without restructuring anything.
- **Async fire-and-forget logging** — this is Phase 3 (MongoDB). Right now
  a request's routing decision isn't persisted anywhere.

## Phase 3: Logging to MongoDB

### What it does

Every `/route` call writes a document to MongoDB after the response has
already been sent to the client — logging never adds latency to what the
caller experiences.

### How to run it

```bash
docker run -d --name llm-router-mongo -p 27017:27017 \
  -v llm-router-mongo-data:/data/db mongo:latest
```

MongoDB then just needs to be running (`docker start llm-router-mongo` on
subsequent sessions) — `router_service/logging_store.py` connects to it
automatically using `MONGODB_URI` from `.env` (defaults to
`mongodb://localhost:27017`).

### Files

| File | Purpose |
|---|---|
| `logging_store.py` | `log_decision(...)` — builds the log document and inserts it into MongoDB |

### Design decisions

- **Fire-and-forget via FastAPI's `BackgroundTasks`**, not an async Mongo
  driver (`motor`). `BackgroundTasks` runs the log write *after* the
  response is returned to the client — which is what the spec's "async,
  non-blocking" requirement is actually asking for — without the added
  complexity of a fully async database layer. A production system with much
  higher throughput might reach for `motor` or a message queue; for this
  project's scale, `BackgroundTasks` is the right-sized tool.
- **Only a SHA-256 hash of the query is stored**, not the raw text — per the
  spec's own privacy note ("avoid storing raw PII unnecessarily"). Enough to
  detect duplicate/repeated queries for analysis, without retaining what a
  user actually typed.
- **`baseline_cost_usd` is computed on every request**, even ones routed to
  the cheap model — it's what *this exact query* would have cost on the
  strong tier, using the same token counts. Summing this field vs.
  `estimated_cost_usd` across all logged requests is exactly the "cost
  savings vs. always using the strongest model" metric the spec's dashboard
  (Phase 7) needs.

### Verification

Queried the database directly after a live request — the log matched the
API response exactly (difficulty score, model used, both cost figures,
latency, token counts), with the query stored only as a hash. Meets the
spec's Phase 3 acceptance criteria: "querying the database shows accurate
logs matching live requests."

## Phase 4: Containerization

### What it does

Packages the router service into a Docker image and brings up the full
stack (router + MongoDB) with `docker compose up`.

### How to run it

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

### Files

| File | Purpose |
|---|---|
| `Dockerfile` | Router service image — installs runtime deps, copies `router_service/` and `classifier/`, runs uvicorn bound to `0.0.0.0` |
| `docker-compose.yml` | Brings up `mongo` + `router` together, wires them onto the same network |
| `requirements.txt` | Full local dev dependency list (includes `datasets`, used only by `classifier/fetch_data.py`) |
| `requirements-router.txt` | Container-only subset — leaner image, no training-only dependencies |
| `.dockerignore` | Excludes `venv/`, `.env`, and `classifier/data/` (large, regenerable, unneeded by the container) from the build context |

### Key decisions & gotchas

1. **Split requirements files.** The router container doesn't need
   `datasets` (only used to build training data, which never happens in
   production) — a separate `requirements-router.txt` keeps the image
   leaner than reusing the full dev `requirements.txt`.
2. **Bind to `0.0.0.0`, not the default `127.0.0.1`.** Inside a container,
   `127.0.0.1` means "this container, talking to itself" — the app would be
   completely unreachable from outside, even with the port mapped, if left
   at the uvicorn default.
3. **`MONGODB_URI` differs between local dev and the container.** Locally,
   the router connects to `mongodb://localhost:27017`. Inside Docker
   Compose's network, `localhost` would mean "inside the router's own
   container" — it has to use the **service name** `mongo` as the hostname,
   which Compose resolves automatically. `docker-compose.yml` overrides just
   this one variable; `.env` keeps the local-dev value for running the
   router directly with uvicorn.
4. **Secrets are never baked into the image.** `.env` is excluded via
   `.dockerignore`; API keys and other config are injected at container
   *runtime* via `env_file` in `docker-compose.yml`, not copied into an
   image layer.
5. **The trained model (`classifier/model.joblib`) is copied in as a build
   artifact**, not regenerated during the Docker build — training requires
   downloading datasets and takes real time; baking in the already-trained
   model file matches the spec's own framing of it as a "deliverable
   artifact... loaded by the Router Service at startup" (section 4.1).

### Verification

Ran the full request → routing → LLM call → MongoDB log path through the
containerized stack (not the host-installed services) and confirmed the
log landed in the compose-managed MongoDB with the router correctly
resolving the `mongo` hostname across the Docker network. Meets the spec's
Phase 4 acceptance criteria: "`docker-compose up` runs the full stack
locally with one command."

## Phase 5: Kubernetes Orchestration (Minikube)

### What it does

Deploys the same containerized stack onto a local Kubernetes cluster
(Minikube) — a Deployment + Service for MongoDB, a Deployment + Service for
the router, and a HorizontalPodAutoscaler (HPA) that automatically adjusts
the router's replica count based on CPU load.

### How to run it

```bash
minikube start --driver=docker
minikube addons enable metrics-server        # required for the HPA to report real metrics

docker compose build router                  # or `docker build -t llmrouter-router:latest .`
minikube image load llmrouter-router:latest   # Minikube has its own container runtime — it can't see images from the host Docker daemon otherwise

kubectl apply -f k8s/mongo.yaml
kubectl apply -f k8s/router-config.yaml
grep '^OPENAI_API_KEY=' .env | kubectl create secret generic router-secret --from-env-file=/dev/stdin
kubectl apply -f k8s/router.yaml
kubectl apply -f k8s/router-hpa.yaml

kubectl port-forward svc/router 8000:8000     # reach the service from your machine
```

### Files

| File | Purpose |
|---|---|
| `k8s/mongo.yaml` | MongoDB Deployment + PersistentVolumeClaim (data survives pod restarts) + Service |
| `k8s/router-config.yaml` | ConfigMap — non-secret tunables (model names, threshold) |
| `k8s/router.yaml` | Router Deployment (with CPU/memory resource requests, required for the HPA to work) + Service |
| `k8s/router-hpa.yaml` | HorizontalPodAutoscaler — scales the router 1→3 replicas if CPU exceeds 50% of its requested 200m |

### Key decisions & gotchas

1. **ConfigMap vs. Secret.** Non-sensitive config (model names, threshold)
   lives in a version-controlled `ConfigMap` YAML file. The API key lives in
   a `Secret`, created by piping *only* that one line from `.env` directly
   into `kubectl create secret` — the key value is never written into a YAML
   file or displayed anywhere in the process.
2. **`imagePullPolicy: Never`.** Minikube runs its own container runtime,
   separate from the host's Docker daemon — an image built via
   `docker compose build` isn't automatically visible to it. `minikube image
   load` copies it in, and `imagePullPolicy: Never` tells Kubernetes to use
   that local copy instead of trying (and failing) to pull `:latest` from a
   registry that doesn't have it.
3. **`resources.requests.cpu` is required for the HPA to function** — the
   autoscaler calculates "current usage" as a percentage *of the requested
   amount*, so without an explicit request, there's nothing for it to
   compute a percentage against.
4. **MongoDB uses a Deployment + PVC here, not a StatefulSet** (the more
   "correct" Kubernetes primitive for databases in production). Acceptable
   simplification at this project's scale — a single-replica database
   doesn't need StatefulSet's stable identity/ordering guarantees.

### Verification

Sent a full `/route` request through `kubectl port-forward` (not a
host-installed service) and confirmed the log landed in the in-cluster
MongoDB pod — the same request → classify → route → call LLM → log pipeline
verified in every previous phase, now running entirely inside Kubernetes.
`kubectl get hpa` shows the autoscaler actively reporting real CPU metrics
(`cpu: 9%/50%`). Meets the spec's Phase 5 acceptance criteria: "Service
reachable inside the cluster; horizontal pod autoscaler configured."

## Phase 6: Cloud Deployment

### Decision: documented, not actually deployed

Deliberately scoped out of this build. The reasoning: this project has near-
zero real traffic, and both AWS EKS and GCP GKE incur *ongoing* costs the
moment a cluster exists — AWS EKS charges a mandatory ~$0.10/hour control-
plane fee with no free-tier exemption; GCP GKE gives one free zonal cluster
but the underlying VM nodes still cost money, and every free-tier cloud
account still requires a credit card on file. As a student already paying
for two other API subscriptions, spending real money to keep infrastructure
running 24/7 for a portfolio project with no real users isn't a good
tradeoff — and it's a legitimate engineering judgment call, not a shortcut:
not over-provisioning idle infrastructure is itself a defensible decision
worth being able to explain.

### Why this is a legitimate stopping point, not a shortcut

**Kubernetes manifests are portable by design** — that's the actual point
of the abstraction. Every manifest in `k8s/` (`Deployment`, `Service`, `HPA`)
would `kubectl apply` against a real EKS or GKE cluster completely
unchanged. Only the *cluster provisioning* and a handful of environment-
specific details differ, laid out below.

### What would actually change, moving from Minikube to a real cloud cluster

1. **Provision the cluster** (one-time, cloud-side):
   ```bash
   # GCP GKE
   gcloud container clusters create llm-router --num-nodes=1 --zone=us-central1-a

   # AWS EKS
   eksctl create cluster --name llm-router --nodes 1
   ```
2. **Push the image to a registry** instead of `minikube image load` — cloud
   clusters can't see images that only exist on a local machine:
   ```bash
   docker tag llmrouter-router:latest gcr.io/<project-id>/llmrouter-router:latest
   docker push gcr.io/<project-id>/llmrouter-router:latest
   ```
   and update `k8s/router.yaml`'s `image:` field to match, removing
   `imagePullPolicy: Never` (that flag only makes sense for locally-loaded
   images).
3. **Change the router's Service from `ClusterIP` to `LoadBalancer`** in
   `k8s/router.yaml` — this is what actually gets you a public IP address.
   `ClusterIP` (what we used for Minikube) is only reachable from inside the
   cluster or via `kubectl port-forward`; it was the right choice there
   since the spec's own Phase 5 acceptance criteria only asks for
   "reachable inside the cluster." Phase 6's criteria ("publicly reachable
   endpoint") is exactly the `LoadBalancer` type's job.
4. **`kubectl apply -f k8s/`** — every manifest applies exactly as written;
   nothing about the Deployment, ConfigMap, Secret, or HPA needs to change.

### How this project would actually be demoed

Since there's no live public URL, "showing" this project relies on:

- **A live local demo** — `docker compose up` or the Minikube cluster,
  hitting the endpoint, showing the MongoDB log and (once built) the
  dashboard. Functionally identical to a cloud deployment, since that's the
  entire premise of containerization — this is a legitimate demonstration,
  not a lesser one.
- **A recorded walkthrough** (planned for Phase 7, once the dashboard
  exists) — a short video/GIF of the full request → routing → logging →
  dashboard flow, embedded in this README, so it's visible without anyone
  needing to run anything themselves.
- **An on-demand one-time cloud deployment**, only if a specific situation
  calls for a real live public URL (e.g. before a particular interview) —
  spin up GKE using free trial credit, record it working live, tear it down
  immediately after. Follows the exact steps above; costs nothing if done
  in one short sitting.

## Phase 7: Dashboard & Writeup

### What it does

A `GET /dashboard` endpoint that reads every logged routing decision from
MongoDB and renders the three things the spec's dashboard requires: total
cost savings vs. the naive "always use the strongest model" baseline, the
distribution of queries by model chosen, and latency percentiles (p50/p95/p99)
by model.

### How to run it

```bash
curl http://127.0.0.1:8000/dashboard   # or open it directly in a browser
```

Send a few requests to `POST /route` first — the dashboard is empty until
there's something logged.

### Files

| File | Purpose |
|---|---|
| `dashboard.py` | `compute_stats()` reads and aggregates the logged decisions; `render_dashboard()` builds the HTML page from those stats |

### Design decisions

- **Server-rendered HTML, no JS charting library.** The spec explicitly
  allows this ("a simple server-rendered HTML page... no external monitoring
  stack required"), and three numbers plus a two-bar comparison don't need
  more than plain CSS to represent clearly.
- **Percentiles computed in Python, not via a MongoDB aggregation operator.**
  At this data scale (hundreds, not millions, of logged decisions), pulling
  the raw values and sorting them in Python is simpler to read and debug
  than a `$percentile` aggregation pipeline stage — and it's transparent
  about exactly what's being computed, which matters more here than
  micro-optimizing a query that runs on a handful of documents.
- **Color and layout follow a validated categorical palette** (fixed hue
  order — cheap tier is always the same blue, strong tier always the same
  orange, never reassigned) with proper contrast in both light and dark
  mode, a legend, and direct value labels — rather than default,
  unstyled HTML.

### A debugging note worth keeping

While testing this phase, `GET /dashboard` returned 404 even after rebuilding
the Docker image with the new code. The cause: a `kubectl port-forward`
process from Phase 5 was still running in the background, silently
intercepting `localhost:8000` and routing requests to the old Kubernetes pod
(and its separate MongoDB) instead of the new Docker container — so every
test was hitting stale, unrelated infrastructure. Killing the leftover
process fixed it immediately. The general lesson: background processes
started in an earlier phase don't announce themselves, and "confirmed
correct code, but the running server disagrees" is a strong signal to check
for exactly this before assuming the code itself is wrong.

### Verification

Screenshotted the rendered dashboard after sending a mix of easy and hard
test queries — confirmed the headline savings figure, the two-bar routing
distribution, and the latency table all rendered correctly and matched the
underlying MongoDB data (see the Results section at the top of this
README).
