"""evaluate: metrikos skaičiuojamos tik čia -> metrics.json + tas pats MLflow run'as."""
import json
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    model = joblib.load(ROOT / "models/model.pkl")
    test = pd.read_parquet(ROOT / "data/processed/test.parquet")
    preds = model.predict(test["text"])
    y = test["label"]

    metrics = {
        "accuracy": accuracy_score(y, preds),
        "f1": f1_score(y, preds),
        "precision": precision_score(y, preds),
        "recall": recall_score(y, preds),
    }
    (ROOT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))

    # Metrikos rašomos į mokymo run'ą; nepavykus - klaida, ne tylus praleidimas
    run_id = (ROOT / "models/run_id.txt").read_text().strip()
    client = mlflow.MlflowClient()
    for key, value in metrics.items():
        client.log_metric(run_id, key, value)
    client.log_dict(
        run_id,
        {"labels": ["neg", "pos"], "matrix": confusion_matrix(y, preds).tolist()},
        "eval/confusion_matrix.json",
    )


if __name__ == "__main__":
    main()
