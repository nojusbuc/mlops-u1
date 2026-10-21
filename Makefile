# Kiekvienas target'as atitinka README žingsnį. Naudojimas: make <target>
NS      := mlops-u1
PORT    := 5050
SHA     := $(shell git rev-parse --short=8 HEAD)
IMAGE   := mlops-u1/train:sha-$(SHA)
GHCR    := ghcr.io/nojusbuc/mlops-u1/train
REV     := e6281661ce1c48d982bc483cf8a173c1bbeb5d31
export MLFLOW_TRACKING_URI ?= http://127.0.0.1:$(PORT)

.PHONY: venv cluster secret mlflow up data repro reproduce image scan publish job clean

venv:
	uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt

cluster:
	kind create cluster --config k8s/kind-config.yaml

# Atsitiktinis slaptažodis tik klasterio Secret'e; idempotentiška (apply)
secret:
	kubectl apply -f k8s/namespace.yaml
	kubectl -n $(NS) create secret generic postgres-credentials \
	  --from-literal=POSTGRES_USER=mlflow --from-literal=POSTGRES_DB=mlflow \
	  --from-literal=POSTGRES_PASSWORD="$$(python3 -c 'import secrets; print(secrets.token_hex(16))')" \
	  --dry-run=client -o yaml | kubectl apply -f -

mlflow:
	kubectl apply -k k8s/
	kubectl -n $(NS) rollout status deploy/postgres --timeout=300s
	kubectl -n $(NS) rollout status deploy/mlflow --timeout=300s
	until curl -sf http://127.0.0.1:$(PORT)/health; do sleep 3; done; echo

up: cluster secret mlflow

# Duomenys: iš DVC remote, o jo nesant - iš Hugging Face fiksuotos revizijos
data:
	dvc pull data/raw.dvc || { \
	  curl -fsSL --create-dirs -o "data/raw/#1.parquet" \
	    "https://huggingface.co/datasets/stanfordnlp/imdb/resolve/$(REV)/plain_text/{train,test}-00000-of-00001.parquet" \
	  && dvc commit -f data/raw.dvc && git diff --exit-code data/raw.dvc; }

repro:
	dvc repro

reproduce:
	time python reproduce.py $(RUN)

image:
	docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=$(SHA) -t $(IMAGE) .

scan:
	trivy image -q --scanners vuln --severity HIGH,CRITICAL --format table -o docs/trivy-train.txt $(IMAGE)
	trivy image -q --scanners vuln --severity CRITICAL --exit-code 1 $(IMAGE)

publish:
	bash scripts/publish.sh

# TAG=sha-xxxxxxxx renkasi publikuotą vaizdą; be jo - vietinis vaizdas įkeliamas į kind
job:
	kubectl -n $(NS) delete job train --ignore-not-found
	kubectl apply -f k8s/jobs/configmap-training.yaml
	@if [ -z "$(TAG)" ]; then docker tag $(IMAGE) $(GHCR):sha-$(SHA) && kind load docker-image $(GHCR):sha-$(SHA) --name mlops-u1; fi
	sed 's|$(GHCR):sha-[0-9a-f]*|$(GHCR):$(or $(TAG),sha-$(SHA))|' k8s/jobs/job-train.yaml | kubectl apply -f -
	kubectl -n $(NS) wait --for=condition=complete job/train --timeout=600s
	kubectl -n $(NS) logs job/train | grep -E 'run_id|View run'

clean:
	kind delete cluster --name mlops-u1
