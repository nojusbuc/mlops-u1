# Mokymo Docker vaizdas

| | |
|---|---|
| Vaizdas | `ghcr.io/nojusbuc/mlops-u1/train:sha-PENDING` (laukia publikavimo) |
| Digest | PENDING |
| Platformos | linux/amd64, linux/arm64 |
| Bazė | `python:3.12.15-slim-trixie` (Debian 13) |
| Dockerfile | [`docker/Dockerfile.train`](../docker/Dockerfile.train) |

Tag'as `sha-<commit>` susieja vaizdą su kodu (`org.opencontainers.image.revision` ir run'o `git_commit` sutampa), digest'as fiksuoja turinį. `latest` nenaudojamas: jis keičiasi, nerodo commit'o ir neleidžia atkurti, kas tiksliai buvo paleista.

## Dydis

Matuota vietiniam arm64 vaizdui `sha-22239046` (`du -sh /` konteineryje).

| | |
|---|---|
| Rootfs (išpakuotas) | **818 MB** (NFR-09 riba 1 GB) |
| Docker `.Size` (suspaustas turinys) | 264 MB |
| `/opt/venv` | 630 MB: `pyarrow` 142, `scipy` 118, `pandas` 77, `sklearn` 57, `numpy` 40, `mlflow` 39 MB |
| `/app/data/processed` | 40 MB (įdėta, nes k8s Job'as nepasiekia lokalaus DVC remote) |

`mlflow-skinny` vietoj pilno `mlflow`: mokymui reikia tik kliento, be serverio ir UI priklausomybių. Multi-stage build: `pip` cache ir build failai nepatenka į galutinį sluoksnį.

## Trivy

Trivy 0.76.1, 2026-10-21, `--scanners vuln --severity HIGH,CRITICAL`. Pilna lentelė: [`trivy-train.txt`](trivy-train.txt).

- **CRITICAL 0**: vartas `trivy image --severity CRITICAL --exit-code 1` grąžina 0. Tas pats vartas yra `scripts/publish.sh` prieš push.
- **HIGH 44**: 8 unikalūs CVE, visi Debian bazės paketuose (`util-linux`, `ncurses`, `libacl1`, `libsystemd0`, `perl-base`), pataisytų versijų dar nėra. Mokymo procesas jų nenaudoja ir veikia ne root. Python paketuose radinių nėra.
- Ne root: `docker run --rm --entrypoint id <vaizdas> -u` → `1000`.
