"""
Central configuration for the router service. Everything here is
overridable via environment variables (loaded from a .env file), per
spec section 8.4 — no hardcoded model names, thresholds, or cost rates.
"""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

CHEAP_MODEL = os.environ.get("CHEAP_MODEL", "gpt-5.6-luna")
STRONG_MODEL = os.environ.get("STRONG_MODEL", "gpt-5.6-sol")

# Below this difficulty score, route to the cheap model; at or above, the strong model.
DIFFICULTY_THRESHOLD = float(os.environ.get("DIFFICULTY_THRESHOLD", "0.3"))

MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1024"))

# $ per token (converted from published $ per 1M tokens), used for cost estimation/logging.
CHEAP_INPUT_COST_PER_TOKEN = float(os.environ.get("CHEAP_INPUT_COST_PER_TOKEN", 0.20 / 1_000_000))
CHEAP_OUTPUT_COST_PER_TOKEN = float(os.environ.get("CHEAP_OUTPUT_COST_PER_TOKEN", 1.20 / 1_000_000))
STRONG_INPUT_COST_PER_TOKEN = float(os.environ.get("STRONG_INPUT_COST_PER_TOKEN", 5.00 / 1_000_000))
STRONG_OUTPUT_COST_PER_TOKEN = float(os.environ.get("STRONG_OUTPUT_COST_PER_TOKEN", 30.00 / 1_000_000))

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "llm_router")
MONGODB_COLLECTION = os.environ.get("MONGODB_COLLECTION", "routing_decisions")
