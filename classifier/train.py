"""
Trains the difficulty classifier on ARC-Easy/ARC-Challenge features and
serializes the fitted pipeline to classifier/model.joblib.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from classifier.features import FEATURE_NAMES, extract_features

DATA_PATH = Path(__file__).parent / "data" / "raw_labeled.csv"
MODEL_PATH = Path(__file__).parent / "model.joblib"


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    rows = [extract_features(q) for q in df["query"]]
    return pd.DataFrame(rows, columns=FEATURE_NAMES)


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} labeled queries")

    print("Extracting features (this calls spaCy + wordfreq on every row, may take a bit)...")
    X = build_feature_matrix(df)
    y = df["difficulty"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("\n--- Evaluation on held-out test set ---")
    print(classification_report(y_test, y_pred, target_names=["easy", "hard"]))
    print("Confusion matrix (rows=actual, cols=predicted):")
    print(confusion_matrix(y_test, y_pred))

    joblib.dump({"pipeline": pipeline, "feature_names": FEATURE_NAMES}, MODEL_PATH)
    print(f"\nSaved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()
