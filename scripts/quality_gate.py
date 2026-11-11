import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def passes(metrics, min_accuracy):
    return metrics["accuracy"] >= min_accuracy


def main():
    metrics = json.loads((ROOT / "metrics.json").read_text())
    min_accuracy = yaml.safe_load((ROOT / "params.yaml").read_text())["gate"]["min_accuracy"]
    accuracy = metrics["accuracy"]

    if passes(metrics, min_accuracy):
        print(f"gate: accuracy {accuracy:.4f} >= {min_accuracy:.4f} -> PASS")
    else:
        print(f"gate: accuracy {accuracy:.4f} < {min_accuracy:.4f} -> FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
