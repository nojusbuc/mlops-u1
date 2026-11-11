# Inferencijos API apkrovos testas

|               |                                                                |
| ------------- | -------------------------------------------------------------- |
| Data          | 2026-11-11                                                     |
| Vaizdas       | `ghcr.io/nojusbuc/mlops-u1/serve:sha-1418dd44`                 |
| Vaizdo dydis  | 1.05 GB (lokalus, linux/arm64)                                 |
| Modelis       | `imdb-sentiment@champion`, versija 1                           |
| Endpoint'as   | `POST /predict`, viena recenzija per užklausą                  |
| Užklausų      | 200, viena po kitos (ne lygiagrečiai)                          |
| Prieiga       | `kubectl port-forward svc/inference 8080:80`                   |
| Aplinka       | kind klasteris, MacBook Air (Apple M2), 1 replika, limitas 1 CPU |
| Skriptas      | [`scripts/load_test.py`](../scripts/load_test.py)              |

## Paleidimas

```bash
kubectl -n mlops-u1 port-forward svc/inference 8080:80
python scripts/load_test.py
```

## Rezultatai

| Metrika    | Reikšmė     |
| ---------- | ----------- |
| Klaidos    | 0 / 200     |
| Vidurkis   | 5.8 ms      |
| p50        | 4.1 ms      |
| **p95**    | **13.4 ms** |
| p99        | 23.1 ms     |
| Pralaidumas | 173.0 req/s |

```
requests:   200
errors:     0
mean:       5.8 ms
p50:        4.1 ms
p95:        13.4 ms
p99:        23.1 ms
throughput: 173.0 req/s
```

## Pastabos

- Matuojama iš kliento pusės, todėl laikas apima ir `port-forward` tunelį. Pats modelis (TF-IDF + logistinė regresija) vieną tekstą klasifikuoja greičiau nei per 2 ms (lokalus testas be klasterio).
- Užklausos siunčiamos nuosekliai, todėl pralaidumas rodo vieno kliento greitį, o ne maksimalų API pajėgumą.
- p95 13.4 ms reiškia, kad 95 % užklausų atsakytos greičiau nei per 13.4 ms.
