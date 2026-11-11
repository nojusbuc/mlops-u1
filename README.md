# IMDB atsiliepimų nuotaikos klasifikatorius: U1–U2 MLOps projektas

Repo: https://github.com/nojusbuc/mlops-u1, tag'ai `u1-final`, `u2-final`.

Atkartojamas DVC pipeline'as (`prepare → train → evaluate`) ir savas MLflow Tracking Server lokaliame `kind` klasteryje.
U2: Optuna HPO, MLflow Model Registry (`@champion`), FastAPI inferencijos API tame pačiame klasteryje, CI/CD su kokybės vartu ir rollback.
Modelis: TF-IDF + logistinė regresija, duomenys `stanfordnlp/imdb`. Išbandyta macOS 26 (Apple Silicon, Docker Desktop).

- **Portai:** MLflow UI ir API http://127.0.0.1:5050 (kind NodePort 30500, tik `127.0.0.1`). Inferencijos API http://127.0.0.1:8080 per `kubectl port-forward` (11 žingsnis). Postgres tik klasterio viduje (`postgres:5432`).
- **Prisijungimai:** MLflow su basic auth (naudotojas `admin`). MLflow ir Postgres slaptažodžiai tik Kubernetes Secret'uose `mlflow-credentials` ir `postgres-credentials` (sukuriami 2 žingsnyje, Git'e jų nėra).
- **Rezultatai:** MLflow eksperimentas ir registruotas modelis `imdb-sentiment` (`@champion`); `metrics.json` (`dvc metrics show`); KPI ir išmatuotos reikšmės `docs/requirements.md`; apkrovos testas `docs/load-test.md`; vaizdas ir Trivy `docs/docker-image.md`; ataskaitos `docs/u1-report.md`, `docs/u2-report.md`; ekrano nuotraukos `docs/img/`.

## Reikalavimai

- Docker su ≥ 6 GB RAM (MLflow ≈ 1,7 GiB, Postgres ≈ 50 MiB, kind mazgas).
- Laisvas `5050` portas (`5000` macOS užima AirPlay Receiver).

| Įrankis | Versija |
| --- | --- |
| Docker Desktop | 28.5 |
| kind | 0.33.0 |
| kubectl | 1.34 |
| uv (Python 3.12 parsiunčia pats) | 0.10 |
| DVC, MLflow | 3.67.1, 3.17.2 (`requirements.txt`) |
| Trivy, gh | 0.76, 2.76 (tik vaizdo publikavimui) |

```sh
brew install kind kubectl uv trivy gh
```

## Paleidimas nuo nulio

### 1. Repo ir Python aplinka

```sh
git clone https://github.com/nojusbuc/mlops-u1.git && cd mlops-u1
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
source .venv/bin/activate
```

### 2. Klasteris ir MLflow

Pirmą kartą siunčiami Postgres ir MLflow vaizdai (~1,5 GB), tai užtrunka kelias minutes. Pabaigoje `curl` atsako `OK`.

```sh
kind create cluster --config k8s/kind-config.yaml
kubectl apply -f k8s/namespace.yaml
kubectl -n mlops-u1 create secret generic postgres-credentials \
  --from-literal=POSTGRES_USER=mlflow --from-literal=POSTGRES_DB=mlflow \
  --from-literal=POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
kubectl -n mlops-u1 create secret generic mlflow-credentials \
  --from-literal=MLFLOW_TRACKING_USERNAME=admin \
  --from-literal=MLFLOW_TRACKING_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(16))')" \
  --from-literal=MLFLOW_FLASK_SERVER_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
kubectl apply -k k8s/
kubectl -n mlops-u1 rollout status deploy/mlflow --timeout=300s
curl -sf http://127.0.0.1:5050/health; echo
```

MLflow klientas prisijungimus ima iš aplinkos kintamųjų. Kiekviename naujame terminale:

```sh
export MLFLOW_TRACKING_URI=http://127.0.0.1:5050
export MLFLOW_TRACKING_USERNAME=admin
export MLFLOW_TRACKING_PASSWORD=$(kubectl -n mlops-u1 get secret mlflow-credentials -o jsonpath='{.data.MLFLOW_TRACKING_PASSWORD}' | base64 -d)
```

UI: http://127.0.0.1:5050 (naudotojas `admin`, slaptažodis `echo $MLFLOW_TRACKING_PASSWORD`).

### 3. Duomenys

DVC remote yra lokalus katalogas `../mlops-u1-dvcstore` (šalia repo):

```sh
dvc pull
```

Jei remote katalogo nėra (kitas kompiuteris), duomenys parsiunčiami iš Hugging Face fiksuotos revizijos; `git diff` turi būti tuščias, t. y. md5 sutampa su `data/raw.dvc`:

```sh
curl -fsSL --create-dirs -o "data/raw/#1.parquet" \
  "https://huggingface.co/datasets/stanfordnlp/imdb/resolve/e6281661ce1c48d982bc483cf8a173c1bbeb5d31/plain_text/{train,test}-00000-of-00001.parquet"
dvc commit -f data/raw.dvc
git diff --exit-code data/raw.dvc && echo "duomenys sutampa"
dvc push
```

### 4. Pipeline: trys run'ai

`train.py` be `MLFLOW_TRACKING_URI` nepasileidžia, kad run'ai nepatektų į lokalų `mlruns/`.
`params.yaml` commit'inamas **prieš** `dvc repro`: run'o `git_commit` tag'as tada turi lygiai tuos parametrus, ir `reproduce.py` gali jį atkurti.

```sh
export MLFLOW_TRACKING_URI=http://127.0.0.1:5050
for c in 0.1 10.0 1.0; do
  python -c "import yaml,sys; p=yaml.safe_load(open('params.yaml')); p['train']['C']=float(sys.argv[1]); yaml.safe_dump(p,open('params.yaml','w'),sort_keys=False)" $c
  git commit -m "params: C=$c" params.yaml
  dvc repro
  git add dvc.lock metrics.json models/run_id.txt && git commit -m "run: C=$c"
done
dvc push
```

Pakeitus `train` parametrą, `dvc status` rodo pasikeitusį `train`; `dvc repro` perleidžia tik `train` ir `evaluate`. `prepare` perleidžiamas tik pakeitus `prepare` parametrus (`test_size`, `seed`), jo kodą arba duomenis. `dvc.lock` pasikeičia pakeisto stage'o `params` ir jo išvesčių md5.

### 5. Rezultatai

- MLflow UI → eksperimentas `imdb-sentiment`; run'ai `tfidf-lr-C<C>-ng<ngram_max>`: parametrai, `accuracy`, `f1`, `precision`, `recall`, tag'ai `git_commit`, `git_dirty`, `dvc_raw_md5`, modelis, duomenų rinkinys, `eval/confusion_matrix.json`.
- `dvc metrics show`; palyginimas `dvc params diff HEAD~4` ir `dvc metrics diff HEAD~4`.
- Imtys nesidalija atsiliepimais (NFR-02), turi išvesti `0`:

```sh
python -c "import pandas as pd; a=pd.read_parquet('data/processed/train.parquet'); b=pd.read_parquet('data/processed/test.parquet'); print(len(set(a.text) & set(b.text)))"
```

### 6. Hiperparametrų paieška (HPO)

`src/hpo.py`: Optuna (TPE, pirmi 5 bandymai atsitiktiniai) ieško `C` (0,01–100, log skalė), `max_features` (10 000 / 25 000 / 50 000) ir `ngram_max` (1–2). Bandymai vertinami validacijos imtyje (10 % mokymo imties), testinė imtis nenaudojama. Reikia 2 žingsnio `export`'ų.

```sh
python src/hpo.py --n-trials 10
```

MLflow UI → `imdb-sentiment`: tėvinis run'as `hpo-optuna` (išskleidus matyti `trial-0` ... `trial-9`), jame `best_C`, `best_max_features`, `best_ngram_max` ir `best_val_accuracy`. Geriausi parametrai įrašomi į `params.yaml` `train` skyrių ir commit'inami prieš `dvc repro`.

Kiekvienas mokymo run'as log'ina ir mokymosi kreivę: `train_size`, `val_accuracy`, `val_f1` per 5 žingsnius (20–100 % mokymo imties), o skirtuke System metrics matyti CPU, atminties, disko ir tinklo grafikai.

### 7. Modelių registras ir `@champion`

Kiekvienas `train.py` run'as registruoja naują `imdb-sentiment` versiją. API aptarnauja tik versiją su alias'u `@champion`.

```sh
python scripts/promote.py              # versija iš models/run_id.txt (paskutinis dvc repro)
python scripts/promote.py --version 2  # konkreti versija
```

MLflow UI → Models → `imdb-sentiment`: versijų sąrašas, `@champion` prie aptarnaujamos versijos.

### 8. Istorinio run'o atkūrimas

Reikia švaraus darbo medžio ir šakos (skriptas grįžta su `git checkout --force`). `<run_id>` matomas MLflow UI arba `models/run_id.txt`.

```sh
time python reproduce.py <run_id>
```

```
accuracy: original=0.9078 reproduced=0.9078 delta=0.0000
f1: original=0.9090 reproduced=0.9090 delta=0.0000
REPRODUCED in 23s -> new run d8ebe1c086734cbf88e0c60265d9ca95
```

### 9. Mokymo Docker vaizdas

Publikuotas vaizdas (amd64 + arm64) pasileidžia be build'o ir log'ina run'ą į klasterio MLflow. macOS/Windows Docker Desktop kompiuterį pasiekia per `host.docker.internal`; Linux pridėkite `--add-host=host.docker.internal:host-gateway`.
Vaizde tik mokymas (`train.py`), todėl tokio run'o metrikų nėra; jas skaičiuoja `evaluate` stage'as.

```sh
docker run --rm -e MLFLOW_TRACKING_URI=http://host.docker.internal:5050 \
  -e MLFLOW_TRACKING_USERNAME -e MLFLOW_TRACKING_PASSWORD ghcr.io/nojusbuc/mlops-u1/train:<sha-tag iš docs/docker-image.md>
```

Savas vaizdas, Trivy ir publikavimas į GHCR (reikia `gh auth refresh -h github.com -s write:packages,read:packages`):

```sh
SHA=$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$SHA -t mlops-u1/train:sha-$SHA .
trivy image -q --scanners vuln --severity HIGH,CRITICAL --format table -o docs/trivy-train.txt mlops-u1/train:sha-$SHA
trivy image -q --scanners vuln --severity CRITICAL --exit-code 1 mlops-u1/train:sha-$SHA
bash scripts/publish.sh
```

`scripts/publish.sh`: CRITICAL vartas, `docker login` su `gh` token'u, amd64 + arm64 vaizdas į `ghcr.io/<user>/mlops-u1/train:sha-<commit>`.
Inferencijos vaizdas (`docker/Dockerfile.serve`) publikuojamas taip pat: `docker build -f docker/Dockerfile.serve ... -t mlops-u1/serve:sha-$SHA .`, tada `bash scripts/publish.sh serve`.

### 10. Mokymas kaip Kubernetes Job

ConfigMap `training-config` duoda Job'ui MLflow adresą `http://mlflow:5000` (Service vardas klasteryje) ir hiperparametrus, Secret `mlflow-credentials` duoda MLflow naudotoją ir slaptažodį.

```sh
kubectl -n mlops-u1 delete job train --ignore-not-found
kubectl apply -f k8s/jobs/
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
kubectl -n mlops-u1 logs job/train
```

Sukurto Job'o keisti negalima, todėl prieš naują paleidimą senas ištrinamas. Kitas hiperparametras, pvz. `C: "1.0"` `k8s/jobs/configmap-training.yaml`, tada:

```sh
kubectl apply -f k8s/jobs/configmap-training.yaml
kubectl -n mlops-u1 delete job train
kubectl apply -f k8s/jobs/job-train.yaml
kubectl -n mlops-u1 wait --for=condition=complete job/train --timeout=600s
```

MLflow atsiranda run'as `tfidf-lr-C1.0-ng2` ir nauja registro versija.

### 11. Inferencijos API

FastAPI servisas (`src/serve/app.py`) paleidimo metu iš MLflow užsikrauna `imdb-sentiment@champion` ir turi du endpoint'us: `GET /health` (rodo modelio versiją) ir `POST /predict`. Champion nustatomas su `python scripts/promote.py`.

```sh
kubectl apply -f k8s/serving/
kubectl -n mlops-u1 get pods
kubectl -n mlops-u1 port-forward svc/inference 8080:80
```

Kitame terminale:

```sh
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/predict -H "Content-Type: application/json" -d '{"texts": ["Great movie!", "Waste of time"]}'
```

Modelis užkraunamas tik paleidžiant, todėl pakeitus `@champion` API reikia perkrauti: `kubectl -n mlops-u1 rollout restart deployment/inference`.

Apkrovos testas (port-forward turi veikti): `python scripts/load_test.py`. Rezultatai: [docs/load-test.md](docs/load-test.md).

### 12. CI

`.github/workflows/ci.yml` (GitHub Actions) kiekvienam push'ui į `main`: `ruff check` → `pytest` → inferencijos vaizdas (amd64 + arm64) į `ghcr.io/nojusbuc/mlops-u1/serve:sha-<commit>`. Build'as vyksta tik jei lint ir testai praėjo; pull request'uose tik lint ir testai.

Tie patys patikrinimai lokaliai:

```sh
ruff check src scripts tests reproduce.py
pytest
```

Testai MLflow nereikia: API testas vietoj `load_champion` naudoja netikrą modelį. Mokymo vaizdas CI nebuild'inamas, nes jame yra `data/processed/`, kurių nėra Git'e (DVC remote lokalus), todėl jis publikuojamas su `bash scripts/publish.sh`.

### 13. CD ir rollback

`.github/workflows/cd.yml` pasileidžia, kai `ci` sėkmingai baigiasi po push'o į `main` (arba ranka: Actions → cd → Run workflow). Vyksta self-hosted runner'yje šiame kompiuteryje, nes tik jis pasiekia kind klasterį, MLflow ir DVC duomenis:

1. `pytest`
2. `dvc pull data/raw.dvc` → `dvc repro` (naujas run'as ir modelio versija MLflow)
3. `python scripts/quality_gate.py`: `metrics.json` `accuracy` ≥ `params.yaml` `gate.min_accuracy`, kitaip workflow raudonas ir toliau nevykdoma
4. `python scripts/promote.py` → `@champion` = nauja versija
5. Manifeste atnaujinamas vaizdo tag'as `sha-<commit>` ir anotacija `model-version`
6. `kubectl apply -f k8s/serving/` → `rollout status` → `/health` patikra

Reikia: runner'is paleistas (`cd ~/actions-runner && ./run.sh`) ir repo secret'ai `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` (Settings → Secrets and variables → Actions).

Paleidimai: [žalias CI](https://github.com/nojusbuc/mlops-u1/actions/runs/43101766841), [žalias CD](https://github.com/nojusbuc/mlops-u1/actions/runs/43103153565), [raudonas CD](https://github.com/nojusbuc/mlops-u1/actions/runs/43105940052).

Raudonas paleidimas (vartas blokuoja deploy):

```sh
sed -i '' 's/min_accuracy: 0.88/min_accuracy: 0.99/' params.yaml
git commit -am "gate: raise threshold to 0.99"
git push
```

CD žingsnis `quality gate` baigiasi `FAIL`, tolesni žingsniai praleidžiami, `/health` rodo tą pačią versiją. Atstatymas: `0.99` → `0.88`, commit, push.

Rollback į ankstesnę modelio versiją:

```sh
python scripts/promote.py --version <ankstesnė versija>
kubectl -n mlops-u1 rollout restart deployment/inference
kubectl -n mlops-u1 rollout status deployment/inference
```

## Išvalymas ir persikrovimas

```sh
kind delete cluster --name mlops-u1
```

PVC (`postgres-data`, `mlflow-artifacts`) išlieka ištrynus Pod'us (`kubectl -n mlops-u1 delete pod -l app=mlflow`), bet dingsta kartu su klasteriu.
Po kompiuterio perkrovimo: `docker start mlops-u1-control-plane`, po minutės Pod'ai vėl `Running`, run'ai vietoje.

## Dažnos klaidos

| Klaida | Priežastis ir sprendimas |
| --- | --- |
| `MLFLOW_TRACKING_URI is not set` | Šiame terminale: `export MLFLOW_TRACKING_URI=http://127.0.0.1:5050` |
| `401 Unauthorized` iš MLflow | Šiame terminale neeksportuoti `MLFLOW_TRACKING_USERNAME` ir `MLFLOW_TRACKING_PASSWORD` (žr. 2 žingsnį) |
| `curl 127.0.0.1:5050` atmeta ryšį | MLflow Pod'as dar kyla (`kubectl -n mlops-u1 get pods`), arba klasteris sukurtas ne su `k8s/kind-config.yaml` (portų susiejimas nustatomas tik kuriant klasterį) |
| `port is already allocated` kuriant klasterį | 5050 užimtas: pakeiskite `hostPort` `k8s/kind-config.yaml` ir `MLFLOW_TRACKING_URI` |
| `403` / `Invalid Host header` iš MLflow | Kliento host'o nėra `--allowed-hosts` sąraše `k8s/mlflow/deployment-mlflow.yaml` |
| Job'as `ImagePullBackOff` | GHCR paketas privatus arba tag'as neegzistuoja: padarykite paketą viešą ir patikrinkite `image:` `k8s/jobs/job-train.yaml` |
| `inference` Pod'as `ImagePullBackOff` | GHCR paketas `mlops-u1/serve` privatus: padarykite jį viešą ir patikrinkite `image:` `k8s/serving/deployment-inference.yaml` |
| `inference` Pod'as lieka `0/1` | Žr. `kubectl -n mlops-u1 logs deployment/inference`: dažniausiai nenustatytas `@champion` (`python scripts/promote.py`) arba nėra Secret `mlflow-credentials` |
| `dvc: command not found` / `ModuleNotFoundError` | Neaktyvuotas venv: `source .venv/bin/activate` |
| `reproduce.py`: `Uncommitted changes` | Commit'inkite arba `git stash` pakeitimus |

## Duomenys ir licencija

- **Duomenys:** Maas, A. L., Daly, R. E., Pham, P. T., Huang, D., Ng, A. Y., & Potts, C. (2011). Learning Word Vectors for Sentiment Analysis. _ACL 2011_. Gauta per Hugging Face `stanfordnlp/imdb`, revizija `e6281661ce1c48d982bc483cf8a173c1bbeb5d31`. Naudojama mokymosi tikslais.
- **Kodas:** MIT, žr. [LICENSE](LICENSE). Rašyta kartu su Claude.

