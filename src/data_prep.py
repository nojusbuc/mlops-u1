"""prepare: IMDB train+test -> išvalyti, be dublikatų, stratifikuotai padalyti."""
from pathlib import Path

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw"
OUT_DIR = ROOT / "data/processed"


def main() -> None:
    params = yaml.safe_load((ROOT / "params.yaml").read_text())["prepare"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Oficialų 25k/25k padalijimą sujungiame ir dalijame patys pagal params.yaml
    df = pd.concat(
        [pd.read_parquet(RAW_DIR / f"{split}.parquet") for split in ("train", "test")],
        ignore_index=True,
    )
    df["text"] = df["text"].str.replace(r"<br\s*/?>", " ", regex=True).str.strip()

    # Tas pats atsiliepimas negali patekti ir į mokymo, ir į testinę imtį (NFR-02)
    before = len(df)
    df = df.drop_duplicates(subset="text").reset_index(drop=True)
    print(f"Dropped {before - len(df)} duplicate reviews")

    train, test = train_test_split(
        df,
        test_size=params["test_size"],
        random_state=params["seed"],
        stratify=df["label"],
    )
    train.to_parquet(OUT_DIR / "train.parquet", index=False)
    test.to_parquet(OUT_DIR / "test.parquet", index=False)
    print(f"Train: {len(train)}, Test: {len(test)}")


if __name__ == "__main__":
    main()
