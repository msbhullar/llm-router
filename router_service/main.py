import time

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from router_service.config import (
    CHEAP_INPUT_COST_PER_TOKEN,
    CHEAP_MODEL,
    CHEAP_OUTPUT_COST_PER_TOKEN,
    STRONG_INPUT_COST_PER_TOKEN,
    STRONG_OUTPUT_COST_PER_TOKEN,
)
from router_service.dashboard import compute_stats, render_dashboard
from router_service.difficulty import score_difficulty
from router_service.llm_client import call_model
from router_service.logging_store import log_decision
from router_service.policy import choose_model

app = FastAPI(title="LLM Router")


class RouteRequest(BaseModel):
    query: str


class RouteResponse(BaseModel):
    answer: str
    model_used: str
    difficulty_score: float
    estimated_cost: float
    latency_ms: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return render_dashboard(compute_stats())


@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest, background_tasks: BackgroundTasks):
    start = time.perf_counter()

    difficulty_score = score_difficulty(req.query)
    model = choose_model(difficulty_score)

    result = call_model(model, req.query)
    input_tokens, output_tokens = result["input_tokens"], result["output_tokens"]

    if model == CHEAP_MODEL:
        input_rate, output_rate = CHEAP_INPUT_COST_PER_TOKEN, CHEAP_OUTPUT_COST_PER_TOKEN
    else:
        input_rate, output_rate = STRONG_INPUT_COST_PER_TOKEN, STRONG_OUTPUT_COST_PER_TOKEN

    estimated_cost = input_tokens * input_rate + output_tokens * output_rate
    baseline_cost = input_tokens * STRONG_INPUT_COST_PER_TOKEN + output_tokens * STRONG_OUTPUT_COST_PER_TOKEN
    latency_ms = int((time.perf_counter() - start) * 1000)

    background_tasks.add_task(
        log_decision,
        query=req.query,
        difficulty_score=round(difficulty_score, 3),
        model_used=model,
        estimated_cost_usd=round(estimated_cost, 6),
        baseline_cost_usd=round(baseline_cost, 6),
        latency_ms=latency_ms,
        token_count_input=input_tokens,
        token_count_output=output_tokens,
    )

    return RouteResponse(
        answer=result["answer"],
        model_used=model,
        difficulty_score=round(difficulty_score, 3),
        estimated_cost=round(estimated_cost, 6),
        latency_ms=latency_ms,
    )
