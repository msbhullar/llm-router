"""
Loads the trained difficulty classifier once at startup and exposes a
single function to score a query. Imports classifier.features directly
so feature computation is guaranteed identical to training time.
"""

import joblib
import pandas as pd

from classifier.features import extract_features
from classifier.train import MODEL_PATH

_bundle = joblib.load(MODEL_PATH)
_pipeline = _bundle["pipeline"]
_feature_names = _bundle["feature_names"]


def score_difficulty(query: str) -> float:
    feats = extract_features(query)
    X = pd.DataFrame([feats], columns=_feature_names)
    return float(_pipeline.predict_proba(X)[0][1])
