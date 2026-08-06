from router_service.config import CHEAP_MODEL, DIFFICULTY_THRESHOLD, STRONG_MODEL


def choose_model(difficulty_score: float) -> str:
    return CHEAP_MODEL if difficulty_score < DIFFICULTY_THRESHOLD else STRONG_MODEL
