import argparse
import os
import subprocess
import sys
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_info() -> tuple[str, str]:
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"], "false"
    try:
        dirty = git("status", "--porcelain", "--untracked-files=no", "--",
                    "src", "params.yaml", "dvc.yaml", "data/raw.dvc", "requirements-train.txt") != ""
        return git("rev-parse", "--short=8", "HEAD"), str(dirty).lower()
    except Exception:
        return "unknown", "unknown"


def dvc_md5(dvc_file: Path) -> str:
    try:
        return yaml.safe_load(dvc_file.read_text())["outs"][0]["md5"]
    except Exception:
        return "untracked"


def main() -> None:
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        sys.exit("MLFLOW_TRACKING_URI is not set. Point it at the cluster MLflow, e.g. http://127.0.0.1:5050")

    params = yaml.safe_load((ROOT / "params.yaml").read_text())["train"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--C", type=float)
    parser.add_argument("--max_features", type=int)
    parser.add_argument("--ngram_max", type=int)
    parser.add_argument("--random_seed", type=int)
    for key, value in vars(parser.parse_args()).items():
        if value is not None:
            params[key] = value

    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "imdb-sentiment"))
    train = pd.read_parquet(ROOT / "data/processed/train.parquet")

    model = Pipeline([
        ("tfidf", ColumnTransformer([
            ("text", TfidfVectorizer(
                max_features=params["max_features"],
                ngram_range=(1, params["ngram_max"]),
                sublinear_tf=True,
            ), "text"),
        ])),
        ("clf", LogisticRegression(
            C=params["C"], max_iter=1000, random_state=params["random_seed"],
        )),
    ])

    commit, dirty = git_info()
    run_name = f"tfidf-lr-C{params['C']}-ng{params['ngram_max']}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        mlflow.set_tags({
            "git_commit": commit,
            "git_dirty": dirty,
            "dvc_raw_md5": dvc_md5(ROOT / "data/raw.dvc"),
            "model_family": "tfidf-logreg",
        })
        mlflow.log_input(
            mlflow.data.from_pandas(train, source="data/processed/train.parquet", targets="label", name="imdb-train"),
            context="training",
        )

        model.fit(train[["text"]], train["label"])

        sample = train[["text"]].head(5)
        mlflow.sklearn.log_model(
            model,
            name="model",
            signature=infer_signature(sample, model.predict(sample)),
            pip_requirements=str(ROOT / "requirements-train.txt"),
            serialization_format="cloudpickle",
        )
        (ROOT / "models").mkdir(exist_ok=True)
        joblib.dump(model, ROOT / "models/model.pkl")
        (ROOT / "models/run_id.txt").write_text(run.info.run_id + "\n")
        print(f"run_id={run.info.run_id} name={run_name}")


if __name__ == "__main__":
    main()
