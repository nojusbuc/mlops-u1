"""Atkuria istorinį MLflow run'ą: python reproduce.py <run_id> [--tolerance 0.005]

Run'o git_commit -> tas pats kodas, params.yaml ir dvc.lock; dvc_raw_md5 -> tie patys duomenys.
Tada dvc repro --force ir metrikų palyginimas su originalu.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import mlflow
import yaml

ROOT = Path(__file__).resolve().parent
METRICS = ("accuracy", "f1")


def sh(*cmd: str) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--tolerance", type=float, default=0.005)
    args = parser.parse_args()
    started = time.time()

    # Skriptas baigiasi git checkout --force, todėl neleidžiame prarasti necommit'intų pakeitimų
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("Uncommitted changes: commit or stash them first")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        sys.exit("Detached HEAD: check out a branch first")

    original = mlflow.get_run(args.run_id)
    tags = original.data.tags
    commit = tags.get("git_commit", "unknown")
    if commit == "unknown":
        sys.exit("Run has no git_commit tag")
    if tags.get("git_dirty") == "true":
        sys.exit("Run was trained from a dirty working tree; its exact code is not in git")

    ok = False
    new_id = "none"
    try:
        sh("git", "checkout", "--quiet", commit)
        sh("dvc", "pull", "--quiet", "data/raw.dvc")

        md5 = yaml.safe_load((ROOT / "data/raw.dvc").read_text())["outs"][0]["md5"]
        if md5 != tags.get("dvc_raw_md5"):
            sys.exit(f"Data at {commit} is {md5}, but the run used {tags.get('dvc_raw_md5')}")

        # params.yaml šiame commit'e turi sutapti su run'o parametrais (lyginame, netaisome)
        train_params = yaml.safe_load((ROOT / "params.yaml").read_text())["train"]
        diff = {k: (str(v), original.data.params.get(k)) for k, v in train_params.items()
                if str(v) != original.data.params.get(k)}
        if diff:
            sys.exit(f"params.yaml at {commit} differs from the run (file, run): {diff}")

        sh("dvc", "repro", "--force")
        new_id = (ROOT / "models/run_id.txt").read_text().strip()
        mlflow.MlflowClient().set_tag(new_id, "reproduces", args.run_id)
        reproduced = mlflow.get_run(new_id).data.metrics

        ok = True
        for key in METRICS:
            delta = abs(reproduced[key] - original.data.metrics[key])
            ok &= delta <= args.tolerance
            print(f"{key}: original={original.data.metrics[key]:.4f} "
                  f"reproduced={reproduced[key]:.4f} delta={delta:.4f}")
    finally:
        # Grąžiname šaką ir jos duomenis/modelius, kad darbo medis liktų kaip prieš paleidimą
        sh("git", "checkout", "--quiet", "--force", branch)
        sh("dvc", "checkout", "--quiet", "--force")

    print(f"{'REPRODUCED' if ok else 'MISMATCH'} in {time.time() - started:.0f}s -> new run {new_id}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
