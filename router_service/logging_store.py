"""
Persists every routing decision to MongoDB, per spec section 4.3. Only a
hash of the query is stored, not the raw text — avoids storing PII we
don't need for cost/latency analysis.
"""

import hashlib
from datetime import datetime, timezone

from pymongo import MongoClient

from router_service.config import MONGODB_COLLECTION, MONGODB_DB, MONGODB_URI

_client = MongoClient(MONGODB_URI)
_collection = _client[MONGODB_DB][MONGODB_COLLECTION]


def log_decision(
    query: str,
    difficulty_score: float,
    model_used: str,
    estimated_cost_usd: float,
    baseline_cost_usd: float,
    latency_ms: int,
    token_count_input: int,
    token_count_output: int,
) -> None:
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query_hash": hashlib.sha256(query.encode()).hexdigest(),
        "difficulty_score": difficulty_score,
        "model_used": model_used,
        "estimated_cost_usd": estimated_cost_usd,
        "baseline_cost_usd": baseline_cost_usd,
        "latency_ms": latency_ms,
        "token_count_input": token_count_input,
        "token_count_output": token_count_output,
    }
    _collection.insert_one(doc)
