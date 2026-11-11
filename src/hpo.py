import argparse
import os
import sys

import mlflow
import optuna
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from train import ROOT, VAL_SIZE, build_model, dvc_md5, git_info


def main() -> None:
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        sys.exit("MLFLOW_TRACKING_URI is not set. Point it at the cluster MLflow, e.g. http://127.0.0.1:5050")

    parser = argparse.ArgumentParser()
    parser.add_argument("--n-trials", type=int, default=10)
    args = parser.parse_args()

    params = yaml.safe_load((ROOT / "params.yaml").read_text())["train"]
    seed = params["random_seed"]

    train = pd.read_parquet(ROOT / "data/processed/train.parquet")
    fit_part, val = train_test_split(train, test_size=VAL_SIZE, stratify=train["label"], random_state=seed)

    def objective(trial: optuna.Trial) -> float:
        trial_params = {
            **params,
            "C": trial.suggest_float("C", 0.01, 100, log=True),
            "max_features": trial.suggest_categorical("max_features", [10000, 25000, 50000]),
            "ngram_max": trial.suggest_int("ngram_max", 1, 2),
        }
        with mlflow.start_run(run_name=f"trial-{trial.number}", nested=True):
            mlflow.log_params(trial_params)
            model = build_model(trial_params).fit(fit_part[["text"]], fit_part["label"])
            val_accuracy = accuracy_score(val["label"], model.predict(val[["text"]]))
            mlflow.log_metric("val_accuracy", val_accuracy)
        print(f"trial {trial.number}: {trial.params} val_accuracy={val_accuracy:.4f}")
        return val_accuracy

    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "imdb-sentiment"))
    mlflow.set_system_metrics_sampling_interval(1)
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    commit, dirty = git_info()
    with mlflow.start_run(run_name="hpo-optuna", log_system_metrics=True):
        mlflow.set_tags({
            "git_commit": commit,
            "git_dirty": dirty,
            "dvc_raw_md5": dvc_md5(ROOT / "data/raw.dvc"),
            "seed": seed,
            "hpo": "optuna-tpe",
        })
        mlflow.log_param("n_trials", args.n_trials)
        mlflow.log_input(
            mlflow.data.from_pandas(train, source="data/processed/train.parquet", targets="label", name="imdb-train"),
            context="training",
        )

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed, n_startup_trials=5))
        study.optimize(objective, n_trials=args.n_trials)

        mlflow.log_params({f"best_{key}": value for key, value in study.best_params.items()})
        mlflow.log_metric("best_val_accuracy", study.best_value)
        print(f"best: {study.best_params} val_accuracy={study.best_value:.4f}")


if __name__ == "__main__":
    main()
