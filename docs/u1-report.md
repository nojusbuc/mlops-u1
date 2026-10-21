# U1 ataskaita

## Kas padaryta

- **R1:** struktūra `src/`, `docker/`, `k8s/`, `docs/`; README su paleidimu nuo nulio; `docs/requirements.md` v1.1: 5 FR, 9 NFR su KPI ir išmatuotomis reikšmėmis, tarp jų reprodukcijos NFR-04.
- **R2:** DVC pipeline'as `prepare → train → evaluate`; `params.yaml` su `prepare` ir `train` skyriais (abu stage'ai priklauso nuo savo parametrų); `dvc.lock` commit'intas po kiekvieno run'o; lokalus DVC remote `../mlops-u1-dvcstore`. 3 run'ai klasterio MLflow su `C` = 0,1 / 10 / 1 (accuracy 0,876 / 0,908 / 0,904). `reproduce.py` atkuria run'ą per 23 s, Δ = 0.
- **R3:** `docker/Dockerfile.train` (multi-stage, `mlflow-skinny`, UID 1000), rootfs 818 MB, Trivy CRITICAL 0 / HIGH 44 (`docs/docker-image.md`), GHCR tag `sha-<commit>`, amd64 + arm64.
- **R4:** `kind` klasteris (`k8s/kind-config.yaml`), namespace `mlops-u1`, PostgreSQL (backend store) ir MLflow (artefaktai per serverį į PVC), abu Deployment + Service + PVC; UI `127.0.0.1:5050` per NodePort be port-forward. Ištrynus abu Pod'us run'ai ir artefaktai išliko.
- **E2:** mokymas kaip Kubernetes Job (`k8s/jobs/`), hiperparametrai per ConfigMap, log'ina į `http://mlflow:5000`.

## Kas neveikė / ką teko spręsti

1. **Lėtas `log_model` (53 s iš 83 s):** MLflow spėliojo priklausomybes ir serializavo TF-IDF žodyną su `skops` (~40 s). Pataisyta aiškiu `pip_requirements`, signatūra ir `cloudpickle` formatu: `dvc repro` 83 → 24 s, todėl reprodukcija telpa į 2 min.
2. **Klaidingas `git_dirty=true`:** DVC prieš stage'ą ištrina savo išvestis (`models/run_id.txt`, sekamas Git), todėl `git status` rodė "nešvarų" medį. Dabar tikrinamos tik įvestys (`src`, `params.yaml`, `dvc.yaml`, `data/raw.dvc`, `requirements-train.txt`); run'ai perdaryti.
3. **Modelis iš MLflow grąžino vieną prognozę vietoj dviejų:** `TfidfVectorizer` gavęs DataFrame iteravo stulpelių pavadinimus. TF-IDF įdėtas į `ColumnTransformer` stulpeliui `text`; dabar `pyfunc` modelis teisingai priima `{"text": [...]}` (svarbu U2 serving'ui).
4. **Portas 5000 užimtas** macOS AirPlay Receiver: MLflow pasiekiamas per 5050.
5. **Dublikatai duomenyse:** 418 pasikartojančių atsiliepimų pašalinami prieš padalijimą (NFR-02).

## Kas nedaryta

E1 (autentifikacija), E3 (Terraform), E4 (GCS remote), E5 (GPU: Apple Silicon neturi NVIDIA GPU). Laikas skirtas branduoliui ir E2.

## Kiek laiko užtruko

~6 val, dalinai su Claude'u
