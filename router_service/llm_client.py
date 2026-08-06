"""
Thin wrapper around the OpenAI API. Returns the response text plus
token usage, so the caller can compute actual cost.
"""

from openai import OpenAI

from router_service.config import MAX_TOKENS, OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY)


def call_model(model: str, query: str) -> dict:
    response = _client.responses.create(
        model=model,
        input=query,
        max_output_tokens=MAX_TOKENS,
    )
    return {
        "answer": response.output_text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
