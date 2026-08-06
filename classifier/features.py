"""
Shared feature extraction for the difficulty classifier.

Imported by both classifier/train.py (training time) and the router
service (inference time), so features are computed identically in both
places — avoids train/serve skew.
"""

import re

import spacy
from wordfreq import zipf_frequency

_nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])

RARE_WORD_ZIPF_THRESHOLD = 3.5

REASONING_KEYWORDS = [
    "compare", "explain why", "step by step", "why", "how does",
    "analyze", "evaluate", "what if", "in order to", "because",
    "difference between", "relationship between",
]

CONJUNCTIONS = {"and", "or", "but"}

FEATURE_NAMES = [
    "word_count",
    "reasoning_keyword_count",
    "question_mark_count",
    "conjunction_count",
    "entity_count",
    "avg_word_length",
    "rare_word_ratio",
]


def extract_features(text: str) -> dict:
    doc = _nlp(text)
    words = [tok.text for tok in doc if tok.is_alpha]
    lower_text = text.lower()

    word_count = len(words)
    reasoning_keyword_count = sum(1 for kw in REASONING_KEYWORDS if kw in lower_text)
    question_mark_count = text.count("?")
    conjunction_count = sum(1 for tok in doc if tok.text.lower() in CONJUNCTIONS)
    entity_count = len(doc.ents)
    avg_word_length = (sum(len(w) for w in words) / word_count) if word_count else 0.0

    if words:
        rare_count = sum(1 for w in words if zipf_frequency(w.lower(), "en") < RARE_WORD_ZIPF_THRESHOLD)
        rare_word_ratio = rare_count / word_count
    else:
        rare_word_ratio = 0.0

    return {
        "word_count": word_count,
        "reasoning_keyword_count": reasoning_keyword_count,
        "question_mark_count": question_mark_count,
        "conjunction_count": conjunction_count,
        "entity_count": entity_count,
        "avg_word_length": round(avg_word_length, 2),
        "rare_word_ratio": round(rare_word_ratio, 2),
    }
