"""
Standing regression check: run the trained model on hand-written queries
that resemble real user input, not sampled from any training dataset.
Held-out test-set accuracy alone can hide dataset-shortcut problems (see
README) — re-run this after every retrain and eyeball the ordering.
"""

import joblib
import pandas as pd

from classifier.features import extract_features
from classifier.train import MODEL_PATH

bundle = joblib.load(MODEL_PATH)
pipeline = bundle["pipeline"]
feature_names = bundle["feature_names"]

queries = [
    "What's the capital of Japan?",
    "How do I reverse a linked list in Python?",
    "Write a short poem about the ocean.",
    "Can you explain step by step how compound interest works and why it grows faster over time than simple interest?",
    "What's 12 + 7?",
    "Compare the tradeoffs between REST and GraphQL APIs, and explain when you'd choose one over the other.",
    "hi",
    "Summarize the plot of Romeo and Juliet in one sentence.",
]

for q in queries:
    feats = extract_features(q)
    X = pd.DataFrame([feats], columns=feature_names)
    score = pipeline.predict_proba(X)[0][1]
    label = "HARD" if score >= 0.5 else "easy"
    print(f"[{label}  score={score:.2f}]  {q}")
