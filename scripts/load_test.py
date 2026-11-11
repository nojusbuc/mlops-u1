import argparse
import time

import numpy as np
import requests

TEXT = "This movie was surprisingly good, the acting was great and the story kept me interested, but the final act fell flat and was quite predictable and not overall that satisfying, but I would say it was quite good"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080/predict")
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args()

    latencies = []
    errors = 0
    start = time.perf_counter()
    for _ in range(args.n):
        t0 = time.perf_counter()
        response = requests.post(args.url, json={"texts": [TEXT]})
        latencies.append((time.perf_counter() - t0) * 1000)
        if response.status_code != 200:
            errors += 1
    total = time.perf_counter() - start

    print(f"requests:   {args.n}")
    print(f"errors:     {errors}")
    print(f"mean:       {np.mean(latencies):.1f} ms")
    print(f"p50:        {np.percentile(latencies, 50):.1f} ms")
    print(f"p95:        {np.percentile(latencies, 95):.1f} ms")
    print(f"p99:        {np.percentile(latencies, 99):.1f} ms")
    print(f"throughput: {args.n / total:.1f} req/s")


if __name__ == "__main__":
    main()
