"""
Downloads a multi-source labeled dataset combining several distinct
question genres per difficulty tier, so the classifier can't shortcut on
dataset-specific writing style (e.g. "contains named entities") instead
of learning genuine difficulty signal.

Easy (0): ARC-Easy (short science, entity-sparse) + SQuAD (Wikipedia
          reading comprehension, entity-rich) -> entities appear on the
          easy side too.
Hard (1): GSM8K (narrative math word problems, entity-rich) + ARC-Challenge
          (short science reasoning, entity-sparse) -> low-entity examples
          appear on the hard side too.
"""

from pathlib import Path

import pandas as pd
from datasets import load_dataset

OUT_DIR = Path(__file__).parent / "data"
OUT_PATH = OUT_DIR / "raw_labeled.csv"

SQUAD_SAMPLE_SIZE = 5000


def load_arc(config_name: str, difficulty: int) -> pd.DataFrame:
    ds = load_dataset("allenai/ai2_arc", config_name, split="train+validation+test")
    df = ds.to_pandas()[["question"]].rename(columns={"question": "query"})
    df["difficulty"] = difficulty
    return df


def load_gsm8k() -> pd.DataFrame:
    ds = load_dataset("openai/gsm8k", "main", split="train+test")
    df = ds.to_pandas()[["question"]].rename(columns={"question": "query"})
    df["difficulty"] = 1
    return df


def load_squad_sample() -> pd.DataFrame:
    ds = load_dataset("rajpurkar/squad", split="train")
    df = ds.to_pandas()[["question"]].rename(columns={"question": "query"})
    df = df.sample(n=SQUAD_SAMPLE_SIZE, random_state=42)
    df["difficulty"] = 0
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    parts = [
        load_arc("ARC-Easy", difficulty=0),
        load_arc("ARC-Challenge", difficulty=1),
        load_gsm8k(),
        load_squad_sample(),
    ]

    combined = pd.concat(parts, ignore_index=True)
    combined = combined.drop_duplicates(subset="query").sample(frac=1, random_state=42).reset_index(drop=True)

    combined.to_csv(OUT_PATH, index=False)

    print(f"Saved {len(combined)} labeled queries to {OUT_PATH}")
    print(f"  easy (0): {(combined['difficulty'] == 0).sum()}")
    print(f"  hard (1): {(combined['difficulty'] == 1).sum()}")


if __name__ == "__main__":
    main()
