import os

import mlflow
from mlflow import MlflowClient


def load_champion():
    name = os.environ.get("MODEL_NAME", "imdb-sentiment")
    alias = os.environ.get("MODEL_ALIAS", "champion")

    client = MlflowClient()
    mv = client.get_model_version_by_alias(name, alias)
    model = mlflow.pyfunc.load_model(f"models:/{name}/{mv.version}")

    info = {
        "name": name,
        "alias": alias,
        "version": mv.version,
        "run_id": mv.run_id,
    }
    return model, info
