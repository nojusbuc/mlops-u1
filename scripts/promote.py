import argparse
import os
import sys
from pathlib import Path

from mlflow import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "imdb-sentiment"
ALIAS = "champion"


def main():
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        sys.exit("MLFLOW_TRACKING_URI is not set")

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=str, help="which version to promote, default is version from models/run_id.txt")
    args = parser.parse_args()

    client = MlflowClient()
    version = args.version

    if version is None:
        run_id = (ROOT / "models/run_id.txt").read_text().strip()
        versions = client.search_model_versions(f"name='{MODEL_NAME}' and run_id='{run_id}'")
        if len(versions) == 0:
            sys.exit(f"no registered version for run {run_id}")
        version = versions[0].version

    client.set_registered_model_alias(MODEL_NAME, ALIAS, version)
    mv = client.get_model_version(MODEL_NAME, version)
    print(f"{MODEL_NAME}@{ALIAS} -> version {version} (run {mv.run_id})")


if __name__ == "__main__":
    main()
